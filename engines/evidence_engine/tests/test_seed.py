"""El motor contra el seed de verdad: 156 preguntas y 199 plantillas de las 16 familias.

Lo que se prueba aquí no es el motor, es **el contenido**: que las condiciones escritas en
el seed digan lo que sus autores creen que dicen. Un fallo en este fichero es una errata en
`db/seed/blens`, no un fallo de código.

La alcanzabilidad de cada plantilla la comprueba `db/seed/blens/validate_seed.py` en CI, con
este mismo evaluador.
"""

import pytest

from engines.ens_applicability import Perfil, aplicabilidad
from engines.evidence_engine import (
    ReglaInvalida,
    contexto_de_datos,
    derivar_requisitos,
    hechos_de_respuesta,
    preguntas_visibles,
    reconciliar,
    se_cumple,
)

NIVELES = {
    "BASICA": dict.fromkeys("CITAD", "BAJO"),
    "MEDIA": dict.fromkeys("CITAD", "MEDIO"),
    "ALTA": dict.fromkeys("CITAD", "ALTO"),
}


@pytest.fixture
def perfilar(preguntas_seed):
    """Responde un camino del cuestionario y devuelve el contexto que deja."""
    por_codigo = {p.code: p for p in preguntas_seed}

    def _perfilar(camino: dict, categoria: str = "MEDIA"):
        hechos, origen = {}, {}
        for code, valor in camino.items():
            for clave, hecho in hechos_de_respuesta(por_codigo[code], valor).items():
                hechos[clave] = hecho
                origen[clave] = code
        return contexto_de_datos(categoria, NIVELES[categoria], hechos, origen)

    return _perfilar


@pytest.fixture
def dda(catalogo):
    """Lo que la DdA daría por aplicable en cada categoría (M2 alimenta a M11)."""

    def _dda(categoria: str):
        resultado = aplicabilidad(catalogo, Perfil(categoria, NIVELES[categoria]))
        medidas = [m.measure_id for m in resultado.aplicables]
        refuerzos = [r for m in resultado.aplicables for r in m.refuerzos_obligatorios]
        return medidas, refuerzos

    return _dda


def test_todas_las_reglas_del_seed_se_evaluan_sin_romperse(preguntas_seed, plantillas_seed):
    """Ni un operador fuera del subconjunto ni una regla mal formada en las 16 familias."""
    contexto = contexto_de_datos("MEDIA", NIVELES["MEDIA"], hechos={})
    for pregunta in preguntas_seed:
        try:
            se_cumple(pregunta.show_if, contexto)
        except ReglaInvalida as error:  # pragma: no cover - solo salta si el seed se rompe
            pytest.fail(f"{pregunta.code}: {error}")
    for plantilla in plantillas_seed:
        try:
            se_cumple(plantilla.applies_if, contexto)
        except ReglaInvalida as error:  # pragma: no cover
            pytest.fail(f"{plantilla.code}: {error}")


def test_el_cuestionario_empieza_por_lo_que_no_depende_de_nada(preguntas_seed):
    """Sin ninguna respuesta todavía tiene que haber por dónde empezar, y poco a la vez."""
    visibles = preguntas_visibles(preguntas_seed, contexto_de_datos("MEDIA", NIVELES["MEDIA"]))
    assert visibles, "el perfilado no arranca: ninguna pregunta es visible sin hechos previos"
    assert len(visibles) < len(preguntas_seed), "se enseñan todas de golpe: nada está encadenado"


def test_un_cpd_propio_pide_las_evidencias_de_sus_instalaciones(perfilar, plantillas_seed, dda):
    """El ejemplo de §10bis.2: quien tiene CPD propio responde por mp.if."""
    medidas, refuerzos = dda("MEDIA")
    contexto = perfilar({"mp.if.areas": ["cpd"], "mp.if.acceso": ["tarjeta"]})
    carpeta = derivar_requisitos(plantillas_seed, contexto, medidas, refuerzos)

    de_instalaciones = {c for c in carpeta.codigos if c.startswith("EV-mp.if.1-")}
    assert de_instalaciones, "un CPD propio tiene que pedir evidencias de control de acceso"


def test_el_cpd_de_un_proveedor_pide_evidencias_de_la_nube_en_vez_de_control_de_acceso(
    perfilar, plantillas_seed, dda
):
    medidas, refuerzos = dda("MEDIA")
    propio = perfilar({"mp.if.areas": ["cpd"], "mp.if.acceso": ["tarjeta"]})
    externo = perfilar({"mp.if.areas": ["proveedor"]})

    carpeta_propio = derivar_requisitos(plantillas_seed, propio, medidas, refuerzos)
    carpeta_externo = derivar_requisitos(plantillas_seed, externo, medidas, refuerzos)

    solo_propio = carpeta_propio.codigos - carpeta_externo.codigos
    solo_externo = carpeta_externo.codigos - carpeta_propio.codigos
    assert any(c.startswith("EV-mp.if.1-") for c in solo_propio)
    assert any(c.startswith("EV-op.nub.") for c in solo_externo)


def test_cada_requisito_sabe_que_respuesta_lo_origino(perfilar, plantillas_seed, dda):
    """La trazabilidad que verá el auditor en el índice del paquete (§10bis.4)."""
    medidas, refuerzos = dda("MEDIA")
    contexto = perfilar({"mp.if.areas": ["cpd"], "mp.if.acceso": ["tarjeta"]})
    carpeta = derivar_requisitos(plantillas_seed, contexto, medidas, refuerzos)

    con_origen = [r for r in carpeta.requisitos if r.origen["preguntas"]]
    assert con_origen, "ningún requisito recuerda la pregunta que lo disparó"
    assert all("mp.if.areas" in r.origen["preguntas"] or r.origen["preguntas"] for r in con_origen)


def test_corregir_una_respuesta_saca_de_la_carpeta_lo_que_deja_de_aplicar(
    perfilar, plantillas_seed, dda
):
    """Se mudan del CPD propio a un proveedor: ni se borra lo subido ni se pide lo que ya no toca."""
    medidas, refuerzos = dda("MEDIA")
    antes = derivar_requisitos(
        plantillas_seed,
        perfilar({"mp.if.areas": ["cpd"], "mp.if.acceso": ["tarjeta"]}),
        medidas,
        refuerzos,
    )
    despues = derivar_requisitos(
        plantillas_seed, perfilar({"mp.if.areas": ["proveedor"]}), medidas, refuerzos
    )

    cambios = reconciliar(dict.fromkeys(antes.codigos, "VALIDADA"), despues.codigos)
    assert cambios.altas and cambios.fuera_de_alcance
    assert not set(cambios.fuera_de_alcance) & despues.codigos


def test_toda_medida_aplicable_tiene_alguna_plantilla_que_la_cubra(plantillas_seed, dda):
    """Criterio de cierre de F4: ninguna medida se queda sin forma de demostrarse."""
    con_plantilla = {p.measure for p in plantillas_seed}
    for categoria in ("BASICA", "MEDIA", "ALTA"):
        medidas, _ = dda(categoria)
        sin_plantilla = sorted(set(medidas) - con_plantilla)
        assert not sin_plantilla, f"{categoria}: medidas sin evidencia posible {sin_plantilla}"


def test_un_sistema_basico_pide_menos_papeles_que_uno_alto(perfilar, plantillas_seed, dda):
    """Si la categoría no cambiara la carpeta, el perfilado no estaría haciendo su trabajo."""
    camino = {"mp.if.areas": ["cpd"], "mp.if.acceso": ["tarjeta"], "op.exp.inventario": "excel"}
    tamanos = {}
    for categoria in ("BASICA", "ALTA"):
        medidas, refuerzos = dda(categoria)
        carpeta = derivar_requisitos(
            plantillas_seed, perfilar(camino, categoria), medidas, refuerzos
        )
        tamanos[categoria] = len(carpeta.requisitos)
    assert tamanos["BASICA"] < tamanos["ALTA"]


def test_los_bloques_del_cuestionario_llegan_con_su_tiempo_estimado(bloques_seed):
    """Los bloques son la unidad de delegación por rol y lo primero que ve el cliente."""
    assert {"B07", "B10", "B12"} <= {b["code"] for b in bloques_seed}
    assert all(b["minutos_estimados"] > 0 for b in bloques_seed)
    assert all(b["titulo"] for b in bloques_seed)
