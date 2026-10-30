"""Dónde está cada módulo: en la 1.0 o después de mudarlo (fase F4).

Estos scripts se corren contra las dos versiones (con el PYTHONPATH de cada
copia). En F4 los módulos del karate se mudaron de ``karlos_annotator`` a
``karlos_karate`` (decisión 0005), y en F5 el núcleo pasó a llamarse
``karlos_core`` (decisión 0006). Se busca primero el sitio nuevo y, si en
esa copia no está, el de la 1.0.
"""
from __future__ import annotations

import importlib
from types import ModuleType


def modulo(nuevo: str, viejo: str) -> ModuleType:
    try:
        return importlib.import_module(nuevo)
    except ModuleNotFoundError as exc:
        # Solo si lo que falta es ese módulo o su paquete (la 1.0 no tiene
        # karlos_karate): si falta otra cosa, es un error de verdad.
        if exc.name not in (nuevo, nuevo.split(".")[0]):
            raise
        return importlib.import_module(viejo)


def poner_la_edicion() -> None:
    """Los deportes los pone una edición desde F5 (decisión 0006); la 1.0
    los registraba sola al importarse."""
    try:
        from karlos_ediciones import karate
    except ModuleNotFoundError as exc:
        if exc.name not in ("karlos_ediciones", "karlos_ediciones.karate"):
            raise
        return
    karate.poner_en_marcha()
