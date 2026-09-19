"""Carpeta de evidencias (M5): huecos, alternativas, revisión y caducidad.

El hilo que se prueba es el del producto entero: alguien responde una pregunta, aparece un
hueco explicado, otra persona sube un fichero, un tercero lo valida y la madurez declarada
pasa a estar sostenida. Y si el cliente se muda de CPD, nada de eso se pierde.
"""

import json
from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.compliance.models import MeasureAssessment
from apps.compliance.services import asegurar_valoraciones
from apps.evidence.models import EstadoEvidencia, EstadoRequisito, EvidenceRequirement
from apps.evidence.services import aportar, caducar, huecos, recalcular, validar
from apps.profiling.services import responder
from apps.tenancy.models import Role
from apps.tenancy.testing import como


@pytest.fixture
def rseg(miembro):
    return miembro(Role.RSEG)


@pytest.fixture
def tecnico(miembro):
    return miembro(Role.TECNICO)


@pytest.fixture
def con_cpd(sistema, pregunta, rseg):
    """Un sistema que ha dicho que tiene CPD propio con control de acceso por tarjeta."""
    responder(sistema, pregunta("mp.if.areas"), ["cpd"], usuario=rseg)
    responder(sistema, pregunta("mp.if.acceso"), ["tarjeta"], usuario=rseg)
    return sistema


def requisito_de(sistema, code: str) -> EvidenceRequirement:
    return EvidenceRequirement.objects.get(system=sistema, template__code=code)


def un_grupo(sistema) -> list[EvidenceRequirement]:
    """Un grupo de alternativas de este sistema, ordenado por solidez."""
    for requisito in EvidenceRequirement.objects.filter(system=sistema).select_related("template"):
        grupo = requisito.template.option_group
        if not grupo:
            continue
        hermanos = list(
            EvidenceRequirement.objects.filter(system=sistema, template__option_group=grupo)
            .select_related("template")
            .order_by("template__preferencia")
        )
        if len(hermanos) > 1:
            return hermanos
    raise AssertionError("el perfil de prueba no ha generado ningún grupo de alternativas")


def fichero(nombre="captura.png"):
    return SimpleUploadedFile(nombre, b"\x89PNG captura de ejemplo", content_type="image/png")


# --- La carpeta ------------------------------------------------------------------


def test_la_carpeta_explica_cada_hueco(con_cpd, rseg):
    respuesta = como(rseg).get(f"/api/systems/{con_cpd.pk}/evidence")
    assert respuesta.status_code == 200

    datos = respuesta.json()
    assert datos["huecos"] > 0
    assert all(
        r["instrucciones"] and r["criterios_aceptacion"] and r["motivo"]
        for r in datos["requisitos"]
    ), "un hueco sin instrucciones ni criterios no lo rellena nadie"

    # Los que ha traído el perfilado recuerdan la respuesta que los originó (§10bis.4).
    del_perfilado = [r for r in datos["requisitos"] if r["origen"].get("preguntas")]
    assert del_perfilado, "ningún requisito recuerda la pregunta que lo disparó"
    assert "mp.if.areas" in {
        pregunta for r in del_perfilado for pregunta in r["origen"]["preguntas"]
    }


def test_la_completitud_no_redondea_al_alza(con_cpd, rseg):
    datos = como(rseg).get(f"/api/systems/{con_cpd.pk}/evidence").json()
    assert datos["completitud"] < 100
    assert datos["por_familia"]["mp.if"]["huecos"] > 0


def test_recalcular_dos_veces_no_cambia_nada(con_cpd):
    cambios = recalcular(con_cpd)
    assert not cambios.hay_cambios


# --- Aportar y revisar --------------------------------------------------------------


def test_aportar_deja_el_requisito_aportado_y_validarlo_lo_cierra(con_cpd, tecnico, rseg):
    requisito = huecos(con_cpd)[0]

    evidencia = aportar(
        con_cpd,
        [requisito],
        fichero=fichero(),
        fecha_evidencia=date(2026, 9, 1),
        usuario=tecnico,
        titulo="Captura de la consola",
    )
    requisito.refresh_from_db()
    assert requisito.estado == EstadoRequisito.APORTADA

    validar(evidencia, rseg)
    requisito.refresh_from_db()
    assert requisito.estado == EstadoRequisito.VALIDADA
    if requisito.template.vigencia_dias:
        assert requisito.proxima_renovacion == date(2026, 9, 1) + timedelta(
            days=requisito.template.vigencia_dias
        )


def test_una_evidencia_cierra_todos_los_requisitos_a_los_que_se_enlaza(con_cpd, tecnico, rseg):
    """Se sube una vez y vale para todos: es la promesa de M5."""
    pendientes = huecos(con_cpd)[:2]

    evidencia = aportar(
        con_cpd, pendientes, fichero=fichero(), fecha_evidencia=date(2026, 9, 1), usuario=tecnico
    )
    validar(evidencia, rseg)

    for requisito in pendientes:
        requisito.refresh_from_db()
        assert requisito.estado == EstadoRequisito.VALIDADA


def test_cubrir_una_alternativa_cierra_el_grupo(con_cpd, tecnico, rseg):
    hermanos = un_grupo(con_cpd)
    evidencia = aportar(
        con_cpd, [hermanos[0]], fichero=fichero(), fecha_evidencia=date(2026, 9, 1), usuario=tecnico
    )
    validar(evidencia, rseg)

    pendientes = {r.pk for r in huecos(con_cpd)}
    assert hermanos[1].pk not in pendientes, "la otra alternativa sigue contando como hueco"

    datos = como(rseg).get(f"/api/systems/{con_cpd.pk}/evidence").json()
    otra = next(r for r in datos["requisitos"] if r["id"] == hermanos[1].pk)
    assert otra["cubierto_por_grupo"] is True
    assert otra["alternativas"], "no dice cuáles son las otras formas válidas"


def test_quien_aporta_una_evidencia_no_puede_validarla(con_cpd, rseg):
    """Separación de funciones impuesta por el sistema, aunque el rol lo permita (§15)."""
    requisito = huecos(con_cpd)[0]
    evidencia = aportar(
        con_cpd, [requisito], fichero=fichero(), fecha_evidencia=date(2026, 9, 1), usuario=rseg
    )

    respuesta = como(rseg).post(f"/api/systems/{con_cpd.pk}/evidencias/{evidencia.pk}/validar")
    assert respuesta.status_code == 403
    evidencia.refresh_from_db()
    assert evidencia.estado == EstadoEvidencia.APORTADA


def test_un_rechazo_sin_motivo_no_le_sirve_a_nadie(con_cpd, tecnico, rseg):
    requisito = huecos(con_cpd)[0]
    evidencia = aportar(
        con_cpd, [requisito], fichero=fichero(), fecha_evidencia=date(2026, 9, 1), usuario=tecnico
    )

    respuesta = como(rseg).post(
        f"/api/systems/{con_cpd.pk}/evidencias/{evidencia.pk}/rechazar",
        data=json.dumps({"motivo": "  "}),
        content_type="application/json",
    )
    assert respuesta.status_code == 422

    con_motivo = como(rseg).post(
        f"/api/systems/{con_cpd.pk}/evidencias/{evidencia.pk}/rechazar",
        data=json.dumps({"motivo": "La captura no muestra la fecha del sistema"}),
        content_type="application/json",
    )
    assert con_motivo.status_code == 200
    requisito.refresh_from_db()
    assert requisito.estado == EstadoRequisito.PENDIENTE


def test_no_aplica_exige_justificacion(con_cpd, rseg):
    requisito = huecos(con_cpd)[0]
    url = f"/api/systems/{con_cpd.pk}/evidence/{requisito.pk}/no-aplica"

    vacio = como(rseg).post(
        url, data=json.dumps({"justificacion": ""}), content_type="application/json"
    )
    assert vacio.status_code == 422

    justificado = como(rseg).post(
        url,
        data=json.dumps({"justificacion": "La sala no tiene ventanas al exterior"}),
        content_type="application/json",
    )
    assert justificado.status_code == 200
    requisito.refresh_from_db()
    assert requisito.estado == EstadoRequisito.NO_APLICA_JUSTIFICADO


def test_una_evidencia_caducada_vuelve_a_pedirse(con_cpd, tecnico, rseg):
    requisito = next(r for r in huecos(con_cpd) if r.template.vigencia_dias)
    evidencia = aportar(
        con_cpd, [requisito], fichero=fichero(), fecha_evidencia=date(2020, 1, 1), usuario=tecnico
    )
    validar(evidencia, rseg)

    assert caducar(hoy=date(2026, 9, 20)) >= 1
    requisito.refresh_from_db()
    assert requisito.estado == EstadoRequisito.CADUCADA


# --- Declarado ≠ demostrado ---------------------------------------------------------


def test_la_madurez_declarada_no_se_sostiene_sin_evidencia_validada(con_cpd, tecnico, rseg):
    """Lo primero que detecta un auditor: L3 sin nada que lo demuestre (§10bis.3)."""
    asegurar_valoraciones(con_cpd)
    requisito = next(r for r in huecos(con_cpd) if r.template.obligatoria)
    medida = requisito.template.measure

    valoracion = MeasureAssessment.objects.get(system=con_cpd, measure=medida)
    valoracion.maturity_level = 3
    valoracion.save(update_fields=["maturity_level"])
    assert valoracion.madurez_soportada is False

    for pendiente in [r for r in huecos(con_cpd) if r.template.measure_id == medida.pk]:
        evidencia = aportar(
            con_cpd,
            [pendiente],
            fichero=fichero(),
            fecha_evidencia=date(2026, 9, 1),
            usuario=tecnico,
        )
        validar(evidencia, rseg)

    assert valoracion.madurez_soportada is True


def test_por_debajo_de_l2_no_se_exige_demostrar_nada(con_cpd):
    asegurar_valoraciones(con_cpd)
    requisito = next(r for r in huecos(con_cpd) if r.template.obligatoria)
    valoracion = MeasureAssessment.objects.get(system=con_cpd, measure=requisito.template.measure)
    valoracion.maturity_level = 1
    valoracion.save(update_fields=["maturity_level"])

    assert valoracion.madurez_soportada is True


def test_el_checklist_marca_como_no_soportada_la_medida_sin_evidencia(con_cpd, rseg):
    asegurar_valoraciones(con_cpd)
    requisito = next(r for r in huecos(con_cpd) if r.template.obligatoria)
    medida = requisito.template.measure
    MeasureAssessment.objects.filter(system=con_cpd, measure=medida).update(maturity_level=4)

    datos = como(rseg).get(f"/api/systems/{con_cpd.pk}/checklist").json()
    fila = next(f for f in datos["medidas"] if f["code"] == medida.code)
    assert fila["no_soportada"] is True


# --- Subida por la API ----------------------------------------------------------------


def test_subir_una_evidencia_por_la_api(con_cpd, tecnico):
    requisito = huecos(con_cpd)[0]
    respuesta = como(tecnico).post(
        f"/api/systems/{con_cpd.pk}/evidence/{requisito.pk}/evidencias",
        data={
            "fichero": fichero(),
            "fecha_evidencia": "2026-09-01",
            "titulo": "Captura del control de accesos",
            "criterios": "Se ve la fecha|Se ve el nombre de la sala",
        },
    )
    assert respuesta.status_code == 200

    requisito.refresh_from_db()
    assert requisito.estado == EstadoRequisito.APORTADA
    evidencia = requisito.evidencias.get()
    assert evidencia.sha256, "sin huella no hay integridad demostrable (§11)"
    assert evidencia.criterios_marcados == ["Se ve la fecha", "Se ve el nombre de la sala"]


def test_sin_credenciales_no_se_ve_la_carpeta(sistema, anonimo):
    assert anonimo.get(f"/api/systems/{sistema.pk}/evidence").status_code == 401
