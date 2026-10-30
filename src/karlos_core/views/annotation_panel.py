"""Annotation panel view for KARLOS ANNOTATOR.

Provides the athlete selector (AKA/AO), technique category buttons loaded
from taxonomy configuration, and an optional notes text area.
Emits signals for technique clicks and athlete switches.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from karlos_core.models.technique import (
    AppColors,
    TaxonomyConfig,
    Technique,
)
from karlos_core.views.theme import Palette, Spacing, Typography


class AnnotationPanelView(QWidget):
    """Side panel for technique selection and athlete switching.

    Signals:
        technique_clicked(technique): Emitted when a technique button is pressed.
        athlete_changed(athlete): Emitted when AKA/AO is toggled ("AKA" or "AO").
        foul_requested(infraction_type): Emitted when a WKF 2026 foul
            button is pressed — one of "Contact", "Target",
            "Illegal Tech", or "Procedure". Only emitted for Karate.
    """

    technique_clicked = Signal(Technique)
    athlete_changed = Signal(str)
    foul_requested = Signal(str)

    def __init__(
        self,
        config: TaxonomyConfig,
        sport_id: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the annotation panel view.

        Args:
            config: Full taxonomy configuration.
            sport_id: Sport identifier (e.g., "karate") for feature gating.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._config = config
        self._colors = config.colors
        self._sport_id = sport_id
        self._p = Palette.from_config(config.colors)
        self._athlete: str = "AKA"
        self._athlete_a_label = config.athlete_a_label
        self._athlete_b_label = config.athlete_b_label
        # ── Dynamic corner colors (updated by controller) ─────
        self._color_a: str = config.colors.aka
        self._color_b: str = config.colors.ao
        self._build()

    @property
    def athlete(self) -> str:
        """Current active athlete ("AKA" or "AO")."""
        return self._athlete

    def get_notes(self) -> str:
        """Get the current text from the notes field.

        Returns:
            Trimmed notes text.
        """
        return self.notes.toPlainText().strip()

    def clear_notes(self) -> None:
        """Clear the notes text field."""
        self.notes.clear()

    def set_notes(self, texto: str) -> None:
        """Escribir en el campo de notas desde el programa.

        Lo usa el motivo escrito de una accion no identificable: lo que
        el evaluador teclea tiene que acabar en la misma columna que
        cualquier otra nota suya, no en un sitio aparte.
        """
        self.notes.setPlainText(texto or "")

    def set_athlete(self, athlete: str) -> None:
        """Programmatically set the active athlete.

        Args:
            athlete: "AKA" or "AO".
        """
        self._set_athlete(athlete)

    def solo_atletas(self, activo: bool) -> None:
        """Solo el conmutador de atleta: en la pasada de fases del
        tiempo-movimiento no hay técnicas que elegir, pero sí de quién son
        las fases."""
        self._scroll_tecnicas.setVisible(not activo)
        self.notes.setVisible(not activo)

    def lock_athlete(self, locked: bool) -> None:
        """Enable or disable the athlete switcher buttons.

        During an active fight pass, the athlete is locked to prevent
        accidental switching.

        Args:
            locked: True to disable athlete buttons, False to enable.
        """
        self.btn_aka.setEnabled(not locked)
        self.btn_ao.setEnabled(not locked)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Construct the complete annotation panel UI."""
        c = self._colors
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(3)

        # Athlete switcher
        self._build_athlete_switcher(root)

        # Scrollable technique buttons
        self._build_technique_buttons(root)

        # Notes field
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Notes...")
        self.notes.setMaximumHeight(28)
        self.notes.setStyleSheet(
            f"background:{c.panel};color:{c.text};"
            f"border:1px solid rgba(255,255,255,0.08);"
            f"border-radius:6px;font-size:11px;padding:2px 4px;"
        )
        root.addWidget(self.notes)

    def _build_athlete_switcher(self, root: QVBoxLayout) -> None:
        """Build the AKA/AO athlete toggle section.

        Args:
            root: Parent layout to add widgets to.
        """
        c = self._colors
        row = QHBoxLayout()
        row.setSpacing(4)

        # ── Athlete labels: corner names for Kickboxing ──
        self._label_a = self._athlete_a_label
        self._label_b = self._athlete_b_label
        self._corner_a = self._athlete_a_label
        self._corner_b = self._athlete_b_label

        self.btn_aka = QPushButton(self._label_a)
        self.btn_ao = QPushButton(self._label_b)
        for btn in [self.btn_aka, self.btn_ao]:
            btn.setCheckable(True)
            btn.setMinimumHeight(28)
            btn.setMaximumHeight(28)

        self.btn_aka.clicked.connect(lambda: self._set_athlete("AKA"))
        self.btn_ao.clicked.connect(lambda: self._set_athlete("AO"))
        row.addWidget(self.btn_aka)
        row.addWidget(self.btn_ao)
        root.addLayout(row)
        self._set_athlete("AKA")

    def _build_technique_buttons(self, root: QVBoxLayout, indice: Optional[int] = None) -> None:
        """Build the scrollable technique category buttons.

        Args:
            root: Parent layout to add widgets to.
            indice: Where to insert them (None: at the end).
        """
        c = self._colors
        p = self._p
        self._grupos_tecnica: list = []
        self._grp_faltas = None
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
        )

        inner = QWidget()
        inner.setStyleSheet(f"background:{c.background};")
        gl = QVBoxLayout(inner)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(2)

        # Group techniques by category for organized layout
        categories: dict[str, list[Technique]] = {}
        for tech in self._config.techniques:
            categories.setdefault(tech.category, []).append(tech)

        for cat_name, techs in categories.items():
            # Dark Pro minimal: clean uppercase text labels, no color blocks
            # «&» es la marca de atajo de Qt: sin doblarlo, «SWEEPS &
            # TAKEDOWNS» salia como «SWEEPS  TAKEDOWNS».
            grp = QGroupBox(cat_name.upper().replace("&", "&&"))
            grp.setStyleSheet(
                f"QGroupBox{{color:{p.text_disabled};font-weight:bold;"
                "font-size:10px;letter-spacing:0.8px;border:none;"
                "text-transform:uppercase;"
                "margin-top:4px;padding-top:4px;background:transparent;}"
                "QGroupBox::title{subcontrol-origin:margin;"
                "left:2px;padding:0 2px;background:transparent;}"
            )
            g = QVBoxLayout(grp)
            g.setSpacing(1)
            g.setContentsMargins(2, 2, 2, 2)

            row_w: Optional[QHBoxLayout] = None
            for i, tech in enumerate(techs):
                if i % 2 == 0:
                    row_w = QHBoxLayout()
                    row_w.setSpacing(1)
                    g.addLayout(row_w)
                row_w.addWidget(self._tech_btn(tech))

            gl.addWidget(grp)
            self._grupos_tecnica.append(grp)

        # ── WKF 2026 Foul buttons (Karate only) ───────────────────
        # WKF unified Category 1/2 penalties into a single CHUI ladder,
        # effective 1.1.2026 (Rules Version 2026.01, §10.2-10.3).
        # Four buttons by infraction type, sharing ONE counter per athlete.
        if self._sport_id == "karate":
            foul_grp = QGroupBox("FOULS (WKF 2026)")
            foul_grp.setStyleSheet(
                f"QGroupBox{{color:{p.warning};font-weight:bold;"
                "font-size:10px;letter-spacing:0.8px;border:none;"
                "text-transform:uppercase;"
                "margin-top:4px;padding-top:4px;background:transparent;}"
                "QGroupBox::title{subcontrol-origin:margin;"
                "left:2px;padding:0 2px;background:transparent;}"
            )
            foul_layout = QHBoxLayout(foul_grp)
            foul_layout.setSpacing(1)
            foul_layout.setContentsMargins(2, 2, 2, 2)

            # Helper to create a foul button — same style as technique buttons
            def _foul_btn(label, shortcut, emit_val):
                btn = QPushButton(f"{label} [{shortcut}]")
                btn.setMinimumHeight(24)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(
                    f"QPushButton{{background-color:{p.surface_2};"
                    f"color:{p.text_bright};"
                    f"border:1px solid {p.border_default};border-radius:4px;"
                    f"padding:2px 4px;font-size:10px;text-align:left;"
                    f"font-weight:500;}}"
                    f"QPushButton:hover{{background-color:{p.surface_3};"
                    f"border:1px solid {p.border_hover};}}"
                    f"QPushButton:pressed{{background-color:rgba(255, 107, 53, 0.15);"
                    f"border:1px solid {p.accent_blue};color:{p.text_inverse};}}"
                )
                btn.clicked.connect(lambda: self.foul_requested.emit(emit_val))
                return btn

            foul_layout.addWidget(_foul_btn("Contact", "C", "Contact"))
            foul_layout.addWidget(_foul_btn("Target", "V", "Target"))
            foul_layout.addWidget(_foul_btn("Illegal", "⇧D", "Illegal Tech"))
            foul_layout.addWidget(_foul_btn("Procedure", "H", "Procedure"))

            gl.addWidget(foul_grp)
            self._grp_faltas = foul_grp
        gl.addStretch()
        scroll.setWidget(inner)
        if indice is None:
            root.addWidget(scroll, stretch=1)
        else:
            root.insertWidget(indice, scroll, 1)
        self._scroll_tecnicas = scroll

    ALTO_NOTAS_PRO = 54

    def alto_minimo_pro(self) -> int:
        """Lo que ocupa el panel en PRO: los dos atletas y las notas.

        Se mide en vez de fijarse a ojo, para que siga cuadrando si
        cambia el tamaño de letra o el alto de los botones. Las notas
        llevan su propio alto porque un campo de texto de dieciseis
        pixeles no se puede usar: cabe una linea a medias.
        """
        alto = max(self.btn_aka.sizeHint().height(), self.btn_aka.height())
        notas = getattr(self, "notes", None)
        if notas is not None and notas.isVisible():
            notas.setFixedHeight(self.ALTO_NOTAS_PRO)
            alto += self.ALTO_NOTAS_PRO
        return alto + 30          # margenes del contenedor y del scroll

    def mostrar_tecnicas(self, visible: bool) -> None:
        """Ensenar u ocultar los botones de tecnica y de falta.

        En la anotacion guiada sobran los dos: la tecnica se elige contestando
        preguntas, y pulsar un boton creaba la anotacion saltandose el
        arbol — sin guardia, sin nivel y sin contexto tactico, y sin
        avisar.

        Las faltas se ocultan por el mismo motivo, y por uno peor. El
        arbol SI las cubre: las que no son un ataque van por la rama
        «falta», y el contacto excesivo y la zona prohibida son el
        resultado del ataque que las provoca, con su tecnica y su nivel.
        Dejar ademas estos cuatro botones daba dos caminos para anotar lo
        mismo, y los datos salian distintos segun cual se tomara — que es
        justo lo que el arbol se escribio para evitar.

        El selector de atleta se queda: eso no lo pregunta nadie.
        """
        self._tecnicas_visibles = visible
        for grp in getattr(self, "_grupos_tecnica", []):
            grp.setVisible(visible)
        if getattr(self, "_grp_faltas", None) is not None:
            self._grp_faltas.setVisible(visible)

    def _tech_btn(self, tech: Technique) -> QPushButton:
        """Create a single technique button.

        Args:
            tech: Technique definition.

        Returns:
            Configured QPushButton.
        """
        label = (
            f"[{tech.abbr}] {tech.name}"
            if not tech.shortcut
            else f"[{tech.abbr}] {tech.name} [{tech.shortcut}]"
        )
        btn = QPushButton(label)
        btn.setMinimumHeight(24)
        btn.setCursor(Qt.PointingHandCursor)
        # Dark Pro minimal: uniform dark buttons, subtle hover glow
        p = self._p
        btn.setStyleSheet(
            f"QPushButton{{background-color:{p.surface_2};"
            f"color:{p.text_bright};"
            f"border:1px solid {p.border_default};border-radius:4px;"
            f"padding:2px 4px;font-size:10px;text-align:left;"
            f"font-weight:500;}}"
            f"QPushButton:hover{{background-color:{p.surface_3};"
            f"border:1px solid {p.border_hover};}}"
            f"QPushButton:pressed{{background-color:rgba(255, 107, 53, 0.15);"
            f"border:1px solid {p.accent_blue};color:{p.text_inverse};}}"
        )
        btn.clicked.connect(
            lambda checked=False, t=tech: self.technique_clicked.emit(t)
        )
        return btn

    def set_corner_colors(self, color_a: str, color_b: str, name_a: str = "", name_b: str = "") -> None:
        """Update athlete button colors and labels from bout_info corner selection."""
        self._color_a = color_a
        self._color_b = color_b
        if name_a:
            self._corner_a = name_a
        if name_b:
            self._corner_b = name_b
        self._label_a = f"{self._corner_a}" if self._corner_a else self._athlete_a_label
        self._label_b = f"{self._corner_b}" if self._corner_b else self._athlete_b_label
        self.btn_aka.setText(self._label_a)
        self.btn_ao.setText(self._label_b)
        self._refresh_athlete_buttons()

    def _set_athlete(self, athlete: str) -> None:
        """Update the active athlete and refresh UI.

        Args:
            athlete: "AKA" or "AO".
        """
        self._athlete = athlete
        self._refresh_athlete_buttons()
        self.athlete_changed.emit(athlete)

    def _refresh_athlete_buttons(self) -> None:
        """Refresh athlete button styles with current corner colors."""
        athlete = self._athlete
        self.btn_aka.setChecked(athlete == "AKA")
        self.btn_ao.setChecked(athlete == "AO")
        self.btn_aka.setStyleSheet(
            self._sw_style(self._color_a, athlete == "AKA")
        )
        self.btn_ao.setStyleSheet(
            self._sw_style(self._color_b, athlete == "AO")
        )

    def _sw_style(self, color: str, active: bool) -> str:
        """Generate stylesheet for athlete toggle buttons.

        Args:
            color: Athlete color.
            active: Whether this athlete is selected.

        Returns:
            Qt stylesheet string.
        """
        p = self._p
        if active:
            return (
                f"QPushButton{{background:{color}26;color:{color};"
                f"border-radius:6px;font-size:12px;font-weight:700;"
                f"border:1px solid {color};padding:2px 0px;}}"
                f"QPushButton:hover{{background:{color}40;}}"
            )
        return (
            f"QPushButton{{background:{p.surface_2};color:{p.text_disabled};"
            f"border-radius:6px;font-size:12px;font-weight:600;"
            f"border:1px solid {p.border_default};padding:2px 0px;}}"
            f"QPushButton:hover{{background:{p.surface_3};color:{p.text_primary};"
            f"border-color:{p.border_hover};}}"
        )
