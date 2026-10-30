"""Tests for VideoManager's drift-corrected playback.

The playback clock is wall-time based: each timer tick computes which
frame SHOULD be showing and skips ahead if decoding fell behind. These
tests drive _advance() directly against a tiny generated video, with
the QtMultimedia audio objects mocked out so they run headless in CI.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

# Imported explicitly so mock.patch can resolve the dotted target on
# Python 3.11 (3.14 auto-imports submodules during resolution; 3.11 not).
import karlos_core.controllers.video_manager  # noqa: F401
from karlos_core.models.technique import VideoConfig

FPS = 30.0
TOTAL_FRAMES = 60  # 2 seconds

VIDEO_CONFIG = VideoConfig(
    speed_options=[0.5, 1.0, 2.0], speed_labels=["0.5x", "1x", "2x"],
    default_speed_index=1, wheel_step_small=1, wheel_step_medium=5,
    wheel_step_large=10, wheel_threshold_small=120,
    wheel_threshold_medium=360, wheel_threshold_large=720,
)


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture(scope="module")
def video_file(tmp_path_factory):
    path = tmp_path_factory.mktemp("video") / "clip.mp4"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (64, 48)
    )
    for i in range(TOTAL_FRAMES):
        frame = np.full((48, 64, 3), i * 4 % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return str(path)


@pytest.fixture()
def vm(video_file):
    # Audio is exercised manually in the app; here it would need a real
    # multimedia backend, so stub it out to keep the test headless.
    with patch("karlos_core.controllers.video_manager.QMediaPlayer", MagicMock()), \
         patch("karlos_core.controllers.video_manager.QAudioOutput", MagicMock()):
        from karlos_core.controllers.video_manager import VideoManager
        manager = VideoManager(VIDEO_CONFIG)
        assert manager.load(video_file)
        yield manager
        manager.release()


class TestArchivosIlegibles:
    """Un archivo que OpenCV no lee avisa con la ruta, y no queda cargado."""

    def _manager(self):
        from karlos_core.controllers.video_manager import VideoManager
        return VideoManager(VIDEO_CONFIG)

    def test_un_archivo_que_no_es_video_lo_dice_con_la_ruta(self, tmp_path):
        falso = tmp_path / "combate.mp4"
        falso.write_bytes(b"isto nao e um video " * 200)
        with patch("karlos_core.controllers.video_manager.QMediaPlayer", MagicMock()), \
             patch("karlos_core.controllers.video_manager.QAudioOutput", MagicMock()):
            manager = self._manager()
            avisos = []
            manager.video_error.connect(avisos.append)
            assert manager.load(str(falso)) is False
            assert not manager.is_loaded
            assert manager.total_frames == 0
        assert len(avisos) == 1 and "combate.mp4" in avisos[0]

    def test_el_video_bueno_sigue_cargando(self, vm, video_file):
        assert vm.is_loaded and vm.total_frames == TOTAL_FRAMES


class TestElPasoDeFramePausaPrimero:
    """[J]/[L]/flechas/rueda con el video en marcha: primero se pausa.

    Sin esto, el reloj de pared seguia corriendo entre pulsacion y
    pulsacion y _advance saltaba los frames que la decodificacion no
    alcanzaba. Anotando de verdad era imposible clavar el frame exacto
    de inicio y fin de cada accion, que es el trabajo entero.
    """

    def test_step_con_el_video_en_marcha_pausa_y_clava_el_frame(self, vm):
        vm.goto(10)
        vm._playing = True
        vm._play_epoch = time.monotonic() - 0.5
        vm._play_start_frame = 10
        vm.step(1)
        assert vm._playing is False
        assert vm.current_frame == 11
        # Y nada vuelve a moverse solo: el tick del reloj ya no avanza.
        antes = vm.current_frame
        vm._advance()
        assert vm.current_frame == antes

    def test_step_en_pausa_sigue_moviendo_un_frame_exacto(self, vm):
        vm.goto(20)
        vm.step(1);  assert vm.current_frame == 21
        vm.step(-1); assert vm.current_frame == 20

    def test_la_rueda_tambien_pausa(self, vm):
        """La rueda acumula y llama a step(): mismo camino, misma pausa."""
        vm.goto(10)
        vm._playing = True
        vm._play_epoch = time.monotonic()
        vm._play_start_frame = 10
        vm._wheel_accumulator = 120.0
        vm._flush_wheel()
        assert vm._playing is False
        assert vm.current_frame == 11


class TestElLectorNoSeDescoloca:
    """Un fallo de lectura descolocaba el lector para siempre.

    `_pos_lectura` dice dónde quedó el decodificador. Ante un grab() o
    un read() fallido se devolvía None sin tocarla, pero el
    decodificador SÍ había consumido el intento: desde ahí el número de
    fotograma y la imagen iban corridos, y lo peor es que la imagen
    equivocada se guardaba en la caché CON el número bueno, así que el
    error no se iba ni volviendo a pasar por ahí.

    Es el fallo que se nota en una máquina justa, donde los tropiezos de
    decodificación son más probables. Reproducido sobre ID30: un solo
    grab() fallido bastaba para que f5002 devolviera la imagen de otro
    fotograma.
    """

    class _CapQueFalla:
        """El decodificador real, que consume el intento pero dice que no."""

        def __init__(self, real, fallos):
            self._r, self._quedan = real, fallos

        def grab(self):
            ok = self._r.grab()
            if self._quedan > 0:
                self._quedan -= 1
                return False
            return ok

        def __getattr__(self, n):
            return getattr(self._r, n)

    def test_tras_un_fallo_no_se_fia_de_la_posicion(self, vm):
        vm.goto(20)
        assert vm._pos_lectura >= 0
        vm._cap = self._CapQueFalla(vm._cap, 1)
        assert vm._leer(25) is None
        assert vm._pos_lectura == -1, "tiene que declarar que no sabe dónde está"

    def test_y_la_siguiente_lectura_resiembra_y_acierta(self, vm):
        """Lo que importa: que la imagen vuelva a ser la del número."""
        vm.goto(20)
        esperado = vm._leer(30)
        vm._cache.clear(); vm._cache_bytes = 0
        vm.goto(20)
        vm._cap = self._CapQueFalla(vm._cap, 1)
        vm._leer(25)                       # falla
        vm._cap._quedan = 0
        vm._cache.clear(); vm._cache_bytes = 0
        assert (vm._leer(30) == esperado).all()

    def test_la_busqueda_no_se_da_por_buena_sin_preguntar(self, vm):
        """En este Mac cae exacta, pero eso no se puede dar por hecho:
        otra compilación de ffmpeg puede aterrizar en el fotograma clave
        anterior, y entonces todo lo que sigue va corrido."""
        import inspect
        fuente = inspect.getsource(type(vm)._sembrar)
        assert "CAP_PROP_POS_FRAMES" in fuente
        assert "get(" in fuente, "hay que preguntarle dónde quedó"

    def test_si_la_busqueda_se_pasa_se_reintenta_mas_atras(self, vm):
        """Desde delante del objetivo no se llega leyendo hacia adelante."""
        vm.goto(500)
        assert vm._sembrar(400, 400) is True
        assert 0 <= vm._pos_lectura <= 400


class TestNuncaSeMuestraOtroFotograma:
    """La garantía dura: o es el fotograma pedido, o no hay imagen.

    Después de leer se le pregunta al decodificador si lo que entrega
    es de verdad lo pedido. Cuesta el 0,01% de una lectura (medido) y
    es lo único que impide que un tropiezo acabe mostrando la imagen de
    otro fotograma con el número de este. Si no cuadra se resiembra y
    se reintenta una vez; si sigue sin cuadrar, no se muestra nada.
    """

    class _CapTramposo:
        """Consume fotogramas de más sin decirlo, como una máquina que
        tropieza."""

        def __init__(self, real, cada):
            self._r, self._n, self._cada = real, 0, cada

        def grab(self):
            self._n += 1
            ok = self._r.grab()
            if self._cada and self._n % self._cada == 0:
                self._r.grab()          # se come uno de más, en silencio
                return False
            return ok

        def __getattr__(self, n):
            return getattr(self._r, n)

    def test_con_una_maquina_que_tropieza_no_hay_imagenes_cambiadas(self, vm):
        buenas = {f: vm._leer(f).copy() for f in range(30, 45)}
        vm._cache.clear(); vm._cache_bytes = 0
        vm.goto(29)
        vm._cap = self._CapTramposo(vm._cap, 3)
        for f in range(30, 45):
            img = vm._leer(f)
            if img is None:
                continue            # negarse es aceptable; mentir no
            assert (img == buenas[f]).all(), f"f{f} devolvió otra imagen"

    def test_si_el_decodificador_no_sabe_decirlo_no_se_bloquea(self, vm):
        """Hay lectores que no informan de la posición: ahí no se puede
        comprobar, y negarse a funcionar sería peor."""
        class _Mudo:
            def __init__(self, real): self._r = real
            def get(self, propid): return 0
            def __getattr__(self, n): return getattr(self._r, n)
        vm.goto(20)
        vm._cap = _Mudo(vm._cap)
        assert vm._leer(21) is not None


class TestReproducirNoDescolocaLaImagen:
    """Reproducir leia «el siguiente» sin mirar donde estaba el lector.

    Si lo ultimo que se enseño salio de la cache, el decodificador se
    quedo donde leyo por ultima vez, y reproducir desde ahi daba la
    imagen de otro fotograma con el numero de este. Lo peor: se guardaba
    en la cache con ese numero, y despues [J] y [L] la enseñaban. Es lo
    que Johan vio anotando (28-09): tras parar y afinar con [J]/[L], el
    video saltaba o volvia a otro sitio. En ID01 el desfase era de 5
    fotogramas, y de 20 en otra pasada.
    """

    def _tick(self, vm):
        """Un tick del reloj de reproduccion, justo en el fotograma siguiente."""
        vm._playing = True
        vm._play_start_frame = vm.current_frame
        vm._play_epoch = time.monotonic() - 1.2 / (vm.fps * vm._speed)
        vm._advance()

    def _referencia(self, vm):
        buenas = {f: vm._leer(f).copy() for f in range(TOTAL_FRAMES)}
        vm._cache.clear(); vm._cache_bytes = 0
        return buenas

    def test_reproducir_tras_un_salto_servido_de_la_cache(self, vm):
        buenas = self._referencia(vm)
        vm.goto(50)                       # el lector queda en 51
        vm.goto(30)                       # sale de la cache: el lector sigue en 51
        vm._cache.clear(); vm._cache_bytes = 0
        for _ in range(5):
            self._tick(vm)
            f = vm.current_frame
            assert (vm.current_bgr == buenas[f]).all(), f"f{f} con la imagen de otro"

    def test_y_lo_que_queda_en_la_cache_es_lo_bueno(self, vm):
        """Lo que se ve despues con [J] sale de lo guardado al reproducir."""
        buenas = self._referencia(vm)
        vm.goto(50)
        vm.goto(30)
        vm._cache.clear(); vm._cache_bytes = 0   # que lo guardado sea lo de reproducir
        for _ in range(8):
            self._tick(vm)
        vm.stop()
        for _ in range(8):
            vm.step(-1)
            f = vm.current_frame
            assert (vm.current_bgr == buenas[f]).all(), f"[J] a f{f} con la imagen de otro"

    def test_nada_llega_a_la_cache_sin_pasar_por_leer(self, vm):
        """El decodificador solo se toca donde se comprueba lo leido."""
        import inspect
        fuente = inspect.getsource(type(vm))
        for fn in ("_advance", "get_frames", "step", "_goto"):
            cuerpo = inspect.getsource(getattr(type(vm), fn))
            assert "_cap.read(" not in cuerpo and "_cap.grab(" not in cuerpo, fn
        assert fuente.count("_cap.read(") == 2 and fuente.count("_cap.grab(") == 1


class TestLaCacheSeAdaptaALaMaquina:
    def test_una_maquina_justa_recibe_menos_cache(self, monkeypatch):
        from karlos_core.controllers import video_manager as vmod
        monkeypatch.setattr(vmod, "_ram_total", lambda: 4 * 10**9)
        chico = vmod._techo_de_cache()
        monkeypatch.setattr(vmod, "_ram_total", lambda: 32 * 10**9)
        grande = vmod._techo_de_cache()
        assert chico < grande
        assert 96 * 1024 * 1024 <= chico <= 384 * 1024 * 1024

    def test_sin_saber_la_memoria_se_queda_en_lo_prudente(self, monkeypatch):
        from karlos_core.controllers import video_manager as vmod
        monkeypatch.setattr(vmod, "_ram_total", lambda: 0)
        assert vmod._techo_de_cache() == 192 * 1024 * 1024


class TestLaRuedaNoSaltaConElRoce:
    """La rueda tiraba el resto y forzaba un fotograma con cualquier delta.

    Un diente de ratón son 120 unidades justas y no se notaba. Un
    trackpad de precisión manda decenas de deltas mínimos por segundo, y
    con cada vaciado se forzaba un paso: el vídeo no se quedaba quieto.
    """

    def test_un_temblor_por_debajo_del_umbral_no_mueve_nada(self, vm):
        vm.goto(20)
        vm._wheel_accumulator = 5.0
        vm._flush_wheel()
        assert vm.current_frame == 20
        # Y no se tira: sigue acumulado para el próximo.
        assert vm._wheel_accumulator == 5.0

    def test_el_temblor_repetido_acaba_sumando_un_fotograma(self, vm):
        vm.goto(20)
        for _ in range(10):
            vm._wheel_accumulator += 5.0
            vm._flush_wheel()
        assert vm.current_frame == 21, "diez roces son un gesto, y valen uno"

    def test_un_diente_entero_mueve_uno_y_no_deja_resto(self, vm):
        vm.goto(20)
        vm._wheel_accumulator = 120.0
        vm._flush_wheel()
        assert vm.current_frame == 21
        assert vm._wheel_accumulator == 0.0

    def test_dos_dientes_y_medio_mueven_dos_y_guardan_el_medio(self, vm):
        vm.goto(20)
        vm._wheel_accumulator = 300.0
        vm._flush_wheel()
        assert vm.current_frame == 22
        assert vm._wheel_accumulator == 60.0

    def test_hacia_atras_igual(self, vm):
        vm.goto(20)
        vm._wheel_accumulator = -120.0
        vm._flush_wheel()
        assert vm.current_frame == 19
        assert vm._wheel_accumulator == 0.0


class TestDriftCorrectedAdvance:
    def _start_playing(self, vm, seconds_ago: float) -> None:
        vm._playing = True
        vm._play_epoch = time.monotonic() - seconds_ago
        vm._play_start_frame = vm.current_frame

    def test_early_tick_shows_nothing_new(self, vm):
        self._start_playing(vm, seconds_ago=0.0)
        vm._advance()
        assert vm.current_frame == 0

    def test_one_second_elapsed_lands_on_wall_clock_frame(self, vm):
        self._start_playing(vm, seconds_ago=1.0)
        vm._advance()
        # 1s × 30fps → frame ~30 even though only ONE tick fired.
        assert 28 <= vm.current_frame <= 33

    def test_far_behind_hard_seeks_to_end(self, vm):
        self._start_playing(vm, seconds_ago=10.0)
        vm._advance()
        assert vm.current_frame == TOTAL_FRAMES - 1

    def test_speed_multiplier_respected(self, vm):
        vm._speed = 2.0
        self._start_playing(vm, seconds_ago=0.5)
        vm._advance()
        # 0.5s × 30fps × 2.0 → frame ~30
        assert 28 <= vm.current_frame <= 33

    def test_seek_during_playback_reanchors_clock(self, vm):
        self._start_playing(vm, seconds_ago=1.0)
        vm.goto(10)
        # goto() must re-anchor: an immediate tick shows ~frame 10,
        # not a snap back to the pre-seek wall-clock timeline (~30).
        vm._advance()
        assert 10 <= vm.current_frame <= 12


class TestVolumeApi:
    def test_volume_clamped(self, vm):
        vm.set_volume(1.7)
        assert vm.volume() == 1.0
        vm.set_volume(-0.3)
        assert vm.volume() == 0.0

    def test_mute_roundtrip(self, vm):
        vm.set_muted(True)
        assert vm.is_muted()
        vm.set_muted(False)
        assert not vm.is_muted()


class TestFightMarkersNoLeak:
    """Los marcadores de combate no deben sobrevivir a un cambio de video.

    Regresion observada en produccion: tras anotar un combate y abrir el
    siguiente video, la sesion del nuevo se guardaba con los marcadores del
    anterior, falseando duracion del combate, tiempo activo y fase.
    """

    def test_load_clears_previous_fight_markers(self, vm, video_file):
        vm.fight_start, vm.fight_end = 120, 900
        assert vm.load(video_file)
        assert vm.fight_start is None
        assert vm.fight_end is None

    def test_load_clears_annotation_markers_too(self, vm, video_file):
        vm.ann_start, vm.ann_end = 10, 20
        assert vm.load(video_file)
        assert vm.ann_start is None
        assert vm.ann_end is None
