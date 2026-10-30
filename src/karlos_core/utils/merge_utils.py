"""Shared utility functions for merging overlapping time intervals
and parsing combinatorial level strings.

Used by ExportManager, AnnotationFlowController, and EditAnnotationPopup
to avoid duplicating merge and parse logic across the codebase.
"""

from __future__ import annotations

from typing import Sequence

from karlos_core.models.annotation import Annotation


def merge_referee_stop_intervals(
    records: Sequence[Annotation],
    fps: float,
    *,
    end_before: int | None = None,
) -> float:
    """Compute the total duration of merged REFEREE STOP intervals.

    Both AKA and AO tag their own Referee Stop for the same real-world
    pause, so summing their individual durations double-counts it.
    This merges overlapping/touching intervals into one timeline
    before computing total stopped seconds.

    Args:
        records: All annotation records (both athletes).
        fps: Frames per second for the video.
        end_before: If set, only consider intervals whose f_end is
            strictly less than this frame index (used for per-annotation
            active-play calculation).

    Returns:
        Total stopped time in seconds (merged, no double-counting).
    """
    intervals = sorted(
        (
            (r.f_start, r.f_end)
            for r in records
            if r.category == "REFEREE STOP"
            and (end_before is None or r.f_end < end_before)
        ),
        key=lambda iv: iv[0],
    )
    if not intervals or fps <= 0:
        return 0.0

    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    total_frames = sum(end - start for start, end in merged)
    return total_frames / fps


def parse_combined_level(tech_level: str) -> dict[str, str]:
    """Parse a combined level string into its individual components.

    The combined string format is: "Stance: X | Level: Y | Action: Z"
    (or any subset of these dimensions). This function extracts each
    component and returns a dict with keys: stance, level, action,
    and any other unrecognised segments stored under "raw".

    Used by both AnnotationFlowController.on_mark_end() and
    EditAnnotationPopup._on_save() to ensure consistent parsing.

    Args:
        tech_level: The combined level string (e.g. "Stance: Lead | Level: Jodan | Action: Direct").

    Returns:
        Dict with parsed components. Keys present only if found:
        - "stance": The stance value (e.g. "Lead", "Rear")
        - "level": The combat level (e.g. "Jodan", "Chudan")
        - "action": The action type (e.g. "Direct", "Counter")
        - "raw": Any segments that didn't match known prefixes
    """
    result: dict[str, str] = {}
    if not tech_level:
        return result

    for segment in tech_level.split(" | "):
        segment = segment.strip()
        if segment.startswith("Stance: "):
            result["stance"] = segment[len("Stance: "):]
        elif segment.startswith("Level: "):
            result["level"] = segment[len("Level: "):]
        elif segment.startswith("Action: "):
            result["action"] = segment[len("Action: "):]
        elif segment.startswith("Target: "):
            result["target"] = segment[len("Target: "):]
        elif segment.startswith("Contact: "):
            result["contact"] = segment[len("Contact: "):]
        elif segment.startswith("Limb: "):
            result["limb"] = segment[len("Limb: "):]
        elif segment.startswith("Follow-up: "):
            result["follow_up"] = segment[len("Follow-up: "):]
        elif segment.startswith("Sanction: "):
            result["sanction"] = segment[len("Sanction: "):]
        elif segment.startswith("Reason: "):
            result["reason"] = segment[len("Reason: "):]
        elif ": " in segment:
            # Una pregunta que el programa no conoce. Antes iba a "raw", que
            # nadie leia, y la respuesta se perdia sin avisar. Ahora vuelve
            # con su nombre en "extra".
            pregunta, valor = segment.split(": ", 1)
            result.setdefault("extra", {})[pregunta.strip()] = valor.strip()
        else:
            # Unrecognised segment — store as raw
            result.setdefault("raw", "")
            if result["raw"]:
                result["raw"] += " | "
            result["raw"] += segment

    return result


def migrate_legacy_combined_levels(records: Sequence[Annotation]) -> int:
    """Migrate annotations whose level still holds a raw combined string.

    Sessions created by old builds stored e.g.
    "Stance: Lead | Target: High | Action: Direct" directly in
    Annotation.level. This maps each component to the same fields
    AnnotationFlowController.on_mark_end() uses (stance/target →
    sport_specific_data, action → action_type) and keeps only the clean
    level (or the Feint limb) in ann.level. Records are mutated in place.

    Returns:
        Number of records migrated.
    """
    migrated = 0
    for ann in records:
        if ann.level and " | " in ann.level:
            parsed = parse_combined_level(ann.level)
            if parsed.get("stance") and not ann.stance:
                ann.stance = parsed["stance"]
            if parsed.get("target") and not ann.target:
                ann.target = parsed["target"]
            if parsed.get("action") and not ann.sport_specific_data.get("action_type"):
                ann.sport_specific_data["action_type"] = parsed["action"]
            guardar_respuestas_extra(ann.sport_specific_data, parsed)
            ann.level = parsed.get("level") or parsed.get("limb") or ""
            migrated += 1
    return migrated


def guardar_respuestas_extra(datos: dict, parsed: dict) -> None:
    """Llevar a los datos de la fila las respuestas sin columna propia.

    Van con el prefijo de `formato.PREFIJO_PREGUNTA`, y de ahi a
    su columna en el CSV. Es el unico sitio que lo hace: la anotacion
    nueva, la editada y la migrada pasan todas por aqui.
    """
    from karlos_core.formato import PREFIJO_PREGUNTA
    for pregunta, respuesta in (parsed.get("extra") or {}).items():
        if respuesta:
            datos[f"{PREFIJO_PREGUNTA}{pregunta}"] = respuesta

