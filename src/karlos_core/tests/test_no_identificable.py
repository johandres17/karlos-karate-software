"""«Não identificável»: lo que se ve pasar pero no se deja leer.

Salió anotando de verdad: el árbitro se cruza, el atleta sale del
encuadre, la espalda del rival tapa la técnica. Sin esta salida el
evaluador tenía que elegir entre inventar una técnica o borrar el
momento, y las dos cosas estropean el dato. Cuánto hay de esto en un
combate, y por qué, es un resultado del estudio y no una pérdida.
"""

from __future__ import annotations

import pytest

from karlos_karate.guided_tree import ArbolGuiado


class TestElRecorrido:
    def test_esta_en_la_raiz_y_se_teclea_con_el_cero(self):
        p = ArbolGuiado().paso_actual()
        claves = [k for _, k in p.opciones]
        assert claves[-1] == "no_ident"
        assert len(p.opciones) == 10, "la décima es la tecla 0"

    def test_pregunta_el_motivo_y_nada_mas(self):
        """Sin nivel, guardia ni contexto: si no se lee la técnica,
        tampoco sus atributos, y ofrecerlos invita a rellenarlos a ojo."""
        a = ArbolGuiado()
        a.elegir("no_ident")
        p = a.paso_actual()
        assert p is not None and len(p.opciones) == 7
        assert not a.completa
        a.elegir("Mot:Referee")
        assert a.completa and a.paso_actual() is None

    @pytest.mark.parametrize("clave,motivo", [
        ("Mot:Referee", "Referee"), ("Mot:OutOfFrame", "OutOfFrame"),
        ("Mot:Occluded", "Occluded"), ("Mot:CameraCut", "CameraCut"),
        ("Mot:TooFast", "TooFast"), ("Mot:VideoFault", "VideoFault"),
        ("Mot:Other", "Other"),
    ])
    def test_cada_motivo_llega_al_registro(self, clave, motivo):
        a = ArbolGuiado()
        a.elegir("no_ident")
        a.elegir(clave)
        tecnica, nivel, categoria, grupo = a.resultado()
        assert tecnica == "Unidentifiable"
        assert nivel == f"Reason: {motivo}"
        assert categoria == grupo == "UNIDENTIFIED"

    def test_se_puede_volver_atras(self):
        a = ArbolGuiado()
        a.elegir("no_ident")
        a.elegir("Mot:Occluded")
        a.retroceder()
        assert a.motivo is None and not a.completa
        a.retroceder()
        assert a.tecnica is None
        assert a.paso_actual().opciones[0][1] == "finta_sup"

    def test_otro_motivo_pide_escribirlo(self):
        a = ArbolGuiado()
        a.elegir("no_ident")
        a.elegir("Mot:Other")
        assert a.pide_motivo_escrito
        b = ArbolGuiado()
        b.elegir("no_ident")
        b.elegir("Mot:Referee")
        assert not b.pide_motivo_escrito

    def test_no_es_lo_mismo_que_descartar(self):
        """Descartar tira el momento; esto lo registra."""
        a = ArbolGuiado(); a.elegir("no_ident"); a.elegir("Mot:Referee")
        assert a.no_identificable and not a.descartada
        b = ArbolGuiado(); b.elegir("descartar")
        assert b.descartada and not b.no_identificable


class TestElMotivoLlegaAlFinal:
    def test_la_cadena_se_vuelve_a_leer(self):
        from karlos_core.utils.merge_utils import parse_combined_level
        assert parse_combined_level("Reason: Occluded")["reason"] == "Occluded"

    def test_tiene_columna_propia_en_el_registro(self):
        from karlos_karate import csv_combate
        assert "reason" in csv_combate.COLUMNAS
        assert ("reason", "reason") in csv_combate._EXTRA

    def test_la_tecnica_existe_en_la_taxonomia(self):
        from karlos_core.utils.config_loader import load_config
        cfg, _ = load_config("karate")
        nombres = [t.name for t in cfg.techniques]
        assert "Unidentifiable" in nombres

    def test_no_lleva_nivel(self):
        """Si no se identifica la técnica, tampoco sus atributos."""
        from karlos_core.utils.config_loader import load_config
        cfg, _ = load_config("karate")
        t = next(t for t in cfg.techniques if t.name == "Unidentifiable")
        assert t.category == "UNIDENTIFIED" and t.group == "UNIDENTIFIED"
        assert not t.has_level

    def test_no_mueve_el_marcador_ni_la_escalera_de_faltas(self):
        """Una acción que no se lee no puede puntuar ni sancionar."""
        from karlos_karate.csv_combate import es_sancion
        from karlos_core.controllers.foul_controller import (
            sanciones_por_competidor,
        )
        from karlos_core.models.annotation import Annotation
        a = Annotation(
            athlete="AO", category="UNIDENTIFIED",
            subcategory="UNIDENTIFIED", technique="Unidentifiable",
            level="Reason: Occluded", score="NONE",
            f_start=1070, f_end=1080,
            sport_specific_data={"reason": "Occluded"})
        assert not es_sancion(a)
        assert sanciones_por_competidor([a]) == (0, 0)
        assert a.score == "NONE"


class TestElPanelDaTeclaALaDecima:
    def test_el_cero_devuelve_la_decima(self):
        from karlos_core.views.guided_panel import GuidedPanel
        import inspect
        fuente = inspect.getsource(GuidedPanel.clave_de)
        assert "numero == 0" in fuente
        assert "self._claves[9]" in fuente
