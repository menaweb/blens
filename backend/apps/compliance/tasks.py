"""Tareas Celery de cumplimiento. El render de PDF **nunca** va en la petición web (§15)."""

from __future__ import annotations

from config.celery import app
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone

from apps.compliance.models import (
    DeclaracionAplicabilidad,
    Dimension,
    InformeCategorizacion,
    Nivel,
)

NOMBRES_DIMENSION = dict(Dimension.choices)
NOMBRES_NIVEL = dict(Nivel.choices)
NOMBRES_MARCO = {
    "org": "Marco organizativo",
    "op": "Marco operacional",
    "mp": "Medidas de protección",
}


def render_pdf(plantilla: str, contexto: dict) -> bytes:
    """HTML de marca → PDF.

    WeasyPrint se importa aquí y no arriba: necesita pango y cairo del sistema, y no
    queremos que el backend entero deje de arrancar en una máquina que no los tenga.
    """
    from weasyprint import HTML

    html = render_to_string(
        plantilla, {"generado_en": timezone.now().strftime("%d/%m/%Y"), **contexto}
    )
    return HTML(string=html).write_pdf()


@app.task(name="compliance.render_categorizacion")
def render_categorizacion(informe_id: int) -> str:
    """Genera el PDF de la categorización (M1, también para quien no tiene cuenta)."""
    informe = InformeCategorizacion.objects.get(pk=informe_id)
    marcan = informe.resumen.get("dimensiones_que_marcan", [])

    contexto = {
        "informe": informe,
        "resumen": informe.resumen,
        "madurez_minima": {"BASICA": 2, "MEDIA": 3, "ALTA": 4}.get(informe.categoria, 0),
        "dimensiones_que_marcan": marcan,
        "nombres_que_marcan": ", ".join(NOMBRES_DIMENSION.get(d, d).lower() for d in marcan),
        "marcos": [
            {"nombre": NOMBRES_MARCO.get(marco, marco), "total": total}
            for marco, total in informe.resumen.get("por_marco", {}).items()
        ],
        "dimensiones": [
            {
                "nombre": NOMBRES_DIMENSION.get(dim, dim),
                "nivel": informe.niveles.get(dim, "NA"),
                "etiqueta": NOMBRES_NIVEL.get(informe.niveles.get(dim, "NA"), "No aplica"),
                "marca": dim in marcan,
            }
            for dim in ("C", "I", "T", "A", "D")
        ],
    }
    try:
        pdf = render_pdf("pdf/categorizacion.html", contexto)
    except Exception:
        InformeCategorizacion.objects.filter(pk=informe_id).update(estado="ERROR")
        raise

    informe.pdf.save(f"categorizacion-{informe.token}.pdf", ContentFile(pdf), save=False)
    informe.estado = "LISTO"
    informe.save(update_fields=["pdf", "estado"])
    return informe.pdf.name


@app.task(name="compliance.render_dda")
def render_dda(dda_id: int) -> int:
    """Genera el PDF de la Declaración de Aplicabilidad (M2)."""
    dda = DeclaracionAplicabilidad.objects.select_related("system", "catalog").get(pk=dda_id)
    medidas = list(dda.medidas.select_related("measure"))
    aplican = [m for m in medidas if m.aplica]

    pdf = render_pdf(
        "pdf/dda.html",
        {
            "dda": dda,
            "aplican": aplican,
            "no_aplican": [m for m in medidas if not m.aplica],
            "total_aplican": len(aplican),
            "total_no_aplican": len(medidas) - len(aplican),
            "total_refuerzos": sum(len(m.refuerzos_obligatorios) for m in aplican),
        },
    )
    return len(pdf)


@app.task(name="compliance.limpiar_categorizaciones_caducadas")
def limpiar_categorizaciones_caducadas() -> int:
    """Borra las categorizaciones anónimas caducadas: son datos de quien aún no es cliente."""
    caducadas = InformeCategorizacion.objects.filter(
        tenant__isnull=True, expira_en__lte=timezone.now()
    )
    total = caducadas.count()
    caducadas.delete()
    return total
