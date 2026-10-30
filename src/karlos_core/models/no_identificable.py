"""«Não identificável»: por qué una acción no se deja identificar.

Los motivos son del programa y no del deporte: hablan del vídeo y de quien
mira, no del reglamento (decisión 0004). Los usan el árbol de preguntas y
la ventana de edición, con la misma lista y los mismos códigos, para que el
dato salga igual por los dos caminos.
"""

from __future__ import annotations

from karlos_core.utils.i18n import I18n


def _t(clave: str) -> str:
    return I18n().t(clave)


# Por que una accion no se deja identificar. Los cuatro primeros son los
# que Johan encontro anotando de verdad; el corte de plano se anade
# porque la realizacion de la WKF mete repeticiones a media accion, que
# es el mismo problema visto desde la mesa de mezclas.
#
# El motivo importa tanto como el hecho: si casi todo lo no identificable
# es el arbitro interponiendose, eso se corrige con otra camara; si es el
# encuadre, con otro plano. Sin el motivo solo queda un agujero.
MOTIVOS = [
    (_t("tree.m_arbitro"), "Mot:Referee"),
    (_t("tree.m_fuera"), "Mot:OutOfFrame"),
    (_t("tree.m_tapado"), "Mot:Occluded"),
    (_t("tree.m_corte"), "Mot:CameraCut"),
    (_t("tree.m_rapido"), "Mot:TooFast"),
    # El archivo, no la realizacion. Es otro motivo distinto del corte
    # de plano porque el remedio tambien es otro: un corte de camara no
    # tiene arreglo, un archivo roto se vuelve a descargar. Ya paso en
    # el estudio, con el video del ID27.
    (_t("tree.m_video"), "Mot:VideoFault"),
    (_t("tree.m_otro"), "Mot:Other"),
]


def motivos_no_identificable() -> list[tuple[str, str]]:
    """Los motivos de «Não identificável», para quien no pase por el arbol:
    la misma lista y los mismos codigos, para que el dato salga igual por
    los dos caminos."""
    return [(etiqueta, clave[4:]) for etiqueta, clave in MOTIVOS]
