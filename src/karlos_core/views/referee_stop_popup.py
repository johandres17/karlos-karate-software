"""Referee Stop type selection popup for KARLOS ANNOTATOR.

Displays a modal dialog when the user clicks "Referee Stop",
offering three options: Referee, VR, or Injury.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from karlos_core import catalogo
from karlos_core.models.technique import AppColors, RefereeStopType
from karlos_core.views.animaciones import aparecer


class RefereeStopPopup(QDialog):
    """Modal dialog for selecting the type of referee stop.

    Attributes:
        selected: The chosen RefereeStopType name ("Referee", "VR", "Injury"),
            or None if the user cancelled.
    """

    def __init__(
        self,
        athlete: str,
        colors: AppColors,
        stop_types: list[RefereeStopType],
        parent: Optional[QDialog] = None,
    ) -> None:
        """Initialize the referee stop popup.

        Args:
            athlete: Current athlete ("AKA" or "AO").
            colors: Application color palette.
            stop_types: List of referee stop type definitions.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        aparecer(self)
        from karlos_core.utils.i18n import I18n
        self._i18n = I18n()
        self.setWindowTitle(self._i18n.t("refstop.title"))
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.selected: Optional[str] = None
        self._build(athlete, colors, stop_types)

    def _build(
        self,
        athlete: str,
        colors: AppColors,
        stop_types: list[RefereeStopType],
    ) -> None:
        """Construct the dialog UI.

        Args:
            athlete: Athlete identifier for color coding.
            colors: Application color palette.
            stop_types: Referee stop type definitions.
        """
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        color = colors.aka if athlete == "AKA" else colors.ao
        athlete_label = catalogo.etiqueta(athlete)
        hdr = QLabel(f"{athlete_label} — Referee Stop")
        hdr.setStyleSheet(
            f"color:{color};font-size:15px;font-weight:600;"
            "background:transparent;border:none;"
        )
        root.addWidget(hdr)

        root.addWidget(QLabel(self._i18n.t("refstop.select_reason")))

        for stop_type in stop_types:
            btn = QPushButton(
                f"[{stop_type.abbr}] {stop_type.name}     [{stop_type.shortcut}]"
            )
            btn.setMinimumHeight(44)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton{{background:{stop_type.color}22;"
                f"color:{colors.text};"
                f"border:1px solid {stop_type.color}66;"
                "border-radius:8px;padding:8px 14px;"
                "font-size:13px;font-weight:600;text-align:left;}"
                f"QPushButton:hover{{background:{stop_type.color}55;"
                f"border:1px solid {stop_type.color};}}"
            )
            btn.clicked.connect(
                lambda _, n=stop_type.name, checked=True: self._select(n)
            )
            root.addWidget(btn)

            QShortcut(QKeySequence(stop_type.shortcut), self).activated.connect(
                lambda _, n=stop_type.name: self._select(n)
            )

        cancel_btn = QPushButton(self._i18n.t("refstop.cancel"))
        cancel_btn.setStyleSheet(
            f"QPushButton{{background:{colors.panel};color:{colors.muted};"
            f"border:1px solid rgba(255,255,255,0.08);"
            "border-radius:8px;padding:8px 16px;font-size:13px;font-weight:500;}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.06);"
            f"color:{colors.text};}}"
        )
        cancel_btn.clicked.connect(self.reject)
        root.addWidget(cancel_btn)

    def _select(self, name: str) -> None:
        """Record the selected stop type and accept the dialog.

        Args:
            name: The chosen RefereeStopType name.
        """
        self.selected = name
        self.accept()