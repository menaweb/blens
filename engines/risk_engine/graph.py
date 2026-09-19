"""Propagación del valor por el grafo de dependencias (§9.1).

El valor nace en los activos terminales (información y servicios) y **desciende** a los
que los soportan: si la sede electrónica vale 9 en disponibilidad y depende al 100 % de
un servidor, ese servidor vale 9 en disponibilidad aunque por sí mismo no valga nada.

    accumulated(a,d) = max( own(a,d),
                            max sobre {p : arista p→a} de degree(p→a) × accumulated(p,d) )

La arista va del que **depende** al que le **da soporte**: `p → a` se lee «p depende de a
en un grado». Por eso el orden topológico coloca a cada activo después de todos los que
dependen de él: cuando le toca, sus fuentes de valor ya están calculadas.

El grafo tiene que ser un DAG. Un ciclo no es un caso raro que se pueda ignorar: es un
error de modelado del cliente («la base de datos depende del servidor y el servidor de la
base de datos») y hay que devolvérselo dicho en castellano, con los activos implicados,
no con un `RecursionError`.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

#: Cuatro decimales: el valor propagado se guarda en NUMERIC y alimenta el riesgo.
Q_VALOR = Decimal("0.0001")


def redondear_valor(valor: Decimal) -> Decimal:
    return valor.quantize(Q_VALOR, rounding=ROUND_HALF_UP)


class CicloDetectado(ValueError):
    """El grafo de dependencias tiene un ciclo: no se puede propagar valor."""

    def __init__(self, ciclo: Sequence[str]):
        self.ciclo = tuple(ciclo)
        cadena = " → ".join(self.ciclo)
        super().__init__(
            "Las dependencias forman un círculo y el valor no puede propagarse: "
            f"{cadena}. Quita una de esas dependencias o invierte su sentido."
        )


@dataclass(frozen=True)
class Activo:
    """Un activo con su valoración propia por dimensión (0..10)."""

    id: str
    #: {'D': Decimal('9'), 'C': Decimal('6')} — lo que no aparece vale 0.
    valores: Mapping[str, Decimal] = field(default_factory=dict)

    def valor(self, dim: str) -> Decimal:
        return Decimal(self.valores.get(dim, 0))


@dataclass(frozen=True)
class Dependencia:
    """`parent` depende de `child` en un grado de 0 a 1."""

    parent: str
    child: str
    degree: Decimal = Decimal("1")


def _adyacencia(dependencias: Iterable[Dependencia]) -> dict[str, list[Dependencia]]:
    salida: dict[str, list[Dependencia]] = {}
    for dep in dependencias:
        salida.setdefault(dep.parent, []).append(dep)
    return salida


def _buscar_ciclo(nodos: Sequence[str], salientes: Mapping[str, list[Dependencia]]) -> list[str]:
    """Devuelve un ciclo concreto dentro de `nodos`, para poder nombrarlo en el error.

    Búsqueda en profundidad iterativa: un grafo grande de un cliente no puede tumbar el
    proceso por recursión.
    """
    dentro = set(nodos)
    estado: dict[str, int] = {}
    for raiz in nodos:
        if estado.get(raiz):
            continue
        pila: list[tuple[str, list[str]]] = [
            (raiz, [d.child for d in salientes.get(raiz, []) if d.child in dentro])
        ]
        estado[raiz] = 1
        camino = [raiz]
        while pila:
            nodo, pendientes = pila[-1]
            if pendientes:
                hijo = pendientes.pop(0)
                if estado.get(hijo) == 1:
                    return camino[camino.index(hijo) :] + [hijo]
                if not estado.get(hijo):
                    estado[hijo] = 1
                    camino.append(hijo)
                    pila.append(
                        (hijo, [d.child for d in salientes.get(hijo, []) if d.child in dentro])
                    )
                continue
            estado[nodo] = 2
            camino.pop()
            pila.pop()
    return []  # pragma: no cover - solo se llama cuando ya se sabe que hay ciclo


def orden_topologico(
    activos: Sequence[Activo], dependencias: Sequence[Dependencia]
) -> tuple[str, ...]:
    """Activos ordenados de arriba abajo: primero los que dependen, después los soportes.

    Algoritmo de Kahn recorriendo los activos en el orden en que llegan: dos activos sin
    relación entre sí salen como entraron, así que el resultado es reproducible y la
    pantalla no baraja las filas entre recálculos.
    """
    conocidos = [a.id for a in activos]
    existe = set(conocidos)
    sueltos = [d for d in dependencias if d.parent not in existe or d.child not in existe]
    if sueltos:
        falta = sorted(
            {d.parent for d in sueltos if d.parent not in existe}
            | {d.child for d in sueltos if d.child not in existe}
        )
        raise ValueError(f"Dependencia sobre activos que no existen: {', '.join(falta)}.")

    salientes = _adyacencia(dependencias)
    entrantes = dict.fromkeys(conocidos, 0)
    for dep in dependencias:
        entrantes[dep.child] += 1

    # La cola es un montículo ordenado por posición de entrada: cuando varios activos
    # quedan listos a la vez, sale antes el que el cliente escribió antes.
    posicion = {a: i for i, a in enumerate(conocidos)}
    listos = [posicion[a] for a in conocidos if entrantes[a] == 0]
    heapq.heapify(listos)
    orden: list[str] = []
    while listos:
        nodo = conocidos[heapq.heappop(listos)]
        orden.append(nodo)
        for dep in salientes.get(nodo, []):
            entrantes[dep.child] -= 1
            if entrantes[dep.child] == 0:
                heapq.heappush(listos, posicion[dep.child])

    if len(orden) != len(conocidos):
        colocados = set(orden)
        raise CicloDetectado(_buscar_ciclo([a for a in conocidos if a not in colocados], salientes))
    return tuple(orden)


def propagar(
    activos: Sequence[Activo],
    dependencias: Sequence[Dependencia],
    dimensiones: Sequence[str],
) -> dict[tuple[str, str], Decimal]:
    """Valor acumulado de cada activo en cada dimensión. Levanta `CicloDetectado`."""
    orden = orden_topologico(activos, dependencias)
    por_id = {a.id: a for a in activos}
    entrantes: dict[str, list[Dependencia]] = {}
    for dep in dependencias:
        entrantes.setdefault(dep.child, []).append(dep)

    acumulado: dict[tuple[str, str], Decimal] = {}
    for activo_id in orden:
        activo = por_id[activo_id]
        for dim in dimensiones:
            heredado = max(
                (
                    Decimal(dep.degree) * acumulado[(dep.parent, dim)]
                    for dep in entrantes.get(activo_id, [])
                ),
                default=Decimal("0"),
            )
            acumulado[(activo_id, dim)] = redondear_valor(max(activo.valor(dim), heredado))
    return acumulado
