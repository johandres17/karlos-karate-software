"""Bout Information popup — WKF 2026 & WAKO Kickboxing Official Standards.

Premium modal dialog for entering bout metadata aligned with
World Karate Federation 2026 and WAKO Kickboxing rules.
Dark-theme, gold-accented, interactive combos with dynamic filtering.
"""

from __future__ import annotations

from typing import Optional

import qtawesome as qta
from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# ── Karlitos Premium Dark Palette ────────────────────────────
from karlos_core.views.theme import Palette
from karlos_core.views.animaciones import aparecer
_p = Palette()  # module-level instance for static QSS

_C_BG = _p.bg_root
_C_PANEL = _p.panel_dark       # was #1A1A1A
_C_TEXT = _p.text_inverse
_C_MUTED = _p.grey_888          # was #888888
_C_ACCENT = _p.warning
_C_BORDER = _p.border_strong
_C_GREEN = _p.chart_green
_C_RED_AKA = _p.timeline_aka
_C_BLUE_AO = _p.ao_dark

_FONT = (
    "-apple-system, 'SF Pro Display', 'SF Pro Text', "
    "'Helvetica Neue', 'Inter', sans-serif"
)

_FONT_SIZE_LABEL = "11px"
_FONT_SIZE_INPUT = "13px"

# Las categorías, los pesos, los asaltos y el área de cada deporte son suyos:
# vienen en su configuración («bout_info», decisión 0007). Aquí solo se
# pintan; antes el boxeo heredaba las del karate (Kata, Kumite, tatami).

# ── Fases del torneo ─────────────────────────────────────────
_FASES_DEL_TORNEO = [
    "Eliminations",
    "Round of 32",
    "Round of 16",
    "Quarter-Final",
    "Semi-Final",
    "Repechage",
    "Bronze Medal",
    "Final",
]

# ── Países ───────────────────────────────────────────────────
_PAISES = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Argentina",
    "Armenia", "Australia", "Austria", "Azerbaijan",
    "Bahrain", "Belarus", "Belgium", "Benin", "Bosnia & Herzegovina",
    "Botswana", "Brazil", "Bulgaria", "Burkina Faso",
    "Cameroon", "Canada", "Chile", "China", "Colombia",
    "Congo DR", "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czech Republic",
    "Denmark", "Dominican Republic",
    "Ecuador", "Egypt", "El Salvador", "England", "Estonia",
    "Finland", "France",
    "Georgia", "Germany", "Ghana", "Greece", "Guatemala",
    "Hong Kong", "Hungary",
    "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland",
    "Israel", "Italy", "Ivory Coast",
    "Jamaica", "Japan", "Jordan",
    "Kazakhstan", "Kenya", "Kosovo", "Kuwait",
    "Latvia", "Lebanon", "Libya", "Lithuania", "Luxembourg",
    "Macau", "Madagascar", "Malaysia", "Mali", "Malta",
    "Mexico", "Moldova", "Monaco", "Montenegro", "Morocco",
    "Nepal", "Netherlands", "New Zealand", "Nicaragua",
    "Nigeria", "North Macedonia", "Norway",
    "Pakistan", "Palestine", "Panama", "Paraguay", "Peru",
    "Philippines", "Poland", "Portugal", "Puerto Rico",
    "Qatar",
    "Romania", "Russia", "Rwanda",
    "San Marino", "Saudi Arabia", "Scotland", "Senegal",
    "Serbia", "Singapore", "Slovakia", "Slovenia",
    "South Africa", "South Korea", "Spain", "Sri Lanka",
    "Sweden", "Switzerland", "Syria",
    "Taiwan", "Thailand", "Togo", "Trinidad & Tobago",
    "Tunisia", "Turkey", "Turkmenistan",
    "Uganda", "Ukraine", "United Arab Emirates", "Uruguay",
    "USA", "Uzbekistan",
    "Venezuela", "Vietnam",
    "Wales", "Zambia", "Zimbabwe",
]

# ── Input field style (Karate default) ───────────────────────
_INPUT_STYLE_KARATE = (
    "QLineEdit{"
    f"background:{_C_PANEL};"
    f"color:{_C_TEXT};"
    f"border:1px solid {_C_BORDER};"
    "border-radius:4px;"
    "padding:6px 12px;"
    "font-size:13px;"
    "min-height:28px;"
    "font-weight:400;"
    "}"
    "QLineEdit:focus{"
    f"border:1px solid {_C_ACCENT};"
    "}"
)

# ── Input field style (Kickboxing — taller) ──────────────────
_INPUT_STYLE_KB = (
    "QLineEdit{"
    f"background:{_C_PANEL};"
    f"color:{_C_TEXT};"
    f"border:1px solid {_C_BORDER};"
    "border-radius:4px;"
    "padding:10px 14px;"
    "font-size:13px;"
    "min-height:34px;"
    "font-weight:400;"
    "}"
    "QLineEdit:focus{"
    f"border:1px solid {_C_ACCENT};"
    "}"
)

# ── Combo style (Karate default) ─────────────────────────────
_COMBO_STYLE_KARATE = (
    "QComboBox{"
    f"background:{_C_PANEL};"
    f"color:{_C_TEXT};"
    f"border:1px solid {_C_BORDER};"
    "border-radius:4px;"
    "padding:6px 32px 6px 12px;"
    "font-size:13px;"
    "min-height:28px;"
    "font-weight:400;"
    "}"
    "QComboBox:hover{"
    f"border:1px solid {_C_ACCENT}66;"
    "}"
    "QComboBox:focus{"
    f"border:1px solid {_C_ACCENT};"
    "}"
    "QComboBox::drop-down{"
    "subcontrol-origin:padding;"
    "subcontrol-position:top right;"
    "width:28px;"
    f"border-left:1px solid {_C_BORDER};"
    "border-top-right-radius:4px;"
    "border-bottom-right-radius:4px;"
    "}"
    "QComboBox::down-arrow{"
    f"color:{_C_ACCENT};"
    "width:10px;height:10px;"
    "}"
    "QComboBox QAbstractItemView{"
    f"background:{_C_PANEL};"
    f"color:{_C_TEXT};"
    f"border:1px solid {_C_BORDER};"
    "border-radius:4px;"
    "padding:4px;"
    "selection-background-color:rgba(213,160,33,0.15);"
    f"selection-color:{_C_ACCENT};"
    "}"
)

# ── Combo style (Kickboxing — taller) ────────────────────────
_COMBO_STYLE_KB = (
    "QComboBox{"
    f"background:{_C_PANEL};"
    f"color:{_C_TEXT};"
    f"border:1px solid {_C_BORDER};"
    "border-radius:4px;"
    "padding:10px 32px 10px 14px;"
    "font-size:13px;"
    "min-height:34px;"
    "font-weight:400;"
    "}"
    "QComboBox:hover{"
    f"border:1px solid {_C_ACCENT}66;"
    "}"
    "QComboBox:focus{"
    f"border:1px solid {_C_ACCENT};"
    "}"
    "QComboBox::drop-down{"
    "subcontrol-origin:padding;"
    "subcontrol-position:top right;"
    "width:28px;"
    f"border-left:1px solid {_C_BORDER};"
    "border-top-right-radius:4px;"
    "border-bottom-right-radius:4px;"
    "}"
    "QComboBox::down-arrow{"
    f"color:{_C_ACCENT};"
    "width:10px;height:10px;"
    "}"
    "QComboBox QAbstractItemView{"
    f"background:{_C_PANEL};"
    f"color:{_C_TEXT};"
    f"border:1px solid {_C_BORDER};"
    "border-radius:4px;"
    "padding:4px;"
    "selection-background-color:rgba(213,160,33,0.15);"
    f"selection-color:{_C_ACCENT};"
    "}"
)

# ── Button styles ────────────────────────────────────────────
_SAVE_BTN_STYLE = (
    "QPushButton{"
    f"background:{_C_ACCENT};"
    f"color:{_p.misc_grey_bg};"
    f"border:1px solid {_C_ACCENT};"
    "border-radius:8px;"
    "padding:10px 32px;"
    "font-size:14px;"
    "font-weight:700;"
    "}"
    "QPushButton:hover{"
    f"background:{_C_ACCENT}DD;"
    "}"
    "QPushButton:pressed{"
    f"background:{_C_ACCENT}BB;"
    "}"
)

_CANCEL_BTN_STYLE = (
    "QPushButton{"
    "background:transparent;"
    f"color:{_C_MUTED};"
    f"border:1px solid {_C_BORDER};"
    "border-radius:6px;"
    "padding:10px 24px;"
    "font-size:13px;"
    "font-weight:500;"
    "}"
    "QPushButton:hover{"
    "background:rgba(255,255,255,0.06);"
    f"color:{_C_TEXT};"
    "}"
    "QPushButton:pressed{"
    "background:rgba(255,255,255,0.04);"
    "}"
)

# ── Scrollbar style ──────────────────────────────────────────
_SCROLLBAR_STYLE = (
    "QScrollArea{"
    "background:transparent;"
    "border:none;"
    "}"
    "QScrollBar:vertical{"
    f"background:{_C_BG};"
    "width:6px;"
    "margin:0px;"
    "border-radius:3px;"
    "}"
    "QScrollBar::handle:vertical{"
    f"background:{_C_BORDER};"
    "min-height:30px;"
    "border-radius:3px;"
    "}"
    "QScrollBar::handle:vertical:hover{"
    f"background:{_C_MUTED};"
    "}"
    "QScrollBar::add-line:vertical,"
    "QScrollBar::sub-line:vertical{"
    "height:0px;"
    "}"
    "QScrollBar::add-page:vertical,"
    "QScrollBar::sub-page:vertical{"
    "background:transparent;"
    "}"
)


def colores_de_esquinas(bout_info: dict, sport_id: str) -> tuple[str, str]:
    """Los colores de los dos competidores: los de la esquina elegida o, si
    no se eligió ninguna (solo el kickboxing la pregunta), los de la esquina
    que el deporte da por defecto.

    Antes el defecto era siempre rojo para el primero, como en el karate
    (AKA). En taekwondo el primero es Chung, que es azul, y el especialista lo vio
    al revés en la cabecera (15-10-2026). Cada deporte dice ahora sus
    esquinas («corners» en su bout_info); el karate no dice nada y sigue
    exactamente igual."""
    hexes = {"Red": _C_RED_AKA, "Blue": _C_BLUE_AO, "White": _p.grey_light,
             "Black": "#1A1A1A", "Green": _C_GREEN, "Yellow": _C_ACCENT}
    try:
        defecto = list(BoutInfoPopup._datos_del_deporte(sport_id).get("corners") or ["Red", "Blue"])
    except Exception:            # noqa: BLE001  (un deporte sin configuración)
        defecto = ["Red", "Blue"]
    ca = (bout_info or {}).get("athlete_a_corner") or defecto[0]
    cb = (bout_info or {}).get("athlete_b_corner") or defecto[1]
    return hexes.get(ca, _C_RED_AKA), hexes.get(cb, _C_BLUE_AO)


class BoutInfoPopup(QDialog):
    """Modal dialog for entering WKF 2026 / WAKO Kickboxing bout metadata.

    Attributes:
        bout_info: Dict with all entered metadata fields.
    """

    # Reverse mapping from storage key to display widget key
    _KEY_TO_WIDGET: dict[str, str] = {
        "competition_name": "competition_name",
        "event_phase": "event_phase",
        "category_type": "category_type",
        "weight_category": "weight_category",
        "pool": "pool",
        "tatami": "tatami",
        "athlete_a_name": "athlete_a_name",
        "athlete_a_country": "athlete_a_country",
        "athlete_a_club": "athlete_a_club",
        "athlete_b_name": "athlete_b_name",
        "athlete_b_country": "athlete_b_country",
        "athlete_b_club": "athlete_b_club",
        "bout_number": "bout_number",
        "bout_round": "bout_round",
        "evaluator_name": "evaluator_name",
        "evaluator_institution": "evaluator_institution",
        "analysis_date": "analysis_date",
        # Kickboxing-specific
        "athlete_a_corner": "athlete_a_corner",
        "athlete_b_corner": "athlete_b_corner",
        "competition_type": "competition_type",
        "discipline": "discipline",
        "age_category": "age_category",
        "gender": "gender",
        "num_rounds": "num_rounds",
        "round_duration": "round_duration",
        # Si el deporte los trae (decisión 0007): el resultado y la guardia.
        "bout_winner": "bout_winner",
        "bout_ending": "bout_ending",
        "athlete_a_guard": "athlete_a_guard",
        "athlete_b_guard": "athlete_b_guard",
    }

    def __init__(
        self,
        athlete_a_label: str = "Athlete A",
        athlete_b_label: str = "Athlete B",
        parent: Optional[QWidget] = None,
        existing_data: Optional[dict[str, str]] = None,
        sport_id: str = "karate",
        anotaciones: int = 0,
    ) -> None:
        super().__init__(parent)
        aparecer(self)
        from karlos_core.utils.i18n import I18n
        self._i18n = I18n()
        self._sport_id = sport_id
        # Con anotaciones el análisis es del combate y no se cambia aquí
        # (Johan, 8-10-2026): el combo lo enseña, apagado, y dice por qué.
        self._anotaciones = int(anotaciones or 0)
        self._datos = self._datos_del_deporte(sport_id)
        self.setObjectName("boutInfoPopup")
        self.setWindowTitle(self._i18n.t("bout.window_title"))

        # ── Sensible defaults: generous initial size, resizable ──
        self.setMinimumSize(920, 620)
        self.resize(980, 780)
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowCloseButtonHint
        )

        from datetime import datetime as _dt

        from karlos_core import identidad

        self._athlete_a_label = athlete_a_label
        self._athlete_b_label = athlete_b_label
        self.bout_info: dict[str, str] = {}
        self._existing_data = existing_data or {}

        # ── Persistent evaluator info (QSettings) ──────────────
        self._settings = identidad.ajustes()   # los de la edición (decisión 0006)
        if not self._existing_data.get("evaluator_name"):
            saved_name = self._settings.value("evaluator/name", "")
            if saved_name:
                self._existing_data["evaluator_name"] = saved_name
        if not self._existing_data.get("evaluator_institution"):
            saved_inst = self._settings.value("evaluator/institution", "")
            if saved_inst:
                self._existing_data["evaluator_institution"] = saved_inst
        # Pre-fill analysis date if not already in existing_data
        if not self._existing_data.get("analysis_date"):
            self._existing_data["analysis_date"] = _dt.now().strftime("%Y-%m-%d")

        self._inputs: dict[str, QLineEdit] = {}
        self._combos: dict[str, QComboBox] = {}
        self._build()
        self._prefill()

    # ------------------------------------------------------------------
    # Show animation
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Fade-in the popup when it first appears.

        Uses QGraphicsOpacityEffect + QPropertyAnimation (150ms,
        InOutQuad) — same pattern as MainWindow.animate_focus_mode.

        Must be in showEvent(), not __init__(), because the widget is
        not yet on screen during construction.
        """
        super().showEvent(event)
        if not hasattr(self, "_fade_done"):
            self._fade_done = True
            effect = QGraphicsOpacityEffect()
            effect.setOpacity(0.0)
            self.setGraphicsEffect(effect)
            self._fade_anim = QPropertyAnimation(effect, b"opacity")
            self._fade_anim.setDuration(150)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self._fade_anim.finished.connect(lambda: self.setGraphicsEffect(None))
            self._fade_anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        # ── Dialog-level: ONLY background, zero widget styling ──
        self.setStyleSheet(
            f"QDialog#boutInfoPopup{{background:{_C_BG};}}"
        )

        # ── Root container ─────────────────────────────────────
        container = QWidget()
        container.setObjectName("boutInfoContainer")
        container.setStyleSheet(
            f"QWidget#boutInfoContainer{{"
            f"color:{_C_TEXT};"
            f"font-family:{_FONT};"
            f"font-size:13px;"
            f"background:transparent;"
            "}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(container)

        inner_root = QVBoxLayout(container)
        inner_root.setContentsMargins(32, 28, 32, 24)
        inner_root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(0)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel(self._i18n.t("bout.title").upper())
        title.setStyleSheet(
            f"color:{_C_ACCENT};font-size:20px;font-weight:700;"
            "letter-spacing:2px;text-transform:uppercase;"
            "background:transparent;border:none;"
        )
        title_block.addWidget(title)
        # El de cada deporte, en sus textos (decisión 0007).
        sub = QLabel(self._i18n.t("bout.subtitle"))
        sub.setStyleSheet(
            f"color:{_C_MUTED};font-size:11px;font-weight:400;"
            "letter-spacing:0.5px;text-transform:none;"
            "background:transparent;border:none;"
        )
        title_block.addWidget(sub)
        header.addLayout(title_block)
        header.addStretch()
        inner_root.addLayout(header)

        inner_root.addSpacing(18)

        # ── Gold separator ─────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            f"background:{_C_ACCENT}44;"
            "min-height:1px;max-height:1px;"
            "border:none;"
        )
        inner_root.addWidget(sep)
        inner_root.addSpacing(20)

        # ── Two-column scrollable layout ───────────────────────
        columns = QHBoxLayout()
        columns.setSpacing(0)

        # ── LEFT scroll area ───────────────────────────────────
        left_scroll = QScrollArea()
        left_scroll.setStyleSheet(_SCROLLBAR_STYLE)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        left_widget = QWidget()
        left_widget.setStyleSheet("background:transparent;")
        left_col = QVBoxLayout(left_widget)
        left_col.setContentsMargins(0, 0, 20, 0)
        left_col.setSpacing(16)

        datos = self._datos
        if datos.get("weights") and not datos.get("category_types"):
            # ── Por género: kickboxing y taekwondo ──
            # Las listas son de cada deporte, de su configuración (decisión
            # 0007): estaban escritas aquí, con edades de tatami en el
            # kickboxing de ring y la repesca que la WAKO no tiene.
            self._add_section_header(
                left_col, "MATCH DETAILS",
                icon_name="fa5s.calendar-alt", icon_color=_C_ACCENT,
            )
            self._add_field(left_col, "competition_name", "Competition Name")
            self._add_combo(left_col, "event_phase", "Event Phase",
                            list(datos.get("phases", _FASES_DEL_TORNEO)))
            self._add_combo(left_col, "gender", "Gender",
                            list(datos["weights"]), on_change=self._on_gender_changed)
            # La edad va ANTES del peso porque lo manda: en el taekwondo,
            # cadete, junior y senior tienen tablas distintas (WT art. 5).
            # Estaba al final, debajo de un peso que ya no podía cambiar.
            if datos.get("age_categories"):
                self._add_combo(left_col, "age_category", "Age Category",
                                list(datos["age_categories"]),
                                on_change=self._on_gender_changed)
            self._add_combo(left_col, "weight_category", "Weight Category", [])
            self._add_combo(left_col, "num_rounds", "Number of Rounds",
                            list(datos.get("rounds", ["3"])),
                            on_change=self._on_rounds_changed)
            self._add_combo(left_col, "round_duration", "Round Duration", [])
            for clave, rotulo, lista in (("competition_type", "Type of Competition", "competition_types"),
                                         ("discipline", "Discipline", "disciplines")):
                if datos.get(lista):
                    self._add_combo(left_col, clave, rotulo, list(datos[lista]))
            # Qué se analiza ya no es un dato del combate: desde el 19-10-2026
            # cada análisis es un cuaderno aparte del mismo vídeo y se elige
            # en el Hub o con «Análise…» (decisión 0008).
            # Init weight list based on default gender
            self._on_gender_changed()
            self._on_rounds_changed()
        else:
            # ── Karate WKF rules ──
            self._add_section_header(
                left_col, self._i18n.t("bout.event_details"),
                icon_name="fa5s.calendar-alt", icon_color=_C_ACCENT,
            )
            self._add_field(left_col, "competition_name", self._i18n.t("bout.competition_name"))
            self._add_combo(left_col, "event_phase", self._i18n.t("bout.event_phase"),
                            list(self._datos.get("phases", _FASES_DEL_TORNEO)))
            self._add_spacer(left_col, 8)
            self._add_section_header(
                left_col, self._i18n.t("bout.fight_setup"),
                icon_name="fa5s.fist-raised", icon_color=_C_ACCENT,
            )
            self._add_combo(
                left_col, "category_type", self._i18n.t("bout.category_type"),
                list(datos.get("category_types", [])), on_change=self._on_category_changed,
            )
            self._add_combo(left_col, "weight_category", self._i18n.t("bout.weight_category"), [])
            self._add_combo(left_col, "num_rounds", "Number of Rounds",
                            list(datos.get("rounds", ["1"])))
            self._add_combo(left_col, "round_duration", "Round Duration",
                            list(datos.get("round_duration", ["3 min"])))
            # El área se guarda con la clave «tatami», la del formato; cada
            # deporte la nombra a su manera (tatami, ring…) en sus textos.
            self._add_row(left_col, [
                ("pool", self._i18n.t("bout.pool"), True, None),
                ("tatami", self._i18n.t("bout.tatami"), False,
                 [str(i) for i in range(1, int(datos.get("areas", 8)) + 1)]),
            ])

        # El resultado, con las decisiones del reglamento del deporte (PTF,
        # WP, KO…), si las trae (decisión 0007). El karate no las trae.
        decisiones = [tuple(d) for d in self._datos.get("decisions", [])]
        if decisiones:
            self._add_spacer(left_col, 8)
            self._add_section_header(
                left_col, self._i18n.t("bout.result"),
                icon_name="fa5s.flag-checkered", icon_color=_C_ACCENT,
            )
            self._add_combo(left_col, "bout_winner", self._i18n.t("bout.winner"),
                            [self._athlete_a_label, self._athlete_b_label])
            self._add_combo(left_col, "bout_ending", self._i18n.t("bout.decision"),
                            [(f"{codigo} — {texto}", codigo) for codigo, texto in decisiones])

        left_col.addStretch()
        left_scroll.setWidget(left_widget)
        columns.addWidget(left_scroll, stretch=1)

        # ── Vertical divider ───────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setStyleSheet(
            f"background:{_C_BORDER};"
            "min-width:1px;max-width:1px;"
            "border:none;"
        )
        columns.addWidget(div)

        # ── RIGHT scroll area ──────────────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setStyleSheet(_SCROLLBAR_STYLE)
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        right_widget = QWidget()
        right_widget.setStyleSheet("background:transparent;")
        right_col = QVBoxLayout(right_widget)
        right_col.setContentsMargins(20, 0, 0, 0)
        right_col.setSpacing(16)

        # ── Corner color palette ────────────────────────────
        _CORNER_COLORS = ["Red", "Blue", "White", "Black", "Green", "Yellow"]

        a_label = self._athlete_a_label
        b_label = self._athlete_b_label
        # El color de cada competidor, el de su deporte: en el taekwondo el
        # primero, Chung, es azul (decisión 0007); antes salía en rojo.
        colores = self._colores_del_deporte(self._sport_id)
        a_color = colores.get("aka", _C_RED_AKA)
        b_color = colores.get("ao", _C_BLUE_AO)

        # Athlete A
        a_tag = "a" if self._sport_id == "kickboxing" else ""
        self._add_section_header(
            right_col, a_label,
            icon_name="fa5s.user", icon_color=a_color,
            tag=a_tag,
        )
        self._add_field(right_col, "athlete_a_name", self._i18n.t("bout.athlete_name"))
        if self._sport_id == "kickboxing":
            self._add_combo(right_col, "athlete_a_corner", f"{a_label} Corner",
                _CORNER_COLORS, on_change=lambda: self._on_corner_changed("a"))
        self._add_combo(right_col, "athlete_a_country", self._i18n.t("bout.country"), _PAISES)
        self._add_field(right_col, "athlete_a_club", self._i18n.t("bout.club"))
        guardias = list(self._datos.get("guards", []))
        if guardias:
            self._add_combo(right_col, "athlete_a_guard", self._i18n.t("bout.guard"), guardias)

        self._add_spacer(right_col, 4)

        # Subtle horizontal rule between athletes
        ath_sep = QFrame()
        ath_sep.setFrameShape(QFrame.HLine)
        ath_sep.setStyleSheet(
            f"background:{_C_BORDER};"
            "min-height:1px;max-height:1px;"
            "border:none;"
        )
        right_col.addWidget(ath_sep)
        self._add_spacer(right_col, 4)

        # Athlete B
        b_tag = "b" if self._sport_id == "kickboxing" else ""
        self._add_section_header(
            right_col, b_label,
            icon_name="fa5s.user", icon_color=b_color,
            tag=b_tag,
        )
        self._add_field(right_col, "athlete_b_name", self._i18n.t("bout.athlete_name"))
        if self._sport_id == "kickboxing":
            self._add_combo(right_col, "athlete_b_corner", f"{b_label} Corner",
                _CORNER_COLORS, on_change=lambda: self._on_corner_changed("b"))
        self._add_combo(right_col, "athlete_b_country", self._i18n.t("bout.country"), _PAISES)
        self._add_field(right_col, "athlete_b_club", self._i18n.t("bout.club"))
        if guardias:
            self._add_combo(right_col, "athlete_b_guard", self._i18n.t("bout.guard"), guardias)

        right_col.addStretch()
        right_scroll.setWidget(right_widget)
        columns.addWidget(right_scroll, stretch=1)

        inner_root.addLayout(columns, stretch=1)

        # ── Bottom separator ───────────────────────────────────
        inner_root.addSpacing(14)
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(
            f"background:{_C_BORDER};"
            "min-height:1px;max-height:1px;"
            "border:none;"
        )
        inner_root.addWidget(sep2)
        inner_root.addSpacing(16)

        # ── Bout # & Round row ─────────────────────────────────
        bout_row = QHBoxLayout()
        bout_row.setSpacing(20)
        self._add_field(bout_row, "bout_number", self._i18n.t("bout.bout_number"), expand=True)
        self._add_field(bout_row, "bout_round", self._i18n.t("bout.round"), expand=True)
        inner_root.addLayout(bout_row)

        inner_root.addSpacing(16)

        # ── Separator ──────────────────────────────────────────
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet(
            f"background:{_C_BORDER};"
            "min-height:1px;max-height:1px;"
            "border:none;"
        )
        inner_root.addWidget(sep3)
        inner_root.addSpacing(16)

        # ── Evaluator section ─────────────────────────────────
        self._add_section_header(
            inner_root, self._i18n.t("bout.evaluator"),
            icon_name="fa5s.user-edit", icon_color=_C_ACCENT,
        )

        eval_row = QHBoxLayout()
        eval_row.setSpacing(20)
        self._add_field(eval_row, "evaluator_name", self._i18n.t("bout.evaluator_name"), expand=True)
        self._add_field(eval_row, "evaluator_institution", self._i18n.t("bout.institution"), expand=True)
        self._add_field(eval_row, "analysis_date", self._i18n.t("bout.analysis_date"), expand=True)
        inner_root.addLayout(eval_row)

        inner_root.addSpacing(20)

        # ── Action buttons ────────────────────────────────────
        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addStretch()

        cancel_btn = QPushButton(self._i18n.t("bout.cancel"))
        cancel_btn.setStyleSheet(_CANCEL_BTN_STYLE)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)

        save_icon = qta.icon("fa5s.save", color=_p.bg_root)
        save_btn = QPushButton(self._i18n.t("bout.save"))
        save_btn.setIcon(save_icon)
        save_btn.setStyleSheet(_SAVE_BTN_STYLE)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._on_save)
        save_btn.setDefault(True)
        actions.addWidget(save_btn)

        inner_root.addLayout(actions)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _INPUT_STYLE(self) -> str:
        """Return the correct input style for the current sport."""
        return _INPUT_STYLE_KB if self._sport_id == "kickboxing" else _INPUT_STYLE_KARATE

    @property
    def _COMBO_STYLE(self) -> str:
        """Return the correct combo style for the current sport."""
        return _COMBO_STYLE_KB if self._sport_id == "kickboxing" else _COMBO_STYLE_KARATE

    def _add_section_header(
        self,
        layout: QVBoxLayout,
        text: str,
        icon_name: Optional[str] = None,
        icon_color: str = _C_ACCENT,
        tag: str = "",
    ) -> None:
        """Add a section header with an optional qtawesome icon."""
        row = QHBoxLayout()
        row.setSpacing(6)

        if icon_name:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(
                qta.icon(icon_name, color=icon_color).pixmap(16, 16)
            )
            icon_lbl.setFixedSize(20, 20)
            icon_lbl.setStyleSheet("background:transparent;border:none;")
            row.addWidget(icon_lbl)

        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{icon_color};font-size:12px;font-weight:600;"
            "letter-spacing:0.8px;text-transform:uppercase;"
            "background:transparent;border:none;"
        )
        row.addWidget(lbl)
        row.addStretch()
        layout.addLayout(row)
        # Store reference for corner color updates
        if tag:
            self._corner_headers[tag] = lbl

    def _add_spacer(self, layout: QVBoxLayout, size: int) -> None:
        layout.addSpacing(size)

    def _add_field(
        self,
        parent_layout,
        key: str,
        label: str,
        expand: bool = False,
    ) -> None:
        """Add a labeled QLineEdit with proper native spacing."""
        # Use a wrapper QVBoxLayout inside a QWidget when expand is True
        # to ensure stretch works correctly in horizontal parent layouts.
        if isinstance(parent_layout, QHBoxLayout) and expand:
            wrapper = QVBoxLayout()
            wrapper.setSpacing(8)

            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"color:{_C_MUTED};font-size:{_FONT_SIZE_LABEL};font-weight:600;"
                "letter-spacing:0.5px;text-transform:uppercase;"
                "background:transparent;border:none;"
                "padding-bottom:2px;"
            )
            wrapper.addWidget(lbl)

            edit = QLineEdit()
            edit.setStyleSheet(self._INPUT_STYLE)
            edit.setPlaceholderText(self._i18n.t("bout.placeholder"))
            wrapper.addWidget(edit)
            self._inputs[key] = edit

            parent_layout.addLayout(wrapper, stretch=1)
        else:
            inner = QVBoxLayout()
            inner.setSpacing(8)

            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"color:{_C_MUTED};font-size:{_FONT_SIZE_LABEL};font-weight:600;"
                "letter-spacing:0.5px;text-transform:uppercase;"
                "background:transparent;border:none;"
                "padding-bottom:2px;"
            )
            inner.addWidget(lbl)

            edit = QLineEdit()
            edit.setStyleSheet(self._INPUT_STYLE)
            edit.setPlaceholderText(self._i18n.t("bout.placeholder"))
            inner.addWidget(edit)
            self._inputs[key] = edit

            parent_layout.addLayout(inner)

    def _add_combo(
        self,
        parent_layout,
        key: str,
        label: str,
        items: list[str],
        on_change: Optional[callable] = None,
    ) -> None:
        """Add a labeled QComboBox with proper native spacing."""
        inner = QVBoxLayout()
        inner.setSpacing(8)

        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"color:{_C_MUTED};font-size:{_FONT_SIZE_LABEL};font-weight:600;"
            "letter-spacing:0.5px;text-transform:uppercase;"
            "background:transparent;border:none;"
            "padding-bottom:2px;"
        )
        inner.addWidget(lbl)

        combo = QComboBox()
        combo.setStyleSheet(self._COMBO_STYLE)
        combo.addItem(self._i18n.t("bout.select"), None)
        # Un elemento es un texto, o un par (lo que se enseña, lo que se
        # guarda): «PTF — final score» se guarda «PTF».
        for item in items:
            texto, dato = item if isinstance(item, (tuple, list)) else (item, item)
            combo.addItem(texto, dato)
        if on_change:
            combo.currentIndexChanged.connect(on_change)
        inner.addWidget(combo)
        self._combos[key] = combo
        parent_layout.addLayout(inner)

    def _add_row(
        self,
        layout: QVBoxLayout,
        fields: list[tuple[str, str, bool, Optional[list[str]]]],
    ) -> None:
        """Add a horizontal row of fields (combos or text)."""
        row = QHBoxLayout()
        row.setSpacing(16)
        for key, label, expand, items in fields:
            inner = QVBoxLayout()
            inner.setSpacing(8)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"color:{_C_MUTED};font-size:{_FONT_SIZE_LABEL};font-weight:600;"
                "letter-spacing:0.5px;text-transform:uppercase;"
                "background:transparent;border:none;"
                "padding-bottom:2px;"
            )
            inner.addWidget(lbl)

            if items:
                combo = QComboBox()
                combo.setStyleSheet(self._COMBO_STYLE)
                combo.addItem("—", None)
                for item in items:
                    combo.addItem(item, item)
                inner.addWidget(combo)
                self._combos[key] = combo
            else:
                edit = QLineEdit()
                edit.setStyleSheet(self._INPUT_STYLE)
                edit.setPlaceholderText("—")
                inner.addWidget(edit)
                self._inputs[key] = edit

            if expand:
                row.addLayout(inner, stretch=1)
            else:
                row.addLayout(inner)
        layout.addLayout(row)

    # ------------------------------------------------------------------
    # Dynamic weight filtering
    # ------------------------------------------------------------------

    _CORNER_HEX: dict[str, str] = {
        "Red": _C_RED_AKA, "Blue": _C_BLUE_AO, "White": _p.grey_light,
        "Black": "#1A1A1A", "Green": _C_GREEN, "Yellow": _C_ACCENT,
    }
    @staticmethod
    def _datos_del_deporte(sport_id: str) -> dict:
        """Lo que el deporte trae para esta ventana («bout_info» de su
        configuración): categorías, pesos, asaltos y número de áreas."""
        from karlos_core import catalogo
        try:
            paquete = catalogo.paquete(sport_id)
        except KeyError:
            return {}
        datos = dict(paquete.configuracion().get("bout_info", {}))
        return datos

    @staticmethod
    def _colores_del_deporte(sport_id: str) -> dict:
        from karlos_core import catalogo
        try:
            return dict(catalogo.paquete(sport_id).configuracion().get("colors", {}))
        except KeyError:
            return {}

    def _pesos_de(self, clave: str) -> list[str]:
        """Los pesos de esa clave (el sexo, o la categoría del karate).

        Si el deporte los parte por edad, debajo hay otro piso con la
        categoría de edad: el taekwondo tiene una tabla para senior, otra
        para junior y otra para cadete (WT art. 5).
        """
        tabla = self._datos.get("weights", {}).get(clave, [])
        if isinstance(tabla, dict):
            edad = self._combos.get("age_category")
            return list(tabla.get(edad.currentData() if edad is not None else None, []))
        return list(tabla)

    def _duraciones_de(self, asaltos: str) -> list[str]:
        """Las duraciones que el reglamento permite con ese número de asaltos.

        Una lista suelta vale para todos (el kickboxing); un diccionario, no:
        el taekwondo son 2 min × 3, pero el Delegado Técnico puede poner
        1 min × 3, 1 min 30 s × 3, 2 min × 2 o 5 min × 1 (art. 7.2).
        """
        tabla = self._datos.get("round_duration", [])
        if isinstance(tabla, dict):
            return list(tabla.get(asaltos, []))
        return list(tabla)

    def _on_rounds_changed(self) -> None:
        """Rehacer las duraciones cuando cambia el número de asaltos."""
        duracion = self._combos.get("round_duration")
        asaltos = self._combos.get("num_rounds")
        if not duracion or not asaltos:
            return
        self._rellenar(duracion, self._duraciones_de(asaltos.currentData()))
    _corner_headers: dict[str, QLabel] = {}

    def _on_corner_changed(self, athlete: str) -> None:
        """Update section header color when corner combo changes."""
        key = f"athlete_{athlete}_corner"
        combo = self._combos.get(key)
        if not combo:
            return
        color_name = combo.currentText()
        hex_color = self._CORNER_HEX.get(color_name, _C_RED_AKA)
        # Update the section header QLabel in real-time
        header_label = self._corner_headers.get(athlete)
        if header_label:
            header_label.setStyleSheet(
                f"color:{hex_color};font-size:12px;font-weight:600;"
                "letter-spacing:0.8px;text-transform:uppercase;"
                "background:transparent;border:none;"
            )
        self._corner_colors = getattr(self, "_corner_colors", {})
        self._corner_colors[athlete] = hex_color

    @staticmethod
    def _rellenar(combo, opciones: list[str]) -> None:
        """Rehacer un desplegable que depende de otro, sin perder lo elegido
        si sigue estando."""
        actual = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("— Select —", None)
        for opcion in opciones:
            combo.addItem(opcion, opcion)
        if actual in opciones:
            combo.setCurrentText(actual)
        combo.blockSignals(False)

    def _on_gender_changed(self) -> None:
        """Update weight_category combo based on selected gender (and age)."""
        weight_combo = self._combos.get("weight_category")
        gender_combo = self._combos.get("gender")
        if not weight_combo or not gender_combo:
            return
        self._rellenar(weight_combo, self._pesos_de(gender_combo.currentData()))

    def _on_category_changed(self) -> None:
        """Update weight_category combo based on selected category type."""
        weight_combo = self._combos.get("weight_category")
        category_combo = self._combos.get("category_type")
        if not weight_combo or not category_combo:
            return
        self._rellenar(weight_combo, self._pesos_de(category_combo.currentData()))

    # ------------------------------------------------------------------
    # Prefill & Save
    # ------------------------------------------------------------------

    # Las que no tienen lista propia: la hace el desplegable del que
    # dependen (el sexo y la edad, o el número de asaltos).
    _DEPENDIENTES = ("weight_category", "round_duration")

    def _restaurar(self, claves) -> None:
        """Poner en los campos lo que se guardó, cuando sigue existiendo."""
        for key in claves:
            widget_key = self._KEY_TO_WIDGET[key]
            value = self._existing_data.get(key, "")
            if not value:
                continue
            if widget_key in self._combos:
                combo = self._combos[widget_key]
                idx = combo.findData(value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                elif combo.findText(value) >= 0:
                    combo.setCurrentText(value)
            elif widget_key in self._inputs:
                self._inputs[widget_key].setText(value)

    def _prefill(self) -> None:
        """Pre-fill the form with existing saved metadata."""
        # Cada una solo actúa si su desplegable existe en este deporte.
        if not self._existing_data:
            self._on_gender_changed()
            self._on_category_changed()
            self._on_rounds_changed()
            return
        self._restaurar(self._KEY_TO_WIDGET)
        self._on_category_changed()
        self._on_gender_changed()
        self._on_rounds_changed()
        # Y ahora las que dependían de ellas. Se restauraban contra un
        # desplegable todavía vacío, así que al reabrir la ventana el peso
        # del combate aparecía sin elegir y se guardaba vacío.
        self._restaurar(self._DEPENDIENTES)

    def _on_save(self) -> None:
        """Read all fields into bout_info dict and accept."""
        self.bout_info = {}

        for key, widget_key in self._KEY_TO_WIDGET.items():
            if widget_key in self._combos:
                data = self._combos[widget_key].currentData()
                self.bout_info[key] = str(data) if data else ""
            elif widget_key in self._inputs:
                self.bout_info[key] = self._inputs[widget_key].text().strip()

        # Backward-compat alias: match_report & project_hub expect "bout_event"
        if self.bout_info.get("competition_name"):
            self.bout_info["bout_event"] = self.bout_info["competition_name"]

        # ── Sync corner colors to hex for UI components ─────
        _CORNER_HEX: dict[str, str] = {
            "Red": _C_RED_AKA, "Blue": _C_BLUE_AO, "White": _p.grey_light,
            "Black": "#1A1A1A", "Green": _C_GREEN, "Yellow": _C_ACCENT,
        }
        self.bout_info["athlete_a_color"], self.bout_info["athlete_b_color"] = \
            colores_de_esquinas(self.bout_info, self._sport_id)

        # ── Persist evaluator info for next session ─────────
        if self.bout_info.get("evaluator_name"):
            self._settings.setValue("evaluator/name", self.bout_info["evaluator_name"])
        if self.bout_info.get("evaluator_institution"):
            self._settings.setValue("evaluator/institution", self.bout_info["evaluator_institution"])

        self.accept()