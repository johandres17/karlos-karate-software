"""Tests del annotation log del panel de tecnicas.

Sirve para vigilar el avance mientras se anota, asi que lo que importa es
que refleje siempre lo que hay, que se vea por donde se va y que lo mas
reciente quede a la vista.
"""

from __future__ import annotations

import pytest

from karlos_core.models.annotation import Annotation
from karlos_core.views.log_compacto import DATOS, LogCompacto


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _log():
    from karlos_core.utils.config_loader import load_config
    cfg, _ = load_config("karate")
    w = LogCompacto(cfg.colors)
    w.resize(290, 320)
    return w


def _ann(atleta="AKA", tecnica="Gyaku Tsuki", f=300, score="", cat="ATTACK",
         level="", dur=0.0):
    return Annotation(athlete=atleta, category=cat, subcategory="HAND",
                      technique=tecnica, level=level, score=score,
                      f_start=f, duration_s=dur)


def _fila(w, visual):
    return w._lista.item(visual).data(DATOS)


class TestOrden:
    def test_lo_ultimo_queda_arriba(self):
        w = _log()
        w.set_registros([_ann(f=30), _ann(f=3000, tecnica="Uraken")], 30.0)
        assert _fila(w, 0)["technique"] == "Uraken"

    def test_cada_accion_lleva_su_numero_de_orden(self):
        """Hace falta saber por donde se va, no solo cuantas van."""
        w = _log()
        w.set_registros([_ann(f=i * 300) for i in range(5)], 30.0)
        arriba = _fila(w, 0)["orden"]
        abajo = _fila(w, 4)["orden"]
        assert (arriba, abajo) == (5, 1)

    def test_el_numero_sigue_el_orden_cronologico(self):
        w = _log()
        w.set_registros([_ann(f=30), _ann(f=600), _ann(f=900)], 30.0)
        ordenes = [_fila(w, i)["orden"] for i in range(3)]
        assert ordenes == [3, 2, 1]


class TestContenido:
    def test_muestra_el_minuto_de_la_accion(self):
        w = _log()
        w.set_registros([_ann(f=1830)], 30.0)      # 61 s
        assert _fila(w, 0)["reloj"] == "01:01"

    def test_muestra_la_categoria_en_claro(self):
        w = _log()
        w.set_registros([_ann(cat="TACTICS", tecnica="Feint")], 30.0)
        assert _fila(w, 0)["categoria"] == "TÁCTICA"

    def test_muestra_nivel_y_duracion(self):
        w = _log()
        w.set_registros([_ann(level="Jodan", dur=0.63)], 30.0)
        d = _fila(w, 0)
        assert d["level"] == "Jodan" and d["dur"] == "0.6s"

    def test_sin_duracion_no_se_inventa_un_cero(self):
        w = _log()
        w.set_registros([_ann(dur=0.0)], 30.0)
        assert _fila(w, 0)["dur"] == ""

    def test_cuenta_por_atleta(self):
        w = _log()
        w.set_registros([_ann("AKA"), _ann("AKA", f=600), _ann("AO", f=900)], 30.0)
        assert "AKA 2" in w._cuenta.text() and "AO 1" in w._cuenta.text()

    def test_el_resumen_por_categoria_esta_en_el_tooltip(self):
        w = _log()
        w.set_registros([_ann(cat="TACTICS"), _ann(cat="TACTICS", f=600),
                         _ann(cat="ATTACK", f=900)], 30.0)
        assert "TÁCTICA: 2" in w.toolTip() and "ATAQUE: 1" in w.toolTip()

    def test_una_categoria_desconocida_no_rompe(self):
        w = _log()
        w.set_registros([_ann(cat="LO QUE SEA")], 30.0)
        assert w._lista.count() == 1

    def test_repintar_no_duplica(self):
        w = _log()
        for _ in range(3):
            w.set_registros([_ann(), _ann(f=600)], 30.0)
        assert w._lista.count() == 2

    def test_sin_registros_queda_vacio(self):
        w = _log()
        w.set_registros([_ann()], 30.0)
        w.set_registros([], 30.0)
        assert w._lista.count() == 0 and w._cuenta.text().startswith("0")
        assert w.toolTip() == "Sin anotaciones"

    def test_fps_invalido_no_rompe(self):
        w = _log()
        w.set_registros([_ann(f=300)], 0.0)
        assert w._lista.count() == 1


class TestPintado:
    """El pintado a mano es el que alinea las columnas: si lanza, la lista
    se queda en blanco y el evaluador pierde la referencia."""

    def test_pinta_todas_las_variantes(self):
        w = _log()
        w.set_registros([
            _ann("AKA", "Gyaku Tsuki", 300, "YUKO", "ATTACK", "Chudan", 0.6),
            _ann("AO", "Feint", 900, "", "TACTICS"),
            _ann("AKA", "Dodge", 1500, "", "DEFENSE"),
            _ann("AO", "Mawashi Geri Jodan", 2400, "IPPON", "ATTACK", "Jodan", 0.9),
            _ann("", "Referee", 3000, "", "REFEREE STOP"),
        ], 30.0)
        w.grab()

    def test_un_nombre_larguisimo_no_rompe_el_pintado(self):
        w = _log()
        w.set_registros([_ann(tecnica="Kizami Ura Mawashi Geri Jodan Kaiten Renraku")], 30.0)
        w.grab()

    def test_un_registro_sin_campos_no_rompe(self):
        w = _log()
        w.set_registros([Annotation(athlete="", category="", subcategory="",
                                    technique="")], 30.0)
        w.grab()


class TestNavegacion:
    def test_pulsar_una_entrada_pide_su_indice(self):
        w = _log()
        w.set_registros([_ann(f=30), _ann(f=3000)], 30.0)
        vistos = []
        w.fila_pedida.connect(vistos.append)
        w._al_pulsar(w._lista.item(0))        # la de arriba es la ultima
        assert vistos == [1]

    def test_doble_clic_pide_editar_esa_ficha(self):
        w = _log()
        w.set_registros([_ann(f=30), _ann(f=3000)], 30.0)
        vistos = []
        w.editar_pedida.connect(vistos.append)
        w._al_doble_pulsar(w._lista.item(0))
        assert vistos == [1]


class TestMenuContextual:
    """Clic derecho para ir, editar o borrar. Borrar es lo unico del flujo
    que no se puede rehacer mirando otra vez el video."""

    def test_pide_borrar_la_fila_pulsada(self):
        w = _log()
        w.set_registros([_ann(f=30), _ann(f=3000)], 30.0)
        vistos = []
        w.borrar_pedida.connect(vistos.append)
        w.borrar_pedida.emit(int(w._lista.item(0).data(DATOS)["orden"]) - 1)
        assert vistos == [1]

    def test_las_tres_senales_son_distintas(self):
        w = _log()
        w.set_registros([_ann()], 30.0)
        ir, editar, borrar = [], [], []
        w.fila_pedida.connect(ir.append)
        w.editar_pedida.connect(editar.append)
        w.borrar_pedida.connect(borrar.append)
        w._al_pulsar(w._lista.item(0))
        assert ir == [0] and editar == [] and borrar == []
        w._al_doble_pulsar(w._lista.item(0))
        assert editar == [0] and borrar == []

    def test_el_menu_sobre_el_vacio_no_hace_nada(self):
        from PySide6.QtCore import QPoint
        w = _log()
        w.set_registros([], 30.0)
        vistos = []
        w.borrar_pedida.connect(vistos.append)
        w._menu(QPoint(10, 10))
        assert vistos == []


class TestBorradoConDeshacer:
    def _tabla(self):
        from PySide6.QtWidgets import QApplication
        from karlos_core.utils.config_loader import load_config
        from karlos_core.views.annotations_table import AnnotationsTableView
        cfg, _ = load_config("karate")
        tv = AnnotationsTableView(cfg.colors)
        tv.set_sport_id("karate")
        for i, t in enumerate(["A", "B", "C"]):
            tv.add_annotation(_ann(tecnica=t, f=i * 100))
        return tv

    def _cmd(self, idx, tv):
        from karlos_core.controllers.undo_commands import BorrarAnotacionCommand
        return BorrarAnotacionCommand(idx, tv)

    def test_borra_la_fila_pedida(self):
        tv = self._tabla()
        self._cmd(1, tv).redo()
        assert [r.technique for r in tv.records] == ["A", "C"]

    def test_deshacer_la_devuelve_a_su_sitio(self):
        """Si volviera al final, el orden cronologico se romperia."""
        tv = self._tabla()
        c = self._cmd(1, tv)
        c.redo()
        c.undo()
        assert [r.technique for r in tv.records] == ["A", "B", "C"]

    def test_borrar_la_ultima_y_deshacer(self):
        tv = self._tabla()
        c = self._cmd(2, tv)
        c.redo()
        assert [r.technique for r in tv.records] == ["A", "B"]
        c.undo()
        assert [r.technique for r in tv.records] == ["A", "B", "C"]

    def test_un_indice_fuera_de_rango_no_rompe(self):
        tv = self._tabla()
        c = self._cmd(99, tv)
        c.redo()
        c.undo()
        assert len(tv.records) == 3
