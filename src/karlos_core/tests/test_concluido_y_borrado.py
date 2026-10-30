"""Tests de quien da un combate por terminado y de tirar lo anotado.

Las dos cosas nacen de la misma queja: el programa decidia por Johan.
Bastaba una anotacion para que el Hub pusiera «Completed», y no habia
forma de vaciar un combate mal anotado sin borrar la sesion entera.

Lo que estos tests defienden:

1. «Completed» solo sale de una marca que puso una persona, y esa marca
   sobrevive a los autoguardados, que ocurren cada pocos segundos.
2. Borrar se puede deshacer, y las paradas del arbitro se pueden salvar
   aparte: son del combate y valen para cualquier pasada.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _anotacion(categoria="ATTACK", tecnica="Gyaku Tsuki", atleta="AKA"):
    from karlos_core.models.annotation import Annotation
    return Annotation(athlete=atleta, category=categoria,
                      subcategory="", technique=tecnica)


def _fichero(tmp_path, categorias=(), concluido=False, **extra):
    ruta = tmp_path / "COMBATE__johan__1.karlos"
    datos = {"version": "1.0", "video_path": "/v/COMBATE.mp4",
             "annotations": [{"category": c, "technique": "x",
                              "subcategory": "", "athlete": "AKA"}
                             for c in categorias],
             "concluido": concluido}
    datos.update(extra)
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


# ======================================================================
# La marca vive en el fichero
# ======================================================================

class TestLaMarcaSobreviveAlAutoguardado:
    """El fallo que esto vigila: anotar una accion despues de marcar el
    combate como terminado borraba la marca, porque cada autoguardado
    reescribe el fichero entero."""

    def test_guardar_sin_decir_nada_conserva_la_marca(self, tmp_path):
        from karlos_core.controllers.session_manager import SessionManager
        ruta = _fichero(tmp_path, ["ATTACK"], concluido=True)
        assert SessionManager._resolver_concluido(ruta, None) is True

    def test_guardar_pidiendolo_lo_cambia(self, tmp_path):
        from karlos_core.controllers.session_manager import SessionManager
        ruta = _fichero(tmp_path, ["ATTACK"], concluido=True)
        assert SessionManager._resolver_concluido(ruta, False) is False

    def test_un_fichero_nuevo_no_esta_concluido(self, tmp_path):
        from karlos_core.controllers.session_manager import SessionManager
        assert SessionManager._resolver_concluido(
            tmp_path / "no_existe.karlos", None) is False

    def test_save_session_lo_escribe(self, tmp_path, monkeypatch):
        """De punta a punta: guardar deja el campo en el JSON."""
        from karlos_core.controllers import session_manager as sm
        video = tmp_path / "COMBATE.mp4"
        video.write_bytes(b"x")
        gestor = sm.SessionManager()
        ruta = gestor.save_session(
            video_path=str(video), bout_info={}, fight_start=0, fight_end=10,
            records=[], evaluator_id="johan", occasion=1)
        datos = json.loads(open(ruta, encoding="utf-8").read())
        assert datos["concluido"] is False
        gestor.save_session(
            video_path=str(video), bout_info={}, fight_start=0, fight_end=10,
            records=[], evaluator_id="johan", occasion=1, concluido=True)
        datos = json.loads(open(ruta, encoding="utf-8").read())
        assert datos["concluido"] is True
        # y el siguiente autoguardado NO la tira
        gestor.save_session(
            video_path=str(video), bout_info={}, fight_start=0, fight_end=10,
            records=[_anotacion()], evaluator_id="johan", occasion=1)
        datos = json.loads(open(ruta, encoding="utf-8").read())
        assert datos["concluido"] is True


class TestMarcarYDesmarcar:
    def test_ida_y_vuelta(self, tmp_path, monkeypatch):
        from karlos_core.controllers.session_manager import SessionManager
        ruta = _fichero(tmp_path, ["ATTACK"])
        monkeypatch.setattr(SessionManager, "ruta_de_sesion",
                            staticmethod(lambda v: ruta))
        assert SessionManager.esta_concluido("/v/COMBATE.mp4") is False
        assert SessionManager.marcar_concluido("/v/COMBATE.mp4", True) is True
        assert SessionManager.esta_concluido("/v/COMBATE.mp4") is True
        SessionManager.marcar_concluido("/v/COMBATE.mp4", False)
        assert SessionManager.esta_concluido("/v/COMBATE.mp4") is False

    def test_sin_fichero_no_marca_ni_revienta(self, tmp_path, monkeypatch):
        from karlos_core.controllers.session_manager import SessionManager
        monkeypatch.setattr(SessionManager, "ruta_de_sesion",
                            staticmethod(lambda v: None))
        assert SessionManager.marcar_concluido("/v/x.mp4", True) is False
        assert SessionManager.esta_concluido("/v/x.mp4") is False

    def test_no_toca_lo_anotado(self, tmp_path, monkeypatch):
        from karlos_core.controllers.session_manager import SessionManager
        ruta = _fichero(tmp_path, ["ATTACK", "DEFENSE", "REFEREE STOP"])
        monkeypatch.setattr(SessionManager, "ruta_de_sesion",
                            staticmethod(lambda v: ruta))
        SessionManager.marcar_concluido("/v/COMBATE.mp4", True)
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert len(datos["annotations"]) == 3


# ======================================================================
# Borrar sobre el fichero, desde el Hub
# ======================================================================

class TestBorrarAnotacionesDelFichero:
    @pytest.fixture
    def montado(self, tmp_path, monkeypatch):
        from karlos_core.controllers.session_manager import SessionManager
        ruta = _fichero(
            tmp_path,
            ["ATTACK", "REFEREE STOP", "TACTICS", "REFEREE STOP"],
            concluido=True, fight_start=120, fight_end=5400,
            aka_fouls=2, ao_fouls=1)
        monkeypatch.setattr(SessionManager, "ruta_de_sesion",
                            staticmethod(lambda v: ruta))
        return SessionManager, ruta

    def test_borrarlo_todo(self, montado):
        gestor, ruta = montado
        assert gestor.borrar_anotaciones("/v/COMBATE.mp4", False) == 4
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert datos["annotations"] == []

    def test_conservando_las_paradas(self, montado):
        gestor, ruta = montado
        assert gestor.borrar_anotaciones("/v/COMBATE.mp4", True) == 2
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert [a["category"] for a in datos["annotations"]] == \
            ["REFEREE STOP", "REFEREE STOP"]

    def test_los_limites_del_combate_no_se_tocan(self, montado):
        """Marcar inicio y fin cuesta encontrar el marcador en el video:
        no es una anotacion y no se pierde al vaciar el registro."""
        gestor, ruta = montado
        gestor.borrar_anotaciones("/v/COMBATE.mp4", False)
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert datos["fight_start"] == 120
        assert datos["fight_end"] == 5400

    def test_las_faltas_vuelven_a_cero(self, montado):
        """Se cuentan de lo anotado: dejarlas seria mentir en el marcador."""
        gestor, ruta = montado
        gestor.borrar_anotaciones("/v/COMBATE.mp4", False)
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert datos["aka_fouls"] == 0 and datos["ao_fouls"] == 0

    def test_deja_de_estar_concluido(self, montado):
        """Lo que queda ya no es lo que Johan dio por terminado."""
        gestor, ruta = montado
        gestor.borrar_anotaciones("/v/COMBATE.mp4", True)
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert datos["concluido"] is False

    def test_deja_copia_de_seguridad(self, montado, tmp_path):
        gestor, ruta = montado
        gestor.borrar_anotaciones("/v/COMBATE.mp4", False)
        copias = list((tmp_path / "backups").glob("*.karlos"))
        assert copias, "borrar sin copia es perder el trabajo"
        previo = json.loads(copias[0].read_text(encoding="utf-8"))
        assert len(previo["annotations"]) == 4

    def test_sin_fichero_devuelve_cero(self, monkeypatch):
        from karlos_core.controllers.session_manager import SessionManager
        monkeypatch.setattr(SessionManager, "ruta_de_sesion",
                            staticmethod(lambda v: None))
        assert SessionManager.borrar_anotaciones("/v/x.mp4", False) == 0


# ======================================================================
# El estado que ve el Hub
# ======================================================================

class _Sesion:
    def __init__(self, ruta="/v/COMBATE.mp4"):
        self.id = 1
        self.video_path = ruta
        self.video_name = "COMBATE.mp4"
        self.status = "Pending"
        self.annotations = []
        self.bout_metadata = {}
        self.resolution = ""
        self.fps = 30.0
        self.duration_s = 0.0


def _controlador(monkeypatch, tmp_path, ruta_sesion):
    from karlos_core.controllers import annotation_controller as ac
    from karlos_core.controllers.session_manager import SessionManager
    c = ac.AnnotationController.__new__(ac.AnnotationController)
    c.session_manager = SessionManager()
    c.sessions = [_Sesion()]
    c.active_session_idx = -1
    monkeypatch.setattr(
        SessionManager, "get_active_round",
        staticmethod(lambda v: {"evaluator_id": "johan", "occasion": 1}))
    monkeypatch.setattr(
        SessionManager, "_session_path",
        staticmethod(lambda v, e="default", o=1: ruta_sesion))
    monkeypatch.setattr(
        ac.AnnotationController, "_validate_session_quality",
        lambda self, s: (True, []))
    return ac, c


class TestElEstadoNoSeInventa:
    """El fallo original: una sola anotacion y el Hub ya decia
    «Completed». Johan queria decidirlo el."""

    def test_con_anotaciones_y_sin_marca_es_en_progreso(
            self, tmp_path, monkeypatch):
        ruta = _fichero(tmp_path, ["ATTACK"] * 50, concluido=False)
        ac, c = _controlador(monkeypatch, tmp_path, ruta)
        s = c._refresh_session_from_disk(_Sesion())
        assert s.status == "In Progress"

    def test_con_la_marca_es_completado(self, tmp_path, monkeypatch):
        ruta = _fichero(tmp_path, ["ATTACK"], concluido=True)
        ac, c = _controlador(monkeypatch, tmp_path, ruta)
        s = c._refresh_session_from_disk(_Sesion())
        assert s.status == "Completed"

    def test_vacio_sigue_pendiente(self, tmp_path, monkeypatch):
        ruta = _fichero(tmp_path, [], concluido=False)
        ac, c = _controlador(monkeypatch, tmp_path, ruta)
        s = c._refresh_session_from_disk(_Sesion())
        assert s.status == "Pending"

    def test_quitar_la_marca_baja_el_estado(self, tmp_path, monkeypatch):
        """Desmarcar tiene que verse: si el Hub se quedara en Completed
        el boton no serviria de nada."""
        ruta = _fichero(tmp_path, ["ATTACK"], concluido=True)
        ac, c = _controlador(monkeypatch, tmp_path, ruta)
        s = _Sesion()
        s.status = "Completed"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        datos["concluido"] = False
        ruta.write_text(json.dumps(datos), encoding="utf-8")
        assert c._refresh_session_from_disk(s).status == "In Progress"


# ======================================================================
# El menu del Hub
# ======================================================================

def _hub(estado="In Progress"):
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.project_hub import ProjectHubView
    cfg, _ = load_config("karate")
    h = ProjectHubView(cfg.colors, {"id": "karate", "name": "Karate"})
    s = _Sesion()
    s.status = estado
    h.set_sessions([s])
    return h


class TestElMenuOfreceLasDosCosas:
    def test_marcar_y_borrar_estan(self):
        h = _hub()
        _menu, acciones = h._construir_menu(0)
        textos = [a.text() for a in acciones]
        assert "Marcar como concluído" in textos
        assert "Apagar todas as anotações…" in textos

    def test_en_un_combate_terminado_ofrece_desmarcar(self):
        h = _hub("Completed")
        _menu, acciones = h._construir_menu(0)
        textos = [a.text() for a in acciones]
        assert "Desmarcar como concluído" in textos
        assert "Marcar como concluído" not in textos

    def test_cada_entrada_dispara_su_senal(self):
        h = _hub()
        _menu, acciones = h._construir_menu(0)
        por_texto = {a.text(): s for a, s in acciones.items()}
        assert por_texto["Marcar como concluído"] is h.marcar_concluido
        assert por_texto["Apagar todas as anotações…"] is h.borrar_anotaciones

    def test_no_hay_dos_entradas_iguales(self):
        h = _hub()
        _menu, acciones = h._construir_menu(0)
        textos = [a.text() for a in acciones]
        assert len(textos) == len(set(textos)), textos

    def test_sin_fila_no_revienta(self):
        """_construir_menu() se llama sin fila en los tests del menu."""
        h = _hub()
        _menu, acciones = h._construir_menu()
        assert "Marcar como concluído" in [a.text() for a in acciones]


class TestElControladorRespondeAlMenu:
    def test_las_senales_y_los_manejadores_existen(self):
        from karlos_core.controllers.annotation_controller import \
            AnnotationController as AC
        from karlos_core.views.project_hub import ProjectHubView
        for nombre in ("marcar_concluido", "borrar_anotaciones"):
            assert hasattr(ProjectHubView, nombre), nombre
        for nombre in ("_marcar_concluido", "_borrar_anotaciones",
                       "_limpiar_registro"):
            assert callable(getattr(AC, nombre, None)), nombre

    def test_marcar_alterna(self, tmp_path, monkeypatch):
        from karlos_core.controllers.session_manager import SessionManager
        ruta = _fichero(tmp_path, ["ATTACK"])
        ac, c = _controlador(monkeypatch, tmp_path, ruta)
        monkeypatch.setattr(SessionManager, "ruta_de_sesion",
                            staticmethod(lambda v: ruta))
        avisos = []
        c.window = type("W", (), {
            "set_status_message": lambda self, t: avisos.append(t),
            "project_hub": type("H", (), {
                "set_sessions": lambda self, s: None})()})()
        assert c._marcar_concluido(0) is True
        assert SessionManager.esta_concluido("/v/COMBATE.mp4") is True
        assert c.sessions[0].status == "Completed"
        assert c._marcar_concluido(0) is True
        assert SessionManager.esta_concluido("/v/COMBATE.mp4") is False
        assert c.sessions[0].status == "In Progress"

    def test_no_borra_el_combate_que_esta_abierto(self, tmp_path, monkeypatch):
        """Con el combate abierto la tabla en memoria volveria a
        escribirlo todo en el siguiente autoguardado."""
        from karlos_core.controllers.session_manager import SessionManager
        ruta = _fichero(tmp_path, ["ATTACK", "REFEREE STOP"])
        ac, c = _controlador(monkeypatch, tmp_path, ruta)
        monkeypatch.setattr(SessionManager, "ruta_de_sesion",
                            staticmethod(lambda v: ruta))
        c.active_session_idx = 0
        c.window = None
        visto = {}
        from PySide6.QtWidgets import QMessageBox
        monkeypatch.setattr(
            QMessageBox, "information",
            staticmethod(lambda *a, **k: visto.update(pedido=True)))
        assert c._borrar_anotaciones(0) == 0
        assert visto.get("pedido") is True
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert len(datos["annotations"]) == 2


# ======================================================================
# Borrar el combate abierto, con vuelta atras
# ======================================================================

class TestBorrarTodoSeDeshace:
    def _tabla(self):
        from karlos_core.utils.config_loader import load_config
        from karlos_core.views.annotations_table import \
            AnnotationsTableView
        cfg, _ = load_config("karate")
        t = AnnotationsTableView(cfg.colors)
        t.set_sport_id("karate")
        for a in (_anotacion("ATTACK"), _anotacion("REFEREE STOP", "Referee"),
                  _anotacion("TACTICS", "Feint")):
            t.add_annotation(a)
        return t

    def test_borra_todo_y_vuelve(self):
        from karlos_core.controllers.undo_commands import BorrarTodoCommand
        t = self._tabla()
        cmd = BorrarTodoCommand(t, False)
        cmd.redo()
        assert len(t.records) == 0
        cmd.undo()
        assert [r.category for r in t.records] == \
            ["ATTACK", "REFEREE STOP", "TACTICS"]

    def test_conserva_las_paradas(self):
        from karlos_core.controllers.undo_commands import BorrarTodoCommand
        t = self._tabla()
        cmd = BorrarTodoCommand(t, True)
        cmd.redo()
        assert [r.category for r in t.records] == ["REFEREE STOP"]
        cmd.undo()
        assert len(t.records) == 3

    def test_el_orden_se_respeta_al_deshacer(self):
        """Volver con el orden cambiado corromperia el eje de tiempos."""
        from karlos_core.controllers.undo_commands import BorrarTodoCommand
        t = self._tabla()
        antes = [r.technique for r in t.records]
        cmd = BorrarTodoCommand(t, False)
        cmd.redo()
        cmd.undo()
        assert [r.technique for r in t.records] == antes


class TestLimpiarElRegistroAbierto:
    def _controlador_abierto(self, monkeypatch, conservar):
        from karlos_core.controllers import annotation_controller as ac
        from karlos_core.utils.config_loader import load_config
        from karlos_core.views.annotations_table import \
            AnnotationsTableView
        from PySide6.QtGui import QUndoStack
        cfg, _ = load_config("karate")
        c = ac.AnnotationController.__new__(ac.AnnotationController)
        tabla = AnnotationsTableView(cfg.colors)
        tabla.set_sport_id("karate")
        for a in (_anotacion("ATTACK"), _anotacion("REFEREE STOP", "Referee"),
                  _anotacion("TACTICS", "Feint")):
            tabla.add_annotation(a)
        avisos = []
        c.window = type("W", (), {
            "table_view": tabla,
            "set_status_message": lambda self, t: avisos.append(t)})()
        c.undo_stack = QUndoStack()
        # El controlador de faltas real DERIVA de la tabla (desde el
        # 21-09-2026): el falso hace lo mismo, que es el contrato.
        from karlos_karate.csv_combate import es_sancion
        c.foul_controller = type("F", (), {
            "aka_fouls": property(lambda s2: sum(
                1 for r in tabla.records
                if es_sancion(r) and r.athlete == "AKA")),
            "ao_fouls": property(lambda s2: sum(
                1 for r in tabla.records
                if es_sancion(r) and r.athlete == "AO")),
            "resincronizar": lambda s2: 0,
        })()
        c.state_machine = type("S", (), {"reset": lambda self: None})()
        # Borrar todo tambien reinicia las pasadas (28-09-2026).
        c.fight_controller = type("P", (), {
            "reinicios": 0,
            "reiniciar": lambda s2: setattr(s2, "reinicios", s2.reinicios + 1),
        })()
        monkeypatch.setattr(ac.AnnotationController, "_update_timeline",
                            lambda self: None)
        monkeypatch.setattr(ac.AnnotationController, "_update_live_stats",
                            lambda self: None)
        monkeypatch.setattr(ac.AnnotationController, "_save_session",
                            lambda self: None)
        return c, tabla, avisos

    def test_borra_todo(self, monkeypatch):
        c, tabla, _ = self._controlador_abierto(monkeypatch, False)
        assert c._limpiar_registro(conservar_paradas=False) == 3
        assert len(tabla.records) == 0

    def test_conserva_las_paradas(self, monkeypatch):
        c, tabla, _ = self._controlador_abierto(monkeypatch, True)
        assert c._limpiar_registro(conservar_paradas=True) == 2
        assert [r.category for r in tabla.records] == ["REFEREE STOP"]

    def test_y_las_pasadas_vuelven_a_la_primera(self, monkeypatch):
        """Si no, la [F] siguiente seguia en la segunda pasada."""
        c, _tabla, _ = self._controlador_abierto(monkeypatch, False)
        c._limpiar_registro(conservar_paradas=False)
        assert c.fight_controller.reinicios == 1

    def test_las_faltas_vuelven_a_cero(self, monkeypatch):
        c, _tabla, _ = self._controlador_abierto(monkeypatch, False)
        c._limpiar_registro(conservar_paradas=False)
        assert c.foul_controller.aka_fouls == 0
        assert c.foul_controller.ao_fouls == 0

    def test_se_puede_deshacer(self, monkeypatch):
        c, tabla, _ = self._controlador_abierto(monkeypatch, False)
        c._limpiar_registro(conservar_paradas=False)
        c.undo_stack.undo()
        assert len(tabla.records) == 3

    def test_con_el_registro_vacio_no_hace_nada(self, monkeypatch):
        c, tabla, avisos = self._controlador_abierto(monkeypatch, False)
        tabla.clear_all()
        assert c._limpiar_registro(conservar_paradas=False) == 0
        assert avisos and "Não há anotações" in avisos[-1]

    def test_el_registro_breve_ofrece_la_entrada(self):
        from karlos_core.views.log_compacto import LogCompacto
        assert hasattr(LogCompacto, "limpiar_pedida")
