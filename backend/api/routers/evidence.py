"""Carpeta de evidencias (M5): los huecos, lo que se aporta y lo que se revisa.

La carpeta se enseña **entera desde el primer día**, con sus huecos a la vista: es lo que
convierte «cumplir el ENS» en una lista de cosas que alguien puede hacer esta semana. Cada
hueco dice qué aportar, qué tiene que verse, por qué se pide y qué suele rechazar un
auditor, y trae la ruta concreta del producto que el cliente ya ha declarado.

Nada de esto decide nada: la carpeta la deriva `engines.evidence_engine` y la escribe
`apps.evidence.services`.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from apps.compliance.models import System
from apps.evidence.models import EstadoRequisito, EvidenceRequirement, Evidencia
from apps.evidence.services import (
    aportar,
    grupos_cubiertos,
    marcar_no_aplica,
    recalcular,
    rechazar,
    validar,
)
from apps.profiling.models import ProfileFact
from apps.tenancy.permissions import require
from django.shortcuts import get_object_or_404
from ninja import File, Form, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile

from api.auth import blens_auth

router = Router(auth=blens_auth)

#: Tamaño máximo de una evidencia. Una captura o un PDF no pasan de aquí; lo que pasa
#: suele ser un vídeo o un volcado que nadie va a auditar.
MAXIMO_BYTES = 50 * 1024 * 1024


class EvidenciaOut(Schema):
    id: int
    titulo: str
    nombre_original: str
    fecha_evidencia: date
    estado: str
    motivo_rechazo: str
    aportada_por: str
    url: str | None


class RequisitoOut(Schema):
    id: int
    code: str
    measure: str
    familia: str
    marco: str
    titulo: str
    instrucciones: str
    tipo: str
    formatos: list[str]
    #: Lo que el revisor marcará; quien sube ya sabe por dónde se lo van a mirar.
    criterios_aceptacion: list[str]
    rechazos_tipicos: list[str]
    #: Dónde sacarla en los productos que este cliente ha declarado.
    pistas: list[str]
    obligatoria: bool
    generable: bool
    vigencia_dias: int | None
    carpeta_paquete: str
    estado: str
    #: Por qué se pide, en una frase, y con qué respuesta del perfilado.
    motivo: str
    origen: dict[str, Any]
    option_group: str
    #: Otras formas igual de válidas de cubrir esto, de más a menos sólida.
    alternativas: list[str]
    #: True cuando otra alternativa del grupo ya lo cubre: entonces no es un hueco.
    cubierto_por_grupo: bool
    responsable_id: int | None
    fecha_limite: date | None
    proxima_renovacion: date | None
    justificacion: str
    evidencias: list[EvidenciaOut]


class CarpetaOut(Schema):
    system_id: int
    sistema: str
    categoria: str
    requisitos: list[RequisitoOut]
    #: Lo que de verdad falta, sin contar lo que ya cubre otra alternativa.
    huecos: int
    obligatorios: int
    completitud: float
    por_familia: dict[str, dict[str, int]]


def _productos_declarados(system: System) -> set[str]:
    nombres: set[str] = set()
    for fila in ProfileFact.objects.filter(system=system, key__startswith="herramienta_"):
        valores = fila.value if isinstance(fila.value, list) else [fila.value]
        nombres |= {str(v).lower() for v in valores if v}
    return nombres


def _pistas(requisito: EvidenceRequirement, productos: set[str]) -> list[str]:
    """Solo las pistas de lo que este cliente usa: el resto es ruido."""
    salida = []
    for pista in requisito.template.pistas_por_producto.all():
        buscado = str(pista.producto_match.get("producto", "")).lower()
        if buscado and any(buscado in producto or producto in buscado for producto in productos):
            salida.append(pista.instrucciones)
    return salida


def _evidencia_out(evidencia: Evidencia) -> EvidenciaOut:
    quien = evidencia.aportada_por
    return EvidenciaOut(
        id=evidencia.pk,
        titulo=evidencia.titulo,
        nombre_original=evidencia.nombre_original,
        fecha_evidencia=evidencia.fecha_evidencia,
        estado=evidencia.estado,
        motivo_rechazo=evidencia.motivo_rechazo,
        aportada_por=(quien.get_full_name() or quien.username) if quien else "",
        url=evidencia.fichero.url if evidencia.fichero else None,
    )


def _carpeta(system: System) -> CarpetaOut:
    cubiertos = grupos_cubiertos(system)
    productos = _productos_declarados(system)
    requisitos = (
        EvidenceRequirement.objects.filter(system=system)
        .select_related("template", "template__measure")
        .prefetch_related("evidencias__aportada_por", "template__pistas_por_producto")
    )
    alternativas: dict[str, list[EvidenceRequirement]] = {}
    for requisito in requisitos:
        if requisito.template.option_group:
            alternativas.setdefault(requisito.template.option_group, []).append(requisito)

    filas, huecos, obligatorios = [], 0, 0
    por_familia: dict[str, dict[str, int]] = {}
    for requisito in requisitos:
        plantilla = requisito.template
        grupo = plantilla.option_group
        cubierto_por_grupo = (
            bool(grupo) and grupo in cubiertos and not requisito.cuenta_como_cubierto
        )
        es_hueco = not requisito.cuenta_como_cubierto and not cubierto_por_grupo

        familia = plantilla.measure.familia
        cuenta = por_familia.setdefault(familia, {"total": 0, "huecos": 0})
        cuenta["total"] += 1
        if es_hueco:
            cuenta["huecos"] += 1
            huecos += 1
        if plantilla.obligatoria and requisito.estado != EstadoRequisito.FUERA_DE_ALCANCE:
            obligatorios += 1

        filas.append(
            RequisitoOut(
                id=requisito.pk,
                code=plantilla.code,
                measure=plantilla.measure.code,
                familia=familia,
                marco=plantilla.measure.marco,
                titulo=plantilla.titulo,
                instrucciones=plantilla.instrucciones,
                tipo=plantilla.tipo,
                formatos=plantilla.formatos or [],
                criterios_aceptacion=plantilla.criterios_aceptacion or [],
                rechazos_tipicos=plantilla.rechazos_tipicos or [],
                pistas=_pistas(requisito, productos),
                obligatoria=plantilla.obligatoria,
                generable=plantilla.generable,
                vigencia_dias=plantilla.vigencia_dias,
                carpeta_paquete=plantilla.carpeta_paquete,
                estado=requisito.estado,
                motivo=requisito.motivo,
                origen=requisito.origen or {},
                option_group=grupo,
                alternativas=[
                    otro.template.code
                    for otro in sorted(
                        alternativas.get(grupo, []), key=lambda r: r.template.preferencia
                    )
                    if otro.pk != requisito.pk
                ],
                cubierto_por_grupo=cubierto_por_grupo,
                responsable_id=requisito.responsable_id,
                fecha_limite=requisito.fecha_limite,
                proxima_renovacion=requisito.proxima_renovacion,
                justificacion=requisito.justificacion,
                evidencias=[_evidencia_out(e) for e in requisito.evidencias.all()],
            )
        )

    total = len(filas)
    return CarpetaOut(
        system_id=system.pk,
        sistema=system.nombre,
        categoria=system.categoria,
        requisitos=filas,
        huecos=huecos,
        obligatorios=obligatorios,
        # Nunca redondea al alza: lo que falta, falta (`docs/competencia_y_ux.md` §3).
        completitud=round((total - huecos) / total * 100, 1) if total else 0.0,
        por_familia=por_familia,
    )


@router.get(
    "/systems/{system_id}/evidence", response=CarpetaOut, summary="Carpeta de evidencias (M5)"
)
def carpeta(request, system_id: int):
    """La carpeta a medida de este sistema, con sus huecos y por qué está cada uno."""
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "evidencia.leer", system)
    return _carpeta(system)


@router.post(
    "/systems/{system_id}/evidence/recalcular",
    response=CarpetaOut,
    summary="Rehacer la carpeta con el perfil de hoy",
)
def recalcular_carpeta(request, system_id: int):
    """Vuelve a derivarla. Idempotente, y nunca borra lo aportado."""
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "evidencia.aportar", system)
    recalcular(system)
    return _carpeta(system)


@router.post(
    "/systems/{system_id}/evidence/{requisito_id}/evidencias",
    response=CarpetaOut,
    summary="Aportar una evidencia",
)
def aportar_evidencia(
    request,
    system_id: int,
    requisito_id: int,
    fichero: UploadedFile = File(...),
    fecha_evidencia: date = Form(...),
    titulo: str = Form(""),
    notas: str = Form(""),
    criterios: str = Form(""),
    otros_requisitos: str = Form(""),
):
    """Sube el fichero y lo enlaza a este requisito y a los demás que cierre.

    `fecha_evidencia` es la del **hecho** (cuándo se hizo la prueba), no la de subida: es
    la que mira el auditor y la que manda la caducidad.
    """
    system = get_object_or_404(System, pk=system_id)
    requisito = get_object_or_404(EvidenceRequirement, pk=requisito_id, system=system)
    require(request.user, "evidencia.aportar", requisito)

    if fichero.size > MAXIMO_BYTES:
        raise HttpError(413, "La evidencia no puede pasar de 50 MB.")

    digest = hashlib.sha256()
    for trozo in fichero.chunks():
        digest.update(trozo)
    fichero.seek(0)

    requisitos = [requisito]
    if otros_requisitos:
        pedidos = [int(x) for x in otros_requisitos.split(",") if x.strip().isdigit()]
        requisitos += list(
            EvidenceRequirement.objects.filter(pk__in=pedidos, system=system).exclude(
                pk=requisito.pk
            )
        )

    aportar(
        system,
        requisitos,
        fichero=fichero,
        fecha_evidencia=fecha_evidencia,
        usuario=request.user,
        titulo=titulo,
        nombre_original=fichero.name,
        content_type=fichero.content_type or "",
        tamano=fichero.size,
        sha256=digest.hexdigest(),
        notas=notas,
        criterios_marcados=[c for c in criterios.split("|") if c],
    )
    return _carpeta(system)


class RevisionIn(Schema):
    motivo: str = ""


@router.post(
    "/systems/{system_id}/evidencias/{evidencia_id}/validar",
    response=CarpetaOut,
    summary="Validar una evidencia",
)
def validar_evidencia(request, system_id: int, evidencia_id: int):
    """Quien la aportó no puede validarla, aunque sea RSEG: lo impide `can()` (§15)."""
    system = get_object_or_404(System, pk=system_id)
    evidencia = get_object_or_404(Evidencia, pk=evidencia_id, system=system)
    require(request.user, "evidencia.validar", evidencia)
    validar(evidencia, request.user)
    return _carpeta(system)


@router.post(
    "/systems/{system_id}/evidencias/{evidencia_id}/rechazar",
    response=CarpetaOut,
    summary="Rechazar una evidencia con motivo",
)
def rechazar_evidencia(request, system_id: int, evidencia_id: int, datos: RevisionIn):
    """El motivo es obligatorio y concreto: «no se ve la fecha», no «no vale»."""
    system = get_object_or_404(System, pk=system_id)
    evidencia = get_object_or_404(Evidencia, pk=evidencia_id, system=system)
    require(request.user, "evidencia.rechazar", evidencia)
    try:
        rechazar(evidencia, request.user, datos.motivo)
    except ValueError as error:
        raise HttpError(422, str(error)) from error
    return _carpeta(system)


class NoAplicaIn(Schema):
    justificacion: str


@router.post(
    "/systems/{system_id}/evidence/{requisito_id}/no-aplica",
    response=CarpetaOut,
    summary="Marcar un requisito como no aplicable",
)
def no_aplica(request, system_id: int, requisito_id: int, datos: NoAplicaIn):
    """No aplica ≠ pendiente. Se puede descartar, pero queda escrito en el paquete."""
    system = get_object_or_404(System, pk=system_id)
    requisito = get_object_or_404(EvidenceRequirement, pk=requisito_id, system=system)
    require(request.user, "evidencia.validar", requisito)
    try:
        marcar_no_aplica(requisito, datos.justificacion)
    except ValueError as error:
        raise HttpError(422, str(error)) from error
    return _carpeta(system)
