"""Editar una anotacion solo cambia lo que se toca.

Lo que pasaba hasta la 6.14.12 (visto el 28-09-2026): la ventana de
edicion arrancaba cada desplegable con `setCurrentText`, y un QComboBox
que no encuentra el texto se queda en el primero de su lista. Al guardar
se escribia lo que mostraba. Abriendo y guardando sin tocar nada, sobre
las 255 filas de las sesiones de Johan:

- las 8 faltas pasaban a ser un ATTACK sin tecnica, con IPPON;
- las 76 fintas perdian el miembro;
- 44 paradas perdian su tipo (Injury pasaba a «Referee Stop»);
- 49 ataques perdian su nombre por guardia (Gyaku Tsuki -> Tsuki,
  Kizami Mae Geri -> Mawashi Geri) y 10 su nivel.

Y la ventana se usa: un evaluador editaba ataques para ponerles el punto.
"""

from __future__ import annotations

import dataclasses
import glob
import json
import os
from pathlib import Path

import pytest

from karlos_core.models.annotation import Annotation


@pytest.fixture(scope="module")
def config():
    from karlos_core.utils.config_loader import load_config
    cfg, _ = load_config("karate")
    return cfg


def _popup(cfg, anotacion):
    from karlos_core.views.edit_annotation_popup import EditAnnotationPopup
    return EditAnnotationPopup(annotation=anotacion, config=cfg, colors=cfg.colors,
                               sport_id="karate", fps=30.0)


def _fila(**kw) -> Annotation:
    base = dict(athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
                technique="Gyaku Tsuki", level="Jodan", score="NONE",
                f_start=1200, f_end=1230, duration_s=1.0, round=1,
                notes="", sport_specific_data={})
    base.update(kw)
    return Annotation(**base)


def _diferencias(a: Annotation, b: Annotation) -> dict:
    return {f.name: (getattr(a, f.name), getattr(b, f.name))
            for f in dataclasses.fields(a) if getattr(a, f.name) != getattr(b, f.name)}


def _guardar(cfg, anotacion, tocar=None) -> Annotation:
    p = _popup(cfg, anotacion)
    if tocar:
        tocar(p)
    p._on_save()
    assert p.edited is not None
    return p.edited


ATAQUE = {"base_technique": "Tsuki", "stance": "Rear", "action_type": "Direct",
          "contact": "NoScore", "sequence_id": "SEQ_004"}

# Cada forma de fila que el programa guarda, sacadas de las sesiones reales.
FORMAS = {
    "gyaku tsuki": _fila(sport_specific_data=dict(ATAQUE)),
    "kizami tsuki": _fila(technique="Kizami Tsuki", level="Chudan",
                          sport_specific_data=dict(ATAQUE, stance="Lead")),
    "kizami mawashi": _fila(subcategory="FOOT TECHNIQUES", technique="Kizami Mawashi",
                            sport_specific_data={"base_technique": "Mawashi Geri",
                                                 "stance": "Lead", "action_type": "Counter"}),
    "kizami mae geri": _fila(subcategory="FOOT TECHNIQUES", technique="Kizami Mae Geri",
                             level="Chudan", score="WAZA",
                             sport_specific_data={"base_technique": "Mae Geri",
                                                  "stance": "Lead"}),
    "mawashi atrasada": _fila(subcategory="FOOT TECHNIQUES", technique="Mawashi Geri",
                              sport_specific_data={"stance": "Rear", "contact": "Score"}),
    "uraken": _fila(technique="Uraken", sport_specific_data={"stance": "Lead"}),
    "con sancion": _fila(sport_specific_data=dict(ATAQUE, sanction="Contact")),
    "punto puesto": _fila(score="YUKO", sport_specific_data={"base_technique": "Tsuki",
                                                             "action_type": "Direct"}),
    "barrido": _fila(subcategory="SWEEPS & TAKEDOWNS", technique="Ashi-barai", level="",
                     sport_specific_data={"action_type": "Direct", "contact": "NoScore"}),
    "barrido antiguo": _fila(subcategory="SWEEPS & TAKEDOWNS", technique="Ashi-barai",
                             level="Action: Direct | Contact: Miss",
                             sport_specific_data={"action_type": "Direct", "contact": "Miss"}),
    "derribo": _fila(subcategory="SWEEPS & TAKEDOWNS", technique="Takedown", level=""),
    "finta alta": _fila(category="TACTICS", subcategory="TACTICS", technique="Feint",
                        level="Upper Limb"),
    "finta baja": _fila(category="TACTICS", subcategory="TACTICS", technique="Feint",
                        level="Lower Limb"),
    "clinch": _fila(category="TACTICS", subcategory="TACTICS", technique="Clinch", level=""),
    "esquiva": _fila(category="DEFENSE", subcategory="BLOCKS & EVASIONS",
                     technique="Dodge", level=""),
    "bloqueo": _fila(category="DEFENSE", subcategory="BLOCKS & EVASIONS",
                     technique="Hand Block", level=""),
    "no identificable": _fila(category="UNIDENTIFIED", subcategory="UNIDENTIFIED",
                              technique="Unidentifiable", level="Reason: Referee",
                              sport_specific_data={"reason": "Referee"}),
    "parada": _fila(category="REFEREE STOP", subcategory="MATCH STATES",
                    technique="Referee", level=""),
    "parada lesion": _fila(category="REFEREE STOP", subcategory="MATCH STATES",
                           technique="Injury", level="", athlete="AO"),
    "parada antigua": _fila(category="REFEREE STOP", subcategory="REFEREE STOP",
                            technique="Referee Stop - Referee", level="", score=""),
    "falta": _fila(category="PENALTY", subcategory="Clinching", technique="CHUI-2",
                   level="", score=""),
    "hansoku": _fila(category="PENALTY", subcategory="Passivity", technique="HANSOKU-CHUI",
                     level="", score="", athlete="AO"),
    "con notas": _fila(notes="entro limpio\n"),
}


@pytest.mark.parametrize("forma", list(FORMAS))
def test_abrir_y_guardar_sin_tocar_no_cambia_nada(config, forma):
    original = FORMAS[forma]
    assert _diferencias(original, _guardar(config, original)) == {}


SESIONES = (os.environ.get("KARLOS_VIDEOS", "/nonexistent/karlos_videos") + "/.karlos_sessions/")


def test_y_con_todas_las_filas_de_las_sesiones_de_verdad(config):
    from karlos_core.controllers.session_manager import SessionManager
    archivos = sorted(glob.glob(SESIONES + "*.karlos"))
    if not archivos:
        pytest.skip("sin las sesiones")
    cambiadas = []
    for ruta in archivos:
        for d in json.loads(Path(ruta).read_text(encoding="utf-8")).get("annotations") or []:
            a = SessionManager.annotation_from_dict(d)
            dif = _diferencias(a, _guardar(config, a))
            if dif:
                cambiadas.append((Path(ruta).name[:20], a.technique, dif))
    assert not cambiadas, cambiadas[:5]


# ── lo que si se toca ────────────────────────────────────────────────

def test_poner_el_punto_solo_pone_el_punto(config):
    """Lo que hacia un evaluador: y el ataque dejaba de ser Gyaku Tsuki."""
    original = FORMAS["gyaku tsuki"]
    editada = _guardar(config, original, lambda p: p._score_combo.setCurrentText("YUKO"))
    assert _diferencias(original, editada) == {"score": ("NONE", "YUKO")}


def test_otra_guardia_es_otro_nombre(config):
    original = FORMAS["gyaku tsuki"]
    editada = _guardar(config, original,
                       lambda p: p._dim_combos["Stance"].setCurrentText("Lead"))
    assert editada.technique == "Kizami Tsuki"
    assert editada.sport_specific_data["stance"] == "Lead"
    assert editada.sport_specific_data["base_technique"] == "Tsuki"
    assert set(_diferencias(original, editada)) == {"technique", "sport_specific_data"}


def test_una_mawashi_que_pasa_a_atrasada_pierde_el_kizami(config):
    editada = _guardar(config, FORMAS["kizami mawashi"],
                       lambda p: p._dim_combos["Stance"].setCurrentText("Rear"))
    assert editada.technique == "Mawashi Geri"
    assert "base_technique" not in editada.sport_specific_data


def test_el_nivel_se_ve_y_se_cambia(config):
    p = _popup(config, FORMAS["mawashi atrasada"])
    assert p._dim_combos["Level"].currentText() == "Jodan"
    assert p._dim_combos["Stance"].currentText() == "Rear"
    p._dim_combos["Level"].setCurrentText("Chudan")
    p._on_save()
    assert _diferencias(FORMAS["mawashi atrasada"], p.edited) == {"level": ("Jodan", "Chudan")}


def test_el_miembro_de_la_finta_se_ve_y_se_cambia(config):
    p = _popup(config, FORMAS["finta alta"])
    assert p._dim_combos["Limb"].currentText() == "Upper Limb"
    p._dim_combos["Limb"].setCurrentText("Lower Limb")
    p._on_save()
    assert _diferencias(FORMAS["finta alta"], p.edited) == \
        {"level": ("Upper Limb", "Lower Limb")}


def test_la_accion_no_sale_dos_veces(config):
    """El contexto de un ataque ya tiene su desplegable; la pregunta
    «Action» de la tecnica es el mismo dato."""
    p = _popup(config, FORMAS["gyaku tsuki"])
    assert "Action" not in p._dim_combos
    assert p._context_combo.currentText() == "Direct"


def test_cambiar_de_tecnica_conserva_lo_que_sigue_valiendo(config):
    """De Tsuki a Uraken: la guardia y el nivel siguen, el nombre por
    guardia no (Uraken no lo tiene), y la secuencia y la sancion, que son
    de la accion y no de la tecnica, tampoco se tocan."""
    original = FORMAS["con sancion"]
    editada = _guardar(config, original,
                       lambda p: p._technique_combo.setCurrentText("Uraken"))
    d = editada.sport_specific_data
    assert editada.technique == "Uraken" and editada.level == "Jodan"
    assert d["stance"] == "Rear" and "base_technique" not in d
    assert d["sanction"] == "Contact" and d["sequence_id"] == "SEQ_004"
    assert d["action_type"] == "Direct" and d["contact"] == "NoScore"


def test_cambiar_a_una_patada_le_da_su_nombre(config):
    def a_mae_geri(p):
        p._subcategory_combo.setCurrentText("FOOT TECHNIQUES")
        p._technique_combo.setCurrentText("Mae Geri")
        p._dim_combos["Stance"].setCurrentText("Lead")
    editada = _guardar(config, FORMAS["gyaku tsuki"], a_mae_geri)
    assert editada.subcategory == "FOOT TECHNIQUES"
    assert editada.technique == "Kizami Mae Geri"
    assert editada.sport_specific_data["base_technique"] == "Mae Geri"


def test_un_ataque_que_pasa_a_finta_deja_el_contacto(config):
    def a_finta(p):
        p._category_combo.setCurrentText("TACTICS")
        p._technique_combo.setCurrentText("Feint")
        p._dim_combos["Limb"].setCurrentText("Lower Limb")
    editada = _guardar(config, FORMAS["gyaku tsuki"], a_finta)
    assert (editada.category, editada.technique, editada.level) == \
        ("TACTICS", "Feint", "Lower Limb")
    d = editada.sport_specific_data
    assert not {"contact", "action_type", "stance", "base_technique"} & set(d)
    assert d["sequence_id"] == "SEQ_004"


def test_en_una_falta_se_corrigen_las_notas_sin_tocar_la_falta(config):
    original = FORMAS["falta"]
    def notas(p):
        p._notes_edit.setPlainText("agarrou duas vezes")
    assert _diferencias(original, _guardar(config, original, notas)) == \
        {"notes": ("", "agarrou duas vezes")}


def test_en_una_parada_se_corrige_el_final_sin_tocar_el_tipo(config):
    original = FORMAS["parada lesion"]
    def final(p):
        p._f_end_input.setText("1290")
    dif = _diferencias(original, _guardar(config, original, final))
    assert set(dif) == {"f_end", "duration_s"} and dif["f_end"] == (1230, 1290)
