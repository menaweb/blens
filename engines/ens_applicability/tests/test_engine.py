"""Aplicabilidad del Anexo II sobre el catálogo oficial.

Los cuatro perfiles son los caminos típicos de `docs/cuestionario_perfilado.md` §5.
"""

import pytest

from engines.ens_applicability import Perfil, aplicabilidad

TODAS = "CITAD"


def perfil(categoria: str, **niveles: str) -> Perfil:
    base = dict.fromkeys(TODAS, "NA")
    base.update(niveles)
    return Perfil(categoria=categoria, niveles=base)


# --- Perfiles tipo -------------------------------------------------------------


@pytest.fixture
def pyme_basica():
    """PYME proveedora, Básica, todo en M365."""
    return perfil("BASICA", C="BAJO", I="BAJO", T="BAJO", A="BAJO", D="BAJO")


@pytest.fixture
def ayuntamiento_media():
    """Ayuntamiento con CPD propio y sede electrónica."""
    return perfil("MEDIA", C="MEDIO", I="MEDIO", T="MEDIO", A="MEDIO", D="MEDIO")


@pytest.fixture
def saas_media():
    """Proveedor SaaS en AWS que además desarrolla."""
    return perfil("MEDIA", C="MEDIO", I="MEDIO", T="BAJO", A="MEDIO", D="MEDIO")


@pytest.fixture
def organismo_alta():
    return perfil("ALTA", C="ALTO", I="ALTO", T="ALTO", A="ALTO", D="ALTO")


def test_cuantas_mas_exigencias_mas_medidas(
    catalogo, pyme_basica, ayuntamiento_media, organismo_alta
):
    basica = len(aplicabilidad(catalogo, pyme_basica).aplicables)
    media = len(aplicabilidad(catalogo, ayuntamiento_media).aplicables)
    alta = len(aplicabilidad(catalogo, organismo_alta).aplicables)
    assert basica < media < alta == 73


def test_en_alta_aplican_todas_las_medidas(catalogo, organismo_alta):
    resultado = aplicabilidad(catalogo, organismo_alta)
    assert len(resultado.aplicables) == 73
    assert resultado.no_aplicables == ()


def test_el_perfil_saas_no_pide_lo_de_trazabilidad_alta(catalogo, saas_media, organismo_alta):
    """mp.info.4 (sellos de tiempo) va por Trazabilidad ALTA, no por categoría."""
    saas = aplicabilidad(catalogo, saas_media).measure_ids
    alta = aplicabilidad(catalogo, organismo_alta).measure_ids
    assert "mp.info.4" not in saas
    assert "mp.info.4" in alta


def test_cada_medida_aplicable_dice_por_que(catalogo, ayuntamiento_media):
    for medida in aplicabilidad(catalogo, ayuntamiento_media).aplicables:
        assert medida.motivo  # va a la DdA, no puede quedar vacío


def test_las_no_aplicables_tambien_llevan_motivo(catalogo, pyme_basica):
    no_aplicables = aplicabilidad(catalogo, pyme_basica).no_aplicables
    assert no_aplicables
    assert all(motivo for _, motivo in no_aplicables)


# --- La regla que más se equivoca: nivel de dimensión ---------------------------


def test_mp_info_3_aplica_por_integridad_y_autenticidad_no_por_categoria(catalogo):
    """Criterio de cierre de F1: la categoría no manda en las medidas por dimensión."""
    sin_firma = perfil("ALTA", C="ALTO", D="ALTO")  # I y A en N/A
    con_integridad = perfil("BASICA", I="BAJO")

    assert "mp.info.3" not in aplicabilidad(catalogo, sin_firma).measure_ids
    assert "mp.info.3" in aplicabilidad(catalogo, con_integridad).measure_ids


def test_mp_eq_2_no_aplica_con_autenticidad_baja(catalogo):
    """Aplica en Autenticidad MEDIO y ALTO; en BAJO es n.a. (errata del título aparte)."""
    assert "mp.eq.2" not in aplicabilidad(catalogo, perfil("BASICA", A="BAJO")).measure_ids
    assert "mp.eq.2" in aplicabilidad(catalogo, perfil("MEDIA", A="MEDIO")).measure_ids


def test_una_dimension_alta_arrastra_sus_medidas_aunque_la_categoria_sea_baja(catalogo):
    """Anexo I.4.2: las dimensiones que no marcan la categoría conservan su nivel."""
    solo_disponibilidad = perfil("BASICA", D="ALTO")
    ids = aplicabilidad(catalogo, solo_disponibilidad).measure_ids
    assert "op.cont.4" in ids  # medios alternativos, exigido en Disponibilidad ALTA


# --- Refuerzos y selecciones ---------------------------------------------------


def test_los_41_refuerzos_sin_props_se_ofrecen_como_opcionales(catalogo, organismo_alta):
    resultado = aplicabilidad(catalogo, organismo_alta)
    opcionales = [r for m in resultado.aplicables for r in m.refuerzos_opcionales]
    assert len(opcionales) == 41


def test_un_refuerzo_de_alta_no_se_pide_en_basica(catalogo, pyme_basica, organismo_alta):
    en_basica = [
        m for m in aplicabilidad(catalogo, pyme_basica).aplicables if m.measure_id == "mp.s.2"
    ][0]
    en_alta = [
        m for m in aplicabilidad(catalogo, organismo_alta).aplicables if m.measure_id == "mp.s.2"
    ][0]

    assert "mp.s.2.r3" in en_basica.refuerzos_no_aplicables
    assert "mp.s.2.r3" in en_alta.refuerzos_obligatorios


def test_en_basica_mp_s_2_se_resuelve_eligiendo_y_en_alta_es_obligatorio(
    catalogo, pyme_basica, organismo_alta
):
    """El mismo refuerzo es opción en Básica y obligación en Alta: no puede desaparecer."""
    basica = [
        m for m in aplicabilidad(catalogo, pyme_basica).aplicables if m.measure_id == "mp.s.2"
    ][0]
    assert [s.param_id for s in basica.selecciones] == ["mp.s.2.prm.rfz.basica"]
    assert basica.selecciones[0].opciones == ("mp.s.2.r1", "mp.s.2.r2")

    alta = [
        m for m in aplicabilidad(catalogo, organismo_alta).aplicables if m.measure_id == "mp.s.2"
    ][0]
    assert alta.selecciones == ()
    assert "mp.s.2.r2" in alta.refuerzos_obligatorios


def test_la_seleccion_pendiente_depende_del_nivel(catalogo):
    """op.acc.5 ofrece cuatro opciones en BAJO y tres en MEDIO."""
    bajo = aplicabilidad(catalogo, perfil("BASICA", C="BAJO", I="BAJO", T="BAJO", A="BAJO"))
    medio = aplicabilidad(catalogo, perfil("MEDIA", C="MEDIO", I="MEDIO", T="MEDIO", A="MEDIO"))

    sel_bajo = [s for s in bajo.selecciones_pendientes if s.measure_id == "op.acc.5"][0]
    sel_medio = [s for s in medio.selecciones_pendientes if s.measure_id == "op.acc.5"][0]

    assert sel_bajo.nivel == "BAJO" and len(sel_bajo.opciones) == 4
    assert sel_medio.nivel == "MEDIO" and len(sel_medio.opciones) == 3
    assert "op.acc.5.r1" not in sel_medio.opciones  # contraseña sola no basta en MEDIO


def test_toda_seleccion_ofrece_mas_de_una_opcion(catalogo, ayuntamiento_media):
    for seleccion in aplicabilidad(catalogo, ayuntamiento_media).selecciones_pendientes:
        assert len(seleccion.opciones) > 1


# --- Contrato del motor --------------------------------------------------------


def test_la_categoria_se_deriva_del_mayor_nivel():
    assert Perfil.desde_niveles({"C": "BAJO", "D": "ALTO"}).categoria == "ALTA"
    assert Perfil.desde_niveles({"C": "BAJO", "D": "MEDIO"}).categoria == "MEDIA"
    assert Perfil.desde_niveles({"C": "BAJO"}).categoria == "BASICA"
    assert Perfil.desde_niveles({"C": "NA"}).categoria == "BASICA"


def test_mismo_perfil_mismo_resultado(catalogo, ayuntamiento_media):
    uno = aplicabilidad(catalogo, ayuntamiento_media)
    dos = aplicabilidad(catalogo, ayuntamiento_media)
    assert uno == dos


def test_ninguna_medida_queda_sin_clasificar(catalogo, ayuntamiento_media):
    resultado = aplicabilidad(catalogo, ayuntamiento_media)
    assert len(resultado.aplicables) + len(resultado.no_aplicables) == 73
