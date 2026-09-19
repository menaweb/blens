"""Subconjunto de JSON Logic con el que están escritas las reglas del seed.

Las reglas son **dato, no código** (§10bis.3): viven en `db/seed/blens/*.yaml`, las evalúa
este módulo en el backend y las evaluará el mismo subconjunto en el frontend para decidir
qué pregunta se enseña sin ir al servidor.

Por qué un evaluador propio y no una librería:

- El seed usa **seis operadores** (`==`, `!=`, `>=`, `in`, `and`, `or`) más `var`. Todo lo
  demás sería superficie de ataque sobre reglas que acaban en un informe de auditoría.
- Hace falta la **misma semántica exacta** en Python y en TypeScript. Con dos librerías
  distintas, la divergencia aparece justo en los bordes (nulos, comparaciones entre tipos).
- Un operador desconocido **revienta** (`ReglaInvalida`) en lugar de evaluar a falso en
  silencio: una errata en el seed tiene que parar la carga, no cambiar la carpeta del
  cliente sin que nadie se entere.

Semántica, elegida para ser determinista antes que fiel a JavaScript:

- `var` resuelve rutas con puntos recorriendo `Mapping`s. Lo que no existe vale `None`.
- Las comparaciones con `None` son **falsas**, nunca comparan tipos distintos ni lanzan.
- `in` mira dentro de listas, tuplas, conjuntos y cadenas; con `None` es falso.
- **Un hecho con varios valores se compara como conjunto**: si la respuesta a «marca todo
  lo que uses» deja `cpd_acceso = ["tarjeta", "llave"]`, tanto `== "llave"` como
  `in ["tarjeta", "biometria"]` se cumplen. Es lo que significa una pregunta de opción
  múltiple, y sin esto una respuesta más completa pediría menos evidencias que una pobre.
  `!=` es su negación: se cumple cuando **ninguno** de los valores coincide.
- Verdad de un valor: la de Python (`0`, `""`, `[]` y `None` son falsos).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["ReglaInvalida", "evaluar", "hechos_citados", "variables_citadas"]


class ReglaInvalida(ValueError):
    """La regla usa un operador o una forma que este subconjunto no admite."""


def evaluar(regla: Any, datos: Mapping[str, Any]) -> Any:
    """Evalúa una regla JSON Logic contra `datos`. Sin regla, verdadero."""
    if regla is None:
        return True
    if not isinstance(regla, Mapping):
        return regla  # literal: número, cadena, lista de literales…

    if len(regla) != 1:
        raise ReglaInvalida(f"una operación por objeto; llegaron {sorted(regla)}")
    ((operador, argumento),) = regla.items()

    if operador == "var":
        return _var(argumento, datos)

    argumentos = (
        argumento
        if isinstance(argumento, Sequence) and not isinstance(argumento, (str, bytes))
        else [argumento]
    )

    # `and` y `or` cortocircuitan: una regla puede preguntar por un hecho solo después de
    # haber comprobado que tiene sentido preguntarlo.
    if operador == "and":
        resultado: Any = True
        for parte in argumentos:
            resultado = evaluar(parte, datos)
            if not resultado:
                return resultado
        return resultado
    if operador == "or":
        resultado = False
        for parte in argumentos:
            resultado = evaluar(parte, datos)
            if resultado:
                return resultado
        return resultado

    valores = [evaluar(parte, datos) for parte in argumentos]

    if operador == "!":
        return not valores[0]
    if operador == "!!":
        return bool(valores[0])
    if operador == "if":
        return _si(valores)
    if operador == "==":
        return _iguales(valores[0], valores[1])
    if operador == "!=":
        return not _iguales(valores[0], valores[1])
    if operador in _COMPARACIONES:
        return _comparar(operador, valores)
    if operador == "in":
        return _dentro(valores[0], valores[1])

    raise ReglaInvalida(f"operador no admitido: {operador!r}")


def variables_citadas(regla: Any) -> set[str]:
    """Rutas que la regla lee. Sirve para saber de qué depende antes de evaluarla."""
    citadas: set[str] = set()
    _recorrer(regla, citadas)
    return citadas


def hechos_citados(regla: Any) -> set[str]:
    """Claves de `ProfileFact` de las que depende la regla, ya sin el prefijo."""
    return {
        ruta[len("hechos.") :] for ruta in variables_citadas(regla) if ruta.startswith("hechos.")
    }


# --- interioridades ----------------------------------------------------------------

_COMPARACIONES = {">", ">=", "<", "<="}


def _var(argumento: Any, datos: Mapping[str, Any]) -> Any:
    """`{"var": "a.b"}`, o `{"var": ["a.b", por_defecto]}`."""
    por_defecto = None
    if isinstance(argumento, Sequence) and not isinstance(argumento, (str, bytes)):
        ruta = argumento[0] if argumento else ""
        if len(argumento) > 1:
            por_defecto = argumento[1]
    else:
        ruta = argumento
    if ruta in ("", None):
        return datos
    if not isinstance(ruta, str):
        raise ReglaInvalida(f"la ruta de var tiene que ser texto: {ruta!r}")

    actual: Any = datos
    for tramo in ruta.split("."):
        if isinstance(actual, Mapping):
            try:
                actual = actual[tramo]
            except KeyError:
                return por_defecto
        else:
            return por_defecto
    return actual


def _si(valores: list[Any]) -> Any:
    """`if` encadenado: condición, entonces, condición, entonces… si no."""
    indice = 0
    while indice + 1 < len(valores):
        if valores[indice]:
            return valores[indice + 1]
        indice += 2
    return valores[indice] if indice < len(valores) else None


def _iguales(izquierda: Any, derecha: Any) -> bool:
    """Igualdad estricta, con dos salvedades: los booleanos no son 1 ni 0, y una lista de
    valores se cumple si la cumple alguno de sus elementos."""
    if _es_conjunto(izquierda) or _es_conjunto(derecha):
        izquierdos = list(izquierda) if _es_conjunto(izquierda) else [izquierda]
        derechos = list(derecha) if _es_conjunto(derecha) else [derecha]
        return any(_iguales(i, d) for i in izquierdos for d in derechos)
    if izquierda is None or derecha is None:
        return izquierda is None and derecha is None
    if isinstance(izquierda, bool) != isinstance(derecha, bool):
        return False
    return izquierda == derecha


def _es_conjunto(valor: Any) -> bool:
    return isinstance(valor, (list, tuple, set, frozenset))


def _comparar(operador: str, valores: list[Any]) -> bool:
    """`>=` y compañía, admitiendo la forma de tres argumentos (a < b < c)."""
    for izquierda, derecha in zip(valores, valores[1:], strict=False):
        if not _numeros(izquierda, derecha):
            return False
        if operador == ">" and not izquierda > derecha:
            return False
        if operador == ">=" and not izquierda >= derecha:
            return False
        if operador == "<" and not izquierda < derecha:
            return False
        if operador == "<=" and not izquierda <= derecha:
            return False
    return True


def _numeros(*valores: Any) -> bool:
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valores)


def _dentro(aguja: Any, pajar: Any) -> bool:
    if pajar is None or aguja is None:
        return False
    if isinstance(pajar, str):
        if _es_conjunto(aguja):
            return any(isinstance(v, str) and v in pajar for v in aguja)
        return isinstance(aguja, str) and aguja in pajar
    if _es_conjunto(pajar):
        return any(_iguales(aguja, elemento) for elemento in pajar)
    return False


def _recorrer(nodo: Any, citadas: set[str]) -> None:
    if isinstance(nodo, Mapping):
        for clave, valor in nodo.items():
            if clave == "var":
                ruta = valor[0] if isinstance(valor, list) and valor else valor
                if isinstance(ruta, str) and ruta:
                    citadas.add(ruta)
            else:
                _recorrer(valor, citadas)
    elif isinstance(nodo, (list, tuple)):
        for elemento in nodo:
            _recorrer(elemento, citadas)
