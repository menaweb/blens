"""Declaración de Aplicabilidad (M2): se genera del motor y no se aprueba a medias."""

import json

import pytest
from django.core.exceptions import ValidationError

from apps.compliance.models import DeclaracionAplicabilidad, EstadoDda
from apps.compliance.services import generar_dda
from apps.tenancy.models import Role
from apps.tenancy.testing import como


@pytest.fixture
def dda(sistema_media, rseg):
    return generar_dda(sistema_media, usuario=rseg)


def patch(cliente, url, payload):
    return cliente.patch(url, data=json.dumps(payload), content_type="application/json")


# --- Generación ----------------------------------------------------------------


def test_la_dda_cubre_las_73_medidas(dda):
    assert dda.medidas.count() == 73
    assert dda.medidas.filter(aplica=True).count() > 0
    assert dda.medidas.filter(aplica=False).count() > 0


def test_se_genera_para_basica_media_y_alta(sistema, rseg):
    """Diferenciador frente a las herramientas que solo cubren una categoría."""
    from apps.compliance.services import guardar_valoracion

    vistos = {}
    for categoria, nivel in (("BASICA", "BAJO"), ("MEDIA", "MEDIO"), ("ALTA", "ALTO")):
        guardar_valoracion(sistema, dict.fromkeys("CITAD", nivel))
        sistema.refresh_from_db()
        dda = generar_dda(sistema, usuario=rseg)
        assert dda.categoria == categoria
        vistos[categoria] = dda.medidas.filter(aplica=True).count()

    assert vistos["BASICA"] < vistos["MEDIA"] < vistos["ALTA"] == 73


def test_guarda_instantanea_de_las_condiciones(dda, sistema_media):
    """Cambiar la categorización mañana no puede reescribir una DdA de ayer."""
    from apps.compliance.services import guardar_valoracion

    guardar_valoracion(sistema_media, dict.fromkeys("CITAD", "ALTO"))
    dda.refresh_from_db()

    assert dda.categoria == "MEDIA"
    assert dda.niveles["T"] == "BAJO"


def test_cada_generacion_es_una_version_nueva(sistema_media, rseg):
    primera = generar_dda(sistema_media, usuario=rseg)
    segunda = generar_dda(sistema_media, usuario=rseg)
    assert (primera.version, segunda.version) == (1, 2)
    assert DeclaracionAplicabilidad.objects.count() == 2


def test_no_se_genera_sin_categorizar(sistema, rseg):
    with pytest.raises(ValueError):
        generar_dda(sistema, usuario=rseg)


def test_las_no_aplicables_nacen_justificadas_por_el_catalogo(dda):
    for fila in dda.medidas.filter(aplica=False):
        assert fila.justificacion
        assert fila.motivo


# --- Lo que impide aprobar ------------------------------------------------------


def test_no_se_aprueba_con_selecciones_sin_resolver(dda, rseg):
    problemas = dda.problemas()
    assert any("selección de refuerzo sin resolver" in p for p in problemas)

    with pytest.raises(ValidationError):
        dda.aprobar(rseg)


def test_no_se_aprueba_una_no_aplicable_sin_justificar(dda, rseg):
    _resolver_selecciones(dda)
    fila = dda.medidas.filter(aplica=True).first()
    fila.aplica = False
    fila.justificacion = ""
    fila.save()

    assert any("sin justificar" in p for p in dda.problemas())
    with pytest.raises(ValidationError):
        dda.aprobar(rseg)


def _resolver_selecciones(dda) -> None:
    for fila in dda.medidas.all():
        if fila.selecciones:
            fila.selecciones = {
                param: dda.catalog.measures.get(code=fila.measure.code)
                .params.get(code=param)
                .choices[0]
                for param in fila.selecciones
            }
            fila.save()


def test_se_aprueba_cuando_no_queda_nada_pendiente(dda, rseg):
    _resolver_selecciones(dda)
    assert dda.problemas() == []

    dda.aprobar(rseg)
    dda.refresh_from_db()
    assert dda.estado == EstadoDda.APROBADA
    assert dda.aprobador == rseg and dda.aprobada_en is not None


def test_aprobar_deja_obsoleta_la_anterior(sistema_media, rseg):
    primera = generar_dda(sistema_media, usuario=rseg)
    _resolver_selecciones(primera)
    primera.aprobar(rseg)

    segunda = generar_dda(sistema_media, usuario=rseg)
    _resolver_selecciones(segunda)
    segunda.aprobar(rseg)

    primera.refresh_from_db()
    assert primera.estado == EstadoDda.OBSOLETA


def test_no_se_aprueba_dos_veces(dda, rseg):
    _resolver_selecciones(dda)
    dda.aprobar(rseg)
    with pytest.raises(ValidationError):
        dda.aprobar(rseg)


# --- Permisos -------------------------------------------------------------------


def test_el_tecnico_edita_la_dda_pero_no_la_aprueba(dda, tecnico, sistema_media):
    cliente = como(tecnico)
    respuesta = patch(
        cliente,
        f"/api/dda/{dda.pk}/measures/org.1",
        {"aplica": False, "justificacion": "Cubierto por la política corporativa"},
    )
    assert respuesta.status_code == 200
    assert cliente.post(f"/api/dda/{dda.pk}/approve").status_code == 403


def test_el_rseg_aprueba_desde_la_api(dda, rseg):
    _resolver_selecciones(dda)
    respuesta = como(rseg).post(f"/api/dda/{dda.pk}/approve")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "APROBADA"


def test_la_api_devuelve_los_problemas_al_intentar_aprobar(dda, rseg):
    respuesta = como(rseg).post(f"/api/dda/{dda.pk}/approve")
    assert respuesta.status_code == 409
    assert "selección" in json.dumps(respuesta.json(), ensure_ascii=False)


def test_una_dda_aprobada_no_se_edita(dda, rseg):
    _resolver_selecciones(dda)
    dda.aprobar(rseg)
    respuesta = patch(como(rseg), f"/api/dda/{dda.pk}/measures/org.1", {"aplica": False})
    assert respuesta.status_code == 409


def test_el_auditor_lee_pero_no_toca(dda, miembro):
    from datetime import timedelta

    from django.utils import timezone

    auditor = miembro(Role.AUDITOR, expires_at=timezone.now() + timedelta(days=30))
    cliente = como(auditor)
    assert cliente.get(f"/api/dda/{dda.pk}").status_code == 200
    assert patch(cliente, f"/api/dda/{dda.pk}/measures/org.1", {"aplica": False}).status_code == 403


def test_una_seleccion_solo_admite_sus_opciones(dda, rseg):
    respuesta = patch(
        como(rseg),
        f"/api/dda/{dda.pk}/measures/op.acc.5",
        {"selecciones": {"op.acc.5.prm.rfz.medio": "op.exp.6.r1"}},
    )
    assert respuesta.status_code == 400


# --- Export ----------------------------------------------------------------------


def test_export_oscal_profile(dda, rseg):
    _resolver_selecciones(dda)
    respuesta = como(rseg).get(f"/api/dda/{dda.pk}/oscal")
    assert respuesta.status_code == 200

    perfil = json.loads(respuesta.content)["profile"]
    incluidos = perfil["imports"][0]["include-controls"][0]["with-ids"]
    excluidos = perfil["imports"][0]["exclude-controls"][0]["with-ids"]

    assert "org.1" in incluidos
    assert set(incluidos) & set(excluidos) == set()
    assert perfil["modify"]["set-parameters"]  # las selecciones resueltas viajan como params
    assert {"ns": "urn:es:ens", "name": "categoria", "value": "MEDIA"} in perfil["metadata"][
        "props"
    ]


def test_el_pdf_de_la_dda_se_encola(dda, rseg, sin_pdf):
    respuesta = como(rseg).post(f"/api/dda/{dda.pk}/pdf")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ENCOLADO"
