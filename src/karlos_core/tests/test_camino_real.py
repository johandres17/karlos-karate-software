"""Tests que EJECUTAN el camino, no que lo leen.

Estos existen por tres fallos concretos, y merece la pena contarlos
porque explican para que sirve este archivo.

Al programar la carga de datos escribi tests que comprobaban que el
codigo fuente contenia ciertas llamadas. Pasaban. Mientras tanto la
funcion invocaba dos metodos que no existen —`load_video` y
`set_records`— y reventaba al primer clic. Un test que lee el fuente
verifica que escribi lo que queria escribir, no que funcione.

El tercero era peor: una carga usaba una variable `video`
cuando el parametro se llama `video_path`. Reventaba al abrir CUALQUIER
video en PRO, durante horas, y ningun test lo vio porque ninguno abria
un video.

Asi que aqui se ejecuta de verdad.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


class TestLaTablaDeAnotaciones:
    def test_los_metodos_que_usa_la_carga_existen(self):
        """`set_records` no existia y el codigo lo llamaba igualmente."""
        from karlos_core.models.annotation import Annotation
        from karlos_core.utils.config_loader import load_config
        from karlos_core.views.annotations_table import \
            AnnotationsTableView
        cfg, _ = load_config("karate")
        t = AnnotationsTableView(cfg.colors)
        t.set_sport_id("karate")
        t.clear_all()
        for i in range(3):
            t.add_annotation(Annotation(
                athlete="AKA", category="ATTACK",
                subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki",
                f_start=100 * i, f_end=100 * i + 10))
        assert len(t.records) == 3
        t.clear_all()
        assert len(t.records) == 0


class TestElCicloDeLosDatos:
    def test_escribir_leer_y_poner_en_la_tabla(self, tmp_path):
        from karlos_karate import csv_combate
        from karlos_core.models.annotation import Annotation
        from karlos_core.utils.config_loader import load_config
        from karlos_core.views.annotations_table import \
            AnnotationsTableView

        acciones = [Annotation(athlete="AKA", category="ATTACK",
                               subcategory="HAND TECHNIQUES",
                               technique="Gyaku Tsuki", level="Jodan",
                               score="YUKO", f_start=100 * i,
                               f_end=100 * i + 20)
                    for i in range(1, 6)]
        video = tmp_path / "COMBATE.mp4"
        video.write_bytes(b"x")
        r = tmp_path / "datos.csv"
        csv_combate.escribir(r, acciones, video=str(video), fps=30.0)

        cab, leidas = csv_combate.leer(r)
        assert csv_combate.buscar_video(r, cab) == str(video)

        cfg, _ = load_config("karate")
        t = AnnotationsTableView(cfg.colors)
        t.set_sport_id("karate")
        t.clear_all()
        for a in leidas:
            t.add_annotation(a)
        assert len(t.records) == 5
        assert t.records[0].technique == "Gyaku Tsuki"
        assert t.records[0].score == "YUKO"

    def test_la_carga_solo_usa_metodos_que_existen(self):
        """Comprueba de verdad que cada metodo llamado existe, en vez de
        confiar en que el fuente 'parece' correcto."""
        import inspect
        import re
        from karlos_core.controllers.annotation_controller import \
            AnnotationController as AC
        from karlos_core.views.annotations_table import \
            AnnotationsTableView
        cuerpo = inspect.getsource(AC._cargar_csv_combate)
        for metodo in set(re.findall(r"self\.(\w+)\(", cuerpo)):
            assert hasattr(AC, metodo), f"AnnotationController.{metodo} no existe"
        for metodo in set(re.findall(r"table_view\.(\w+)\(", cuerpo)):
            assert hasattr(AnnotationsTableView, metodo), \
                f"la tabla no tiene {metodo}"
