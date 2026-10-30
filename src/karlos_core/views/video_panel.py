"""Video panel view for KARLOS ANNOTATOR.

Displays the video playback area with frame counter, timeline slider,
playback controls, speed selector, annotation/fight marker buttons,
and a live scoring stats strip. Emits signals for user actions; all
video logic is handled by VideoManager.
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from karlos_core import catalogo
from karlos_core.formato import COMPETIDORES
from karlos_core.models.technique import AppColors, VideoConfig
from karlos_core.views.timeline_overlay import TimelineOverlay
from karlos_core.views.zoom_bar import ZoomBar
from karlos_core.views.theme import Palette

_HUD_AKA_COLOR = (60, 60, 231)
_HUD_AO_COLOR = (219, 152, 52)
_HUD_TEXT_COLOR = (255, 255, 255)
_HUD_BG = (0, 0, 0)


class VideoPanelView(QWidget):
    """Video playback panel with transport controls and markers."""

    play_toggled = Signal()
    speed_changed = Signal(float)
    volume_changed = Signal(float)  # 0.0 – 1.0
    mute_toggled = Signal(bool)
    slider_moved = Signal(int)
    step_requested = Signal(int)
    mark_start_requested = Signal()
    mark_end_requested = Signal()
    fight_start_requested = Signal()
    fight_end_requested = Signal()
    wheel_scrolled = Signal(int, bool, bool)

    def __init__(
        self, colors: AppColors, video_config: VideoConfig,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        from karlos_core.utils.i18n import I18n
        self._i18n = I18n()
        self._colors = colors
        self._modo_pro = False
        self._video_config = video_config
        self._hud_recording: bool = False
        self._hud_athlete: str = ""
        self._hud_start_frame: int = 0
        self._muted: bool = False
        self._build()

    def _build(self) -> None:
        c = self._colors
        p = Palette.from_config(c)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(2)

        # Video display container
        self._video_container = QFrame()
        self._video_container.setObjectName("videoContainer")
        self._video_container.setStyleSheet(
            f"#videoContainer{{border:1px solid {p.border_default};border-radius:8px;background:#000;}}"
        )
        vc_layout = QVBoxLayout(self._video_container)
        vc_layout.setContentsMargins(0, 0, 0, 0)
        self.display = QLabel(self._i18n.t("video.open_prompt"))
        self.display.setAlignment(Qt.AlignCenter)
        # 480x270 y no 640x360: con la lupa, un minimo de 360 dejaba el
        # registro en una sola fila a 900 px de alto. El video sigue
        # creciendo hasta llenar lo que haya.
        self.display.setMinimumSize(480, 270)
        self.display.setSizePolicy(
            QWidget().sizePolicy().Policy.Expanding,
            QWidget().sizePolicy().Policy.Expanding,
        )
        self.display.setStyleSheet(
            f"background:transparent;color:{c.muted};font-size:14px;font-weight:400;border:none;"
        )
        vc_layout.addWidget(self.display)

        self.display.installEventFilter(self)
        lay.addWidget(self._video_container, stretch=1)

        # ---- Franja de estado: cronometro, asalto y recuento ----
        # Iban en tres filas apiladas y un deslizador aparte, unos 110 px
        # que le quitaban altura al video para decir cuatro numeros. En una
        # sola franja se lee igual de bien y el video crece.
        self._fight_timer = QLabel("00:00")
        self._fight_timer.setStyleSheet(
            f"color:{c.text};font-size:17px;font-weight:700;"
            "background:transparent;border:none;")

        self._round_label = QLabel("")
        self._round_label.setStyleSheet(
            f"color:{c.accent};font-size:11px;font-weight:600;"
            "background:transparent;border:none;")

        from karlos_core.views.contador_faltas import ContadorFaltas
        # Junto al marcador porque es el mismo dato: como va la luta.
        # En el video los cuadraditos estan debajo del tanteo; aqui al
        # lado, que es donde queda sitio en una franja de una fila.
        self.contador_faltas = ContadorFaltas(c)
        self.contador_faltas.setVisible(False)

        a, b = (catalogo.etiqueta(c) for c in COMPETIDORES)
        self._live_stats = QLabel(self._i18n.t(
            "video.live_stats", a=a, b=b, aka="0", ao="0", total="0", elapsed="0"))
        self._live_stats.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._live_stats.setStyleSheet(
            f"color:{p.text_disabled};font-size:11px;font-weight:500;"
            "background:transparent;border:none;")

        # El cronometro, el asalto y el recuento: en tres filas antes de
        # abrir un combate, y en la fila de controles con la anotacion
        # guiada, para darle el alto al video.
        self._pila_clasica = QWidget()
        pila = QVBoxLayout(self._pila_clasica)
        pila.setContentsMargins(0, 0, 0, 0)
        pila.setSpacing(2)
        lay.addWidget(self._pila_clasica)

        self._franja = QWidget()
        self._franja.setFixedHeight(30)
        self._franja.setStyleSheet(
            f"background:{p.surface_2};border:1px solid {p.border_default};"
            "border-radius:5px;")
        fl = QHBoxLayout(self._franja)
        fl.setContentsMargins(10, 0, 10, 0)
        fl.setSpacing(10)
        fl.addWidget(self._fight_timer)
        fl.addWidget(self._round_label)
        fl.addStretch(1)
        fl.addWidget(self._live_stats)
        lay.addWidget(self._franja)

        # El deslizador duplicaba a la linea de tiempo, que ademas muestra
        # las marcas. Se conserva por compatibilidad pero no ocupa sitio.
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(lambda v: self.slider_moved.emit(v))
        lay.addWidget(self.slider)

        self.timeline = TimelineOverlay()
        # 22 px: con 10 px las marcas de accion eran invisibles
        self.timeline.setFixedHeight(22)
        self.timeline.seek_requested.connect(lambda frame: self.slider_moved.emit(frame))
        lay.addWidget(self.timeline)

        # Lupa temporal: la linea de tiempo del combate no da para marcar
        # medio segundo, asi que debajo va el mismo tramo ampliado. Se ve
        # cuando hay un video abierto.
        self.zoom_bar = ZoomBar(self._colors)
        self.zoom_bar.hide()
        lay.addWidget(self.zoom_bar)

        # Controls row
        ctrl = QHBoxLayout()
        self._ctrl = ctrl
        ctrl.setContentsMargins(2, 0, 2, 0)
        ctrl.setSpacing(6)

        self.lbl_info = QLabel("Frame: 0 / 0 | 0.000s | -- FPS")
        self.lbl_info.setStyleSheet(f"color:{c.muted};font-size:10px;font-weight:400;background:transparent;border:none;")
        ctrl.addWidget(self.lbl_info)
        ctrl.addStretch(1)

        # Sin botones de fotograma. Eran cuatro — «<<», «<», «>», «>>» —
        # y hacian exactamente lo mismo que [←] [→] y [Shift+←] [Shift+→],
        # que es como se navega de verdad: con la mano ya en el teclado
        # entre una anotacion y la siguiente. La senal step_requested
        # sigue, que es la que usan esas teclas y la rueda del raton.
        self.btn_play = self._flat_btn(self._i18n.t("video.play_pause"), c.green, self.play_toggled.emit, 11)
        ctrl.addWidget(self.btn_play)

        self.cmb_speed = QComboBox()
        self.cmb_speed.addItems(self._video_config.speed_labels)
        self.cmb_speed.setCurrentIndex(self._video_config.default_speed_index)
        self.cmb_speed.setFixedWidth(55)
        self.cmb_speed.setStyleSheet(
            f"QComboBox{{background:{c.panel};color:{c.text};border:1px solid rgba(255,255,255,0.08);border-radius:4px;padding:2px 4px;font-size:10px;}}"
            f"QComboBox:hover{{border:1px solid {c.ao}88;}}"
        )
        self.cmb_speed.currentIndexChanged.connect(self._on_speed_change)
        ctrl.addWidget(self.cmb_speed)
        ctrl.addSpacing(8)

        # ---- Audio: mute button + volume slider ----
        self.btn_mute = self._flat_btn("🔊", c.muted, self._on_mute_clicked, 12)
        self.btn_mute.setFixedWidth(32)
        self.btn_mute.setToolTip(self._i18n.t("video.mute"))
        ctrl.addWidget(self.btn_mute)

        self.sld_volume = QSlider(Qt.Horizontal)
        self.sld_volume.setRange(0, 100)
        self.sld_volume.setValue(80)
        self.sld_volume.setFixedWidth(72)
        self.sld_volume.setToolTip(self._i18n.t("video.volume"))
        self.sld_volume.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:rgba(255,255,255,0.08);border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:10px;height:10px;margin:-3px 0;background:{c.green};border-radius:5px;}}"
            f"QSlider::sub-page:horizontal{{background:{c.green}66;border-radius:2px;}}"
        )
        self.sld_volume.valueChanged.connect(self._on_volume_change)
        ctrl.addWidget(self.sld_volume)
        ctrl.addSpacing(12)

        self.btn_fight_start = self._outline_btn(self._i18n.t("video.fight_start"), p.success, lambda: self.fight_start_requested.emit())
        self.btn_fight_end = self._outline_btn(self._i18n.t("video.fight_end"), p.aka, lambda: self.fight_end_requested.emit())
        ctrl.addWidget(self.btn_fight_start)
        ctrl.addWidget(self.btn_fight_end)

        self.lbl_fight = QLabel("F: --")
        self.lbl_fight.setStyleSheet(f"color:{c.accent};font-size:10px;font-weight:500;background:transparent;border:none;")
        ctrl.addWidget(self.lbl_fight)
        ctrl.addSpacing(12)

        self.btn_mark_start = self._mark_btn_compact(self._i18n.t("video.mark_start"), c.aka, lambda: self.mark_start_requested.emit())
        self.btn_mark_end = self._mark_btn_compact(self._i18n.t("video.mark_end"), c.ao, lambda: self.mark_end_requested.emit())
        ctrl.addWidget(self.btn_mark_start)
        ctrl.addWidget(self.btn_mark_end)

        self.lbl_marks = QLabel("--")
        self.lbl_marks.setStyleSheet(f"color:{c.yellow};font-size:10px;font-weight:500;background:transparent;border:none;")
        ctrl.addWidget(self.lbl_marks)

        self.lbl_pass = QLabel("")
        self.lbl_pass.setStyleSheet(f"color:{c.accent};font-size:10px;font-weight:500;background:transparent;border:none;")
        ctrl.addWidget(self.lbl_pass)
        ctrl.addStretch(1)
        lay.addLayout(ctrl)

    # Que tecla anuncia cada boton en cada modo. Se reescribe el rotulo en
    # vez de duplicar las traducciones: el texto sale del idioma elegido y
    # solo cambia la tecla entre corchetes.
    #
    # [I] y [O] marcan entrada y salida, como en todos los programas de
    # video: si alguna vez has tocado un montador, ya te las sabes.
    _TECLAS = {
        "btn_mark_start":  ("I", "I"),
        "btn_mark_end":    ("O", "O"),
        "btn_fight_start": ("F", "F"),
        "btn_fight_end":   ("G", "G"),
    }

    def _rotular_teclas(self, pro: bool) -> None:
        """Poner en cada boton la tecla que de verdad lo dispara."""
        import re
        for nombre, (clasico, asistido) in self._TECLAS.items():
            btn = getattr(self, nombre, None)
            if btn is None:
                continue
            base = re.sub(r"\s*\[[^\]]*\]\s*$", "", btn.text()).strip()
            btn.setText(f"{base} [{asistido if pro else clasico}]")

    def aplicar_modo(self, pro: bool) -> None:
        """Colocar los controles: con la anotacion guiada, el cronometro, el
        asalto y el recuento van en la fila de controles y el deslizador se
        esconde, porque la linea de tiempo ya busca y ademas muestra las
        marcas."""
        self._modo_pro = pro
        self.update_play_button(False)
        self._rotular_teclas(pro)
        # La franja de 30 px ya no se usa: sus tres datos caben en la fila
        # de controles, y sus treinta pixeles se los queda el video.
        self._franja.setVisible(False)
        self._pila_clasica.setVisible(not pro)
        self.slider.setVisible(not pro)
        # La lupa la muestra u oculta el controlador segun haya video.
        for w, estilo in (
            (self._fight_timer, self._estilo_reloj(pro)),
            (self._round_label, self._estilo_asalto(pro)),
            (self._live_stats, self._estilo_recuento(pro)),
        ):
            w.setStyleSheet(estilo)
            w.setAlignment(Qt.AlignRight | Qt.AlignVCenter if pro and w is self._live_stats
                           else (Qt.AlignLeft | Qt.AlignVCenter if pro else Qt.AlignCenter))
        for w in (self._fight_timer, self._round_label, self._live_stats):
            if w.parent() is not None:
                w.setParent(None)
        if pro:
            for w in (self._fight_timer, self._round_label, self._live_stats):
                self._ctrl.addWidget(w)
        else:
            pl = self._pila_clasica.layout()
            for w in (self._fight_timer, self._round_label, self._live_stats):
                pl.addWidget(w)
        # Los cuadros de faltas, al final de la fila de controles: una fila
        # propia le quitaba al registro el alto que no tiene.
        self._ctrl.removeWidget(self.contador_faltas)
        self._ctrl.addWidget(self.contador_faltas)
        for w in (self._fight_timer, self._round_label, self._live_stats):
            w.setVisible(True)
        # Los cuadros de faltas: el grado de la siguiente sale de cuantas
        # lleva el atleta.
        self.contador_faltas.setVisible(True)

    def _estilo_reloj(self, pro: bool) -> str:
        c = self._colors
        tam = "17px" if pro else "28px"
        return (f"color:{c.text};font-size:{tam};font-weight:700;"
                "background:transparent;border:none;")

    def _estilo_asalto(self, pro: bool) -> str:
        c = self._colors
        tam = "11px" if pro else "14px"
        return (f"color:{c.accent};font-size:{tam};font-weight:600;"
                "background:transparent;border:none;")

    def _estilo_recuento(self, pro: bool) -> str:
        c = self._colors
        p = Palette.from_config(c)
        if pro:
            # Es el dato mas importante de la franja y estaba en gris de
            # 11px, del mismo tamaño que el resto. Aqui manda.
            return ("font-size:17px;font-weight:700;letter-spacing:0.5px;"
                    "background:transparent;border:none;")
        return (f"background:{p.surface_2};color:{p.text_disabled};font-size:11px;"
                "font-weight:500;border-radius:4px;padding:2px 10px;"
                f"border:1px solid {p.border_default};")

    def show_zoom(self, visible: bool) -> None:
        """La lupa solo aparece cuando hay una accion que delimitar."""
        self.zoom_bar.setVisible(visible)

    def set_zoom_video(self, total: int, fps: float) -> None:
        self.zoom_bar.set_video(total, fps)

    def set_zoom_atleta(self, atleta: str) -> None:
        self.zoom_bar.set_atleta(atleta)

    def set_zoom_frame(self, frame: int) -> None:
        self.zoom_bar.set_frame(frame)

    def set_zoom_anotadas(self, tramos) -> None:
        self.zoom_bar.set_anotadas(tramos)

    def set_zoom_marcas(self, inicio, fin) -> None:
        self.zoom_bar.set_marcas(inicio, fin)

    # ------------------------------------------------------------------
    # HUD state
    # ------------------------------------------------------------------

    def set_hud_state(self, recording: bool, athlete: str, start_frame: int) -> None:
        self._hud_recording = recording
        self._hud_athlete = athlete
        self._hud_start_frame = start_frame

    # ------------------------------------------------------------------
    # Live Stats
    # ------------------------------------------------------------------

    def update_faltas(self, aka: int, ao: int) -> None:
        """Las faltas acumuladas de cada atleta, en cuadraditos."""
        self.contador_faltas.set_faltas(aka, ao)

    def update_live_stats(self, aka: int, ao: int, total: int, elapsed_s: float) -> None:
        """Update the live scoring strip below the video."""
        if self._modo_pro:
            # El marcador, y ya. El total de acciones lo lleva la
            # cabecera del registro, y «decorrido» duplicaba el reloj.
            c = self._colors
            self._live_stats.setTextFormat(Qt.TextFormat.RichText)
            self._live_stats.setText(
                f"<span style='color:{c.aka};font-weight:700'>{aka}</span>"
                f"<span style='color:{c.muted}'>&nbsp;—&nbsp;</span>"
                f"<span style='color:{c.ao};font-weight:700'>{ao}</span>")
            a, b = (catalogo.etiqueta(c) for c in COMPETIDORES)
            self._live_stats.setToolTip(
                f"{a} {aka} · {b} {ao} · {total} acciones anotadas")
        else:
            a, b = (catalogo.etiqueta(c) for c in COMPETIDORES)
            self._live_stats.setText(self._i18n.t(
                "video.live_stats", a=a, b=b, aka=str(aka), ao=str(ao),
                total=str(total), elapsed=f"{elapsed_s:.1f}"))

    # ------------------------------------------------------------------
    # Public update methods
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        """Al cambiar de tamaño: re-escalar el vídeo.

        El fotograma se escalaba una vez, al pintarlo, y se quedaba con
        ese tamaño. Agrandando la ventana con el vídeo parado la imagen
        seguia pequeña en medio de un marco negro hasta que algo la
        movia — que es justo lo que pasa mirando una accion parada.
        """
        from PySide6.QtCore import QEvent
        if obj is self.display and event.type() == QEvent.Resize:
            ultimo = getattr(self, "_ultimo_bgr", None)
            if ultimo is not None:
                self.update_frame_display(ultimo)
        return super().eventFilter(obj, event)

    def _densidad_de_pantalla(self) -> float:
        """Pixeles por punto del panel: 2 en una Retina, 1,25-1,5 en un
        Windows con la escala del sistema subida."""
        return float(self.display.devicePixelRatioF() or 1.0)

    def _pixmap_para_pantalla(self, bgr: np.ndarray) -> QPixmap:
        """El fotograma listo para el panel, a los pixeles reales de la pantalla."""
        h, w = bgr.shape[:2]
        # El fotograma se escala a los PIXELES REALES del panel, no a sus
        # puntos. Antes se reducia con Qt.FastTransformation (el pixel mas
        # cercano, sin filtrar) al tamaño en puntos, y en una pantalla
        # Retina el sistema lo volvia a ampliar al doble: un video 1080p
        # se veia con ~1200 pixeles de detalle y los bordes dentados.
        # Ahora: area al reducir (sin dientes), cubico al ampliar, y el
        # pixmap dice su densidad para que nadie lo reescale despues.
        dpr = self._densidad_de_pantalla()
        ancho = max(1, int(self.display.width() * dpr))
        alto = max(1, int(self.display.height() * dpr))
        escala = min(ancho / w, alto / h)
        nw, nh = max(1, round(w * escala)), max(1, round(h * escala))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if (nw, nh) != (w, h):
            rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA
                             if escala < 1 else cv2.INTER_CUBIC)
        rgb = np.ascontiguousarray(rgb)
        qimg = QImage(rgb.data, nw, nh, nw * 3, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        pix.setDevicePixelRatio(dpr)
        return pix

    def update_frame_display(self, bgr: np.ndarray, current_frame: int = -1) -> None:
        self._ultimo_bgr = bgr
        h, w = bgr.shape[:2]
        canvas = bgr
        if self._hud_recording:
            border_color = _HUD_AKA_COLOR if self._hud_athlete == "AKA" else _HUD_AO_COLOR
            thickness = max(3, min(w, h) // 200)
            cv2.rectangle(canvas, (0, 0), (w - 1, h - 1), border_color, thickness)
            # El nombre del competidor en el deporte, no el código del
            # formato: en taekwondo «AKA» no es nadie (decisión 0007).
            label = f"REC {catalogo.etiqueta(self._hud_athlete)}  F{self._hud_start_frame} -> ..."
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = max(0.7, min(min(w, h) / 800.0, 1.4))
            (tw, th), baseline = cv2.getTextSize(label, font, font_scale, 2)
            pad = int(th * 0.4)
            overlay = canvas.copy()
            cv2.rectangle(overlay, (4, 4), (4 + tw + pad * 2, 4 + th + pad * 2 + baseline), _HUD_BG, cv2.FILLED)
            cv2.addWeighted(overlay, 0.55, canvas, 0.45, 0, canvas)
            cv2.putText(canvas, label, (4 + pad, 4 + th + pad), font, font_scale, _HUD_TEXT_COLOR, 2, cv2.LINE_AA)
        self.display.setPixmap(self._pixmap_para_pantalla(canvas))

    def update_info_label(self, frame_idx: int, total: int, fps: float) -> None:
        """Donde esta el video. En PRO, solo eso.

        Decia «F:1860/12226  62.062s  30.0FPS». El total esta dibujado
        en la linea de tiempo, los fotogramas por segundo no cambian
        nunca y tres decimales de segundo no se leen de un vistazo. Lo
        largo se queda en el tooltip, para cuando de verdad haga falta.
        """
        seg = frame_idx / fps if fps > 0 else 0.0
        if self._modo_pro:
            self.lbl_info.setText(
                f"f{frame_idx}  ·  {int(seg) // 60}:{seg % 60:04.1f}")
        else:
            self.lbl_info.setText(f"F:{frame_idx}/{total}  {seg:.3f}s  {fps:.1f}FPS")
        self.lbl_info.setToolTip(
            f"fotograma {frame_idx} de {total} · {seg:.3f} s · {fps:.2f} fps")

    def update_slider(self, frame_idx: int, total: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, total - 1))
        self.slider.setValue(frame_idx)
        self.slider.blockSignals(False)

    def update_play_button(self, playing: bool) -> None:
        """Con la anotacion guiada, un simbolo; antes, la palabra de siempre.

        «Reproduzir/Pausar» son diecisiete caracteres en una fila donde
        todo lo demas cabe en cuatro. El simbolo se entiende igual y el
        atajo va en el tooltip, que es donde se busca.
        """
        if self._modo_pro:
            self.btn_play.setText("⏸" if playing else "▶")
            self.btn_play.setToolTip(
                self._i18n.t("video.pause" if playing else "video.play")
                + "   ·   " + self._i18n.t("video.tecla_k"))
            return
        self.btn_play.setText(self._i18n.t("video.pause") if playing
                              else self._i18n.t("video.play"))

    def update_marks_label(self, ann_start: Optional[int], ann_end: Optional[int]) -> None:
        """El corte en curso. En PRO, solo cuando lo hay.

        Ponia «M:-----» todo el rato, que no dice nada y ocupa sitio.
        Ahora aparece al marcar y desaparece al cerrar, que es cuando
        interesa mirarlo.
        """
        if self._modo_pro:
            if ann_start is None and ann_end is None:
                self.lbl_marks.setText("")
                return
            ini = f"f{ann_start}" if ann_start is not None else "—"
            fin = f"f{ann_end}" if ann_end is not None else "…"
            self.lbl_marks.setText(f"{ini} → {fin}")
            return
        s = str(ann_start) if ann_start is not None else "--"
        e = str(ann_end) if ann_end is not None else "--"
        self.lbl_marks.setText(f"M:{s}-{e}")

    def set_modo_fases(self, activo: bool) -> None:
        """La pasada de fases del tiempo-movimiento: [I] y [O] dicen lo que
        hacen ahi —empieza y acaba la lucha— y el marcador y la pasada se
        van, que no tienen que ver con las fases."""
        self._modo_fases = bool(activo)
        # Los botones de accion, el marcador, la pasada y la lupa son de las
        # acciones: en las fases no hay nada que delimitar ni que contar.
        self.btn_mark_start.setVisible(not activo)
        self.btn_mark_end.setVisible(not activo and not getattr(self, "_modo_eventos", False))
        self._live_stats.setVisible(not activo)
        self.lbl_pass.setVisible(not activo)
        # En la pasada de fases la línea de tiempo es más alta y la lupa se
        # queda: el especialista (15-10-2026) la quería «más alta y con zoom, como en
        # las versiones anteriores». La lupa la enciende el controlador.
        self.timeline.setFixedHeight(40 if activo else 22)

    def set_modo_eventos(self, activo: bool) -> None:
        """El técnico-táctico del taekwondo: la acción es un evento y no
        tiene fin, así que el botón FIM no está (Johan, 8-10-2026)."""
        self._modo_eventos = bool(activo)
        self.btn_mark_end.setVisible(not activo and not getattr(self, "_modo_fases", False))

    def set_pass_label(self, pass_num: int, athlete: str) -> None:
        if pass_num == 0 or not athlete:
            self.lbl_pass.setText("")
        else:
            self.lbl_pass.setText(
                self._i18n.t("pro.passe", n=str(pass_num)) if self._modo_pro else
                self._i18n.t("video.pass_label",
                             pass_num=str(pass_num), athlete=athlete))
            self.lbl_pass.setToolTip(self._i18n.t("pro.passe_tooltip", n=str(pass_num), atleta=athlete))

    def update_fight_label(self, fight_start: Optional[int], fight_end: Optional[int], fps: float) -> None:
        # Cada linea sale en cuanto existe su marca: la verde con [F], sin
        # esperar a la roja de [G]. Antes, sin final, se borraban las dos,
        # y como esto se llama en cada fotograma, el inicio del combate no
        # se veia nunca mientras se anotaba.
        self.timeline.set_fight_markers(fight_start, fight_end)
        if fight_start is None or fight_end is None:
            if fight_start is None:
                self.lbl_fight.setText("F:--")
            else:
                self.lbl_fight.setText("" if self._modo_pro
                                       else f"F:{fight_start}-")
                self.btn_fight_start.setToolTip(
                    self._i18n.t("pro.inicio_combate", frame=str(fight_start)))
            return
        dur = abs(fight_end - fight_start) / fps if fps > 0 else 0.0
        # En PRO no ocupa sitio: es un dato que no cambia en toda la
        # sesion, y los botones que lo fijan estan justo al lado.
        self.lbl_fight.setText("" if self._modo_pro
                               else f"F:{fight_start}-{fight_end} {dur:.1f}s")
        self.lbl_fight.setToolTip(self._i18n.t("pro.combate_tooltip", inicio=str(fight_start),
                                               fim=str(fight_end), dur=f"{dur:.1f}"))
        self.btn_fight_start.setToolTip(self._i18n.t("pro.inicio_combate", frame=str(fight_start)))
        self.btn_fight_end.setToolTip(self._i18n.t("pro.fim_combate", frame=str(fight_end)))
        self.timeline.set_fight_markers(fight_start, fight_end)

    def set_round_label(self, current: int, total: int,
                        fase: str = "") -> None:
        """Show 'Round X of Y' between fight timer and live stats.

        Los asaltos se marcan con [F] y [G]: el asalto avanza al cerrar el
        anterior. ``fase`` es la fase del tiempo-movimiento que rige en el
        fotograma, si se marcan.
        """
        if total > 0 and current > 0:
            texto = self._i18n.t("video.asalto", n=current, total=total)
            if fase:
                texto += f"   ·   {fase}"
            self._round_label.setText(texto)
        else:
            self._round_label.setText("")

    def set_corner_colors(self, color_a: str, color_b: str) -> None:
        """Update HUD colors from bout_info corner selection."""
        self._color_a = color_a
        self._color_b = color_b

    def update_fight_timer(self, current_frame: int, fight_start: int, fps: float) -> None:
        """Update the live fight timer (MM:SS) between fight_start and current_frame."""
        if fight_start is None or fps <= 0:
            self._fight_timer.setText("00:00")
            return
        elapsed_s = max(0, (current_frame - fight_start) / fps)
        m = int(elapsed_s) // 60
        s = int(elapsed_s) % 60
        self._fight_timer.setText(f"{m:02d}:{s:02d}")

    def set_recording_indicator(self, active: bool) -> None:
        p = Palette.from_config(self._colors)
        if active:
            # Subtle accent border while recording (no neon green)
            self._video_container.setStyleSheet(
                f"#videoContainer{{border:1px solid {p.accent_blue};border-radius:8px;background:#000;}}"
            )
        else:
            self._video_container.setStyleSheet(
                f"#videoContainer{{border:1px solid {p.border_default};border-radius:8px;background:#000;}}"
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _on_speed_change(self, idx: int) -> None:
        self.speed_changed.emit(self._video_config.speed_options[idx])

    def _on_volume_change(self, value: int) -> None:
        self.volume_changed.emit(value / 100.0)
        if not self._muted:
            self.btn_mute.setText("🔇" if value == 0 else "🔊")

    def _on_mute_clicked(self) -> None:
        self._muted = not self._muted
        self.btn_mute.setText("🔇" if self._muted else "🔊")
        self.mute_toggled.emit(self._muted)

    def _outline_btn(self, text: str, color: str, callback) -> QPushButton:
        """Minimal outline-style button: transparent bg, colored border/text."""
        btn = QPushButton(text)
        btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{color};"
            f"border:1px solid {color};border-radius:4px;"
            f"padding:3px 8px;font-size:10px;font-weight:600;}}"
            f"QPushButton:hover{{background:{color}22;}}"
            f"QPushButton:pressed{{background:{color}33;}}"
        )
        btn.clicked.connect(callback)
        return btn

    def _mark_btn_compact(self, text: str, color: str, callback) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{color};"
            f"border:1px solid {color};border-radius:4px;"
            f"padding:3px 8px;font-size:10px;font-weight:600;}}"
            f"QPushButton:hover{{background:{color}22;}}"
        )
        btn.clicked.connect(callback)
        return btn

    def _flat_btn(self, text: str, fg: str, callback, font_size: int = 12) -> QPushButton:
        p = Palette.from_config(self._colors)
        btn = QPushButton(text)
        btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{p.text_bright};border:none;"
            f"padding:5px 8px;font-size:{font_size}px;}}"
            f"QPushButton:hover{{background:{p.surface_3};border-radius:4px;}}"
        )
        btn.clicked.connect(callback)
        return btn

    def wheelEvent(self, event) -> None:
        pixel = event.pixelDelta()
        angle = event.angleDelta()
        if not pixel.isNull():
            dy = pixel.y()
        elif not angle.isNull():
            dy = angle.y()
        else:
            return
        mods = event.modifiers()
        self.wheel_scrolled.emit(dy, bool(mods & Qt.ControlModifier), bool(mods & Qt.ShiftModifier))