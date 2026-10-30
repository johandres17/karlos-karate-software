"""Timeline overlay widget for KARLOS ANNOTATOR.

Renders a compact dual-track visual timeline of annotation segments
overlaid on the video slider area. Color-coded by athlete:
AKA (red, upper half) and AO (blue, lower half).
Supports hover tooltips and click-to-seek.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from karlos_core.views.theme import Palette

_p = Palette()

# ── Fight marker colors ──
_FIGHT_START_COLOR = QColor(_p.success_alt)  # green
_FIGHT_END_COLOR = QColor(_p.aka_dark)    # red


# Las fases marcadas del tiempo-movimiento: tenues bajo las acciones, y
# fuertes y con non-fighting en la pasada de fases, donde son lo que se mira.
# Los asaltos: la raya de donde empieza y acaba cada uno, con su número.
_ASALTO_COLOR = QColor(255, 255, 255, 90)
_ASALTO_TEXTO = QColor(255, 255, 255, 170)
_FASE_BANDA = {"fighting": QColor(245, 135, 50, 46), "stoppage": QColor(56, 102, 194, 52)}
_FASE_FUERTE = {"fighting": QColor(245, 135, 50, 130), "non_fighting": QColor(121, 131, 148, 60),
                "stoppage": QColor(56, 102, 194, 130)}
_FALTA_COLOR = QColor(229, 83, 75, 240)           # sancion
_FALTA_BORDE = QColor(255, 255, 255, 160)
_CURSOR_COLOR = QColor(255, 255, 255, 230)        # donde va el video
_CURSOR_SOMBRA = QColor(0, 0, 0, 120)


class TimelineOverlay(QWidget):
    """Painted overlay showing annotation segments on the video timeline.

    Uses a dual-track layout: the upper half of the widget is reserved
    for AKA (red) annotations, the lower half for AO (blue). Both
    tracks are painted independently from the same record list, so
    all annotations from both athletes are always visible.

    Signals:
        seek_requested(frame_idx): Emitted when user clicks a segment
            to seek to that frame.
    """

    seek_requested = Signal(int)

    # Athlete track colors
    _color_a = QColor(_p.timeline_aka)
    _color_b = QColor(_p.ao_dark)
    AKA_COLOR = property(lambda self: self._color_a)
    AO_COLOR = property(lambda self: self._color_b)
    PADDING_H = 4

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._records: list = []
        self._total_frames: int = 1
        self._fight_start: Optional[int] = None
        self._fight_end: Optional[int] = None
        self._solo_atleta: Optional[str] = None
        self._posicion: int = 0
        self._arrastrando: bool = False
        self.setMouseTracking(True)
        self.setFixedHeight(20)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_corner_colors(self, color_a: str, color_b: str) -> None:
        """Update timeline dot colors from bout_info corner selection."""
        self._color_a = QColor(color_a)
        self._color_b = QColor(color_b)
        self.update()

    def set_data(self, records: list, total_frames: int) -> None:
        """Update the overlay with current annotations and video length.

        Args:
            records: List of Annotation instances.
            total_frames: Total frame count of the loaded video.
        """
        self._records = list(records) if records else []
        self._total_frames = max(total_frames, 1)
        self.update()

    def set_position(self, frame: int) -> None:
        """Donde esta el video ahora mismo."""
        if frame != self._posicion:
            self._posicion = frame
            self.update()

    def set_asaltos(self, asaltos: list) -> None:
        """Los asaltos marcados: (n, inicio, fin). Se pintan con su número
        para que se vea dónde empieza y acaba cada uno (Johan, 9-10-2026)."""
        self._asaltos = list(asaltos or [])
        self.update()

    def _pintar_asaltos(self, painter, usable_width: int, h: int) -> None:
        asaltos = getattr(self, "_asaltos", None)
        if not asaltos:
            return
        from PySide6.QtGui import QFont
        fuente = QFont(); fuente.setPixelSize(9); fuente.setBold(True)
        for n, ini, fin in asaltos:
            xa = self.PADDING_H + int((ini / self._total_frames) * usable_width)
            painter.setPen(QPen(_ASALTO_COLOR, 1, Qt.PenStyle.DashLine))
            painter.drawLine(xa, 0, xa, h)
            painter.setFont(fuente)
            painter.setPen(QPen(_ASALTO_TEXTO, 1))
            painter.drawText(xa + 3, 10, f"R{n}")
            if fin is None:
                continue
            xb = self.PADDING_H + int(((fin + 1) / self._total_frames) * usable_width)
            painter.setPen(QPen(_ASALTO_COLOR, 1, Qt.PenStyle.DashLine))
            painter.drawLine(xb, 0, xb, h)

    def set_fases(self, fases: list, fuerte: bool = False) -> None:
        """Las fases marcadas del tiempo-movimiento: (inicio, fin, estado).
        Tenues bajo las acciones; fuertes, y con non-fighting en gris, en la
        pasada de fases, donde la estructura del combate es lo que se mira."""
        self._fases = list(fases or [])
        self._fases_fuertes = bool(fuerte)
        self.update()

    def _pintar_fases(self, painter, usable_width: int, h: int) -> None:
        fases = getattr(self, "_fases", None)
        if not fases:
            return
        paleta = _FASE_FUERTE if getattr(self, "_fases_fuertes", False) else _FASE_BANDA
        painter.setPen(Qt.PenStyle.NoPen)
        for ini, fin, estado in fases:
            color = paleta.get(estado)
            if color is None:
                continue
            xa = self.PADDING_H + int((ini / self._total_frames) * usable_width)
            xb = self.PADDING_H + int(((fin + 1) / self._total_frames) * usable_width)
            painter.setBrush(color)
            painter.drawRect(xa, 0, max(1, xb - xa), h)

    def set_solo_atleta(self, atleta: Optional[str]) -> None:
        """Mostrar solo lo de un atleta, o todo si es None.

        La anotacion guiada es primero AKA y despues AO: ver las marcas de
        los dos a la vez obliga a distinguir cual toca en cada una, que es
        justo el trabajo que la pasada por atleta evita.
        """
        self._solo_atleta = atleta
        self.update()

    def set_fight_markers(self, fight_start: Optional[int], fight_end: Optional[int]) -> None:
        """Set fight segment markers to draw vertical lines on the timeline.

        Args:
            fight_start: Start frame of the fight segment (green line).
            fight_end: End frame of the fight segment (red line).
        """
        self._fight_start = fight_start
        self._fight_end = fight_end
        self.update()

    # ------------------------------------------------------------------
    # Paint — Dual Track System
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        """Paint dual-track annotation segments.

        Upper half: AKA (red, p.timeline_aka).
        Lower half: AO  (blue, p.ao_dark).
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        h = self.height()
        if h < 4:
            painter.end()
            event.accept()
            return

        usable_width = self.width() - self.PADDING_H * 2
        if usable_width <= 0:
            painter.end()
            event.accept()
            return

        # ── Las fases del tiempo-movimiento, de fondo, debajo de todo ──
        self._pintar_fases(painter, usable_width, h)
        # ── Los asaltos, con su número: donde empieza y acaba cada uno ──
        self._pintar_asaltos(painter, usable_width, h)

        # ── Fight markers (vertical lines) — drawn first (behind annotations) ──
        if self._fight_start is not None:
            x = self.PADDING_H + int((self._fight_start / self._total_frames) * usable_width)
            painter.setPen(QPen(_FIGHT_START_COLOR, 2))
            painter.drawLine(x, 0, x, h)

        if self._fight_end is not None:
            x = self.PADDING_H + int((self._fight_end / self._total_frames) * usable_width)
            painter.setPen(QPen(_FIGHT_END_COLOR, 2))
            painter.drawLine(x, 0, x, h)

        # ── Annotation segments ────────────────────────────────────────
        if not self._records:
            # Sin anotaciones tambien hay que pintar: el cursor es lo que
            # dice por donde va el video, y en un pase nuevo no hay nada
            # anotado todavia.
            self._pintar_faltas(painter, usable_width, h)
            self._pintar_cursor(painter, usable_width, h)
            painter.end()
            event.accept()
            return

        # Split height with a small gap between tracks
        mid = h // 2
        gap = 2
        track_height = mid - (gap // 2)

        # No outline for clean, sharp rectangles
        no_pen = QPen(Qt.PenStyle.NoPen)

        for record in self._records:
            # Validate required fields
            f_start = getattr(record, "f_start", None)
            f_end = getattr(record, "f_end", None)
            athlete = getattr(record, "athlete", "")
            if getattr(record, "category", "") == "PHASE":
                continue      # las fases van de fondo, en bandas (set_fases)
            if self._solo_atleta is not None and athlete != self._solo_atleta:
                continue
            if f_start is None or f_end is None:
                continue
            if f_end <= f_start:
                continue

            # Determine track position and color
            if athlete == "AKA":
                brush = QBrush(self.AKA_COLOR)
                y = 0
            elif athlete == "AO":
                brush = QBrush(self.AO_COLOR)
                y = mid
            else:
                continue  # skip records with unknown athlete

            painter.setPen(no_pen)
            painter.setBrush(brush)

            x_start = self.PADDING_H + int((f_start / self._total_frames) * usable_width)
            x_end = self.PADDING_H + int((f_end / self._total_frames) * usable_width)
            seg_width = max(x_end - x_start, 2)

            painter.drawRect(x_start, y, seg_width, track_height)

        # ── Draw annotation dots (small circles at f_start positions) ─
        dot_radius = 3
        for record in self._records:
            f_start = getattr(record, "f_start", None)
            athlete = getattr(record, "athlete", "")
            if f_start is None:
                continue
            px = self.PADDING_H + int((f_start / self._total_frames) * usable_width)
            cy = h // 2
            dot_color = self.AKA_COLOR if athlete == "AKA" else self.AO_COLOR
            painter.setBrush(QBrush(dot_color))
            painter.setPen(no_pen)
            painter.drawEllipse(int(px - dot_radius), int(cy - dot_radius), dot_radius * 2, dot_radius * 2)

        self._pintar_faltas(painter, usable_width, h)
        self._pintar_cursor(painter, usable_width, h)
        painter.end()
        event.accept()

    def _pintar_faltas(self, painter, usable_width: int, h: int) -> None:
        """Marcar las sanciones como etiqueta, no como tramo.

        Una falta no dura: es un instante. Pintada como los demas tramos
        salia de un pixel de ancho y no se veia — el dibujo de tramos la
        descarta ademas por tener el mismo inicio que final. Aqui va como
        banderin, que es lo que es: una marca en el minuto.
        """
        if not self._records or self._total_frames <= 0:
            return
        for r in self._records:
            if getattr(r, "category", "") != "PENALTY":
                continue
            atleta = getattr(r, "athlete", "")
            if self._solo_atleta is not None and atleta != self._solo_atleta:
                continue
            f = getattr(r, "f_start", None)
            if f is None:
                continue
            x = self.PADDING_H + int((f / self._total_frames) * usable_width)
            painter.setPen(QPen(_FALTA_COLOR, 2))
            painter.drawLine(x, 0, x, h)
            # banderin arriba, del lado del atleta que la comete
            hacia = 1 if atleta != "AO" else -1
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_FALTA_COLOR)
            base = 0 if atleta != "AO" else h
            from PySide6.QtGui import QPolygon
            from PySide6.QtCore import QPoint
            painter.drawPolygon(QPolygon([
                QPoint(x, base),
                QPoint(x + 7 * hacia, base + 3 * hacia),
                QPoint(x, base + 7 * hacia),
            ]))
            painter.setPen(QPen(_FALTA_BORDE, 1))
            painter.drawLine(x, base, x, base + 7 * hacia)

    def _pintar_cursor(self, painter, usable_width: int, h: int) -> None:
        """Marcar donde va el video, con un tirador para arrastrarlo.

        Antes esto lo hacia un deslizador aparte. Tenerlo aqui ahorra esa
        fila y ademas pone la posicion sobre las marcas, que es donde hay
        que leerla.
        """
        if self._total_frames <= 0:
            return
        x = self.PADDING_H + int((self._posicion / self._total_frames) * usable_width)
        painter.setPen(QPen(_CURSOR_SOMBRA, 3))
        painter.drawLine(x, 0, x, h)
        painter.setPen(QPen(_CURSOR_COLOR, 1))
        painter.drawLine(x, 0, x, h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_CURSOR_COLOR)
        painter.drawEllipse(x - 4, h // 2 - 4, 8, 8)

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Arrastrar mueve el video; sin arrastrar, informa de la marca."""
        if self._arrastrando:
            self.seek_requested.emit(self._frame_at_x(event.position().x()))
            return
        if not self._records:
            QToolTip.hideText()
            return

        x = event.position().x()
        y = event.position().y()
        frame = self._frame_at_x(x)
        athlete = self._athlete_at_y(y)
        record = self._record_at_frame_and_track(frame, athlete)
        if record:
            tooltip = (
                f"{record.technique} [{record.athlete}]\n"
                f"Score: {record.score} | "
                f"Frames: {record.f_start}–{record.f_end} | "
                f"Duration: {record.duration_s:.1f}s"
            )
            QToolTip.showText(event.globalPos(), tooltip, self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Ir al punto pulsado, o al inicio de la marca si se pulsa una."""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        x = event.position().x()
        frame = self._frame_at_x(x)
        self._arrastrando = True
        if self._records:
            record = self._record_at_frame_and_track(
                frame, self._athlete_at_y(event.position().y()))
            if record:
                self.seek_requested.emit(record.f_start)
                return
        self.seek_requested.emit(frame)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: ARG002
        self._arrastrando = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _frame_at_x(self, x: int) -> int:
        """Convert pixel x coordinate to approximate frame index."""
        usable_width = self.width() - self.PADDING_H * 2
        if usable_width <= 0:
            return 0
        ratio = max(0.0, min(1.0, (x - self.PADDING_H) / usable_width))
        return int(ratio * self._total_frames)

    def _athlete_at_y(self, y: float) -> str:
        """Determine which dual track a Y coordinate falls on.

        Upper half → AKA, lower half → AO.
        """
        return "AKA" if y < self.height() / 2 else "AO"

    def _record_at_frame_and_track(self, frame: int, athlete: str):
        """Find the annotation that spans the given frame AND matches the athlete track.

        Filters both by time range (X axis) and athlete (Y axis / track)
        so hover and click events on the lower track only match AO records,
        and events on the upper track only match AKA records.
        """
        for record in self._records:
            if record.athlete != athlete:
                continue
            if record.f_start <= frame <= record.f_end:
                return record
        return None
