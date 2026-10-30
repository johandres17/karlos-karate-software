"""Tests del aviso cuando hay acciones fuera del combate declarado.

Las anotaciones son la verdad y los limites del combate una ayuda, asi
que esto enseña el desajuste en vez de corregirlo por su cuenta.
"""

from __future__ import annotations

import pytest

from karlos_core.controllers.annotation_controller import \
    AnnotationController as AC
from karlos_core.models.annotation import Annotation


def _a(f_start, f_end):
    return Annotation(athlete="AKA", category="ATTACK",
                      subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki",
                      f_start=f_start, f_end=f_end)


class TestQueSeConsideraFuera:
    def test_dentro_no_avisa(self):
        assert AC.acciones_fuera_del_combate([_a(200, 300)], 100, 1000) == []

    def test_una_accion_posterior(self):
        fuera = AC.acciones_fuera_del_combate([_a(200, 300), _a(1100, 1200)],
                                              100, 1000)
        assert [a.f_start for a in fuera] == [1100]

    def test_una_accion_anterior(self):
        fuera = AC.acciones_fuera_del_combate([_a(50, 80), _a(200, 300)],
                                              100, 1000)
        assert [a.f_start for a in fuera] == [50]

    def test_una_que_empieza_dentro_y_acaba_fuera(self):
        """Lo que pasa con la ultima parada del arbitro en ID30."""
        fuera = AC.acciones_fuera_del_combate([_a(900, 1100)], 100, 1000)
        assert len(fuera) == 1

    def test_justo_en_los_bordes_esta_dentro(self):
        assert AC.acciones_fuera_del_combate([_a(100, 1000)], 100, 1000) == []

    def test_sin_combate_declarado_no_avisa(self):
        """Antes de analizar no hay rango contra el que comparar."""
        assert AC.acciones_fuera_del_combate([_a(200, 300)], None, None) == []
        assert AC.acciones_fuera_del_combate([_a(200, 300)], 100, None) == []

    def test_sin_anotaciones(self):
        assert AC.acciones_fuera_del_combate([], 100, 1000) == []

    def test_el_caso_de_ID30(self):
        """Ocho acciones despues del fin que el reloj detecto."""
        anotaciones = [_a(f, f + 10) for f in
                       (11209, 11529, 11779, 11783, 11788, 11793, 11796,
                        11798, 11801)]
        fuera = AC.acciones_fuera_del_combate(anotaciones, 155, 11189)
        assert len(fuera) == 9
        assert max(a.f_end for a in fuera) == 11811
