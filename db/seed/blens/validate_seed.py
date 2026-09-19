#!/usr/bin/env python3
"""Valida el seed propio de BLENS contra el catálogo OSCAL oficial. Se ejecuta en CI."""
import glob, itertools, json, os, sys, collections, yaml

OSCAL = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/ENS_Anexo_II_rev_9-copia.txt"
BASE = os.path.dirname(os.path.abspath(__file__))
# Las condiciones se evalúan con el motor de verdad, no con una imitación: lo que valide
# la CI y lo que luego vea el cliente tienen que salir del mismo código (engines/evidence_engine).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(BASE))))
from engines.evidence_engine import contexto_de_datos, plantillas_desde, preguntas_desde  # noqa: E402
from engines.evidence_engine.jsonlogic import ReglaInvalida, evaluar, hechos_citados  # noqa: E402
errs, warns = [], []

cat = json.load(open(OSCAL, encoding="utf-8"))["catalog"]
nodes = []
def walk(n):
    for c in n.get("groups", []) + n.get("controls", []):
        nodes.append(c); walk(c)
walk(cat)
ids = {n["id"] for n in nodes}
medidas = {n["id"] for n in nodes if n.get("class") not in ("family", "subfamily") and not n.get("groups") and n.get("class") != "ens-refuerzo"}
items = set()
def collect(parts):
    for p in parts or []:
        if p.get("name") == "item":
            lab = next((q["value"] for q in p.get("props", []) if q["name"] == "label"), None)
            if lab: items.add(lab)
        collect(p.get("parts"))
for n in nodes: collect(n.get("parts"))

def load(pattern):
    return {f: yaml.safe_load(open(f, encoding="utf-8")) for f in glob.glob(os.path.join(BASE, pattern))}

# --- preguntas: hechos emitidos vs usados
emits, used = set(), set()
def scan(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "var" and isinstance(v, str) and v.startswith("hechos."): used.add(v[7:])
            else: scan(v)
    elif isinstance(o, list):
        for i in o: scan(i)

questions = load("questions.*.yaml")
for f, doc in questions.items():
    for q in doc["questions"]:
        for opt in q.get("opciones") or []: emits |= set((opt.get("emits") or {}).keys())
        for c in q.get("campos") or []: emits.add(c["code"])
    scan(doc)

# --- plantillas de evidencia
templates, ev_codes = {}, set()
for f, doc in load("evidence_templates.*.yaml").items():
    scan(doc)
    for t in doc["templates"]:
        ev_codes.add(t["code"])
        templates[t["code"]] = t
        if t["measure"] not in ids: errs.append(f"{os.path.basename(f)}: medida inexistente {t['measure']} en {t['code']}")
        if t.get("refuerzo") and t["refuerzo"] not in ids: errs.append(f"{t['code']}: refuerzo inexistente {t['refuerzo']}")
        for campo in ("titulo", "instrucciones", "criterios_aceptacion", "carpeta_paquete"):
            if not t.get(campo): errs.append(f"{t['code']}: falta {campo}")
        if not t.get("vigencia_dias"): warns.append(f"{t['code']}: sin vigencia_dias")

for h in sorted(used - emits): errs.append(f"hecho usado y nunca emitido: {h}")

# --- alcanzabilidad: toda plantilla tiene que poder pedirse por algún camino (§15)
# No basta con que el hecho exista: hace falta que ALGUNA respuesta posible cumpla la
# condición. El caso que esto caza es la pregunta múltiple cuya clave paraguas solo emite
# la opción negativa: «si tienes soportes, aporta X» no se dispararía nunca.
valores = collections.defaultdict(set)
for doc in questions.values():
    for q in preguntas_desde(doc):
        for opcion in q.opciones:
            for clave, valor in (opcion.emits or {}).items():
                valores[clave].update(valor if isinstance(valor, list) else [valor])
        for campo in q.campos: valores[campo.code].update({0, 1, 100})
        for clave, valor in (q.emits or {}).items():
            valores[clave].add("2026-01-01" if valor == "$value" else valor)

def alcanzable(regla):
    citados = sorted(hechos_citados(regla))
    if not citados: return True
    combinaciones = [sorted(valores.get(c, {True, False}), key=str) for c in citados]
    if any(len(c) > 8 for c in combinaciones): return True   # demasiado abierto para explorarlo
    for combo in itertools.product(*combinaciones):
        hechos = dict(zip(citados, combo))
        for categoria, nivel in (("ALTA", "ALTO"), ("BASICA", "BAJO")):
            datos = contexto_de_datos(categoria, dict.fromkeys("CITAD", nivel), hechos).datos
            if evaluar(regla, datos): return True
    return False

for doc in load("evidence_templates.*.yaml").values():
    for t in plantillas_desde(doc):
        try:
            if not alcanzable(t.applies_if):
                errs.append(f"{t.code}: ninguna respuesta posible cumple su applies_if")
        except ReglaInvalida as error:
            errs.append(f"{t.code}: applies_if no evaluable ({error})")
for doc in questions.values():
    for q in preguntas_desde(doc):
        try:
            if not alcanzable(q.show_if):
                errs.append(f"{q.code}: ninguna respuesta posible cumple su show_if")
        except ReglaInvalida as error:
            errs.append(f"{q.code}: show_if no evaluable ({error})")

medidas_con_evidencia = {t["measure"] for t in templates.values()}
for m in sorted(medidas - medidas_con_evidencia): errs.append(f"medida sin ninguna plantilla de evidencia: {m}")

# --- grupos de opciones: preferencias únicas
for grupo, ts in collections.defaultdict(list, {g: [t for t in templates.values() if t.get("option_group") == g]
        for g in {t.get("option_group") for t in templates.values() if t.get("option_group")}}).items():
    prefs = [t.get("preferencia") for t in ts]
    if len(prefs) != len(set(prefs)): errs.append(f"grupo {grupo}: preferencias repetidas")

# --- checks
check_codes = set()
for f, doc in load("checks/checks.*.yaml").items():
    for c in doc["checks"]:
        if c["code"] in check_codes: errs.append(f"check duplicado: {c['code']}")
        check_codes.add(c["code"])
        if c["measure"] not in ids: errs.append(f"{c['code']}: medida inexistente")
        if c["item"] not in items: errs.append(f"{c['code']}: item inexistente {c['item']}")
        for e in c.get("evidencia_esperada") or []:
            if e not in ev_codes: errs.append(f"{c['code']}: evidencia inexistente {e}")
        if not c.get("evidencia_esperada"): warns.append(f"{c['code']}: sin evidencia asociada")

# --- MAGERIT
th = yaml.safe_load(open(os.path.join(BASE, "magerit/threats.yaml"), encoding="utf-8"))
at = yaml.safe_load(open(os.path.join(BASE, "magerit/asset_types.yaml"), encoding="utf-8"))
mp = yaml.safe_load(open(os.path.join(BASE, "magerit/measure_threat_map.yaml"), encoding="utf-8"))
tcodes = {t["code"] for t in th["threats"]}
acodes = {a["code"] for a in at["asset_types"]}
mapped = set()
for tc, entries in mp["map"].items():
    if tc not in tcodes: errs.append(f"mapa: amenaza inexistente {tc}")
    seen = set()
    for e in entries:
        mapped.add(e["measure"])
        key = (e["measure"], e["aspect"], e.get("dim"))
        if key in seen: errs.append(f"mapa {tc}: par duplicado {key}")
        seen.add(key)
        if e["measure"] not in ids: errs.append(f"mapa {tc}: medida inexistente {e['measure']}")
        if e["aspect"] not in ("FREQ", "IMPACT"): errs.append(f"mapa {tc}: aspecto inválido")
        if not 0 < e["weight"] <= 0.7: errs.append(f"mapa {tc}/{e['measure']}: peso fuera de rango")
for t in th["threats"]:
    if t["code"] not in mp["map"]: errs.append(f"amenaza sin salvaguardas: {t['code']}")
    for a in t["aplica_a"]:
        if a not in acodes: errs.append(f"{t['code']}: tipo de activo inexistente {a}")
    for dim in t["default_degradation"]:
        if dim not in t["dims"]: errs.append(f"{t['code']}: degradación en dimensión no declarada")
for m in sorted(medidas - mapped): errs.append(f"medida sin salvaguarda en el mapa MAGERIT: {m}")

# Eficacia por madurez: alimenta el riesgo residual, y tiene que cubrir L0-L5 y ser monótona.
me = yaml.safe_load(open(os.path.join(BASE, "magerit/maturity_effectiveness.yaml"), encoding="utf-8"))
niveles = {l["level"]: l["effectiveness"] for l in me["levels"]}
if sorted(niveles) != list(range(6)): errs.append(f"eficacia por madurez: faltan niveles {sorted(set(range(6)) - set(niveles))}")
if niveles.get(0) != 0: errs.append("eficacia por madurez: L0 tiene que valer 0")
if niveles.get(5) != 1: errs.append("eficacia por madurez: L5 tiene que valer 1")
for n in range(1, 6):
    if n in niveles and n - 1 in niveles and niveles[n] < niveles[n - 1]:
        errs.append(f"eficacia por madurez: L{n} no puede valer menos que L{n-1}")

print(f"medidas OSCAL: {len(medidas)} | items: {len(items)}")
print(f"preguntas: {sum(len(d['questions']) for d in questions.values())} | plantillas: {len(ev_codes)} | checks: {len(check_codes)}")
print(f"pares medida-amenaza: {sum(len(v) for v in mp['map'].values())}")
for w in warns[:15]: print("AVISO:", w)
if len(warns) > 15: print(f"... y {len(warns)-15} avisos más")
for e in errs: print("ERROR:", e)
print("RESULTADO:", "OK" if not errs else f"{len(errs)} ERRORES")
sys.exit(1 if errs else 0)
