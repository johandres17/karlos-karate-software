"""La navegación del vídeo: que sea rápida y que no mienta.

`cap.set()` obliga a decodificar desde el fotograma clave anterior.
Medido sobre un combate de 1080p: 80 ms para avanzar UNO, frente a
0,7 ms leyendo seguido. Como el 90% del trabajo de anotar es mover el
vídeo, ese era el cuello de botella de todo el programa.

Ahora se avanza con `grab()` cuando el salto es corto y se guardan los
fotogramas recientes. Eso mete un riesgo nuevo que estos tests vigilan:
si alguien mueve el cabezal por detrás sin decirlo, `grab()` avanza
desde donde no toca y se enseña OTRO fotograma sin avisar. Lento se
nota; equivocado, no.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

VIDEOS = Path(os.environ.get("KARLOS_VIDEOS", "/nonexistent/karlos_videos") + "/")
VIDEO = VIDEOS / "ID30_-75KG_MALE_ASSEMAT X DUARTE POR.mp4"


@pytest.fixture(scope="module")
def vm():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    if not VIDEO.exists():
        pytest.skip("sin los vídeos")
    from karlos_core.utils.config_loader import load_config
    from karlos_core.controllers.video_manager import VideoManager
    cfg, _ = load_config("karate")
    v = VideoManager(cfg.video)
    assert v.load(str(VIDEO))
    yield v
    v.release()


def _verdad(idx: int):
    """El fotograma idx leído desde cero, sin trucos."""
    import cv2
    cap = cv2.VideoCapture(str(VIDEO))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = cap.read()
    cap.release()
    assert ok
    return f


def _igual(a, b) -> bool:
    return a is not None and b is not None and np.array_equal(a, b)


# ── lo que se enseña es lo que se pide ──────────────────────────────

@pytest.mark.parametrize("camino", ["adelante", "atras", "salto", "vaiven"])
def test_el_fotograma_que_sale_es_el_que_se_pidio(vm, camino):
    vm.goto(4000)
    if camino == "adelante":
        for _ in range(5):
            vm.step(1)
    elif camino == "atras":
        for _ in range(5):
            vm.step(-1)
    elif camino == "salto":
        vm.goto(9000); vm.goto(1200); vm.goto(7777)
    else:
        for d in (1, 1, -1, 1, -1, -1, 1):
            vm.step(d)
    assert _igual(vm.current_bgr, _verdad(vm.current_frame)), (
        f"tras «{camino}» dice estar en f{vm.current_frame} y enseña otro")


def test_get_frames_no_descoloca_el_cabezal(vm):
    """Movia el cap y no lo decia: despues se enseñaba otro fotograma."""
    vm.goto(5000)
    vm.ann_start, vm.ann_end = 2000, 2010
    vm.get_frames()
    vm.goto(5000)
    vm.step(1)
    assert _igual(vm.current_bgr, _verdad(vm.current_frame))
    vm.ann_start = vm.ann_end = None


def test_reproducir_y_luego_avanzar_a_mano(vm):
    """La reproduccion tambien mueve el cabezal."""
    vm.goto(3000)
    vm.toggle_play()
    for _ in range(4):
        vm._advance()
    vm.toggle_play()
    vm.step(1)
    assert _igual(vm.current_bgr, _verdad(vm.current_frame))


def test_abrir_otro_video_no_deja_fotogramas_del_anterior(vm):
    """Lo grave no seria guardar de mas: seria enseñar el vídeo de antes."""
    import cv2
    otros = [p for p in VIDEOS.glob("*.mp4") if p != VIDEO]
    if not otros:
        pytest.skip("hace falta un segundo vídeo")
    vm.goto(3000)
    for _ in range(5):
        vm.step(1)
    guardados_antes = set(vm._cache)
    assert guardados_antes

    otro = otros[0]
    assert vm.load(str(otro))
    # De lo anterior no puede quedar nada mas que lo que el propio
    # arranque vuelve a leer del vídeo nuevo.
    assert set(vm._cache) <= {0}

    cap = cv2.VideoCapture(str(otro))
    ok, cero = cap.read()
    cap.release()
    assert ok and _igual(vm.current_bgr, cero), "enseña el vídeo anterior"

    vm.load(str(VIDEO))


# ── y que de verdad sea rapido ──────────────────────────────────────

def test_avanzar_un_fotograma_ya_no_cuesta_una_busqueda(vm):
    """Si esto se rompe, vuelven los 80 ms por flecha."""
    import time
    vm.goto(3000)
    vm.step(1)                                   # calienta
    t = []
    for _ in range(20):
        a = time.perf_counter(); vm.step(1); t.append(time.perf_counter() - a)
    mediana = sorted(t)[len(t) // 2] * 1000
    assert mediana < 15, f"{mediana:.1f} ms por fotograma: se resembró el decodificador"


def test_volver_sobre_lo_andado_sale_de_la_memoria(vm):
    """Ajustar un limite es ir y volver sobre los mismos fotogramas."""
    import time
    vm.goto(7000)
    for _ in range(6):
        vm.step(1)
    a = time.perf_counter()
    for _ in range(6):
        vm.step(-1)
    ms = (time.perf_counter() - a) * 1000
    assert ms < 30, f"{ms:.1f} ms para volver seis: no se estan guardando"


def test_la_memoria_tiene_techo(vm):
    vm.goto(1000)
    for i in range(200):
        vm.goto(1000 + i)
    assert vm._cache_bytes <= vm._CACHE_MAX_BYTES


# ── el arrastre de la lupa solo atiende la ultima posicion ──────────

def test_arrastrar_no_encola_una_busqueda_por_cada_posicion(vm):
    from PySide6.QtWidgets import QApplication
    vm.goto(2000)
    for destino in range(6000, 6400, 20):        # como mover el raton
        vm.arrastrar(destino)
    assert vm.current_frame == 2000, "no debería moverse hasta que pare"
    import time
    fin = time.time() + 2
    while vm.current_frame == 2000 and time.time() < fin:
        QApplication.processEvents(); time.sleep(0.01)
    assert vm.current_frame == 6380, "tiene que ir a la ÚLTIMA posición pedida"
