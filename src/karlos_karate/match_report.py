"""Match Report view — Board Report Executive Dashboard.

Bloomberg Terminal layout: sidebar navigation (5 sections) + Round selector.
Works for Karate WKF and Kickboxing with sport-specific metrics.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Optional

import qtawesome as qta
from PySide6.QtCharts import (
    QBarCategoryAxis, QBarSeries, QBarSet,
    QCategoryAxis, QChart, QChartView,
    QLineSeries, QPieSeries, QValueAxis,
)
from PySide6.QtCore import QMargins, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from karlos_core import catalogo
from karlos_core.formato import COMPETIDORES
from karlos_core.models.technique import AppColors
from karlos_core.views.theme import Palette
from karlos_core.views.animaciones import aparecer
from karlos_core import catalogo
# ------------------------------------------------------------------
# Premium Design Tokens — Centralized color system
# ------------------------------------------------------------------
_p_default = Palette()  # module-level defaults for static QSS
_BG_PRIMARY = _p_default.black
_BG_SECONDARY = _p_default.bg_deeper
_BG_PANEL = _p_default.surface_1
_BG_CARD = _p_default.misc_grey_card
_BG_HOVER = _p_default.bg_card
_BORDER = "rgba(255,255,255,0.10)"
_BORDER_SUBTLE = "rgba(255,255,255,0.06)"
_TEXT_PRIMARY = _p_default.text_inverse
_TEXT_SECONDARY = _p_default.misc_light_grey
_TEXT_TERTIARY = "rgba(235,235,245,0.60)"
_TEXT_MUTED = "rgba(235,235,245,0.40)"
_ACCENT_GOLD = _p_default.warning_bright
_ACCENT_BLUE = _p_default.ao_bright
_ACCENT_RED = _p_default.danger_light
_ACCENT_GREEN = _p_default.success_bright
_ACCENT_ORANGE = _p_default.warning_orange
_AKA_COLOR = _ACCENT_RED
_AO_COLOR = _ACCENT_BLUE

# ------------------------------------------------------------------
# Scoring constants — Karate. Lo que vale cada código lo dice el deporte
# (catalogo.paquete(...).reglamento.puntos, decisión 0004); aquí solo
# cómo se pinta.
# ------------------------------------------------------------------
_SCORE_QUALITY_COLORS_KARATE: dict[str, QColor] = {
    "IPPON (3)":     QColor(_ACCENT_GOLD),
    "WAZA-ARI (2)":  QColor(_TEXT_TERTIARY),
    "YUKO (1)":      QColor(_ACCENT_ORANGE),
    "NO SCORE":      QColor(_BG_CARD),
}
_SCORE_QUALITY_ORDER_KARATE = ["IPPON (3)", "WAZA-ARI (2)", "YUKO (1)", "NO SCORE"]

# ------------------------------------------------------------------
# Scoring constants — Taekwondo WT
# ------------------------------------------------------------------
_SCORE_QUALITY_COLORS_TKD: dict[str, QColor] = {
    "6 PTS (Turn→Head)": QColor(_p_default.warning_light),
    "4 PTS (Turn→Trunk)": QColor(_ACCENT_ORANGE),
    "3 PTS (Kick→Head)":  QColor(_ACCENT_GOLD),
    "2 PTS (Kick→Trunk)": QColor(_ACCENT_GREEN),
    "1 PT  (Punch→Trunk)": QColor(_TEXT_TERTIARY),
    "NO POINT":           QColor(_BG_CARD),
}
_SCORE_QUALITY_ORDER_TKD = [
    "6 PTS (Turn→Head)", "4 PTS (Turn→Trunk)", "3 PTS (Kick→Head)",
    "2 PTS (Kick→Trunk)", "1 PT  (Punch→Trunk)", "NO POINT",
]




def _zonas_de(sport_id: str) -> list[str]:
    """Las zonas del deporte, las de su configuración: Jodan y Chudan en el
    karate, cabeza y tronco en el taekwondo… (decisión 0007)."""
    try:
        return list(catalogo.paquete(sport_id).configuracion().get("levels", []))
    except KeyError:
        return []


def _zona_de(nivel: str, zonas: list[str]) -> str:
    """La zona de una fila: su nivel, o la «Target» de una cadena de
    dimensiones como las que guardaba el kickboxing hasta la 1.0."""
    if nivel in zonas:
        return nivel
    return _extract_kb_target(nivel)


def _calidad_por_reglamento(sport_id: str) -> tuple[list[str], dict[str, QColor]]:
    """El reparto de puntuaciones de un deporte sin tabla propia: las de su
    reglamento, con su nombre («Scored», «Landed»…), en verde si puntúan."""
    puntuaciones = catalogo.paquete(sport_id).reglamento.puntuaciones
    orden = [p.nombre for p in puntuaciones]
    colores = {p.nombre: QColor(_ACCENT_GREEN if p.puntos > 0 else
                                _ACCENT_RED if p.codigo == "FOUL" else _TEXT_TERTIARY)
               for p in puntuaciones}
    return orden, colores

# ── Sidebar stylesheet (premium minimal) ─────────────────────────
_SIDEBAR_STYLE = f"""
QListWidget {{
    background: {_BG_SECONDARY};
    border: none;
    border-right: 1px solid {_BORDER};
    padding: 8px 0;
    min-width: 190px;
    max-width: 190px;
}}
QListWidget::item {{
    color: {_TEXT_TERTIARY};
    padding: 14px 20px;
    font-size: 12px;
    font-weight: 500;
    border: none;
}}
QListWidget::item:selected {{
    background: {_BG_CARD};
    color: {_TEXT_PRIMARY};
    border-left: 2px solid {_ACCENT_GOLD};
    padding-left: 18px;
}}
QListWidget::item:hover:!selected {{
    color: {_TEXT_SECONDARY};
}}
"""

_ROUND_BTN_STYLE = f"""
QPushButton {{
    background: {_BG_CARD};
    color: {_TEXT_TERTIARY};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 500;
    min-width: 48px;
}}
QPushButton:hover {{
    background: {_BG_HOVER};
    color: {_TEXT_SECONDARY};
}}
QPushButton:checked {{
    background: {_ACCENT_GOLD};
    color: {_BG_PRIMARY};
    border: 1px solid {_ACCENT_GOLD};
}}
"""

# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════

def _technique_base_name(full_name: str) -> str:
    for suffix in (" Jodan", " Chudan", " Head", " Trunk"):
        if full_name.endswith(suffix):
            return full_name[: -len(suffix)]
    return full_name



def _extract_kb_target(level_str: str) -> str:
    """Extract Target from kickboxing multi-level string 'Stance: Lead | Target: High'."""
    if not level_str:
        return ""
    for part in level_str.split("|"):
        part = part.strip()
        if part.startswith("Target:"):
            return part.split(":", 1)[1].strip()
    return ""


# ── Range classification for Distance Analysis ───────────────────
_RANGE_MAP: dict[str, str] = {
    "Jab": "Mid", "Rear Straight": "Mid", "Hook": "Mid",
    "Uppercut": "Close", "Spinning Backfist": "Close",
    "Roundhouse Kick": "Mid", "Front Kick": "Long", "Side Kick": "Long",
    "Hook Kick": "Mid", "Push Kick (Teep)": "Long", "Knee Strike": "Close",
    "Spinning Hook Kick": "Long", "Back Kick": "Long",
    # Los nombres del kickboxing desde la decisión 0007, con la distancia de
    # su nombre de la 1.0 (el low kick, la del roundhouse kick, que lo
    # incluía). Ninguno es del karate.
    "Cross": "Mid", "Spinning Back Fist": "Close", "Low Kick": "Mid",
    "Heel Kick": "Mid", "Spinning Heel Kick": "Long", "Spinning Back Kick": "Long",
    "Front Knee": "Close", "Circular Knee": "Close", "Clinch Knee": "Close",
}


def _classify_range(tech_name: str) -> str:
    """Classify a technique into Long / Mid / Close range."""
    return _RANGE_MAP.get(tech_name, "Mid")


# ══════════════════════════════════════════════════════════════════
# Analytical helpers (module-level, pure functions)
# ══════════════════════════════════════════════════════════════════

def _calc_tech_diversity(attacks: list) -> dict:
    """Calculate technical diversity metrics."""
    if not attacks:
        return {"unique": 0, "entropy": 0.0, "top3_pct": 0.0}
    counter = Counter(a.technique for a in attacks if a.technique)
    total = sum(counter.values())
    unique = len(counter)
    entropy = 0.0
    for count in counter.values():
        p = count / total
        entropy -= p * math.log(p)
    top3 = sum(c for _, c in counter.most_common(3))
    return {
        "unique": unique,
        "entropy": round(entropy, 3),
        "top3_pct": round(top3 / total * 100, 1) if total > 0 else 0.0,
    }


def _calc_sequences(attacks: list, length: int = 2, max_gap_s: float = 2.0) -> list:
    """Find most frequent strike sequences of given length."""
    if len(attacks) < length:
        return []
    sorted_attacks = sorted(attacks, key=lambda a: a.f_start)
    seq_counter: Counter = Counter()
    for i in range(len(sorted_attacks) - length + 1):
        window = sorted_attacks[i:i + length]
        if window[-1].f_start - window[0].f_start > 999999:
            continue
        ok = True
        for j in range(length - 1):
            gap = (window[j + 1].f_start - window[j].f_start) / 30.0
            if gap > max_gap_s or window[j].athlete != window[j + 1].athlete:
                ok = False
                break
        if ok:
            seq = tuple(a.technique for a in window if a.technique)
            if len(seq) == length:
                seq_counter[seq] += 1
    return seq_counter.most_common(5)


def _calc_defensive_profile(defense_list: list, total_attacks: int = 0) -> dict:
    """Calculate defensive response metrics.
    
    Args:
        defense_list: List of DEFENSE annotations.
        total_attacks: Total attack count for ratio calculation.
    """
    total_def = len(defense_list)
    if total_def == 0:
        return {"def_to_attack_ratio": 0.0, "total_def": 0, "preferred_defense": "—"}
    def_types = Counter(a.subcategory for a in defense_list)
    preferred = def_types.most_common(1)[0][0] if def_types else "—"
    return {
        "def_to_attack_ratio": round(total_def / max(total_attacks, 1), 2),
        "total_def": total_def,
        "preferred_defense": preferred,
    }


def _count_subcategory(annotations: list, subcat: str) -> int:
    """Count annotations matching a specific subcategory."""
    return sum(1 for a in annotations if a.subcategory == subcat)


def _top_technique(annotations: list) -> str:
    """Return the most frequently used technique name."""
    if not annotations:
        return "—"
    counter = Counter(a.technique for a in annotations if a.technique)
    return counter.most_common(1)[0][0] if counter else "—"


def _calc_stance_profile(attacks: list) -> dict:
    """Calculate Lead vs Rear limb usage from sport_specific_data (v6.1).

    Combinatorial Engine analytics: reads the ``stance`` key stored in
    each annotation's ``sport_specific_data`` dict and computes the
    percentage of Lead (front) vs Rear (back) limb attacks — a key
    technical-tactical indicator in WKF karate literature.

    Args:
        attacks: List of ATTACK annotations for one athlete.

    Returns:
        Dict with lead_pct, rear_pct, lead_count, rear_count and total
        (total = attacks that carry stance data; others are ignored).
    """
    stances = Counter(
        a.sport_specific_data.get("stance", "")
        for a in attacks
        if getattr(a, "sport_specific_data", None)
    )
    lead = stances.get("Lead", 0)
    rear = stances.get("Rear", 0)
    total = lead + rear
    if total == 0:
        return {"lead_pct": 0.0, "rear_pct": 0.0,
                "lead_count": 0, "rear_count": 0, "total": 0}
    return {
        "lead_pct": round(lead / total * 100, 1),
        "rear_pct": round(rear / total * 100, 1),
        "lead_count": lead,
        "rear_count": rear,
        "total": total,
    }


def _calc_action_type_profile(attacks: list) -> dict:
    """Calculate tactical action-type distribution (v6.1).

    Reads ``action_type`` from ``sport_specific_data`` (Direct / Counter /
    Anticipation / Combination) — the most cited tactical variable in
    elite WKF analysis (Koropanovski, Tabben et al.) — and computes both
    usage percentage and scoring effectiveness per action type.

    Args:
        attacks: List of ATTACK annotations for one athlete.

    Returns:
        Dict mapping action_type → {"count", "pct", "eff_pct"} where
        eff_pct is the % of that action type resulting in a score.
    """
    scored_codes = {"IPPON", "WAZA", "YUKO", "CONNECTED"}
    typed = [
        a for a in attacks
        if getattr(a, "sport_specific_data", None)
        and a.sport_specific_data.get("action_type")
    ]
    total = len(typed)
    result: dict[str, dict] = {}
    for action in ("Direct", "Counter", "Anticipation", "Combination"):
        subset = [a for a in typed
                  if a.sport_specific_data.get("action_type") == action]
        count = len(subset)
        scored = sum(1 for a in subset if a.score in scored_codes)
        result[action] = {
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0.0,
            "eff_pct": round(scored / count * 100, 1) if count else 0.0,
        }
    return result


def _calc_range_analysis(attacks: list, puntua=None) -> dict:
    """Calculate range preference and effectiveness.

    ``puntua`` dice si una acción puntuó. Sin él, lo de la 1.0: contar
    «CONNECTED», el código del kickboxing de entonces, que en el karate da
    siempre 0 % (anotado en la decisión 0007; se queda así hasta que Johan
    lo decida).
    """
    if puntua is None:
        def puntua(a):
            return a.score == "CONNECTED"
    if not attacks:
        return {"Long": (0, 0.0), "Mid": (0, 0.0), "Close": (0, 0.0)}
    ranges: dict[str, list] = {"Long": [], "Mid": [], "Close": []}
    for a in attacks:
        r = _classify_range(a.technique or "")
        ranges[r].append(a)
    result = {}
    for r in ["Long", "Mid", "Close"]:
        total = len(ranges[r])
        connected = sum(1 for a in ranges[r] if puntua(a))
        eff = round(connected / total * 100, 1) if total > 0 else 0.0
        result[r] = (total, eff)
    return result


# ══════════════════════════════════════════════════════════════════
# Helper widgets
# ══════════════════════════════════════════════════════════════════

def _caja(widget: QWidget, nombre: str, reglas: str) -> None:
    """El estilo de una caja solo para ella, no para lo que lleva dentro.

    Con ``QFrame{...}`` lo heredaban también sus etiquetas, porque una
    QLabel es un QFrame: el ``padding`` de la caja se lo comían ellas y no
    les quedaba sitio para el texto. Las tarjetas de cifras salían vacías, y
    el medidor de control sin su título ni su lectura (visto en la pantalla
    de la tableta el 11-10-2026; antes solo en capturas).
    """
    widget.setObjectName(nombre)
    widget.setStyleSheet(f"QFrame#{nombre}{{{reglas}}}")


class _KPICard(QFrame):
    def __init__(self, label: str, value: str, accent: str,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Relleno vertical de 8: con 16 la cifra (28 px) no cabía por un
        # punto en los 90 de alto de la tarjeta.
        _caja(self, "tarjetaKPI",
              f"background:{_BG_CARD};border:1px solid {_BORDER};"
              f"border-radius:6px;padding:8px 16px;")
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        val_lbl = QLabel(value)
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setStyleSheet(
            f"color:{accent};font-size:28px;font-weight:700;background:transparent;border:none;"
        )
        layout.addWidget(val_lbl)
        desc_lbl = QLabel(label)
        desc_lbl.setAlignment(Qt.AlignCenter)
        desc_lbl.setStyleSheet(
            f"color:{_TEXT_TERTIARY};font-size:10px;font-weight:500;"
            "letter-spacing:0.5px;text-transform:uppercase;background:transparent;border:none;"
        )
        layout.addWidget(desc_lbl)

    def set_value(self, value: str) -> None:
        lbl = self.layout().itemAt(0).widget()
        if isinstance(lbl, QLabel):
            lbl.setText(value)


class _AthleteComparisonPanel(QFrame):
    AKA_COLOR = _AKA_COLOR
    AO_COLOR = _AO_COLOR

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        _caja(self, "comparacionAtletas",
              f"background:{_BG_CARD};border:1px solid {_BORDER};"
              f"border-radius:6px;padding:8px;")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        # El deporte que se anota desde el principio, no el karate hasta
        # que llegue una sesión (decisión 0007), y sus zonas.
        self._sport_id = catalogo.activo().id
        self._zonas = _zonas_de(self._sport_id)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(4)
        title_lbl = QLabel("ATHLETE COMPARISON")
        title_lbl.setMinimumHeight(35)
        title_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        title_lbl.setStyleSheet(
            f"color:{_TEXT_TERTIARY};font-size:10px;font-weight:600;"
            "letter-spacing:0.5px;text-transform:uppercase;background:transparent;border:none;"
        )
        outer.addWidget(title_lbl)
        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 12, 0, 0)
        self._grid.setSpacing(8)
        self._grid.setColumnMinimumWidth(0, 110)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(2, 1)
        self._aka_hdr = QLabel(catalogo.etiqueta("AKA"))
        self._aka_hdr.setMinimumHeight(35)
        self._aka_hdr.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._aka_hdr.setAlignment(Qt.AlignCenter)
        self._aka_hdr.setStyleSheet(
            f"color:{self.AKA_COLOR};font-size:13px;font-weight:700;background:transparent;border:none;"
        )
        self._ao_hdr = QLabel(catalogo.etiqueta("AO"))
        self._ao_hdr.setMinimumHeight(35)
        self._ao_hdr.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._ao_hdr.setAlignment(Qt.AlignCenter)
        self._ao_hdr.setStyleSheet(
            f"color:{self.AO_COLOR};font-size:13px;font-weight:700;background:transparent;border:none;"
        )
        self._grid.addWidget(self._aka_hdr, 0, 1)
        self._grid.addWidget(self._ao_hdr, 0, 2)
        self._metric_lbls: dict[str, QLabel] = {}
        self._aka_vals: dict[str, QLabel] = {}
        self._ao_vals: dict[str, QLabel] = {}
        self._build_metric_rows()
        self._grid.setAlignment(Qt.AlignTop)
        outer.addLayout(self._grid, stretch=1)

    def _build_metric_rows(self) -> None:
        for lbl in list(self._metric_lbls.values()):
            self._grid.removeWidget(lbl)
            lbl.deleteLater()
        for lbl in list(self._aka_vals.values()):
            self._grid.removeWidget(lbl)
            lbl.deleteLater()
        for lbl in list(self._ao_vals.values()):
            self._grid.removeWidget(lbl)
            lbl.deleteLater()
        self._metric_lbls.clear()
        self._aka_vals.clear()
        self._ao_vals.clear()
        metrics = self._get_comparison_metrics()
        for row, metric in enumerate(metrics, start=1):
            ml = QLabel(metric)
            ml.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:10px;font-weight:500;background:transparent;border:none;")
            self._grid.addWidget(ml, row, 0)
            self._metric_lbls[metric] = ml
            al = QLabel("-")
            al.setMinimumHeight(35)
            al.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            al.setAlignment(Qt.AlignCenter)
            al.setStyleSheet(f"color:{self.AKA_COLOR};font-size:16px;font-weight:700;background:transparent;border:none;")
            self._grid.addWidget(al, row, 1)
            self._aka_vals[metric] = al
            bl = QLabel("-")
            bl.setMinimumHeight(35)
            bl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            bl.setAlignment(Qt.AlignCenter)
            bl.setStyleSheet(f"color:{self.AO_COLOR};font-size:16px;font-weight:700;background:transparent;border:none;")
            self._grid.addWidget(bl, row, 2)
            self._ao_vals[metric] = bl

    def _get_comparison_metrics(self) -> list[str]:
        # Una fila por zona del deporte: «Jodan Preference %» en el karate,
        # «Head Preference %» en el taekwondo…
        return ["Total Attacks", "Effectiveness %", "Most Used Technique",
                *[f"{zona} Preference %" for zona in self._zonas]]


    def set_sport_id(self, sport_id: str) -> None:
        if self._sport_id == sport_id:
            return
        self._sport_id = sport_id
        self._zonas = _zonas_de(sport_id)
        self._build_metric_rows()

    def set_athlete_labels(self, aka_label: str, ao_label: str) -> None:
        self._aka_hdr.setText(aka_label)
        self._ao_hdr.setText(ao_label)

    def update_data(self, aka_attacks: int, ao_attacks: int,
                    aka_effectiveness: float, ao_effectiveness: float,
                    aka_top_tech: str, ao_top_tech: str,
                    zonas_aka: Optional[dict[str, float]] = None,
                    zonas_ao: Optional[dict[str, float]] = None) -> None:
        """``zonas_*``: el porcentaje de cada zona del deporte."""
        self._aka_vals["Total Attacks"].setText(str(aka_attacks))
        self._ao_vals["Total Attacks"].setText(str(ao_attacks))
        self._aka_vals["Effectiveness %"].setText(f"{aka_effectiveness:.0f}%")
        self._ao_vals["Effectiveness %"].setText(f"{ao_effectiveness:.0f}%")
        self._aka_vals["Most Used Technique"].setText(aka_top_tech or "-")
        self._ao_vals["Most Used Technique"].setText(ao_top_tech or "-")
        for zona in self._zonas:
            fila = f"{zona} Preference %"
            if fila in self._aka_vals:
                self._aka_vals[fila].setText(f"{(zonas_aka or {}).get(zona, 0.0):.0f}%")
                self._ao_vals[fila].setText(f"{(zonas_ao or {}).get(zona, 0.0):.0f}%")


# ══════════════════════════════════════════════════════════════════
# Main Dashboard
# ══════════════════════════════════════════════════════════════════

class MatchReportView(QWidget):
    back_to_hub_requested = Signal()
    export_pdf_requested = Signal()

    def __init__(self, colors: AppColors,
                 sport_meta: Optional[dict[str, str]] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        aparecer(self)
        self._colors = colors
        self._sport_meta = sport_meta or {}
        self._session: Optional[any] = None
        self._active_round: Optional[int] = None  # None = all rounds
        self._all_annotations: list = []
        self._aka_name, self._ao_name = (catalogo.etiqueta(x) for x in COMPETIDORES)
        self._sport_id = self._sport_meta.get("id") or catalogo.activo().id
        self._is_kb = self._sport_id == "kickboxing"
        self._is_tkd = self._sport_id == "taekwondo"
        self._max_round = 1
        self._phase_annotations: list = []  # TKD temporal phases
        # El tiempo-movimiento, solo donde el deporte lo hace (taekwondo):
        # una página más, con las fases por asalto.
        try:
            self._tiempo_movimiento = catalogo.paquete(self._sport_id).tiempo_movimiento()
        except (KeyError, AttributeError):
            self._tiempo_movimiento = None
        self._time_motion_lbl: Optional[QLabel] = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        c = self._colors
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        # ── Top Bar ───────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(16)
        back_btn = QPushButton("Back to Hub")
        back_btn.setIcon(qta.icon("fa5s.arrow-left", color=c.muted))
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setMinimumHeight(36)
        back_btn.setStyleSheet(
            f"QPushButton{{background:{c.panel};color:{c.muted};"
            f"border:1px solid {c.border};border-radius:6px;padding:5px 14px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{c.border};color:{c.text};}}"
        )
        back_btn.clicked.connect(self.back_to_hub_requested.emit)
        top.addWidget(back_btn)
        self._title_lbl = QLabel("Board Report")
        self._title_lbl.setStyleSheet(
            f"color:{c.yellow};font-size:20px;font-weight:700;background:transparent;border:none;"
        )
        top.addWidget(self._title_lbl)
        top.addStretch()
        export_btn = QPushButton("Export to PDF")
        export_btn.setIcon(qta.icon("fa5s.file-pdf", color=_p_default.text_inverse))
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setMinimumHeight(36)
        export_btn.setStyleSheet(
            f"QPushButton{{background:rgba(255,255,255,0.06);color:{_p_default.white};"
            "border:1px solid rgba(255,255,255,0.10);border-radius:6px;padding:5px 16px;font-size:12px;font-weight:600;}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.10);border:1px solid {c.yellow};}}"
        )
        export_btn.clicked.connect(self.export_pdf_requested.emit)
        top.addWidget(export_btn)
        root.addLayout(top)

        # ── Bout Info Header ──────────────────────────────────────
        self._bout_header = QFrame()
        _caja(self._bout_header, "cabeceraCombate",
              f"background:{_BG_CARD};border:1px solid {_BORDER};border-radius:6px;")
        self._bout_header.setMinimumHeight(48)
        self._bout_header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout = QHBoxLayout(self._bout_header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(24)
        self._header_info_lbl = QLabel()
        self._header_info_lbl.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:11px;font-weight:500;background:transparent;")
        header_layout.addWidget(self._header_info_lbl)
        header_layout.addStretch()
        root.addWidget(self._bout_header)

        # ── Round Selector Bar ────────────────────────────────────
        self._round_selector = QHBoxLayout()
        self._round_selector.setSpacing(6)
        self._round_btn_group: list[QPushButton] = []
        round_lbl = QLabel("ROUND:")
        round_lbl.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:11px;font-weight:600;background:transparent;")
        self._round_selector.addWidget(round_lbl)
        self._round_selector.addStretch()
        root.addLayout(self._round_selector)

        # ── KPI Cards (2 rows: totals + individual times) ─────────
        kpi_container = QWidget()
        kpi_container.setFixedHeight(200)
        kpi_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        kpi_layout = QVBoxLayout(kpi_container)
        kpi_layout.setSpacing(8)
        kpi_row1 = QHBoxLayout()
        kpi_row1.setSpacing(16)
        self._kpi_total = _KPICard("TOTAL ANNOTATIONS", "0", _p_default.text_inverse)
        self._kpi_time = _KPICard("ACTIVE FIGHT TIME", "0s", c.green)
        # Con el nombre de cada competidor en el deporte que se anota.
        a, b = (catalogo.etiqueta(x) for x in COMPETIDORES)
        self._kpi_score_aka = _KPICard(f"SCORE — {a}", "0", c.aka)
        self._kpi_score_ao = _KPICard(f"SCORE — {b}", "0", c.ao)
        kpi_row1.addWidget(self._kpi_total)
        kpi_row1.addWidget(self._kpi_time)
        kpi_row1.addWidget(self._kpi_score_aka)
        kpi_row1.addWidget(self._kpi_score_ao)
        kpi_layout.addLayout(kpi_row1)
        kpi_row2 = QHBoxLayout()
        kpi_row2.setSpacing(16)
        self._kpi_aka_active = _KPICard(f"{a} ACTIVE TIME", "0s", c.aka)
        self._kpi_ao_active = _KPICard(f"{b} ACTIVE TIME", "0s", c.ao)
        self._kpi_aka_stopped = _KPICard(f"{a} STOPPED TIME", "0s", c.aka)
        self._kpi_ao_stopped = _KPICard(f"{b} STOPPED TIME", "0s", c.ao)
        kpi_row2.addWidget(self._kpi_aka_active)
        kpi_row2.addWidget(self._kpi_ao_active)
        kpi_row2.addWidget(self._kpi_aka_stopped)
        kpi_row2.addWidget(self._kpi_ao_stopped)
        kpi_layout.addLayout(kpi_row2)
        root.addWidget(kpi_container)

        # ── Sidebar + Stacked Widget ──────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(0)
        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._stack.setStyleSheet("QStackedWidget{background:transparent;border:none;}")
        self._sidebar = self._create_sidebar()
        body.addWidget(self._sidebar)
        body.addWidget(self._stack, stretch=1)
        root.addLayout(body, stretch=1)

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _create_sidebar(self) -> QListWidget:
        sidebar = QListWidget()
        sidebar.setStyleSheet(_SIDEBAR_STYLE)
        items = [
            (qta.icon("fa5s.trophy", color=_p_default.warning), "Executive Summary"),
            (qta.icon("fa5s.crosshairs", color=_p_default.grey_mid), "Tactical Analysis"),
            (qta.icon("fa5s.tachometer-alt", color=_p_default.grey_mid), "Fight Rhythm"),
            (qta.icon("fa5s.chart-line", color=_p_default.grey_mid), "Performance Charts"),
            (qta.icon("fa5s.dna", color=_p_default.grey_mid), "Deep Analysis"),
        ]
        self._tecnico_lbl: Optional[QLabel] = None
        _TM = (qta.icon("fa5s.stopwatch", color=_p_default.grey_mid), "Time-Motion")
        if self._tiempo_movimiento and self._sport_id != "karate":
            # En los demás deportes el informe es el de su análisis (Johan,
            # 8-10-2026: «cada modo genera un reporte diferente basado en
            # los datos que toma»): la página técnico-táctica, la de
            # tiempo-movimiento, o las dos. Las cinco páginas de arriba se
            # construyen (las rellena `_refresh`) pero no se enseñan:
            # hablan de karate.
            items = [(qta.icon("fa5s.crosshairs", color=_p_default.warning), "Technical-tactical"),
                     _TM]
        elif self._tiempo_movimiento:
            # El karate conserva sus cinco páginas —son su informe
            # técnico-táctico de siempre, y el modo completo no cambia
            # (decisión 0008)— y gana la de tiempo-movimiento.
            items = items + [_TM]
        for icon, text in items:
            sidebar.addItem(QListWidgetItem(icon, text))
        sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        self._exec_page = self._create_executive_view()
        self._tactical_page = self._create_tactical_view()
        self._rhythm_page = self._create_rhythm_view()
        self._charts_page = self._create_charts_view()
        self._deep_page = self._create_deep_analysis_view()
        if self._tiempo_movimiento:
            self._stack.addWidget(self._create_tecnico_view())
            self._stack.addWidget(self._create_time_motion_view())
        else:
            self._stack.addWidget(self._exec_page)
            self._stack.addWidget(self._tactical_page)
            self._stack.addWidget(self._rhythm_page)
            self._stack.addWidget(self._charts_page)
            self._stack.addWidget(self._deep_page)
        sidebar.setCurrentRow(0)
        return sidebar

    # ------------------------------------------------------------------
    # Technical-tactical (solo donde el deporte hace tiempo-movimiento)
    # ------------------------------------------------------------------

    def _create_tecnico_view(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)
        self._tecnico_lbl = QLabel()
        self._tecnico_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._tecnico_lbl.setWordWrap(True)
        self._tecnico_lbl.setStyleSheet(
            f"color:{_TEXT_PRIMARY};font-size:12px;background:transparent;border:none;")
        layout.addWidget(self._tecnico_lbl)
        layout.addStretch()
        scroll.setWidget(inner)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _analisis_de(self, session) -> str:
        meta = getattr(session, "bout_metadata", None) or {}
        return str(meta.get("analysis", "") or "")

    def _populate_tecnico(self, annotations: list) -> None:
        """La página técnico-táctica, con las acciones del asalto elegido."""
        if self._tecnico_lbl is None or not self._session:
            return
        from karlos_core.informe_tecnico import html
        puntos = catalogo.paquete(self._sport_id).reglamento.puntos
        self._tecnico_lbl.setText(html(
            annotations, self._analisis_de(self._session) != "technical_tactical",
            _TEXT_TERTIARY, _p_default.warning, puntos))

    def _mostrar_paginas_del_analisis(self, analisis: str) -> None:
        """Técnico-táctico: sus páginas; tiempo-movimiento: la suya;
        completo (o sin análisis dicho): todas.

        Se esconde por el nombre de la página y no por su número, porque el
        karate tiene cinco técnico-tácticas y los demás deportes una
        (decisión 0008).
        """
        if not self._tiempo_movimiento:
            return
        if analisis == "technical_tactical":
            ocultas = {"Time-Motion"}
        elif analisis == "time_motion":
            ocultas = {self._sidebar.item(i).text()
                       for i in range(self._sidebar.count())} - {"Time-Motion"}
        else:
            ocultas = set()
        primera = None
        for i in range(self._sidebar.count()):
            oculta = self._sidebar.item(i).text() in ocultas
            self._sidebar.item(i).setHidden(oculta)
            if not oculta and primera is None:
                primera = i
        if primera is not None:
            self._sidebar.setCurrentRow(primera)

    # ------------------------------------------------------------------
    # Time-Motion (solo donde el deporte lo hace)
    # ------------------------------------------------------------------

    def _create_time_motion_view(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)
        self._time_motion_lbl = QLabel()
        self._time_motion_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._time_motion_lbl.setWordWrap(True)
        self._time_motion_lbl.setStyleSheet(
            f"color:{_TEXT_PRIMARY};font-size:12px;background:transparent;border:none;")
        layout.addWidget(self._time_motion_lbl)
        layout.addStretch()
        scroll.setWidget(inner)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _populate_time_motion(self, session) -> None:
        """Por asalto: las fases marcadas con las teclas, las derivadas de las
        acciones (con las definiciones del especialista de taekwondo) y su acuerdo."""
        if self._time_motion_lbl is None:
            return
        from karlos_core.tiempo_movimiento import html_informe

        meta = getattr(session, "bout_metadata", None) or {}
        self._time_motion_lbl.setText(html_informe(
            self._all_annotations, getattr(session, "asaltos", None),
            getattr(session, "fases", None), session.fps if session.fps > 0 else 30.0,
            float((self._tiempo_movimiento or {}).get("gap_s", 2.0)),
            _TEXT_TERTIARY, _p_default.warning,
            derivar=meta.get("analysis", "") != "technical_tactical"))
        self._mostrar_paginas_del_analisis(self._analisis_de(session))

    def _on_sidebar_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Executive View (page 0)
    # ------------------------------------------------------------------

    def _create_executive_view(self) -> QWidget:
        # Desplazable, como «Deep Analysis»: sin espacio (la tableta) la
        # página se apretaba y el medidor y las métricas quedaban cortados.
        # Así su mínimo no cuenta para el de la ventana, que no crece.
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)
        self._exec_winner = QLabel()
        self._exec_winner.setAlignment(Qt.AlignCenter)
        self._exec_winner.setMinimumHeight(60)
        self._exec_winner.setStyleSheet(
            f"font-size:24px;font-weight:700;background:{_BG_CARD};"
            f"border:1px solid {_BORDER};border-radius:6px;padding:16px;"
        )
        layout.addWidget(self._exec_winner)
        self._exec_score_summary = QLabel()
        self._exec_score_summary.setAlignment(Qt.AlignCenter)
        self._exec_score_summary.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:14px;font-weight:500;background:transparent;border:none;padding:8px;")
        layout.addWidget(self._exec_score_summary)

        # ── Momentum Meter (Control Bar) ──
        momentum_frame = QFrame()
        _caja(momentum_frame, "medidorControl",
              f"background:{_BG_CARD};border:1px solid {_BORDER};"
              f"border-radius:6px;padding:12px;")
        # Sin alto mínimo fijo: con 80 se podía apretar por debajo de lo
        # que ocupa (título, barra, punto y lectura) y el punto pisaba la
        # lectura. Ahora manda lo que lleva dentro.
        momentum_layout = QVBoxLayout(momentum_frame)
        momentum_layout.setContentsMargins(16, 8, 16, 8)
        momentum_layout.setSpacing(4)
        momentum_title = QLabel("CONTROL")
        momentum_title.setAlignment(Qt.AlignCenter)
        momentum_title.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:10px;font-weight:600;letter-spacing:0.5px;background:transparent;border:none;")
        momentum_layout.addWidget(momentum_title)
        self._momentum_bar = QFrame()
        self._momentum_bar.setFixedHeight(6)
        # El borde, suyo: antes lo heredaba de la caja y era lo único que
        # dejaba ver la barra (tiene el mismo fondo que la caja).
        self._momentum_bar.setStyleSheet(f"QFrame{{background:{_BG_CARD};border:1px solid {_BORDER};border-radius:3px;}}")
        momentum_layout.addWidget(self._momentum_bar)
        self._momentum_indicator = QFrame()
        self._momentum_indicator.setFixedSize(14, 14)
        self._momentum_indicator.setStyleSheet(f"QFrame{{background:{_TEXT_TERTIARY};border-radius:7px;}}")
        momentum_layout.addWidget(self._momentum_indicator, alignment=Qt.AlignCenter)
        self._momentum_lbl = QLabel("Neutral")
        self._momentum_lbl.setAlignment(Qt.AlignCenter)
        self._momentum_lbl.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:12px;font-weight:600;background:transparent;border:none;")
        momentum_layout.addWidget(self._momentum_lbl)
        layout.addWidget(momentum_frame)

        # ── Coach Insights (Key Metrics) ──
        insights_frame = QFrame()
        _caja(insights_frame, "metricasClave",
              f"background:{_BG_CARD};border:1px solid {_BORDER};"
              f"border-radius:6px;padding:12px;")
        # Igual: con 80 cortaba las tarjetas, que piden 90.
        insights_layout = QHBoxLayout(insights_frame)
        insights_layout.setContentsMargins(16, 8, 16, 8)
        insights_layout.setSpacing(24)
        self._insight_attack_rate = _KPICard("ATTACK RATE", "0/min", _TEXT_TERTIARY)
        self._insight_efficiency = _KPICard("EFFICIENCY", "0%", _TEXT_TERTIARY)
        self._insight_defense = _KPICard("DEFENSE RATIO", "0.0", _TEXT_TERTIARY)
        insights_layout.addWidget(self._insight_attack_rate)
        insights_layout.addWidget(self._insight_efficiency)
        insights_layout.addWidget(self._insight_defense)
        layout.addWidget(insights_frame)

        # ── Athlete Comparison Grid ──
        insights_grid = QGridLayout()
        insights_grid.setSpacing(12)
        self._exec_insights: dict[str, QLabel] = {}
        insight_items = [
            ("Scoring Efficiency", "aka_eff_val", "ao_eff_val"),
            ("Attack Rate", "aka_rate_val", "ao_rate_val"),
            ("Time to First Score", "aka_first_val", "ao_first_val"),
            ("Longest Streak", "aka_streak_val", "ao_streak_val"),
        ]
        for row, (label, aka_key, ao_key) in enumerate(insight_items):
            ml = QLabel(label)
            ml.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:11px;font-weight:500;background:transparent;border:none;")
            insights_grid.addWidget(ml, row, 0)
            al = QLabel("-")
            al.setAlignment(Qt.AlignCenter)
            al.setStyleSheet(f"color:{_AKA_COLOR};font-size:14px;font-weight:700;background:transparent;border:none;")
            insights_grid.addWidget(al, row, 1)
            self._exec_insights[aka_key] = al
            bl = QLabel("-")
            bl.setAlignment(Qt.AlignCenter)
            bl.setStyleSheet(f"color:{_AO_COLOR};font-size:14px;font-weight:700;background:transparent;border:none;")
            insights_grid.addWidget(bl, row, 2)
            self._exec_insights[ao_key] = bl
        layout.addLayout(insights_grid)
        layout.addStretch()
        scroll.setWidget(inner)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    # ------------------------------------------------------------------
    # Tactical View (page 1)
    # ------------------------------------------------------------------

    def _create_tactical_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)
        self._comparison_panel = _AthleteComparisonPanel()
        layout.addWidget(self._comparison_panel, stretch=0)
        self._scoring_breakdown_lbl = QLabel()
        self._scoring_breakdown_lbl.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:12px;font-weight:500;background:transparent;border:none;padding:8px;")
        layout.addWidget(self._scoring_breakdown_lbl)
        self._best_tech_lbl = QLabel()
        self._best_tech_lbl.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:12px;font-weight:500;background:transparent;border:none;padding:8px;")
        layout.addWidget(self._best_tech_lbl)
        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Rhythm View (page 2)
    # ------------------------------------------------------------------

    def _create_rhythm_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)
        charts_row = QHBoxLayout()
        self._rhythm_aka_fatigue = self._create_fatigue_bar_view(_ACCENT_RED)
        self._rhythm_ao_fatigue = self._create_fatigue_bar_view(_ACCENT_BLUE)
        charts_row.addWidget(self._rhythm_aka_fatigue, stretch=1)
        charts_row.addWidget(self._rhythm_ao_fatigue, stretch=1)
        layout.addLayout(charts_row, stretch=1)
        self._rhythm_metrics_lbl = QLabel()
        self._rhythm_metrics_lbl.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:11px;font-weight:500;background:transparent;border:none;padding:8px;")
        layout.addWidget(self._rhythm_metrics_lbl)
        return page

    # ------------------------------------------------------------------
    # Charts View (page 3)
    # ------------------------------------------------------------------

    def _create_charts_view(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)
        self._storyline_chart = self._create_storyline_chart()
        self._storyline_chart.setMinimumSize(400, 250)
        layout.addWidget(self._storyline_chart, stretch=1)
        donuts_row = QHBoxLayout()
        self._aka_donut = self._create_donut_view()
        self._ao_donut = self._create_donut_view()
        donuts_row.addWidget(self._aka_donut, stretch=1)
        donuts_row.addWidget(self._ao_donut, stretch=1)
        layout.addLayout(donuts_row, stretch=1)
        return page

    # ------------------------------------------------------------------
    # Deep Analysis View (page 4) — NEW
    # ------------------------------------------------------------------

    def _create_deep_analysis_view(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)
        self._deep_content = QVBoxLayout()
        layout.addLayout(self._deep_content)
        layout.addStretch()
        scroll.setWidget(inner)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _populate_deep_analysis(self, annotations: list, aka_name: str, ao_name: str) -> None:
        """Populate the Deep Analysis page with all sections."""
        # Clear previous content
        while self._deep_content.count():
            item = self._deep_content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        c = self._colors
        # TKD: COUNTERATTACK counts as attack too
        is_tkd = self._sport_id == "taekwondo"
        aka_attacks = [a for a in annotations if a.athlete == "AKA" and (a.category == "ATTACK" or (is_tkd and a.category == "COUNTERATTACK"))]
        ao_attacks = [a for a in annotations if a.athlete == "AO" and (a.category == "ATTACK" or (is_tkd and a.category == "COUNTERATTACK"))]


        # --- A. Technical Diversity (ATTACK only) ---
        self._add_section_title(self._deep_content, "A. TECHNICAL DIVERSITY INDEX")
        aka_div = _calc_tech_diversity(aka_attacks)
        ao_div = _calc_tech_diversity(ao_attacks)
        self._add_metric_row(self._deep_content, "Unique Techniques", str(aka_div["unique"]), str(ao_div["unique"]))
        # ✅ BUG 8 FIX: Añadir interpretación cualitativa al entropy score
        def _entropy_label(entropy: float) -> str:
            if entropy > 1.5: return f"{entropy:.2f} (High)"
            elif entropy > 0.8: return f"{entropy:.2f} (Med)"
            else: return f"{entropy:.2f} (Low)"
        self._add_metric_row(self._deep_content, "Diversity Index (0-3)", 
                             _entropy_label(aka_div['entropy']), 
                             _entropy_label(ao_div['entropy']))
        self._add_metric_row(self._deep_content, "Top 3 Weapons %", f"{aka_div['top3_pct']:.1f}%", f"{ao_div['top3_pct']:.1f}%")

        # --- B. Offensive Sequences (ATTACK only) ---
        self._add_section_title(self._deep_content, "B. OFFENSIVE SEQUENCES")
        aka_seqs_2 = _calc_sequences(aka_attacks, length=2)
        ao_seqs_2 = _calc_sequences(ao_attacks, length=2)
        # ✅ BUG 6 FIX: Limpiar nombres de técnicas (remover " Jodan", " Chudan")
        aka_top_seq = " → ".join(_technique_base_name(t) for t in aka_seqs_2[0][0]) if aka_seqs_2 else "—"
        ao_top_seq = " → ".join(_technique_base_name(t) for t in ao_seqs_2[0][0]) if ao_seqs_2 else "—"
        self._add_metric_row(self._deep_content, "Top 2-Strike Combo", aka_top_seq, ao_top_seq, as_str=True)
        aka_seqs_3 = _calc_sequences(aka_attacks, length=3)
        ao_seqs_3 = _calc_sequences(ao_attacks, length=3)
        # ✅ BUG 6 FIX: Limpiar nombres de técnicas (remover " Jodan", " Chudan")
        aka_top3 = " → ".join(_technique_base_name(t) for t in aka_seqs_3[0][0]) if aka_seqs_3 else "—"
        ao_top3 = " → ".join(_technique_base_name(t) for t in ao_seqs_3[0][0]) if ao_seqs_3 else "—"
        self._add_metric_row(self._deep_content, "Top 3-Strike Combo", aka_top3, ao_top3, as_str=True)

        # --- C. Defensive Response Profile ---
        self._add_section_title(self._deep_content, "C. DEFENSIVE RESPONSE PROFILE")
        aka_defs = [a for a in annotations if a.athlete == "AKA" and a.category == "DEFENSE"]
        ao_defs = [a for a in annotations if a.athlete == "AO" and a.category == "DEFENSE"]
        aka_total_attacks = len([a for a in annotations if a.athlete == "AKA" and (a.category == "ATTACK" or (is_tkd and a.category == "COUNTERATTACK"))])
        ao_total_attacks = len([a for a in annotations if a.athlete == "AO" and (a.category == "ATTACK" or (is_tkd and a.category == "COUNTERATTACK"))])
        aka_def = _calc_defensive_profile(aka_defs, aka_total_attacks)
        ao_def = _calc_defensive_profile(ao_defs, ao_total_attacks)
        self._add_metric_row(self._deep_content, "Total Defenses", str(aka_def.get("total_def", 0)), str(ao_def.get("total_def", 0)))
        self._add_metric_row(self._deep_content, "Defense/Attack Ratio", f"{aka_def['def_to_attack_ratio']:.2f}", f"{ao_def['def_to_attack_ratio']:.2f}")
        if is_tkd:
            self._add_metric_row(self._deep_content, "Dodge", str(_count_subcategory(aka_defs, "DODGE")), str(_count_subcategory(ao_defs, "DODGE")))
            self._add_metric_row(self._deep_content, "Block", str(_count_subcategory(aka_defs, "BLOCK")), str(_count_subcategory(ao_defs, "BLOCK")))
            self._add_metric_row(self._deep_content, "Cut", str(_count_subcategory(aka_defs, "CUT")), str(_count_subcategory(ao_defs, "CUT")))
        else:
            self._add_metric_row(self._deep_content, "Hand Defenses", str(_count_subcategory(aka_defs, "HAND DEFENSES")), str(_count_subcategory(ao_defs, "HAND DEFENSES")))
            self._add_metric_row(self._deep_content, "Evasions & Footwork", str(_count_subcategory(aka_defs, "EVASIONS & FOOTWORK")), str(_count_subcategory(ao_defs, "EVASIONS & FOOTWORK")))


        # --- D. Tactics & Fouls ---
        self._add_section_title(self._deep_content, "D. TACTICS & FOULS")
        aka_tactics = [a for a in annotations if a.athlete == "AKA" and a.category == "TACTICS"]
        ao_tactics = [a for a in annotations if a.athlete == "AO" and a.category == "TACTICS"]
        aka_fouls = [a for a in annotations if a.athlete == "AKA" and a.category == "FOUL"]
        ao_fouls = [a for a in annotations if a.athlete == "AO" and a.category == "FOUL"]
        self._add_metric_row(self._deep_content, "Total Tactics", str(len(aka_tactics)), str(len(ao_tactics)))
        self._add_metric_row(self._deep_content, "Total Fouls", str(len(aka_fouls)), str(len(ao_fouls)))
        self._add_metric_row(self._deep_content, "Most Used Tactic", _top_technique(aka_tactics), _top_technique(ao_tactics), as_str=True)
        self._add_metric_row(self._deep_content, "Most Common Foul", _top_technique(aka_fouls), _top_technique(ao_fouls), as_str=True)

        # --- E. Distance & Range Analysis (ATTACK only) ---
        self._add_section_title(self._deep_content, "E. DISTANCE & RANGE ANALYSIS")
        # Fuera del karate, lo que puntúa lo dice el reglamento del deporte.
        puntua = None
        if self._sport_id != "karate":
            puntos = catalogo.paquete(self._sport_id).reglamento.puntos

            def puntua(a):
                return puntos(a.score) > 0
        aka_range = _calc_range_analysis(aka_attacks, puntua)
        ao_range = _calc_range_analysis(ao_attacks, puntua)
        for rng in ["Long", "Mid", "Close"]:
            aka_cnt, aka_eff = aka_range[rng]
            ao_cnt, ao_eff = ao_range[rng]
            self._add_metric_row(self._deep_content, f"{rng} Range %",
                                 f"{aka_cnt} atk ({aka_eff:.0f}%)" if aka_cnt else "—",
                                 f"{ao_cnt} atk ({ao_eff:.0f}%)" if ao_cnt else "—",
                                 as_str=True)

        # --- F. Stance Analysis (Combinatorial Engine v6.1) ---
        # Lead vs Rear limb usage extracted from sport_specific_data.
        aka_stance = _calc_stance_profile(aka_attacks)
        ao_stance = _calc_stance_profile(ao_attacks)
        if aka_stance["total"] > 0 or ao_stance["total"] > 0:
            self._add_section_title(self._deep_content, "F. STANCE ANALYSIS (LEAD vs REAR)")
            self._add_metric_row(
                self._deep_content, "Lead Limb Usage %",
                f"{aka_stance['lead_pct']:.0f}% ({aka_stance['lead_count']})" if aka_stance["total"] else "—",
                f"{ao_stance['lead_pct']:.0f}% ({ao_stance['lead_count']})" if ao_stance["total"] else "—",
                as_str=True)
            self._add_metric_row(
                self._deep_content, "Rear Limb Usage %",
                f"{aka_stance['rear_pct']:.0f}% ({aka_stance['rear_count']})" if aka_stance["total"] else "—",
                f"{ao_stance['rear_pct']:.0f}% ({ao_stance['rear_count']})" if ao_stance["total"] else "—",
                as_str=True)

        # --- G. Tactical Action-Type Analysis (WKF literature) ---
        # Direct / Counter / Anticipation / Combination distribution and
        # effectiveness — the key tactical indicator in elite WKF studies.
        aka_actions = _calc_action_type_profile(aka_attacks)
        ao_actions = _calc_action_type_profile(ao_attacks)
        if any(v["count"] for v in aka_actions.values()) or \
           any(v["count"] for v in ao_actions.values()):
            self._add_section_title(self._deep_content, "G. TACTICAL ACTION-TYPE ANALYSIS")
            for action in ("Direct", "Counter", "Anticipation", "Combination"):
                ak = aka_actions[action]
                ao_ = ao_actions[action]
                self._add_metric_row(
                    self._deep_content, f"{action} % (Eff.)",
                    f"{ak['pct']:.0f}% (eff {ak['eff_pct']:.0f}%)" if ak["count"] else "—",
                    f"{ao_['pct']:.0f}% (eff {ao_['eff_pct']:.0f}%)" if ao_["count"] else "—",
                    as_str=True)

    def _add_section_title(self, parent: QVBoxLayout, title: str) -> None:
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color:{self._colors.yellow};font-size:12px;font-weight:700;"
            "background:transparent;border:none;padding:4px 0;"
        )
        parent.addWidget(lbl)

    def _add_metric_row(self, parent: QVBoxLayout, label: str, aka_val: str, ao_val: str, as_str: bool = True) -> None:
        row = QHBoxLayout()
        row.setSpacing(16)
        ml = QLabel(label)
        ml.setStyleSheet(f"color:{_TEXT_TERTIARY};font-size:11px;font-weight:500;background:transparent;min-width:160px;")
        row.addWidget(ml)
        al = QLabel(str(aka_val))
        al.setAlignment(Qt.AlignCenter)
        al.setStyleSheet(f"color:{_AKA_COLOR};font-size:11px;font-weight:600;background:transparent;min-width:120px;")
        row.addWidget(al)
        bl = QLabel(str(ao_val))
        bl.setAlignment(Qt.AlignCenter)
        bl.setStyleSheet(f"color:{_AO_COLOR};font-size:11px;font-weight:600;background:transparent;min-width:120px;")
        row.addWidget(bl)
        row.addStretch()
        parent.addLayout(row)

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                MatchReportView._clear_layout(item.layout())

    # ------------------------------------------------------------------
    # Chart factories
    # ------------------------------------------------------------------

    def _create_donut_view(self) -> QChartView:
        series = QPieSeries()
        series.setHoleSize(0.55)
        sl = series.append("No Data", 1)
        sl.setColor(QColor(_BG_CARD))
        sl.setLabelVisible(False)
        chart = QChart()
        chart.addSeries(series)
        chart.setBackgroundBrush(Qt.GlobalColor.transparent)
        chart.setTitle("")
        chart.setMargins(QMargins(0, 0, 0, 0))
        chart.layout().setContentsMargins(0, 0, 0, 0)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.legend().setLabelColor(QColor(_TEXT_SECONDARY))
        chart.legend().setFont(QFont("Inter", 10))
        chart.legend().setMinimumHeight(30)
        view = QChartView(chart)
        view.setRenderHint(QPainter.Antialiasing)
        view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        view.setMinimumSize(280, 200)
        view.setStyleSheet("background:transparent;border:none;")
        return view

    def _create_fatigue_bar_view(self, color: str) -> QChartView:
        # Bar set con color base
        bar_set = QBarSet("Attacks")
        bar_set.setColor(QColor(color))
        bar_set.setBorderColor(QColor(color))
        series = QBarSeries()
        series.append(bar_set)
        # Línea de tendencia (fatiga)
        self._trend_line = QLineSeries()
        self._trend_line.setPen(QPen(QColor(color).lighter(140), 2.0, Qt.DashLine))
        chart = QChart()
        chart.addSeries(series)
        chart.addSeries(self._trend_line)
        chart.setBackgroundBrush(Qt.GlobalColor.transparent)
        chart.setTitle("")
        chart.setMargins(QMargins(0, 0, 0, 0))
        chart.layout().setContentsMargins(0, 0, 0, 0)
        chart.legend().setVisible(False)
        ax_y = QValueAxis()
        ax_y.setRange(0, 5)
        ax_y.setLabelFormat("%d")
        ax_y.setLabelsColor(QColor(_TEXT_TERTIARY))
        ax_y.setTitleBrush(QColor(_TEXT_TERTIARY))
        ax_y.setGridLineVisible(False)
        chart.addAxis(ax_y, Qt.AlignLeft)
        series.attachAxis(ax_y)
        self._trend_line.attachAxis(ax_y)
        ax_x = QBarCategoryAxis()
        ax_x.setLabelsColor(QColor(_TEXT_TERTIARY))
        ax_x.setGridLineVisible(False)
        chart.addAxis(ax_x, Qt.AlignBottom)
        series.attachAxis(ax_x)
        self._trend_line.attachAxis(ax_x)
        view = QChartView(chart)
        view.setRenderHint(QPainter.Antialiasing)
        view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        view.setMinimumSize(280, 180)
        view.setStyleSheet("background:transparent;border:none;")
        return view

    def _create_storyline_chart(self) -> QChartView:
        chart = QChart()
        chart.setBackgroundBrush(Qt.GlobalColor.transparent)
        chart.setTitle("")
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.legend().setLabelColor(QColor(_TEXT_TERTIARY))
        chart.legend().setFont(QFont("Inter", 9))
        ax_y = QValueAxis()
        ax_y.setTitleText("Cumulative Score")
        ax_y.setRange(0, 5)
        ax_y.setLabelFormat("%.0f")
        ax_y.setLabelsColor(QColor(_TEXT_MUTED))
        ax_y.setTitleBrush(QColor(_TEXT_MUTED))
        ax_y.setLinePenColor(QColor(_TEXT_MUTED))
        ax_y.setGridLineVisible(False)
        chart.addAxis(ax_y, Qt.AlignLeft)
        self._story_aka = QLineSeries()
        self._story_aka.setName("AKA")
        self._story_aka.setPen(QPen(QColor(_ACCENT_RED), 4.0))
        chart.addSeries(self._story_aka)
        self._story_aka.attachAxis(ax_y)
        self._story_ao = QLineSeries()
        self._story_ao.setName("AO")
        self._story_ao.setPen(QPen(QColor(_ACCENT_BLUE), 4.0))
        chart.addSeries(self._story_ao)
        self._story_ao.attachAxis(ax_y)
        view = QChartView(chart)
        view.setRenderHint(QPainter.Antialiasing)
        view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        view.setMinimumSize(320, 220)
        view.setStyleSheet("background:transparent;border:none;")
        return view

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def datos_para_pdf(self) -> tuple[str, list, object]:
        """Lo que el informe PDF necesita de lo que se está enseñando: el
        deporte, las anotaciones y la sesión (decisión 0004: el núcleo ya no
        mira dentro del informe)."""
        return self._sport_id, self._all_annotations, self._session

    def set_session(self, session, colors: AppColors) -> None:
        self._session = session
        self._colors = colors
        self._all_annotations = session.annotations

        meta = getattr(session, 'bout_metadata', None) or {}
        a, b = (catalogo.etiqueta(x) for x in COMPETIDORES)
        self._aka_name = meta.get("athlete_a_name", a)
        self._ao_name = meta.get("athlete_b_name", b)
        self._sport_id = self._sport_meta.get("id", "karate")
        self._is_kb = self._sport_id == "kickboxing"
        self._is_tkd = self._sport_id == "taekwondo"


        event = meta.get("bout_event") or meta.get("competition_name", "")
        round_ = meta.get("bout_round", "")
        if self._aka_name != "AKA" or self._ao_name != "AO":
            # El código del formato no se enseña: en taekwondo salía
            # «Chung (AKA)». En karate la etiqueta ES «AKA», así que no
            # cambia nada (decisión 0007).
            title = (f"{self._aka_name} ({catalogo.etiqueta('AKA')}) vs "
                     f"{self._ao_name} ({catalogo.etiqueta('AO')})")
            if event:
                title += f"  —  {event}"
            if round_:
                title += f"  {round_}"
        else:
            title = f"Board Report: {session.video_name}"
        self._title_lbl.setText(title)
        self._comparison_panel.set_athlete_labels(
            f"{self._aka_name} ({catalogo.etiqueta('AKA')})",
            f"{self._ao_name} ({catalogo.etiqueta('AO')})")

        dur_str = self._format_duration_short(session.duration_s)
        info_parts = []
        if session.resolution:
            info_parts.append(session.resolution)
        if session.fps > 0:
            info_parts.append(f"{session.fps:.1f} FPS")
        if dur_str:
            info_parts.append(dur_str)
        video_meta = "  |  ".join(info_parts) if info_parts else ""
        header_text = f"{session.video_name}"
        if video_meta:
            header_text += f"    —    {video_meta}"
        self._header_info_lbl.setText(header_text)

        # Determine max round
        rounds = set(a.round for a in self._all_annotations if a.round)
        self._max_round = max(rounds) if rounds else 1

        # Build round selector buttons
        self._build_round_buttons()

        # Show all rounds by default
        self._set_active_round(None)

        if self._tiempo_movimiento:
            self._populate_time_motion(session)

    # ------------------------------------------------------------------
    # Round selector
    # ------------------------------------------------------------------

    def _build_round_buttons(self) -> None:
        """Build round selector buttons dynamically."""
        # Clear everything except the "ROUND:" label (index 0)
        while self._round_selector.count() > 1:
            item = self._round_selector.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
            del item

        for r in range(1, self._max_round + 1):
            btn = QPushButton(f"R{r}")
            btn.setCheckable(True)
            btn.setStyleSheet(_ROUND_BTN_STYLE)
            btn.clicked.connect(lambda checked, rn=r: self._set_active_round(rn))
            self._round_selector.addWidget(btn)
            self._round_btn_group.append(btn)

        all_btn = QPushButton("ALL")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.setStyleSheet(_ROUND_BTN_STYLE)
        all_btn.clicked.connect(lambda: self._set_active_round(None))
        self._round_selector.addWidget(all_btn)
        self._round_btn_group.append(all_btn)
        self._round_selector.addStretch()

    def _set_active_round(self, round_num: Optional[int]) -> None:
        """Set the active round and refresh all metrics."""
        self._active_round = round_num
        # Update button states
        for btn in self._round_btn_group:
            if round_num is None and btn.text() == "ALL":
                btn.setChecked(True)
            elif round_num is not None and btn.text() == f"R{round_num}":
                btn.setChecked(True)
            else:
                btn.setChecked(False)
        self._refresh()

    def _filtered_annotations(self) -> list:
        """Return annotations filtered by active round."""
        if self._active_round is None:
            return self._all_annotations
        return [a for a in self._all_annotations if a.round == self._active_round]

    # ------------------------------------------------------------------
    # Refresh — single pass extraction + populate all pages
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        annotations = self._filtered_annotations()
        session = self._session
        if not session:
            return
        if self._tiempo_movimiento:
            self._populate_tecnico(annotations)

        puntos = catalogo.paquete(self._sport_id).reglamento.puntos
        _SCORE_QUALITY_ORDER, _ = self._calidad()
        zonas = _zonas_de(self._sport_id)
        zonas_aka: Counter = Counter()
        zonas_ao: Counter = Counter()
        por_puntuacion_aka: Counter = Counter()
        por_puntuacion_ao: Counter = Counter()


        total = len(annotations)
        aka_score = 0
        ao_score = 0
        fps = session.fps if session.fps > 0 else 30.0

        # ── Referee Stops INDIVIDUALES por atleta ──────────────────
        # Igual que en export_manager.py: cada atleta tiene su propio
        # tiempo de pausa. No se suman los RS de AKA y AO juntos.
        aka_ref_dur = sum(
            a.duration_s for a in annotations
            if a.category == "REFEREE STOP" and a.athlete == "AKA"
        )
        ao_ref_dur = sum(
            a.duration_s for a in annotations
            if a.category == "REFEREE STOP" and a.athlete == "AO"
        )
        max_time = session.duration_s if session.duration_s > 0 else 1.0

        # Tiempo activo individual por atleta
        aka_active_time = max(0.0, max_time - aka_ref_dur)
        ao_active_time = max(0.0, max_time - ao_ref_dur)

        # ── Buckets basados en tiempo activo (4 buckets: 3 min + Extra Time) ──
        # En Karate son 3 minutos de tiempo activo cronometrado + posible extra.
        # Para kickboxing se usan los rounds.
        if self._is_kb:
            num_buckets = max(1, int(max_time / 60) + 1)
        else:
            num_buckets = 3  # Min 1, Min 2, Min 3 (Atoshibaraku incluido en Min 3)
        aka_buckets = [0] * num_buckets
        ao_buckets = [0] * num_buckets
        if self._is_kb:
            bucket_labels = [f"R{i+1}" for i in range(num_buckets)]
        else:
            bucket_labels = [f"Min {i+1}" for i in range(num_buckets)]

        aka_attacks = 0
        ao_attacks = 0
        aka_scored = 0
        ao_scored = 0
        aka_techniques: list[str] = []
        ao_techniques: list[str] = []

        aka_score_quality: dict[str, int] = {k: 0 for k in _SCORE_QUALITY_ORDER}
        ao_score_quality: dict[str, int] = {k: 0 for k in _SCORE_QUALITY_ORDER}

        story_aka_points: list[tuple[float, int]] = [(0.0, 0)]
        story_ao_points: list[tuple[float, int]] = [(0.0, 0)]

        aka_first_time = ""
        ao_first_time = ""
        aka_tech_score: dict[str, int] = defaultdict(int)
        ao_tech_score: dict[str, int] = defaultdict(int)
        aka_streak = 0; ao_streak = 0
        current_streak = 0; current_ath = None
        scoring_events: list[tuple[float, str, int]] = []

        # ── Pre-calcular Active_Play_Cumulative_s para cada anotación ──
        # Misma lógica que export_manager.py: tiempo desde fight_start
        # restando solo los RS del mismo atleta que ya terminaron.
        fight_start = session.fight_start_frame if hasattr(session, 'fight_start_frame') and session.fight_start_frame else (annotations[0].f_start if annotations else 0)
        fight_start = fight_start or 0

        # Listas de RS por atleta ordenadas por f_start
        aka_rs_list = sorted(
            [a for a in annotations if a.category == "REFEREE STOP" and a.athlete == "AKA"],
            key=lambda x: x.f_start,
        )
        ao_rs_list = sorted(
            [a for a in annotations if a.category == "REFEREE STOP" and a.athlete == "AO"],
            key=lambda x: x.f_start,
        )

        for ann in annotations:
            sv = puntos(ann.score)
            if ann.athlete == "AKA":
                aka_score += sv
            elif ann.athlete == "AO":
                ao_score += sv

            # Calcular Active_Play_Cumulative_s para esta anotación
            elapsed = (ann.f_start - fight_start) / fps if fight_start > 0 else 0.0
            athlete_rs = aka_rs_list if ann.athlete == "AKA" else ao_rs_list
            stopped_before = sum(
                rs.duration_s for rs in athlete_rs if rs.f_end < ann.f_start
            )
            apc = max(0.0, elapsed - stopped_before)

            if ann.category == "REFEREE STOP":
                continue

            # Bucket basado en APC (tiempo activo acumulado), no en Match_Time_s
            bucket_idx = min(int(apc / 60), num_buckets - 1)
            if ann.athlete == "AKA":
                aka_buckets[bucket_idx] += 1
            elif ann.athlete == "AO":
                ao_buckets[bucket_idx] += 1

            # Usar APC como time_s para storyline y scoring events
            time_s = apc

            if ann.athlete == "AKA":
                # TKD: COUNTERATTACK counts as attack too
                if ann.category == "ATTACK" or (self._is_tkd and ann.category == "COUNTERATTACK"):
                    aka_attacks += 1
                    if sv > 0:
                        aka_scored += 1
                        story_aka_points.append((time_s, aka_score - sv))
                        story_aka_points.append((time_s, aka_score))
                        scoring_events.append((time_s, "AKA", sv))
                    if ann.technique:
                        aka_techniques.append(_technique_base_name(ann.technique))
                zona = _zona_de(ann.level, zonas)
                if zona in zonas:
                    zonas_aka[zona] += 1
                self._add_score_quality(aka_score_quality, ann.score)
                por_puntuacion_aka[ann.score] += 1
                if sv > 0 and ann.technique:
                    aka_tech_score[_technique_base_name(ann.technique)] += sv
            elif ann.athlete == "AO":
                # TKD: COUNTERATTACK counts as attack too
                if ann.category == "ATTACK" or (self._is_tkd and ann.category == "COUNTERATTACK"):
                    ao_attacks += 1
                    if sv > 0:
                        ao_scored += 1
                        story_ao_points.append((time_s, ao_score - sv))
                        story_ao_points.append((time_s, ao_score))
                        scoring_events.append((time_s, "AO", sv))
                    if ann.technique:
                        ao_techniques.append(_technique_base_name(ann.technique))
                zona = _zona_de(ann.level, zonas)
                if zona in zonas:
                    zonas_ao[zona] += 1
                self._add_score_quality(ao_score_quality, ann.score)
                por_puntuacion_ao[ann.score] += 1
                if sv > 0 and ann.technique:
                    ao_tech_score[_technique_base_name(ann.technique)] += sv


        # Time to first score
        for t, ath, sv in sorted(scoring_events, key=lambda x: x[0]):
            if ath == "AKA" and not aka_first_time:
                aka_first_time = self._format_duration_short(t)
            if ath == "AO" and not ao_first_time:
                ao_first_time = self._format_duration_short(t)

        # Streaks
        for _, ath, _ in scoring_events:
            if ath == current_ath:
                current_streak += 1
            else:
                if current_ath == "AKA": aka_streak = max(aka_streak, current_streak)
                elif current_ath == "AO": ao_streak = max(ao_streak, current_streak)
                current_ath = ath
                current_streak = 1
        if current_ath == "AKA": aka_streak = max(aka_streak, current_streak)
        elif current_ath == "AO": ao_streak = max(ao_streak, current_streak)

        # Tiempo activo combinado (usamos el mayor de los dos tiempos activos)
        active_time = max(aka_active_time, ao_active_time)
        active_min = active_time / 60.0 if active_time > 0 else 1.0

        aka_eff = (aka_scored / aka_attacks * 100) if aka_attacks > 0 else 0.0
        ao_eff = (ao_scored / ao_attacks * 100) if ao_attacks > 0 else 0.0

        aka_counter = Counter(aka_techniques)
        ao_counter = Counter(ao_techniques)
        aka_top = aka_counter.most_common(1)[0][0] if aka_counter else ""
        ao_top = ao_counter.most_common(1)[0][0] if ao_counter else ""

        def _porcentajes(cuenta: Counter) -> dict[str, float]:
            total = sum(cuenta[z] for z in zonas)
            return {z: (cuenta[z] / total * 100) if total > 0 else 0.0 for z in zonas}
        pct_zonas_aka = _porcentajes(zonas_aka)
        pct_zonas_ao = _porcentajes(zonas_ao)

        diff = abs(aka_score - ao_score)
        if aka_score > ao_score:
            winner_text = f"WINNER — {self._aka_name} ({catalogo.etiqueta('AKA')})"
            winner_color = _ACCENT_RED
        elif ao_score > aka_score:
            winner_text = f"WINNER — {self._ao_name} ({catalogo.etiqueta('AO')})"
            winner_color = _ACCENT_BLUE
        else:
            winner_text = "DRAW"
            winner_color = _TEXT_TERTIARY

        # ── Momentum Meter (Control Bar) ──
        total_score = aka_score + ao_score
        if total_score > 0:
            aka_control = (aka_score + aka_attacks * 0.3) / (total_score + (aka_attacks + ao_attacks) * 0.3)
        else:
            aka_control = 0.5
        aka_control = max(0.0, min(1.0, aka_control))
        control_pct = aka_control * 100
        if control_pct > 60:
            control_text = f"{self._aka_name} Control {control_pct:.0f}%"
            indicator_color = _ACCENT_RED
        elif control_pct < 40:
            control_text = f"{self._ao_name} Control {100 - control_pct:.0f}%"
            indicator_color = _ACCENT_BLUE
        else:
            control_text = "Neutral"
            indicator_color = _TEXT_TERTIARY
        self._momentum_lbl.setText(control_text)
        self._momentum_lbl.setStyleSheet(f"color:{indicator_color};font-size:12px;font-weight:600;background:transparent;border:none;")
        self._momentum_indicator.setStyleSheet(f"QFrame{{background:{indicator_color};border-radius:7px;}}")
        # Posicionar el indicador en la barra
        bar_width = self._momentum_bar.width() if self._momentum_bar.width() > 0 else 200
        indicator_pos = int(aka_control * bar_width) - 7
        indicator_pos = max(0, min(indicator_pos, bar_width - 14))
        self._momentum_indicator.move(indicator_pos, 0)

        # ── Coach Insights (Key Metrics) ──
        total_attacks = aka_attacks + ao_attacks
        attack_rate = total_attacks / active_min if active_min > 0 else 0
        total_eff = (aka_scored + ao_scored) / max(total_attacks, 1) * 100
        aka_defenses = len([a for a in annotations if a.athlete == "AKA" and a.category == "DEFENSE"])
        ao_defenses = len([a for a in annotations if a.athlete == "AO" and a.category == "DEFENSE"])
        def_ratio = (aka_defenses + ao_defenses) / max(total_attacks, 1)
        self._insight_attack_rate.set_value(f"{attack_rate:.1f}/min")
        self._insight_efficiency.set_value(f"{total_eff:.0f}%")
        self._insight_defense.set_value(f"{def_ratio:.2f}")

        # KPI cards (fila 1: totales)
        self._kpi_total.set_value(str(total))
        self._kpi_time.set_value(self._format_duration_short(active_time))
        self._kpi_score_aka.set_value(str(aka_score))
        self._kpi_score_ao.set_value(str(ao_score))
        
        # KPI cards (fila 2: tiempos INDIVIDUALES por atleta)
        self._kpi_aka_active.set_value(self._format_duration_short(aka_active_time))
        self._kpi_ao_active.set_value(self._format_duration_short(ao_active_time))
        self._kpi_aka_stopped.set_value(self._format_duration_short(aka_ref_dur))
        self._kpi_ao_stopped.set_value(self._format_duration_short(ao_ref_dur))

        # Executive View
        self._exec_winner.setText(winner_text)
        self._exec_winner.setStyleSheet(
            f"font-size:24px;font-weight:700;color:{winner_color};background:{_BG_CARD};border-radius:8px;padding:16px;"
        )
        self._exec_score_summary.setText(
            f"Final Score: {self._aka_name} ({catalogo.etiqueta('AKA')}) {aka_score} — "
            f"{ao_score} {self._ao_name} ({catalogo.etiqueta('AO')})  |  Difference: {diff} pts"
        )
        round_label = f"Round {self._active_round}" if self._active_round else "All Rounds"
        self._exec_insights["aka_eff_val"].setText(f"{round_label}\n{aka_score / max(aka_attacks, 1):.2f} pts/att")
        self._exec_insights["ao_eff_val"].setText(f"{round_label}\n{ao_score / max(ao_attacks, 1):.2f} pts/att")
        self._exec_insights["aka_rate_val"].setText(f"{aka_attacks / active_min:.1f}/min")
        self._exec_insights["ao_rate_val"].setText(f"{ao_attacks / active_min:.1f}/min")
        self._exec_insights["aka_first_val"].setText(aka_first_time or "—")
        self._exec_insights["ao_first_val"].setText(ao_first_time or "—")
        self._exec_insights["aka_streak_val"].setText(str(aka_streak))
        self._exec_insights["ao_streak_val"].setText(str(ao_streak))

        # Tactical View
        self._comparison_panel.set_sport_id(self._sport_id)
        self._comparison_panel.update_data(
            aka_attacks, ao_attacks, aka_eff, ao_eff,
            aka_top, ao_top, pct_zonas_aka, pct_zonas_ao,
        )
        # Una cuenta por puntuación del reglamento, con su nombre: las que
        # puntúan (IPPON, WAZA-ARI, YUKO en el karate) o, si solo puntúa
        # una («Scored», «Landed»), todas.
        reparto = catalogo.paquete(self._sport_id).reglamento.puntuaciones
        filas = [p for p in reparto if p.puntos > 0]
        if len(filas) < 2:
            filas = list(reparto)
        self._scoring_breakdown_lbl.setText("  |  ".join(
            f"{p.nombre}: {self._aka_name} {por_puntuacion_aka[p.codigo]} — "
            f"{por_puntuacion_ao[p.codigo]} {self._ao_name}"
            for p in filas))
        aka_best = max(aka_tech_score, key=aka_tech_score.get) if aka_tech_score else "—"
        ao_best = max(ao_tech_score, key=ao_tech_score.get) if ao_tech_score else "—"
        self._best_tech_lbl.setText(
            f"Most Effective Technique (by score): {self._aka_name} — {aka_best}  |  {self._ao_name} — {ao_best}"
        )

        # Rhythm View — RS separados por atleta
        self._populate_fatigue_chart(self._rhythm_aka_fatigue, aka_buckets, bucket_labels)
        self._populate_fatigue_chart(self._rhythm_ao_fatigue, ao_buckets, bucket_labels)
        aka_ref_count = len([a for a in annotations if a.category == "REFEREE STOP" and a.athlete == "AKA"])
        ao_ref_count = len([a for a in annotations if a.category == "REFEREE STOP" and a.athlete == "AO"])
        self._rhythm_metrics_lbl.setText(
            f"Time to First Score: {self._aka_name} {aka_first_time or '—'}  |  "
            f"{self._ao_name} {ao_first_time or '—'}    "
            f"Referee Stops — {self._aka_name}: {aka_ref_count} ({aka_ref_dur:.1f}s)  |  "
            f"{self._ao_name}: {ao_ref_count} ({ao_ref_dur:.1f}s)"
        )

        # Charts
        self._populate_donut(self._aka_donut, aka_score_quality)
        self._populate_donut(self._ao_donut, ao_score_quality)
        self._populate_storyline(story_aka_points, story_ao_points, max_time)

        # Deep Analysis
        self._populate_deep_analysis(annotations, self._aka_name, self._ao_name)

    # ------------------------------------------------------------------
    # Chart population helpers
    # ------------------------------------------------------------------

    def _populate_storyline(self, aka_points, ao_points, max_time):
        self._story_aka.clear()
        self._story_ao.clear()
        for t, s in aka_points:
            self._story_aka.append(t, s)
        for t, s in ao_points:
            self._story_ao.append(t, s)
        chart = self._storyline_chart.chart()
        for axis in list(chart.axes()):
            if axis.orientation() == Qt.Horizontal:
                chart.removeAxis(axis)
        max_score = 0
        for _, s in aka_points + ao_points:
            if s > max_score: max_score = s
        for ax in chart.axes():
            if ax.orientation() == Qt.Vertical:
                ax.setRange(0, max_score + 1)
        
        # ✅ BUG 2 FIX: Calcular tiempo activo real (sin paradas)
        # Obtener el máximo tiempo de los puntos reales
        max_active_time = max((t for t, _ in aka_points + ao_points), default=max_time)
        # Redondear al minuto superior para el eje, máximo 3 minutos para Karate
        max_active_time = min(max_active_time, 180)
        
        ax_x = QCategoryAxis()
        ax_x.setTitleText("Time")
        ax_x.setRange(0, max_active_time)
        ax_x.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
        ax_x.setLabelsColor(QColor(_TEXT_MUTED))
        ax_x.setTitleBrush(QColor(_TEXT_MUTED))
        ax_x.setLinePenColor(QColor(_TEXT_MUTED))
        ax_x.setGridLineVisible(False)
        tick_interval = 60
        num_ticks = int(max_active_time / tick_interval) + 1
        for i in range(num_ticks):
            t_val = i * tick_interval
            if t_val <= max_active_time:
                ax_x.append(self._format_duration_short(t_val), t_val)
        chart.addAxis(ax_x, Qt.AlignBottom)
        self._story_aka.attachAxis(ax_x)
        self._story_ao.attachAxis(ax_x)

    def _populate_fatigue_chart(self, chart_view, buckets, labels):
        chart = chart_view.chart()
        for s in list(chart.series()):
            chart.removeSeries(s)
        bar_set = QBarSet("Attacks")
        bar_set.setColor(QColor(_ACCENT_RED) if chart_view is self._rhythm_aka_fatigue else QColor(_ACCENT_BLUE))
        bar_set.setBorderColor(bar_set.color())
        for v in buckets:
            bar_set.append(v)
        series = QBarSeries()
        series.append(bar_set)
        chart.addSeries(series)
        for ax in list(chart.axes()):
            chart.removeAxis(ax)
        ax_y = QValueAxis()
        max_val = max(buckets) if buckets else 5
        ax_y.setRange(0, max_val + 1 if max_val > 0 else 5)
        ax_y.setLabelFormat("%d")
        ax_y.setLabelsColor(QColor(_TEXT_TERTIARY))
        ax_y.setTitleBrush(QColor(_TEXT_TERTIARY))
        ax_y.setGridLineVisible(False)
        chart.addAxis(ax_y, Qt.AlignLeft)
        series.attachAxis(ax_y)
        ax_x = QBarCategoryAxis()
        ax_x.append(labels)
        ax_x.setLabelsColor(QColor(_TEXT_TERTIARY))
        ax_x.setGridLineVisible(False)
        chart.addAxis(ax_x, Qt.AlignBottom)
        series.attachAxis(ax_x)

    def _calidad(self) -> tuple[list[str], dict[str, QColor]]:
        """Orden y colores del reparto de puntuaciones de este deporte."""
        if self._sport_id == "taekwondo":
            return _SCORE_QUALITY_ORDER_TKD, _SCORE_QUALITY_COLORS_TKD
        if self._sport_id == "karate":
            return _SCORE_QUALITY_ORDER_KARATE, _SCORE_QUALITY_COLORS_KARATE
        return _calidad_por_reglamento(self._sport_id)

    def _add_score_quality(self, quality: dict[str, int], score: str) -> None:
        sport_id = self._sport_meta.get("id", "karate")
        if sport_id == "taekwondo":
            if score == "6_PTS": quality["6 PTS (Turn→Head)"] += 1
            elif score == "4_PTS": quality["4 PTS (Turn→Trunk)"] += 1
            elif score == "3_PTS": quality["3 PTS (Kick→Head)"] += 1
            elif score == "2_PTS": quality["2 PTS (Kick→Trunk)"] += 1
            elif score == "1_PT": quality["1 PT  (Punch→Trunk)"] += 1
            else: quality["NO POINT"] += 1
        elif sport_id != "karate":
            nombres = {p.codigo: p.nombre for p in
                       catalogo.paquete(sport_id).reglamento.puntuaciones}
            if nombres.get(score) in quality:
                quality[nombres[score]] += 1
        else:
            if score == "IPPON": quality["IPPON (3)"] += 1
            elif score == "WAZA": quality["WAZA-ARI (2)"] += 1
            elif score == "YUKO": quality["YUKO (1)"] += 1
            else: quality["NO SCORE"] += 1


    def _populate_donut(self, donut_view, score_quality):
        _sc_order, _sc_colors = self._calidad()

        pie_series = QPieSeries()
        pie_series.setHoleSize(0.55)
        for key in _sc_order:
            count = score_quality.get(key, 0)
            if count > 0:
                # ✅ BUG 3 FIX: Usar ":" en lugar de "()" para evitar concatenación
                sl = pie_series.append(f"{key}: {count}", count)
                sl.setColor(_sc_colors[key])
                sl.setLabelVisible(False)
        if pie_series.count() == 0:
            sl = pie_series.append("No Data", 1)
            sl.setColor(QColor(_BG_CARD))
            sl.setLabelVisible(False)
        old_chart = donut_view.chart()
        new_chart = QChart()
        new_chart.addSeries(pie_series)
        new_chart.setBackgroundBrush(Qt.GlobalColor.transparent)
        new_chart.setTitle("")
        new_chart.setMargins(QMargins(0, 0, 0, 0))
        new_chart.layout().setContentsMargins(0, 0, 0, 0)
        new_chart.legend().setVisible(True)
        new_chart.legend().setAlignment(Qt.AlignBottom)
        new_chart.legend().setLabelColor(QColor(_TEXT_SECONDARY))
        new_chart.legend().setFont(QFont("Inter", 10))
        new_chart.legend().setMinimumHeight(30)
        donut_view.setChart(new_chart)
        old_chart.deleteLater()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_duration_short(seconds: float) -> str:
        if seconds < 0: return "00:00"
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m:02d}:{s:02d}"

    @staticmethod
    def _update_kpi_value(kpi_widget: QFrame, value: str) -> None:
        layout = kpi_widget.layout()
        if layout and layout.count() > 0:
            lbl = layout.itemAt(0).widget()
            if isinstance(lbl, QLabel):
                lbl.setText(value)