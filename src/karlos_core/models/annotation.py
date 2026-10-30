"""Annotation data model for KARLOS ANNOTATOR.

Defines the Annotation dataclass representing a single annotated
technique or match-state event in a combat-sport bout.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Annotation:
    """A single ground-truth annotation record for a combat-sport technique or event.

    Attributes:
        athlete: Athlete identifier ("AKA" or "AO", or sport-specific labels).
        category: High-level category (e.g., "ATTACK", "DEFENSE", "REFEREE STOP").
        subcategory: Technique group (e.g., "HAND TECHNIQUES", "FOOT TECHNIQUES").
        technique: Full technique name including level/type (e.g., "Gyaku-tsuki Jodan").
        level: Target level if applicable ("Jodan", "Chudan", or "").
        score: Scoring outcome code ("IPPON", "WAZA", "YUKO", "NONE", "FOUL", or "").
        f_start: Start frame index.
        f_end: End frame index.
        duration_s: Duration in seconds.
        fight_f_start: Fight segment start frame (optional).
        fight_f_end: Fight segment end frame (optional).
        fight_dur_s: Fight segment duration in seconds (optional).
        active_play_s: Active play time in seconds (optional).
        video_file: Source video filename.
        timestamp: ISO format timestamp of annotation creation.
        notes: Free-text annotator notes.
        status: Record status ("Ready", "Error", "Pending").
        features: Reserved dictionary for future feature extraction data.
    """

    athlete: str
    category: str
    subcategory: str
    technique: str
    level: str = ""
    score: str = ""
    f_start: int = 0
    f_end: int = 0
    # AUSENTE (None) cuando no se han marcado los extremos: en el analisis
    # tecnico-tactico la accion es un evento y no tiene duracion que medir
    # (decision 0008). Cero significaria «dura cero», que es falso.
    duration_s: Optional[float] = 0.0
    fight_f_start: int | None = None
    fight_f_end: int | None = None
    fight_dur_s: float | None = None
    active_play_s: float | None = None
    video_file: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""
    status: str = "Ready"
    features: dict[str, Any] = field(default_factory=dict)
    # Bout metadata
    bout_id: str = ""
    bout_event: str = ""
    bout_number: str = ""
    bout_round: str = ""
    athlete_a_name: str = ""
    athlete_a_origin: str = ""
    athlete_b_name: str = ""
    athlete_b_origin: str = ""
    weight_category: str = ""
    round: int = 0
    # Sport-specific data (generic extensible dictionary)
    sport_specific_data: dict[str, Any] = field(default_factory=dict)

    # ── Convenience properties for backward compatibility ────────────
    @property
    def stance(self) -> str:
        """Kickboxing: Lead/Rear. Returns '' if not present."""
        return self.sport_specific_data.get("stance", "")
    
    @stance.setter
    def stance(self, value: str) -> None:
        """Setter for backward compatibility with existing code."""
        if value:
            self.sport_specific_data["stance"] = value
        elif "stance" in self.sport_specific_data:
            del self.sport_specific_data["stance"]
    
    @property
    def target(self) -> str:
        """Kickboxing: High/Middle/Low. Returns '' if not present."""
        return self.sport_specific_data.get("target", "")
    
    @target.setter
    def target(self, value: str) -> None:
        """Setter for backward compatibility with existing code."""
        if value:
            self.sport_specific_data["target"] = value
        elif "target" in self.sport_specific_data:
            del self.sport_specific_data["target"]

    def to_csv_row(self, row_id: int, sequence_id: str = "") -> dict[str, Any]:
        """Convert annotation to a flat dictionary suitable for CSV/Excel export.

        Returns a denormalised flat row with keys matching ANNOTATION_COLUMNS
        from ExportManager. Bout metadata (Bout_Event, Bout_Phase, etc.) is
        injected separately by the export manager — this method returns only
        the annotation-specific fields.

        **FASE 3 REFACTOR**: Implements dynamic flattening of sport_specific_data.
        All keys in sport_specific_data are extracted and prefixed with "Sport_"
        to create independent columns (e.g., Sport_stance, Sport_target).

        **v6.2 ML-ready**: If ``sequence_id`` is not provided explicitly, the
        method will attempt to read it from ``sport_specific_data["sequence_id"]``.
        This allows the auto-assigned Sequence_ID (from AnnotationFlowController)
        to flow through to the CSV export automatically.

        Args:
            row_id: Sequential row identifier.
            sequence_id: Temporal sequence group identifier (e.g. "SEQ_001").
                If empty, falls back to sport_specific_data.get("sequence_id", "").

        Returns:
            Dictionary with annotation fields keyed for the flat dataset.
        """
        # «Scored» si la puntuación vale algo en el deporte que se anota: lo
        # dice su reglamento (decisión 0007). Antes era una lista de códigos
        # del karate y del kickboxing, y un punto de taekwondo o un golpe
        # conectado de boxeo salían «No_Score».
        from karlos_core import catalogo
        action_result = ("Scored" if catalogo.activo().reglamento.puntos(self.score) > 0
                         else "No_Score")

        # ── v6.2: Auto-populate Sequence_ID from sport_specific_data ──
        # If not explicitly passed, try to read from the ML-ready field.
        if not sequence_id:
            sequence_id = self.sport_specific_data.get("sequence_id", "")

        row = {
            # ── KPIs Tácticos (orden especificado por el cliente) ────────
            "Timestamp": self.timestamp,
            "Athlete": self.athlete,
            "Category": self.category,
            "Technique": self.technique,
            "Level": self.level,
            "Modifier": self.stance,          # Mapea stance → Modifier (backward compat)
            "Score": self.score,
            "Sequence_ID": sequence_id,       # v6.2: auto-assigned temporal grouping
            "Action_Result": action_result,   # "Scored" / "No_Score"
            # ── Columnas Técnicas Adicionales (trazabilidad del video) ──
            "subcategory": self.subcategory,
            "target": self.target,            # Backward compat (also in sport_specific_data)
            "f_start": self.f_start,
            "f_end": self.f_end,
            "duration_s": self.duration_s,
            "notes": self.notes,
            "round": self.round,
            "bout_id": self.bout_id,
            "video_file": self.video_file,
            "id": row_id,
        }

        # ── FASE 3: Dynamic Flattening of sport_specific_data ────────────
        # Iterate over all keys in sport_specific_data and create Sport_* columns.
        # This ensures extensibility: new sports can add custom fields without
        # modifying the core Annotation model or ExportManager logic.
        for key, value in self.sport_specific_data.items():
            # Prefix with "Sport_" to avoid collisions with core columns
            column_name = f"Sport_{key}"
            # Convert value to string for CSV compatibility (handles None, int, float, str)
            row[column_name] = str(value) if value is not None else ""

        return row
