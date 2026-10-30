"""El contrato SportPack y el paquete de karate (fase F2 de las ediciones).

Dos cosas: que el karate cumple el contrato sin cambiar lo que hace la 1.0,
y que el contrato no es del karate (cabe un deporte inventado).

La tabla de puntos merece su propia prueba: el 5 de octubre de 2026 estaba
copiada en seis sitios y cada pantalla la leía a su manera. Desde F3.2 solo
está en la configuración de cada deporte y todo el programa la consulta con
``reglamento.puntos``; la prueba falla si vuelve a aparecer una copia.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from karlos_core.deporte import Competidor, Puntuacion, Reglamento, SportPack
from karlos_karate import KaratePack


@pytest.fixture(scope="module")
def karate():
    return KaratePack()


def test_karate_cumple_el_contrato(karate):
    assert isinstance(karate, SportPack)
    assert (karate.id, karate.edicion) == ("karate", "Karlos Karate")


def test_los_competidores_son_los_que_ya_guardan_las_sesiones(karate):
    from karlos_core.utils.config_loader import load_config
    cfg, _ = load_config("karate")
    assert [c.codigo for c in karate.competidores] == ["AKA", "AO"]
    assert (cfg.athlete_a_label, cfg.athlete_b_label) == ("AKA", "AO")


def test_los_puntos_del_karate_son_los_de_la_1_0(karate):
    assert {p.codigo: p.puntos for p in karate.reglamento.puntuaciones if p.puntos} == \
        {"IPPON": 3, "WAZA": 2, "YUKO": 1}


def test_los_puntos_se_buscan_por_codigo_o_por_nombre_sin_mayusculas(karate):
    r = karate.reglamento
    assert [r.puntos(x) for x in ("IPPON", "waza", "WAZA-ARI", "Waza-Ari", "YUKO")] == [3, 2, 2, 2, 1]
    assert [r.puntos(x) for x in ("NONE", "FOUL", "", None, "CONNECTED")] == [0, 0, 0, 0, 0]
    # Si el nombre de una coincide con el código de otra, manda el código.
    raro = Reglamento(puntuaciones=(Puntuacion("A", 1, "B"), Puntuacion("B", 5, "Otra")),
                      escalera_de_faltas=("X",), duracion_s=1.0, tipos_de_parada=(),
                      fase_de=lambda s: "")
    assert raro.puntos("b") == 5


def test_la_tabla_de_puntos_solo_esta_en_las_configuraciones():
    """Ningún diccionario código→puntos fuera de las configuraciones, ni en
    el núcleo ni en los paquetes de los deportes."""
    from karlos_core.config import SPORTS
    codigos = {c for cfg in SPORTS.values() for c in cfg["scoring"]}
    src = Path(__file__).resolve().parents[2]
    copias = []
    paquetes = ("karlos_core", "karlos_karate", "karlos_kickboxing", "karlos_taekwondo", "karlos_boxing")
    for f in sorted(f for p in paquetes for f in (src / p).rglob("*.py")):
        rel = f.relative_to(src).as_posix()
        if "/tests/" in rel or rel.endswith("_config.py"):
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(n, ast.Dict):
                continue
            pares = [(k.value, v.value) for k, v in zip(n.keys, n.values)
                     if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)]
            if sum(1 for k, v in pares if k in codigos and type(v) is int) >= 2:
                copias.append(f"{rel}:{n.lineno}")
    assert not copias, f"copias de la tabla de puntos: {copias}"


def test_la_escalera_de_faltas_es_la_wkf_2026(karate):
    escalera = ("CHUI-1", "CHUI-2", "CHUI-3", "HANSOKU-CHUI", "HANSOKU")
    assert karate.reglamento.escalera_de_faltas == escalera
    for n in range(1, 8):
        assert karate.reglamento.grado(n) == escalera[min(n, 5) - 1]
    with pytest.raises(ValueError):
        karate.reglamento.grado(0)


def test_la_fase_y_la_duracion_son_las_del_csv(karate):
    from karlos_karate import csv_combate
    for activo in (0, 59.99, 60, 119.9, 120, 179.99, 180, 180.01, 300):
        assert karate.reglamento.fase(activo) == csv_combate._fase(activo)
    assert karate.reglamento.duracion_s == 180.0


def test_las_paradas_son_las_de_la_configuracion(karate):
    assert karate.reglamento.tipos_de_parada == ("Referee", "VR", "Injury")


def test_que_es_una_sancion_lo_decide_lo_mismo_que_en_el_csv(karate):
    from karlos_karate import csv_combate
    from karlos_core.models.annotation import Annotation
    casos = [
        Annotation(athlete="AO", category="PENALTY", subcategory="Jogai", technique="CHUI-1"),
        Annotation(athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
                   technique="Gyaku Tsuki", sport_specific_data={"sanction": "Contact"}),
        Annotation(athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
                   technique="Gyaku Tsuki"),
    ]
    assert [karate.es_sancion(a) for a in casos] == [csv_combate.es_sancion(a) for a in casos] \
        == [True, True, False]


def test_la_taxonomia_y_el_arbol_salen_del_karate(karate):
    tax = karate.taxonomia()
    assert tax.athlete_a_label == "AKA"
    arbol = karate.arbol()
    assert arbol is not karate.arbol(), "cada acción empieza con un árbol nuevo"


def test_un_deporte_inventado_cabe_en_el_contrato():
    """El contrato no lleva nada del karate dentro."""

    class Inventado:
        id = "inventado"
        nombre = "Inventado"
        edicion = "Karlos Inventado"
        competidores = (Competidor("HONG", "Hong", "rojo"), Competidor("CHUNG", "Chung", "azul"))
        reglamento = Reglamento(
            puntuaciones=(Puntuacion("PUÑO", 1, "Puño"), Puntuacion("CABEZA", 3, "Cabeza")),
            escalera_de_faltas=("AVISO", "DESCALIFICADO"),
            duracion_s=120.0, tipos_de_parada=("Árbitro",),
            fase_de=lambda s: f"Asalto_{int(s // 120) + 1}")

        def configuracion(self):
            return {}

        def taxonomia(self):
            return None

        def arbol(self):
            return None

        def es_sancion(self, anotacion):
            return False

        def tiempo_movimiento(self):
            return None          # sin fases que marcar, como el karate

        def salidas(self):
            return None

        def textos(self):
            return {}

    d = Inventado()
    assert isinstance(d, SportPack)
    assert d.reglamento.puntos("cabeza") == 3
    assert d.reglamento.grado(9) == "DESCALIFICADO"
    assert d.reglamento.fase(130) == "Asalto_2"


def test_las_salidas_del_karate_son_las_de_siempre(karate):
    """El núcleo las pide al deporte; el karate entrega sus módulos."""
    from karlos_karate import csv_combate
    from karlos_karate.export_manager import ExportManager
    from karlos_core.deporte import Salidas
    s = karate.salidas()
    assert isinstance(s, Salidas)
    assert s.csv_del_combate() is csv_combate
    assert type(s.exportador()) is ExportManager
    assert s.exportador() is not s.exportador(), "cada exportador es nuevo"
    assert s.probar() == (True, "reportlab dentro")


def test_la_ventana_principal_pone_el_informe_del_deporte():
    from PySide6.QtWidgets import QApplication

    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.main_window import MainWindow
    from karlos_karate.match_report import MatchReportView
    QApplication.instance() or QApplication([])
    cfg, meta = load_config("karate")
    w = MainWindow(cfg, meta)
    try:
        assert type(w.match_report) is MatchReportView
    finally:
        w.close()
