"""Fallos de la 1.0 arreglados en la 1.1 (pedidos por Johan el 11 y el
12-10-2026).

- **Las tarjetas del informe salían vacías.** El estilo ``QFrame{padding}``
  de cada caja lo heredaban sus etiquetas (una QLabel es un QFrame) y no les
  quedaba sitio para el texto: las ocho tarjetas de cifras, el título y la
  lectura del medidor de control y las tres métricas clave. Visto en la
  pantalla de la tableta; antes solo en capturas.
- **«Exportar Dataset» del hub no guardaba nada.** Pedía al exportador un
  ``_annotation_to_row`` que nunca existió. Ahora las filas y las hojas las
  da el exportador (``filas_de_anotaciones``, ``hojas_del_combate``).
- **«Back to Hub» no volvía desde un informe abierto en el hub.** Sin vídeo
  abierto soltaba el bloqueo de ``None`` y se caía.
"""
from __future__ import annotations

import csv
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMessageBox


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    yield QApplication.instance() or QApplication([])


def _accion(atleta="AKA", inicio=100, puntos="YUKO"):
    from karlos_core.models.annotation import Annotation
    return Annotation(athlete=atleta, category="ATTACK", subcategory="HAND TECHNIQUES",
                      technique="Gyaku Tsuki", level="Chudan", score=puntos,
                      f_start=inicio, f_end=inicio + 20)


# ----------------------------------------------------------------------
# Las tarjetas del informe
# ----------------------------------------------------------------------

def test_todas_las_etiquetas_del_informe_tienen_sitio_para_su_texto():
    from karlos_core import catalogo
    from karlos_core.models.state import FightSession
    from karlos_core.utils.config_loader import load_config
    cfg, meta = load_config("karate")
    informe = catalogo.activo().salidas().vista_informe(colors=cfg.colors, sport_meta=meta)
    sesion = FightSession(id=0, video_path="/v/ID99.mp4", fps=30.0, duration_s=180.0,
                          bout_metadata={}, annotations=[_accion(), _accion("AO", 400, "NONE")])
    informe.set_session(sesion, cfg.colors)
    informe.resize(1600, 1000)
    informe.show()
    QApplication.processEvents()
    try:
        sin_sitio = [(e.text(), e.contentsRect().height(), e.fontMetrics().height())
                     for e in informe.findChildren(QLabel)
                     if e.isVisibleTo(informe) and e.text().strip() and e.pixmap().isNull()
                     and e.contentsRect().height() < e.fontMetrics().height()]
        assert sin_sitio == []
        assert informe._kpi_total.layout().itemAt(0).widget().text() == "2"
    finally:
        informe.close()


def test_con_poco_alto_el_resumen_se_desplaza_y_no_se_aprieta():
    """En la tableta el resumen se apretaba: el punto del medidor pisaba su
    lectura y las métricas salían cortadas. Ahora se desplaza, y la ventana
    no pide más alto que antes."""
    from PySide6.QtWidgets import QFrame

    from karlos_core import catalogo
    from karlos_core.models.state import FightSession
    from karlos_core.utils.config_loader import load_config
    cfg, meta = load_config("karate")
    informe = catalogo.activo().salidas().vista_informe(colors=cfg.colors, sport_meta=meta)
    informe.set_session(FightSession(id=0, video_path="/v/ID99.mp4", fps=30.0, duration_s=180.0,
                                     bout_metadata={}, annotations=[_accion()]), cfg.colors)
    assert informe.minimumSizeHint().height() <= 897     # lo que pedía la 1.0
    informe._stack.setFixedHeight(260)
    informe.resize(1240, 900)
    informe.show()
    QApplication.processEvents()
    try:
        for nombre in ("medidorControl", "metricasClave"):
            caja = informe._exec_page.findChild(QFrame, nombre)
            assert caja.height() >= caja.layout().minimumSize().height(), nombre
    finally:
        informe.close()


def test_back_to_hub_desde_un_informe_abierto_en_el_hub(tmp_path, monkeypatch):
    from karlos_core.controllers.annotation_controller import AnnotationController
    from karlos_core.controllers.session_manager import SessionManager
    from karlos_core.models.state import FightSession
    from karlos_core.utils.config_loader import load_config
    monkeypatch.setattr(SessionManager, "_GLOBAL_ROUNDS_PATH", tmp_path / "rounds.json")
    cfg, meta = load_config("karate")
    c = AnnotationController(cfg, meta)
    c.aplicar_modo_inicial()
    c.show()
    try:
        c.sessions = [FightSession(id=0, video_path=str(tmp_path / "ID99.mp4"), video_name="ID99.mp4",
                                   fps=30.0, bout_metadata={}, annotations=[_accion()])]
        c.window.project_hub.set_sessions(c.sessions)
        c.navigation.show_hub()
        assert c._video_path is None                 # ningún vídeo abierto
        c._on_view_report(0)
        assert c.window._stack.currentIndex() == 2   # el informe
        c._on_back_to_hub()                          # antes: TypeError
        assert c.window._stack.currentIndex() == 0   # el hub
    finally:
        c.window.close()


# ----------------------------------------------------------------------
# Exportar Dataset
# ----------------------------------------------------------------------

def test_las_filas_del_dataset_son_las_de_la_hoja():
    from openpyxl import Workbook

    from karlos_core import catalogo
    exportador = catalogo.activo().salidas().exportador()
    exportador.set_records([_accion("AO", 400), _accion()])
    exportador.set_bout_info({"athlete_a_name": "A. Uno", "athlete_b_name": "B. Dos"})
    libro = Workbook()
    filas = exportador.hojas_del_combate(libro, "ID01.mp4_johan_1")
    assert libro.sheetnames[1:] == ["ID01.mp4_johan_1 - Info", "ID01.mp4_johan_1 - Data"]
    hoja = libro["ID01.mp4_johan_1 - Data"]
    columnas = exportador.ANNOTATION_COLUMNS
    assert [c.value for c in hoja[1]] == columnas            # con sus títulos
    assert [r["f_start"] for r in filas] == [100, 400]       # en orden
    for n, fila in enumerate(filas, start=2):
        assert [c.value for c in hoja[n]] == [fila.get(col, "") for col in columnas]
    assert filas[0]["AKA_Name"] == "A. Uno"


def test_los_nombres_de_hoja_los_acepta_excel():
    from openpyxl import Workbook

    from karlos_core import catalogo
    exportador = catalogo.activo().salidas().exportador()
    exportador.set_records([_accion()])
    libro = Workbook()
    largo = "Final [Tatami 1] A:B/C*D?_un nombre muy largo"
    exportador.hojas_del_combate(libro, largo)
    exportador.hojas_del_combate(libro, largo)              # el mismo otra vez
    nombres = libro.sheetnames[1:]
    assert len(nombres) == 4 and len({n.lower() for n in nombres}) == 4
    for nombre in nombres:
        assert len(nombre) <= 31
        assert not set(nombre) & set("[]:*?/\\")


def test_exportar_dataset_guarda_el_excel_y_el_csv(tmp_path, monkeypatch):
    from openpyxl import load_workbook

    from karlos_core import catalogo
    from karlos_core.controllers.anotador.exportacion import ExportacionMixin
    from karlos_core.models.state import FightSession
    sesiones = [
        FightSession(id=0, video_path="/v/ID01.mp4", video_name="ID01.mp4", fps=30.0,
                     status="Completed", bout_metadata={"athlete_a_name": "A. Uno"},
                     annotations=[_accion(), _accion("AO", 400, "NONE")]),
        FightSession(id=1, video_path="/v/ID03.mp4", video_name="ID03.mp4", fps=30.0,
                     status="Completed", bout_metadata={}, annotations=[_accion("AO", 50)]),
        FightSession(id=2, video_path="/v/ID04.mp4", video_name="ID04.mp4", fps=30.0,
                     status="Pending", bout_metadata={}, annotations=[]),
    ]
    guardadas = {"/v/ID01.mp4": {"evaluator_id": "johan", "occasion": 1,
                                 "fight_start": 30, "fight_end": 5430},
                 "/v/ID03.mp4": {"evaluator_id": "otro", "occasion": 2}}
    avisos = []
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a: str(tmp_path)))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda padre, titulo, texto, botones, *a: QMessageBox.Ok if "Ready" in texto else QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a: avisos.append(a[1])))
    yo = SimpleNamespace(
        sessions=sesiones, window=SimpleNamespace(set_status_message=avisos.append),
        session_manager=SimpleNamespace(load_session=guardadas.get),
        export_manager=catalogo.activo().salidas().exportador(), _sport_meta={"id": "karate"})
    ExportacionMixin._on_export_unified_dataset(yo)

    xlsx = list(tmp_path.glob("KarlosDataset_*.xlsx"))
    filas_csv = list(csv.DictReader(next(tmp_path.glob("KarlosDataset_*.csv")).open(encoding="utf-8")))
    assert len(xlsx) == 1 and "Export Complete" in avisos
    libro = load_workbook(xlsx[0])
    assert libro.sheetnames == ["Summary", "ID01.mp4_johan_1 - Info", "ID01.mp4_johan_1 - Data",
                                "ID03.mp4_otro_2 - Info", "ID03.mp4_otro_2 - Data"]
    assert [(f["Evaluator_ID"], f["Occasion"], f["f_start"]) for f in filas_csv] == [
        ("johan", "1", "100"), ("johan", "1", "400"), ("otro", "2", "50")]
    # El inicio del combate viene de la sesión guardada: 100 - 30 fotogramas.
    assert filas_csv[0]["Match_Time_s"] == "2.3"
