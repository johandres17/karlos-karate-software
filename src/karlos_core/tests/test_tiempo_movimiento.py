"""El tiempo-movimiento en el programa: solo donde el deporte lo hace.

Tres análisis del mismo combate —técnico-táctico, tiempo-movimiento,
integrado—, las fases marcadas con sus teclas o derivadas de las acciones,
y el informe y el Excel que las cuentan.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QListWidget

from karlos_core import catalogo
from karlos_core.models.annotation import Annotation
from karlos_core.models.state import FightSession
from karlos_core.utils.config_loader import load_config

FPS = 30.0
ASALTOS = [{"asalto": 1, "inicio": 0, "fin": 3599}, {"asalto": 2, "inicio": 4000, "fin": 7599},
           {"asalto": 3, "inicio": None, "fin": None}]
# Las fases de Chung (AKA): las de cada atleta van con su atleta.
FASES = [{"fotograma": 0, "fase": "non_fighting", "atleta": "AKA"},
         {"fotograma": 300, "fase": "fighting", "atleta": "AKA"},
         {"fotograma": 600, "fase": "non_fighting", "atleta": "AKA"},
         {"fotograma": 1200, "fase": "stoppage", "atleta": "AKA"},
         {"fotograma": 1500, "fase": "non_fighting", "atleta": "AKA"}]


def _acciones():
    return [
        Annotation(athlete="AKA", category="ATTACK", subcategory="CIRCULAR KICKS",
                   technique="Bandal-chagi", level="Head", score="3_PTS", f_start=300, f_end=330,
                   duration_s=1.0, round=1),
        Annotation(athlete="AO", category="DEFENSE", subcategory="DEFENSE", technique="Dodge",
                   f_start=340, f_end=360, duration_s=0.7, round=1),
        Annotation(athlete="AKA", category="REFEREE STOP", subcategory="REFEREE STOP",
                   technique="Referee Stop - Kal-yeo", f_start=1200, f_end=1500,
                   duration_s=10.0, round=1),
        Annotation(athlete="AO", category="ATTACK", subcategory="LINEAR KICKS",
                   technique="Yeop-chagi", level="Trunk", score="NO_PT", f_start=4500, f_end=4530,
                   duration_s=1.0, round=2),
    ]


@pytest.fixture(autouse=True)
def qt():
    QApplication.instance() or QApplication([])
    yield
    # El análisis elegido se recuerda en los ajustes: que no se cuele en
    # las pruebas siguientes, que esperan el técnico-táctico de siempre.
    from karlos_core import identidad
    from karlos_core.views.dialogo_analisis import ANALISIS
    identidad.ajustes().remove(ANALISIS)
    catalogo.establecer("karate")


def test_la_ventana_de_datos_ya_no_pregunta_que_se_analiza():
    """Desde el 19-10-2026 el análisis es el cuaderno abierto (decisión
    0008): se elige al entrar o en el Hub, no en los datos del combate."""
    from karlos_core.views.bout_info_popup import BoutInfoPopup
    catalogo.establecer("karate")
    assert "analysis" not in BoutInfoPopup("AKA", "AO", sport_id="karate")._combos


def test_la_sesion_guarda_las_fases_con_los_asaltos(tmp_path):
    from pathlib import Path
    from karlos_core.controllers.session_manager import SessionManager
    sm = SessionManager()
    (tmp_path / "v.mp4").write_bytes(b"")
    ruta = sm.save_session(video_path=str(tmp_path / "v.mp4"), bout_info={}, fight_start=0,
                           fight_end=100, records=[], asaltos=ASALTOS, fases=FASES)
    datos = SessionManager._load_from_path(Path(ruta))
    assert datos["fases"] == FASES and datos["asaltos"] == ASALTOS


def test_el_informe_del_karate_suma_esa_pagina_a_las_cinco_suyas():
    """Decisión 0008: el karate conserva sus cinco páginas —son su informe
    técnico-táctico de siempre— y gana la de tiempo-movimiento al final."""
    catalogo.establecer("karate")
    cfg, meta = load_config("karate")
    vista = catalogo.paquete("karate").salidas().vista_informe(cfg.colors, meta)
    lista = vista.findChild(QListWidget)
    paginas = [lista.item(i).text() for i in range(lista.count())]
    assert paginas == ["Executive Summary", "Tactical Analysis", "Fight Rhythm",
                       "Performance Charts", "Deep Analysis", "Time-Motion"]


# ----------------------------------------------------------------------
# Qué se analiza: se pregunta al entrar en el asistido (Johan, 8-10-2026)
# ----------------------------------------------------------------------

def test_el_dialogo_de_analisis_recuerda_la_eleccion():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from karlos_core.views import dialogo_analisis as da
    catalogo.establecer("karate")
    cfg, _meta = load_config("karate")
    assert da.analisis_por_defecto() == "complete", "el de siempre, si no se eligió nada"
    d = da.DialogoAnalisis(cfg.colors)
    assert len(d._tarjetas) == 3 and d._tarjetas["complete"].elegida
    d._elegir("time_motion")
    assert d.analisis == "time_motion" and da.analisis_por_defecto() == "time_motion"
    otro = da.DialogoAnalisis(cfg.colors)
    assert otro.analisis == "time_motion", "la próxima vez viene marcado"
    otro.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_3, Qt.NoModifier))
    assert otro.analisis == "complete" and da.analisis_por_defecto() == "complete"


def test_el_orden_de_las_tarjetas_es_del_mas_acotado_al_mas_completo():
    """Johan, 16-10-2026: primero tiempo-movimiento, después
    técnico-táctico, después el completo. Y las teclas 1, 2 y 3 van con
    ese orden, no con el de antes."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from karlos_core.views import dialogo_analisis as da
    catalogo.establecer("karate")
    cfg, _meta = load_config("karate")
    d = da.DialogoAnalisis(cfg.colors)
    assert list(d._tarjetas) == ["time_motion", "technical_tactical", "complete"]
    for tecla, esperado in ((Qt.Key_1, "time_motion"),
                            (Qt.Key_2, "technical_tactical"),
                            (Qt.Key_3, "complete")):
        d.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, tecla, Qt.NoModifier))
        assert d.analisis == esperado


def test_sin_duraciones_no_se_deriva_nada():
    """Técnico-táctico: las acciones son eventos; derivar fases de ellas
    sería inventar. La tabla lo dice en vez de calcular."""
    from karlos_core.models.fases import por_asaltos
    from karlos_core.tiempo_movimiento import html_informe
    con = por_asaltos(ASALTOS, _acciones(), None, FPS, 2.0)
    sin = por_asaltos(ASALTOS, _acciones(), None, FPS, 2.0, derivar=False)
    assert con[0]["derivadas"] is not None and sin[0]["derivadas"] is None
    texto = html_informe(_acciones(), ASALTOS, None, FPS, 2.0, "#888", "#fa0", derivar=False)
    assert "events without duration" in texto and "derived" not in texto.split("</p>")[-1]


def test_el_dialogo_tiene_atras():
    from karlos_core.views import dialogo_analisis as da
    catalogo.establecer("karate")
    cfg, _meta = load_config("karate")
    d = da.DialogoAnalisis(cfg.colors)
    cerrado = []
    d.rejected.connect(lambda: cerrado.append(1))
    d._volver.click()
    assert cerrado == [1], "«Sair» cierra sin elegir"


