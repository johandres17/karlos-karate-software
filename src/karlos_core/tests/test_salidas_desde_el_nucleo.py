"""Lo que el núcleo hace con las salidas del deporte, fijado (fase F3.7).

Al partir el controlador, dos rutinas que calculan rutas a partir de su
propio fichero quedaron un nivel más hondas; estas pruebas fijan que
apuntan a lo mismo que antes, se lancen desde donde se lancen. Y el PDF:
lo que se le pasa sale del informe en pantalla.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

SRC = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def test_el_pdf_se_propone_en_src_exports_reports(monkeypatch):
    import os

    from PySide6.QtWidgets import QFileDialog

    from karlos_core.controllers.anotador.exportacion import ExportacionMixin
    creadas, propuesta = [], {}
    monkeypatch.setattr(os, "makedirs", lambda ruta, exist_ok=False: creadas.append(ruta))

    def elegir(parent, titulo, ruta, filtro):
        propuesta["ruta"] = ruta
        return "", ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(elegir))
    ExportacionMixin._on_export_pdf(SimpleNamespace(_bout_info={}, window=None))
    destino = SRC / "exports" / "reports"
    assert creadas == [str(destino)]
    assert Path(propuesta["ruta"]).parent == destino
    assert Path(propuesta["ruta"]).name.startswith("karlos_report_")


def test_el_pdf_lleva_lo_que_enseña_el_informe(tmp_path, monkeypatch):
    import os

    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from karlos_core.controllers.anotador.exportacion import ExportacionMixin
    from karlos_core.models.annotation import Annotation
    from karlos_core.models.state import FightSession
    from karlos_core.utils.config_loader import load_config
    from karlos_core import catalogo
    from karlos_karate.salidas import SalidasKarate

    cfg, meta = load_config("karate")
    informe = catalogo.activo().salidas().vista_informe(colors=cfg.colors, sport_meta=meta)
    sesion = FightSession(
        id=0, video_path="/v/ID99.mp4", fps=30.0, duration_s=180.0,
        bout_metadata={"athlete_a_name": "A. Uno", "athlete_b_name": "B. Dos"},
        annotations=[Annotation(athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
                                technique="Gyaku Tsuki", level="Chudan", score="YUKO",
                                f_start=100, f_end=120)])
    informe.set_session(sesion, cfg.colors)
    pedido, avisos = {}, []
    monkeypatch.setattr(os, "makedirs", lambda ruta, exist_ok=False: None)  # nada en el repo
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a: (str(tmp_path / "r.pdf"), "")))
    monkeypatch.setattr(SalidasKarate, "informe_pdf",
                        lambda self, **datos: pedido.update(datos) or datos["output_path"])
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a: avisos.append(a[1])))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a: avisos.append(a[1])))
    # Desde la decisión 0008 el karate también hace tiempo-movimiento, así
    # que el PDF lleva además los asaltos y las fases: el doble tiene que
    # saber darlos. Este combate no tiene ninguna marca.
    yo = SimpleNamespace(_bout_info={"athlete_a_name": "otro"},
                         window=SimpleNamespace(match_report=informe),
                         _marcas_del_video=lambda ses: ([], []),
                         # y el análisis es el del cuaderno abierto (19-10-2026)
                         _analisis_del_combate=lambda: "complete")
    ExportacionMixin._on_export_pdf(yo)
    assert avisos == ["PDF Exported Successfully"]
    assert pedido["output_path"] == str(tmp_path / "r.pdf")
    assert pedido["bout_metadata"] is sesion.bout_metadata
    assert pedido["annotations"] is sesion.annotations
    assert pedido["sport_id"] == "karate"
    assert pedido["session_data"] == {"duration_s": 180.0, "fps": 30.0, "video_name": "ID99.mp4",
                                      "asaltos": [], "fases": [], "gap_s": 2.0, "analysis": "complete"}
