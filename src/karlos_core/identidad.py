"""Qué edición del programa está en marcha, y quién es (decisión 0006).

Una edición es un programa: Karlos Karate. El núcleo no elige ninguna:
quien arranca (el lanzador del programa o la suite de pruebas) pone una en
marcha, y eso registra su deporte en el catálogo.

Todo lo que da identidad al programa sale de aquí: el nombre y la versión
que se enseñan y se apuntan, el nombre de sus ajustes y la carpeta donde
guarda lo suyo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from karlos_core.catalogo import CATALOGO, Catalogo
from karlos_core.deporte import SportPack

_log = logging.getLogger(__name__)

# La carpeta que usan los módulos mientras nadie pone una edición en marcha.
CARPETA_POR_DEFECTO = Path.home() / ".karlos_karate"


@dataclass(frozen=True)
class Edicion:
    """Un programa.

    ``identificador`` es el de macOS; ``ajustes``, el par (organización,
    aplicación) de QSettings; ``carpeta``, donde guarda lo suyo (el log y
    las pasadas). De ``deportes``, el primero es el de por defecto.
    """

    nombre: str
    version: str
    identificador: str
    ajustes: tuple[str, str]
    carpeta: Path
    deportes: tuple[tuple[str, Callable[[], SportPack]], ...]

    def registrar_en(self, catalogo: Catalogo) -> None:
        for id, fabrica in self.deportes:
            catalogo.registrar(id, fabrica)


_en_marcha: Optional[Edicion] = None


def poner_en_marcha(edicion: Edicion) -> None:
    """Pone la edición en marcha y registra sus deportes en el catálogo.

    Un programa es una sola edición: ponerla otra vez no hace nada, y poner
    otra distinta es un error (sus deportes se mezclarían en el catálogo).
    """
    global _en_marcha
    if _en_marcha is edicion:
        return
    if _en_marcha is not None:
        raise RuntimeError(f"ya está en marcha {_en_marcha.nombre}: un programa es una sola edición")
    edicion.registrar_en(CATALOGO)
    _repartir_carpeta(edicion.carpeta)
    _en_marcha = edicion


def _repartir_carpeta(carpeta: Path) -> None:
    """Todo lo que el programa guarda cuelga de la carpeta de la edición:
    el log y el registro de pasadas (una prueba lo vigila)."""
    from karlos_core.controllers.session_manager import SessionManager
    from karlos_core.utils import app_logging
    app_logging.LOG_DIR = carpeta / "logs"
    app_logging.LOG_FILE = carpeta / "logs" / "karlos.log"
    SessionManager._GLOBAL_ROUNDS_DIR = carpeta
    SessionManager._GLOBAL_ROUNDS_PATH = carpeta / "rounds.json"


def programa() -> str:
    """«Karlos Karate 1.2.0»: la edición que escribe, para que cada
    exportación y cada sesión digan con qué se hicieron (decisión 0008).
    Vive aquí y no en `formato`, que es parte del contrato y no puede
    depender del resto del programa."""
    e = _en_marcha
    return f"{e.nombre} {e.version}" if e is not None else "Karlos"


def en_marcha() -> Edicion:
    """La edición en marcha."""
    if _en_marcha is None:
        raise LookupError("no hay ninguna edición en marcha: el lanzador, la suite o el script "
                          "tiene que poner una (karlos_ediciones)")
    return _en_marcha


def ajustes():
    """Los ajustes (QSettings) de la edición en marcha."""
    from PySide6.QtCore import QSettings
    return QSettings(*en_marcha().ajustes)
