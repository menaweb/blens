"""Prototipo v2: fichas CCN-STIC-105 con pdfplumber (nombre = celda de cabecera azul; etiquetas en negrita)."""
import re, sys, json, collections
import pdfplumber

FIELDS = ["Versión", "Fabricante", "Familia", "Tipo", "Categoría ENS", "Clasificación",
          "Fecha Inclusión", "Revisión de Validez"]
BLOCKS = ["Descripción", "Observaciones"]
APARTADO = {"7": "CUALIFICADO", "8": "APROBADO", "9": "CONFORMIDAD_GOBERNANZA"}
SEC = re.compile(r"^(\d{1,2})(?:\.\d{1,2}){0,2}\.?\s+\S")
BLUE = (0.18, 0.455, 0.71)
TOP_MARGIN, BOTTOM_MARGIN = 40, 760

def is_blue(c):
    return isinstance(c, (tuple, list)) and len(c) == 3 and all(abs(a - b) < 0.02 for a, b in zip(c, BLUE))

def split_label(line):
    bold = "".join(ch["text"] for ch in line["chars"] if "Bold" in ch["fontname"]).strip()
    lab = next((f for f in FIELDS + BLOCKS if re.sub(r"\s", "", bold).startswith(re.sub(r"\s", "", f))), None)
    if not lab:
        return None, line["text"].strip()
    val = line["text"].strip()[len(lab):].strip()
    return lab, val

def parse(pdf_path, start_page=12):
    rows, cur, sec, block = [], None, {}, None
    pending_field_vals = []   # valores sueltos (texto partido) en la zona de campos
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            if pno < start_page:
                continue
            heads = [r for r in page.rects if is_blue(r.get("non_stroking_color")) and r["height"] >= 10 and r["width"] > 150]
            lines = [l for l in page.extract_text_lines(return_chars=True) if TOP_MARGIN < l["top"] < BOTTOM_MARGIN]
            name_buf = []
            # pre-cálculo: etiqueta de cada línea y zona
            info = []
            for l in lines:
                txt = l["text"].strip()
                mid = (l["top"] + l["bottom"]) / 2
                in_head = any(r["top"] - 1 <= mid <= r["bottom"] + 1 for r in heads)
                lab, val = (None, txt) if in_head else split_label(l)
                info.append((l, txt, mid, in_head, lab, val))
            def nearest_field_label(i):
                """Para un valor partido, la etiqueta de campo más cercana en vertical dentro del mismo bloque."""
                best, bd = None, 1e9
                for step in (-1, 1):
                    j = i + step
                    while 0 <= j < len(info):
                        _, _, mj, hj, lj, _ = info[j]
                        if hj or lj in BLOCKS: break
                        if lj in FIELDS:
                            d = abs(mj - info[i][2])
                            if d < bd: best, bd = j, d
                            break
                        j += step
                return best
            deferred = {}   # índice de línea-etiqueta -> fragmentos (con posición)
            for i, (l, txt, mid, in_head, lab, val) in enumerate(info):
                if txt == "INFORMACIÓN IMPORTANTE":
                    continue
                bold_all = all("Bold" in c["fontname"] for c in l["chars"] if c["text"].strip())
                m = SEC.match(txt)
                if bold_all and m and txt.upper() == txt and not in_head:
                    if m.group(1) in ("10", "11"):
                        return rows
                    if m.group(1) in APARTADO:
                        level = txt.split()[0].rstrip(".")
                        sec = {**sec, "apartado": APARTADO[m.group(1)]}
                        if level.count(".") == 1:
                            sec["grupo"] = txt; sec.pop("seccion", None)
                        else:
                            sec["seccion"] = txt
                    continue
                if in_head:
                    name_buf.append(txt)
                    continue
                if lab is None and block == "fields" or (lab is None and i + 1 < len(info) and info[i+1][4] == "Versión"):
                    j = nearest_field_label(i)
                    if j is not None:
                        deferred.setdefault(j, []).append((mid, txt))
                        continue
                if lab == "Versión":
                    cur = {"nombre": " ".join(name_buf), "source_page": pno, **sec,
                           "fields": {}, "descripcion": "", "observaciones": "", "warnings": []}
                    if not name_buf: cur["warnings"].append("sin_cabecera")
                    name_buf, block = [], "fields"
                    rows.append(cur)
                if cur is None:
                    continue
                if lab in FIELDS:
                    parts = [(mid, val)] if val else []
                    parts += deferred.pop(i, [])
                    # fragmentos posteriores se añaden cuando aparezcan
                    cur["fields"][lab] = " ".join(t for _, t in sorted(parts)).strip()
                    cur.setdefault("_pos", {})[lab] = (i, parts)
                    block = "fields"
                elif lab in BLOCKS:
                    block = lab
                elif block in BLOCKS:
                    k = "descripcion" if block == "Descripción" else "observaciones"
                    cur[k] = (cur[k] + " " + txt).strip()
            # fragmentos que quedaron por debajo de su etiqueta
            for j, frs in deferred.items():
                for r in rows[::-1]:
                    pos = r.get("_pos", {})
                    hit = [k for k, (ii, _) in pos.items() if ii == j and r["source_page"] == pno]
                    if hit:
                        k = hit[0]; ii, parts = pos[k]; parts = parts + frs; pos[k] = (ii, parts)
                        r["fields"][k] = " ".join(t for _, t in sorted(parts)).strip()
                        break
            for r in rows:
                r.pop("_pos", None)
    return rows

DATE = re.compile(r"\d{2}/\d{2}/\d{4}")
def quality(r):
    f = r["fields"]; probs = list(r.get("warnings", []))
    for k in ("Fabricante", "Familia", "Tipo", "Fecha Inclusión", "Revisión de Validez"):
        if not f.get(k): probs.append(k)
    if r["apartado"] == "CUALIFICADO" and not f.get("Categoría ENS"): probs.append("Categoría ENS")
    if r["apartado"] == "APROBADO" and not f.get("Clasificación"): probs.append("Clasificación")
    for k in ("Fecha Inclusión", "Revisión de Validez"):
        if f.get(k) and not DATE.fullmatch(f[k]): probs.append(k + ":formato")
    if f.get("Tipo") not in ("Producto", "Servicio"): probs.append("Tipo:valor")
    return probs

if __name__ == "__main__":
    rows = parse(sys.argv[1])
    json.dump(rows, open("cpstic_rows_v2.json", "w"), ensure_ascii=False, indent=1)
    bad = [(r, quality(r)) for r in rows if quality(r)]
    print("fichas:", len(rows), dict(collections.Counter(r["apartado"] for r in rows)))
    print("con problemas:", len(bad))
    for r, q in bad[:20]: print(" p", r["source_page"], r["nombre"][:60], q, r["fields"])
