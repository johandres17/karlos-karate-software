"""Session wizard for KARLOS ANNOTATOR.

Multi-step wizard guiding users through video selection, bout information,
fight segment marking, and final confirmation before starting annotation.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from karlos_core.models.technique import AppColors, TaxonomyConfig
from karlos_core.utils.i18n import I18n
from karlos_core.views.theme import Palette
from karlos_core.views.animaciones import aparecer


class SessionWizard(QDialog):
    """Multi-step wizard for creating a new annotation session.

    Signals:
        session_configured(config): Emitted when wizard completes with session config dict.
    """

    session_configured = Signal(dict)

    def __init__(
        self,
        config: TaxonomyConfig,
        sport_meta: dict[str, str],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the session wizard.

        Args:
            config: Full taxonomy configuration.
            sport_meta: Dict with sport metadata (id, name, short).
            parent: Optional parent widget.
        """
        super().__init__(parent)
        aparecer(self)
        self._config = config
        self._colors = config.colors
        self._sport_meta = sport_meta
        self._session_data: dict = {}
        self._i18n = I18n()

        self.setWindowTitle(self._i18n.t("wizard.title"))
        self.setModal(True)
        self.setMinimumSize(800, 600)
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the wizard UI."""
        c = self._colors
        self.setStyleSheet(f"background:{c.background};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Stacked widget for steps
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{c.background};")

        # Import step widgets
        from karlos_core.views.wizard_steps.video_step import VideoStep
        from karlos_core.views.wizard_steps.bout_info_step import BoutInfoStep
        from karlos_core.views.wizard_steps.fight_segment_step import FightSegmentStep
        from karlos_core.views.wizard_steps.ready_step import ReadyStep

        self._video_step = VideoStep(self._colors, self)
        self._bout_step = BoutInfoStep(self._colors, self._sport_meta, self._config, self)
        self._fight_step = FightSegmentStep(self._colors, self)
        self._ready_step = ReadyStep(self._colors, self)

        self._stack.addWidget(self._video_step)
        self._stack.addWidget(self._bout_step)
        self._stack.addWidget(self._fight_step)
        self._stack.addWidget(self._ready_step)

        layout.addWidget(self._stack, 1)

        # Footer with navigation
        footer = self._create_footer()
        layout.addWidget(footer)

        # Wire step signals
        self._video_step.next_requested.connect(self._on_video_next)
        self._bout_step.next_requested.connect(self._on_bout_next)
        self._bout_step.skip_requested.connect(self._on_bout_skip)
        self._fight_step.next_requested.connect(self._on_fight_next)
        self._fight_step.skip_requested.connect(self._on_fight_skip)
        self._ready_step.start_requested.connect(self._on_start)

    def _create_header(self) -> QWidget:
        """Create the wizard header with step indicator.

        Returns:
            QWidget containing the header.
        """
        c = self._colors
        i18n = self._i18n
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet(
            f"background:{c.panel};"
            f"border-bottom:1px solid {c.border};"
        )

        layout = QHBoxLayout(header)
        layout.setContentsMargins(32, 0, 32, 0)

        # Back button
        self._back_btn = QPushButton(i18n.t("wizard.back"))
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setStyleSheet(
            f"QPushButton{{"
            f"background:transparent;"
            f"color:{c.text};"
            f"border:none;"
            f"padding:8px 16px;"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:13px;font-weight:400;"
            f"}}"
            f"QPushButton:hover{{"
            f"color:{c.accent};"
            f"}}"
        )
        self._back_btn.clicked.connect(self._go_back)
        layout.addWidget(self._back_btn)

        layout.addStretch()

        # Step indicator
        self._step_label = QLabel(i18n.t("wizard.step", current="1", total="4"))
        self._step_label.setStyleSheet(
            f"color:{c.muted};"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:11px;font-weight:600;letter-spacing:0.8px;"
            "background:transparent;border:none;"
        )
        layout.addWidget(self._step_label)

        return header

    def _create_footer(self) -> QWidget:
        """Create the wizard footer with navigation buttons.

        Returns:
            QWidget containing the footer.
        """
        c = self._colors
        footer = QWidget()
        footer.setFixedHeight(80)
        footer.setStyleSheet(
            f"background:{c.panel};"
            f"border-top:1px solid {c.border};"
        )

        layout = QHBoxLayout(footer)
        layout.setContentsMargins(32, 0, 32, 0)

        # Cancel button
        cancel_btn = QPushButton(self._i18n.t("wizard.cancel"))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"QPushButton{{"
            f"background:transparent;"
            f"color:{c.muted};"
            f"border:none;"
            f"padding:8px 16px;"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:13px;font-weight:400;"
            f"}}"
            f"QPushButton:hover{{"
            f"color:{c.text};"
            f"}}"
        )
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

        layout.addStretch()

        # Skip button (hidden by default)
        self._skip_btn = QPushButton(self._i18n.t("wizard.skip"))
        self._skip_btn.setCursor(Qt.PointingHandCursor)
        self._skip_btn.setStyleSheet(
            f"QPushButton{{"
            f"background:transparent;"
            f"color:{c.muted};"
            f"border:none;"
            f"padding:8px 16px;"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:13px;font-weight:400;"
            f"}}"
            f"QPushButton:hover{{"
            f"color:{c.text};"
            f"}}"
        )
        self._skip_btn.setVisible(False)
        layout.addWidget(self._skip_btn)

        # Next button
        self._next_btn = QPushButton(self._i18n.t("wizard.next"))
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setStyleSheet(
            f"QPushButton{{"
            f"background:{c.accent};"
            f"color:p.misc_grey_card;"
            f"border:none;"
            f"border-radius:6px;"
            f"padding:10px 24px;"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:13px;font-weight:600;"
            f"}}"
            f"QPushButton:hover{{"
            f"background:p.warning_amber;"
            f"}}"
            f"QPushButton:disabled{{"
            f"background:{c.border};"
            f"color:{c.muted};"
            f"}}"
        )
        layout.addWidget(self._next_btn)

        return footer

    def _go_back(self) -> None:
        """Navigate to previous step."""
        current = self._stack.currentIndex()
        if current > 0:
            self._stack.setCurrentIndex(current - 1)
            self._update_navigation()

    def _update_navigation(self) -> None:
        """Update navigation buttons and step indicator based on current step."""
        current = self._stack.currentIndex()
        total = self._stack.count()

        # Update step label
        self._step_label.setText(
            self._i18n.t("wizard.step", current=str(current + 1), total=str(total))
        )

        # Update back button visibility
        self._back_btn.setVisible(current > 0)

        # Update skip button visibility (only for steps 2 and 3)
        self._skip_btn.setVisible(current in [1, 2])

        # Update next button text
        if current == total - 1:
            self._next_btn.setText(self._i18n.t("wizard.start"))
        else:
            self._next_btn.setText(self._i18n.t("wizard.next"))

    def _on_video_next(self, video_data: dict) -> None:
        """Handle video step completion.

        Args:
            video_data: Dict with 'path', 'duration', 'fps', 'resolution', etc.
        """
        self._session_data["video"] = video_data
        self._stack.setCurrentIndex(1)
        self._update_navigation()

    def _on_bout_next(self, bout_data: dict) -> None:
        """Handle bout info step completion.

        Args:
            bout_data: Dict with bout metadata.
        """
        self._session_data["bout_info"] = bout_data
        self._fight_step.set_video_path(self._session_data["video"]["path"])
        self._stack.setCurrentIndex(2)
        self._update_navigation()

    def _on_bout_skip(self) -> None:
        """Handle bout info step skip."""
        self._session_data["bout_info"] = {}
        self._fight_step.set_video_path(self._session_data["video"]["path"])
        self._stack.setCurrentIndex(2)
        self._update_navigation()

    def _on_fight_next(self, fight_data: dict) -> None:
        """Handle fight segment step completion.

        Args:
            fight_data: Dict with 'start_frame', 'end_frame', 'duration'.
        """
        self._session_data["fight_segment"] = fight_data
        self._ready_step.set_session_data(self._session_data, self._sport_meta)
        self._stack.setCurrentIndex(3)
        self._update_navigation()

    def _on_fight_skip(self) -> None:
        """Handle fight segment step skip."""
        self._session_data["fight_segment"] = {}
        self._ready_step.set_session_data(self._session_data, self._sport_meta)
        self._stack.setCurrentIndex(3)
        self._update_navigation()

    def _on_start(self) -> None:
        """Handle final start button click."""
        self.session_configured.emit(self._session_data)
        self.accept()
