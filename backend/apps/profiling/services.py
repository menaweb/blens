"""Perfilado (M11): qué se pregunta, qué deja cada respuesta y a quién se le delega.

Traduce entre la base de datos y `engines.evidence_engine`, y nada más: la decisión de qué
pregunta toca y qué hechos deja una respuesta es del motor, que es puro y está probado sin
Django. Al responder se rehace la carpeta de evidencias, que es el efecto que el cliente ve.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import CatalogVersion, ProfileQuestion
from apps.catalog.motor import pregunta_de, preguntas_del_catalogo
from apps.compliance.services import niveles_de
from apps.profiling.models import (
    EstadoDelegacion,
    ProfileAnswer,
    ProfileAnswerHistory,
    ProfileDelegation,
    ProfileFact,
)
from engines.evidence_engine import (
    Contexto,
    Pregunta,
    contexto_de_datos,
    hechos_de_respuesta,
    preguntas_visibles,
)


def contexto_de(system) -> Contexto:
    """Lo que hoy se sabe del sistema, tal y como lo leen las reglas."""
    hechos, origen = {}, {}
    for fila in ProfileFact.objects.filter(system=system).select_related("source_answer__question"):
        hechos[fila.key] = fila.value
        if fila.source_answer_id:
            origen[fila.key] = fila.source_answer.question.code
    return contexto_de_datos(system.categoria, niveles_de(system), hechos, origen)


def preguntas_pendientes(system) -> tuple[Pregunta, ...]:
    """Las preguntas que toca enseñar y que nadie ha respondido todavía."""
    respondidas = set(
        ProfileAnswer.objects.filter(system=system).values_list("question__code", flat=True)
    )
    visibles = preguntas_visibles(_catalogo(), contexto_de(system))
    return tuple(p for p in visibles if p.code not in respondidas)


def preguntas_del_sistema(system) -> tuple[Pregunta, ...]:
    """Todas las visibles, respondidas o no: es lo que pinta el cuestionario."""
    return preguntas_visibles(_catalogo(), contexto_de(system))


def progreso(system) -> list[dict]:
    """Cuánto queda, por bloque. Es lo que decide si alguien termina el perfilado."""
    respondidas = set(
        ProfileAnswer.objects.filter(system=system).values_list("question__code", flat=True)
    )
    por_bloque: dict[str, dict] = {}
    for pregunta in preguntas_del_sistema(system):
        fila = por_bloque.setdefault(
            pregunta.bloque, {"bloque": pregunta.bloque, "total": 0, "respondidas": 0, "minutos": 0}
        )
        fila["total"] += 1
        fila["minutos"] += pregunta.minutos_estimados
        if pregunta.code in respondidas:
            fila["respondidas"] += 1
            fila["minutos"] -= pregunta.minutos_estimados
    return [por_bloque[code] for code in sorted(por_bloque)]


@transaction.atomic
def responder(system, question: ProfileQuestion, valor, usuario=None) -> dict:
    """Guarda una respuesta, actualiza los hechos y rehace la carpeta de evidencias.

    El permiso se comprueba antes, en la vista. Aquí se cuida de que la respuesta anterior
    no se pierda y de que los hechos que ya no se emiten desaparezcan: si alguien corrige
    «tenemos CPD propio» por «está en un proveedor», el hecho viejo no puede quedarse.
    """
    from apps.evidence.services import recalcular

    respuesta = ProfileAnswer.objects.filter(system=system, question=question).first()
    if respuesta is None:
        respuesta = ProfileAnswer.objects.create(
            tenant=system.tenant,
            system=system,
            question=question,
            value=valor,
            respondido_por=usuario,
        )
    else:
        if respuesta.value != valor:
            ProfileAnswerHistory.objects.create(
                answer=respuesta,
                value=respuesta.value,
                respondido_por=respuesta.respondido_por,
                fecha=respuesta.fecha,
            )
        respuesta.value = valor
        respuesta.respondido_por = usuario
        respuesta.save(update_fields=["value", "respondido_por", "fecha"])

    nuevos = hechos_de_respuesta(pregunta_de(question), valor)
    ProfileFact.objects.filter(system=system, source_answer=respuesta).exclude(
        key__in=nuevos
    ).delete()
    for clave, dato in nuevos.items():
        ProfileFact.objects.update_or_create(
            system=system,
            key=clave,
            defaults={"tenant": system.tenant, "value": dato, "source_answer": respuesta},
        )

    ProfileDelegation.objects.filter(
        system=system, question=question, estado=EstadoDelegacion.PENDIENTE
    ).update(estado=EstadoDelegacion.RESUELTA, resuelto_en=timezone.now())

    cambios = recalcular(system)
    return {
        "hechos": nuevos,
        "requisitos_nuevos": list(cambios.altas),
        "requisitos_fuera_de_alcance": list(cambios.fuera_de_alcance),
    }


def delegar(system, question: ProfileQuestion, *, usuario, asignado=None, email="", nota=""):
    """«Preguntárselo a otra persona»: lo que hay en vez de un «no lo sé» en el menú.

    Exige elegir a quién. Que la tasa de delegación por pregunta se pueda medir es
    justamente el punto: por encima del 20 % la pregunta está mal escrita (§4 M11).
    """
    if asignado is None and not email:
        raise ValueError("Delegar una pregunta exige decir a quién se le pregunta.")
    return ProfileDelegation.objects.create(
        tenant=system.tenant,
        system=system,
        question=question,
        asignado_a=asignado,
        asignado_email=email,
        creado_por=usuario,
        nota=nota,
    )


def _catalogo() -> tuple[Pregunta, ...]:
    version = CatalogVersion.current()
    return preguntas_del_catalogo(version) if version else ()
