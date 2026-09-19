"""La carpeta de evidencias: derivarla, llenarla, revisarla y saber qué falta.

El reparto es el de siempre (§15): decide `engines.evidence_engine`, que es puro; escribe
esto. Aquí no hay ni una condición del seed interpretada a mano.

Lo que sostiene el producto está en `recalcular`: el cliente cambia una respuesta y la
carpeta se rehace **sin perder nada**. Lo que deja de aplicar se aparta con sus ficheros
dentro, y si la respuesta vuelve atrás, el requisito vuelve con lo que ya tenía.
"""

from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import CatalogVersion, EvidenceTemplate
from apps.catalog.motor import plantillas_del_catalogo
from apps.compliance.services import aplicabilidad_del_sistema, refuerzos_del_sistema
from apps.evidence.models import EstadoEvidencia, EstadoRequisito, EvidenceRequirement, Evidencia
from engines.evidence_engine import Reconciliacion, derivar_requisitos, reconciliar

#: Estados en los que un requisito ya no es un hueco que perseguir.
CUBIERTOS = (
    EstadoRequisito.VALIDADA,
    EstadoRequisito.FUERA_DE_ALCANCE,
    EstadoRequisito.NO_APLICA_JUSTIFICADO,
)

#: A partir de L2 la madurez declarada tiene que poder demostrarse (§10bis.3).
MADUREZ_QUE_EXIGE_EVIDENCIA = 2


@transaction.atomic
def recalcular(system) -> Reconciliacion:
    """Rehace la carpeta de este sistema con lo que hoy se sabe de él.

    Se llama al responder una pregunta y al regenerar la DdA. Es idempotente: si nada ha
    cambiado, no toca nada.
    """
    from apps.profiling.services import contexto_de

    version = CatalogVersion.current()
    if version is None:
        return Reconciliacion()

    resultado = derivar_requisitos(
        plantillas_del_catalogo(version),
        contexto_de(system),
        medidas_aplicables=aplicabilidad_del_sistema(system),
        refuerzos_activos=refuerzos_del_sistema(system),
    )

    existentes = {
        req.template.code: req
        for req in EvidenceRequirement.objects.filter(system=system).select_related("template")
    }
    cambios = reconciliar({code: req.estado for code, req in existentes.items()}, resultado.codigos)
    derivados = {r.code: r for r in resultado.requisitos}

    plantillas = {
        t.code: t
        for t in EvidenceTemplate.objects.filter(
            catalog=version, code__in=[*cambios.altas, *cambios.reactivados, *cambios.sin_cambio]
        )
    }

    for code in cambios.altas:
        derivado = derivados[code]
        EvidenceRequirement.objects.create(
            tenant=system.tenant,
            system=system,
            template=plantillas[code],
            estado=EstadoRequisito.PENDIENTE,
            origen=derivado.origen,
            motivo=derivado.motivo[:400],
        )

    for code in cambios.fuera_de_alcance:
        requisito = existentes[code]
        requisito.estado = EstadoRequisito.FUERA_DE_ALCANCE
        requisito.save(update_fields=["estado"])

    for code in cambios.reactivados:
        requisito = existentes[code]
        requisito.estado = _estado_segun_evidencias(requisito)
        requisito.origen = derivados[code].origen
        requisito.motivo = derivados[code].motivo[:400]
        requisito.save(update_fields=["estado", "origen", "motivo"])

    # Los que siguen igual refrescan su trazabilidad: la respuesta que los justifica puede
    # haber cambiado aunque el requisito se mantenga.
    for code in cambios.sin_cambio:
        requisito = existentes[code]
        derivado = derivados[code]
        if requisito.origen != derivado.origen:
            requisito.origen = derivado.origen
            requisito.motivo = derivado.motivo[:400]
            requisito.save(update_fields=["origen", "motivo"])

    return cambios


def _estado_segun_evidencias(requisito: EvidenceRequirement) -> str:
    """El estado que le corresponde por lo que tenga dentro.

    Una evidencia rechazada o caducada no cuenta como aportada: el hueco vuelve a estar
    abierto, que es justo lo que tiene que ver quien lo va a arreglar.
    """
    estados = set(requisito.evidencias.values_list("estado", flat=True))
    if EstadoEvidencia.VALIDADA in estados:
        return EstadoRequisito.VALIDADA
    if estados & {EstadoEvidencia.APORTADA, EstadoEvidencia.EN_REVISION}:
        return EstadoRequisito.APORTADA
    return EstadoRequisito.PENDIENTE


# --- aportar y revisar ---------------------------------------------------------------


@transaction.atomic
def aportar(system, requisitos, *, fichero=None, fecha_evidencia, usuario, **datos) -> Evidencia:
    """Sube una evidencia y la enlaza a todos los requisitos que cierra.

    Se sube una vez aunque valga para varios huecos (§4 M5). El permiso lo comprueba la
    vista con `can(user, "evidencia.aportar", requisito)`, no esto.
    """
    evidencia = Evidencia.objects.create(
        tenant=system.tenant,
        system=system,
        titulo=datos.get("titulo", ""),
        fichero=fichero,
        nombre_original=datos.get("nombre_original", ""),
        content_type=datos.get("content_type", ""),
        tamano=datos.get("tamano", 0),
        sha256=datos.get("sha256", ""),
        fecha_evidencia=fecha_evidencia,
        criterios_marcados=list(datos.get("criterios_marcados") or []),
        notas=datos.get("notas", ""),
        aportada_por=usuario,
    )
    evidencia.requisitos.set(requisitos)
    for requisito in requisitos:
        if requisito.estado in (EstadoRequisito.PENDIENTE, EstadoRequisito.CADUCADA):
            requisito.estado = EstadoRequisito.APORTADA
            requisito.save(update_fields=["estado"])
    return evidencia


@transaction.atomic
def validar(evidencia: Evidencia, usuario) -> None:
    """Da por buena la evidencia y cierra los requisitos que cubre.

    Quien la aportó no puede validarla: eso lo impone `can()` antes de llegar aquí
    (separación de funciones, §15).
    """
    evidencia.estado = EstadoEvidencia.VALIDADA
    evidencia.revisor = usuario
    evidencia.revisado_en = timezone.now()
    evidencia.motivo_rechazo = ""
    evidencia.save(update_fields=["estado", "revisor", "revisado_en", "motivo_rechazo"])

    for requisito in evidencia.requisitos.select_related("template"):
        requisito.estado = EstadoRequisito.VALIDADA
        requisito.renovacion_desde(evidencia.fecha_evidencia)
        requisito.save(update_fields=["estado", "proxima_renovacion"])


@transaction.atomic
def rechazar(evidencia: Evidencia, usuario, motivo: str) -> None:
    """Rechaza con un motivo concreto: «no se ve la fecha», no «no vale»."""
    if not motivo.strip():
        raise ValueError("Un rechazo sin motivo no le sirve a quien tiene que corregirlo.")
    evidencia.estado = EstadoEvidencia.RECHAZADA
    evidencia.revisor = usuario
    evidencia.revisado_en = timezone.now()
    evidencia.motivo_rechazo = motivo
    evidencia.save(update_fields=["estado", "revisor", "revisado_en", "motivo_rechazo"])

    for requisito in evidencia.requisitos.all():
        requisito.estado = _estado_segun_evidencias(requisito)
        requisito.save(update_fields=["estado"])


def marcar_no_aplica(requisito: EvidenceRequirement, justificacion: str) -> None:
    """No aplica ≠ pendiente: se puede descartar, pero explicándolo (§10bis.3)."""
    if not justificacion.strip():
        raise ValueError("Marcar un requisito como no aplicable exige justificarlo.")
    requisito.estado = EstadoRequisito.NO_APLICA_JUSTIFICADO
    requisito.justificacion = justificacion
    requisito.save(update_fields=["estado", "justificacion"])


def caducar(hoy: date | None = None) -> int:
    """Devuelve a pendiente lo que ha perdido vigencia. Lo llama una tarea diaria."""
    hoy = hoy or timezone.localdate()
    return EvidenceRequirement.objects.filter(
        estado=EstadoRequisito.VALIDADA, proxima_renovacion__lt=hoy
    ).update(estado=EstadoRequisito.CADUCADA)


# --- qué falta -------------------------------------------------------------------------


def grupos_cubiertos(system) -> set[str]:
    """Grupos de opciones ya resueltos: con cubrir una alternativa basta (§4 M5)."""
    return {
        grupo
        for grupo, estado in EvidenceRequirement.objects.filter(system=system)
        .exclude(template__option_group="")
        .values_list("template__option_group", "estado")
        if estado in CUBIERTOS
    }


def huecos(system) -> list[EvidenceRequirement]:
    """Lo que de verdad falta: sin contar lo que ya cubre otra alternativa de su grupo."""
    cubiertos = grupos_cubiertos(system)
    return [
        requisito
        for requisito in EvidenceRequirement.objects.filter(system=system).select_related(
            "template", "template__measure"
        )
        if requisito.estado not in CUBIERTOS and requisito.template.option_group not in cubiertos
    ]


def medidas_soportadas(system) -> set[str]:
    """Medidas cuya madurez declarada se puede demostrar con evidencia validada.

    Una medida sin requisitos derivados todavía cuenta como soportada: no se le puede
    reprochar a nadie no haber aportado lo que aún no se le ha pedido. En cuanto el
    perfilado pide algo obligatorio y no está validado, deja de estarlo.
    """
    pendientes = {
        requisito.template.measure.code
        for requisito in huecos(system)
        if requisito.template.obligatoria
    }
    con_requisitos = set(
        EvidenceRequirement.objects.filter(system=system).values_list(
            "template__measure__code", flat=True
        )
    )
    return con_requisitos - pendientes


def madurez_soportada(system, measure_code: str, nivel: int | None) -> bool:
    """¿Sostiene la evidencia el nivel declarado? Por debajo de L2 no se exige."""
    if nivel is None or nivel < MADUREZ_QUE_EXIGE_EVIDENCIA:
        return True
    if not EvidenceRequirement.objects.filter(
        system=system, template__measure__code=measure_code
    ).exists():
        return True
    return measure_code in medidas_soportadas(system)
