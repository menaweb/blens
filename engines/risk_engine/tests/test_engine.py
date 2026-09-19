"""Riesgo intrínseco, residual, agregación y simulador (§9.2 a §9.4).

El primer test es **el ejemplo trabajado de §9.3** y es obligatorio: si cambia el
resultado, ha cambiado el método, y eso se discute antes de tocar el código.
"""

from decimal import Decimal

import pytest

from engines.risk_engine import (
    FREQ,
    IMPACT,
    MAX,
    MEJOR,
    SUMA,
    Activo,
    Amenaza,
    Dependencia,
    Salvaguarda,
    agregar_por_activo,
    analizar,
    simular,
)


def d(valor: str) -> Decimal:
    return Decimal(valor)


#: Tabla `MaturityEffectiveness` por defecto (§7.1). En producción viene de la base de
#: datos, que es donde se puede configurar; aquí se escribe entera a propósito.
EFICACIA = {
    0: d("0"),
    1: d("0.1"),
    2: d("0.5"),
    3: d("0.8"),
    4: d("0.9"),
    5: d("1.0"),
}


# --- §9.3: test de regresión obligatorio -------------------------------------------


@pytest.fixture
def caso_9_3():
    """Servidor que hereda D=9 de la Sede al 100 %, amenaza de denegación de servicio."""
    activos = [Activo("sede", {"D": d("9")}), Activo("servidor")]
    dependencias = [Dependencia("sede", "servidor", d("1"))]
    amenazas = [
        Amenaza(
            asset_id="servidor",
            threat_id="A.24",
            dim="D",
            frequency=d("2"),
            degradation=d("0.80"),
        )
    ]
    salvaguardas = [
        Salvaguarda("A.24", "op.mon.1", FREQ, d("0.4"), nivel=3),
        Salvaguarda("A.24", "mp.com.1", FREQ, d("0.5"), nivel=2),
        Salvaguarda("A.24", "op.cont.2", IMPACT, d("0.6"), nivel=3),
    ]
    return activos, dependencias, amenazas, salvaguardas


def test_ejemplo_trabajado_de_la_especificacion(caso_9_3):
    activos, dependencias, amenazas, salvaguardas = caso_9_3
    analisis = analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=salvaguardas,
        eficacia_por_nivel=EFICACIA,
    )
    riesgo = analisis.de("servidor", "A.24", "D")

    assert riesgo.valor_acumulado == d("9.0000")
    assert riesgo.riesgo_intrinseco == d("14.4000")
    assert riesgo.factor_freq == d("0.510000")
    assert riesgo.factor_impacto == d("0.520000")
    # §9.3: 3,82 con tolerancia de una centésima.
    assert abs(riesgo.riesgo_residual - d("3.82")) <= d("0.01")
    assert riesgo.reduccion_pct == d("73.48")


def test_el_desglose_explica_de_donde_sale_cada_factor(caso_9_3):
    activos, dependencias, amenazas, salvaguardas = caso_9_3
    analisis = analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=salvaguardas,
        eficacia_por_nivel=EFICACIA,
    )
    aportaciones = {a.measure_id: a for a in analisis.de("servidor", "A.24", "D").salvaguardas}
    assert aportaciones["op.mon.1"].reduccion == d("0.320000")  # 0,8 × 0,4
    assert aportaciones["mp.com.1"].reduccion == d("0.250000")  # 0,5 × 0,5
    assert aportaciones["op.cont.2"].reduccion == d("0.480000")  # 0,8 × 0,6
    # Primero las de impacto y luego las de frecuencia: es el orden de la pantalla.
    assert [a.aspect for a in analisis.de("servidor", "A.24", "D").salvaguardas] == [
        IMPACT,
        FREQ,
        FREQ,
    ]


# --- Acoplamiento con la madurez ----------------------------------------------------


def test_subir_la_madurez_baja_el_riesgo_residual(caso_9_3):
    activos, dependencias, amenazas, _ = caso_9_3
    from dataclasses import replace

    base = [
        Salvaguarda("A.24", "op.mon.1", FREQ, d("0.4"), nivel=3),
        Salvaguarda("A.24", "op.cont.2", IMPACT, d("0.6"), nivel=3),
    ]

    def residual(salvaguardas):
        return (
            analizar(
                activos=activos,
                dependencias=dependencias,
                amenazas=amenazas,
                salvaguardas=salvaguardas,
                eficacia_por_nivel=EFICACIA,
            )
            .riesgos[0]
            .riesgo_residual
        )

    antes = residual(base)
    despues = residual([replace(s, nivel=5) for s in base])
    assert despues < antes


def test_sin_salvaguardas_el_residual_es_el_intrinseco(caso_9_3):
    activos, dependencias, amenazas, _ = caso_9_3
    riesgo = analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=[],
        eficacia_por_nivel=EFICACIA,
    ).riesgos[0]
    assert riesgo.riesgo_residual == riesgo.riesgo_intrinseco
    assert riesgo.factor_freq == Decimal("1")
    assert riesgo.reduccion_pct == d("0.00")


def test_una_medida_en_l0_no_reduce_nada(caso_9_3):
    activos, dependencias, amenazas, _ = caso_9_3
    riesgo = analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=[Salvaguarda("A.24", "op.mon.1", FREQ, d("0.7"), nivel=0)],
        eficacia_por_nivel=EFICACIA,
    ).riesgos[0]
    assert riesgo.riesgo_residual == riesgo.riesgo_intrinseco


def test_ninguna_combinacion_llega_a_cero(caso_9_3):
    """Un riesgo residual de cero no lo firma un auditor: la amenaza no desaparece."""
    activos, dependencias, amenazas, _ = caso_9_3
    salvaguardas = [
        Salvaguarda("A.24", f"m{i}", aspecto, d("0.7"), nivel=5)
        for i in range(6)
        for aspecto in (FREQ, IMPACT)
    ]
    riesgo = analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=salvaguardas,
        eficacia_por_nivel=EFICACIA,
    ).riesgos[0]
    assert riesgo.riesgo_residual > 0


def test_madurez_no_soportada_cuenta_la_mitad(caso_9_3):
    activos, dependencias, amenazas, _ = caso_9_3
    declarada = Salvaguarda("A.24", "op.mon.1", FREQ, d("0.5"), nivel=4)
    sin_evidencia = Salvaguarda("A.24", "op.mon.1", FREQ, d("0.5"), nivel=4, soportada=False)
    assert declarada.eficacia(EFICACIA) == d("0.9")
    assert sin_evidencia.eficacia(EFICACIA) == d("0.450000")


def test_nivel_sin_eficacia_definida():
    with pytest.raises(ValueError, match="sin eficacia"):
        Salvaguarda("A.24", "op.mon.1", FREQ, d("0.5"), nivel=7).eficacia(EFICACIA)


# --- Selección de salvaguardas -------------------------------------------------------


def test_una_salvaguarda_de_otra_dimension_no_cuenta(caso_9_3):
    activos, dependencias, amenazas, _ = caso_9_3
    riesgo = analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=[Salvaguarda("A.24", "mp.info.3", FREQ, d("0.6"), nivel=5, dim="I")],
        eficacia_por_nivel=EFICACIA,
    ).riesgos[0]
    assert riesgo.factor_freq == Decimal("1")


def test_una_salvaguarda_de_su_dimension_si_cuenta(caso_9_3):
    activos, dependencias, amenazas, _ = caso_9_3
    riesgo = analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=[Salvaguarda("A.24", "op.cont.2", FREQ, d("0.6"), nivel=5, dim="D")],
        eficacia_por_nivel=EFICACIA,
    ).riesgos[0]
    assert riesgo.factor_freq == d("0.400000")


def test_una_salvaguarda_de_otra_amenaza_no_cuenta(caso_9_3):
    activos, dependencias, amenazas, _ = caso_9_3
    riesgo = analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=[Salvaguarda("N.1", "mp.if.5", FREQ, d("0.5"), nivel=5)],
        eficacia_por_nivel=EFICACIA,
    ).riesgos[0]
    assert riesgo.riesgo_residual == riesgo.riesgo_intrinseco


# --- Modos de combinación -------------------------------------------------------------


def test_modo_mejor_se_queda_con_la_salvaguarda_mas_fuerte(caso_9_3):
    activos, dependencias, amenazas, salvaguardas = caso_9_3
    riesgo = analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=salvaguardas,
        eficacia_por_nivel=EFICACIA,
        modo=MEJOR,
    ).riesgos[0]
    assert riesgo.factor_freq == d("0.680000")  # 1 − 0,32, la mayor de las dos
    assert riesgo.riesgo_residual > d("3.82")  # menos optimista que la multiplicativa


def test_modo_desconocido(caso_9_3):
    activos, dependencias, amenazas, salvaguardas = caso_9_3
    with pytest.raises(ValueError, match="Modo de combinación"):
        analizar(
            activos=activos,
            dependencias=dependencias,
            amenazas=amenazas,
            salvaguardas=salvaguardas,
            eficacia_por_nivel=EFICACIA,
            modo="PROMEDIO",
        )


# --- Varias instancias, agregación y errores -------------------------------------------


@pytest.fixture
def analisis_multiple():
    activos = [Activo("sede", {"D": d("9"), "C": d("6")}), Activo("servidor")]
    dependencias = [Dependencia("sede", "servidor", d("1"))]
    amenazas = [
        Amenaza("servidor", "A.24", "D", d("2"), d("0.8")),
        Amenaza("servidor", "A.11", "C", d("1"), d("0.5")),
        Amenaza("sede", "E.1", "D", d("3"), d("0.1")),
    ]
    return analizar(
        activos=activos,
        dependencias=dependencias,
        amenazas=amenazas,
        salvaguardas=[],
        eficacia_por_nivel=EFICACIA,
    )


def test_los_riesgos_salen_ordenados_y_por_dimension(analisis_multiple):
    assert [(r.asset_id, r.threat_id) for r in analisis_multiple.riesgos] == [
        ("sede", "E.1"),
        ("servidor", "A.11"),
        ("servidor", "A.24"),
    ]
    assert analisis_multiple.de("servidor", "A.11", "C").valor_acumulado == d("6.0000")


def test_agregacion_por_activo(analisis_multiple):
    peor = agregar_por_activo(analisis_multiple.riesgos, MAX)
    total = agregar_por_activo(analisis_multiple.riesgos, SUMA)
    assert peor["servidor"] == d("14.4000")
    assert total["servidor"] == d("17.4000")
    assert peor["sede"] == total["sede"] == d("2.7000")


def test_modo_de_agregacion_desconocido(analisis_multiple):
    with pytest.raises(ValueError, match="agregación"):
        agregar_por_activo(analisis_multiple.riesgos, "MEDIA")


def test_una_amenaza_sobre_un_activo_inexistente():
    with pytest.raises(ValueError, match="activo que no existe"):
        analizar(
            activos=[Activo("a", {"D": d("5")})],
            dependencias=[],
            amenazas=[Amenaza("fantasma", "A.24", "D", d("1"), d("1"))],
            salvaguardas=[],
            eficacia_por_nivel=EFICACIA,
        )


def test_instancia_inexistente(analisis_multiple):
    assert analisis_multiple.de("servidor", "A.99", "D") is None


def test_riesgo_intrinseco_cero_no_divide_por_cero():
    riesgo = analizar(
        activos=[Activo("a")],
        dependencias=[],
        amenazas=[Amenaza("a", "A.24", "D", d("2"), d("0.8"))],
        salvaguardas=[],
        eficacia_por_nivel=EFICACIA,
    ).riesgos[0]
    assert riesgo.riesgo_intrinseco == d("0.0000")
    assert riesgo.reduccion_pct == d("0.00")


# --- Simulador inverso (§9.4) ----------------------------------------------------------


@pytest.fixture
def amenaza_dos():
    return Amenaza("servidor", "A.24", "D", d("2"), d("0.8"))


def test_el_simulador_dice_que_subir_para_llegar_al_objetivo(amenaza_dos):
    salvaguardas = [
        Salvaguarda("A.24", "op.mon.1", FREQ, d("0.4"), nivel=3),
        Salvaguarda("A.24", "mp.com.1", FREQ, d("0.5"), nivel=2),
        Salvaguarda("A.24", "op.cont.2", IMPACT, d("0.6"), nivel=3),
    ]
    simulacion = simular(
        amenaza=amenaza_dos,
        valor_acumulado=d("9"),
        salvaguardas=salvaguardas,
        eficacia_por_nivel=EFICACIA,
        objetivo=d("3.00"),
    )
    assert simulacion.alcanzable
    assert simulacion.riesgo_inicial > d("3.00")
    assert simulacion.riesgo_final <= d("3.00")
    assert simulacion.subidas  # dice qué medidas y hasta qué nivel
    for subida in simulacion.subidas:
        assert subida.nivel_propuesto > subida.nivel_actual


def test_si_ya_se_cumple_el_objetivo_no_propone_nada(amenaza_dos):
    simulacion = simular(
        amenaza=amenaza_dos,
        valor_acumulado=d("9"),
        salvaguardas=[Salvaguarda("A.24", "op.cont.2", IMPACT, d("0.7"), nivel=5)],
        eficacia_por_nivel=EFICACIA,
        objetivo=d("100"),
    )
    assert simulacion.alcanzable
    assert simulacion.subidas == ()
    assert simulacion.riesgo_inicial == simulacion.riesgo_final


def test_un_objetivo_inalcanzable_se_dice_claro(amenaza_dos):
    """Con todo a L5 sigue habiendo riesgo: el simulador no promete lo que no puede."""
    simulacion = simular(
        amenaza=amenaza_dos,
        valor_acumulado=d("9"),
        salvaguardas=[Salvaguarda("A.24", "op.cont.2", IMPACT, d("0.7"), nivel=2)],
        eficacia_por_nivel=EFICACIA,
        objetivo=d("0.01"),
    )
    assert not simulacion.alcanzable
    assert simulacion.subidas == (
        # Ha llegado hasta donde ha podido antes de rendirse.
        simulacion.subidas[0],
    )
    assert simulacion.subidas[0].nivel_propuesto == 5


def test_sin_salvaguardas_no_hay_nada_que_subir(amenaza_dos):
    simulacion = simular(
        amenaza=amenaza_dos,
        valor_acumulado=d("9"),
        salvaguardas=[],
        eficacia_por_nivel=EFICACIA,
        objetivo=d("1"),
    )
    assert not simulacion.alcanzable
    assert simulacion.subidas == ()


def test_el_simulador_es_determinista(amenaza_dos):
    salvaguardas = [
        Salvaguarda("A.24", "mp.com.1", FREQ, d("0.5"), nivel=2),
        Salvaguarda("A.24", "op.mon.1", FREQ, d("0.5"), nivel=2),
    ]
    kwargs = dict(
        amenaza=amenaza_dos,
        valor_acumulado=d("9"),
        eficacia_por_nivel=EFICACIA,
        objetivo=d("6"),
    )
    uno = simular(salvaguardas=salvaguardas, **kwargs)
    otro = simular(salvaguardas=list(reversed(salvaguardas)), **kwargs)
    assert uno == otro
    # A igualdad de reducción gana el código menor.
    assert uno.subidas[0].measure_id == "mp.com.1"
