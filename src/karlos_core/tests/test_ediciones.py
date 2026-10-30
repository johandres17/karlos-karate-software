"""La edición: Karlos Karate es un programa (fase F5, decisión 0006).

El núcleo no registra deportes por su cuenta: los pone la edición que
arranca. Karlos Karate trae el karate.
"""
from __future__ import annotations

import pytest

from karlos_core import catalogo, identidad
from karlos_core.catalogo import Catalogo
from karlos_ediciones import karate


def test_la_suite_corre_con_karlos_karate():
    assert identidad.en_marcha() is karate.EDICION
    assert catalogo.registrados() == ("karate",)


def test_karlos_karate_trae_solo_el_karate():
    c = Catalogo()
    karate.EDICION.registrar_en(c)
    assert c.registrados() == ("karate",)
    assert c.activo().edicion == "Karlos Karate"


def test_poner_la_misma_edicion_otra_vez_no_hace_nada():
    karate.poner_en_marcha()
    assert catalogo.registrados() == ("karate",)


def test_un_programa_es_una_sola_edicion():
    from dataclasses import replace
    otra = replace(karate.EDICION, nombre="Otra")
    with pytest.raises(RuntimeError, match="una sola edición"):
        identidad.poner_en_marcha(otra)
    assert identidad.en_marcha() is karate.EDICION, "no cambia nada"


def test_sin_edicion_el_programa_no_arranca(monkeypatch, capsys):
    from karlos_core import main as M
    monkeypatch.setattr(identidad, "_en_marcha", None)
    with pytest.raises(SystemExit) as fin:
        M.main()
    assert fin.value.code == 2
    assert "karlos_ediciones" in capsys.readouterr().err


def test_la_identidad_de_karlos_karate():
    from pathlib import Path
    k = karate.EDICION
    assert (k.nombre, k.version, k.identificador) == ("Karlos Karate", "1.2.0", "com.karlitos.karate")
    assert k.ajustes == ("Karlitos", "KarlosKarate")
    assert k.carpeta == Path.home() / ".karlos_karate"


def test_los_ajustes_son_los_de_la_edicion_en_marcha():
    assert identidad.ajustes().fileName().endswith("Karlitos__KarlosKarate.ini")


def test_el_titulo_de_la_ventana_es_el_de_la_edicion():
    from PySide6.QtWidgets import QApplication

    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.main_window import MainWindow
    QApplication.instance() or QApplication([])
    cfg, meta = load_config("karate")
    w = MainWindow(cfg, meta)
    assert w.windowTitle() == "Karlos Karate v1.2.0"
    w.close()


def test_el_pdf_lleva_el_nombre_y_la_version_de_la_edicion():
    from karlos_karate.pdf_report_generator import _programa
    assert _programa() == ("KARLOS KARATE", "1.2.0")


def test_poner_karlos_karate_en_marcha(tmp_path, monkeypatch):
    """De una vez: su deporte y su carpeta para el log y las pasadas."""
    from dataclasses import replace

    from karlos_core.controllers.session_manager import SessionManager
    from karlos_core.utils import app_logging
    for objeto, nombre in ((app_logging, "LOG_DIR"), (app_logging, "LOG_FILE"),
                           (SessionManager, "_GLOBAL_ROUNDS_DIR"),
                           (SessionManager, "_GLOBAL_ROUNDS_PATH")):
        monkeypatch.setattr(objeto, nombre, getattr(objeto, nombre))
    ed = replace(karate.EDICION, carpeta=tmp_path / "karlos_karate")
    nuevo_catalogo = Catalogo()
    monkeypatch.setattr(identidad, "CATALOGO", nuevo_catalogo)
    monkeypatch.setattr(identidad, "_en_marcha", None)
    identidad.poner_en_marcha(ed)
    assert identidad.en_marcha() is ed and nuevo_catalogo.registrados() == ("karate",)
    carpeta = tmp_path / "karlos_karate"
    assert app_logging.LOG_DIR == carpeta / "logs"
    assert app_logging.LOG_FILE == carpeta / "logs" / "karlos.log"
    assert SessionManager._GLOBAL_ROUNDS_PATH == carpeta / "rounds.json"


def test_el_hub_no_ofrece_cambiar_de_deporte():
    from PySide6.QtWidgets import QApplication

    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.main_window import MainWindow
    QApplication.instance() or QApplication([])
    cfg, meta = load_config("karate")
    w = MainWindow(cfg, meta)
    assert not hasattr(w.project_hub, "_change_sport_btn")
    w.close()


def test_los_specs_empaquetan_karlos_karate_con_su_identidad():
    """El nombre, la versión y el identificador salen de la edición, no del
    spec."""
    from pathlib import Path
    src = Path(__file__).resolve().parents[2]
    for nombre in ("karlos_karate_macos.spec", "karlos_karate_windows.spec"):
        texto = (src / nombre).read_text(encoding="utf-8")
        assert "from karlos_ediciones.karate import EDICION" in texto, nombre
        assert "arrancar_karlos_karate.py" in texto and "Karlos Annotator" not in texto, nombre
    assert "bundle_identifier=EDICION.identificador" in (src / "karlos_karate_macos.spec").read_text(encoding="utf-8")
