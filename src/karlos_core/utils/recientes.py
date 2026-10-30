"""Las carpetas de vídeos abiertas hace poco, y cuál se abre al arrancar.

Las apunta el hub cada vez que carga una carpeta, en los ajustes de la
edición. Al arrancar, el programa abre la más reciente que sigue ahí y
tiene vídeos; la pantalla de inicio la anuncia con esta misma función,
para que lo que dice sea lo que pasa.
"""
from __future__ import annotations

import os
from typing import Optional

CLAVE = "project_hub/recent_folders"
EXTENSIONES_DE_VIDEO = (".mp4", ".avi", ".mov", ".mkv")


def recientes(ajustes) -> list[str]:
    """Las carpetas apuntadas, de la más reciente a la más vieja.

    QSettings devuelve un texto suelto, y no una lista, cuando en un
    fichero INI solo hay una: recorrerlo letra a letra buscaría carpetas
    llamadas «/», «U», «s»…
    """
    valor = ajustes.value(CLAVE, []) or []
    if isinstance(valor, str):
        valor = [valor]
    return [str(c) for c in valor if c]


def carpeta_de_arranque(ajustes) -> Optional[str]:
    """La carpeta que se abre al arrancar, o None si no queda ninguna."""
    for carpeta in recientes(ajustes):
        if os.path.isdir(carpeta) and _tiene_videos(carpeta):
            return carpeta
    return None


def _tiene_videos(carpeta: str) -> bool:
    try:
        nombres = os.listdir(carpeta)
    except OSError:
        return False
    return any(n.lower().endswith(EXTENSIONES_DE_VIDEO)
               and os.path.isfile(os.path.join(carpeta, n)) for n in nombres)
