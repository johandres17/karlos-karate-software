"""Professional PDF Report Generator for KARLOS ANNOTATOR.

Elite-level combat sports analysis reports with:
- Premium hybrid design (sports + scientific)
- Vector graphics and professional typography
- Advanced data visualization
- Multi-page layouts with consistent branding
"""

from __future__ import annotations

import io
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image, KeepTogether, Frame, PageTemplate
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF

from karlos_core import catalogo


def _programa() -> tuple[str, str]:
    """El nombre (en mayúsculas) y la versión de la edición en marcha.

    Hasta la 1.0 ponía «KARLOS ANNOTATOR v6.0» escrito a mano (decisión 0006).
    """
    from karlos_core import identidad
    edicion = identidad.en_marcha()
    return edicion.nombre.upper(), edicion.version


# ══════════════════════════════════════════════════════════════════
# BRAND COLORS — Hybrid Sports/Scientific Palette
# ══════════════════════════════════════════════════════════════════

class BrandColors:
    """Professional color palette for combat sports analysis."""
    
    # Primary Brand
    KARLOS_GOLD = colors.HexColor("#D5A021")
    KARLOS_DARK = colors.HexColor("#0B0D10")
    KARLOS_SLATE = colors.HexColor("#1C2128")
    
    # Athlete Colors (High Contrast)
    AKA_RED = colors.HexColor("#E5534B")
    AO_BLUE = colors.HexColor("#4384E6")
    
    # Data Visualization
    SUCCESS_GREEN = colors.HexColor("#2B9E66")
    WARNING_ORANGE = colors.HexColor("#F58732")
    NEUTRAL_GRAY = colors.HexColor("#8892A0")
    
    # Backgrounds
    BG_LIGHT = colors.HexColor("#FAFAFA")
    BG_PANEL = colors.HexColor("#FFFFFF")
    BORDER_LIGHT = colors.HexColor("#E0E4E8")
    
    # Text
    TEXT_PRIMARY = colors.HexColor("#1A1A1A")
    TEXT_SECONDARY = colors.HexColor("#555555")
    TEXT_MUTED = colors.HexColor("#888888")


# ══════════════════════════════════════════════════════════════════
# TYPOGRAPHY SYSTEM
# ══════════════════════════════════════════════════════════════════

def create_styles() -> dict[str, ParagraphStyle]:
    """Create professional typography system."""
    styles = getSampleStyleSheet()
    
    custom_styles = {
        'Title': ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=32,
            textColor=BrandColors.KARLOS_GOLD,
            spaceAfter=6,
            fontName='Helvetica-Bold',
            leading=38,
            letterSpacing=2,
        ),
        'Subtitle': ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=14,
            textColor=BrandColors.TEXT_SECONDARY,
            spaceAfter=20,
            fontName='Helvetica',
        ),
        'SectionHeader': ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=18,
            textColor=BrandColors.KARLOS_DARK,
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderPadding=0,
            leftIndent=0,
            borderColor=BrandColors.KARLOS_GOLD,
        ),
        'Body': ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            textColor=BrandColors.TEXT_PRIMARY,
            spaceAfter=8,
            fontName='Helvetica',
            leading=14,
        ),
        'Caption': ParagraphStyle(
            'Caption',
            parent=styles['Normal'],
            fontSize=9,
            textColor=BrandColors.TEXT_MUTED,
            spaceAfter=4,
            fontName='Helvetica',
        ),
        'MetricLabel': ParagraphStyle(
            'MetricLabel',
            parent=styles['Normal'],
            fontSize=9,
            textColor=BrandColors.TEXT_SECONDARY,
            fontName='Helvetica',
            alignment=1,  # Center
        ),
        'MetricValue': ParagraphStyle(
            'MetricValue',
            parent=styles['Normal'],
            fontSize=28,
            textColor=BrandColors.TEXT_PRIMARY,
            fontName='Helvetica-Bold',
            alignment=1,  # Center
        ),
    }
    
    return custom_styles


# ══════════════════════════════════════════════════════════════════
# PROFESSIONAL PDF REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════

def _fases(sport_id: str) -> tuple[list[str], list[str], list[str]]:
    """Las fases del combate (clave, rótulo, rótulo corto) de un deporte.

    En el karate, los minutos y el Atoshibaraku, como siempre; en los
    demás, sus asaltos y lo que pase del último (decisión 0007).
    """
    if sport_id == "karate":
        return (["Minute_1", "Minute_2", "Minute_3", "Atoshibaraku"],
                ["Minute 1", "Minute 2", "Minute 3", "Atoshibaraku"],
                ["Min 1", "Min 2", "Min 3", "Atoshi"])
    asaltos = int(catalogo.paquete(sport_id).configuracion()["rules"]["rounds"])
    claves = [f"Round_{i}" for i in range(1, asaltos + 2)]
    return (claves, [f"Round {i}" for i in range(1, asaltos + 1)] + ["Extra"],
            [f"R{i}" for i in range(1, asaltos + 1)] + ["Extra"])


def _reparto(sport_id: str, aka_attacks: list, ao_attacks: list, karate: tuple) -> list:
    """Las filas del desglose de puntuaciones: (rótulo, AKA, AO).

    En el karate, IPPON, WAZA y YUKO como siempre (``karate`` trae sus
    cuentas); en los demás, las puntuaciones de su reglamento con su
    nombre: las que puntúan o, si solo puntúa una, todas.
    """
    if sport_id == "karate":
        return karate
    reparto = catalogo.paquete(sport_id).reglamento.puntuaciones
    filas = [p for p in reparto if p.puntos > 0]
    if len(filas) < 2:
        filas = list(reparto)
    return [(p.nombre, sum(1 for a in aka_attacks if a.score == p.codigo),
             sum(1 for a in ao_attacks if a.score == p.codigo)) for p in filas]


class ProfessionalReportGenerator:
    """Generate elite-level PDF reports for combat sports analysis."""
    
    def __init__(self, output_path: str | Path):
        """Initialize the report generator.
        
        Args:
            output_path: Path where the PDF will be saved.
        """
        self.output_path = Path(output_path)
        self.styles = create_styles()
        self.story = []
        self.page_width, self.page_height = landscape(A4)
        
    def generate_report(
        self,
        bout_metadata: dict[str, Any],
        annotations: list,
        session_data: dict[str, Any],
        sport_id: str = "karate",
    ) -> str:
        """Generate the complete professional report.
        
        Args:
            bout_metadata: Bout information (athletes, event, etc.)
            annotations: List of annotation objects
            session_data: Session metrics and statistics
            sport_id: Sport identifier ("karate" or "kickboxing")
            
        Returns:
            Path to the generated PDF file.
        """
        # Build document
        doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=landscape(A4),
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=15*mm,
        )
        
        # Calculate metrics
        metrics = self._calculate_metrics(annotations, session_data, sport_id)
        
        # Build story
        self._add_cover_page(bout_metadata, metrics)
        self.story.append(PageBreak())
        
        self._add_executive_summary(bout_metadata, metrics)
        self.story.append(PageBreak())
        
        self._add_tactical_analysis(bout_metadata, metrics, sport_id)
        self.story.append(PageBreak())
        
        self._add_performance_charts(bout_metadata, metrics, sport_id)
        
        # Build PDF
        doc.build(self.story, onFirstPage=self._add_header_footer, onLaterPages=self._add_header_footer)
        
        return str(self.output_path)
    
    def _calculate_metrics(self, annotations: list, session_data: dict, sport_id: str) -> dict:
        """Calculate all metrics for the report.

        Reads from the hierarchical taxonomy (sport_specific_data dict) for
        subcategory, level, stance, and action_type — the v6.1 standard.
        Falls back to direct attribute access for backward compatibility.
        """
        is_kb = sport_id == "kickboxing"
        is_tkd = sport_id == "taekwondo"

        # Helper: read from sport_specific_data or fallback to attribute
        def _ssd(ann, key: str, default=None):
            """Read a value from sport_specific_data dict or direct attribute."""
            ssd = getattr(ann, 'sport_specific_data', None) or {}
            if isinstance(ssd, dict) and key in ssd:
                return ssd[key]
            # Fallback to direct attribute
            return getattr(ann, key, default)

        # Split by athlete
        aka_anns = [a for a in annotations if a.athlete == "AKA"]
        ao_anns = [a for a in annotations if a.athlete == "AO"]

        # TKD: COUNTERATTACK counts as attack too
        attack_cats = {"ATTACK"}
        if is_tkd:
            attack_cats.add("COUNTERATTACK")

        aka_attacks = [a for a in aka_anns if a.category in attack_cats]
        ao_attacks = [a for a in ao_anns if a.category in attack_cats]

        # Score calculation with detailed breakdown. Lo que vale cada código
        # lo dice el deporte (decisión 0004); «puntúa» es valer algo.
        puntos = catalogo.paquete(sport_id).reglamento.puntos

        def puntua(a) -> bool:
            return puntos(a.score) > 0

        if is_kb:
            aka_score = sum(1 for a in aka_attacks if puntua(a))
            ao_score = sum(1 for a in ao_attacks if puntua(a))
            aka_effectiveness = (aka_score / len(aka_attacks) * 100) if aka_attacks else 0.0
            ao_effectiveness = (ao_score / len(ao_attacks) * 100) if ao_attacks else 0.0
            aka_ippon = aka_waza = aka_yuko = 0
            ao_ippon = ao_waza = ao_yuko = 0
            aka_connected = aka_score
            ao_connected = ao_score
        else:
            aka_score = sum(puntos(a.score) for a in aka_attacks)
            ao_score = sum(puntos(a.score) for a in ao_attacks)
            aka_scored = sum(1 for a in aka_attacks if puntua(a))
            ao_scored = sum(1 for a in ao_attacks if puntua(a))
            aka_effectiveness = (aka_scored / len(aka_attacks) * 100) if aka_attacks else 0.0
            ao_effectiveness = (ao_scored / len(ao_attacks) * 100) if ao_attacks else 0.0
            if is_tkd:
                aka_ippon = aka_waza = aka_yuko = 0
                ao_ippon = ao_waza = ao_yuko = 0
            else:
                aka_ippon = sum(1 for a in aka_attacks if a.score == "IPPON")
                aka_waza = sum(1 for a in aka_attacks if a.score == "WAZA")
                aka_yuko = sum(1 for a in aka_attacks if a.score == "YUKO")
                ao_ippon = sum(1 for a in ao_attacks if a.score == "IPPON")
                ao_waza = sum(1 for a in ao_attacks if a.score == "WAZA")
                ao_yuko = sum(1 for a in ao_attacks if a.score == "YUKO")
            aka_connected = ao_connected = 0

        # Active time — INDIVIDUAL por atleta
        ref_stops = [a for a in annotations if a.category == "REFEREE STOP"]
        total_stopped = sum(a.duration_s for a in ref_stops)
        fight_duration = session_data.get("duration_s", 0.0)
        active_time = max(0.0, fight_duration - total_stopped)
        
        # Tiempos INDIVIDUALES por atleta (AKA vs AO)
        aka_ref_stops = [a for a in ref_stops if a.athlete == "AKA"]
        ao_ref_stops = [a for a in ref_stops if a.athlete == "AO"]
        aka_stopped_time = sum(a.duration_s for a in aka_ref_stops)
        ao_stopped_time = sum(a.duration_s for a in ao_ref_stops)
        aka_active_time = max(0.0, fight_duration - aka_stopped_time)
        ao_active_time = max(0.0, fight_duration - ao_stopped_time)
        aka_ref_stops_count = len(aka_ref_stops)
        ao_ref_stops_count = len(ao_ref_stops)

        # Technical diversity
        aka_techs = Counter(a.technique for a in aka_attacks if a.technique)
        ao_techs = Counter(a.technique for a in ao_attacks if a.technique)

        aka_top_tech = aka_techs.most_common(1)[0][0] if aka_techs else "—"
        ao_top_tech = ao_techs.most_common(1)[0][0] if ao_techs else "—"

        def calc_entropy(counter):
            if not counter:
                return 0.0
            total = sum(counter.values())
            entropy = 0.0
            for count in counter.values():
                p = count / total
                entropy -= p * math.log(p)
            return round(entropy, 3)

        aka_entropy = calc_entropy(aka_techs)
        ao_entropy = calc_entropy(ao_techs)

        # ═══ HIERARCHICAL TAXONOMY METRICS (v6.1) ═══

        # Technique type breakdown (subcategory from sport_specific_data)
        def _subcat_count(attacks, subcat):
            return sum(1 for a in attacks if _ssd(a, 'subcategory') == subcat)

        aka_hand = _subcat_count(aka_attacks, "HAND TECHNIQUES")
        aka_foot = _subcat_count(aka_attacks, "FOOT TECHNIQUES")
        ao_hand = _subcat_count(ao_attacks, "HAND TECHNIQUES")
        ao_foot = _subcat_count(ao_attacks, "FOOT TECHNIQUES")

        # Sweeps from DEFENSE category
        aka_sweeps = sum(
            1 for a in aka_anns
            if a.category == "DEFENSE" and _ssd(a, 'subcategory') == "SWEEPS & TAKEDOWNS"
        )
        ao_sweeps = sum(
            1 for a in ao_anns
            if a.category == "DEFENSE" and _ssd(a, 'subcategory') == "SWEEPS & TAKEDOWNS"
        )

        # Target level analysis (from sport_specific_data or direct .level)
        def _level_count(attacks, level):
            return sum(1 for a in attacks if _ssd(a, 'level') == level)

        def _level_scored(attacks, level):
            return sum(
                1 for a in attacks
                if _ssd(a, 'level') == level and puntua(a)
            )

        # Karate levels
        aka_jodan = _level_count(aka_attacks, "Jodan")
        aka_chudan = _level_count(aka_attacks, "Chudan")
        aka_jodan_scored = _level_scored(aka_attacks, "Jodan")
        aka_chudan_scored = _level_scored(aka_attacks, "Chudan")

        ao_jodan = _level_count(ao_attacks, "Jodan")
        ao_chudan = _level_count(ao_attacks, "Chudan")
        ao_jodan_scored = _level_scored(ao_attacks, "Jodan")
        ao_chudan_scored = _level_scored(ao_attacks, "Chudan")

        # Kickboxing: las tres zonas de su configuración (cabeza, tronco y
        # piernas en K1 Style, decisión 0007), de la «Target» o del nivel.
        # Fuera del kickboxing se quedan los rótulos de la 1.0: el PDF del
        # karate enseña esta tabla a ceros (_is_kickboxing mira si existen
        # las claves, y existen siempre) y tiene que salir igual.
        zonas_kb = (list(catalogo.paquete(sport_id).configuracion().get("levels", []))[:3]
                    if is_kb else ["High", "Middle", "Low"])
        zonas_kb += [""] * (3 - len(zonas_kb))

        def _kb_zona(a):
            return _ssd(a, 'target') or getattr(a, 'level', '')

        def _kb_target_count(attacks, target):
            return sum(1 for a in attacks if target and _kb_zona(a) == target)

        def _kb_target_scored(attacks, target):
            return sum(
                1 for a in attacks
                if target and _kb_zona(a) == target and puntua(a)
            )

        z_cabeza, z_tronco, z_piernas = zonas_kb
        aka_high = _kb_target_count(aka_attacks, z_cabeza)
        aka_mid = _kb_target_count(aka_attacks, z_tronco)
        aka_low = _kb_target_count(aka_attacks, z_piernas)
        aka_high_scored = _kb_target_scored(aka_attacks, z_cabeza)
        aka_mid_scored = _kb_target_scored(aka_attacks, z_tronco)
        aka_low_scored = _kb_target_scored(aka_attacks, z_piernas)

        ao_high = _kb_target_count(ao_attacks, z_cabeza)
        ao_mid = _kb_target_count(ao_attacks, z_tronco)
        ao_low = _kb_target_count(ao_attacks, z_piernas)
        ao_high_scored = _kb_target_scored(ao_attacks, z_cabeza)
        ao_mid_scored = _kb_target_scored(ao_attacks, z_tronco)
        ao_low_scored = _kb_target_scored(ao_attacks, z_piernas)

        # Tactical actions
        aka_tactics = [a for a in aka_anns if a.category == "TACTICS"]
        ao_tactics = [a for a in ao_anns if a.category == "TACTICS"]
        aka_feints = sum(1 for a in aka_tactics if a.technique == "Feint")
        aka_clinches = sum(1 for a in aka_tactics if a.technique == "Clinch")
        ao_feints = sum(1 for a in ao_tactics if a.technique == "Feint")
        ao_clinches = sum(1 for a in ao_tactics if a.technique == "Clinch")

        # Defensive actions
        aka_defense = [a for a in aka_anns if a.category == "DEFENSE"]
        ao_defense = [a for a in ao_anns if a.category == "DEFENSE"]

        # Temporal analysis (Phase from sport_specific_data or direct attribute)
        phases, _, _ = _fases(sport_id)
        aka_by_phase = {}
        ao_by_phase = {}
        aka_score_by_phase = {}
        ao_score_by_phase = {}

        for phase in phases:
            aka_phase_attacks = [a for a in aka_attacks if _ssd(a, 'Phase') == phase or _ssd(a, 'phase') == phase]
            ao_phase_attacks = [a for a in ao_attacks if _ssd(a, 'Phase') == phase or _ssd(a, 'phase') == phase]
            aka_by_phase[phase] = len(aka_phase_attacks)
            ao_by_phase[phase] = len(ao_phase_attacks)
            aka_score_by_phase[phase] = sum(puntos(a.score) for a in aka_phase_attacks)
            ao_score_by_phase[phase] = sum(puntos(a.score) for a in ao_phase_attacks)

        # ═══ STANCE ANALYSIS (Combinatorial Engine v6.1) ═══
        def _stance_profile(attacks):
            stances = Counter(
                _ssd(a, 'stance', '')
                for a in attacks
            )
            lead = stances.get("Lead", 0)
            rear = stances.get("Rear", 0)
            total = lead + rear
            return {
                "lead": lead,
                "rear": rear,
                "total": total,
                "lead_pct": round(lead / total * 100, 1) if total else 0.0,
                "rear_pct": round(rear / total * 100, 1) if total else 0.0,
            }

        aka_stance = _stance_profile(aka_attacks)
        ao_stance = _stance_profile(ao_attacks)

        # ═══ ACTION-TYPE ANALYSIS (WKF literature) ═══
        def _action_type_profile(attacks):
            typed = [a for a in attacks if _ssd(a, 'action_type')]
            total = len(typed)
            result = {}
            for action in ("Direct", "Counter", "Anticipation", "Combination"):
                subset = [a for a in typed if _ssd(a, 'action_type') == action]
                count = len(subset)
                scored = sum(1 for a in subset if puntua(a))
                result[action] = {
                    "count": count,
                    "pct": round(count / total * 100, 1) if total else 0.0,
                    "eff_pct": round(scored / count * 100, 1) if count else 0.0,
                }
            return result

        aka_actions = _action_type_profile(aka_attacks)
        ao_actions = _action_type_profile(ao_attacks)

        return {
            # Basic metrics
            "aka_score": aka_score,
            "ao_score": ao_score,
            "aka_attacks": len(aka_attacks),
            "ao_attacks": len(ao_attacks),
            "aka_effectiveness": aka_effectiveness,
            "ao_effectiveness": ao_effectiveness,
            "aka_top_tech": aka_top_tech,
            "ao_top_tech": ao_top_tech,
            "aka_unique_techs": len(aka_techs),
            "ao_unique_techs": len(ao_techs),
            "aka_entropy": aka_entropy,
            "ao_entropy": ao_entropy,
            "total_annotations": len(annotations),
            "active_time_s": active_time,
            "ref_stops_count": len(ref_stops),
            "ref_stops_duration": total_stopped,
            "fight_duration": fight_duration,
            
            # Tiempos INDIVIDUALES por atleta
            "aka_active_time_s": aka_active_time,
            "ao_active_time_s": ao_active_time,
            "aka_stopped_time_s": aka_stopped_time,
            "ao_stopped_time_s": ao_stopped_time,
            "aka_ref_stops_count": aka_ref_stops_count,
            "ao_ref_stops_count": ao_ref_stops_count,

            # Scoring breakdown
            "aka_ippon": aka_ippon,
            "aka_waza": aka_waza,
            "aka_yuko": aka_yuko,
            "ao_ippon": ao_ippon,
            "ao_waza": ao_waza,
            "ao_yuko": ao_yuko,
            "aka_connected": aka_connected,
            "ao_connected": ao_connected,

            # Technique type breakdown
            "aka_hand": aka_hand,
            "aka_foot": aka_foot,
            "aka_sweeps": aka_sweeps,
            "ao_hand": ao_hand,
            "ao_foot": ao_foot,
            "ao_sweeps": ao_sweeps,

            # Target level analysis
            "aka_jodan": aka_jodan,
            "aka_chudan": aka_chudan,
            "aka_jodan_scored": aka_jodan_scored,
            "aka_chudan_scored": aka_chudan_scored,
            "ao_jodan": ao_jodan,
            "ao_chudan": ao_chudan,
            "ao_jodan_scored": ao_jodan_scored,
            "ao_chudan_scored": ao_chudan_scored,

            # Tactical actions
            "aka_tactics_total": len(aka_tactics),
            "ao_tactics_total": len(ao_tactics),
            "aka_feints": aka_feints,
            "aka_clinches": aka_clinches,
            "ao_feints": ao_feints,
            "ao_clinches": ao_clinches,

            # Defensive actions
            "aka_defense": len(aka_defense),
            "ao_defense": len(ao_defense),

            # Temporal analysis
            "aka_by_phase": aka_by_phase,
            "fases": _fases(sport_id),
            "reparto": _reparto(sport_id, aka_attacks, ao_attacks, [
                ("IPPON (3)", aka_ippon, ao_ippon), ("WAZA (2)", aka_waza, ao_waza),
                ("YUKO (1)", aka_yuko, ao_yuko)]),
            "ao_by_phase": ao_by_phase,
            "aka_score_by_phase": aka_score_by_phase,
            "ao_score_by_phase": ao_score_by_phase,

            # ═══ KICKBOXING TARGET ZONE METRICS ═══
            "zonas_kb": zonas_kb,
            "aka_high": aka_high,
            "aka_mid": aka_mid,
            "aka_low": aka_low,
            "aka_high_scored": aka_high_scored,
            "aka_mid_scored": aka_mid_scored,
            "aka_low_scored": aka_low_scored,
            "ao_high": ao_high,
            "ao_mid": ao_mid,
            "ao_low": ao_low,
            "ao_high_scored": ao_high_scored,
            "ao_mid_scored": ao_mid_scored,
            "ao_low_scored": ao_low_scored,

            # ═══ NEW v6.1 METRICS ═══
            # Stance Analysis (Combinatorial Engine)
            "aka_stance": aka_stance,
            "ao_stance": ao_stance,

            # Action-Type Analysis (WKF literature)
            "aka_actions": aka_actions,
            "ao_actions": ao_actions,
        }
    
    def _add_cover_page(self, metadata: dict, metrics: dict):
        """Add professional cover page."""
        # Header bar with branding
        header_drawing = Drawing(self.page_width - 30*mm, 60)
        header_drawing.add(Rect(0, 0, self.page_width - 30*mm, 60, 
                                fillColor=BrandColors.KARLOS_DARK, strokeColor=None))
        header_drawing.add(String(20, 35, _programa()[0], 
                                  fontSize=28, fillColor=BrandColors.KARLOS_GOLD, 
                                  fontName="Helvetica-Bold"))
        header_drawing.add(String(20, 15, "PROFESSIONAL COMBAT ANALYSIS REPORT", 
                                  fontSize=12, fillColor=colors.white, 
                                  fontName="Helvetica"))
        self.story.append(header_drawing)
        self.story.append(Spacer(1, 20))
        
        # Event information
        event = metadata.get("competition_name", "—")
        weight = metadata.get("weight_category", "—")
        
        event_text = f"<b>{event}</b> • {weight}"
        self.story.append(Paragraph(event_text, self.styles['Subtitle']))
        self.story.append(Spacer(1, 30))
        
        # Fighter matchup (large and prominent)
        aka_name = metadata.get("athlete_a_name", catalogo.etiqueta("AKA"))
        ao_name = metadata.get("athlete_b_name", catalogo.etiqueta("AO"))
        
        matchup_text = f'<font color="#E5534B" size="24"><b>{aka_name}</b></font> <font size="20">vs</font> <font color="#4384E6" size="24"><b>{ao_name}</b></font>'
        matchup_style = ParagraphStyle(
            'Matchup',
            parent=self.styles['Title'],
            fontSize=24,
            alignment=1,  # Center
            spaceAfter=40,
        )
        self.story.append(Paragraph(matchup_text, matchup_style))
        
        # Winner banner
        aka_score = metrics["aka_score"]
        ao_score = metrics["ao_score"]
        
        if aka_score > ao_score:
            winner_text = f'<font color="#E5534B"><b>WINNER — {aka_name}</b></font>'
            winner_color = BrandColors.AKA_RED
        elif ao_score > aka_score:
            winner_text = f'<font color="#4384E6"><b>WINNER — {ao_name}</b></font>'
            winner_color = BrandColors.AO_BLUE
        else:
            winner_text = '<font color="#888888"><b>DRAW</b></font>'
            winner_color = BrandColors.NEUTRAL_GRAY
        
        winner_style = ParagraphStyle(
            'Winner',
            parent=self.styles['Title'],
            fontSize=32,
            alignment=1,
            spaceAfter=10,
        )
        self.story.append(Paragraph(winner_text, winner_style))
        
        # Final score
        score_text = f'<font size="18">Final Score: <b>{aka_score}</b> — <b>{ao_score}</b></font>'
        score_style = ParagraphStyle('Score', parent=self.styles['Body'], fontSize=18, alignment=1)
        self.story.append(Paragraph(score_text, score_style))
        self.story.append(Spacer(1, 40))
        
        # Key metrics grid (6 KPIs) — incluye tiempos INDIVIDUALES por atleta
        kpi_data = [
            [self._create_kpi_cell(str(metrics["total_annotations"]), "TOTAL\nANNOTATIONS"),
             self._create_kpi_cell(self._format_time(metrics["active_time_s"]), "ACTIVE\nFIGHT TIME"),
             self._create_kpi_cell(f"{metrics['aka_effectiveness']:.0f}%", f"{aka_name}\nEFFECTIVENESS"),
             self._create_kpi_cell(f"{metrics['ao_effectiveness']:.0f}%", f"{ao_name}\nEFFECTIVENESS")],
            [self._create_kpi_cell(self._format_time(metrics["aka_active_time_s"]), f"{aka_name}\nACTIVE TIME"),
             self._create_kpi_cell(self._format_time(metrics["ao_active_time_s"]), f"{ao_name}\nACTIVE TIME"),
             self._create_kpi_cell(self._format_time(metrics["aka_stopped_time_s"]), f"{aka_name}\nSTOPPED TIME"),
             self._create_kpi_cell(self._format_time(metrics["ao_stopped_time_s"]), f"{ao_name}\nSTOPPED TIME")],
        ]
        
        kpi_table = Table(kpi_data, colWidths=[160, 160, 160, 160])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), BrandColors.BG_LIGHT),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, BrandColors.BORDER_LIGHT),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        self.story.append(kpi_table)
        self.story.append(Spacer(1, 30))
        
        # Footer metadata
        evaluator = metadata.get("evaluator_name", "—")
        institution = metadata.get("evaluator_institution", "—")
        date_str = datetime.now().strftime("%d %B %Y — %H:%M")
        
        footer_text = f'<font size="10" color="#888888">Evaluator: {evaluator} ({institution}) • Generated: {date_str}</font>'
        footer_style = ParagraphStyle('Footer', parent=self.styles['Caption'], alignment=1)
        self.story.append(Paragraph(footer_text, footer_style))
    
    def _create_kpi_cell(self, value: str, label: str) -> Paragraph:
        """Create a KPI cell with value and label."""
        text = f'<font size="32" color="#1A1A1A"><b>{value}</b></font><br/><font size="9" color="#888888">{label}</font>'
        style = ParagraphStyle('KPI', parent=self.styles['Body'], alignment=1, leading=36)
        return Paragraph(text, style)
    
    def _add_executive_summary(self, metadata: dict, metrics: dict):
        """Add executive summary page with optimized 2-column layout."""
        self.story.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeader']))
        self.story.append(Spacer(1, 10))
        
        aka_name = metadata.get("athlete_a_name", catalogo.etiqueta("AKA"))
        ao_name = metadata.get("athlete_b_name", catalogo.etiqueta("AO"))
        
        # ═══ OPTIMIZED LAYOUT: 2 COLUMNS ═══
        # Left column: Comparison + Scoring
        # Right column: Technique Type + Target Level
        
        # Comparison table (reduced width)
        comparison_data = [
            ['Metric', aka_name, ao_name, 'Adv'],
            ['Attacks', str(metrics['aka_attacks']), str(metrics['ao_attacks']), 
             self._advantage_symbol(metrics['aka_attacks'], metrics['ao_attacks'])],
            ['Effectiveness', f"{metrics['aka_effectiveness']:.1f}%", f"{metrics['ao_effectiveness']:.1f}%",
             self._advantage_symbol(metrics['aka_effectiveness'], metrics['ao_effectiveness'])],
            ['Top Technique', metrics['aka_top_tech'][:15], metrics['ao_top_tech'][:15], '—'],
            ['Unique Techs', str(metrics['aka_unique_techs']), str(metrics['ao_unique_techs']),
             self._advantage_symbol(metrics['aka_unique_techs'], metrics['ao_unique_techs'])],
            ['Diversity', f"{metrics['aka_entropy']:.2f}", f"{metrics['ao_entropy']:.2f}",
             self._advantage_symbol(metrics['aka_entropy'], metrics['ao_entropy'])],
        ]
        
        comparison_table = Table(comparison_data, colWidths=[110, 85, 85, 40])
        comparison_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BrandColors.KARLOS_SLATE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, BrandColors.BORDER_LIGHT),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TEXTCOLOR', (1, 1), (1, -1), BrandColors.AKA_RED),
            ('TEXTCOLOR', (2, 1), (2, -1), BrandColors.AO_BLUE),
            ('FONTNAME', (1, 1), (2, -1), 'Helvetica-Bold'),
        ]))
        
        # Scoring breakdown (compact)
        scoring_data = [
            ['Score', aka_name, ao_name],
            *[[rotulo, str(a), str(b)] for rotulo, a, b in metrics['reparto']],
            ['Total', str(metrics['aka_score']), str(metrics['ao_score'])],
            ['Success %', f"{metrics['aka_effectiveness']:.0f}%", f"{metrics['ao_effectiveness']:.0f}%"],
        ]
        
        scoring_table = Table(scoring_data, colWidths=[110, 85, 85])
        scoring_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BrandColors.KARLOS_SLATE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, BrandColors.BORDER_LIGHT),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TEXTCOLOR', (1, 1), (1, -1), BrandColors.AKA_RED),
            ('TEXTCOLOR', (2, 1), (2, -1), BrandColors.AO_BLUE),
            ('FONTNAME', (1, 1), (2, -1), 'Helvetica-Bold'),
        ]))
        
        # Technique type breakdown (compact)
        tech_type_data = [
            ['Type', aka_name, ao_name],
            ['Hand', str(metrics['aka_hand']), str(metrics['ao_hand'])],
            ['Foot', str(metrics['aka_foot']), str(metrics['ao_foot'])],
            ['Sweeps', str(metrics['aka_sweeps']), str(metrics['ao_sweeps'])],
            ['Tactics', str(metrics['aka_tactics_total']), str(metrics['ao_tactics_total'])],
            ['Defense', str(metrics['aka_defense']), str(metrics['ao_defense'])],
        ]
        
        tech_type_table = Table(tech_type_data, colWidths=[110, 85, 85])
        tech_type_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BrandColors.KARLOS_SLATE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, BrandColors.BORDER_LIGHT),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TEXTCOLOR', (1, 1), (1, -1), BrandColors.AKA_RED),
            ('TEXTCOLOR', (2, 1), (2, -1), BrandColors.AO_BLUE),
            ('FONTNAME', (1, 1), (2, -1), 'Helvetica-Bold'),
        ]))
        
        # Target level analysis — sport-specific
        is_kb = self._is_kickboxing(metrics)
        if is_kb:
            target_data = [
                ['Target', f'{aka_name[:6]} Atk', f'{aka_name[:6]} Scr', f'{ao_name[:6]} Atk', f'{ao_name[:6]} Scr'],
                [metrics['zonas_kb'][0], str(metrics['aka_high']), str(metrics['aka_high_scored']),
                 str(metrics['ao_high']), str(metrics['ao_high_scored'])],
                [metrics['zonas_kb'][1], str(metrics['aka_mid']), str(metrics['aka_mid_scored']),
                 str(metrics['ao_mid']), str(metrics['ao_mid_scored'])],
                [metrics['zonas_kb'][2], str(metrics['aka_low']), str(metrics['aka_low_scored']),
                 str(metrics['ao_low']), str(metrics['ao_low_scored'])],
            ]
        else:
            target_data = [
                ['Level', f'{aka_name[:6]} Atk', f'{aka_name[:6]} Scr', f'{ao_name[:6]} Atk', f'{ao_name[:6]} Scr'],
                ['Jodan', str(metrics['aka_jodan']), str(metrics['aka_jodan_scored']), 
                 str(metrics['ao_jodan']), str(metrics['ao_jodan_scored'])],
                ['Chudan', str(metrics['aka_chudan']), str(metrics['aka_chudan_scored']), 
                 str(metrics['ao_chudan']), str(metrics['ao_chudan_scored'])],
            ]
        
        target_table = Table(target_data, colWidths=[70, 50, 50, 50, 50])
        target_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BrandColors.KARLOS_SLATE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, BrandColors.BORDER_LIGHT),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TEXTCOLOR', (1, 1), (2, -1), BrandColors.AKA_RED),
            ('TEXTCOLOR', (3, 1), (4, -1), BrandColors.AO_BLUE),
            ('FONTNAME', (1, 1), (4, -1), 'Helvetica-Bold'),
        ]))
        
        # ═══ 2-COLUMN LAYOUT ═══
        # Create a master table with 2 columns
        left_column = [
            [Paragraph("<b>PERFORMANCE COMPARISON</b>", self.styles['Body'])],
            [comparison_table],
            [Spacer(1, 15)],
            [Paragraph("<b>SCORING BREAKDOWN</b>", self.styles['Body'])],
            [scoring_table],
        ]
        
        target_section_title = "TARGET ZONES (High/Mid/Low)" if is_kb else "TARGET LEVELS"
        right_column = [
            [Paragraph("<b>TECHNIQUE TYPES</b>", self.styles['Body'])],
            [tech_type_table],
            [Spacer(1, 15)],
            [Paragraph(f"<b>{target_section_title}</b>", self.styles['Body'])],
            [target_table],
        ]
        
        # Combine into 2-column layout
        layout_data = [[Table(left_column), Table(right_column)]]
        layout_table = Table(layout_data, colWidths=[380, 380])
        layout_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        self.story.append(layout_table)
        self.story.append(Spacer(1, 20))
        
        # Key insights (full width)
        self.story.append(Paragraph("KEY INSIGHTS", self.styles['SectionHeader']))
        self.story.append(Spacer(1, 10))
        
        insights = self._generate_insights(metadata, metrics)
        for insight in insights:
            bullet = Paragraph(f"• {insight}", self.styles['Body'])
            self.story.append(bullet)
            self.story.append(Spacer(1, 5))
    
    def _add_tactical_analysis(self, metadata: dict, metrics: dict, sport_id: str):
        """Add tactical analysis page with temporal and tactical breakdowns."""
        self.story.append(Paragraph("TACTICAL ANALYSIS", self.styles['SectionHeader']))
        self.story.append(Spacer(1, 10))
        
        aka_name = metadata.get("athlete_a_name", catalogo.etiqueta("AKA"))
        ao_name = metadata.get("athlete_b_name", catalogo.etiqueta("AO"))
        
        # ═══ TEMPORAL ANALYSIS ═══
        self.story.append(Paragraph("<b>TEMPORAL ANALYSIS — Performance by Phase</b>", self.styles['Body']))
        self.story.append(Spacer(1, 8))
        
        temporal_data = [
            ['Phase', f'{aka_name} Attacks', f'{aka_name} Score', f'{ao_name} Attacks', f'{ao_name} Score'],
        ]
        
        phases, phase_labels, _ = metrics['fases']
        
        for phase, label in zip(phases, phase_labels):
            aka_atk = metrics['aka_by_phase'].get(phase, 0)
            ao_atk = metrics['ao_by_phase'].get(phase, 0)
            aka_scr = metrics['aka_score_by_phase'].get(phase, 0)
            ao_scr = metrics['ao_score_by_phase'].get(phase, 0)
            temporal_data.append([label, str(aka_atk), str(aka_scr), str(ao_atk), str(ao_scr)])
        
        temporal_table = Table(temporal_data, colWidths=[100, 90, 90, 90, 90])
        temporal_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BrandColors.KARLOS_SLATE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, BrandColors.BORDER_LIGHT),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TEXTCOLOR', (1, 1), (2, -1), BrandColors.AKA_RED),
            ('TEXTCOLOR', (3, 1), (4, -1), BrandColors.AO_BLUE),
            ('FONTNAME', (1, 1), (4, -1), 'Helvetica-Bold'),
        ]))
        
        self.story.append(temporal_table)
        self.story.append(Spacer(1, 20))
        
        # ═══ TACTICAL ACTIONS ═══
        self.story.append(Paragraph("<b>TACTICAL ACTIONS — Feints & Clinches</b>", self.styles['Body']))
        self.story.append(Spacer(1, 8))
        
        tactical_data = [
            ['Action Type', aka_name, ao_name],
            ['Feints', str(metrics['aka_feints']), str(metrics['ao_feints'])],
            ['Clinches', str(metrics['aka_clinches']), str(metrics['ao_clinches'])],
            ['Total Tactics', str(metrics['aka_tactics_total']), str(metrics['ao_tactics_total'])],
        ]
        
        tactical_table = Table(tactical_data, colWidths=[150, 100, 100])
        tactical_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BrandColors.KARLOS_SLATE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, BrandColors.BORDER_LIGHT),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TEXTCOLOR', (1, 1), (1, -1), BrandColors.AKA_RED),
            ('TEXTCOLOR', (2, 1), (2, -1), BrandColors.AO_BLUE),
            ('FONTNAME', (1, 1), (2, -1), 'Helvetica-Bold'),
        ]))
        
        self.story.append(tactical_table)
        self.story.append(Spacer(1, 20))
        
        # ═══ DEFENSIVE PROFILE ═══
        self.story.append(Paragraph("<b>DEFENSIVE PROFILE</b>", self.styles['Body']))
        self.story.append(Spacer(1, 8))
        
        aka_atk_def_ratio = f"{metrics['aka_attacks']}:{metrics['aka_defense']}" if metrics['aka_defense'] > 0 else f"{metrics['aka_attacks']}:0"
        ao_atk_def_ratio = f"{metrics['ao_attacks']}:{metrics['ao_defense']}" if metrics['ao_defense'] > 0 else f"{metrics['ao_attacks']}:0"
        
        defensive_data = [
            ['Metric', aka_name, ao_name],
            ['Defensive Actions', str(metrics['aka_defense']), str(metrics['ao_defense'])],
            ['Attack/Defense Ratio', aka_atk_def_ratio, ao_atk_def_ratio],
        ]
        
        defensive_table = Table(defensive_data, colWidths=[150, 100, 100])
        defensive_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BrandColors.KARLOS_SLATE),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, BrandColors.BORDER_LIGHT),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TEXTCOLOR', (1, 1), (1, -1), BrandColors.AKA_RED),
            ('TEXTCOLOR', (2, 1), (2, -1), BrandColors.AO_BLUE),
            ('FONTNAME', (1, 1), (2, -1), 'Helvetica-Bold'),
        ]))
        
        self.story.append(defensive_table)
        self.story.append(Spacer(1, 20))
        
        # ═══ TACTICAL INSIGHTS ═══
        self.story.append(Paragraph("<b>TACTICAL INSIGHTS</b>", self.styles['Body']))
        self.story.append(Spacer(1, 8))
        
        tactical_insights = []
        
        # Temporal dominance
        aka_total_attacks = sum(metrics['aka_by_phase'].values())
        ao_total_attacks = sum(metrics['ao_by_phase'].values())
        
        if aka_total_attacks > 0:
            aka_minute_3 = metrics['aka_by_phase'].get('Minute_3', 0)
            aka_minute_1 = metrics['aka_by_phase'].get('Minute_1', 0)
            if aka_minute_3 > aka_minute_1 * 1.5:
                tactical_insights.append(f"<b>{aka_name}</b> showed strong finishing power, increasing attack volume by {((aka_minute_3/max(aka_minute_1,1)-1)*100):.0f}% in the final minute.")
        
        if ao_total_attacks > 0:
            ao_minute_3 = metrics['ao_by_phase'].get('Minute_3', 0)
            ao_minute_1 = metrics['ao_by_phase'].get('Minute_1', 0)
            if ao_minute_3 > ao_minute_1 * 1.5:
                tactical_insights.append(f"<b>{ao_name}</b> demonstrated excellent conditioning, increasing offensive output by {((ao_minute_3/max(ao_minute_1,1)-1)*100):.0f}% in the final minute.")
        
        # Tactical usage
        if metrics['aka_feints'] > metrics['ao_feints'] * 2:
            tactical_insights.append(f"<b>{aka_name}</b> employed significantly more feints ({metrics['aka_feints']} vs {metrics['ao_feints']}), indicating a more deceptive tactical approach.")
        elif metrics['ao_feints'] > metrics['aka_feints'] * 2:
            tactical_insights.append(f"<b>{ao_name}</b> used feints more frequently ({metrics['ao_feints']} vs {metrics['aka_feints']}), creating openings through deception.")
        
        # Defensive approach
        if metrics['aka_defense'] > metrics['ao_defense'] * 1.5:
            tactical_insights.append(f"<b>{aka_name}</b> showed a more defensive approach with {metrics['aka_defense']} defensive actions vs {metrics['ao_defense']}, prioritizing counter-attacking opportunities.")
        elif metrics['ao_defense'] > metrics['aka_defense'] * 1.5:
            tactical_insights.append(f"<b>{ao_name}</b> demonstrated superior defensive awareness with {metrics['ao_defense']} defensive actions, effectively neutralizing opponent attacks.")
        
        if not tactical_insights:
            tactical_insights.append("Both athletes showed balanced tactical approaches throughout the bout.")
        
        for insight in tactical_insights:
            bullet = Paragraph(f"• {insight}", self.styles['Body'])
            self.story.append(bullet)
            self.story.append(Spacer(1, 5))
    
    def _add_performance_charts(self, metadata: dict, metrics: dict, sport_id: str):
        """Add performance visualization page with professional charts."""
        self.story.append(Paragraph("PERFORMANCE VISUALIZATION", self.styles['SectionHeader']))
        self.story.append(Spacer(1, 10))
        
        aka_name = metadata.get("athlete_a_name", catalogo.etiqueta("AKA"))
        ao_name = metadata.get("athlete_b_name", catalogo.etiqueta("AO"))
        
        # ═══ BAR CHART: TECHNIQUE TYPE COMPARISON ═══
        self.story.append(Paragraph("<b>TECHNIQUE TYPE DISTRIBUTION</b>", self.styles['Body']))
        self.story.append(Spacer(1, 8))
        
        bar_chart = self._create_technique_bar_chart(metrics, aka_name, ao_name)
        self.story.append(bar_chart)
        self.story.append(Spacer(1, 20))
        
        # ═══ PIE CHARTS: TARGET LEVEL DISTRIBUTION ═══
        self.story.append(Paragraph("<b>TARGET LEVEL DISTRIBUTION</b>", self.styles['Body']))
        self.story.append(Spacer(1, 8))
        
        pie_charts = self._create_target_pie_charts(metrics, aka_name, ao_name)
        self.story.append(pie_charts)
        self.story.append(Spacer(1, 20))
        
        # ═══ LINE CHART: SCORE EVOLUTION ═══
        self.story.append(Paragraph("<b>SCORE EVOLUTION BY PHASE</b>", self.styles['Body']))
        self.story.append(Spacer(1, 8))
        
        line_chart = self._create_score_line_chart(metrics, aka_name, ao_name)
        self.story.append(line_chart)
    
    def _create_technique_bar_chart(self, metrics: dict, aka_name: str, ao_name: str) -> Drawing:
        """Create a bar chart comparing technique types."""
        drawing = Drawing(600, 250)
        
        chart = VerticalBarChart()
        chart.x = 50
        chart.y = 50
        chart.height = 180
        chart.width = 500
        
        # Data: [Hand, Foot, Sweeps, Tactics, Defense]
        chart.data = [
            [metrics['aka_hand'], metrics['aka_foot'], metrics['aka_sweeps'], 
             metrics['aka_tactics_total'], metrics['aka_defense']],
            [metrics['ao_hand'], metrics['ao_foot'], metrics['ao_sweeps'], 
             metrics['ao_tactics_total'], metrics['ao_defense']],
        ]
        
        chart.categoryAxis.categoryNames = ['Hand', 'Foot', 'Sweeps', 'Tactics', 'Defense']
        chart.categoryAxis.labels.fontSize = 10
        chart.categoryAxis.labels.angle = 0
        
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(max(chart.data[0]), max(chart.data[1])) * 1.2
        chart.valueAxis.valueStep = max(1, int(chart.valueAxis.valueMax / 5))
        chart.valueAxis.labels.fontSize = 10
        
        chart.bars[0].fillColor = BrandColors.AKA_RED
        chart.bars[1].fillColor = BrandColors.AO_BLUE
        
        chart.barWidth = 15
        chart.groupSpacing = 20
        chart.barSpacing = 3
        
        # Legend
        drawing.add(Rect(50, 10, 15, 15, fillColor=BrandColors.AKA_RED, strokeColor=None))
        drawing.add(String(70, 15, aka_name, fontSize=10, fillColor=BrandColors.TEXT_PRIMARY))
        
        drawing.add(Rect(200, 10, 15, 15, fillColor=BrandColors.AO_BLUE, strokeColor=None))
        drawing.add(String(220, 15, ao_name, fontSize=10, fillColor=BrandColors.TEXT_PRIMARY))
        
        drawing.add(chart)
        return drawing
    
    def _is_kickboxing(self, metrics: dict) -> bool:
        """Detect if the metrics are for kickboxing by checking for KB-specific keys."""
        return 'aka_high' in metrics or 'aka_mid' in metrics or 'aka_low' in metrics

    def _create_target_pie_charts(self, metrics: dict, aka_name: str, ao_name: str) -> Table:
        """Create side-by-side pie charts for target distribution."""
        is_kb = self._is_kickboxing(metrics)
        
        # AKA pie chart
        aka_drawing = Drawing(280, 200)
        aka_pie = Pie()
        aka_pie.x = 90
        aka_pie.y = 50
        aka_pie.width = 120
        aka_pie.height = 120
        
        if is_kb:
            aka_total = metrics['aka_high'] + metrics['aka_mid'] + metrics['aka_low']
            if aka_total > 0:
                aka_pie.data = [metrics['aka_high'], metrics['aka_mid'], metrics['aka_low']]
                z = metrics['zonas_kb']
                aka_pie.labels = [f"{z[0]}\n{metrics['aka_high']}", f"{z[1]}\n{metrics['aka_mid']}", f"{z[2]}\n{metrics['aka_low']}"]
            else:
                aka_pie.data = [1]
                aka_pie.labels = ["No data"]
            aka_pie.slices[0].fillColor = BrandColors.AKA_RED
            aka_pie.slices[1].fillColor = colors.HexColor("#F28B82") if aka_total > 0 else BrandColors.NEUTRAL_GRAY
            aka_pie.slices[2].fillColor = colors.HexColor("#F5C6C2") if aka_total > 0 else BrandColors.NEUTRAL_GRAY
        else:
            aka_total = metrics['aka_jodan'] + metrics['aka_chudan']
            if aka_total > 0:
                aka_pie.data = [metrics['aka_jodan'], metrics['aka_chudan']]
                aka_pie.labels = [f"Jodan\n{metrics['aka_jodan']}", f"Chudan\n{metrics['aka_chudan']}"]
            else:
                aka_pie.data = [1]
                aka_pie.labels = ["No data"]
            aka_pie.slices[0].fillColor = BrandColors.AKA_RED
            aka_pie.slices[1].fillColor = colors.HexColor("#F28B82") if aka_total > 0 else BrandColors.NEUTRAL_GRAY
        
        for i in range(len(aka_pie.data)):
            aka_pie.slices[i].strokeColor = colors.white
            aka_pie.slices[i].strokeWidth = 2
        
        aka_drawing.add(aka_pie)
        aka_drawing.add(String(140, 180, aka_name, fontSize=12, fillColor=BrandColors.AKA_RED, 
                               fontName="Helvetica-Bold", textAnchor="middle"))
        
        # AO pie chart
        ao_drawing = Drawing(280, 200)
        ao_pie = Pie()
        ao_pie.x = 90
        ao_pie.y = 50
        ao_pie.width = 120
        ao_pie.height = 120
        
        if is_kb:
            ao_total = metrics['ao_high'] + metrics['ao_mid'] + metrics['ao_low']
            if ao_total > 0:
                ao_pie.data = [metrics['ao_high'], metrics['ao_mid'], metrics['ao_low']]
                z = metrics['zonas_kb']
                ao_pie.labels = [f"{z[0]}\n{metrics['ao_high']}", f"{z[1]}\n{metrics['ao_mid']}", f"{z[2]}\n{metrics['ao_low']}"]
            else:
                ao_pie.data = [1]
                ao_pie.labels = ["No data"]
            ao_pie.slices[0].fillColor = BrandColors.AO_BLUE
            ao_pie.slices[1].fillColor = colors.HexColor("#8AB4F8") if ao_total > 0 else BrandColors.NEUTRAL_GRAY
            ao_pie.slices[2].fillColor = colors.HexColor("#C6DAF7") if ao_total > 0 else BrandColors.NEUTRAL_GRAY
        else:
            ao_total = metrics['ao_jodan'] + metrics['ao_chudan']
            if ao_total > 0:
                ao_pie.data = [metrics['ao_jodan'], metrics['ao_chudan']]
                ao_pie.labels = [f"Jodan\n{metrics['ao_jodan']}", f"Chudan\n{metrics['ao_chudan']}"]
            else:
                ao_pie.data = [1]
                ao_pie.labels = ["No data"]
            ao_pie.slices[0].fillColor = BrandColors.AO_BLUE
            ao_pie.slices[1].fillColor = colors.HexColor("#8AB4F8") if ao_total > 0 else BrandColors.NEUTRAL_GRAY
        
        for i in range(len(ao_pie.data)):
            ao_pie.slices[i].strokeColor = colors.white
            ao_pie.slices[i].strokeWidth = 2
        
        ao_drawing.add(ao_pie)
        ao_drawing.add(String(140, 180, ao_name, fontSize=12, fillColor=BrandColors.AO_BLUE, 
                             fontName="Helvetica-Bold", textAnchor="middle"))
        
        # Combine in table
        pie_table = Table([[aka_drawing, ao_drawing]], colWidths=[380, 380])
        pie_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        return pie_table
    
    def _create_score_line_chart(self, metrics: dict, aka_name: str, ao_name: str) -> Drawing:
        """Create a line chart showing score evolution by phase."""
        drawing = Drawing(600, 250)
        
        chart = HorizontalLineChart()
        chart.x = 50
        chart.y = 50
        chart.height = 180
        chart.width = 500
        
        # Cumulative scores by phase
        phases, _, cortos = metrics['fases']
        aka_cumulative = []
        ao_cumulative = []
        aka_sum = 0
        ao_sum = 0
        
        for phase in phases:
            aka_sum += metrics['aka_score_by_phase'].get(phase, 0)
            ao_sum += metrics['ao_score_by_phase'].get(phase, 0)
            aka_cumulative.append(aka_sum)
            ao_cumulative.append(ao_sum)
        
        chart.data = [aka_cumulative, ao_cumulative]
        
        chart.categoryAxis.categoryNames = list(cortos)
        chart.categoryAxis.labels.fontSize = 10
        
        max_score = max(max(aka_cumulative), max(ao_cumulative))
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(max_score * 1.2, 3)
        chart.valueAxis.valueStep = max(1, int(chart.valueAxis.valueMax / 5))
        chart.valueAxis.labels.fontSize = 10
        
        chart.lines[0].strokeColor = BrandColors.AKA_RED
        chart.lines[1].strokeColor = BrandColors.AO_BLUE
        chart.lines[0].strokeWidth = 3
        chart.lines[1].strokeWidth = 3
        chart.lines[0].symbol = None
        chart.lines[1].symbol = None
        
        # Legend
        drawing.add(Line(50, 10, 80, 10, strokeColor=BrandColors.AKA_RED, strokeWidth=3))
        drawing.add(String(85, 7, aka_name, fontSize=10, fillColor=BrandColors.TEXT_PRIMARY))
        
        drawing.add(Line(200, 10, 230, 10, strokeColor=BrandColors.AO_BLUE, strokeWidth=3))
        drawing.add(String(235, 7, ao_name, fontSize=10, fillColor=BrandColors.TEXT_PRIMARY))
        
        drawing.add(chart)
        return drawing
    
    def _add_header_footer(self, canvas_obj, doc):
        """Add header and footer to each page."""
        canvas_obj.saveState()
        
        # Footer
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(BrandColors.TEXT_MUTED)
        nombre, version = _programa()
        footer_text = f"{nombre} v{version} • Page {doc.page}"
        canvas_obj.drawCentredString(self.page_width / 2, 10*mm, footer_text)
        
        canvas_obj.restoreState()
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as MM:SS."""
        if seconds <= 0:
            return "00:00"
        m = int(seconds) // 60
        s = int(seconds) % 60
        return f"{m:02d}:{s:02d}"
    
    @staticmethod
    def _advantage_symbol(a_val: float, b_val: float) -> str:
        """Return advantage symbol."""
        if a_val > b_val:
            return f"▲ {catalogo.etiqueta('AKA')}"
        elif b_val > a_val:
            return f"▲ {catalogo.etiqueta('AO')}"
        return "="
    
    def _generate_insights(self, metadata: dict, metrics: dict) -> list[str]:
        """Generate automatic insights from the data (v6.1)."""
        insights = []

        aka_name = metadata.get("athlete_a_name", catalogo.etiqueta("AKA"))
        ao_name = metadata.get("athlete_b_name", catalogo.etiqueta("AO"))

        # Effectiveness insight
        if metrics['aka_effectiveness'] > metrics['ao_effectiveness'] + 10:
            insights.append(f"<b>{aka_name}</b> demonstrated superior effectiveness ({metrics['aka_effectiveness']:.0f}% vs {metrics['ao_effectiveness']:.0f}%), converting attacks into scores more efficiently.")
        elif metrics['ao_effectiveness'] > metrics['aka_effectiveness'] + 10:
            insights.append(f"<b>{ao_name}</b> showed higher effectiveness ({metrics['ao_effectiveness']:.0f}% vs {metrics['aka_effectiveness']:.0f}%), indicating better precision in scoring opportunities.")

        # Volume insight
        if metrics['aka_attacks'] > metrics['ao_attacks'] * 1.3:
            insights.append(f"<b>{aka_name}</b> maintained higher offensive pressure with {metrics['aka_attacks']} attacks vs {metrics['ao_attacks']}, controlling the pace of the bout.")
        elif metrics['ao_attacks'] > metrics['aka_attacks'] * 1.3:
            insights.append(f"<b>{ao_name}</b> dominated offensive volume with {metrics['ao_attacks']} attacks vs {metrics['aka_attacks']}, dictating the fight rhythm.")

        # Diversity insight
        if metrics['aka_entropy'] > metrics['ao_entropy'] + 0.3:
            insights.append(f"<b>{aka_name}</b> displayed greater technical diversity (entropy: {metrics['aka_entropy']:.2f}), making their attack patterns less predictable.")
        elif metrics['ao_entropy'] > metrics['aka_entropy'] + 0.3:
            insights.append(f"<b>{ao_name}</b> showed more varied technique selection (entropy: {metrics['ao_entropy']:.2f}), adapting tactics throughout the bout.")

        # Active time insight
        active_pct = (metrics['active_time_s'] / metrics['fight_duration'] * 100) if metrics['fight_duration'] > 0 else 0
        if active_pct < 70:
            insights.append(f"High number of referee stops ({metrics['ref_stops_count']}) resulted in only {active_pct:.0f}% active fight time, potentially affecting rhythm and conditioning.")

        # ═══ STANCE INSIGHT (v6.1) ═══
        aka_stance = metrics.get('aka_stance', {})
        ao_stance = metrics.get('ao_stance', {})
        if aka_stance.get('total', 0) > 0 and ao_stance.get('total', 0) > 0:
            if aka_stance['lead_pct'] > 70:
                insights.append(f"<b>{aka_name}</b> showed a strong Lead-limb preference ({aka_stance['lead_pct']:.0f}%), suggesting an aggressive forward-pressure fighting style.")
            if ao_stance['lead_pct'] > 70:
                insights.append(f"<b>{ao_name}</b> relied heavily on Lead-limb attacks ({ao_stance['lead_pct']:.0f}%), indicating a front-foot offensive approach.")

        # ═══ ACTION-TYPE INSIGHT (v6.1) ═══
        aka_actions = metrics.get('aka_actions', {})
        ao_actions = metrics.get('ao_actions', {})
        for name, actions in [(aka_name, aka_actions), (ao_name, ao_actions)]:
            if actions.get('Counter', {}).get('count', 0) > 0:
                counter_eff = actions['Counter']['eff_pct']
                direct_eff = actions.get('Direct', {}).get('eff_pct', 0)
                if counter_eff > direct_eff + 15:
                    insights.append(f"<b>{name}</b> was highly effective in counter-attacks ({counter_eff:.0f}% eff vs {direct_eff:.0f}% direct), demonstrating elite reactive timing.")

        # ═══ KICKBOXING TARGET ZONE INSIGHTS ═══
        is_kb = self._is_kickboxing(metrics)
        if is_kb:
            # AKA target preference
            z = metrics.get('zonas_kb', ['Head', 'Torso', 'Legs'])
            aka_targets = {
                z[0]: metrics.get('aka_high', 0),
                z[1]: metrics.get('aka_mid', 0),
                z[2]: metrics.get('aka_low', 0),
            }
            ao_targets = {
                z[0]: metrics.get('ao_high', 0),
                z[1]: metrics.get('ao_mid', 0),
                z[2]: metrics.get('ao_low', 0),
            }
            
            for name, targets in [(aka_name, aka_targets), (ao_name, ao_targets)]:
                total = sum(targets.values())
                if total > 0:
                    preferred = max(targets, key=targets.get)
                    pct = round(targets[preferred] / total * 100, 0)
                    insights.append(f"<b>{name}</b> showed a preference for <b>{preferred}</b> target ({pct:.0f}% of {total} attacks), indicating a clear tactical targeting strategy.")
            
            # Compare target diversity
            aka_high_pct = (metrics.get('aka_high', 0) / max(sum(aka_targets.values()), 1)) * 100
            ao_high_pct = (metrics.get('ao_high', 0) / max(sum(ao_targets.values()), 1)) * 100
            if aka_high_pct > 60 and ao_high_pct < 40:
                insights.append(f"<b>{aka_name}</b> focused heavily on {z[0]} attacks ({aka_high_pct:.0f}%) while <b>{ao_name}</b> varied targets more, suggesting different tactical philosophies.")
            elif ao_high_pct > 60 and aka_high_pct < 40:
                insights.append(f"<b>{ao_name}</b> prioritized {z[0]} attacks ({ao_high_pct:.0f}%) while <b>{aka_name}</b> distributed attacks more evenly across target zones.")

        return insights


# ══════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ══════════════════════════════════════════════════════════════════

def generate_professional_report(
    output_path: str | Path,
    bout_metadata: dict[str, Any],
    annotations: list,
    session_data: dict[str, Any],
    sport_id: str = "karate",
) -> str:
    """Generate a professional PDF report.
    
    Args:
        output_path: Where to save the PDF
        bout_metadata: Bout information
        annotations: List of annotations
        session_data: Session metrics
        sport_id: Sport identifier
        
    Returns:
        Path to generated PDF
    """
    generator = ProfessionalReportGenerator(output_path)
    return generator.generate_report(bout_metadata, annotations, session_data, sport_id)
