"""Propagación de valor por el grafo de dependencias (§9.1)."""

from decimal import Decimal

import pytest

from engines.risk_engine import Activo, CicloDetectado, Dependencia, orden_topologico, propagar


def d(valor: str) -> Decimal:
    return Decimal(valor)


def test_el_valor_desciende_al_activo_que_da_soporte():
    """La sede vale 9 en D; el servidor que la sostiene al 100 % pasa a valer 9."""
    activos = [Activo("sede", {"D": d("9")}), Activo("servidor")]
    valores = propagar(activos, [Dependencia("sede", "servidor", d("1"))], ["D"])
    assert valores[("sede", "D")] == d("9.0000")
    assert valores[("servidor", "D")] == d("9.0000")


def test_una_dependencia_parcial_atenua_el_valor():
    activos = [Activo("sede", {"D": d("9")}), Activo("cpd")]
    valores = propagar(activos, [Dependencia("sede", "cpd", d("0.5"))], ["D"])
    assert valores[("cpd", "D")] == d("4.5000")


def test_manda_el_camino_mas_valioso_no_la_suma():
    """Dos servicios sobre el mismo servidor: hereda el mayor, no la suma (§9.1)."""
    activos = [
        Activo("sede", {"D": d("9")}),
        Activo("intranet", {"D": d("4")}),
        Activo("servidor"),
    ]
    deps = [
        Dependencia("sede", "servidor", d("0.5")),
        Dependencia("intranet", "servidor", d("1")),
    ]
    valores = propagar(activos, deps, ["D"])
    assert valores[("servidor", "D")] == d("4.5000")


def test_el_valor_propio_nunca_se_pierde():
    activos = [Activo("sede", {"D": d("2")}), Activo("bbdd", {"D": d("7")})]
    valores = propagar(activos, [Dependencia("sede", "bbdd", d("1"))], ["D"])
    assert valores[("bbdd", "D")] == d("7.0000")


def test_el_valor_atraviesa_varios_saltos():
    activos = [Activo("servicio", {"D": d("10")}), Activo("vm"), Activo("host"), Activo("sai")]
    deps = [
        Dependencia("servicio", "vm", d("1")),
        Dependencia("vm", "host", d("0.8")),
        Dependencia("host", "sai", d("0.5")),
    ]
    valores = propagar(activos, deps, ["D"])
    assert valores[("host", "D")] == d("8.0000")
    assert valores[("sai", "D")] == d("4.0000")


def test_cada_dimension_va_por_su_cuenta():
    activos = [Activo("expediente", {"C": d("8"), "D": d("3")}), Activo("disco")]
    valores = propagar(activos, [Dependencia("expediente", "disco", d("1"))], ["C", "D"])
    assert valores[("disco", "C")] == d("8.0000")
    assert valores[("disco", "D")] == d("3.0000")


def test_dimension_no_valorada_vale_cero():
    valores = propagar([Activo("x", {"D": d("5")})], [], ["C"])
    assert valores[("x", "C")] == d("0.0000")


# --- Orden y ciclos ---------------------------------------------------------------


def test_orden_topologico_pone_antes_al_que_depende():
    activos = [Activo("host"), Activo("vm"), Activo("servicio")]
    deps = [Dependencia("servicio", "vm"), Dependencia("vm", "host")]
    assert orden_topologico(activos, deps) == ("servicio", "vm", "host")


def test_activos_sueltos_conservan_el_orden_de_entrada():
    activos = [Activo("a"), Activo("b"), Activo("c")]
    assert orden_topologico(activos, []) == ("a", "b", "c")


def test_un_ciclo_se_detecta_y_se_explica():
    activos = [Activo("bbdd", {"D": d("5")}), Activo("servidor")]
    deps = [Dependencia("bbdd", "servidor"), Dependencia("servidor", "bbdd")]
    with pytest.raises(CicloDetectado) as error:
        propagar(activos, deps, ["D"])
    assert error.value.ciclo == ("bbdd", "servidor", "bbdd")
    assert "círculo" in str(error.value)
    assert "bbdd → servidor → bbdd" in str(error.value)


def test_un_ciclo_largo_senala_solo_los_implicados():
    activos = [Activo("a"), Activo("b"), Activo("c"), Activo("d")]
    deps = [
        Dependencia("a", "b"),
        Dependencia("b", "c"),
        Dependencia("c", "d"),
        Dependencia("d", "b"),
    ]
    with pytest.raises(CicloDetectado) as error:
        orden_topologico(activos, deps)
    assert error.value.ciclo == ("b", "c", "d", "b")


def test_un_activo_que_depende_de_si_mismo_tambien_es_ciclo():
    with pytest.raises(CicloDetectado):
        orden_topologico([Activo("a")], [Dependencia("a", "a")])


def test_un_rombo_no_es_un_ciclo():
    """Dos caminos hasta el mismo activo son normales: no se visita dos veces."""
    activos = [Activo("s", {"D": d("6")}), Activo("a"), Activo("b"), Activo("z")]
    deps = [
        Dependencia("s", "a"),
        Dependencia("s", "b"),
        Dependencia("a", "z", d("0.5")),
        Dependencia("b", "z", d("0.9")),
    ]
    valores = propagar(activos, deps, ["D"])
    assert valores[("z", "D")] == d("5.4000")


def test_dependencia_sobre_un_activo_que_no_existe():
    with pytest.raises(ValueError, match="no existen: fantasma"):
        orden_topologico([Activo("a")], [Dependencia("a", "fantasma")])


def test_el_ciclo_se_encuentra_aunque_arrastre_activos_sanos():
    """Lo que cuelga de un ciclo también se atasca; el mensaje nombra solo el círculo.

    Aquí `x` e `y` no forman parte de ningún ciclo, pero dependen de `c`, que sí, así
    que tampoco se pueden ordenar. El error tiene que señalar `c → d → c`, no arrastrar
    a los otros dos a la explicación.
    """
    activos = [Activo("x"), Activo("y"), Activo("c"), Activo("d")]
    deps = [
        Dependencia("c", "x"),
        Dependencia("x", "y"),
        Dependencia("c", "d"),
        Dependencia("d", "c"),
    ]
    with pytest.raises(CicloDetectado) as error:
        orden_topologico(activos, deps)
    assert error.value.ciclo == ("c", "d", "c")
