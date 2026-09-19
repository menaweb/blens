#!/usr/bin/env python3
"""
Genera el esqueleto de checks de verificación a partir de los requisitos atómicos
(items) del catálogo OSCAL oficial del Anexo II.

Por qué así: la CCN-STIC-808 describe cómo verifica el auditor, pero el desglose
atómico de cada medida ya está en el catálogo oficial (467 items con su numeración
literal). Derivar de ahí garantiza cobertura total y trazabilidad al texto de la norma,
sin inventar checks ni reproducir una guía con licencia restrictiva.

Uso:
    python generate_checks_from_oscal.py db/seed/oscal/ENS_Anexo_II.json op.exp \
        > db/seed/blens/checks/checks.op_exp.skeleton.yaml

Después se CURA a mano: método de verificación, evidencia esperada y enlace con las
plantillas de evidencia. El esqueleto no se usa directamente en producción.
"""
import json
import sys


def walk(node, out):
    for child in node.get("groups", []) + node.get("controls", []):
        out.append(child)
        walk(child, out)


def prop(node, name):
    return next((p["value"] for p in node.get("props", []) if p["name"] == name), None)


def items(parts, acc, parent=None):
    """Recorre los parts 'requisitos' → 'item' anidados y devuelve (label, prose, parent)."""
    for part in parts or []:
        if part.get("name") == "item":
            label = prop(part, "label")
            acc.append((label, (part.get("prose") or "").strip(), parent))
            items(part.get("parts"), acc, label)
        else:
            items(part.get("parts"), acc, parent)
    return acc


def yaml_text(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    path, familia = sys.argv[1], sys.argv[2]
    catalog = json.load(open(path, encoding="utf-8"))["catalog"]
    nodes: list = []
    walk(catalog, nodes)

    print("# ESQUELETO generado por generate_checks_from_oscal.py — CURAR A MANO antes de usar.")
    print(f"# Familia: {familia} · Fuente: catálogo OSCAL oficial del Anexo II (items = requisitos atómicos)")
    print("version: 1")
    print(f"familia: {familia}")
    print("checks:")

    total = 0
    for node in nodes:
        node_id = node.get("id", "")
        if not node_id.startswith(familia + "."):
            continue
        es_refuerzo = node.get("class") == "ens-refuerzo"
        medida = node_id.split(".r")[0] if es_refuerzo else node_id
        for label, prose, parent in items(node.get("parts"), []):
            if not label:
                continue
            total += 1
            code = f"{parent}{label}" if parent and not label.startswith(medida) else label
            print(f"  - code: {yaml_text('CHK-' + code.replace(')', '').rstrip('.'))}")
            print(f"    measure: {medida}")
            if es_refuerzo:
                print(f"    refuerzo: {node_id}")
            print(f"    item: {yaml_text(label)}")
            if parent:
                print(f"    item_padre: {yaml_text(parent)}")
            print(f"    requisito: {yaml_text(prose)}")
            print("    # --- a curar ---")
            print("    descripcion: TODO        # qué comprueba el auditor, en una frase")
            print("    metodo: TODO             # DOCUMENTAL | ENTREVISTA | INSPECCION_TECNICA | MUESTREO")
            print("    evidencia_esperada: []   # códigos de EvidenceTemplate que lo demuestran")
        # separador visual por medida
    print(f"# total de checks generados: {total}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
