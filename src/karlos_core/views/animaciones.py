"""Animaciones de aparicion para dialogos y ventanas.

Qt no anima desde el stylesheet, asi que lo poco que se mueve se
declara aqui. La regla es la de los productos serios: UNA animacion,
corta y con proposito — la aparicion. Nada parpadea, nada rebota,
nada dura mas de un cuarto de segundo.

    from karlos_core.views.animaciones import aparecer
    class MiDialogo(QDialog):
        def __init__(self):
            ...
            aparecer(self)

`aparecer` deja el dialogo transparente y, en cuanto se muestra, lo
funde a opaco subiendolo 12 px, con curva de frenado (OutCubic). Si
el entorno no dibuja (tests sin pantalla), no molesta: la opacidad
final llega igual porque la animacion termina sola.
"""

from __future__ import annotations

from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QEvent,
                            QObject, QPoint, QPropertyAnimation)

DURACION_MS = 190
SUBIDA_PX = 12


class _Aparicion(QObject):
    """Vigila el primer Show del widget y dispara el fundido."""

    def __init__(self, widget):
        super().__init__(widget)
        self._hecho = False
        widget.installEventFilter(self)

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.Type.Show and not self._hecho:
            self._hecho = True
            self._animar(objeto)
        return False

    def _animar(self, w) -> None:
        # Fundido de opacidad de la ventana...
        fundido = QPropertyAnimation(w, b"windowOpacity", self)
        fundido.setDuration(DURACION_MS)
        fundido.setStartValue(0.0)
        fundido.setEndValue(1.0)
        fundido.setEasingCurve(QEasingCurve.Type.OutCubic)

        # ...y una subida corta, que es lo que lo hace sentirse vivo.
        destino = w.pos()
        subida = QPropertyAnimation(w, b"pos", self)
        subida.setDuration(DURACION_MS)
        subida.setStartValue(destino + QPoint(0, SUBIDA_PX))
        subida.setEndValue(destino)
        subida.setEasingCurve(QEasingCurve.Type.OutCubic)

        fundido.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        subida.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def aparecer(widget) -> None:
    """Preparar un dialogo para aparecer con fundido al mostrarse."""
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.platformName() in ("offscreen", "minimal"):
        return          # sin pantalla no hay nada que fundir
    widget.setWindowOpacity(0.0)
    _Aparicion(widget)
