"""Detail popup dialog for technique level and scoring selection in KARLOS ANNOTATOR.

Displays a modal dialog allowing the annotator to select target level
(Jodan/Chudan) and scoring outcome (IPPON/WAZA/YUKO/NONE/FOUL) for a
selected technique.

v6.1 — Premium Dark Pro UX:
    - Score buttons auto-validate & close the dialog (no Confirm button
      needed in "full" mode). Clicking IPPON/WAZA/... immediately accepts
      once all required level dimensions are selected.
    - Hollow-to-Fill premium QSS styling with per-score objectNames.
    - QButtonGroup exclusive selection for every option row.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from karlos_core.models.technique import AppColors, ScoringEngine, ScoringRule
from karlos_core.views.theme import Palette
from karlos_core.views.animaciones import aparecer

# ══════════════════════════════════════════════════════════════════
# PREMIUM DARK PRO STYLESHEET (QSS) — resolves Palette tokens
# ══════════════════════════════════════════════════════════════════

def _build_detail_popup_qss(p: Palette) -> str:
    """Build the detail popup QSS from a Palette instance."""
    return f"""
QDialog {{ background-color: {p.bg_alt}; }}

QLabel {{
    color: {p.text_disabled};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    background: transparent;
    border: none;
}}

QLabel#popup_header {{
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0px;
}}

QLabel#hint_label {{
    color: {p.border_hover};
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0px;
    font-style: italic;
}}

/* Botones Base (Stance, Level, Action) */
QPushButton {{
    background-color: {p.surface_2}; color: {p.text_disabled};
    border: 1px solid {p.border_default}; border-radius: 6px;
    padding: 10px; font-weight: bold; font-size: 13px;
}}
QPushButton:hover {{ background-color: {p.surface_3}; color: {p.text_bright}; border-color: {p.border_hover}; }}
QPushButton:checked {{ background-color: {p.accent_blue}; color: {p.text_inverse}; border-color: {p.accent_blue_light}; }}

/* Botones de Puntuación (Premium Hollow-to-Fill) */
QPushButton#score_ippon {{ background-color: {p.ippon_bg}; color: {p.ippon_fg}; border: 1px solid {p.ippon_fg}; }}
QPushButton#score_ippon:hover {{ background-color: {p.ippon_fg}; color: {p.bg_alt}; }}
QPushButton#score_ippon:checked {{ background-color: {p.ippon_fg}; color: {p.bg_alt}; border: 2px solid {p.ippon_glow}; }}

QPushButton#score_waza {{ background-color: {p.ao_dim}; color: {p.accent_blue_light}; border: 1px solid {p.accent_blue_light}; }}
QPushButton#score_waza:hover {{ background-color: {p.accent_blue_light}; color: {p.bg_alt}; }}
QPushButton#score_waza:checked {{ background-color: {p.accent_blue_light}; color: {p.bg_alt}; border: 2px solid {p.accent_blue_lighter}; }}

QPushButton#score_yuko {{ background-color: {p.yuko_bg}; color: {p.text_bright}; border: 1px solid {p.text_disabled}; }}
QPushButton#score_yuko:hover {{ background-color: {p.text_disabled}; color: {p.bg_alt}; }}
QPushButton#score_yuko:checked {{ background-color: {p.text_disabled}; color: {p.bg_alt}; border: 2px solid {p.border_checked_glow}; }}

QPushButton#score_none {{ background-color: {p.bg_alt}; color: {p.border_hover}; border: 1px dashed {p.border_default}; }}
QPushButton#score_none:hover {{ border: 1px solid {p.text_disabled}; color: {p.text_bright}; }}
QPushButton#score_none:checked {{ background-color: {p.border_default}; color: {p.text_bright}; border: 2px solid {p.text_disabled}; }}

QPushButton#score_foul {{ background-color: {p.aka_dim}; color: {p.aka}; border: 1px solid {p.aka}; }}
QPushButton#score_foul:hover {{ background-color: {p.aka}; color: {p.bg_alt}; }}
QPushButton#score_foul:checked {{ background-color: {p.aka}; color: {p.bg_alt}; border: 2px solid {p.aka_light}; }}

/* Generic score buttons (other sports: PTS codes, etc.) */
QPushButton#score_generic {{ background-color: {p.yuko_bg}; color: {p.text_bright}; border: 1px solid {p.text_disabled}; }}
QPushButton#score_generic:hover {{ background-color: {p.text_disabled}; color: {p.bg_alt}; }}
QPushButton#score_generic:checked {{ background-color: {p.text_disabled}; color: {p.bg_alt}; border: 2px solid {p.border_checked_glow}; }}

/* Confirm button (only visible in technique/score fallback modes) */
QPushButton#confirm_btn {{
    background-color: {p.success}; color: {p.text_inverse};
    border: 1px solid {p.success_hover}; border-radius: 6px;
    padding: 10px 16px; font-weight: bold; font-size: 13px;
}}
QPushButton#confirm_btn:hover {{ background-color: {p.success_hover}; border-color: {p.success_glow}; }}
"""

# Map score codes → premium objectNames for QSS targeting.
_SCORE_OBJECT_NAMES: dict[str, str] = {
    "IPPON": "score_ippon",
    "WAZA": "score_waza",
    "YUKO": "score_yuko",
    "NONE": "score_none",
    "NO_PT": "score_none",
    "FOUL": "score_foul",
}


class DetailPopup(QDialog):
    """Modal dialog for selecting technique level and scoring outcome.

    Supports three modes:
        - "full": Level dimensions + score. Clicking a score button
          validates required selections and auto-accepts (premium UX —
          no Confirm button needed).
        - "technique": Only level selection; auto-confirms on selection.
        - "score": Only score selection; auto-confirms on selection.

    When ``levels_config`` is provided (multi-level), renders N rows of
    labeled selectors (e.g., Stance → [Lead/Rear], Level → [Jodan/Chudan]).
    Otherwise falls back to the legacy single flat level list.

    Attributes:
        level: Selected target level string (legacy flat, or joined multi-level).
        score: Selected scoring outcome code ("IPPON", "WAZA", etc.).
    """

    def __init__(
        self,
        tech_name: str,
        has_level: bool,
        athlete: str,
        colors: AppColors,
        levels: list[str],
        scoring_rules: list[ScoringRule],
        parent: Optional[QDialog] = None,
        mode: str = "full",
        athlete_a_label: str = "AKA",
        athlete_b_label: str = "AO",
        levels_config: Optional[dict[str, list[str]]] = None,
        scoring_engine: Optional[ScoringEngine] = None,
    ) -> None:
        """Initialize the detail popup.

        Args:
            tech_name: Display name of the selected technique.
            has_level: Whether this technique requires level selection.
            athlete: Current athlete ("AKA" or "AO").
            colors: Application color palette.
            levels: List of target level names (fallback if no levels_config).
            scoring_rules: List of scoring outcome definitions.
            parent: Optional parent widget.
            mode: Popup mode ("full", "technique", "score").
            athlete_a_label: Display label for athlete A (e.g., "AKA", "Red").
            athlete_b_label: Display label for athlete B (e.g., "AO", "Blue").
            levels_config: Optional multi-level dict, e.g.
                {"Stance": ["Lead","Rear"], "Level": ["Jodan","Chudan"]}.
            scoring_engine: Optional ScoringEngine for auto-score suggestions.
        """
        super().__init__(parent)
        aparecer(self)
        from karlos_core.utils.i18n import I18n
        self._i18n = I18n()
        self.setWindowTitle(f"{self._i18n.t('bout.title')} — {tech_name}")
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self._colors = colors
        self._tech_name = tech_name
        self._levels = levels
        self._levels_config = levels_config
        self._scoring_rules = scoring_rules
        self._scoring_engine = scoring_engine
        self._athlete_a_label = athlete_a_label
        self._athlete_b_label = athlete_b_label
        self.level: str = ""
        self.score: str = "NONE"
        self._mode = mode
        self._lv_btns: dict[str, QPushButton] = {}
        self._lv_group: Optional[QButtonGroup] = None
        self._multi_selections: dict[str, str] = {}
        self._multi_btns: dict[str, dict[str, QPushButton]] = {}
        self._multi_groups: dict[str, QButtonGroup] = {}
        self._sc_btns: dict[str, QPushButton] = {}
        self._sc_group: Optional[QButtonGroup] = None
        self._hint_label: Optional[QLabel] = None

        # ── Premium Dark Pro QSS ─────────────────────────────────
        self._p = Palette.from_config(colors)
        self.setStyleSheet(_build_detail_popup_qss(self._p))

        self._build(tech_name, has_level, athlete)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self, tech: str, has_level: bool, athlete: str) -> None:
        """Construct the dialog UI.

        Args:
            tech: Technique display name.
            has_level: Whether level buttons should be shown.
            athlete: Athlete identifier for color coding.
        """
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        color = self._colors.aka if athlete == "AKA" else self._colors.ao
        athlete_label = (
            self._athlete_a_label if athlete == "AKA"
            else self._athlete_b_label
        )
        hdr = QLabel(f"{athlete_label} — {tech}")
        hdr.setObjectName("popup_header")
        hdr.setStyleSheet(
            f"color:{color};font-size:16px;font-weight:700;"
            "background:transparent;border:none;"
        )
        root.addWidget(hdr)

        show_level = self._mode in ("full", "technique")
        show_score = self._mode in ("full", "score")

        if show_level and has_level:
            if self._levels_config:
                self._build_multi_level_section(root)
            else:
                self._build_level_section(root)

        if show_score:
            self._build_score_section(root)

        # ── Hint label: guides user + shows validation warnings ──
        if self._mode == "full":
            self._hint_label = QLabel(
                self._i18n.t("detail.hint_click_score")
                if self._i18n.t("detail.hint_click_score") != "detail.hint_click_score"
                else "Select options, then click a score to confirm"
            )
            self._hint_label.setObjectName("hint_label")
            self._hint_label.setAlignment(Qt.AlignCenter)
            root.addWidget(self._hint_label)

        # ── Confirm button: only for modes WITHOUT score auto-close.
        # In "full" mode the score click itself validates & accepts,
        # and "technique"/"score" modes auto-accept on selection, so
        # the button is kept only as a keyboard-accessible fallback
        # in "technique" mode (Enter key).
        if self._mode != "full":
            ok_btn = QPushButton(self._i18n.t("detail.confirm"))
            ok_btn.setObjectName("confirm_btn")
            ok_btn.setDefault(True)
            ok_btn.clicked.connect(self.accept)
            root.addWidget(ok_btn)

    def _build_level_section(self, root: QVBoxLayout) -> None:
        """Add target level selection buttons to the layout (legacy flat list).

        Args:
            root: Parent layout to add widgets to.
        """
        root.addWidget(QLabel(self._i18n.t("detail.target_level").upper()))
        lv_row = QHBoxLayout()
        lv_row.setSpacing(8)
        self._lv_group = QButtonGroup(self)
        self._lv_group.setExclusive(True)
        for lv in self._levels:
            btn = QPushButton(lv)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, v=lv: self._pick_level(v))
            lv_row.addWidget(btn)
            self._lv_group.addButton(btn)
            self._lv_btns[lv] = btn
        root.addLayout(lv_row)
        self._pick_level(self._levels[0])

        QShortcut(QKeySequence("J"), self).activated.connect(
            lambda: self._pick_level("Jodan")
        )
        QShortcut(QKeySequence("C"), self).activated.connect(
            lambda: self._pick_level("Chudan")
        )

    def _build_score_section(self, root: QVBoxLayout) -> None:
        """Add scoring outcome selection buttons to the layout.

        Each score button gets a premium objectName (score_ippon,
        score_waza, ...) for QSS targeting, and clicking it triggers
        on_score_selected() which validates & auto-accepts.

        Args:
            root: Parent layout to add widgets to.
        """
        root.addWidget(QLabel(self._i18n.t("detail.scoring_outcome").upper()))
        self._sc_group = QButtonGroup(self)
        self._sc_group.setExclusive(True)
        for rule in self._scoring_rules:
            btn = QPushButton(rule.label)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setObjectName(
                _SCORE_OBJECT_NAMES.get(rule.code, "score_generic")
            )
            btn.clicked.connect(
                lambda _, v=rule.code: self.on_score_selected(v)
            )
            root.addWidget(btn)
            self._sc_group.addButton(btn)
            self._sc_btns[rule.code] = btn

            sh = QShortcut(QKeySequence(rule.shortcut), self)
            sh.activated.connect(
                lambda v=rule.code: self.on_score_selected(v)
            )

    # ------------------------------------------------------------------
    # Selection handlers
    # ------------------------------------------------------------------

    def _pick_level(self, value: str) -> None:
        """Select a target level and update button states (legacy flat list).

        Args:
            value: Level name to select.
        """
        self.level = value
        for lv, btn in self._lv_btns.items():
            btn.setChecked(lv == value)
        # Auto-accept only in "technique" mode (level-only, no score).
        if self._mode == "technique":
            self.accept()

    def on_score_selected(self, score_value: str) -> None:
        """Handle a score button click: validate, persist, auto-accept.

        Premium UX flow — the score click is the FINAL action:
        1. Verify all required level dimensions are selected.
        2. If incomplete → flash a visual warning, keep dialog open.
        3. If complete → store score and self.accept() immediately,
           sending the data back to the AnnotationFlowController.

        Args:
            score_value: Scoring outcome code (e.g., "IPPON").
        """
        # ── Validate required selections (multi-level dimensions) ──
        if self._mode == "full" and not self._required_selections_complete():
            # Undo the visual check on the clicked button
            btn = self._sc_btns.get(score_value)
            if btn is not None:
                self._sc_group.setExclusive(False)
                btn.setChecked(False)
                self._sc_group.setExclusive(True)
            self._flash_hint_warning()
            return

        # ── Persist & highlight ──
        self.score = score_value
        for code, btn in self._sc_btns.items():
            btn.setChecked(code == score_value)

        # ── Auto-accept: score click is the final confirmation ──
        if self._mode in ("full", "score"):
            self.accept()

    def _set_score_visual(self, score_value: str) -> None:
        """Highlight a score button WITHOUT accepting (auto-suggestion).

        Used by the ScoringEngine to visually suggest a score when the
        user picks a level dimension. Never closes the dialog.

        Args:
            score_value: Scoring outcome code to highlight.
        """
        self.score = score_value
        for code, btn in self._sc_btns.items():
            btn.setChecked(code == score_value)

    def _required_selections_complete(self) -> bool:
        """Check whether all mandatory level dimensions are selected.

        Returns:
            True if every dimension in levels_config has a selection
            (or the technique uses the legacy flat level list).
        """
        if self._levels_config:
            return all(
                dim in self._multi_selections and self._multi_selections[dim]
                for dim in self._levels_config
            )
        # Legacy flat list: a level is always pre-selected.
        return True

    def _flash_hint_warning(self) -> None:
        """Flash the hint label in red to indicate missing selections."""
        if self._hint_label is None:
            return
        missing = [
            dim for dim in (self._levels_config or {})
            if dim not in self._multi_selections
        ]
        warn_text = (
            f"⚠ Select: {', '.join(missing)}" if missing
            else "⚠ Complete all selections first"
        )
        self._hint_label.setText(warn_text)
        self._hint_label.setStyleSheet(
            f"color:{self._p.aka};font-size:11px;font-weight:700;"
            "background:transparent;border:none;"
        )
        QTimer.singleShot(1800, self._reset_hint)

    def _reset_hint(self) -> None:
        """Restore the hint label to its neutral state."""
        if self._hint_label is None:
            return
        self._hint_label.setText(
            "Select options, then click a score to confirm"
        )
        self._hint_label.setStyleSheet("")
        self._hint_label.setObjectName("hint_label")
        # Re-polish so the objectName QSS re-applies
        self._hint_label.style().unpolish(self._hint_label)
        self._hint_label.style().polish(self._hint_label)

    # ------------------------------------------------------------------
    # Multi-Level section (Karate combinatorial, Taekwondo kicks, etc.)
    # ------------------------------------------------------------------

    def _build_multi_level_section(self, root: QVBoxLayout) -> None:
        """Add N rows of labeled toggle selectors for multi-level techniques.

        Each key in levels_config becomes a labeled row of exclusive
        toggle buttons managed by a QButtonGroup. The first option in
        each row is auto-selected as a sensible default.

        Args:
            root: Parent layout to add widgets to.
        """
        if not self._levels_config:
            return

        for label, options in self._levels_config.items():
            section_label = QLabel(f"{label.upper()}")
            root.addWidget(section_label)

            # Hasta cuatro opciones van en una fila, como siempre. Con más
            # se reparten: las siete de la táctica del taekwondo en una
            # sola fila salían cortadas («rect At», «us Cou»), y hay que
            # poder leer lo que se elige.
            row = QGridLayout()
            row.setSpacing(8)
            columnas = len(options) if len(options) <= 4 else (
                2 if max(len(o) for o in options) > 12 else 4)
            self._multi_btns[label] = {}

            group = QButtonGroup(self)
            group.setExclusive(True)
            self._multi_groups[label] = group

            first = True
            for i, opt in enumerate(options):
                btn = QPushButton(opt)
                btn.setCheckable(True)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(
                    lambda _, l=label, o=opt: self._pick_multi(l, o)
                )
                row.addWidget(btn, i // columnas, i % columnas)
                group.addButton(btn)
                self._multi_btns[label][opt] = btn

                if first:
                    btn.setChecked(True)
                    self._multi_selections[label] = opt
                    first = False

            root.addLayout(row)

        # Initialize combined level string from defaults
        self._sync_level_string()

    def _sync_level_string(self) -> None:
        """Recompute the combined ``self.level`` string from selections."""
        parts = [
            f"{dim}: {self._multi_selections[dim]}"
            for dim in self._multi_selections
        ]
        self.level = " | ".join(parts)

    def _pick_multi(self, label: str, value: str) -> None:
        """Select a value for a multi-level dimension.

        Args:
            label: Dimension name (e.g., "Stance").
            value: Selected value (e.g., "Lead").
        """
        self._multi_selections[label] = value
        for opt, btn in self._multi_btns[label].items():
            btn.setChecked(opt == value)
        self._sync_level_string()

        # ── Auto-suggest score using ScoringEngine (visual only) ──
        # The suggestion highlights the score button but NEVER closes
        # the dialog — the user's explicit score click is the final
        # confirmation (see on_score_selected).
        if self._scoring_engine and self._mode == "full":
            # Karate combinatorial: auto-score depends on the "Level"
            # dimension (Jodan/Chudan), not Stance or Action.
            level_value = (
                value if label == "Level"
                else self._multi_selections.get("Level", "")
            )
            if level_value:
                suggested_score = self._scoring_engine.calculate_score(
                    self._tech_name, level_value
                )
                if suggested_score and suggested_score != "NONE":
                    self._set_score_visual(suggested_score)
            # Taekwondo: auto-score depends on "Strike Area"
            elif label == "Strike Area":
                suggested_score = self._scoring_engine.calculate_score(
                    self._tech_name, value
                )
                if suggested_score and suggested_score != "NONE":
                    self._set_score_visual(suggested_score)
            # Kickboxing: auto-score depends on "Target"
            elif label == "Target":
                suggested_score = self._scoring_engine.calculate_score(
                    self._tech_name, value
                )
                if suggested_score and suggested_score != "NONE":
                    self._set_score_visual(suggested_score)

        # Auto-accept in "technique" mode (level-only, no score)
        if self._mode == "technique":
            self.accept()
