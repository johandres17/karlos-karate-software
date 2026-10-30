"""Tests de completar un ataque ya anotado desde la pantalla de edicion.

Dos cosas se vigilan aqui. Que se puedan poner el contacto y el
contexto, que el arbol pregunta y esta pantalla no dejaba corregir; y
que editar NO se lleve por delante la guardia, que es lo que hacia
antes en silencio.
"""

from __future__ import annotations

import pytest

from karlos_core.models.annotation import Annotation


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def config():
    from karlos_core.utils.config_loader import load_config
    cfg, _ = load_config("karate")
    return cfg


def _ataque(**kw):
    base = dict(athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
                technique="Gyaku Tsuki", level="Chudan", f_start=219, f_end=279,
                sport_specific_data={"base_technique": "Tsuki",
                                     "stance": "Rear",
                                     "sequence_id": "SEQ_001"})
    base.update(kw)
    return Annotation(**base)


def _popup(cfg, anotacion):
    from karlos_core.views.edit_annotation_popup import EditAnnotationPopup
    return EditAnnotationPopup(annotation=anotacion, config=cfg,
                               colors=cfg.colors, sport_id="karate", fps=30.0)


class TestSePuedeCompletar:
    def test_ofrece_contacto_y_contexto(self, config):
        p = _popup(config, _ataque())
        assert p._contact_combo is not None
        assert p._context_combo is not None
        assert "Score" in [p._contact_combo.itemText(i)
                           for i in range(p._contact_combo.count())]
        assert "Touch" not in [p._contact_combo.itemText(i)
                               for i in range(p._contact_combo.count())], \
            "'Toco' se quito: no se observa con fiabilidad"
        assert "Counter" in [p._context_combo.itemText(i)
                             for i in range(p._context_combo.count())]

    def test_lo_elegido_se_guarda(self, config):
        p = _popup(config, _ataque())
        p._contact_combo.setCurrentText("Score")
        p._context_combo.setCurrentText("Counter")
        p._on_save()
        assert p.edited.sport_specific_data["contact"] == "Score"
        assert p.edited.sport_specific_data["action_type"] == "Counter"

    def test_lo_que_ya_habia_aparece_marcado(self, config):
        p = _popup(config, _ataque(sport_specific_data={"contact": "NoScore",
                                                        "action_type": "Direct"}))
        assert p._contact_combo.currentText() == "NoScore"
        assert p._context_combo.currentText() == "Direct"

    def test_dejarlo_vacio_lo_quita(self, config):
        p = _popup(config, _ataque(sport_specific_data={"contact": "Score"}))
        p._contact_combo.setCurrentText("")
        p._on_save()
        assert "contact" not in p.edited.sport_specific_data


class TestNoSePierdeLoQueYaEstaba:
    def test_editar_no_borra_la_guardia(self, config):
        """Lo que hacia antes: se editaba para arreglar otra cosa y la
        guardia desaparecia sin avisar."""
        p = _popup(config, _ataque())
        p._contact_combo.setCurrentText("Touch")
        p._on_save()
        assert p.edited.sport_specific_data.get("stance") == "Rear"

    def test_editar_no_borra_la_secuencia_ni_la_tecnica_base(self, config):
        p = _popup(config, _ataque())
        p._on_save()
        d = p.edited.sport_specific_data
        assert d.get("sequence_id") == "SEQ_001"
        assert d.get("base_technique") == "Tsuki"

    def test_una_accion_que_no_es_ataque_no_pide_contacto(self, config):
        """Una finta o una esquiva no tienen contacto que declarar."""
        p = _popup(config, _ataque(category="TACTICS", subcategory="TACTICS",
                                   technique="Feint", level="Upper Limb"))
        assert p._contact_combo is None
        p._on_save()
        assert "contact" not in p.edited.sport_specific_data
