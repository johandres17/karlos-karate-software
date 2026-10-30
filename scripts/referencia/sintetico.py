"""Combates sintéticos para las pruebas de referencia.

No contienen nada real: atletas inventados, tiempos inventados. Tienen la
misma forma que las sesiones de Karlos (comprobada contra sesiones reales) y
cubren los casos que importan al comparar versiones: los tres tipos de punto,
la escalera de faltas hasta HANSOKU-CHUI, una falta ligada a un ataque,
paradas en pareja (y una pareja desigualada), un no identificable, un
barrido con derribo, fintas, defensas, agarres, una acción después del
final del combate y notas con comas y comillas.
"""
from __future__ import annotations

from rutas import modulo

Annotation = modulo("karlos_core.models.annotation", "karlos_annotator.models.annotation").Annotation

HORA = "2026-01-01T00:00:00"
BOUT = {
    "competition_name": "SINTETICO", "event_phase": "Eliminations",
    "category_type": "Kumite Male", "weight_category": "-75 kg",
    "athlete_a_name": "A. ATLETA", "athlete_a_country": "AAA",
    "athlete_b_name": "B. ATLETA", "athlete_b_country": "BBB",
    "bout_number": "1", "bout_round": "1",
    "evaluator_name": "Referencia", "evaluator_institution": "Pruebas",
}


def _a(atleta, cat, sub, tec, f0, f1, *, nivel="", score="NONE", ssd=None, notas=""):
    return Annotation(athlete=atleta, category=cat, subcategory=sub, technique=tec,
                      level=nivel, score=score, f_start=f0, f_end=f1, notes=notas,
                      timestamp=HORA, sport_specific_data=dict(ssd or {}))


def _ataque(atleta, tec, f0, f1, *, sub="HAND TECHNIQUES", nivel="Jodan", base="Tsuki",
            guardia="Rear", ctx="Direct", contacto="NoScore", score="NONE", extra=None):
    ssd = {"action_type": ctx, "contact": contacto}
    if base:
        ssd["base_technique"] = base
    if guardia:
        ssd["stance"] = guardia
    ssd.update(extra or {})
    return _a(atleta, "ATTACK", sub, tec, f0, f1, nivel=nivel, score=score, ssd=ssd)


def _parada(f0, f1, tipo="Referee"):
    return [_a("AKA", "REFEREE STOP", "MATCH STATES", tipo, f0, f1),
            _a("AO", "REFEREE STOP", "MATCH STATES", tipo, f0, f1)]


def _falta(atleta, grupo, grado, f):
    return _a(atleta, "PENALTY", grupo, grado, f, f, score="")


def combate_completo():
    an = [
        _a("AKA", "TACTICS", "TACTICS", "Feint", 120, 136, nivel="Upper Limb"),
        _ataque("AKA", "Kizami Tsuki", 140, 158, guardia="Lead", contacto="Score", score="YUKO"),
        _a("AO", "DEFENSE", "BLOCKS & EVASIONS", "Dodge", 142, 160),
        *_parada(170, 620),
        _a("AO", "TACTICS", "TACTICS", "Feint", 700, 716, nivel="Lower Limb"),
        _ataque("AO", "Mawashi Geri", 718, 744, sub="FOOT TECHNIQUES", nivel="Chudan", base="",
                contacto="Score", score="WAZA"),
        _a("AKA", "DEFENSE", "BLOCKS & EVASIONS", "Hand Block", 724, 732),
        _a("AKA", "TACTICS", "TACTICS", "Clinch", 750, 800),
        _a("AO", "TACTICS", "TACTICS", "Clinch", 752, 796),
        _falta("AO", "Clinching", "CHUI-1", 790),
        *_parada(805, 1200),
        _ataque("AKA", "Gyaku Tsuki", 1300, 1318, nivel="Chudan"),
        _ataque("AKA", "Gyaku Tsuki", 1322, 1338, ctx="Combination"),
        _ataque("AO", "Kizami Tsuki", 1340, 1352, guardia="Lead", ctx="Counter"),
        _ataque("AO", "Gyaku Tsuki", 1400, 1414, contacto="Foul", score="FOUL",
                extra={"sanction": "Contact"}),
        *_parada(1420, 1900, "VR"),
        _ataque("AKA", "Kizami Mawashi", 2000, 2024, sub="FOOT TECHNIQUES", base="Mawashi Geri",
                guardia="Lead", ctx="Anticipation"),
        _ataque("AO", "Ashi-barai", 2100, 2112, sub="SWEEPS & TAKEDOWNS", nivel="", base="",
                guardia="", contacto="Down", extra={"sequence_id": "SEQ_001"}),
        _ataque("AO", "Gyaku Tsuki", 2116, 2130, contacto="Score", score="IPPON",
                extra={"sequence_id": "SEQ_001"}),
        *_parada(2140, 2600),
        _falta("AKA", "Jogai", "CHUI-1", 2700),
        _falta("AO", "Jogai", "CHUI-2", 2760),
        _a("AO", "UNIDENTIFIED", "UNIDENTIFIED", "Unidentifiable", 2800, 2820,
           nivel="Reason: Referee", ssd={"reason": "Referee"}),
        _ataque("AKA", "Kizami Ura Mawashi", 2900, 2930, sub="FOOT TECHNIQUES",
                base="Ura Mawashi", guardia="Lead", extra={"sequence_id": "SEQ_002"}),
        _ataque("AO", "Ashi-barai", 2950, 2962, sub="SWEEPS & TAKEDOWNS", nivel="", base="",
                guardia="", contacto="Miss"),
        # Una pareja de parada desigualada, como la que sale al anotar cada
        # atleta en una pasada distinta.
        _a("AKA", "REFEREE STOP", "MATCH STATES", "VR", 3010, 3400),
        _a("AO", "REFEREE STOP", "MATCH STATES", "Referee", 2990, 3410),
        _falta("AO", "Avoiding", "CHUI-3", 3000),
        _falta("AKA", "Clinching", "CHUI-2", 3500),
        _falta("AO", "Jogai", "HANSOKU-CHUI", 3560),
        _a("AKA", "TACTICS", "TACTICS", "Feint", 3600, 3612, nivel="Upper Limb",
           notas='rápida, con "pausa" antes'),
        _ataque("AKA", "Gyaku Tsuki", 3614, 3630, contacto="Score", score="YUKO"),
        # Después del final del combate (fight_end = 6000)
        _ataque("AO", "Kizami Tsuki", 6010, 6024, guardia="Lead"),
    ]
    return an, dict(BOUT), 60, 6000


def combates():
    """Nombre → (anotaciones, bout_info, fight_start, fight_end)."""
    return {
        "SINT01": combate_completo(),
        "SINT02": ([], dict(BOUT), 0, 5400),
        "SINT03": ([_ataque("AKA", "Gyaku Tsuki", 300, 318)], {}, None, None),
    }
