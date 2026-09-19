"""Consulta del catálogo ENS y derivación de aplicabilidad.

El catálogo es de **solo lectura** para todo el mundo (`docs/roles_y_permisos.md` §1):
aquí no hay escritura. La aplicabilidad se calcula, no se almacena.
"""

from __future__ import annotations

from typing import Literal

from apps.catalog.models import CatalogVersion, EnsMeasure
from apps.catalog.services import aplicabilidad_de
from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from engines.ens_applicability import Perfil
from engines.oscal_io.models import CATEGORIAS, NIVELES

router = Router()

Categoria = Literal["BASICA", "MEDIA", "ALTA"]
Nivel = Literal["NA", "BAJO", "MEDIO", "ALTO"]


class VersionOut(Schema):
    code: str
    oscal_version: str
    source_version: str
    source_sha256: str
    is_current: bool
    license: str
    source_url: str


class RefuerzoOut(Schema):
    code: str
    titulo: str
    opcional: bool
    aplicacion_por: str
    categorias: list[str]
    niveles: list[str]
    dimensiones: list[str]


class ItemOut(Schema):
    code: str
    label: str
    prose: str


class MeasureOut(Schema):
    code: str
    nombre: str
    marco: str
    familia: str
    aplicacion_por: str
    categorias: list[str]
    niveles: list[str]
    dimensiones: list[str]


class MeasureDetailOut(MeasureOut):
    overview: str
    refuerzos: list[RefuerzoOut]
    items: list[ItemOut]


class SeleccionOut(Schema):
    param_id: str
    measure_id: str
    nivel: str | None
    opciones: list[str]
    usage: str


class MedidaAplicableOut(Schema):
    measure_id: str
    marco: str
    familia: str
    motivo: str
    refuerzos_obligatorios: list[str]
    refuerzos_opcionales: list[str]
    refuerzos_no_aplicables: list[str]
    selecciones: list[SeleccionOut]


class AplicabilidadOut(Schema):
    categoria: str
    niveles: dict[str, str]
    total_aplicables: int
    aplicables: list[MedidaAplicableOut]
    no_aplicables: list[tuple[str, str]]
    selecciones_pendientes: list[SeleccionOut]


class PerfilIn(Schema):
    """Categoría y nivel por dimensión. Si no se da categoría, se deriva (Anexo I)."""

    categoria: Categoria | None = None
    C: Nivel = "NA"
    I: Nivel = "NA"  # noqa: E741 — es el código de la dimensión Integridad
    T: Nivel = "NA"
    A: Nivel = "NA"
    D: Nivel = "NA"

    def a_perfil(self) -> Perfil:
        niveles = {"C": self.C, "I": self.I, "T": self.T, "A": self.A, "D": self.D}
        if self.categoria:
            return Perfil(categoria=self.categoria, niveles=niveles)
        return Perfil.desde_niveles(niveles)


@router.get("/versions", response=list[VersionOut], summary="Versiones del catálogo")
def versions(request):
    return CatalogVersion.objects.all()


@router.get("/measures", response=list[MeasureOut], summary="Medidas del Anexo II")
def measures(request, marco: str | None = None, familia: str | None = None, q: str | None = None):
    version = CatalogVersion.current()
    if version is None:
        return []
    consulta = version.measures.all()
    if marco:
        consulta = consulta.filter(marco=marco)
    if familia:
        consulta = consulta.filter(familia=familia)
    if q:
        consulta = consulta.filter(nombre__icontains=q)
    return consulta


@router.get("/measures/{code}", response=MeasureDetailOut, summary="Detalle de una medida")
def measure(request, code: str):
    version = get_object_or_404(CatalogVersion, is_current=True)
    medida = get_object_or_404(EnsMeasure, catalog=version, code=code)
    return MeasureDetailOut(
        code=medida.code,
        nombre=medida.nombre,
        marco=medida.marco,
        familia=medida.familia,
        aplicacion_por=medida.aplicacion_por,
        categorias=medida.categorias,
        niveles=medida.niveles,
        dimensiones=medida.dimensiones,
        overview=medida.overview,
        refuerzos=[RefuerzoOut.from_orm(r) for r in medida.refuerzos.all()],
        items=[ItemOut.from_orm(i) for i in medida.items.all()],
    )


@router.post("/applicability", response=AplicabilidadOut, summary="Medidas aplicables a un sistema")
def applicability(request, perfil: PerfilIn):
    """Deriva medidas, refuerzos y selecciones pendientes. No guarda nada."""
    resultado = aplicabilidad_de(perfil.a_perfil())
    return AplicabilidadOut(
        categoria=resultado.perfil.categoria,
        niveles=resultado.perfil.niveles,
        total_aplicables=len(resultado.aplicables),
        aplicables=[
            MedidaAplicableOut(
                measure_id=m.measure_id,
                marco=m.marco,
                familia=m.familia,
                motivo=m.motivo,
                refuerzos_obligatorios=list(m.refuerzos_obligatorios),
                refuerzos_opcionales=list(m.refuerzos_opcionales),
                refuerzos_no_aplicables=list(m.refuerzos_no_aplicables),
                selecciones=[SeleccionOut(**vars(s)) for s in m.selecciones],
            )
            for m in resultado.aplicables
        ],
        no_aplicables=list(resultado.no_aplicables),
        selecciones_pendientes=[SeleccionOut(**vars(s)) for s in resultado.selecciones_pendientes],
    )


@router.get("/dimensiones", summary="Vocabulario de categorías y niveles")
def dimensiones(request):
    return {"categorias": list(CATEGORIAS), "niveles": list(NIVELES), "dimensiones": list("CITAD")}
