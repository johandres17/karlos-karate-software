"""La pantalla de inicio (decisión 0006, F5.3d).

Karlos Karate solo anota karate: no se pregunta el deporte. Se arranca en
una sola pantalla, «¿Qué se analiza?», con el nombre y la versión del
programa, el reglamento y el idioma.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel

from karlos_core import identidad
from karlos_core.utils import recientes
from karlos_core.utils.config_loader import load_config
from karlos_core.utils.i18n import I18n


@pytest.fixture(autouse=True)
def qt():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])


def _inicio():
    from karlos_core.views.dialogo_analisis import DialogoAnalisis
    cfg, _ = load_config("karate")
    return DialogoAnalisis(cfg.colors)


def test_no_se_pregunta_el_deporte():
    from karlos_core import main
    assert main.deporte_de_arranque() == "karate"


# ----------------------------------------------------------------------
# El programa que se abre
# ----------------------------------------------------------------------

class TestElPrograma:
    def test_la_pantalla_dice_su_nombre_su_version_y_su_reglamento(self):
        d = _inicio()
        assert d.windowTitle() == "Karlos Karate"
        assert "KARATE" in d._nombre.text()
        assert identidad.en_marcha().version in d._linea_deporte.text()
        assert "WKF 2026" in d._linea_deporte.text()

    def test_la_cabecera_del_anotador_dice_el_nombre_de_la_edicion(self):
        from karlos_core.views.main_window import MainWindow
        cfg, meta = load_config("karate")
        w = MainWindow(cfg, meta)
        titulo = w._title_lbl.text()
        assert "KARATE" in titulo and "ANNOTATOR" not in titulo
        assert "WKF 2026" in w._subtitle_lbl.text()
        w.set_pro_branding(True)
        assert "KARATE" in w._title_lbl.text() and "ASSISTIDO" in w._title_lbl.text()
        w.set_pro_branding(False)
        assert w._title_lbl.text() == titulo
        w.close()

    def test_la_cabecera_del_hub_dice_el_nombre_de_la_edicion(self):
        from karlos_core.views.project_hub import ProjectHubView
        cfg, meta = load_config("karate")
        h = ProjectHubView(cfg.colors, meta)
        assert h._title_label.text() == "KARLOS KARATE"
        h._refresh_strings()
        assert h._title_label.text() == "KARLOS KARATE"

    def test_el_hub_dice_el_analisis_y_que_el_integrado_es_asistido(self):
        from karlos_core.views.project_hub import ProjectHubView
        cfg, meta = load_config("karate")
        h = ProjectHubView(cfg.colors, meta)
        h.set_analisis("complete")
        assert h._etiqueta_analisis.text() == f"{I18n().t('analisis.completo').upper()}  ·  {I18n().t('pro.assistido')}"
        h.set_analisis("time_motion")
        assert h._etiqueta_analisis.text() == I18n().t("analisis.tm").upper()


# ----------------------------------------------------------------------
# El idioma
# ----------------------------------------------------------------------

class TestElIdioma:
    @pytest.fixture(autouse=True)
    def volver_al_portugues(self):
        yield
        I18n().set_lang("pt")

    def test_cambiarlo_lo_traduce_todo_al_momento(self):
        d = _inicio()
        d._idioma.setCurrentIndex(d._idioma.findData("en"))
        assert I18n().lang == "en"
        assert d._pregunta.text() == "What do you analyse?"
        assert d._tarjetas["complete"].titulo.text() == "Integrated"

    @pytest.mark.parametrize("idioma", list(I18n.LANGS))
    def test_no_queda_ninguna_clave_sin_traducir(self, idioma):
        d = _inicio()
        d._idioma.setCurrentIndex(d._idioma.findData(idioma))
        for w in d.findChildren(QLabel) + [d._entrar, d._volver]:
            assert "analisis." not in w.text() and "deporte." not in w.text(), (idioma, w.text())
        d.grab()

    def test_la_primera_vez_es_el_del_sistema(self, monkeypatch):
        from karlos_core.utils import i18n
        QSettings("Karlitos", "KarlosKarate").remove("i18n/language")
        monkeypatch.setattr(i18n, "idioma_del_sistema", lambda local=None: "fr")
        monkeypatch.setattr(I18n, "_instance", None)
        assert I18n().lang == "fr"

    def test_el_del_sistema_si_el_programa_lo_habla_y_si_no_ingles(self):
        from karlos_core.utils.i18n import idioma_del_sistema
        assert idioma_del_sistema("es_EC") == "es"
        assert idioma_del_sistema("pt_PT") == "pt"
        assert idioma_del_sistema("ja_JP") == "ja"
        assert idioma_del_sistema("de_DE") == "en"



# ----------------------------------------------------------------------
# Las carpetas recientes
# ----------------------------------------------------------------------

class _Ajustes:
    def __init__(self, valor):
        self._valor = valor

    def value(self, clave, defecto=None):
        return defecto if self._valor is None else self._valor


class TestLasCarpetasRecientes:
    def test_una_sola_apuntada_no_se_trocea_letra_a_letra(self):
        assert recientes.recientes(_Ajustes("/Users/x/ID30")) == ["/Users/x/ID30"]

    def test_sin_ninguna(self):
        assert recientes.recientes(_Ajustes(None)) == []
        assert recientes.carpeta_de_arranque(_Ajustes(None)) is None

    def test_el_anotador_abre_la_que_anuncia_el_inicio(self, tmp_path):
        from karlos_core.controllers.annotation_controller import AnnotationController
        con = tmp_path / "ID30"
        con.mkdir()
        (con / "a.mp4").write_bytes(b"")
        identidad.ajustes().setValue(recientes.CLAVE, [str(tmp_path / "no"), str(con)])
        c = AnnotationController.__new__(AnnotationController)
        abiertas = []
        c._load_sessions_from_folder = abiertas.append
        c.window = type("W", (), {"set_status_message": lambda self, m: None})()
        c._auto_load_recent_folder()
        assert abiertas == [str(con)] == [recientes.carpeta_de_arranque(identidad.ajustes())]
