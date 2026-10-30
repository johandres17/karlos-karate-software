"""Karlos: el núcleo común (decisión 0006).

Lo que no depende del deporte: vídeo y paso de fotograma, tabla y sesiones,
faltas, hub, tema e idioma. El deporte entra por el contrato de
``karlos_core.deporte`` y se pide al catálogo (``karlos_core.catalogo``).

Single source of truth for the app version: bump __version__ here and
rebuild — the spec, the DMG name and the UI all read it from this file.
"""

__version__ = "6.14.14"
__author__ = "Johan Robalino"

# El núcleo no registra deportes: los pone la edición que arranca
# (karlos_ediciones, decisión 0006).
