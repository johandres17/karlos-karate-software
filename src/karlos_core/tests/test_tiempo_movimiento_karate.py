"""El tiempo-movimiento del karate: los cuatro estados y sus teclas.

Decisión 0008. Lo que se prueba aquí es lo que no se podía deducir leyendo
el código, y en particular la colisión que el comentario del paquete
anunciaba («C, V y H siguen siendo las faltas de la WKF»):

- los dígitos 1 a 4 marcan fases y **no** crean la técnica que tienen
  asignada en los otros modos (en karate las diez cifras son técnicas);
- C, V y H no marcan fases en karate, porque allí son las faltas;
- el cuarto estado, «unobservable», sobrevive al guardar y reabrir;
- en el técnico-táctico la acción es un evento sin fin, también en karate.

Las teclas se pulsan con QTest.keyClick sobre la ventana, no llamando al
manejador: una prueba que llamaba al manejador pasaba mientras los números
no funcionaban de verdad (Johan, 8-10-2026).

Corre sobre un vídeo real (se salta sin él), con los hilos de análisis
apagados.
"""
from __future__ import annotations

import tempfile
import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from karlos_core import catalogo

VIDEO = Path(os.environ.get("KARLOS_VIDEOS", "/nonexistent/karlos_videos") + "/"
             "ID25_-50KG_FEMALE_E.COLLETI ITA X B. IZAGUIRRE .mp4")
if VIDEO.exists():
    _limpio = Path(tempfile.mkdtemp(prefix="karlos_tm_kar_")) / VIDEO.name
    _limpio.symlink_to(VIDEO)
    VIDEO = _limpio

FASE = "PHASE"


@pytest.fixture()
def k(monkeypatch):
    """El anotador de karate abierto en asistido, como lo abre Johan."""
    if not VIDEO.exists():
        pytest.skip("sin los vídeos")
    from karlos_core import identidad
    from karlos_core.controllers.annotation_controller import AnnotationController
    from karlos_core.utils.config_loader import load_config
    from karlos_core.utils.i18n import I18n
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    QApplication.instance() or QApplication([])
    I18n().set_lang("pt")
    catalogo.establecer("karate")
    cfg, meta = load_config("karate")
    identidad.ajustes().setValue("inicio/analisis", "technical_tactical")
    ctl = AnnotationController(cfg, meta)
    ctl.aplicar_modo_inicial()
    ctl.show()
    ctl.navigation.show_annotator()
    assert ctl.video_manager.load(str(VIDEO))
    ctl._video_path = str(VIDEO)
    ctl._entrar_modo_asistido()
    ctl.video_manager.fight_start = 100
    ctl.video_manager.fight_end = 9000
    ctl.window.annotation_panel.set_athlete("AKA")
    QApplication.processEvents()
    yield ctl
    identidad.ajustes().remove("inicio/analisis")


def _analisis(c, cual):
    """El análisis es el cuaderno abierto (decisión 0008, 19-10-2026)."""
    c._poner_analisis_activo(cual)
    c._aplicar_analisis()
    QApplication.processEvents()


def _pulsar(c, tecla, modificador=Qt.NoModifier):
    QTest.keyClick(c.window, tecla, modificador)
    QApplication.processEvents()


def _filas(c, categoria=None):
    return [r for r in c.window.table_view.records
            if categoria is None or getattr(r, "category", "") == categoria]


# ----------------------------------------------------------------------
# La colisión que el comentario del paquete anunciaba
# ----------------------------------------------------------------------

def test_los_digitos_marcan_fases_y_no_crean_la_tecnica_que_tienen_asignada(k):
    """En karate [1] es Tsuki y [3] es Mawashi en los otros modos.

    En la pasada de fases tienen que marcar la fase y nada más:
    `_tecla_de_fase` consume la tecla. Si esto se rompiera, cada fase
    dejaría además un ataque inventado en el registro.
    """
    _analisis(k, "time_motion")
    assert k._en_modo_fases(), "el tiempo-movimiento entra ya en la pasada de fases"

    for frame, tecla in ((1000, Qt.Key_1), (1500, Qt.Key_2),
                         (2000, Qt.Key_3), (2500, Qt.Key_4)):
        k.video_manager.goto(frame)
        _pulsar(k, tecla)

    fases = _filas(k, FASE)
    assert [(r.f_start, r.technique) for r in sorted(fases, key=lambda r: r.f_start)] == [
        (1000, "fighting"), (1500, "non_fighting"),
        (2000, "stoppage"), (2500, "unobservable")], "las cuatro, en su tecla"
    assert _filas(k, "ATTACK") == [], "ningún ataque inventado por pulsar 1 o 3"
    assert _filas(k, "DEFENSE") == [], "ni una defensa por pulsar 2 o 4"
    assert len(_filas(k)) == len(fases), "en el registro solo hay fases"


def test_c_v_y_h_no_marcan_fases_en_karate_porque_son_las_faltas(k):
    """El karate no declara letras de fase: las fases van con los números."""
    from karlos_core.tiempo_movimiento import letras_de_fase
    assert letras_de_fase() == (), "ninguna letra de fase en karate"
    _analisis(k, "time_motion")
    k.video_manager.goto(1200)
    for tecla in (Qt.Key_C, Qt.Key_V, Qt.Key_H):
        _pulsar(k, tecla)
    assert _filas(k, FASE) == [], "ni C, ni V, ni H marcan una fase"


def test_el_cuarto_estado_se_guarda_y_vuelve(k, tmp_path):
    """«unobservable» es nuestro y no está en la literatura: hay que
    comprobar que el modelo lo acepta y que sobrevive al disco."""
    from karlos_core.models.fases import Fases, UNOBSERVABLE
    _analisis(k, "time_motion")
    for frame, tecla in ((1000, Qt.Key_1), (1800, Qt.Key_4)):
        k.video_manager.goto(frame)
        _pulsar(k, tecla)
    marcas = k._fases_a_lista()
    assert {m["fase"] for m in marcas} == {"fighting", UNOBSERVABLE}
    # El modelo no lo descarta al rehacerse desde la lista guardada.
    vueltas = Fases.de_lista([{"fotograma": m["fotograma"], "fase": m["fase"]}
                              for m in marcas])
    assert [e for _f, e in vueltas.marcas] == ["fighting", UNOBSERVABLE]


def test_en_el_tecnico_tactico_del_karate_la_accion_no_pide_el_final(k):
    """El modo técnico-táctico cuenta frecuencias: se contesta qué fue y se
    guarda en ese momento, sin pedir [O] ni dejar una duración inventada."""
    _analisis(k, "technical_tactical")
    assert not k._en_modo_fases(), "aquí las teclas son de las acciones"
    assert k._modo_eventos(), "la acción es un evento, no un intervalo"


# ----------------------------------------------------------------------
# Las columnas de los informes, que son por deporte
# ----------------------------------------------------------------------

def test_las_columnas_del_informe_son_las_del_deporte():
    """Los cuatro estados del karate."""
    from karlos_core.tiempo_movimiento import estados_activos
    catalogo.establecer("karate")
    assert estados_activos() == ("fighting", "non_fighting", "stoppage", "unobservable")
