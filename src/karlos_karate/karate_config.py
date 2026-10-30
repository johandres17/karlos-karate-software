"""Karate sport configuration for KARLOS ANNOTATOR.

Exports SPORT_CONFIG dict matching the taxonomy.json schema consumed by
config_loader. Labels and taxonomy names are in English for international use.

v1.0 — COMBINATORIAL ENGINE:
The ATTACK taxonomy now uses BASE techniques (e.g., "Tsuki") combined with
a Stance modifier (Lead/Rear). The COMBINATORIAL_MAP resolves the official
Japanese name before persistence (e.g., Tsuki + Lead → "Kizami Tsuki"),
so downstream analytics (Match Report, PDF, CSV) keep working unchanged.

Scientific rationale (WKF technical-tactical literature — Tabben et al.,
Chaabène et al., Koropanovski et al.):
- action_type (Direct/Counter/Anticipation/Combination) is the most cited
  tactical variable in elite WKF analysis and is captured per annotation.
- Ashi-barai is classified as ATTACK (WKF rules: sweeps are scoring-enabling
  offensive actions when followed by a technique).
"""

# ══════════════════════════════════════════════════════════════════
# COMBINATORIAL NAME RESOLUTION MAP
# ══════════════════════════════════════════════════════════════════
# Maps: base_technique → {stance → official Japanese technique name}
# Resolution happens BEFORE the Annotation is persisted, so the
# `technique` field always stores the resolved official name.
# Techniques absent from this map resolve to themselves (Open/Closed).
COMBINATORIAL_MAP: dict[str, dict[str, str]] = {
    # ── Punches (Tsuki) ────────────────────────────────────────
    # Lead hand  → Kizami Tsuki (front-hand jab punch)
    # Rear hand  → Gyaku Tsuki  (reverse punch)
    "Tsuki": {
        "Lead": "Kizami Tsuki",
        "Rear": "Gyaku Tsuki",
    },
    # ── Roundhouse kicks (Mawashi Geri family) ─────────────────
    # Lead leg → Kizami Mawashi   (front-leg roundhouse)
    # Rear leg → Mawashi Geri     (rear-leg roundhouse)
    "Mawashi Geri": {
        "Lead": "Kizami Mawashi",
        "Rear": "Mawashi Geri",
    },
    # ── Hook/reverse roundhouse kicks (Ura Mawashi family) ─────
    # Lead leg → Kizami Ura Mawashi (front-leg hook kick)
    # Rear leg → Ura Mawashi       (rear-leg hook kick)
    "Ura Mawashi": {
        "Lead": "Kizami Ura Mawashi",
        "Rear": "Ura Mawashi",
    },
    # ── Front kicks (Mae Geri family) ──────────────────────────
    # Lead leg → Kizami Mae Geri   (front-leg front kick)
    # Rear leg → Mae Geri          (rear-leg front kick)
    "Mae Geri": {
        "Lead": "Kizami Mae Geri",
        "Rear": "Mae Geri",
    },
    # ── Side kicks (Yoko Geri family) ──────────────────────────
    # Lead leg → Kizami Yoko Geri  (front-leg side kick)
    # Rear leg → Yoko Geri         (rear-leg side kick)
    "Yoko Geri": {
        "Lead": "Kizami Yoko Geri",
        "Rear": "Yoko Geri",
    },
    # ── Back kick (Ushiro Geri) ────────────────────────────────
    # Only Rear (spinning technique, no lead-leg version)
    "Ushiro Geri": {
        "Rear": "Ushiro Geri",
    },
}

SPORT_CONFIG = {
    "app": {
        "name": "Karlos Annotator",
        "version": "1.0",
        "min_width": 1440,
        "min_height": 860,
        "font_family": "Inter,-apple-system,sans-serif",
        "font_size": 11,
    },
    "sport": {
        "id": "karate",
        "name": "Karate",
        "short": "K",
        "athlete_a_label": "AKA",
        "athlete_b_label": "AO",
    },
    "colors": {
        "background": "#0B0D10",
        "panel": "#14171C",
        "border": "#22262E",
        "text": "#E1E7EF",
        "muted": "#798394",
        "aka": "#E5534B",
        "ao": "#4384E6",
        "punch": "#208B7A",
        "kick": "#3866C2",
        "sweep": "#854C9E",
        "state": "#637083",
        "accent": "#E8B33A",
        "green": "#2B9E66",
        "yellow": "#D5A021",
    },
    "levels": ["Jodan", "Chudan"],
    "scoring": {
        "IPPON": {
            "points": 3,
            "label": "IPPON  (3 pts)    [1]",
            "color": "#F58732",
            "shortcut": "1",
        },
        "WAZA": {
            "points": 2,
            "label": "WAZA-ARI (2 pts)  [2]",
            "color": "#D5A021",
            "shortcut": "2",
        },
        "YUKO": {
            "points": 1,
            "label": "YUKO  (1 pt)      [3]",
            "color": "#2B9E66",
            "shortcut": "3",
        },
        "NONE": {
            "points": 0,
            "label": "No Score          [4]",
            "color": "#798394",
            "shortcut": "4",
        },
        "FOUL": {
            "points": 0,
            "label": "FOUL  (Chui)      [5]",
            "color": "#E5534B",
            "shortcut": "5",
        },
    },
    # ── COMBINATORIAL NAME RESOLUTION (v1.0) ─────────────────────────
    # Consumed by config_loader → TaxonomyConfig.combinatorial_map and
    # resolved via models.technique.resolve_combat_action().
    "combinatorial_map": COMBINATORIAL_MAP,
    # ── UNIFIED HIERARCHICAL TAXONOMY (v1.0) ─────────────────────────
    # ATTACK techniques are now BASE techniques with a multi-dimension
    # levels_config: Stance (Lead/Rear) + Level (Jodan/Chudan) +
    # Action (tactical context, per WKF scientific literature).
    # scoring_rules: level → score_code mapping for auto-score calculation.
    # range: distance classification for tactical analysis.
    "taxonomy": [
        {
            "name": "HAND TECHNIQUES",
            "category": "ATTACK",
            "color": "#208B7A",
            "range": "close",  # Close-range combat
            "scoring_rules": {
                # WKF Kumite Rules, Art. 6 — Yuko (1 pt) is awarded for
                # Tsuki/Uchi to ANY of the seven scoring areas, head
                # (Jodan) included. Ippon is reserved for Jodan KICKS and
                # for techniques scored on a thrown/fallen opponent, so a
                # punch to the head must NOT auto-propose Ippon.
                "Jodan": "YUKO",
                "Chudan": "YUKO",
            },
            "techniques": [
                # BASE technique: resolved via COMBINATORIAL_MAP
                # Tsuki + Lead → Kizami Tsuki | Tsuki + Rear → Gyaku Tsuki
                {
                    "name": "Tsuki", "abbr": "TSK", "has_level": True, "shortcut": "1",
                    "levels_config": {
                        "Stance": ["Lead", "Rear"],
                        "Level": ["Jodan", "Chudan"],
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                    },
                },
                {
                    "name": "Uraken", "abbr": "URK", "has_level": True, "shortcut": "2",
                    "levels_config": {
                        "Stance": ["Lead", "Rear"],
                        "Level": ["Jodan", "Chudan"],
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                    },
                },
                {
                    "name": "Other Punch", "abbr": "OTH", "has_level": True, "shortcut": "Q",
                    "levels_config": {
                        "Stance": ["Lead", "Rear"],
                        "Level": ["Jodan", "Chudan"],
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                    },
                },
            ],
        },
        {
            "name": "FOOT TECHNIQUES",
            "category": "ATTACK",
            "color": "#3866C2",
            "range": "mid",  # Mid-range combat
            "scoring_rules": {
                # Kicks to head (Jodan) score IPPON (3 pts)
                # Kicks to body (Chudan) score WAZA-ARI (2 pts)
                "Jodan": "IPPON",
                "Chudan": "WAZA",
            },
            "techniques": [
                # BASE: Mawashi Geri + Lead → Kizami Mawashi | + Rear → Mawashi Geri
                {
                    "name": "Mawashi Geri", "abbr": "MAW", "has_level": True, "shortcut": "3",
                    "levels_config": {
                        "Stance": ["Lead", "Rear"],
                        "Level": ["Jodan", "Chudan"],
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                    },
                },
                # BASE: Ura Mawashi + Lead → Kizami Ura Mawashi | + Rear → Ura Mawashi
                {
                    "name": "Ura Mawashi", "abbr": "URA", "has_level": True, "shortcut": "4",
                    "levels_config": {
                        "Stance": ["Lead", "Rear"],
                        "Level": ["Jodan", "Chudan"],
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                    },
                },
                # BASE: Mae Geri + Lead → Kizami Mae Geri | + Rear → Mae Geri
                {
                    "name": "Mae Geri", "abbr": "MAE", "has_level": True, "shortcut": "5",
                    "levels_config": {
                        "Stance": ["Lead", "Rear"],
                        "Level": ["Jodan", "Chudan"],
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                    },
                },
                # BASE: Yoko Geri + Lead → Kizami Yoko Geri | + Rear → Yoko Geri
                {
                    "name": "Yoko Geri", "abbr": "YOK", "has_level": True, "shortcut": "6",
                    "levels_config": {
                        "Stance": ["Lead", "Rear"],
                        "Level": ["Jodan", "Chudan"],
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                    },
                },
                # BASE: Ushiro Geri → only Rear (spinning technique)
                {
                    "name": "Ushiro Geri", "abbr": "USH", "has_level": True, "shortcut": "7",
                    "levels_config": {
                        "Stance": ["Rear"],
                        "Level": ["Jodan", "Chudan"],
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                    },
                },
                {
                    "name": "Other Kick", "abbr": "OTK", "has_level": True, "shortcut": "W",

                    "levels_config": {
                        "Stance": ["Lead", "Rear"],
                        "Level": ["Jodan", "Chudan"],
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                    },
                },
            ],
        },
        {
            # WKF rules: sweeps/takedowns are OFFENSIVE scoring-enabling
            # actions (Ashi-barai + Tsuki is a canonical scoring pattern).
            # v1.0 — ML-ready: Ashi-barai now captures tactical context (Action)
            # and follow-up technique type, enabling Sequence_ID grouping for
            # temporal pattern learning (Ashi-barai → Gyaku-zuki).
            "name": "SWEEPS & TAKEDOWNS",
            "category": "ATTACK",
            "color": "#854C9E",
            "range": "close",
            "scoring_rules": {},  # Score comes from the follow-up technique
            "techniques": [
                {
                    "name": "Ashi-barai", "abbr": "ASH", "has_level": True, "shortcut": "8",
                    "levels_config": {
                        "Action": ["Direct", "Counter", "Anticipation", "Combination"],
                        "Follow-up": ["None", "Kizami Tsuki", "Gyaku-zuki", "Mawashi Geri", "Other"],
                    },
                },
                {"name": "Takedown", "abbr": "TKD", "has_level": False, "shortcut": "9"},
            ],
        },

        {
            "name": "BLOCKS & EVASIONS",
            "category": "DEFENSE",
            "color": "#637083",
            "range": "close",
            "scoring_rules": {},  # No scoring for defensive actions
            "techniques": [
                {"name": "Hand Block", "abbr": "BLK", "has_level": False, "shortcut": "0"},
                {"name": "Dodge", "abbr": "DGE", "has_level": False, "shortcut": "Z"},
            ],
        },
        {
            "name": "TACTICS",
            "category": "TACTICS",
            "color": "#637083",
            "range": "",  # No range classification for tactics
            "scoring_rules": {},  # No scoring for tactical actions
            "techniques": [
                {"name": "Feint", "abbr": "FNT", "has_level": True, "shortcut": "-",
                 "levels_config": {"Limb": ["Upper Limb", "Lower Limb"]}},
                {"name": "Clinch", "abbr": "CLN", "has_level": False, "shortcut": "="},
            ],
        },
        {
            # Lo que se ve que pasa pero no se puede leer: el arbitro se
            # cruza, el atleta sale del encuadre, la espalda del rival
            # tapa la tecnica. No es una accion mas ni es descartarla:
            # es un hecho sobre el VIDEO, y cuanto hay de esto en un
            # combate es un dato del estudio, no una perdida que
            # esconder. Sin esta salida el evaluador tenia que elegir
            # entre inventar una tecnica o borrar el momento.
            "name": "UNIDENTIFIED",
            "category": "UNIDENTIFIED",
            "color": "#8A8F98",
            "range": "",
            "scoring_rules": {},
            "techniques": [
                {"name": "Unidentifiable", "abbr": "N/I", "has_level": False,
                 "shortcut": ""},
            ],
        },
        {
            "name": "MATCH STATES",
            "category": "REFEREE STOP",
            "color": "#D5A021",
            "range": "",
            "scoring_rules": {},
            "techniques": [
                {"name": "Referee Stop", "abbr": "YME", "has_level": False, "shortcut": "Ctrl+R"},
            ],
        },
    ],
    "referee_stop_types": [
        {"name": "Referee", "abbr": "YME-R", "shortcut": "R", "color": "#E5534B"},
        {"name": "VR", "abbr": "YME-V", "shortcut": "V", "color": "#4384E6"},
        {"name": "Injury", "abbr": "YME-I", "shortcut": "I", "color": "#D5A021"},
    ],
    # Lo que pide la ventana de los datos del combate (decisión 0007):
    # estaba escrito en el núcleo y lo heredaba el boxeo.
    "bout_info": {
        "category_types": ["Kumite Male", "Kumite Female", "Kata Male", "Kata Female"],
        "weights": {
            "Kumite Male": ["-60 kg", "-67 kg", "-75 kg", "-84 kg", "+84 kg"],
            "Kumite Female": ["-50 kg", "-55 kg", "-61 kg", "-68 kg", "+68 kg"],
            "Kata Male": ["N/A (Kata)"],
            "Kata Female": ["N/A (Kata)"],
        },
        "rounds": ["1"],
        "round_duration": ["3 min"],
        "areas": 8,
    },
    # El tiempo-movimiento del karate (decision 0008). Los tres primeros
    # estados y sus definiciones son de Chaabene et al. 2014 (Int J Sports
    # Physiol Perform 9(2):302-308); el cuarto es nuestro y se declara.
    #
    #   1 fighting      sale de la guardia hacia un intercambio -> acaba
    #                   cuando el miembro esta retraido, el pie ha vuelto al
    #                   suelo y el contacto ha cesado
    #   2 non_fighting  HAJIME o fin del intercambio -> YAME o inicio del
    #                   intercambio siguiente (en karate se llama
    #                   «preparatory», de ahi phase_labels)
    #   3 stoppage      YAME -> HAJIME
    #   4 unobservable  el video no permite decidir
    #
    # Las teclas son los digitos, en el orden de esta lista. En el modo
    # tiempo-movimiento no hay tecnicas que elegir, asi que los numeros no
    # chocan con nada. `letters` esta vacia a proposito: C, V y H son las
    # faltas de la WKF en karate, y el taekwondo si las usa para las fases.
    "time_motion": {
        "gap_s": 2.0,
        "phases": ["fighting", "non_fighting", "stoppage", "unobservable"],
        "letters": [],
        # El de siempre: un combate sin analisis dicho —los 20 del estudio,
        # y cualquiera anotado antes del 16-10-2026— es el COMPLETO. Sin
        # esto pasarian a tratarse como eventos y perderian sus duraciones.
        "default_analysis": "complete",
        # Las fases son DEL COMBATE, no de cada atleta: en karate el estado
        # es de los dos (Chaabène et al. 2014, «an exchange between the two
        # contestants»; ningún estudio de karate codifica estados por
        # atleta). Una sola pasada. El taekwondo sigue con una por atleta,
        # que es lo que pidió el especialista (decisión 0008).
        # Cada atleta marca sus fases, en una pasada por atleta (Johan,
        # 19-10-2026): la literatura de kárate informa el tiempo-movimiento
        # por karateka (Chaabène et al. 2014 comparan ganadores y perdedores;
        # Tabben et al. 2015, 60 atletas). Hasta ese día eran del combate.
        "phases_per_athlete": True,
        # Lo que dicen la hoja y el informe sobre el método, con las
        # definiciones de Chaabène et al. 2014 y no las del especialista.
        "method_note": (
            "The phases are marked once per athlete, as the karate literature "
            "reports time-motion per karateka (Chaabène et al. 2014, Int J Sports "
            "Physiol Perform 9(2):302-308, winners vs defeated; Tabben et al. 2015, "
            "J Sports Sci 33(8):841-849, 60 athletes). Definitions after Chaabène et "
            "al. 2014. fighting: from leaving the "
            "fighting stance towards an exchange until the striking limb is retracted, "
            "the kicking foot is back on the floor and contact has ceased. preparatory: "
            "from HAJIME, or the end of an exchange, until the next exchange or YAME. "
            "stoppage: from YAME to HAJIME. unobservable: the video does not allow "
            "deciding (our addition; excluded when comparing with the literature). "
            "Marked: keyed in with 1, 2, 3 and 4. Derived: from the annotated actions "
            "and the referee stops."),
        # Retirar la ultima marca. En taekwondo va con la primera
        # letra; en karate no hay letras, asi que va con el primer digito.
        "remove_key": "Shift+1",
        "phase_labels": {"non_fighting": "preparatory"},
        "analyses": [("Technical-tactical", "technical_tactical"),
                     ("Time-motion", "time_motion"),
                     ("Complete (both)", "complete")],
    },
    "video": {
        "speed_options": [1.50, 1.25, 1.0, 0.5, 0.25, 0.125],
        "speed_labels": ["1.50x", "1.25x", "1x", "0.5x", "0.25x", "0.125x"],
        "default_speed_index": 2,
        "wheel_step_small": 1,
        "wheel_step_medium": 2,
        "wheel_step_large": 5,
        "wheel_threshold_small": 120,
        "wheel_threshold_medium": 240,
        "wheel_threshold_large": 480,
    },
}
