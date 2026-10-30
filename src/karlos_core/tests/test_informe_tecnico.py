"""El informe técnico-táctico: lo que recoge ese análisis (Johan, 8-10-2026:
«cada modo tiene que generar un reporte diferente basado en los datos que
toma»). Cada análisis lleva sus páginas y sus hojas del Excel."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QListWidget

from karlos_core import catalogo
from karlos_core.informe_tecnico import dimensiones, hoja_excel, html, resumen
from karlos_core.models.annotation import Annotation
from karlos_core.models.state import FightSession
from karlos_core.utils.config_loader import load_config

FPS = 30.0
ASALTOS = [{"asalto": 1, "inicio": 0, "fin": 999}]


@pytest.fixture(autouse=True)
def qt():
    QApplication.instance() or QApplication([])
    catalogo.establecer("karate")
    yield


def _fila(atleta, tecnica, sub, cat="ATTACK", ini=0, fin=10, score="", datos=None, nivel=""):
    return Annotation(athlete=atleta, category=cat, subcategory=sub, technique=tecnica, level=nivel,
                      score=score, f_start=ini, f_end=fin, duration_s=(fin - ini) / FPS,
                      sport_specific_data=datos or {})


def _acciones():
    return [
        _fila("AKA", "Gyaku Tsuki", "HAND TECHNIQUES", score="YUKO", ini=100, fin=115, nivel="Chudan",
              datos={"stance": "Rear", "target": "Chudan", "action_type": "Direct", "contact": "Score"}),
        _fila("AKA", "Kizami Mawashi Geri", "KICK TECHNIQUES", ini=300, fin=320, nivel="Jodan",
              datos={"stance": "Lead", "target": "Jodan", "action_type": "Counter", "contact": "NoScore"}),
        _fila("AO", "Dodge", "DEFENSE", cat="DEFENSE", ini=200, fin=206),
        _fila("AO", "Upper Feint", "TACTICS", cat="TACTICS", ini=400, fin=410),
        Annotation(athlete="AKA", category="REFEREE STOP", subcategory="REFEREE STOP",
                   technique="Referee", f_start=600, f_end=700, duration_s=100 / FPS),
    ]


def test_las_dimensiones_salen_de_los_campos_de_la_fila():
    assert dimensiones(_acciones()[0]) == {"Action": "Direct", "Stance": "Rear",
                                           "Target": "Chudan", "Contact": "Score"}


def test_el_resumen_cuenta_por_competidor_y_no_cuenta_paradas():
    r = resumen(_acciones(), True, catalogo.activo().reglamento.puntos)
    aka, ao = r["atletas"]["AKA"], r["atletas"]["AO"]
    assert (aka["acciones"], aka["puntuadas"], aka["puntos"]) == (2, 1, 1)
    assert (ao["acciones"], ao["puntuadas"], ao["puntos"]) == (2, 0, 0)
    assert dict(aka["por_tactica"]) == {"Direct": 1, "Counter": 1}
    assert dict(r["paradas"]) == {"Referee": 1}
    assert aka["duracion_media_s"] == pytest.approx((15 + 20) / 2 / FPS)


def test_la_hoja_de_excel_lleva_las_tablas_del_karate():
    from openpyxl import Workbook
    wb = Workbook()
    hoja_excel(wb.active, _acciones(), False, catalogo.activo().reglamento.puntos)
    filas = [list(f) for f in wb.active.iter_rows(values_only=True)]
    assert filas[0][0] == "Technical-tactical analysis"
    assert ["Tactical context", "AKA", "AO"] in filas
    assert ["Target level", "AKA", "AO"] in filas and ["Jodan", 1, 0] in filas
    assert ["Outcome", "AKA", "AO"] in filas and ["Scored", 1, 0] in filas
    assert not any(f and f[0] == "Mean action duration (s)" for f in filas), "un evento no tiene duración"


def test_el_informe_en_pantalla_lo_dice_con_las_palabras_del_karate():
    texto = html(_acciones(), True, "#777", "#fc0", catalogo.activo().reglamento.puntos)
    assert "Tactical context" in texto and "Target level" in texto
    assert "Mean action duration" in texto


def _paginas(analisis):
    cfg, meta = load_config("karate")
    vista = catalogo.activo().salidas().vista_informe(cfg.colors, meta)
    sesion = FightSession(id=1, video_path="/v.mp4", status="Completed", fps=FPS,
                          annotations=_acciones(), bout_metadata={"analysis": analisis},
                          asaltos=ASALTOS, fases=[])
    vista.set_session(sesion, cfg.colors)
    lista = vista.findChild(QListWidget)
    return [lista.item(i).text() for i in range(lista.count()) if not lista.item(i).isHidden()]


def test_el_informe_en_pantalla_ensena_las_paginas_de_su_analisis():
    tecnico = ["Executive Summary", "Tactical Analysis", "Fight Rhythm",
               "Performance Charts", "Deep Analysis"]
    assert _paginas("technical_tactical") == tecnico
    assert _paginas("time_motion") == ["Time-Motion"]
    assert _paginas("complete") == tecnico + ["Time-Motion"]
    # Un combate de antes, sin análisis dicho: todas.
    assert _paginas("") == tecnico + ["Time-Motion"]


def test_el_excel_lleva_las_hojas_de_su_analisis(tmp_path):
    from openpyxl import load_workbook
    em = catalogo.activo().salidas().exportador()
    em.set_bout_info({"athlete_a_name": "Uno", "athlete_b_name": "Dos"})
    em.set_sport_id("karate"); em.set_fps(FPS); em.set_records(_acciones())
    em.set_tiempo_movimiento(ASALTOS, [], 2.0, derivar=False)
    em.set_analisis("technical_tactical")
    assert load_workbook(em.export_xlsx(tmp_path / "tt.xlsx")).sheetnames == [
        "Bout Info", "Annotations", "Technical-Tactical"]
    em.set_tiempo_movimiento(ASALTOS, [], 2.0, derivar=True)
    em.set_analisis("time_motion")
    assert load_workbook(em.export_xlsx(tmp_path / "tm.xlsx")).sheetnames == [
        "Bout Info", "Annotations", "Time-Motion", "Time-Motion matrix"]
    em.set_analisis("complete")
    assert load_workbook(em.export_xlsx(tmp_path / "c.xlsx")).sheetnames == [
        "Bout Info", "Annotations", "Technical-Tactical", "Time-Motion", "Time-Motion matrix"]
