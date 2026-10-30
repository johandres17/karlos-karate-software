"""Welcome screen for KARLOS ANNOTATOR.

Displays a premium, minimalist landing page with options to start a new
session, load a previous session, or access recent sessions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karlos_core.models.technique import AppColors
from karlos_core.utils.i18n import I18n


class WelcomeScreen(QWidget):
    """Welcome screen with session management options.

    Signals:
        new_session_requested: Emitted when user clicks "New Session".
        load_session_requested: Emitted when user clicks "Load Session".
        recent_session_selected(path): Emitted when user clicks a recent session.
    """

    new_session_requested = Signal()
    load_session_requested = Signal()
    recent_session_selected = Signal(str)

    def __init__(
        self,
        colors: AppColors,
        recent_sessions: Optional[list[dict]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the welcome screen.

        Args:
            colors: Application color palette.
            recent_sessions: List of dicts with 'path', 'name', 'time_ago'.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._colors = colors
        self._recent_sessions = recent_sessions or []
        self._i18n = I18n()
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the welcome screen UI."""
        c = self._colors
        i18n = self._i18n
        self.setStyleSheet(f"background:{c.background};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(80, 60, 80, 60)
        layout.setSpacing(40)

        # Title section
        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)

        from karlos_core import identidad
        title = QLabel(identidad.en_marcha().nombre.upper())
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color:{c.text};"
            "font-family:'SF Pro Display',-apple-system,'Inter',sans-serif;"
            "font-size:28px;font-weight:600;letter-spacing:1px;"
            "background:transparent;border:none;"
        )
        title_layout.addWidget(title)

        subtitle = QLabel(i18n.t("welcome.subtitle"))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            f"color:{c.muted};"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:14px;font-weight:400;letter-spacing:0.3px;"
            "background:transparent;border:none;"
        )
        title_layout.addWidget(subtitle)

        version = QLabel(i18n.t("welcome.version"))
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet(
            f"color:{c.muted};"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:12px;font-weight:400;"
            "background:transparent;border:none;"
        )
        title_layout.addWidget(version)

        layout.addLayout(title_layout)
        layout.addSpacing(20)

        # Action cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(24)

        # New Session card
        new_card = self._create_action_card(
            i18n.t("welcome.new_session"),
            i18n.t("welcome.new_session_desc"),
            self.new_session_requested.emit,
        )
        cards_layout.addWidget(new_card)

        # Load Session card
        load_card = self._create_action_card(
            i18n.t("welcome.load_session"),
            i18n.t("welcome.load_session_desc"),
            self.load_session_requested.emit,
        )
        cards_layout.addWidget(load_card)

        layout.addLayout(cards_layout)
        layout.addSpacing(20)

        # Separator
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{c.border};")
        layout.addWidget(sep)

        # Recent sessions
        if self._recent_sessions:
            recent_label = QLabel(i18n.t("welcome.recent_sessions"))
            recent_label.setStyleSheet(
                f"color:{c.muted};"
                "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
                "font-size:11px;font-weight:600;letter-spacing:0.8px;"
                "background:transparent;border:none;"
            )
            layout.addWidget(recent_label)

            for session in self._recent_sessions[:5]:  # Max 5 recent
                session_btn = self._create_recent_session_row(
                    session["name"], session["time_ago"], session["path"]
                )
                layout.addWidget(session_btn)

        layout.addStretch()

        # Footer buttons
        footer = QHBoxLayout()
        footer.addStretch()

        settings_btn = QPushButton(i18n.t("welcome.settings"))
        settings_btn.setStyleSheet(self._get_footer_button_style())
        footer.addWidget(settings_btn)

        help_btn = QPushButton(i18n.t("welcome.help"))
        help_btn.setStyleSheet(self._get_footer_button_style())
        footer.addWidget(help_btn)

        layout.addLayout(footer)

    def _create_action_card(
        self, title: str, description: str, callback
    ) -> QWidget:
        """Create a large action card button.

        Args:
            title: Card title text.
            description: Card description text.
            callback: Function to call on click.

        Returns:
            QWidget containing the card.
        """
        c = self._colors
        card = QWidget()
        card.setFixedSize(280, 180)
        card.setCursor(Qt.PointingHandCursor)

        # Styling
        card.setStyleSheet(
            f"QWidget{{"
            f"background:{c.panel};"
            f"border:1px solid {c.border};"
            f"border-radius:12px;"
            f"}}"
            f"QWidget:hover{{"
            f"border:1px solid {c.border_hover};"
            f"background:rgba(255,255,255,0.03);"
            f"}}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(12)

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"color:{c.text};"
            "font-family:'SF Pro Display',-apple-system,'Inter',sans-serif;"
            "font-size:16px;font-weight:600;letter-spacing:0.5px;"
            "background:transparent;border:none;"
        )
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            f"color:{c.muted};"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:13px;font-weight:400;line-height:1.4;"
            "background:transparent;border:none;"
        )
        layout.addWidget(desc_lbl)

        layout.addStretch()

        # Make card clickable
        card.mousePressEvent = lambda e: callback()

        return card

    def _create_recent_session_row(
        self, name: str, time_ago: str, path: str
    ) -> QPushButton:
        """Create a recent session row button.

        Args:
            name: Session name.
            time_ago: Time since last modified (e.g., "2 hours ago").
            path: Full path to session file.

        Returns:
            QPushButton for the session row.
        """
        c = self._colors
        btn = QPushButton(f"{name}    {time_ago}    →")
        btn.setFixedHeight(36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton{{"
            f"background:transparent;"
            f"color:{c.text};"
            f"border:none;"
            f"text-align:left;"
            f"padding-left:12px;"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:13px;font-weight:400;"
            f"}}"
            f"QPushButton:hover{{"
            f"background:rgba(255,255,255,0.04);"
            f"color:{c.accent};"
            f"}}"
        )
        btn.clicked.connect(lambda: self.recent_session_selected.emit(path))
        return btn

    def _get_footer_button_style(self) -> str:
        """Get stylesheet for footer buttons.

        Returns:
            CSS stylesheet string.
        """
        c = self._colors
        return (
            f"QPushButton{{"
            f"background:transparent;"
            f"color:{c.muted};"
            f"border:none;"
            f"padding:6px 12px;"
            "font-family:'SF Pro Text',-apple-system,'Inter',sans-serif;"
            "font-size:12px;font-weight:400;"
            f"}}"
            f"QPushButton:hover{{"
            f"color:{c.text};"
            f"}}"
        )
