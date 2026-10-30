"""La escalera de faltas WKF 2026: la cuenta ES la tabla.

Reescrito el 21-09-2026 tras el bug que encontró Johan anotando: el
controlador llevaba contadores propios que solo sabían sumar, así que
borrar unas faltas anotadas por error no los bajaba y la siguiente
salía con grado de HANSOKU-CHUI. Ahora la cuenta se DERIVA de la tabla
con la regla del CSV (es_sancion), y estos tests protegen exactamente
ese escenario y sus vecinos: borrar, deshacer, editar, insertar hacia
atrás, y la falta ligada a un ataque.
"""

from __future__ import annotations

import pytest

from karlos_core.controllers.foul_controller import FoulController
from karlos_core.models.annotation import Annotation
from karlos_core import catalogo


# ══════════════════════════════════════════════════════════════════
# La escalera oficial
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("count, expected", [
    (1, "CHUI-1"), (2, "CHUI-2"), (3, "CHUI-3"),
    (4, "HANSOKU-CHUI"), (5, "HANSOKU"), (10, "HANSOKU"),
])
def test_escalera_wkf_2026(count, expected):
    assert catalogo.paquete("karate").reglamento.grado(count) == expected


# ══════════════════════════════════════════════════════════════════
# Un arnés real en miniatura: tabla y pila de deshacer que ejecutan
# de verdad, nada de contadores que puedan mentir.
# ══════════════════════════════════════════════════════════════════


class _Tabla:
    """Lo mínimo de AnnotationsTable que usa el controlador."""

    def __init__(self):
        self.records = []

    def add_annotation(self, a):
        self.records.append(a)

    def remove_row(self, i):
        del self.records[i]

    def replace_record(self, i, a):
        self.records[i] = a


class _Pila:
    """Pila de deshacer que ejecuta, como QUndoStack."""

    def __init__(self):
        self._hechos = []

    def push(self, cmd):
        cmd.redo()
        self._hechos.append(cmd)

    def undo(self):
        if self._hechos:
            self._hechos.pop().undo()


class _Cosa:
    """Objeto con atributos; lo que no se defina, traga y calla."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, _n):
        return lambda *a, **k: None


def _controlador(atleta="AO", frame=100):
    tabla = _Tabla()
    fc = FoulController(
        table_view=tabla,
        undo_stack=_Pila(),
        window=_Cosa(),
        annotation_panel=_Cosa(athlete=atleta),
        video_manager=_Cosa(current_frame=frame, fight_start=0,
                            fight_end=9000,
                            fight_duration_s=lambda: 120.0),
        bout_info={"current_round": 1},
    )
    return fc, tabla


def _sancion_en_ataque(atleta, f):
    """Un ataque que acabó en falta: la sanción viaja EN su fila."""
    return Annotation(
        athlete=atleta, category="ATTACK", subcategory="",
        technique="Gyaku Tsuki", level="Jodan", score="NONE",
        f_start=f, f_end=f + 10, duration_s=0.3, round=1,
        sport_specific_data={"sanction": "Contact"},
    )


# ══════════════════════════════════════════════════════════════════
# El escenario de Johan, exacto
# ══════════════════════════════════════════════════════════════════


class TestBorrarYReanotar:
    def test_borrar_faltas_baja_la_cuenta(self):
        fc, tabla = _controlador("AO")
        for _ in range(3):
            fc.register_foul("Contact")
        assert fc.get_count("AO") == 3

        tabla.records.clear()          # el usuario borra sus errores
        assert fc.get_count("AO") == 0, \
            "borrar las anotaciones tiene que borrar la cuenta"

    def test_reanotar_tras_borrar_empieza_en_chui_1(self):
        """El bug literal: 3 faltas por error, borradas, y la nueva
        salía como si fuera la cuarta."""
        fc, tabla = _controlador("AO")
        for _ in range(3):
            fc.register_foul("Contact")
        tabla.records.clear()

        fc.register_foul("Contact")
        assert len(tabla.records) == 1
        assert tabla.records[0].technique == "CHUI-1", \
            f"tras borrar todo, la primera es CHUI-1, no {tabla.records[0].technique}"

    def test_deshacer_una_falta_baja_la_cuenta(self):
        fc, tabla = _controlador("AKA", frame=50)
        fc.register_foul("Contact")
        fc.register_foul("Target")
        assert fc.get_count("AKA") == 2
        fc._undo_stack.undo()
        assert fc.get_count("AKA") == 1

    def test_hansoku_fantasma_desaparece(self):
        fc, tabla = _controlador("AO")
        for _ in range(5):
            fc.register_foul("Contact")
        assert fc.ya_descalificado("AO")
        tabla.records.clear()
        assert not fc.ya_descalificado("AO"), \
            "sin anotaciones no hay descalificación que valga"


# ══════════════════════════════════════════════════════════════════
# La resincronización de grados
# ══════════════════════════════════════════════════════════════════


class TestResincronizar:
    def test_borrar_la_de_en_medio_reetiqueta(self):
        fc, tabla = _controlador("AKA")
        for f in (100, 200, 300):
            fc._vm.current_frame = f
            fc.register_foul("Contact")
        assert [r.technique for r in tabla.records] == \
            ["CHUI-1", "CHUI-2", "CHUI-3"]

        tabla.remove_row(1)            # fuera la CHUI-2
        corregidas = fc.resincronizar()
        assert corregidas == 1
        assert [r.technique for r in tabla.records] == \
            ["CHUI-1", "CHUI-2"], "la que era tercera pasa a segunda"

    def test_insertar_hacia_atras_recoloca_las_posteriores(self):
        fc, tabla = _controlador("AKA")
        for f in (200, 300):
            fc._vm.current_frame = f
            fc.register_foul("Contact")
        # una falta olvidada, anotada después pero anterior en el vídeo
        fc._vm.current_frame = 100
        fc.register_foul("Target")
        en_orden = sorted(tabla.records, key=lambda r: r.f_start)
        assert [r.technique for r in en_orden] == \
            ["CHUI-1", "CHUI-2", "CHUI-3"]

    def test_editar_el_atleta_recoloca_ambas_escaleras(self):
        fc, tabla = _controlador("AKA")
        for f in (100, 200):
            fc._vm.current_frame = f
            fc.register_foul("Contact")
        # la segunda era de AO en realidad
        tabla.records[1].athlete = "AO"
        fc.resincronizar()
        assert tabla.records[1].technique == "CHUI-1"
        assert fc.get_count("AKA") == 1 and fc.get_count("AO") == 1


# ══════════════════════════════════════════════════════════════════
# La falta que viaja dentro del ataque
# ══════════════════════════════════════════════════════════════════


class TestSancionLigadaAlAtaque:
    def test_cuenta_peldano_sin_fila_propia(self):
        fc, tabla = _controlador("AO")
        tabla.add_annotation(_sancion_en_ataque("AO", 50))
        assert fc.get_count("AO") == 1

        fc._vm.current_frame = 200
        fc.register_foul("Contact")
        assert tabla.records[-1].technique == "CHUI-2", \
            "la ligada al ataque ya subió un peldaño"

    def test_borrar_el_ataque_sancionado_baja_la_cuenta(self):
        fc, tabla = _controlador("AO")
        tabla.add_annotation(_sancion_en_ataque("AO", 50))
        fc._vm.current_frame = 200
        fc.register_foul("Contact")
        tabla.remove_row(0)            # fuera el ataque con sanción
        fc.resincronizar()
        assert fc.get_count("AO") == 1
        assert tabla.records[0].technique == "CHUI-1"

    def test_resincronizar_no_rotula_la_fila_del_ataque(self):
        fc, tabla = _controlador("AO")
        tabla.add_annotation(_sancion_en_ataque("AO", 50))
        fc.resincronizar()
        assert tabla.records[0].technique == "Gyaku Tsuki", \
            "el ataque conserva su técnica; el grado no pisa la fila"


# ══════════════════════════════════════════════════════════════════
# Las propiedades derivadas que consume el resto del programa
# ══════════════════════════════════════════════════════════════════


class TestPropiedadesDerivadas:
    def test_aka_y_ao_salen_de_la_tabla(self):
        fc, tabla = _controlador("AKA")
        fc.register_foul("Contact")
        fc._ap.athlete = "AO"
        fc._vm.current_frame = 300
        fc.register_foul("Target")
        fc.register_foul("Procedure")
        assert (fc.aka_fouls, fc.ao_fouls) == (1, 2)

    def test_registro_guarda_categoria_penalty(self):
        fc, tabla = _controlador("AKA")
        fc.register_foul("Illegal Tech")
        a = tabla.records[0]
        assert a.category == "PENALTY"
        assert a.subcategory == "Illegal Tech"
        assert a.f_start == a.f_end == 100


# ══════════════════════════════════════════════════════════════════
# Export: Most Used Technique excluye PENALTY (se conserva del
# archivo anterior: no dependía de los contadores)
# ══════════════════════════════════════════════════════════════════

def test_most_used_excludes_penalty() -> None:
    """Verify that _most_used() does NOT count PENALTY annotations."""
    from karlos_karate.export_manager import ExportManager

    penalty_records = [
        Annotation(
            athlete="AKA", category="PENALTY", subcategory="Contact",
            technique="CHUI-1", f_start=10, f_end=20, duration_s=0.5,
            round=1,
        ),
        Annotation(
            athlete="AKA", category="PENALTY", subcategory="Target",
            technique="CHUI-2", f_start=30, f_end=40, duration_s=0.5,
            round=1,
        ),
    ]
    real_techniques = [
        Annotation(
            athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
            technique="Gyaku-tsuki", level="Jodan", score="IPPON",
            f_start=110, f_end=130, duration_s=0.5, round=1,
        ),
        Annotation(
            athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
            technique="Gyaku-tsuki", level="Chudan", score="WAZA",
            f_start=140, f_end=160, duration_s=0.5, round=1,
        ),
        Annotation(
            athlete="AKA", category="ATTACK", subcategory="FOOT TECHNIQUES",
            technique="Mawashi-geri", level="Jodan", score="YUKO",
            f_start=170, f_end=190, duration_s=0.5, round=1,
        ),
    ]
    all_records = penalty_records + real_techniques
    filtered_records = [r for r in all_records if r.category != "PENALTY"]
    filtered_top = ExportManager._most_used(filtered_records)
    assert filtered_top == "Gyaku-tsuki"
    assert filtered_top not in {"CHUI-1", "CHUI-2", "CHUI-3",
                                "HANSOKU-CHUI", "HANSOKU"}


def test_most_used_empty_records() -> None:
    from karlos_karate.export_manager import ExportManager
    assert ExportManager._most_used([]) == ""


def test_most_used_only_penalty() -> None:
    from karlos_karate.export_manager import ExportManager
    records = [
        Annotation(
            athlete="AKA", category="PENALTY", subcategory="Contact",
            technique="CHUI-1", f_start=10, f_end=20, duration_s=0.5,
            round=1,
        ),
    ]
    filtered = [r for r in records if r.category != "PENALTY"]
    assert ExportManager._most_used(filtered) == ""
