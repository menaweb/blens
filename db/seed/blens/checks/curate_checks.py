#!/usr/bin/env python3
"""Genera checks curados por familia: esqueleto desde OSCAL + método heurístico + enlace a evidencias.
Uso: python curate_checks.py <oscal.json> <familia> [familia...]"""
import json, re, sys, os, yaml

BASE = os.path.dirname(os.path.abspath(__file__)); SEED = os.path.dirname(BASE)
DOC = r'procedimiento|normativa|polític|documentar|se documentará|plan |acuerdo|contrat|instrucci|aprobad|autorizad|designa|justificac'
TEC = r'se instalará|instalar|configurad|configurar|activar|se activarán|cifrad|registro|registros|herramienta|mecanismo|dispositiv|copia|análisis|escane|actualizad|inventario|red |equipos|acceso'
ENT = r'personal|responsable|formación|concienciación|usuarios|administrador'
PER = r'periódic|regularment|cada |anual|continuo|permanentemente|antes de|al menos una vez'

def prop(n, k): return next((p["value"] for p in n.get("props", []) if p["name"] == k), None)

def items(parts, acc, parent=None):
    for p in parts or []:
        if p.get("name") == "item":
            lab = prop(p, "label")
            acc.append((lab, (p.get("prose") or "").strip(), parent)); items(p.get("parts"), acc, lab)
        else:
            items(p.get("parts"), acc, parent)
    return acc

def metodo(t):
    m = []
    if re.search(TEC, t, re.I): m.append("INSPECCION_TECNICA")
    if re.search(DOC, t, re.I): m.append("DOCUMENTAL")
    if re.search(ENT, t, re.I) and not m: m.append("ENTREVISTA")
    if re.search(PER, t, re.I): m.append("MUESTREO")
    return m or ["DOCUMENTAL"]

def resumen(t):
    t = t.strip().rstrip(".")
    if len(t) > 220:
        t = (t[:220].rsplit(".", 1)[0] if "." in t[:220] else t[:220].rsplit(" ", 1)[0]) + "…"
    return t

def main():
    oscal, familias = sys.argv[1], sys.argv[2:]
    cat = json.load(open(oscal, encoding="utf-8"))["catalog"]; nodes = []
    def walk(n):
        for c in n.get("groups", []) + n.get("controls", []): nodes.append(c); walk(c)
    walk(cat)
    for fam in familias:
        import glob as _glob
        by_m, by_r = {}, {}
        ficheros = [x for x in _glob.glob(os.path.join(SEED, "evidence_templates.*.yaml"))
                    if fam.replace(".", "_") in os.path.basename(x)]
        for f in ficheros:
            for t in yaml.safe_load(open(f, encoding="utf-8"))["templates"]:
                (by_r.setdefault(t["refuerzo"], []) if t.get("refuerzo") else by_m.setdefault(t["measure"], [])).append(t["code"])
        out = [f"# Seed BLENS · Checks de verificación — familia {fam}",
               "# DERIVADOS de los requisitos atómicos (items) del catálogo OSCAL oficial (generate_checks_from_oscal.py).",
               "# `metodo` y `evidencia_esperada`: primera pasada automática. REVISAR contra CCN-STIC-808.",
               "version: 1", f"familia: {fam}", "checks:"]
        n = 0
        for node in nodes:
            nid = node.get("id", "")
            if not nid.startswith(fam + "."): continue
            ref = node.get("class") == "ens-refuerzo"; med = nid.split(".r")[0] if ref else nid
            for label, prose, parent in items(node.get("parts"), []):
                if not label: continue
                n += 1
                code = f"CHK-{parent}{label}" if parent and not label.startswith(med) else f"CHK-{label}"
                code = code.replace(")", "").rstrip(".")
                evs = by_r.get(nid, []) if ref else by_m.get(med, [])
                out += [f'  - code: "{code}"', f"    measure: {med}"]
                if ref: out.append(f"    refuerzo: {nid}")
                out.append(f'    item: "{label}"')
                if parent: out.append(f'    item_padre: "{parent}"')
                out.append('    descripcion: "' + resumen(prose).replace('"', '\\"') + '"')
                out.append(f"    metodo: [{', '.join(metodo(prose))}]")
                out.append("    evidencia_esperada: [" + ", ".join(evs) + "]")
        dest = os.path.join(BASE, f"checks.{fam.replace('.', '_')}.yaml")
        open(dest, "w", encoding="utf-8").write("\n".join(out) + "\n")
        print(f"{fam}: {n} checks → {os.path.basename(dest)}")

main()
