"""El tema de KARLOS ANNOTATOR: grafito, plata y oro.

Fase 1 (julio 2026) consolido los 73 hexadecimales sueltos en tokens.
Esta es la Fase 2 que quedo pendiente: los valores. La familia sale de
la iconografia — el grafito azulado de las placas, la plata de la
linea, el ORO del nodo de la K como unico acento de accion, y el azul
de la K como secundario. Una regla: el oro es para lo que hay que
mirar o pulsar; todo lo demas calla.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import ClassVar

from karlos_core.models.technique import AppColors


# ══════════════════════════════════════════════════════════════════
# Palette — complete token set (73 tokens = 1:1 original hex codes)
# ══════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Palette:
    """All color tokens used across the 14 views files.

    Phase 1: every token is the EXACT original hex code from the
    scattered QSS. No unification, no "close enough" merges.
    """

    # ── Greyscale (Phase 0 tokens) ─────────────────────────────
    bg_root: str = "#0F1114"
    surface_1: str = "#15181D"
    surface_2: str = "#1B2028"
    surface_3: str = "#262D37"
    border_subtle: str = "#232831"
    border_default: str = "#333B46"
    border_hover: str = "#4A5563"
    text_primary: str = "#F4F7FB"
    text_secondary: str = "#96A1AF"
    text_disabled: str = "#5F6875"

    # ── Extended greyscale variants (preserve exact hex) ───────
    bg_alt: str = "#12151A"        # dialog/popup backgrounds
    bg_deeper: str = "#0B0D10"     # darkest (buttons, cards)
    panel_dark: str = "#171B21"     # dark panel (bout_info_popup)
    bg_card: str = "#1A1F26"       # card surfaces
    bg_table_alt: str = "#13171C"  # table alternate row
    surface_popup: str = "#12151A"  # popup active bg (match_report)
    border_dashed: str = "#333B46" # dashed borders
    border_strong: str = "#38404C" # stronger borders
    text_bright: str = "#F4F7FB"   # slightly brighter text
    text_header: str = "#96A1AF"   # header text
    border_checked_glow: str = "#C6D0DC"  # checked/hover border glow (YUKO, generic)
    text_inverse: str = "#FFFFFF"  # white text
    bg_selection: str = "#1E3A5C"  # selection highlight blue
    bg_header: str = "#171B21"     # table header bg
    bg_dialog: str = "#12151A"     # dialog background
    bg_inactive: str = "#13171C"   # inactive/disabled bg
    white: str = "#FFFFFF"
    black: str = "#000000"
    grey_light: str = "#C6D0DC"
    grey_mid: str = "#96A1AF"
    grey_medium: str = "#8A94A2"
    grey_888: str = "#848E9C"       # exact match for bout_info_popup muted
    grey_dark: str = "#5F6875"
    grey_xdark: str = "#4A5563"

    # ── Accent (from config) ───────────────────────────────────
    accent: str = "#E8B33A"
    accent_blue: str = "#2E9BE8"   # secondary accent (state)
    accent_blue_light: str = "#56B1F0"  # lighter blue
    accent_blue_lighter: str = "#8FD0FF"  # lightest blue

    # ── Semantic — Athlete ─────────────────────────────────────
    aka: str = "#E5534B"
    aka_dark: str = "#C62828"
    aka_dim: str = "#3D1C1B"       # dim bg for AKA
    aka_light: str = "#F07C75"     # light variant

    ao: str = "#4384E6"
    ao_dark: str = "#1976D2"
    ao_dim: str = "#172D40"        # dim bg for AO
    ao_bright: str = "#0A84FF"

    # ── Semantic — Scores ──────────────────────────────────────
    ippon_fg: str = "#E8B33A"      # IPPON foreground
    ippon_bg: str = "#3C2E17"      # IPPON background
    ippon_glow: str = "#FFE08A"    # IPPON glow border

    waza_fg: str = "#56B1F0"       # WAZA foreground
    waza_bg: str = "#172D40"       # WAZA background
    waza_glow: str = "#8FD0FF"     # WAZA glow border

    yuko_fg: str = "#F4F7FB"       # YUKO foreground
    yuko_bg: str = "#232831"       # YUKO background

    none_fg: str = "#4A5563"       # NONE foreground
    none_bg: str = "#12151A"       # NONE background
    none_border: str = "#333B46"   # NONE dashed border

    foul_fg: str = "#E5534B"       # FOUL foreground
    foul_bg: str = "#3D1C1B"       # FOUL background

    score_generic_fg: str = "#F4F7FB"
    score_generic_bg: str = "#232831"

    # ── Semantic — Foul button colors (current 4-color scheme) ─
    foul_contact_bg: str = "#3D1A1A"
    foul_contact_fg: str = "#E5534B"
    foul_contact_border: str = "#5C2A2A"

    foul_target_bg: str = "#1A1A3D"
    foul_target_fg: str = "#4384E6"
    foul_target_border: str = "#2A2A5C"

    foul_illegal_bg: str = "#1A2E1A"
    foul_illegal_fg: str = "#4CAF50"
    foul_illegal_border: str = "#2A5C2A"

    foul_procedure_bg: str = "#3D2A1A"
    foul_procedure_fg: str = "#FF9800"
    foul_procedure_border: str = "#5C3A2A"

    # ── Semantic — Success / Warning / Danger ──────────────────
    success: str = "#238636"
    success_hover: str = "#2EA043"
    success_glow: str = "#3FB950"
    success_bright: str = "#30D158"
    success_alt: str = "#2E7D32"

    warning: str = "#D5A021"
    warning_light: str = "#FFE08A"
    warning_amber: str = "#E8B33A"
    warning_orange: str = "#FF9F0A"
    warning_bright: str = "#FFD60A"
    warning_dark: str = "#B8953E"

    danger: str = "#E5534B"
    danger_light: str = "#FF453A"

    # ── Semantic — Timeline / Chart ────────────────────────────
    timeline_aka: str = "#D32F2F"
    timeline_ao: str = "#1976D2"
    chart_green: str = "#2B9E66"
    chart_orange: str = "#F58732"
    timeline_accent: str = "#E8B33A"

    # ── Misc specific hex codes from views ─────────────────────
    misc_gold: str = "#B58A2E"
    misc_gold_light: str = "#FFE08A"
    misc_green_bright: str = "#00c864"
    misc_orange: str = "#ffa500"
    misc_purple: str = "#8888cc"
    misc_grey_bg: str = "#0F1114"
    misc_grey_card: str = "#1A1F26"
    misc_grey_border: str = "#2A313C"
    misc_grey_text: str = "#96A1AF"
    misc_offwhite: str = "#F4F7FB"
    misc_light_grey: str = "#DEE5EE"
    misc_white_dim: str = "#C6D0DC"

    @classmethod
    def from_config(cls, colors: AppColors) -> "Palette":
        """Crear la paleta con los colores propios del deporte.

        Del config solo vienen los semanticos (aka, ao, state): el
        resto hereda la familia grafito-plata-oro de esta clase.
        """
        return cls(
            accent_blue=colors.state,
            aka=colors.aka,
            ao=colors.ao,
            danger=colors.aka,
            danger_light=colors.aka,
        )


# ══════════════════════════════════════════════════════════════════
# Spacing — 4px grid
# ══════════════════════════════════════════════════════════════════


class Spacing:
    """4px-grid spacing scale for consistent margins/paddings."""

    XS: ClassVar[int] = 4
    SM: ClassVar[int] = 8
    MD: ClassVar[int] = 12
    LG: ClassVar[int] = 16
    XL: ClassVar[int] = 20
    XXL: ClassVar[int] = 24
    XXXL: ClassVar[int] = 32
    HUGE: ClassVar[int] = 48


# ══════════════════════════════════════════════════════════════════
# Typography
# ══════════════════════════════════════════════════════════════════


class Typography:
    """Typography system — Inter with tabular numbers."""

    FONT_STACK: ClassVar[str] = (
        "'Inter', 'SF Pro Display', 'SF Pro Text', "
        "-apple-system, 'Helvetica Neue', system-ui, sans-serif"
    )
    FONT_MONO: ClassVar[str] = (
        "'JetBrains Mono', 'SF Mono', 'Cascadia Code', "
        "'Fira Code', 'Menlo', monospace"
    )

    SIZE_H1: ClassVar[int] = 16
    SIZE_H2: ClassVar[int] = 14
    SIZE_H3: ClassVar[int] = 13
    SIZE_BODY: ClassVar[int] = 12
    SIZE_SMALL: ClassVar[int] = 11
    SIZE_XS: ClassVar[int] = 10

    WEIGHT_BOLD: ClassVar[int] = 700
    WEIGHT_SEMIBOLD: ClassVar[int] = 600
    WEIGHT_MEDIUM: ClassVar[int] = 500
    WEIGHT_REGULAR: ClassVar[int] = 400

    TNUM: ClassVar[str] = "'tnum' on, 'lnum' on"


# ══════════════════════════════════════════════════════════════════
# Global QSS Builder
# ══════════════════════════════════════════════════════════════════


def build_global_qss(p: Palette) -> str:
    """Build the global application stylesheet from palette tokens.

    Phase 1 — preserves exact original colors via Palette tokens.
    """
    return f"""
    /* ═════════════════════════════════════════════════════════════
       KARLOS ANNOTATOR — grafito, plata y oro (Fase 2)
       Generado por theme.py::build_global_qss()
       ═════════════════════════════════════════════════════════════ */

    QMainWindow {{
        background: {p.bg_root};
    }}
    QWidget {{
        background: {p.bg_root};
        color: {p.text_primary};
        font-family: {Typography.FONT_STACK};
        font-size: {Typography.SIZE_BODY}px;
    }}

    QMenuBar {{
        background: {p.surface_1};
        color: {p.text_secondary};
        border-bottom: 1px solid {p.border_subtle};
        padding: 2px {Spacing.SM}px;
        font-size: {Typography.SIZE_SMALL}px;
    }}
    QMenuBar::item:selected {{
        background: {p.surface_2};
        color: {p.text_primary};
        border-radius: 4px;
    }}
    QMenu {{
        background: {p.surface_2};
        color: {p.text_primary};
        border: 1px solid {p.border_default};
        border-radius: 10px;
        padding: {Spacing.XS}px;
    }}
    QMenu::item {{
        padding: 6px 24px 6px {Spacing.MD}px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background: {p.surface_2};
    }}
    QMenu::separator {{
        height: 1px;
        background: {p.border_subtle};
        margin: {Spacing.XS}px {Spacing.SM}px;
    }}

    QDockWidget {{
        color: {p.text_primary};
        titlebar-close-icon: url(none);
        titlebar-normal-icon: url(none);
    }}
    QDockWidget::title {{
        background: {p.surface_1};
        color: {p.text_secondary};
        padding: 6px {Spacing.MD}px;
        border-bottom: 1px solid {p.border_subtle};
        font-size: {Typography.SIZE_SMALL}px;
        font-weight: {Typography.WEIGHT_SEMIBOLD};
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border_default};
        border-radius: 3px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p.text_disabled};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {p.border_default};
        border-radius: 3px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {p.text_disabled};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    QToolTip {{
        background: {p.surface_3};
        color: {p.text_primary};
        border: 1px solid {p.border_hover};
        border-radius: 8px;
        padding: {Spacing.XS}px {Spacing.SM}px;
        font-size: {Typography.SIZE_XS}px;
    }}

    QMessageBox QLabel {{
        background: transparent;
    }}

    QStatusBar {{
        background: {p.surface_1};
        color: {p.text_secondary};
        border-top: 1px solid {p.border_subtle};
        font-size: {Typography.SIZE_SMALL}px;
        padding: 2px {Spacing.SM}px;
    }}

    QGroupBox {{
        color: {p.text_secondary};
        font-weight: {Typography.WEIGHT_BOLD};
        font-size: {Typography.SIZE_XS}px;
        letter-spacing: 0.8px;
        border: none;
        text-transform: uppercase;
        margin-top: {Spacing.SM}px;
        padding-top: {Spacing.XS}px;
        background: transparent;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 2px;
        padding: 0 2px;
        background: transparent;
    }}

    QPushButton {{
        background: {p.surface_1};
        color: {p.text_primary};
        border: 1px solid {p.border_default};
        border-radius: 8px;
        padding: 6px {Spacing.LG}px;
        font-size: {Typography.SIZE_BODY}px;
        font-weight: {Typography.WEIGHT_MEDIUM};
    }}
    QPushButton:hover {{
        background: {p.surface_2};
        border: 1px solid {p.border_hover};
    }}
    QPushButton:pressed {{
        background: {p.bg_deeper};
        border: 1px solid {p.border_default};
    }}
    QPushButton:focus {{
        border: 1px solid {p.accent};
        outline: none;
    }}
    QPushButton:disabled {{
        background: transparent;
        color: {p.text_disabled};
        border: 1px solid {p.border_subtle};
    }}
    /* Un boton con la propiedad clase="primario" es EL boton de la
       pantalla: oro, y solo puede haber uno a la vista. */
    QPushButton[clase="primario"] {{
        background: {p.accent};
        color: #1A1405;
        border: 1px solid {p.accent};
        font-weight: {Typography.WEIGHT_SEMIBOLD};
    }}
    QPushButton[clase="primario"]:hover {{
        background: {p.ippon_glow};
        border: 1px solid {p.ippon_glow};
    }}
    QPushButton[clase="primario"]:pressed {{
        background: {p.misc_gold};
        border: 1px solid {p.misc_gold};
    }}
    QPushButton[clase="primario"]:disabled {{
        background: {p.surface_2};
        color: {p.text_disabled};
        border: 1px solid {p.border_subtle};
    }}

    QLineEdit, QTextEdit, QPlainTextEdit {{
        background: {p.bg_deeper};
        color: {p.text_primary};
        border: 1px solid {p.border_default};
        border-radius: 8px;
        padding: 6px {Spacing.SM}px;
        font-size: {Typography.SIZE_SMALL}px;
        selection-background-color: {p.bg_selection};
        selection-color: {p.text_primary};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {p.accent};
        background: {p.surface_1};
    }}
    QLineEdit:hover, QTextEdit:hover {{
        border: 1px solid {p.border_hover};
    }}

    QComboBox {{
        background: {p.surface_1};
        color: {p.text_primary};
        border: 1px solid {p.border_default};
        border-radius: 8px;
        padding: 5px {Spacing.SM}px;
        font-size: {Typography.SIZE_SMALL}px;
    }}
    QComboBox:hover {{ border: 1px solid {p.border_hover}; }}
    QComboBox:focus {{ border: 1px solid {p.accent}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background: {p.surface_1};
        color: {p.text_primary};
        border: 1px solid {p.border_default};
        border-radius: 4px;
        selection-background-color: {p.surface_2};
    }}

    QSpinBox, QDoubleSpinBox {{
        background: {p.surface_1};
        color: {p.text_primary};
        border: 1px solid {p.border_default};
        border-radius: 8px;
        padding: 5px {Spacing.SM}px;
        font-size: {Typography.SIZE_SMALL}px;
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {p.accent}; }}

    QCheckBox, QRadioButton {{
        color: {p.text_primary};
        spacing: {Spacing.SM}px;
        font-size: {Typography.SIZE_SMALL}px;
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {p.border_default};
        border-radius: 4px;
        background: {p.surface_1};
    }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border: 1px solid {p.border_hover};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {p.accent};
        border: 1px solid {p.accent};
    }}
    QRadioButton::indicator {{ border-radius: 8px; }}

    QSlider::groove:horizontal {{
        background: {p.border_subtle};
        height: 4px; border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {p.text_primary};
        width: 14px; height: 14px;
        margin: -5px 0; border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{ background: {p.accent}; }}
    QSlider::sub-page:horizontal {{
        background: {p.accent};
        border-radius: 2px;
    }}

    QScrollArea {{ border: none; background: transparent; }}
    QSplitter::handle {{ background: {p.border_subtle}; }}
    QSplitter::handle:hover {{ background: {p.accent}; }}

    QTabWidget::pane {{
        border: 1px solid {p.border_subtle};
        border-radius: 6px;
        background: {p.surface_1};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {p.text_secondary};
        border: 1px solid transparent;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        padding: 6px {Spacing.LG}px;
        font-size: {Typography.SIZE_SMALL}px;
        font-weight: {Typography.WEIGHT_MEDIUM};
    }}
    QTabBar::tab:selected {{
        background: {p.surface_1};
        color: {p.text_primary};
        border-bottom: 2px solid {p.accent};
    }}
    QTabBar::tab:hover {{ color: {p.text_primary}; }}

    QProgressBar {{
        background: {p.border_subtle};
        border: none; border-radius: 4px; height: 6px;
        text-align: center;
        font-size: {Typography.SIZE_XS}px;
        color: {p.text_secondary};
    }}
    QProgressBar::chunk {{
        background: {p.accent};
        border-radius: 4px;
    }}

    QTableView, QTreeView, QListView {{
        background: {p.bg_root};
        color: {p.text_primary};
        border: 1px solid {p.border_subtle};
        border-radius: 6px;
        gridline-color: {p.border_subtle};
        selection-background-color: {p.surface_2};
        selection-color: {p.text_primary};
    }}
    QHeaderView::section {{
        background: {p.surface_1};
        color: {p.text_secondary};
        border: none;
        border-bottom: 1px solid {p.border_subtle};
        padding: 6px {Spacing.SM}px;
        font-size: {Typography.SIZE_SMALL}px;
        font-weight: {Typography.WEIGHT_SEMIBOLD};
    }}
    QHeaderView::section:hover {{ color: {p.text_primary}; }}

    [objectName="frameLabel"], [objectName="timerLabel"], QLabel[cssClass="tabular"] {{
        font-feature-settings: {Typography.TNUM};
        font-family: {Typography.FONT_MONO};
    }}

    QDialog {{
        background: {p.surface_1};
        border: 1px solid {p.border_default};
        border-radius: 12px;
    }}
    QMessageBox {{ background: {p.surface_1}; }}
    QMessageBox QPushButton {{ min-width: 84px; }}
    """


def marca(nombre: str, color: str, acento: str) -> str:
    """El nombre del programa como se rotula, en texto enriquecido.

    «KARLOS» en el color del texto y, en el del acento, lo que dice qué
    programa es: «KARATE» en Karlos Karate, «ANNOTATOR» en la edición de
    desarrollo. Lo usan la pantalla de inicio y la cabecera del anotador.
    """
    primero, _, resto = nombre.upper().partition(" ")
    texto = f"<span style='color:{color};'>{html.escape(primero)}</span>"
    if resto:
        texto += f" <span style='color:{acento};'>{html.escape(resto)}</span>"
    return texto
