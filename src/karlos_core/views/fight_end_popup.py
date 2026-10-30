"""Fight end popup for KARLOS ANNOTATOR.

Dialog displayed when the user marks the end of a fight segment via [G]
or the "FIGHT END" button. Shows a summary of the recorded segment and
offers contextual actions depending on whether one or both athletes have
been analyzed.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karlos_core.models.technique import AppColors
from karlos_core.views.theme import Palette
from karlos_core.views.animaciones import aparecer


class FightEndPopup(QDialog):
    """Post-fight-segment dialog with export and analysis options.

    Signals:
        export_requested: Emitted when user clicks the export button.
        analyze_other_athlete_requested: Emitted when user chooses to
            switch to the other athlete for a second analysis pass.
        new_bout_requested: Emitted when user wants to start a new bout.
    """

    export_requested = Signal()
    analyze_other_athlete_requested = Signal()
    new_bout_requested = Signal()
    continue_current_requested = Signal()
    next_fight_requested = Signal()
    finish_and_export_requested = Signal()

    def __init__(
        self,
        fight_start: Optional[int],
        fight_end: Optional[int],
        duration: Optional[float],
        aka_count: int,
        ao_count: int,
        aka_label: str = "Athlete A (AKA)",
        ao_label: str = "Athlete B (AO)",
        colors: Optional[AppColors] = None,
        parent: Optional[QWidget] = None,
        current_athlete: str = "AKA",
        current_round: int = 0,
        num_rounds: int = 0,
    ) -> None:
        """Initialize the fight end popup.

        Args:
            fight_start: Fight start frame index (or None).
            fight_end: Fight end frame index (or None).
            duration: Fight duration in seconds (or None).
            aka_count: Number of annotations for athlete A.
            ao_count: Number of annotations for athlete B.
            aka_label: Display label for athlete A.
            ao_label: Display label for athlete B.
            colors: Application color palette.
            parent: Optional parent widget.
            current_athlete: 'AKA' or 'AO' — who was being annotated.
        """
        super().__init__(parent)
        aparecer(self)
        self._fight_start = fight_start
        self._fight_end = fight_end
        self._duration = duration
        self._aka_count = aka_count
        self._ao_count = ao_count
        self._aka_label = aka_label
        self._ao_label = ao_label
        self._current_athlete = current_athlete
        self._both_analyzed = aka_count > 0 and ao_count > 0
        self._current_round = current_round
        self._num_rounds = num_rounds

        self._p = Palette.from_config(colors) if colors else Palette()

        from karlos_core.utils.i18n import I18n
        self._i18n = I18n()
        self.setWindowTitle(self._i18n.t("fightend.title"))
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setMaximumWidth(560)
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the dialog UI."""
        p = self._p
        self.setStyleSheet(f"background:{p.bg_root};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # Title
        title = QLabel(self._i18n.t("fightend.heading"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color:{p.text_primary};"
            "font-family:'SF Pro Display',-apple-system,'Inter',sans-serif;"
            "font-size:18px;font-weight:600;letter-spacing:0.3px;"
            "background:transparent;border:none;"
        )
        layout.addWidget(title)

        subtitle = QLabel(self._i18n.t("fightend.subtitle"))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            f"color:{p.text_secondary};"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:13px;font-weight:400;"
            "background:transparent;border:none;"
        )
        layout.addWidget(subtitle)

        # Separator
        sep1 = QLabel()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background:{p.border_subtle};")
        layout.addWidget(sep1)

        # Stats section
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(8)

        fs_str = str(self._fight_start) if self._fight_start is not None else "--"
        fe_str = str(self._fight_end) if self._fight_end is not None else "--"
        dur_str = f"{self._duration:.1f}s" if self._duration is not None else "--"

        stats_layout.addWidget(
            self._stat_row(self._i18n.t("fightend.fight_start"), self._i18n.t("fightend.frame", frame=fs_str))
        )
        stats_layout.addWidget(
            self._stat_row(self._i18n.t("fightend.fight_end"), self._i18n.t("fightend.frame", frame=fe_str))
        )
        stats_layout.addWidget(
            self._stat_row(self._i18n.t("fightend.duration"), dur_str)
        )
        stats_layout.addWidget(self._stat_spacer())
        stats_layout.addWidget(
            self._stat_row(
                self._aka_label,
                self._i18n.t("fightend.annotations", count=str(self._aka_count)),
                p.aka,
            )
        )
        stats_layout.addWidget(
            self._stat_row(
                self._ao_label,
                self._i18n.t("fightend.annotations", count=str(self._ao_count)) if self._ao_count > 0 else self._i18n.t("fightend.not_analyzed"),
                p.ao,
            )
        )

        if self._both_analyzed:
            total = self._aka_count + self._ao_count
            stats_layout.addWidget(self._stat_spacer())
            stats_layout.addWidget(
                self._stat_row(self._i18n.t("fightend.total"), self._i18n.t("fightend.records", count=str(total)), p.accent)
            )

        layout.addLayout(stats_layout)

        # Separator
        sep2 = QLabel()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{p.border_subtle};")
        layout.addWidget(sep2)

        # Action buttons — context-dependent
        # ── Round-aware buttons (only if num_rounds is configured) ─
        has_rounds = self._num_rounds > 0
        is_last_round = has_rounds and self._current_round >= self._num_rounds

        if self._both_analyzed:
            if not has_rounds:
                # No rounds configured — simple finish
                layout.addWidget(
                    self._action_button(
                        "SAVE ANALYSIS",
                        "Save all data and mark fight as completed",
                        True,
                        self._on_finish_and_close,
                    )
                )
            elif is_last_round:
                layout.addWidget(
                    self._action_button(
                        "SAVE ANALYSIS",
                        "Save all data and mark fight as completed",
                        True,
                        self._on_finish_and_close,
                    )
                )
                layout.addWidget(
                    self._action_button(
                        self._i18n.t("fightend.next_fight"),
                        self._i18n.t("fightend.next_fight_desc"),
                        False,
                        self._on_next_fight,
                    )
                )
            else:
                layout.addWidget(
                    self._action_button(
                        f"NEXT ROUND ({self._current_round + 1} of {self._num_rounds})",
                        f"Press [F] to start Round {self._current_round + 1}",
                        True,
                        self._on_next_round,
                    )
                )
                layout.addWidget(
                    self._action_button(
                        "FINISH FIGHT",
                        self._i18n.t("fightend.finish_export_desc"),
                        False,
                        self.finish_and_export_requested.emit,
                    )
                )
        else:
            # Only one athlete analyzed — offer the other or continue same
            if self._current_athlete == "AKA":
                other_label = self._ao_label
            else:
                other_label = self._aka_label
            layout.addWidget(
                self._action_button(
                    self._i18n.t("fightend.analyze", athlete=other_label.upper()),
                    self._i18n.t("fightend.analyze_desc"),
                    True,
                    self.analyze_other_athlete_requested.emit,
                )
            )
            layout.addWidget(
                self._action_button(
                    self._i18n.t("fightend.continue"),
                    self._i18n.t("fightend.continue_desc"),
                    False,
                    self._on_continue_current,
                )
            )

    def _stat_row(
        self,
        label: str,
        value: str,
        value_color: Optional[str] = None,
    ) -> QWidget:
        """Create a horizontal stat row.

        Args:
            label: Left-aligned label.
            value: Right-aligned value.
            value_color: Optional color for the value text.

        Returns:
            QWidget containing the row.
        """
        p = self._p
        row = QWidget()
        row.setStyleSheet("background:transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color:{p.text_secondary};"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:13px;font-weight:400;"
            "background:transparent;border:none;"
        )
        row_layout.addWidget(lbl)
        row_layout.addStretch()

        val = QLabel(value)
        color = value_color if value_color else p.text_primary
        val.setStyleSheet(
            f"color:{color};"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:13px;font-weight:500;"
            "background:transparent;border:none;"
        )
        row_layout.addWidget(val)

        return row

    def _stat_spacer(self) -> QWidget:
        """Create a thin spacer line for the stats section.

        Returns:
            QWidget spacer.
        """
        spacer = QWidget()
        spacer.setFixedHeight(4)
        spacer.setStyleSheet("background:transparent;")
        return spacer

    def _action_button(
        self,
        title: str,
        description: str,
        highlighted: bool,
        callback,
    ) -> QWidget:
        """Create an action button card.

        Args:
            title: Button title (uppercase label).
            description: Brief description of the action.
            highlighted: Whether this is the primary/recommended action.
            callback: Function to call on click.

        Returns:
            QWidget representing the action card.
        """
        p = self._p
        card = QWidget()
        card.setCursor(Qt.PointingHandCursor)

        if highlighted:
            bg = p.accent
            title_color = p.bg_root
            desc_color = p.bg_root
            hover_bg = p.warning
        else:
            bg = p.surface_1
            title_color = p.text_primary
            desc_color = p.text_secondary
            hover_bg = "rgba(255,255,255,0.03)"

        card.setStyleSheet(
            f"QWidget{{"
            f"background:{bg};"
            f"border:1px solid {p.border_subtle};"
            f"border-radius:8px;"
            f"}}"
            f"QWidget:hover{{"
            f"background:{hover_bg};"
            f"border:1px solid {p.border_hover};"
            f"}}"
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"color:{title_color};"
            "font-family:'SF Pro Display',-apple-system,'Inter',sans-serif;"
            "font-size:14px;font-weight:600;letter-spacing:0.5px;"
            "background:transparent;border:none;"
        )
        card_layout.addWidget(title_lbl)

        if description:
            desc_lbl = QLabel(description)
            desc_lbl.setAlignment(Qt.AlignCenter)
            desc_lbl.setStyleSheet(
                f"color:{desc_color};"
                "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
                "font-size:12px;font-weight:400;"
                "background:transparent;border:none;"
            )
            card_layout.addWidget(desc_lbl)

        # Make card clickable
        card.mousePressEvent = lambda e: callback()

        return card

    def _on_finish_and_close(self) -> None:
        """Emit finish-and-export signal then close the dialog."""
        self.finish_and_export_requested.emit()
        self.accept()

    def _on_continue_current(self) -> None:
        """Emit continue signal then close the dialog."""
        self.continue_current_requested.emit()
        self.accept()

    def _on_next_round(self) -> None:
        """Emit next round signal then close the dialog."""
        self.accept()

    def _on_next_fight(self) -> None:
        """Emit next fight signal then close the dialog."""
        self.next_fight_requested.emit()
        self.accept()
