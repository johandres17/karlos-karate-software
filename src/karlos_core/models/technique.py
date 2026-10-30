"""Technique and taxonomy data models for KARLOS ANNOTATOR."""

from dataclasses import dataclass, field
from typing import Any, Optional


def resolve_combat_action(
    base_technique: str,
    stance: str,
    combinatorial_map: dict[str, dict[str, str]],
) -> str:
    """Resolve the official Japanese technique name from base + stance.

    Combinatorial Engine (v1.0): instead of static buttons per variant,
    the annotator selects a BASE technique (e.g., "Tsuki") and a Stance
    modifier ("Lead"/"Rear"). This function resolves the official name
    (e.g., "Kizami Tsuki" / "Gyaku Tsuki") BEFORE the Annotation is
    persisted, so downstream analytics (Match Report, PDF, CSV) keep
    working with recognized technique names.

    Follows the Open/Closed principle: techniques or stances absent from
    the map gracefully fall back to the base technique name, so adding
    new combinations only requires editing the sport config.

    Args:
        base_technique: Base technique name selected in the UI (e.g., "Tsuki").
        stance: Stance modifier ("Lead" or "Rear"). Empty string allowed.
        combinatorial_map: Mapping of base_technique → {stance → resolved name},
            typically TaxonomyConfig.combinatorial_map loaded from sport config.

    Returns:
        The resolved official technique name, or ``base_technique`` if no
        mapping exists for the given combination.

    Examples:
        >>> cmap = {"Tsuki": {"Lead": "Kizami Tsuki", "Rear": "Gyaku Tsuki"}}
        >>> resolve_combat_action("Tsuki", "Lead", cmap)
        'Kizami Tsuki'
        >>> resolve_combat_action("Tsuki", "Rear", cmap)
        'Gyaku Tsuki'
        >>> resolve_combat_action("Uraken", "Lead", cmap)  # not mapped
        'Uraken'
    """
    if not base_technique:
        return base_technique
    return combinatorial_map.get(base_technique, {}).get(stance, base_technique)


@dataclass(frozen=True)
class Technique:
    """A single technique definition loaded from taxonomy configuration.

    Attributes:
        name: Display name (e.g., "Gyaku-tsuki").
        abbr: Short abbreviation (e.g., "GYK").
        has_level: Whether this technique requires a target level (Jodan/Chudan).
        category: The taxonomy group name (e.g., "HAND TECHNIQUES").
        group: The high-level category (e.g., "ATTACK", "DEFENSE").
        color: Hex color string for UI rendering.
        shortcut: Keyboard shortcut string (e.g., "1", "Ctrl+R").
        levels_config: Optional multi-level config dict, e.g.
            {"Pierna": ["Delantera","Trasera"], "Objetivo": ["Peto","Casco"]}.
            When present, the DetailPopup renders N selectors instead of a
            single flat level list. Defaults to None (legacy flat levels).
    """

    name: str
    abbr: str
    has_level: bool
    category: str
    group: str
    color: str
    shortcut: str
    levels_config: Optional[dict[str, list[str]]] = None


@dataclass(frozen=True)
class ScoringRule:
    """A WKF scoring outcome definition.

    Attributes:
        code: Internal code (e.g., "IPPON", "WAZA", "NONE").
        points: Numeric points awarded.
        label: Full display label shown on buttons.
        color: Hex color string for UI rendering.
        shortcut: Keyboard shortcut string.
    """

    code: str
    points: int
    label: str
    color: str
    shortcut: str


@dataclass(frozen=True)
class RefereeStopType:
    """A referee stop reason definition.

    Attributes:
        name: Display name (e.g., "Referee", "VR", "Injury").
        abbr: Short abbreviation (e.g., "YME-R").
        shortcut: Keyboard shortcut string.
        color: Hex color string for UI rendering.
    """

    name: str
    abbr: str
    shortcut: str
    color: str


@dataclass(frozen=True)
class AppColors:
    """Centralized color palette for the application theme.

    Attributes:
        background: Main background.
        panel: Panel/card background.
        border: Border color.
        text: Primary text color.
        muted: Muted/secondary text color.
        aka: AKA (red) athlete color.
        ao: AO (blue) athlete color.
        punch: Punch techniques color.
        kick: Kick techniques color.
        sweep: Sweep techniques color.
        state: State/defense color.
        accent: Accent/highlight color.
        green: Success/positive color.
        yellow: Warning/yellow color.
    """

    background: str
    panel: str
    border: str
    text: str
    muted: str
    aka: str
    ao: str
    punch: str
    kick: str
    sweep: str
    state: str
    accent: str
    green: str
    yellow: str
    border_hover: str = "rgba(255,255,255,0.15)"


@dataclass(frozen=True)
class VideoConfig:
    """Video playback configuration parameters.

    Attributes:
        speed_options: List of available playback speeds.
        speed_labels: Display labels for each speed.
        default_speed_index: Index of default speed in speed_options.
        wheel_step_small: Frames to skip on small wheel scroll.
        wheel_step_medium: Frames to skip on medium wheel scroll.
        wheel_step_large: Frames to skip on large wheel scroll.
        wheel_threshold_small: Pixel threshold for small step.
        wheel_threshold_medium: Pixel threshold for medium step.
        wheel_threshold_large: Pixel threshold for large step.
    """

    speed_options: list[float]
    speed_labels: list[str]
    default_speed_index: int
    wheel_step_small: int
    wheel_step_medium: int
    wheel_step_large: int
    wheel_threshold_small: int
    wheel_threshold_medium: int
    wheel_threshold_large: int


@dataclass
class ScoringEngine:
    """Unified scoring engine for all sports.
    
    Auto-score rules and heuristics for automatic score calculation based
    on technique + level. Lo que vale cada código lo dice el deporte
    (``catalogo.activo().reglamento.puntos``, decisión 0004): aquí había
    una copia de la tabla que nadie usaba.
    
    Attributes:
        auto_score_rules: Explicit technique_name → {level → score_code} mapping.
    """
    
    auto_score_rules: dict[str, dict[str, str]] = field(default_factory=dict)
    
    def calculate_score(
        self,
        technique_name: str,
        level: str,
        category: Optional["TechniqueCategory"] = None,
    ) -> str:
        """Calculate score automatically based on technique + level.
        
        Priority order:
        1. Explicit auto_score_rules mapping
        2. Category scoring_rules metadata
        3. Category trajectory heuristics (Taekwondo)
        4. Default fallback
        
        Args:
            technique_name: Name of the technique (e.g., "Bandal/Dollyo Chagi").
            level: Target level (e.g., "Head", "Trunk", "Jodan").
            category: Optional TechniqueCategory for metadata-based scoring.
        
        Returns:
            Score code (e.g., "3_PTS", "IPPON", "CONNECTED").
        """
        # 1. Explicit auto_score_rules (highest priority)
        if technique_name in self.auto_score_rules:
            level_map = self.auto_score_rules[technique_name]
            if level in level_map:
                return level_map[level]
        
        # 2. Category scoring_rules metadata
        if category and category.scoring_rules:
            if level in category.scoring_rules:
                return category.scoring_rules[level]
        
        # 3. Trajectory heuristics (Taekwondo WT)
        if category and category.trajectory:
            if category.trajectory == "spinning":
                return "6_PTS" if level == "Head" else "4_PTS"
            elif category.trajectory in ("circular", "linear"):
                return "3_PTS" if level == "Head" else "2_PTS"
            elif category.trajectory == "punch":
                return "1_PT" if level == "Trunk" else "NO_PT"
        
        # 4. Default fallback
        return "NONE"


@dataclass(frozen=True)
class TechniqueCategory:
    """Hierarchical technique category (e.g., CIRCULAR, PUNCHES, HAND TECHNIQUES).
    
    Represents a group of related techniques with shared metadata for
    auto-calculation and analysis.
    
    Attributes:
        name: Category name (e.g., "CIRCULAR", "PUNCHES", "HAND TECHNIQUES").
        group: High-level group (e.g., "ATTACK", "DEFENSE", "REFEREE STOP").
        color: Hex color string for UI rendering.
        techniques: List of techniques in this category.
        trajectory: Optional trajectory type (e.g., "circular", "linear", "spinning").
        range: Optional range classification (e.g., "long", "mid", "close").
        scoring_rules: Optional level → score_code mapping for auto-scoring.
    """
    
    name: str
    group: str
    color: str
    techniques: list[Technique]
    trajectory: str = ""
    range: str = ""
    scoring_rules: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TaxonomyConfig:
    """Complete taxonomy configuration loaded from sport config.

    Attributes:
        colors: Application color palette.
        levels: Target levels list (e.g., ["Jodan", "Chudan"]).
        scoring_rules: List of scoring outcomes.
        categories: Hierarchical technique categories (NEW - unified structure).
        techniques: Flat list of all techniques (auto-generated from categories).
        referee_stop_types: List of referee stop reason options.
        video: Video playback configuration.
        athlete_a_label: Display label for athlete A (e.g., "AKA", "Red").
        athlete_b_label: Display label for athlete B (e.g., "AO", "Blue").
        scoring_engine: Unified scoring engine instance.
        auto_score: DEPRECATED - use scoring_engine.auto_score_rules instead.
    """

    colors: AppColors
    levels: list[str]
    scoring_rules: list[ScoringRule]
    categories: list[TechniqueCategory]
    techniques: list[Technique]
    referee_stop_types: list[RefereeStopType]
    video: VideoConfig
    athlete_a_label: str = "AKA"
    athlete_b_label: str = "AO"
    scoring_engine: ScoringEngine = field(default_factory=ScoringEngine)
    # ── Combinatorial Engine (v1.0) ──────────────────────────────
    # base_technique → {stance → resolved official name}. Empty for
    # sports without combinatorial resolution (zero impact).
    combinatorial_map: dict[str, dict[str, str]] = field(default_factory=dict)
    # DEPRECATED fields (kept for backward compatibility)
    auto_score: dict[str, dict[str, str]] = field(default_factory=dict)
