"""El motor de scoring, probado contra las reglas de §8 y del handoff.

Cobertura del 100 % exigida por el plan de fase: cada rama de decisión tiene su caso.
"""

from decimal import Decimal

import pytest

from engines.scoring_engine import (
    AMARILLO,
    GRIS,
    ROJO,
    VERDE,
    Medida,
    objetivo_de,
    porcentaje,
    puntuar,
    semaforo,
)


def medida(code, madurez=None, **extra):
    marco, familia = _marco_familia(code)
    return Medida(measure_id=code, marco=marco, familia=familia, madurez=madurez, **extra)


def _marco_familia(code: str) -> tuple[str, str]:
    partes = code.split(".")
    return partes[0], ".".join(partes[:2]) if partes[0] != "org" else "org"


# --- Tabla de la 815 -------------------------------------------------------------


@pytest.mark.parametrize(
    ("nivel", "pct"), [(0, "0"), (1, "10"), (2, "50"), (3, "80"), (4, "90"), (5, "100")]
)
def test_porcentaje_por_nivel(nivel, pct):
    assert porcentaje(nivel) == Decimal(pct)


def test_porcentaje_fuera_de_escala():
    with pytest.raises(ValueError, match="L0-L5"):
        porcentaje(6)


@pytest.mark.parametrize(
    ("categoria", "objetivo"), [("BASICA", 2), ("MEDIA", 3), ("ALTA", 4), ("", 0)]
)
def test_objetivo_por_categoria(categoria, objetivo):
    assert objetivo_de(categoria) == objetivo


def test_objetivo_de_medida_fuera_de_escala():
    with pytest.raises(ValueError, match="Objetivo"):
        puntuar([medida("org.1", 3, objetivo=9)], "MEDIA")


# --- Semáforo (§8 y prototipo del checklist) -------------------------------------


@pytest.mark.parametrize(
    ("delta", "color"),
    [(2, VERDE), (0, VERDE), (-1, AMARILLO), (-2, ROJO), (-5, ROJO), (None, GRIS)],
)
def test_semaforo(delta, color):
    assert semaforo(delta) == color


# --- Por medida -------------------------------------------------------------------


def test_medida_en_objetivo():
    fila = puntuar([medida("op.exp.6", 3)], "MEDIA").medidas[0]
    assert (fila.objetivo, fila.delta, fila.semaforo) == (3, 0, VERDE)
    assert fila.madurez_pct == Decimal("80.00")
    assert fila.cumplimiento_pct == Decimal("100.00")
    assert fila.puntos_a_ganar == Decimal("0.00")
    assert fila.en_objetivo


def test_medida_por_encima_del_objetivo_no_pasa_del_cien():
    """Pasarse del objetivo es bueno, pero no compensa otra medida por debajo."""
    fila = puntuar([medida("mp.info.6", 5)], "BASICA").medidas[0]
    assert fila.delta == 3
    assert fila.cumplimiento_pct == Decimal("100.00")


def test_medida_por_debajo():
    fila = puntuar([medida("op.mon.1", 1)], "MEDIA").medidas[0]
    assert fila.delta == -2
    assert fila.semaforo == ROJO
    # 10 % logrado sobre un objetivo del 80 %.
    assert fila.cumplimiento_pct == Decimal("12.50")
    assert fila.puntos_a_ganar == Decimal("87.50")


def test_sin_datos_puntua_cero_y_no_finge_delta():
    """El indicador nunca redondea al alza: sin valorar es 0, no «pendiente»."""
    fila = puntuar([medida("org.4")], "MEDIA").medidas[0]
    assert fila.sin_datos
    assert fila.madurez is None
    assert fila.delta is None
    assert fila.semaforo == GRIS
    assert fila.madurez_pct == Decimal("0.00")
    assert not fila.en_objetivo


def test_medida_que_no_aplica_no_estorba():
    resultado = puntuar([medida("op.nub.1", 0, aplica=False), medida("org.1", 3)], "MEDIA")
    no_aplica = resultado.medida("op.nub.1")
    assert no_aplica.semaforo == GRIS
    assert no_aplica.puntos_a_ganar == Decimal("0.00")
    # El índice del sistema solo mira las aplicables.
    assert resultado.sistema.medidas == 1
    assert resultado.sistema.cumplimiento == Decimal("100.00")


def test_categoria_sin_determinar_no_exige_nada():
    resultado = puntuar([medida("org.1", 0)], "")
    assert resultado.objetivo_categoria == 0
    assert resultado.medidas[0].cumplimiento_pct == Decimal("100.00")


# --- Madurez no soportada (§10bis) ------------------------------------------------


def test_madurez_no_soportada_no_cuenta_como_alcanzada():
    fila = puntuar([medida("op.exp.6", 4, soportada=False)], "MEDIA").medidas[0]
    assert fila.no_soportada
    assert fila.madurez == 4  # el nivel declarado no se toca
    assert fila.delta == 1  # el delta refleja lo declarado: es lo que dice el cliente
    assert not fila.en_objetivo  # pero no suma
    # Puntúa como un nivel por debajo del objetivo (L2 = 50 % sobre un objetivo de 80 %).
    assert fila.cumplimiento_pct == Decimal("62.50")


def test_sin_evidencia_pero_por_debajo_del_objetivo_no_se_marca():
    """La marca es para quien dice haber llegado, no para quien aún no ha llegado."""
    fila = puntuar([medida("op.exp.6", 1, soportada=False)], "MEDIA").medidas[0]
    assert not fila.no_soportada


def test_no_soportada_con_objetivo_cero():
    fila = puntuar([medida("org.1", 0, soportada=False)], "").medidas[0]
    assert fila.no_soportada
    assert fila.cumplimiento_pct == Decimal("100.00")


# --- Composición por el peor componente -------------------------------------------


def test_la_familia_vale_lo_que_su_peor_medida():
    resultado = puntuar(
        [
            medida("op.exp.1", 4),
            medida("op.exp.2", 4),
            medida("op.exp.3", 4),
            medida("op.exp.4", 0),
        ],
        "MEDIA",
    )
    familia = resultado.por_familia["op.exp"]
    assert familia.cumplimiento == Decimal("0.00")
    assert familia.peor == "op.exp.4"
    # La media existe, pero es dato informativo, no el índice.
    assert familia.cumplimiento_medio == Decimal("75.00")
    assert familia.madurez_media == Decimal("67.50")


def test_indices_por_marco_y_sistema():
    resultado = puntuar([medida("org.1", 3), medida("op.exp.6", 2), medida("mp.if.1", 5)], "MEDIA")
    assert set(resultado.por_marco) == {"org", "op", "mp"}
    assert resultado.por_marco["org"].cumplimiento == Decimal("100.00")
    assert resultado.por_marco["op"].cumplimiento == Decimal("62.50")
    assert resultado.sistema.cumplimiento == Decimal("62.50")
    assert resultado.sistema.peor == "op.exp.6"
    assert resultado.sistema.madurez == Decimal("50.00")
    assert resultado.sistema.con_datos == 3
    assert resultado.sistema.en_objetivo == 2


def test_ambito_sin_medidas_aplicables_vale_cero_no_cien():
    resultado = puntuar([medida("op.nub.1", 5, aplica=False)], "MEDIA")
    assert resultado.sistema.medidas == 0
    assert resultado.sistema.cumplimiento == Decimal("0.00")
    assert resultado.sistema.peor is None


def test_sin_medidas():
    resultado = puntuar([], "BASICA")
    assert resultado.medidas == ()
    assert resultado.sistema.cumplimiento == Decimal("0.00")


# --- Brechas y determinismo --------------------------------------------------------


def test_brechas_ordenadas_por_lo_que_cuestan():
    resultado = puntuar(
        [
            medida("op.exp.6", 2),  # 62.5 → faltan 37.5
            medida("op.mon.1", 0),  # 0    → faltan 100
            medida("org.1", 3),  # en objetivo
            medida("mp.per.3", 1),  # 12.5 → faltan 87.5
            medida("op.nub.1", 0, aplica=False),
        ],
        "MEDIA",
    )
    assert [m.measure_id for m in resultado.brechas] == ["op.mon.1", "mp.per.3", "op.exp.6"]


def test_empate_en_brechas_se_desempata_por_codigo():
    resultado = puntuar([medida("op.exp.6", 1), medida("mp.if.1", 1)], "MEDIA")
    assert [m.measure_id for m in resultado.brechas] == ["mp.if.1", "op.exp.6"]


def test_no_soportada_aparece_en_las_brechas():
    resultado = puntuar([medida("op.exp.6", 5, soportada=False)], "MEDIA")
    assert [m.measure_id for m in resultado.brechas] == ["op.exp.6"]
    assert resultado.sistema.no_soportadas == 1


def test_el_orden_de_entrada_no_cambia_el_resultado():
    entrada = [medida("mp.if.1", 2), medida("org.1", 4), medida("op.exp.6", 1)]
    uno = puntuar(entrada, "MEDIA")
    otro = puntuar(list(reversed(entrada)), "MEDIA")
    assert uno == otro
    assert [m.measure_id for m in uno.medidas] == ["mp.if.1", "op.exp.6", "org.1"]


def test_medida_inexistente():
    assert puntuar([medida("org.1", 2)], "MEDIA").medida("no.existe") is None
