"""Cuestionario de perfilado (M11).

Lo que devuelve esta API no es una lista de preguntas: es una pregunta que alguien puede
contestar sin ser experto. Por eso viaja con su **por qué**, su **dónde mirarlo** y su
glosario (`docs/cuestionario_perfilado.md` §1bis), y por eso no hay ninguna opción que
diga «no lo sé»: hay un botón para preguntárselo a quien lo sepa.

Responder tiene efecto inmediato en la carpeta de evidencias, y la respuesta lo dice: es
la relación causa-efecto que hace que el perfilado no parezca un formulario más.
"""

from __future__ import annotations

from typing import Any

from apps.catalog.models import ProfileQuestion
from apps.compliance.models import System
from apps.profiling.models import EstadoDelegacion, ProfileAnswer, ProfileDelegation
from apps.profiling.services import delegar, preguntas_del_sistema, progreso, responder
from apps.tenancy.permissions import require
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError

from api.auth import blens_auth

router = Router(auth=blens_auth)


class OpcionOut(Schema):
    code: str
    label: str


class PreguntaOut(Schema):
    code: str
    bloque: str
    tipo: str
    texto: str
    #: Para qué sirve responder esto. Sin esto, la pregunta parece burocracia.
    por_que: str
    como_saberlo: str
    a_quien_preguntar: str
    glosario: dict[str, str]
    campos: list[dict[str, str]]
    opciones: list[OpcionOut]
    minutos_estimados: int
    respondida: bool
    valor: Any = None
    delegada_a: str | None = None


class BloqueOut(Schema):
    bloque: str
    titulo: str
    total: int
    respondidas: int
    #: Minutos que quedan en el bloque, no los que costaba entero.
    minutos: int


class CuestionarioOut(Schema):
    system_id: int
    sistema: str
    categoria: str
    bloques: list[BloqueOut]
    preguntas: list[PreguntaOut]
    #: Cuántas preguntas visibles quedan por responder.
    pendientes: int


def _cuestionario(system: System) -> CuestionarioOut:
    visibles = preguntas_del_sistema(system)
    codigos = [p.code for p in visibles]
    filas = {
        f.code: f for f in ProfileQuestion.objects.filter(code__in=codigos).select_related("bloque")
    }
    respuestas = {
        r.question.code: r
        for r in ProfileAnswer.objects.filter(
            system=system, question__code__in=codigos
        ).select_related("question")
    }
    delegadas = {
        d.question.code: d
        for d in ProfileDelegation.objects.filter(
            system=system, question__code__in=codigos, estado=EstadoDelegacion.PENDIENTE
        ).select_related("question", "asignado_a")
    }
    titulos = {fila.bloque.code: fila.bloque.titulo for fila in filas.values() if fila.bloque_id}

    preguntas = []
    for pregunta in visibles:
        fila = filas[pregunta.code]
        respuesta = respuestas.get(pregunta.code)
        delegada = delegadas.get(pregunta.code)
        preguntas.append(
            PreguntaOut(
                code=pregunta.code,
                bloque=pregunta.bloque,
                tipo=pregunta.tipo,
                texto=pregunta.texto,
                por_que=fila.por_que,
                como_saberlo=fila.como_saberlo,
                a_quien_preguntar=fila.a_quien_preguntar,
                glosario=fila.glosario or {},
                campos=fila.campos or [],
                opciones=[OpcionOut(code=o.code, label=o.label) for o in pregunta.opciones],
                minutos_estimados=pregunta.minutos_estimados,
                respondida=respuesta is not None,
                valor=respuesta.value if respuesta else None,
                delegada_a=_quien(delegada) if delegada else None,
            )
        )

    return CuestionarioOut(
        system_id=system.pk,
        sistema=system.nombre,
        categoria=system.categoria,
        bloques=[
            BloqueOut(**fila, titulo=titulos.get(fila["bloque"], fila["bloque"]))
            for fila in progreso(system)
        ],
        preguntas=preguntas,
        pendientes=sum(1 for p in preguntas if not p.respondida),
    )


def _quien(delegacion: ProfileDelegation) -> str:
    if delegacion.asignado_a:
        return delegacion.asignado_a.get_full_name() or delegacion.asignado_a.username
    return delegacion.asignado_email


@router.get(
    "/systems/{system_id}/profiling",
    response=CuestionarioOut,
    summary="Cuestionario de perfilado (M11)",
)
def cuestionario(request, system_id: int):
    """Las preguntas que toca enseñar ahora, con su ayuda y lo ya respondido.

    Las de seguimiento aparecen solas cuando su condición se cumple: nadie ve el
    cuestionario entero de golpe.
    """
    system = get_object_or_404(System, pk=system_id)
    require(request.user, "perfilado.leer", system)
    return _cuestionario(system)


class RespuestaIn(Schema):
    valor: Any = None


class RespuestaOut(Schema):
    #: Hechos que ha dejado la respuesta: es la trazabilidad, y se enseña.
    hechos: dict[str, Any]
    requisitos_nuevos: list[str]
    requisitos_fuera_de_alcance: list[str]
    cuestionario: CuestionarioOut


@router.put(
    "/systems/{system_id}/profiling/{code}",
    response=RespuestaOut,
    summary="Responder una pregunta del perfilado",
)
def responder_pregunta(request, system_id: int, code: str, datos: RespuestaIn):
    """Guarda la respuesta y rehace la carpeta de evidencias.

    Devuelve qué requisitos aparecen y cuáles se apartan: responder tiene consecuencias
    visibles, no es rellenar un formulario.
    """
    system = get_object_or_404(System, pk=system_id)
    pregunta = get_object_or_404(ProfileQuestion, code=code, catalog__is_current=True)
    require(request.user, "perfilado.responder", _ambito(system, pregunta))

    cambios = responder(system, pregunta, datos.valor, usuario=request.user)
    return RespuestaOut(**cambios, cuestionario=_cuestionario(system))


class DelegacionIn(Schema):
    """A quién se le pregunta. Uno de los dos, pero alguno."""

    usuario_id: int | None = None
    email: str = ""
    nota: str = ""


class DelegacionOut(Schema):
    pregunta: str
    delegada_a: str


@router.post(
    "/systems/{system_id}/profiling/{code}/delegar",
    response=DelegacionOut,
    summary="Preguntárselo a otra persona",
)
def delegar_pregunta(request, system_id: int, code: str, datos: DelegacionIn):
    """Lo que hay en vez de un «no lo sé»: la pregunta pasa a quien la sepa, con nombre."""
    system = get_object_or_404(System, pk=system_id)
    pregunta = get_object_or_404(ProfileQuestion, code=code, catalog__is_current=True)
    require(request.user, "perfilado.responder", _ambito(system, pregunta))

    asignado = None
    if datos.usuario_id:
        asignado = get_user_model().objects.filter(pk=datos.usuario_id).first()
        if asignado is None:
            raise HttpError(404, "Esa persona no existe.")
    try:
        delegacion = delegar(
            system,
            pregunta,
            usuario=request.user,
            asignado=asignado,
            email=datos.email,
            nota=datos.nota,
        )
    except ValueError as error:
        raise HttpError(422, str(error)) from error
    return DelegacionOut(pregunta=code, delegada_a=_quien(delegacion))


def _ambito(system: System, pregunta: ProfileQuestion):
    """Objeto que `can()` mira para acotar al COLABORADOR a sus bloques."""

    class Ambito:
        tenant_id = system.tenant_id
        system_id = system.pk
        bloque = pregunta.bloque.code if pregunta.bloque_id else ""

    return Ambito()
