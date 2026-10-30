"""Las reglas del libro de codigos, aplicadas de verdad al anotar.

test_regras prueba las funciones puras; esto prueba que el flujo las
consulta en el momento correcto y reacciona como se prometio: sin
crear la fila, alargando la anterior, o ajustando la parada. Corre
sobre un video real (se salta sin el), con los hilos de analisis
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
    _limpio = Path(tempfile.mkdtemp(prefix="karlos_reglas_")) / VIDEO.name
    _limpio.symlink_to(VIDEO)
    VIDEO = _limpio


def _anotador():
    from karlos_core.controllers.annotation_controller import AnnotationController
    from karlos_core.utils.config_loader import load_config
    from karlos_core.utils.i18n import I18n
    QApplication.instance() or QApplication([])
    I18n().set_lang("pt")
    cfg, meta = load_config("karate")
    c = AnnotationController(cfg, meta)
    c.aplicar_modo_inicial()          # modo manual: [I], boton, [O]
    c.show()
    c.navigation.show_annotator()
    QApplication.processEvents()
    if not VIDEO.exists():
        pytest.skip("sin los vídeos")
    assert c.video_manager.load(str(VIDEO))
    c.video_manager.fight_start = 100
    c.video_manager.fight_end = 9000
    return c


def _fila(atleta, categoria, tecnica, f0, f1, nivel=""):
    from karlos_core.models.annotation import Annotation
    return Annotation(athlete=atleta, category=categoria, subcategory="",
                      technique=tecnica, level=nivel, score="",
                      f_start=f0, f_end=f1, duration_s=(f1 - f0) / 30.0, round=1)


def _tecnica(c, nombre):
    """El objeto Technique del config, por nombre."""
    for cat in c._config.categories:
        for t in cat.techniques:
            if t.name == nombre:
                return t, cat
    raise KeyError(nombre)


def _anotar(c, atleta, nombre, f0, f1, nivel=""):
    """[I] en f0, elegir la tecnica, [O] en f1 — por la maquina de estados."""
    c.window.annotation_panel.set_athlete(atleta)
    c.video_manager.goto(f0)
    c.flow_controller.on_mark_start()
    tec, cat = _tecnica(c, nombre)
    c.flow_controller._last_technique = tec
    c.state_machine.select_technique(nombre, nivel, "NONE", tec.group, tec.category)
    c.video_manager.goto(f1)
    c.flow_controller.on_mark_end()
    QApplication.processEvents()


def _si(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))


def test_dentro_de_una_parada_tambien_se_anota(monkeypatch):
    """Antes se rechazaba. El programa ya no decide qué se anota.

    Si una acción cae dentro de una parada, eso se ve en el propio
    registro, que lleva los frames de las dos: filtrarlo es del
    tratamiento de datos.
    """
    c = _anotador()
    c.window.table_view.add_annotation(_fila("AKA", "REFEREE STOP", "Referee", 1000, 1500))
    antes = len(c.window.table_view.records)
    _anotar(c, "AO", "Feint", 1200, 1230, "Lower Limb")
    assert len(c.window.table_view.records) == antes + 1


def test_ninguna_regla_mira_lo_que_hay_alrededor():
    """Ninguna decisión depende ya de otras filas ni del reloj."""
    from karlos_core.models import regras
    for retirada in ("prohibida_en_pausa", "parada_que_contiene",
                     "ataque_rival_reciente", "parada_solapada",
                     "finta_a_extender", "finta_corta"):
        assert not hasattr(regras, retirada), retirada


def test_dos_fintas_seguidas_son_dos_filas(monkeypatch):
    """Antes la segunda alargaba la primera y salían en una sola fila.

    Retirado el 24-09-2026: cada registro tiene su propia línea y las
    tandas se agrupan en el procesamiento de datos, donde el criterio se
    puede cambiar sin volver a ver los combates.
    """
    _si(monkeypatch)
    c = _anotador()
    _anotar(c, "AKA", "Feint", 2000, 2020, "Lower Limb")
    _anotar(c, "AKA", "Feint", 2030, 2050, "Lower Limb")
    fintas = [a for a in c.window.table_view.records if a.technique == "Feint"]
    assert len(fintas) == 2, "cada finta es una fila, también en la misma tanda"
    assert [(f.f_start, f.f_end) for f in fintas] == [(2000, 2020), (2030, 2050)]


def test_dos_fintas_pegadas_tampoco_se_juntan(monkeypatch):
    """Ni siquiera cuando una empieza en el fotograma siguiente."""
    _si(monkeypatch)
    c = _anotador()
    _anotar(c, "AKA", "Feint", 2000, 2020, "Lower Limb")
    _anotar(c, "AKA", "Feint", 2021, 2040, "Lower Limb")
    assert sum(1 for a in c.window.table_view.records if a.technique == "Feint") == 2


def test_otro_miembro_es_otra_fila(monkeypatch):
    _si(monkeypatch)
    c = _anotador()
    _anotar(c, "AKA", "Feint", 2000, 2020, "Lower Limb")
    _anotar(c, "AKA", "Feint", 2030, 2050, "Upper Limb")
    assert sum(1 for a in c.window.table_view.records if a.technique == "Feint") == 2


def test_una_finta_corta_se_anota_sin_preguntar_nada(monkeypatch):
    """El cuadro de «finta muito curta» cortaba el trabajo.

    Si algo lo abriera otra vez, esta respuesta automática diría que no
    y la finta no se crearía: el test falla justo en ese caso.
    """
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    c = _anotador()
    _anotar(c, "AKA", "Feint", 2000, 2004, "Lower Limb")
    fintas = [a for a in c.window.table_view.records if a.technique == "Feint"]
    assert len(fintas) == 1, "una finta de 4 fotogramas se anota igual"
    assert (fintas[0].f_start, fintas[0].f_end) == (2000, 2004)


def test_un_esquive_sin_ataque_delante_se_anota_sin_preguntar(monkeypatch):
    """Preguntaba si no había ataque del rival en el segundo anterior.

    Era otra regla de tiempo y otra interrupción. Si el cuadro volviera,
    esta caja falsa contestaría «Não anotar» y el test fallaría.
    """
    c = _anotador()
    preguntas = []

    class _Caja:
        def __init__(self, *a, **k): self._botones = []
        def setWindowTitle(self, t): preguntas.append(t)
        def setText(self, t): pass
        def addButton(self, texto, rol): self._botones.append(texto); return texto
        def exec(self): pass
        def clickedButton(self): return self._botones[-1]
    from karlos_core.controllers import annotation_flow_controller as afc
    monkeypatch.setattr(afc, "QMessageBox", type("QMB", (), {
        "__new__": lambda cls, *a, **k: _Caja(),
        "ButtonRole": QMessageBox.ButtonRole,
        "StandardButton": QMessageBox.StandardButton,
        "question": staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
        "warning": staticmethod(lambda *a, **k: None)}))
    _anotar(c, "AO", "Dodge", 3000, 3010)
    assert preguntas == []
    assert sum(1 for a in c.window.table_view.records
               if a.technique == "Dodge") == 1


def test_un_esquive_con_ataque_delante_no_pregunta(monkeypatch):
    c = _anotador()
    c.window.table_view.add_annotation(_fila("AKA", "ATTACK", "Gyaku Tsuki", 2990, 3000))
    _anotar(c, "AO", "Dodge", 3005, 3015)
    assert any(a.technique == "Dodge" for a in c.window.table_view.records)
