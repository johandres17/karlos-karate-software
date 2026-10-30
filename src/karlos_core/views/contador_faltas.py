"""Las faltas acumuladas, como los cuadraditos del marcador de la WKF.

Johan lo pidio asi: «un lugar que me permita ver las faltas que va
acumulando de manera visual, similar a como aparece en el video, como
cuadritos». Y tiene sentido mas alla de la costumbre: el grado de una
sancion no se elige, sale del contador del atleta, asi que para anotar
una falta hay que saber por donde va la escalera — y hasta ahora habia
que contarlas a mano en el registro.

Hay un cuadro por peldaño de la escalera del deporte que se anota
(``catalogo.activo().reglamento``, decisión 0004). En karate es la del
reglamento 2026, una sola, de cinco peldaños:

    1ª → CHUI-1     2ª → CHUI-2     3ª → CHUI-3
    4ª → HANSOKU-CHUI               5ª → HANSOKU

Los dos ultimos se pintan distinto porque no son un aviso mas: el
penultimo es la ultima advertencia y el ultimo es la descalificacion.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from karlos_core import catalogo


class ContadorFaltas(QWidget):
    """Dos filas de cuadros, una por atleta, un cuadro por peldaño."""

    LADO = 9          # el cuadro
    HUECO = 3         # entre cuadros
    SEPARACION = 4    # entre las dos filas

    def __init__(self, colors, parent: Optional[QWidget] = None,
                 deporte=None) -> None:
        super().__init__(parent)
        deporte = deporte or catalogo.activo()
        self._c = colors
        self._escalera = deporte.reglamento.escalera_de_faltas
        self._competidores = deporte.competidores
        self.peldaños = len(self._escalera)
        self._aka = 0
        self._ao = 0
        ancho = self.peldaños * self.LADO + (self.peldaños - 1) * self.HUECO
        alto = 2 * self.LADO + self.SEPARACION
        self.setFixedSize(ancho, alto)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._refrescar_tooltip()

    def set_faltas(self, aka: int, ao: int) -> None:
        aka, ao = max(0, int(aka)), max(0, int(ao))
        if (aka, ao) == (self._aka, self._ao):
            return
        self._aka, self._ao = aka, ao
        self._refrescar_tooltip()
        self.update()

    def _refrescar_tooltip(self) -> None:
        def texto(n: int) -> str:
            # Pasado el ultimo peldaño se queda en el ultimo.
            return "sem faltas" if n <= 0 else self._escalera[min(n, self.peldaños) - 1]
        a, b = self._competidores
        self.setToolTip(f"{a.etiqueta}: {texto(self._aka)}   ·   {b.etiqueta}: {texto(self._ao)}")

    def _color(self, indice: int, encendido: bool, competidor) -> QColor:
        if not encendido:
            return QColor(255, 255, 255, 26)
        if indice == self.peldaños - 1:            # descalificado: se acabo
            return QColor("#E5534B")
        if indice == self.peldaños - 2:            # ultima advertencia
            return QColor(self._c.yellow)
        return QColor(getattr(self._c, competidor.color))

    def paintEvent(self, evento) -> None:          # noqa: N802
        """Como en el marcador: AKA se llena hacia dentro, AO hacia fuera.

        En el overlay de la WKF los dos grupos crecen desde el centro,
        donde pone PENALTY. Se copia el gesto para que comparar el
        contador con el video sea mirar dos veces la misma forma, y no
        traducir de una a otra.
        """
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cuentas = (self._aka, self._ao)
        for fila, (competidor, n) in enumerate(zip(self._competidores, cuentas)):
            y = fila * (self.LADO + self.SEPARACION)
            for i in range(self.peldaños):
                # El primero (AKA) crece de derecha a izquierda, como en
                # el marcador.
                col = (self.peldaños - 1 - i) if fila == 0 else i
                x = col * (self.LADO + self.HUECO)
                cuadro = QPainterPath()
                cuadro.addRoundedRect(QRectF(x, y, self.LADO, self.LADO), 2, 2)
                p.fillPath(cuadro, self._color(i, i < n, competidor))
        p.end()
