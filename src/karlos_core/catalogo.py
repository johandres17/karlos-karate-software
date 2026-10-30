"""El catálogo de deportes: cuáles hay y cuál se está anotando.

El núcleo no importa ningún deporte: los pide aquí (decisión 0004). La
edición pone los suyos al cargarse (``karlos_core.edicion``) y el
programa marca el que se está anotando cuando la persona lo elige.

Se registra una fábrica y no el paquete: registrar no carga nada, y cada
paquete se construye una sola vez, la primera vez que alguien lo pide.
"""
from __future__ import annotations

from typing import Callable, Optional

from karlos_core.deporte import SportPack


class Catalogo:
    """Los deportes de una edición. El programa usa uno solo (``CATALOGO``);
    las pruebas pueden crear los suyos sin tocarlo."""

    def __init__(self) -> None:
        self._fabricas: dict[str, Callable[[], SportPack]] = {}
        self._paquetes: dict[str, SportPack] = {}
        self._activo: Optional[str] = None

    def registrar(self, id: str, fabrica: Callable[[], SportPack]) -> None:
        """Añade un deporte. Registrar dos veces el mismo es un error: la
        segunda taparía a la primera sin que nadie se enterase."""
        if id in self._fabricas:
            raise ValueError(f"el deporte {id!r} ya está registrado")
        self._fabricas[id] = fabrica

    def registrados(self) -> tuple[str, ...]:
        """Los deportes de la edición, en el orden en que se registraron."""
        return tuple(self._fabricas)

    def paquete(self, id: str) -> SportPack:
        """El paquete de un deporte, construido la primera vez que se pide."""
        if id not in self._paquetes:
            if id not in self._fabricas:
                hay = ", ".join(self._fabricas) or "ninguno"
                raise KeyError(f"deporte no registrado: {id!r} (registrados: {hay})")
            paquete = self._fabricas[id]()
            if paquete.id != id:
                raise ValueError(f"la fábrica de {id!r} devolvió el paquete de {paquete.id!r}")
            self._paquetes[id] = paquete
        return self._paquetes[id]

    def establecer(self, id: str) -> SportPack:
        """Marca el deporte que se está anotando."""
        paquete = self.paquete(id)
        self._activo = id
        return paquete

    def olvidar_activo(self) -> None:
        """Vuelve al deporte por defecto (el primero registrado)."""
        self._activo = None

    def activo(self) -> SportPack:
        """El deporte que se está anotando; si no se ha elegido ninguno, el
        primero que registró la edición."""
        if self._activo is not None:
            return self.paquete(self._activo)
        if not self._fabricas:
            raise LookupError("no hay ningún deporte en el catálogo: falta cargar la edición")
        return self.paquete(next(iter(self._fabricas)))


CATALOGO = Catalogo()

registrar = CATALOGO.registrar
registrados = CATALOGO.registrados
paquete = CATALOGO.paquete
establecer = CATALOGO.establecer
olvidar_activo = CATALOGO.olvidar_activo
activo = CATALOGO.activo


def etiqueta(codigo: str) -> str:
    """Cómo se llama en pantalla el competidor de ese código en el deporte
    activo: «AKA» y «AO» en el karate.

    El código es el del formato común (``karlos_core.formato``); lo que se
    enseña es la etiqueta del deporte.
    """
    for competidor in activo().competidores:
        if competidor.codigo == codigo:
            return competidor.etiqueta
    return codigo


def asistido_disponible() -> bool:
    """Si el deporte activo tiene modo asistido: hace falta su árbol de
    preguntas, que sale de su libro de códigos."""
    return activo().arbol() is not None
