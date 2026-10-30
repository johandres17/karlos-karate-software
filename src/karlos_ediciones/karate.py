"""Karlos Karate: el núcleo con el kárate (decisión 0006).

Desde el código: ``python -m karlos_ediciones.karate``.
"""
from __future__ import annotations

from pathlib import Path

from karlos_core import identidad
from karlos_karate import KaratePack

EDICION = identidad.Edicion(
    nombre="Karlos Karate",
    # 1.2.0: los tres modos de anotación (decisión 0008).
    version="1.2.0",
    identificador="com.karlitos.karate",
    ajustes=("Karlitos", "KarlosKarate"),
    carpeta=Path.home() / ".karlos_karate",
    deportes=(("karate", KaratePack),),
)


def poner_en_marcha() -> None:
    identidad.poner_en_marcha(EDICION)


def arrancar() -> None:
    poner_en_marcha()
    from karlos_core.main import main
    main()


if __name__ == "__main__":
    arrancar()
