"""Video playback manager for KARLOS ANNOTATOR.

Encapsulates all OpenCV video I/O, frame navigation, playback control,
and fight-segment tracking. Designed to be used by a VideoPanelView
via signals/slots, keeping UI code free of video processing logic.

Audio playback is handled by QMediaPlayer + QAudioOutput (QtMultimedia)
running in parallel with the OpenCV frame pipeline, keeping them in sync
via the shared playback state (play/pause/seek/speed).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from collections import OrderedDict

import cv2
import numpy as np
import logging
import os
import time

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

_log = logging.getLogger(__name__)


def _ram_total() -> int:
    """Memoria fisica de la maquina, en bytes, o 0 si no se puede saber."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        pass
    try:                                    # Windows
        import ctypes

        class _Mem(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        info = _Mem()
        info.dwLength = ctypes.sizeof(_Mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info))
        return int(info.ullTotalPhys)
    except Exception:                       # noqa: BLE001
        return 0


def _techo_de_cache() -> int:
    """Cuanta memoria se le da a los fotogramas guardados.

    Fija en 384 MB era comodo en una maquina holgada y arriesgado en una
    justa: 384 MB de imagenes mas Qt pueden
    empujar a la memoria virtual, y ahi el decodificador empieza a
    tropezar. Los tropiezos ya no dan imagenes equivocadas, pero es
    mejor no provocarlos. Se toma el 4% de la memoria de la maquina,
    entre 96 y 384 MB.
    """
    ram = _ram_total()
    if ram <= 0:
        return 192 * 1024 * 1024            # sin saberlo, lo prudente
    techo = int(ram * 0.04)
    techo = max(96 * 1024 * 1024, min(384 * 1024 * 1024, techo))
    _log.info("Caché de fotogramas: %d MB (RAM %.1f GB)",
              techo // (1024 * 1024), ram / 1e9)
    return techo

from karlos_core.models.technique import VideoConfig


def mensaje_no_abre(path: str) -> str:
    """Aviso cuando OpenCV no reconoce el archivo. Con la ruta entera."""
    from karlos_core.utils.i18n import I18n
    return I18n().t("video.nao_abre", path=path)


def mensaje_sin_frames(path: str, lector: str, n: int) -> str:
    """Aviso cuando el archivo abre pero no se lee ni un fotograma."""
    from karlos_core.utils.i18n import I18n
    return I18n().t("video.sem_frames", path=path, leitor=(lector or "?"), n=str(n))


class VideoManager(QObject):
    """Manages video file loading, playback, and frame navigation via OpenCV.

    Audio is played by QMediaPlayer in sync with the OpenCV frame timer.

    Signals:
        frame_changed(frame_idx): Emitted when the current frame changes.
        playback_toggled(playing): Emitted when play/pause state changes.
        video_loaded(total_frames, fps): Emitted after successful video load.
        video_error(message): Emitted when a video operation fails.
    """

    frame_changed = Signal(int)
    playback_toggled = Signal(bool)
    video_loaded = Signal(int, float)
    video_error = Signal(str)

    def __init__(
        self,
        video_config: VideoConfig,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialize the video manager.

        Args:
            video_config: Video playback configuration from taxonomy.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._config = video_config
        self._cap: Optional[cv2.VideoCapture] = None
        self._total_frames: int = 0
        self._fps: float = 30.0
        self._current_frame: int = 0
        self._playing: bool = False
        self._speed: float = 1.0
        self._bgr: Optional[np.ndarray] = None

        # Fight segment markers
        self.fight_start: Optional[int] = None
        self.fight_end: Optional[int] = None

        # Annotation markers
        self.ann_start: Optional[int] = None
        self.ann_end: Optional[int] = None

        # Playback timer. PreciseTimer matters on Windows: the default
        # coarse timer has ~5% slack, which reads as constant micro-jitter
        # and slow drift against the audio track.
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._advance)

        # Wall-clock anchor for drift-corrected playback
        self._play_epoch: float = 0.0
        self._play_start_frame: int = 0

        # ── Navegacion fluida ──────────────────────────────────────
        # `cap.set()` obliga a decodificar desde el fotograma clave
        # anterior: medido sobre un combate de 1080p son 80 ms para
        # avanzar UNO, frente a 0,7 ms leyendo seguido. Ciento quince
        # veces. Como el 90% del trabajo de anotar es mover el video,
        # era el cuello de botella de todo.
        #
        # `_pos_lectura` es el fotograma que devolvera el proximo
        # `read()`. Sabiendolo se puede avanzar con `grab()`, que
        # descarta sin convertir a imagen, en vez de resembrar.
        self._pos_lectura: int = 0
        # Hasta aqui sale a cuenta ir tragando: cada grab cuesta ~0,9 ms
        # y un salto duro 80, asi que el punto de equilibrio esta cerca
        # de 88. Se deja margen.
        self._SALTO_MAX = 60
        # Por debajo de esto, lo que llega de la rueda es temblor y no
        # un gesto: se acumula y se espera en vez de mover el video.
        self._RUIDO_RUEDA = 40
        # Hacia atras no hay atajo, asi que cuando toca pagar un salto
        # se aprovecha para dejar preparados los de alrededor: una sola
        # busqueda sirve para varias flechas seguidas.
        #
        # Medido barriendo hacia atras en ID30 (1080p), que es como se
        # afina el fin de una accion:
        #
        #     prerrelleno 12, cache 192 MB    6,36 ms por fotograma
        #     prerrelleno 24, cache 192 MB    3,35
        #     prerrelleno 48, cache 384 MB    2,13
        #     prerrelleno 90, cache 768 MB    2,08
        #
        # A partir de 48 solo se gasta memoria. Con 384 MB caben 64
        # fotogramas de 1080p, suficiente para que el prerrelleno entero
        # sobreviva al barrido; con los 192 MB de antes cabian 32 y la
        # segunda mitad se expulsaba antes de llegar a usarse.
        self._PRERRELLENO = 48
        self._cache: "OrderedDict[int, np.ndarray]" = OrderedDict()
        self._cache_bytes: int = 0
        self._CACHE_MAX_BYTES = _techo_de_cache()

        # Arrastre de la lupa: llegan decenas de posiciones por segundo
        # y cada una cuesta un salto. Sin esto se encolan y la imagen va
        # detras del raton; con esto solo se atiende la ultima.
        self._arrastre_destino: Optional[int] = None
        self._arrastre_timer = QTimer(self)
        self._arrastre_timer.setSingleShot(True)
        self._arrastre_timer.timeout.connect(self._aplicar_arrastre)

        # Wheel scroll accumulator
        self._wheel_accumulator: float = 0.0
        self._wheel_timer = QTimer(self)
        self._wheel_timer.setSingleShot(True)
        self._wheel_timer.timeout.connect(self._flush_wheel)

        # ── Audio playback via QtMultimedia ────────────────────────
        self._audio_output = QAudioOutput(self)
        self._audio_output.setVolume(0.8)
        self._media_player = QMediaPlayer(self)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.errorOccurred.connect(self._on_media_error)
        self._media_duration_ms: int = 0
        self._audio_muted: bool = False
        self._volume: float = 0.8
        self._last_seek_frame: int = -1  # avoid feedback loop on seek

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_frames(self) -> int:
        """Total number of frames in the loaded video."""
        return self._total_frames

    @property
    def total_duration_s(self) -> float:
        """Total duration of the loaded video in seconds."""
        if self._fps > 0:
            return self._total_frames / self._fps
        return 0.0

    @property
    def fps(self) -> float:
        """Frames per second of the loaded video."""
        return self._fps

    @property
    def current_frame(self) -> int:
        """Current frame index (0-based)."""
        return self._current_frame

    @property
    def is_playing(self) -> bool:
        """Whether playback is currently active."""
        return self._playing

    @property
    def is_loaded(self) -> bool:
        """Whether a video file has been successfully loaded."""
        return self._cap is not None and self._cap.isOpened()

    @property
    def current_bgr(self) -> Optional[np.ndarray]:
        """Current frame as a BGR numpy array, or None if no video loaded."""
        return self._bgr

    # ------------------------------------------------------------------
    # Video Loading
    # ------------------------------------------------------------------

    def load(self, path: str | Path) -> bool:
        """Load a video file for playback.

        Args:
            path: Filesystem path to the video file.

        Returns:
            True if the video was loaded successfully, False otherwise.
        """
        self._release()
        path_str = str(path)
        self._cap = cv2.VideoCapture(path_str)
        if not self._cap.isOpened():
            self._cap = None
            self.video_error.emit(mensaje_no_abre(path_str))
            return False

        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        lector = self._cap.getBackendName()
        self.ann_start = None
        self.ann_end = None
        # Los marcadores de combate pertenecen al video que se abandona.
        # Sin este reinicio se filtraban al siguiente video y se guardaban
        # en su sesion, corrompiendo duracion del combate, tiempo activo y
        # fase (Minute_1/2/3) de un combate que nunca se marco.
        # El restaurador de sesion vuelve a fijarlos, si los hubiera,
        # al recibir video_loaded.
        self.fight_start = None
        self.fight_end = None
        if self._total_frames <= 0 or not self._goto(0):
            # Abrir no es leer. Un archivo que OpenCV reconoce pero no
            # decodifica (nube sin descargar, decodificador que falta)
            # dejaba la ventana en negro y la linea de tiempo vacia sin
            # decir nada.
            motivo = mensaje_sin_frames(path_str, lector, self._total_frames)
            self._release()
            self.video_error.emit(motivo)
            return False
        self.video_loaded.emit(self._total_frames, self._fps)

        # ── Load audio track via QMediaPlayer ─────────────────────
        self._media_player.setSource(QUrl.fromLocalFile(path_str))
        # Duration is not immediately available; defer until media is loaded
        self._media_duration_ms = 0
        # Start at the beginning
        self._media_player.setPosition(0)

        return True

    def release(self) -> None:
        """Release the current video capture and reset state."""
        self.stop()
        self._release()

    def _release(self) -> None:
        """Internal: release OpenCV capture and audio without stopping timer."""
        self._media_player.stop()
        self._media_player.setSource(QUrl())
        self._media_duration_ms = 0
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._total_frames = 0
        self._fps = 30.0
        self._current_frame = 0
        self._bgr = None
        self._olvidar()

    # ------------------------------------------------------------------
    # Frame Navigation
    # ------------------------------------------------------------------

    def goto(self, frame_idx: int) -> bool:
        """Seek to a specific frame index.

        Args:
            frame_idx: Target frame index (clamped to valid range).

        Returns:
            True if the seek was successful.
        """
        return self._goto(frame_idx)

    def _goto(self, frame_idx: int) -> bool:
        """Internal: seek to frame index without extra validation."""
        if not self.is_loaded:
            return False
        frame_idx = max(0, min(frame_idx, self._total_frames - 1))
        if frame_idx == self._current_frame and self._bgr is not None:
            return True
        frame = self._leer(frame_idx)
        if frame is None:
            return False
        self._current_frame = frame_idx
        self._bgr = frame
        self.frame_changed.emit(frame_idx)

        # ── Seek audio to match new frame position ────────────────
        self._sync_audio_to_frame()

        # Re-anchor the playback clock so a seek during playback does
        # not snap back to the pre-seek timeline on the next tick.
        if self._playing:
            self._play_epoch = time.monotonic()
            self._play_start_frame = frame_idx

        return True

    # ------------------------------------------------------------------
    # Lectura barata
    # ------------------------------------------------------------------

    def _guardar(self, idx: int, frame) -> None:
        """Dejar el fotograma a mano, con un techo de memoria.

        El techo va en bytes y no en numero de fotogramas porque un
        combate de 1080p ocupa el triple que uno de 720p por fotograma,
        y el limite tiene que ser el mismo en los dos.
        """
        if idx in self._cache:
            return
        self._cache[idx] = frame
        self._cache_bytes += frame.nbytes
        while self._cache_bytes > self._CACHE_MAX_BYTES and len(self._cache) > 1:
            _, viejo = self._cache.popitem(last=False)
            self._cache_bytes -= viejo.nbytes

    def _leer(self, objetivo: int, reintento: bool = False):
        """El fotograma pedido, por el camino mas barato que sirva.

        Tres caminos, de barato a caro: ya lo tenemos, lo alcanzamos
        tragando hacia adelante, o hay que resembrar el decodificador.

        Sea cual sea el camino, al final se le pregunta al decodificador
        si lo que entrega es de verdad el fotograma pedido. Si no lo es,
        se resiembra y se reintenta una vez; si sigue sin serlo, se
        devuelve None. Antes se prefiere no enseñar nada que enseñar la
        imagen de otro fotograma con el numero de este.
        """
        guardado = self._cache.get(objetivo)
        if guardado is not None:
            self._cache.move_to_end(objetivo)
            return guardado

        # `_pos_lectura` a -1 significa «no se sabe donde quedo el
        # decodificador». Se pone asi ante cualquier fallo, y obliga a
        # resembrar en vez de contar a ciegas desde una posicion que ya
        # no es cierta.
        salto = (objetivo - self._pos_lectura
                 if self._pos_lectura >= 0 else None)
        if salto is not None and 0 <= salto <= self._SALTO_MAX:
            for _ in range(salto):
                if not self._cap.grab():
                    self._pos_lectura = -1
                    return None
                self._pos_lectura += 1
        else:
            # Hacia atras se retrocede un poco de mas y se lee hasta el
            # objetivo: la busqueda ya esta pagada y los fotogramas que
            # se cruzan por el camino son los que vienen despues si se
            # sigue retrocediendo, asi que se quedan guardados.
            desde = objetivo
            # Solo se prerrellena cuando el salto hacia atras es corto,
            # que es el retroceso de quien esta ajustando un limite y va
            # a seguir retrocediendo. En un salto largo —soltar la lupa
            # lejos— nadie va a pedir los de al lado, y leerlos era pagar
            # doce fotogramas de mas por nada.
            if salto is not None and -self._SALTO_MAX <= salto < 0:
                desde = max(0, objetivo - self._PRERRELLENO)
            if not self._sembrar(desde, objetivo):
                return None
            while self._pos_lectura < objetivo:
                ok, previo = self._cap.read()
                if not ok:
                    self._pos_lectura = -1
                    return None
                if not self._donde_dice_estar(self._pos_lectura + 1):
                    # Se salto uno por el camino: lo que viene detras ya
                    # no lleva el numero que creemos, asi que no se
                    # guarda nada mas y se vuelve a empezar.
                    self._pos_lectura = -1
                    return None if reintento else self._leer(objetivo, True)
                self._guardar(self._pos_lectura, previo)
                self._pos_lectura += 1

        ok, frame = self._cap.read()
        if not ok:
            self._pos_lectura = -1
            return None

        # La comprobacion que lo cierra todo: el decodificador tiene que
        # confirmar que lo leido ES el fotograma pedido. Cuesta el 0,01%
        # de una lectura —medido— y es lo unico que garantiza que nunca
        # se muestre una imagen que no corresponde a su numero. Sin
        # ella, un tropiezo de decodificacion corria la cuenta y la
        # imagen equivocada acababa guardada con el numero bueno.
        if not self._donde_dice_estar(objetivo + 1):
            self._pos_lectura = -1
            if reintento:
                _log.warning("El decodificador no entrega el fotograma %d "
                             "ni resembrando; no se muestra nada.", objetivo)
                return None
            _log.info("Fotograma %d descolocado; se resiembra.", objetivo)
            return self._leer(objetivo, True)

        self._pos_lectura = objetivo + 1
        self._guardar(objetivo, frame)
        return frame

    def _donde_dice_estar(self, esperado: int) -> bool:
        """Si el decodificador confirma que va por donde creemos.

        Devuelve True cuando no sabe decirlo: hay lectores que no
        informan de la posicion, y ahi no se puede comprobar nada. Mejor
        seguir que negarse a funcionar.
        """
        pos = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
        if pos <= 0:
            return True
        return pos == esperado

    def _sembrar(self, desde: int, objetivo: int) -> bool:
        """Dejar el decodificador listo para leer, y saber DONDE quedo.

        No se da por supuesto que la busqueda caiga donde se pide. Segun
        la compilacion de ffmpeg puede aterrizar en el fotograma clave
        anterior, y entonces todo lo que se lea despues va corrido: la
        imagen no corresponde al numero, y encima se guarda en la cache
        CON ese numero, asi que el error no se va ni volviendo. En este
        Mac la busqueda es exacta; en otra maquina no tiene por que, y
        eso no se puede dar por hecho.

        Se le pregunta al decodificador donde quedo. Si se paso del
        objetivo se reintenta mas atras, porque desde delante no se
        puede llegar leyendo hacia adelante.
        """
        for intento in (desde, max(0, desde - 120), 0):
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, intento))
            real = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
            if real < 0:
                real = max(0, intento)      # el lector no sabe decirlo
            if real <= objetivo:
                self._pos_lectura = real
                return True
        self._pos_lectura = -1
        return False

    def _olvidar(self) -> None:
        self._cache.clear()
        self._cache_bytes = 0
        self._pos_lectura = 0

    # ------------------------------------------------------------------
    # Arrastre de la lupa
    # ------------------------------------------------------------------

    def arrastrar(self, frame_idx: int) -> None:
        """Posicion pedida arrastrando: solo se atiende la ultima.

        Arrastrando llegan decenas por segundo. Atenderlas todas era
        encolar saltos de 80 ms y ver la imagen ir detras del raton.
        """
        self._arrastre_destino = int(frame_idx)
        if not self._arrastre_timer.isActive():
            self._arrastre_timer.start(16)

    def _aplicar_arrastre(self) -> None:
        destino = self._arrastre_destino
        self._arrastre_destino = None
        if destino is not None:
            self._goto(destino)

    def step(self, delta: int) -> None:
        """Advance or rewind by a number of frames, pausing playback first.

        Pisar un frame es una decision de precision: si el video sigue
        reproduciendose, el reloj interno avanza solo entre pulsacion y
        pulsacion, y en una maquina justa ademas salta los frames que la
        decodificacion no alcanza (_advance corrige contra el reloj de
        pared). Anotando de verdad eso se sentia como [J]/[L] "saltando"
        justo despues de marcar [I] al vuelo: imposible clavar el frame
        exacto. Todos los montadores hacen lo mismo desde hace decadas:
        el paso de frame pausa primero. Por aqui pasan las flechas,
        [J]/[L] y la rueda, asi que una sola pausa cubre todo.

        Args:
            delta: Positive to advance, negative to rewind.
        """
        self.stop()
        self._goto(self._current_frame + delta)

    # ------------------------------------------------------------------
    # Playback Control
    # ------------------------------------------------------------------

    def toggle_play(self) -> None:
        """Toggle between play and pause states."""
        if not self.is_loaded:
            return
        self._playing = not self._playing
        if self._playing:
            self._play_epoch = time.monotonic()
            self._play_start_frame = self._current_frame
            interval = int(1000 / (self._fps * self._speed))
            self._timer.start(max(16, interval))
            # ── Sync audio position to current frame then play ──
            self._sync_audio_to_frame()
            self._media_player.play()
        else:
            self._timer.stop()
            self._media_player.pause()
        self.playback_toggled.emit(self._playing)

    def stop(self) -> None:
        """Stop playback and reset the timer."""
        if self._playing:
            self._playing = False
            self._timer.stop()
            self._media_player.pause()
            self.playback_toggled.emit(False)

    def set_speed(self, speed: float) -> None:
        """Change playback speed multiplier.

        Args:
            speed: Playback speed (e.g., 1.0 = normal, 0.5 = half).
        """
        self._speed = speed
        # ── Audio playback rate ─────────────────────────────────
        self._media_player.setPlaybackRate(speed)
        if self._playing:
            # Re-anchor the clock so the speed change applies from here
            self._play_epoch = time.monotonic()
            self._play_start_frame = self._current_frame
            self._sync_audio_to_frame()
            self._timer.stop()
            interval = int(1000 / (self._fps * self._speed))
            self._timer.start(max(16, interval))

    def _advance(self) -> None:
        """Internal: advance playback locked to wall-clock time.

        Weak machines cannot always decode + paint at full fps. Instead
        of letting the video slip behind the audio (the old behaviour:
        one frame per tick no matter how late the tick fires), compute
        the frame the clock says we should be showing and skip cheaply
        to it with grab() — dropping frames keeps motion and audio in
        sync, which reads as "smooth" even on slow hardware.
        """
        if self._cap is None or not self._playing:
            # Un tick que ya estaba en la cola de eventos llega despues
            # de pausar. Sin esta guarda ese tick tardio calculaba el
            # objetivo con el reloj viejo y teletransportaba el frame
            # justo despues de un paso de precision. Es el salto que se
            # sentia anotando: pausar, pisar un frame, y verlo huir.
            return
        if self._current_frame >= self._total_frames - 1:
            self.stop()
            return

        elapsed = time.monotonic() - self._play_epoch
        target = self._play_start_frame + int(elapsed * self._fps * self._speed)
        if target <= self._current_frame:
            return  # timer fired early — this frame is still current
        target = min(target, self._total_frames - 1)

        # El fotograma se pide por el mismo camino que un paso. Antes se
        # leia «el siguiente» del decodificador, dando por hecho que
        # estaba justo detras del fotograma en pantalla, y no siempre lo
        # esta: si lo ultimo salio de la cache, el decodificador se quedo
        # donde leyo por ultima vez. Parar, retroceder con [J], volver
        # con [L] y dar a reproducir bastaba para que el numero y la
        # imagen fueran cinco fotogramas corridos (medido en ID01), y
        # esas imagenes se guardaban en la cache con el numero malo:
        # despues [J] y [L] las ensenaban, y el video parecia saltar o
        # volver a otro sitio. `_leer` sabe donde esta el decodificador,
        # se salta con grab() lo que haga falta, busca si el salto es
        # largo, y comprueba que la imagen sea la del numero.
        frame = self._leer(target)
        if frame is None:
            self.stop()
            return
        self._current_frame = target
        self._bgr = frame
        self.frame_changed.emit(self._current_frame)
        # Audio is played independently by QMediaPlayer at the correct rate;
        # no per-frame audio sync needed during continuous playback.

    # ------------------------------------------------------------------
    # Annotation Markers
    # ------------------------------------------------------------------

    def mark_annotation_start(self) -> None:
        """Record the current frame as the annotation START marker."""
        self.ann_start = self._current_frame

    def mark_annotation_end(self) -> None:
        """Record the current frame as the annotation END marker."""
        self.ann_end = self._current_frame

    def clear_annotation_markers(self) -> None:
        """Reset both annotation markers."""
        self.ann_start = None
        self.ann_end = None

    def set_fight_start(self) -> None:
        """Record the current frame as the fight segment START."""
        self.fight_start = self._current_frame
        _log.debug("set_fight_start: fight_start=%s", self.fight_start)

    def set_fight_end(self) -> None:
        """Record the current frame as the fight segment END."""
        self.fight_end = self._current_frame
        _log.debug("set_fight_end: fight_end=%s", self.fight_end)

    # ------------------------------------------------------------------
    # Wheel Scroll Handling
    # ------------------------------------------------------------------

    def accumulate_wheel(self, delta_y: int, ctrl: bool, shift: bool) -> None:
        """Accumulate mouse wheel scroll delta for batched frame stepping.

        Args:
            delta_y: Raw wheel delta in pixels/angle units.
            ctrl: Whether Ctrl modifier was held during scroll.
            shift: Whether Shift modifier was held during scroll.
        """
        if ctrl and shift:
            multiplier = 60
        elif shift:
            multiplier = 30
        elif ctrl:
            multiplier = 10
        else:
            multiplier = 1
        self._wheel_accumulator += delta_y * multiplier
        self._wheel_timer.start(16)

    def _flush_wheel(self) -> None:
        """Apply accumulated wheel scroll as frame steps."""
        if not self.is_loaded:
            self._wheel_accumulator = 0.0
            return

        acc = self._wheel_accumulator
        if acc == 0:
            return

        abs_acc = abs(acc)
        cfg = self._config
        if abs_acc >= cfg.wheel_threshold_large:
            step = cfg.wheel_step_large
        elif abs_acc >= cfg.wheel_threshold_medium:
            step = cfg.wheel_step_medium
        else:
            step = cfg.wheel_step_small

        # Un diente de rueda son 120 unidades. Lo que sobra se GUARDA:
        # antes se tiraba el acumulador entero en cada vaciado y ademas
        # se forzaba un fotograma aunque no hubiera llegado a un diente,
        # asi que cualquier roce movia el video. Con un raton no se nota
        # —sus dientes son de 120 justos— pero un trackpad de precision
        # manda decenas de deltas minimos por segundo y el video no se
        # quedaba quieto.
        dientes = int(abs_acc / 120)
        if dientes >= 1:
            gastado = dientes * 120
            self._wheel_accumulator = acc - (gastado if acc > 0 else -gastado)
        elif abs_acc >= self._RUIDO_RUEDA:
            # Un gesto corto pero deliberado: vale un fotograma.
            dientes = 1
            self._wheel_accumulator = 0.0
        else:
            return          # ruido: se guarda y se espera al siguiente

        total_steps = dientes * step
        self.step(total_steps if acc > 0 else -total_steps)

    # ------------------------------------------------------------------
    # Frame Retrieval
    # ------------------------------------------------------------------

    def get_frames(self) -> list[np.ndarray]:
        """Extract all frames between annotation START and END markers.

        Returns:
            List of BGR frame arrays, or empty list if markers are invalid.
        """
        if (
            not self.is_loaded
            or self.ann_start is None
            or self.ann_end is None
        ):
            return []

        a = min(self.ann_start, self.ann_end)
        b = max(self.ann_start, self.ann_end)
        # Por `_leer`, como todo lo que llega a la cache: mover el
        # decodificador por detras y guardar sin comprobar es justo lo
        # que dejaba imagenes con el numero de otro fotograma.
        frames: list[np.ndarray] = []
        for idx in range(a, b + 1):
            f = self._leer(idx)
            if f is None:
                break
            frames.append(f)
        return frames

    # ------------------------------------------------------------------
    # Fight Duration
    # ------------------------------------------------------------------

    def fight_duration_s(self) -> Optional[float]:
        """Calculate fight segment duration in seconds.

        Returns:
            Duration in seconds, or None if fight markers are not set.
        """
        if self.fight_start is None or self.fight_end is None:
            return None
        return abs(self.fight_end - self.fight_start) / self._fps

    # ------------------------------------------------------------------
    # Audio Helpers
    # ------------------------------------------------------------------

    def _sync_audio_to_frame(self) -> None:
        """Seek the QMediaPlayer to the position matching current frame."""
        if self._fps <= 0:
            return
        pos_ms = self._frame_to_position_ms(self._current_frame)
        self._media_player.setPosition(pos_ms)

    def _frame_to_position_ms(self, frame_idx: int) -> int:
        """Convert a frame index to milliseconds for QMediaPlayer."""
        return int((frame_idx / self._fps) * 1000)

    def _on_media_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """Handle QMediaPlayer errors without blocking annotation."""
        # Audio errors shouldn't block video annotation, but they must
        # reach the log file — a windowed .exe has no console for print.
        _log.warning("QMediaPlayer error %s: %s", error, error_string)

    # ------------------------------------------------------------------
    # Public Volume / Mute API
    # ------------------------------------------------------------------

    def set_volume(self, volume: float) -> None:
        """Set audio volume (0.0 = silent, 1.0 = max).

        Args:
            volume: Volume level between 0.0 and 1.0.
        """
        self._volume = max(0.0, min(1.0, volume))
        self._audio_output.setVolume(self._volume)

    def volume(self) -> float:
        """Return current volume level."""
        return self._volume

    def set_muted(self, muted: bool) -> None:
        """Mute or unmute audio.

        Args:
            muted: True to mute, False to unmute.
        """
        self._audio_muted = muted
        self._audio_output.setMuted(muted)

    def is_muted(self) -> bool:
        """Return True if audio is currently muted."""
        return self._audio_muted
