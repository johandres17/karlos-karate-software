"""Sport configuration registry for KARLOS ANNOTATOR.

Las configuraciones de los deportes de la edición, vistas desde el catálogo.
Antes este módulo importaba las cuatro; ahora cada deporte trae la suya
(``SportPack.configuracion()``, decisión 0004) y aquí se ofrecen como
siempre, para que quien las lee no tenga que cambiar:

- ``SPORTS``: id del deporte → su configuración;
- ``SPORT_LIST``: id, nombre y abreviatura de cada uno.

Las dos siguen el orden de la edición y se leen al usarlas, no al importar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from karlos_core import catalogo


class _Configuraciones(Mapping):
    """id → configuración, de solo lectura."""

    def __getitem__(self, id: str) -> dict[str, Any]:
        if id not in catalogo.registrados():
            raise KeyError(id)
        return catalogo.paquete(id).configuracion()

    def __iter__(self):
        return iter(catalogo.registrados())

    def __len__(self) -> int:
        return len(catalogo.registrados())


class _Lista(Sequence):
    """[{"id", "name", "short"}], de solo lectura."""

    def _filas(self) -> list[dict[str, str]]:
        return [{"id": id, "name": cfg["sport"]["name"], "short": cfg["sport"]["short"]}
                for id, cfg in SPORTS.items()]

    def __getitem__(self, i):
        return self._filas()[i]

    def __len__(self) -> int:
        return len(catalogo.registrados())


SPORTS: Mapping[str, dict[str, Any]] = _Configuraciones()
SPORT_LIST: Sequence[dict[str, str]] = _Lista()
