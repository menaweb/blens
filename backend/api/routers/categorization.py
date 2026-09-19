"""Categorización del Anexo I (M1). **Se usa sin cuenta**: es la puerta del producto.

No hay autenticación aquí a propósito. Lo que se guarda de una categorización anónima
caduca (§ `services.DIAS_CADUCIDAD_ANONIMA`), porque son datos de quien todavía no es
cliente.
"""

from __future__ import annotations

from typing import Literal

from apps.compliance.models import Dimension, InformeCategorizacion, Nivel
from apps.compliance.services import categorizar, crear_informe, resumen
from apps.compliance.tasks import render_categorizacion
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

router = Router()

NivelIn = Literal["NA", "BAJO", "MEDIO", "ALTO"]
MADUREZ = {"BASICA": 2, "MEDIA": 3, "ALTA": 4}


class NivelesIn(Schema):
    C: NivelIn = "NA"
    I: NivelIn = "NA"  # noqa: E741 — código de la dimensión Integridad
    T: NivelIn = "NA"
    A: NivelIn = "NA"
    D: NivelIn = "NA"

    def como_dict(self) -> dict[str, str]:
        return {"C": self.C, "I": self.I, "T": self.T, "A": self.A, "D": self.D}


class InformeIn(NivelesIn):
    organizacion: str = ""
    alcance: str = ""


class DimensionOut(Schema):
    dim: str
    nombre: str
    nivel: str
    marca_categoria: bool


class CategorizacionOut(Schema):
    categoria: str  # vacío = sin determinar
    sin_determinar: bool
    aviso: str = ""
    madurez_minima: int
    requiere_certificacion: bool
    dimensiones: list[DimensionOut]
    resumen: dict


def _respuesta(niveles: dict[str, str]) -> CategorizacionOut:
    perfil, resultado = categorizar(niveles)
    cifras = resumen(resultado)
    marcan = cifras["dimensiones_que_marcan"]
    sin_determinar = not perfil.categoria

    return CategorizacionOut(
        categoria=perfil.categoria,
        sin_determinar=sin_determinar,
        aviso=(
            "Las cinco dimensiones están en «no aplica», así que no hay categoría. "
            "Suele significar que el alcance está mal delimitado."
            if sin_determinar
            else ""
        ),
        madurez_minima=MADUREZ.get(perfil.categoria, 0),
        # Básica se resuelve con autoevaluación; Media y Alta exigen entidad acreditada (art. 38).
        requiere_certificacion=perfil.categoria in ("MEDIA", "ALTA"),
        dimensiones=[
            DimensionOut(
                dim=dim,
                nombre=dict(Dimension.choices)[dim],
                nivel=niveles.get(dim, "NA"),
                marca_categoria=dim in marcan,
            )
            for dim in ("C", "I", "T", "A", "D")
        ],
        resumen={} if sin_determinar else cifras,
    )


@router.post("/preview", response=CategorizacionOut, auth=None, summary="Categorizar (sin cuenta)")
def preview(request, niveles: NivelesIn):
    """Categoría y cifras. No guarda nada: es lo que responde el asistente de 5 pasos."""
    return _respuesta(niveles.como_dict())


class InformeOut(Schema):
    token: str
    categoria: str
    estado: str
    descarga: str


@router.post("/report", response=InformeOut, auth=None, summary="Pedir el PDF del resultado")
def report(request, datos: InformeIn):
    """Crea el informe y **encola** el PDF: el render no va en la petición web."""
    informe = crear_informe(
        datos.como_dict(), organizacion=datos.organizacion, alcance=datos.alcance
    )
    render_categorizacion.delay(informe.pk)
    return InformeOut(
        token=str(informe.token),
        categoria=informe.categoria,
        estado=informe.estado,
        descarga=f"/api/categorization/report/{informe.token}/pdf",
    )


@router.get("/report/{token}", response=InformeOut, auth=None, summary="Estado del PDF")
def report_status(request, token: str):
    informe = get_object_or_404(InformeCategorizacion, token=token)
    if informe.caducado:
        raise Http404("El informe ha caducado.")
    return InformeOut(
        token=str(informe.token),
        categoria=informe.categoria,
        estado=informe.estado,
        descarga=f"/api/categorization/report/{informe.token}/pdf",
    )


@router.get(
    "/report/{token}/pdf", auth=None, url_name="categorizacion_pdf", summary="Descargar el PDF"
)
def report_pdf(request, token: str):
    informe = get_object_or_404(InformeCategorizacion, token=token)
    if informe.caducado or not informe.pdf:
        raise Http404("El PDF no está disponible.")
    return FileResponse(
        informe.pdf.open("rb"),
        as_attachment=True,
        filename=f"categorizacion-ENS-{informe.categoria or 'sin-determinar'}.pdf",
        content_type="application/pdf",
    )


@router.get("/vocabulario", auth=None, summary="Dimensiones y niveles")
def vocabulario(request):
    return {
        "dimensiones": [{"code": c, "nombre": n} for c, n in Dimension.choices],
        "niveles": [{"code": c, "nombre": n} for c, n in Nivel.choices],
    }
