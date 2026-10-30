"""Una accion contestada que espera su [O] no se pierde sin avisar.

Johan lo vio con dos faltas (28-09): anoto un contacto excesivo y
despues otra falta, y en los cuadros de abajo solo salio una. El
contacto excesivo va dentro del ataque que lo provoca, y el ataque
necesita su final; la otra falta (pasividad, jogai...) es un suceso y se
guarda al contestar. Si se pasaba a la segunda con [I] sin haber
cerrado la primera con [O], la [I] tiraba el ataque con su falta sin
decir nada. No era la cuenta: la primera falta nunca llego a guardarse.

Corre sobre un video real (se salta sin el), con los hilos de analisis
apagados y las preguntas contestadas por el test.
"""

from __future__ import annotations

import tempfile
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

VIDEO = Path(os.environ.get("KARLOS_VIDEOS", "/nonexistent/karlos_videos") + "/"
             "ID25_-50KG_FEMALE_E.COLLETI ITA X B. IZAGUIRRE .mp4")
if VIDEO.exists():
    _limpio = Path(tempfile.mkdtemp(prefix="karlos_sin_fin_")) / VIDEO.name
    _limpio.symlink_to(VIDEO)
    VIDEO = _limpio

CONTACTO = ["ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Foul", "S:Contact"]


@pytest.fixture()
def c(monkeypatch):
    if not VIDEO.exists():
        pytest.skip("sin los vídeos")
    from karlos_core.controllers.annotation_controller import AnnotationController
    from karlos_core.utils.config_loader import load_config
    from karlos_core.utils.i18n import I18n
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    QApplication.instance() or QApplication([])
    I18n().set_lang("pt")
    cfg, meta = load_config("karate")
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
    assert ctl._en_modo_pro()
    return ctl


def _contestar(c, claves):
    for clave in claves:
        c._guia_elegir(clave)
    QApplication.processEvents()


def _cuadros(c):
    c._update_live_stats()
    cf = c.window.video_panel.contador_faltas
    return cf._aka, cf._ao


def test_una_i_nueva_avisa_en_vez_de_tirar_la_accion(c):
    c.video_manager.goto(1000)
    c._marcar_inicio()
    _contestar(c, CONTACTO)
    assert c._arbol_listo is not None
    assert c.window.guided_panel.isVisible(), "lo pendiente tiene que verse"

    c.video_manager.goto(2000)
    c._marcar_inicio()
    assert c._arbol_listo is not None, "la [I] tiro la accion contestada"
    assert c.window.guided_panel._aviso.isVisible()


def test_con_el_o_se_guarda_con_su_falta_y_los_cuadros_suman(c):
    """El caso de Johan: contacto excesivo, y despues una falta sin contacto."""
    c.video_manager.goto(1000)
    c._marcar_inicio()
    _contestar(c, CONTACTO)
    c.video_manager.goto(2000)
    c._marcar_inicio()                       # avisa: aun no tiene fin
    c.video_manager.goto(1030)
    c._marcar_fin()                          # se cierra donde toca
    assert _cuadros(c) == (1, 0)

    c.video_manager.goto(2000)
    c._marcar_inicio()
    _contestar(c, ["falta", "F:Jogai"])
    assert _cuadros(c) == (2, 0)
    penal = [r for r in c.window.table_view.records if r.category == "PENALTY"]
    assert [r.technique for r in penal] == ["CHUI-2"]


def test_repetir_la_i_descarta_a_sabiendas(c):
    c.video_manager.goto(1000)
    c._marcar_inicio()
    _contestar(c, CONTACTO)
    c.video_manager.goto(1500)
    c._marcar_inicio()
    c._marcar_inicio()
    assert c._arbol_listo is None
    assert c._arbol is not None and c.state_machine.f_start == 1500
    assert c.window.table_view.records == []


def test_tab_pasa_por_el_mismo_aviso(c):
    c.video_manager.goto(1000)
    c._marcar_inicio()
    _contestar(c, ["ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:NoScore"])
    c._tab_accion(1)
    assert c._arbol_listo is not None
    c._tab_accion(1)
    assert c._arbol_listo is None

