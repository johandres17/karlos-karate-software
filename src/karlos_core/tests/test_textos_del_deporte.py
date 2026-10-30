"""Los textos del deporte, aparte de los del programa (fase F3.6).

El árbol de preguntas del karate y su identidad («Karlitos WKF 2026»)
estaban en el diccionario del programa. Ahora los trae el karate y tienen
preferencia: ``I18n.t`` mira primero los textos del deporte que se anota.
Con el karate, todo se lee exactamente como en la 1.0 (comprobado clave a
clave en los seis idiomas al hacer el cambio).
"""
from __future__ import annotations

from karlos_core.utils.i18n import I18n
from karlos_core import catalogo


class _SinTextos:
    def textos(self):
        return {}


class _ConTextos:
    def textos(self):
        return {"hub.col_score": {"es": "MARCADOR", "en": "BOARD"}}


def test_el_programa_ya_no_trae_el_arbol_del_karate():
    """Solo quedan los motivos de «Não identificável», que son suyos."""
    del_arbol = [k for k in I18n._STRINGS if k.startswith("tree.")]
    assert del_arbol and all(k.startswith("tree.m_") for k in del_arbol), del_arbol


def test_el_karate_trae_su_arbol_y_su_identidad():
    textos = catalogo.paquete("karate").textos()
    assert "tree.q_accion" in textos and "tree.f_jogai" in textos
    assert "WKF 2026" in textos["bout.window_title"]["es"]
    assert not any(k.startswith("tree.m_") for k in textos)


def test_los_textos_del_deporte_van_primero(monkeypatch):
    i = I18n()
    monkeypatch.setattr(i, "_lang", "es")
    assert i.t("hub.col_score") == "PUNTOS"
    monkeypatch.setattr(catalogo, "activo", lambda: _ConTextos())
    assert i.t("hub.col_score") == "MARCADOR"
    # En un idioma que el deporte no trae, su inglés antes que el programa.
    monkeypatch.setattr(i, "_lang", "pt")
    assert i.t("hub.col_score") == "BOARD"


def test_sin_el_karate_el_dialogo_del_combate_es_neutro(monkeypatch):
    i = I18n()
    monkeypatch.setattr(i, "_lang", "es")
    assert i.t("bout.window_title") == "Información del Combate — Karlitos WKF 2026"
    monkeypatch.setattr(catalogo, "activo", lambda: _SinTextos())
    assert i.t("bout.window_title") == "Información del Combate"
    assert i.t("bout.subtitle") == "Registro Elite de Combate"
    assert i.t("tree.q_accion") == "tree.q_accion", "el árbol es del karate"
    assert i.t("tree.m_arbitro") != "tree.m_arbitro", "los motivos son del programa"
