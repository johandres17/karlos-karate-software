"""Tests de la navegacion con [Tab] entre las anotaciones propias.

[Tab] recorre lo que el evaluador ya anoto, por posicion en el video.
"""

from __future__ import annotations

import pytest

from karlos_core.controllers.annotation_controller import \
    siguiente_anotacion
from karlos_core.models.annotation import Annotation


def anot(f, quien="AKA", cat="ATTACK", tec="Gyaku Tsuki"):
    return Annotation(athlete=quien, category=cat,
                      subcategory="HAND TECHNIQUES", technique=tec,
                      f_start=f, f_end=f + 20)


@pytest.fixture
def combate():
    return [anot(100), anot(500, "AO"), anot(900), anot(1400, "AO")]


class TestNavegarPorLoAnotado:
    def test_avanza_a_la_siguiente(self, combate):
        assert siguiente_anotacion(combate, 300, +1).f_start == 500

    def test_retrocede_a_la_anterior(self, combate):
        assert siguiente_anotacion(combate, 600, -1).f_start == 500

    def test_desde_el_principio_va_a_la_primera(self, combate):
        assert siguiente_anotacion(combate, 0, +1).f_start == 100

    def test_al_final_no_hay_siguiente(self, combate):
        assert siguiente_anotacion(combate, 5000, +1) is None

    def test_al_principio_no_hay_anterior(self, combate):
        assert siguiente_anotacion(combate, 0, -1) is None

    def test_sin_anotaciones_no_rompe(self):
        assert siguiente_anotacion([], 100, +1) is None
        assert siguiente_anotacion([], 100, -1) is None

    def test_no_se_queda_atrapado_en_la_actual(self, combate):
        """Estando justo encima de una, [Tab] tiene que pasar a la que
        viene: si no, se queda clavado y hay que mover el video a mano."""
        assert siguiente_anotacion(combate, 500, +1).f_start == 900
        assert siguiente_anotacion(combate, 500, -1).f_start == 100

    def test_el_orden_de_llegada_no_importa(self):
        """Editar una anotacion la manda al final de la lista, y [Tab]
        tiene que seguir yendo por el video, no por la lista."""
        desordenadas = [anot(900), anot(100), anot(500)]
        assert siguiente_anotacion(desordenadas, 200, +1).f_start == 500

    def test_recorre_los_dos_atletas(self, combate):
        """El evaluador anota a los dos: [Tab] los recorre a los dos y
        no filtra por el que este seleccionado."""
        vistos = []
        pos = 0
        while (a := siguiente_anotacion(combate, pos, +1)) is not None:
            vistos.append(a.athlete)
            pos = a.f_start
        assert vistos == ["AKA", "AO", "AKA", "AO"]


class TestLasParadasNoSonAcciones:
    def test_se_salta_la_parada_del_arbitro(self):
        """No son acciones del atleta: pasar por ellas obligaria a dar
        un [Tab] de mas en cada una, y en ID30 hay veinticuatro."""
        acciones = [anot(100), anot(500, cat="REFEREE STOP", tec="Referee"),
                    anot(900)]
        assert siguiente_anotacion(acciones, 200, +1).f_start == 900

    def test_tampoco_al_retroceder(self):
        acciones = [anot(100), anot(500, cat="REFEREE STOP", tec="Referee"),
                    anot(900)]
        assert siguiente_anotacion(acciones, 800, -1).f_start == 100

    def test_una_falta_si_se_recorre(self):
        """Una sancion es un hecho del combate que el evaluador querra
        revisar."""
        acciones = [anot(100), anot(500, cat="PENALTY", tec="Chui (1st)")]
        assert siguiente_anotacion(acciones, 200, +1).f_start == 500


