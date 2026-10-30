"""Las pasadas son de cada combate, y [F] no empieza la segunda por error.

Johan, 28-09: al marcar el inicio de un combate con [F] le salio «Na
pasada de AO há 34 momentos com movimento e sem anotação. Rever agora,
antes de começar o outro atleta?». Nada que ver con lo que hacia. Tres
fallos juntos:

1. `restore_pass` daba la primera pasada por terminada con solo haberla
   empezado (`>= 1`), asi que al reabrir el combate la [F] abria la
   segunda.
2. El estado vivia en el controlador, uno para toda la sesion de
   trabajo: el siguiente video heredaba las pasadas del anterior.
3. Borrar las anotaciones no devolvia el combate a la primera pasada.

Y aparte, la linea verde del inicio no salia hasta marcar tambien el
final: sin final se borraban las dos, en cada fotograma.
"""

from __future__ import annotations

import json

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    yield QApplication.instance() or QApplication([])


class _Video:
    is_loaded = True
    fps = 30.0

    def __init__(self):
        self.fight_start = None
        self.fight_end = None
        self.current_frame = 300

    def set_fight_start(self):
        self.fight_start = self.current_frame


class _Panel:
    def __init__(self):
        self.pase = None

    def set_pass_label(self, n, atleta):
        self.pase = (n, atleta)

    def update_fight_label(self, *a):
        pass


class _Atletas:
    athlete = "AKA"

    def lock_athlete(self, bloqueado):
        self.bloqueado = bloqueado


class _Tabla:
    records: list = []


def _controlador():
    from karlos_core.controllers.fight_session_controller import (
        FightSessionController,
    )
    fc = FightSessionController(_Video(), _Panel(), _Atletas(), _Tabla(), {})
    emitidas = []
    fc.pass_changed.connect(lambda n, a: emitidas.append(n))
    return fc, emitidas


def test_una_sesion_a_medias_de_la_primera_no_la_da_por_terminada():
    fc, emitidas = _controlador()
    fc.restore_pass(1)
    fc.on_fight_start()
    assert fc.current_pass == 1
    assert 2 not in emitidas, "la [F] empezo la segunda pasada"


def test_la_segunda_pasada_si_se_repone():
    fc, _ = _controlador()
    fc.restore_pass(2)
    assert fc.current_pass == 2 and fc.is_two_pass_complete


def test_volver_a_pulsar_f_no_repite_el_aviso():
    """Corregir el inicio no es empezar otro atleta."""
    fc, emitidas = _controlador()
    fc.on_fight_start()
    fc.on_analyze_other_athlete()
    fc.on_fight_start()
    fc.on_fight_start()
    assert emitidas.count(2) == 1


def test_cada_combate_empieza_sin_pasadas():
    fc, emitidas = _controlador()
    fc.restore_pass(2)
    fc.reiniciar()
    assert fc.current_pass == 0 and not fc.is_two_pass_complete
    fc.on_fight_start()
    assert fc.current_pass == 1 and 2 not in emitidas


def test_borrar_las_anotaciones_vuelve_a_la_primera_pasada(tmp_path, monkeypatch):
    from karlos_core.controllers.session_manager import SessionManager
    ruta = tmp_path / "COMBATE__johan__1.karlos"
    ruta.write_text(json.dumps({
        "version": "1.0", "current_pass": 2, "current_athlete": "AO",
        "annotations": [{"category": "ATTACK", "technique": "Gyaku Tsuki",
                         "subcategory": "", "athlete": "AO"}]}),
        encoding="utf-8")
    monkeypatch.setattr(SessionManager, "ruta_de_sesion",
                        staticmethod(lambda video: ruta))
    assert SessionManager.borrar_anotaciones(str(tmp_path / "COMBATE.mp4")) == 1
    assert json.loads(ruta.read_text(encoding="utf-8"))["current_pass"] == 0


def test_la_linea_verde_sale_con_solo_el_inicio():
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.video_panel import VideoPanelView
    cfg, _ = load_config("karate")
    vp = VideoPanelView(cfg.colors, cfg.video)
    vp.update_fight_label(1522, None, 30.0)
    assert vp.timeline._fight_start == 1522
    assert vp.timeline._fight_end is None
    vp.update_fight_label(1522, 9000, 30.0)
    assert (vp.timeline._fight_start, vp.timeline._fight_end) == (1522, 9000)
