"""Lupa temporal para marcar el inicio y el final de una accion.

La linea de tiempo del combate mete doce mil fotogramas en unos
ochocientos pixeles: una accion de medio segundo ocupa un pixel, asi que
marcarla ahi es imposible. Esta barra muestra solo unos segundos
alrededor del cursor, donde cada fotograma ocupa varios pixeles.

Se arrastra con el raton para recorrer el video, como el scrub de un
editor: se agarra la tira y se empuja, asi que arrastrar a la derecha
trae hacia atras lo que ya paso. Debajo dibuja lo ya anotado del atleta.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from karlos_core.models.technique import AppColors

VENTANA_S = 2.0        # segundos visibles a cada lado del cursor
ALTO = 78          # 60 mas la franja de lo ya anotado
MARGEN_AGARRE = 7      # pixeles de tolerancia para agarrar un tirador
# Lo ya anotado, en carriles justo encima de la regla. Dos acciones que
# se pisan caen en carriles distintos, que es la unica forma de VER un
# solape: en un solo carril se fundirian en una barra continua y no se
# distinguiria de una accion larga.
ALTO_CARRIL = 8
HUECO_CARRIL = 1
CARRILES_MAX = 2
ALTO_FRANJA = CARRILES_MAX * (ALTO_CARRIL + HUECO_CARRIL)
ANCHO_MIN_ETIQUETA = 24   # por debajo de esto la etiqueta no cabe
UMBRAL_ARRASTRE = 3    # pixeles: por debajo de esto fue un clic, no un arrastre
FACTOR_RAPIDO = 5.0    # con Shift, para recorrer mas video


class ZoomBar(QWidget):
    """Tramo ampliado alrededor del cursor, con lo anotado y dos tiradores."""

    inicio_movido = Signal(int)
    fin_movido = Signal(int)
    frame_pedido = Signal(int)

    def __init__(self, colors: AppColors, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._c = colors
        self._anotadas: list[tuple[int, int, str, bool]] = []
        self._frame = 0
        self._total = 1
        self._fps = 30.0
        self._ini: Optional[int] = None
        self._fin: Optional[int] = None
        self._atleta = "AKA"
        self._arrastrando: Optional[str] = None
        self._raton_x: Optional[float] = None
        self._recorrido = 0.0
        self._resto = 0.0
        self.setFixedHeight(ALTO)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)

    # ── datos ────────────────────────────────────────────────────────
    def set_atleta(self, atleta: str) -> None:
        """El atleta que se esta anotando: su color y lo suyo."""
        self._atleta = atleta
        self.update()

    def set_video(self, total: int, fps: float) -> None:
        self._total = max(1, total)
        self._fps = fps if fps > 0 else 30.0
        self.update()

    def set_frame(self, frame: int) -> None:
        if frame != self._frame:
            self._frame = frame
            self.update()

    def set_anotadas(self, tramos) -> None:
        """Lo que ya esta anotado, para verlo mientras se marca.

        Cada tramo es (f_inicio, f_fin, etiqueta, es_parada). Se dibujan
        siempre, tambien despues de guardarse: marcar a ciegas era como
        se duplicaban acciones y como una anotacion acababa dentro de una
        pausa sin que nadie lo viera hasta el analisis.
        """
        self._anotadas = [(int(a), int(b), str(e), bool(p))
                          for a, b, e, p in tramos if int(b) >= int(a)]
        self.update()

    def set_marcas(self, inicio: Optional[int], fin: Optional[int]) -> None:
        self._ini, self._fin = inicio, fin
        self.update()

    # ── geometria ────────────────────────────────────────────────────
    def _rango(self) -> tuple[int, int]:
        media = int(VENTANA_S * self._fps)
        return self._frame - media, self._frame + media

    def _x(self, frame: int) -> float:
        a, b = self._rango()
        return (frame - a) / max(1, b - a) * self.width()

    def _frame_en(self, x: float) -> int:
        a, b = self._rango()
        f = a + (x / max(1, self.width())) * (b - a)
        return max(0, min(self._total - 1, int(round(f))))

    # ── raton ────────────────────────────────────────────────────────
    def _agarre(self, x: float) -> Optional[str]:
        for marca, nombre in ((self._ini, "I"), (self._fin, "O")):
            if marca is not None and abs(x - self._x(marca)) <= MARGEN_AGARRE:
                return nombre
        return None

    def mousePressEvent(self, event) -> None:
        x = event.position().x()
        self._arrastrando = self._agarre(x)
        self._raton_x = x
        self._recorrido = 0.0
        self._resto = 0.0
        if self._arrastrando is None:
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        x = event.position().x()
        if self._raton_x is None:
            self.setCursor(Qt.SizeHorCursor if self._agarre(x) else Qt.OpenHandCursor)
            return
        dx = x - self._raton_x
        self._raton_x = x
        self._recorrido += abs(dx)

        if self._arrastrando is None:
            self._desplazar(dx, event.modifiers() & Qt.ShiftModifier)
            return

        f = self._frame_en(x)
        # el inicio nunca pasa del fin, ni al reves
        if self._arrastrando == "I":
            if self._fin is not None:
                f = min(f, self._fin)
            self.inicio_movido.emit(f)
        else:
            if self._ini is not None:
                f = max(f, self._ini)
            self.fin_movido.emit(f)

    def _desplazar(self, dx: float, rapido: bool) -> None:
        """Mover el video con el raton, como el scrub de un editor.

        Se usa el desplazamiento del raton y no su posicion absoluta: la
        vista se recentra en el fotograma actual, asi que con la posicion
        el arrastre se realimentaria y se disparia solo.

        El resto fraccionario se guarda para que un movimiento lento
        avance igual; a esta escala un pixel es una septima parte de
        fotograma y si no se acumulara no pasaria nada al mover despacio.
        """
        a, b = self._rango()
        por_pixel = (b - a) / max(1, self.width())
        # signo invertido a proposito: se arrastra la pelicula, no el
        # cursor. Empujar a la derecha trae hacia atras lo que ya paso,
        # que es lo que espera la mano al agarrar una tira de video.
        avance = -dx * por_pixel * (FACTOR_RAPIDO if rapido else 1.0) + self._resto
        entero = int(avance)
        self._resto = avance - entero
        if entero:
            destino = max(0, min(self._total - 1, self._frame + entero))
            if destino != self._frame:
                # se adelanta al controlador: si el arrastre dependiera de
                # que vuelva el frame nuevo, se atascaria al minimo retraso
                self._frame = destino
                self.update()
                self.frame_pedido.emit(destino)

    def mouseReleaseEvent(self, event) -> None:
        # Un clic limpio, sin arrastre, sigue sirviendo para saltar a un punto
        if (self._arrastrando is None and self._raton_x is not None
                and self._recorrido < UMBRAL_ARRASTRE):
            self.frame_pedido.emit(self._frame_en(event.position().x()))
        self._arrastrando = None
        self._raton_x = None
        self._resto = 0.0
        self.setCursor(Qt.OpenHandCursor)

    # ── pintado ──────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: ARG002
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self._c
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(c.panel))

        a, b = self._rango()
        color = QColor(c.aka if self._atleta == "AKA" else c.ao)

        # tramo marcado, detras de todo
        if self._ini is not None and self._fin is not None:
            x0, x1 = self._x(self._ini), self._x(self._fin)
            relleno = QColor(color)
            relleno.setAlpha(46)
            p.fillRect(QRectF(x0, 0, max(1.0, x1 - x0),
                              self._base_franja()), relleno)

        self._pintar_anotadas(p, a, b, color)
        self._pintar_regla(p, a, b)

        # tiradores de inicio y fin
        for marca, etiqueta in ((self._ini, "I"), (self._fin, "O")):
            if marca is None or not (a <= marca <= b):
                continue
            x = self._x(marca)
            p.setPen(QPen(color, 2))
            p.drawLine(int(x), 0, int(x), h - 16)
            p.setBrush(QBrush(color))
            p.setPen(Qt.NoPen)
            p.drawRect(QRectF(x - 7, 0, 14, 14))
            p.setPen(QPen(QColor("#ffffff")))
            p.drawText(QRectF(x - 7, 0, 14, 14), Qt.AlignCenter, etiqueta)

        # cursor
        x = self._x(self._frame)
        p.setPen(QPen(QColor(c.text), 1, Qt.DashLine))
        p.drawLine(int(x), 0, int(x), h - 16)
        p.end()

    def _base_franja(self) -> int:
        """Donde empieza la franja de lo anotado, encima de la regla."""
        return self.height() - 16 - ALTO_FRANJA

    def _carriles(self, visibles) -> list[int]:
        """A que fila va cada tramo: la primera donde no se pise con otro.

        Es la asignacion de un diagrama de Gantt, y aqui hace el trabajo
        de fondo: si dos acciones acaban en filas distintas es porque se
        solapan, y eso se ve de un vistazo.
        """
        fin_de_carril: list[int] = []
        salida = []
        for f0, f1, _e, _p in visibles:
            for i, fin in enumerate(fin_de_carril):
                if f0 > fin:
                    fin_de_carril[i] = f1
                    salida.append(i)
                    break
            else:
                fin_de_carril.append(f1)
                salida.append(len(fin_de_carril) - 1)
        return salida

    def _pintar_anotadas(self, p: QPainter, a: int, b: int,
                         color: QColor) -> None:
        if not self._anotadas:
            return
        c = self._c
        dentro = [t for t in self._anotadas if t[1] >= a and t[0] <= b]
        arriba = self._base_franja()

        # Las paradas van de fondo y no como un carril mas. Duran
        # decenas de segundos: puestas en la fila se comian un carril
        # entero y empujaban fuera de la franja las acciones de al lado,
        # que es justo lo que se viene a mirar. De fondo dicen lo suyo,
        # que ahi el combate estaba parado, sin quitar sitio a nadie.
        for f0, f1, _e, parada in dentro:
            if not parada:
                continue
            x0, x1 = self._x(f0), self._x(f1)
            fondo = QColor(c.muted)
            fondo.setAlpha(64)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(fondo))
            p.drawRect(QRectF(x0, arriba, max(2.0, x1 - x0), ALTO_FRANJA))

        visibles = sorted((t for t in dentro if not t[3]), key=lambda x: x[0])
        if not visibles:
            return
        fuente = p.font()
        tam = fuente.pointSize()
        for (f0, f1, etiqueta, parada), carril in zip(visibles,
                                                      self._carriles(visibles)):
            if carril >= CARRILES_MAX:
                continue
            x0, x1 = self._x(f0), self._x(f1)
            ancho = max(2.0, x1 - x0)
            y = arriba + carril * (ALTO_CARRIL + HUECO_CARRIL)
            # Borde del color del fondo: dos barras pegadas, una encima
            # de otra o una detras de otra, se leian como una sola.
            p.setPen(QPen(QColor(c.panel), 1))
            p.setBrush(QBrush(QColor(color)))
            p.drawRect(QRectF(x0, y, ancho, ALTO_CARRIL))
            if ancho >= ANCHO_MIN_ETIQUETA and etiqueta:
                fuente.setPointSize(6)
                p.setFont(fuente)
                p.setPen(QPen(QColor("#ffffff")))
                p.drawText(QRectF(x0, y - 1, ancho, ALTO_CARRIL + 2),
                           Qt.AlignCenter, etiqueta)
        fuente.setPointSize(tam)
        p.setFont(fuente)

    def _pintar_regla(self, p: QPainter, a: int, b: int) -> None:
        """Marcas cada medio segundo, para no perder la escala."""
        c = self._c
        base = self.height() - 16
        p.setPen(QPen(QColor(c.border), 1))
        p.drawLine(0, base, self.width(), base)
        paso = max(1, int(self._fps / 2))
        p.setPen(QPen(QColor(c.muted), 1))
        for f in range((a // paso) * paso, b + 1, paso):
            if f < 0:
                continue
            x = self._x(f)
            p.drawLine(int(x), base, int(x), base + 4)
            if f % max(1, int(self._fps)) == 0:
                p.drawText(QRectF(x - 24, base + 3, 48, 13), Qt.AlignCenter,
                           f"{f / self._fps:.0f}s")
