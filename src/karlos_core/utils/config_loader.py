"""Configuration loader for KARLOS ANNOTATOR taxonomy.

Converts raw sport-configuration dictionaries into strongly-typed
dataclass instances (TaxonomyConfig, Technique, ScoringRule, etc.).
"""

from typing import Any

from karlos_core.models.technique import (
    AppColors,
    RefereeStopType,
    ScoringEngine,
    ScoringRule,
    TaxonomyConfig,
    Technique,
    TechniqueCategory,
    VideoConfig,
)


def _parse_colors(raw: dict[str, Any]) -> AppColors:
    """Parse the colors section from a sport configuration dict.

    Args:
        raw: Raw colors dictionary.

    Returns:
        AppColors instance.
    """
    return AppColors(
        background=raw["background"],
        panel=raw["panel"],
        border=raw["border"],
        text=raw["text"],
        muted=raw["muted"],
        aka=raw["aka"],
        ao=raw["ao"],
        punch=raw["punch"],
        kick=raw["kick"],
        sweep=raw["sweep"],
        state=raw["state"],
        accent=raw["accent"],
        green=raw["green"],
        yellow=raw["yellow"],
    )


def _parse_scoring(raw: dict[str, Any]) -> list[ScoringRule]:
    """Parse the scoring section from a sport configuration dict.

    Args:
        raw: Raw scoring dictionary (keyed by code).

    Returns:
        List of ScoringRule instances.
    """
    rules: list[ScoringRule] = []
    for code, data in raw.items():
        rules.append(
            ScoringRule(
                code=code,
                points=data["points"],
                label=data["label"],
                color=data["color"],
                shortcut=data["shortcut"],
            )
        )
    return rules


def _parse_categories(raw_taxonomy: list[dict[str, Any]]) -> list[TechniqueCategory]:
    """Parse the taxonomy section into hierarchical TechniqueCategory instances.

    Args:
        raw_taxonomy: Raw taxonomy list from sport config.

    Returns:
        List of TechniqueCategory instances with nested Technique objects.
    """
    categories: list[TechniqueCategory] = []
    for group in raw_taxonomy:
        category_name: str = group["name"]
        group_name: str = group["category"]
        color: str = group["color"]
        
        # Parse techniques for this category
        techniques: list[Technique] = []
        for tech in group["techniques"]:
            techniques.append(
                Technique(
                    name=tech["name"],
                    abbr=tech["abbr"],
                    has_level=tech["has_level"],
                    category=category_name,
                    group=group_name,
                    color=color,
                    shortcut=tech["shortcut"],
                    levels_config=tech.get("levels_config"),
                )
            )
        
        # Create TechniqueCategory with metadata
        categories.append(
            TechniqueCategory(
                name=category_name,
                group=group_name,
                color=color,
                techniques=techniques,
                trajectory=group.get("trajectory", ""),
                range=group.get("range", ""),
                scoring_rules=group.get("scoring_rules", {}),
            )
        )
    return categories


def _parse_techniques(raw_taxonomy: list[dict[str, Any]]) -> list[Technique]:
    """Parse the taxonomy section from a sport configuration dict.
    
    LEGACY FUNCTION: Flattens categories into a single technique list.
    Kept for backward compatibility with existing code.

    Args:
        raw_taxonomy: Raw taxonomy list.

    Returns:
        Flat list of all Technique instances across all categories.
    """
    techniques: list[Technique] = []
    for group in raw_taxonomy:
        category_name: str = group["name"]
        group_name: str = group["category"]
        color: str = group["color"]
        for tech in group["techniques"]:
            techniques.append(
                Technique(
                    name=tech["name"],
                    abbr=tech["abbr"],
                    has_level=tech["has_level"],
                    category=category_name,
                    group=group_name,
                    color=color,
                    shortcut=tech["shortcut"],
                    levels_config=tech.get("levels_config"),
                )
            )
    return techniques


def _parse_referee_stops(raw: list[dict[str, Any]]) -> list[RefereeStopType]:
    """Parse the referee_stop_types section from a sport configuration dict.

    Args:
        raw: Raw referee_stop_types list.

    Returns:
        List of RefereeStopType instances.
    """
    return [
        RefereeStopType(
            name=item["name"],
            abbr=item["abbr"],
            shortcut=item["shortcut"],
            color=item["color"],
        )
        for item in raw
    ]


def _parse_video(raw: dict[str, Any]) -> VideoConfig:
    """Parse the video configuration section from a sport configuration dict.

    Args:
        raw: Raw video dictionary.

    Returns:
        VideoConfig instance.
    """
    return VideoConfig(
        speed_options=raw["speed_options"],
        speed_labels=raw["speed_labels"],
        default_speed_index=raw["default_speed_index"],
        wheel_step_small=raw["wheel_step_small"],
        wheel_step_medium=raw["wheel_step_medium"],
        wheel_step_large=raw["wheel_step_large"],
        wheel_threshold_small=raw["wheel_threshold_small"],
        wheel_threshold_medium=raw["wheel_threshold_medium"],
        wheel_threshold_large=raw["wheel_threshold_large"],
    )


def load_config(sport_id: str) -> tuple[TaxonomyConfig, dict[str, str]]:
    """Load and parse a sport configuration by its identifier.

    This is the primary entry point for the multidisport system. It imports
    the matching sport-config module and parses its SPORT_CONFIG dict.

    Args:
        sport_id: Sport identifier ("karate", "kickboxing", etc.).

    Returns:
        A tuple of (TaxonomyConfig, sport_meta) where sport_meta contains
        {"id": ..., "name": ..., "short": ...}.

    Raises:
        ValueError: If the sport_id is not registered in config.SPORTS.
        KeyError: If required keys are missing from the config.
    """
    from karlos_core.config import SPORTS

    raw = SPORTS.get(sport_id)
    if raw is None:
        available = ", ".join(SPORTS.keys())
        raise ValueError(
            f"Unknown sport: '{sport_id}'. Available: {available}"
        )
    return load_config_from_dict(raw)


def load_config_from_dict(raw: dict[str, Any]) -> tuple[TaxonomyConfig, dict[str, str]]:
    """La misma carga, desde una configuracion ya montada."""
    sport_meta = dict(raw["sport"])

    # Parse hierarchical categories (NEW unified structure)
    categories = _parse_categories(raw["taxonomy"])
    
    # Parse flat techniques list (LEGACY backward compatibility)
    techniques = _parse_techniques(raw["taxonomy"])
    
    # Create scoring engine with auto_score rules built from category scoring_rules
    # Each category's scoring_rules (e.g., Head → 3_PTS) are applied to each
    # technique in that category, creating the explicit technique → level → score
    # mapping that ScoringEngine.calculate_score() uses as priority #1.
    auto_score_rules: dict[str, dict[str, str]] = {}
    for cat in raw.get("taxonomy", []):
        cat_scoring = cat.get("scoring_rules", {})
        if not cat_scoring:
            continue
        for tech in cat.get("techniques", []):
            tech_name = tech["name"]
            if tech_name not in auto_score_rules:
                auto_score_rules[tech_name] = {}
            # Merge category scoring_rules into technique-level mapping
            for level_key, score_code in cat_scoring.items():
                auto_score_rules[tech_name][level_key] = score_code

    scoring_engine = ScoringEngine(
        auto_score_rules=auto_score_rules
    )

    config = TaxonomyConfig(
        colors=_parse_colors(raw["colors"]),
        levels=raw["levels"],
        scoring_rules=_parse_scoring(raw["scoring"]),
        categories=categories,  # NEW: hierarchical structure
        techniques=techniques,  # LEGACY: flat list
        referee_stop_types=_parse_referee_stops(raw["referee_stop_types"]),
        video=_parse_video(raw["video"]),
        athlete_a_label=sport_meta.get("athlete_a_label", "AKA"),
        athlete_b_label=sport_meta.get("athlete_b_label", "AO"),
        scoring_engine=scoring_engine,  # NEW: unified scoring engine
        # Combinatorial Engine (v1.0): base+stance → official name resolution.
        # Empty dict for sports without combinatorial taxonomy (zero impact).
        combinatorial_map=raw.get("combinatorial_map", {}),
        auto_score=raw.get("auto_score", {}),  # DEPRECATED: kept for compatibility
    )
    return config, sport_meta

