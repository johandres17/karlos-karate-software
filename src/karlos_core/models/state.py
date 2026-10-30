"""State machine and flow control for KARLOS ANNOTATOR annotation workflow.

Enforces a strict annotation sequence:
    IDLE -> STARTED -> TECHNIQUE_SELECTED -> ENDED -> IDLE

Referee Stop events bypass the start/end flow and register immediately.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class FightSession:
    """Represents a single fight video session in a multi-fight project.

    Tracks the video path, analysis status (0/2, 1/2, 2/2 athletes),
    annotation records, and source video metadata for the Hub table.

    Attributes:
        id: Unique session identifier within the project.
        video_path: Absolute filesystem path to the video file.
        video_name: Display name derived from the video filename.
        status: Current analysis status:
            - "Pending": Not yet opened.
            - "In Progress": Currently being annotated.
            - "Completed": Both athletes analyzed (2/2 passes).
        annotations: List of Annotation records for this session.
        resolution: Display resolution string (e.g. "1920x1080").
        fps: Source video frames per second.
        duration_s: Total video duration in seconds.
    """

    id: int
    video_path: str
    video_name: str = ""
    status: str = "Pending"
    annotations: list[Any] = field(default_factory=list)
    resolution: str = ""
    fps: float = 0.0
    duration_s: float = 0.0
    bout_metadata: dict = field(default_factory=dict)
    # Lo que es del vídeo y no de la pasada (7 y 8-10-2026): las marcas de
    # los asaltos y las de las fases del tiempo-movimiento, tal como van en
    # la sesión guardada. None donde el deporte no las tiene.
    asaltos: Optional[list] = None
    fases: Optional[list] = None

    def __post_init__(self) -> None:
        """Derive video_name from path if not explicitly set."""
        if not self.video_name and self.video_path:
            self.video_name = Path(self.video_path).name


class AnnotationState(Enum):
    """Valid states in the annotation workflow state machine.

    IDLE:
        Awaiting the user to press [I] (mark START frame).
    STARTED:
        START frame has been marked; awaiting technique selection.
    TECHNIQUE_SELECTED:
        A technique (with optional level/score) has been chosen;
        awaiting [O] (mark END frame).
    """

    IDLE = auto()
    STARTED = auto()
    TECHNIQUE_SELECTED = auto()


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current: AnnotationState, attempted_action: str) -> None:
        self.current = current
        self.attempted_action = attempted_action
        super().__init__(
            f"Cannot perform '{attempted_action}' in state '{current.name}'."
        )


@dataclass
class AnnotationStateMachine:
    """Strict state machine governing the annotation workflow.

    Attributes:
        state: Current annotation state.
        f_start: Frame index where the current technique starts.
        pending_technique: Name of the technique awaiting END marker.
        pending_level: Target level if applicable.
        pending_score: Scoring outcome code if applicable.
        pending_category: High-level category of the pending technique.
        pending_subcategory: Technique group of the pending technique.

    Example:
        >>> sm = AnnotationStateMachine()
        >>> sm.mark_start(142)
        >>> sm.state  # AnnotationState.STARTED
        >>> sm.select_technique("Gyaku-tsuki", "Jodan", "IPPON", "ATTACK", "HAND TECHNIQUES")
        >>> sm.state  # AnnotationState.TECHNIQUE_SELECTED
        >>> sm.mark_end(180)
        >>> sm.state  # AnnotationState.IDLE
    """

    state: AnnotationState = AnnotationState.IDLE
    f_start: int = 0
    pending_technique: str = ""
    pending_level: str = ""
    pending_score: str = ""
    pending_category: str = ""
    pending_subcategory: str = ""
    pending_referee_stop_type: str = ""
    is_referee_stop: bool = False

    def mark_start(self, frame: int) -> None:
        """Record the START frame and transition to STARTED state.

        Args:
            frame: Current video frame index.

        Raises:
            StateTransitionError: If already in STARTED or TECHNIQUE_SELECTED.
        """
        self.state = AnnotationState.STARTED
        self.f_start = frame
        self._clear_pending()

    def select_technique(
        self,
        technique: str,
        level: str,
        score: str,
        category: str,
        subcategory: str,
    ) -> None:
        """Record the selected technique and transition to TECHNIQUE_SELECTED.

        Args:
            technique: Full technique name (e.g., "Gyaku-tsuki Jodan").
            level: Target level ("Jodan", "Chudan", or "").
            score: Scoring outcome code ("IPPON", "WAZA", "YUKO", "NONE", "FOUL").
            category: High-level category ("ATTACK", "DEFENSE", etc.).
            subcategory: Technique group name.

        Raises:
            StateTransitionError: If state is not STARTED.
        """
        if self.state != AnnotationState.STARTED:
            raise StateTransitionError(self.state, "select_technique")
        self.state = AnnotationState.TECHNIQUE_SELECTED
        self.pending_technique = technique
        self.pending_level = level
        self.pending_score = score
        self.pending_category = category
        self.pending_subcategory = subcategory
        self.is_referee_stop = False

    def select_referee_stop(self, stop_type: str) -> None:
        """Record a referee stop with its type and transition to TECHNIQUE_SELECTED.

        Args:
            stop_type: The referee stop type name (e.g., "Referee", "VR", "Injury").

        Raises:
            StateTransitionError: If state is not STARTED.
        """
        if self.state != AnnotationState.STARTED:
            raise StateTransitionError(self.state, "select_referee_stop")
        self.state = AnnotationState.TECHNIQUE_SELECTED
        self.pending_referee_stop_type = stop_type
        self.pending_technique = f"Referee Stop - {stop_type}"
        self.pending_level = ""
        self.pending_score = ""
        self.pending_category = "REFEREE STOP"
        self.pending_subcategory = "REFEREE STOP"
        self.is_referee_stop = True

    def mark_end(self) -> None:
        """Consume the pending technique and return to IDLE.

        Raises:
            StateTransitionError: If state is not TECHNIQUE_SELECTED.
        """
        if self.state != AnnotationState.TECHNIQUE_SELECTED:
            raise StateTransitionError(self.state, "mark_end")
        self.state = AnnotationState.IDLE
        self.f_start = 0
        self._clear_pending()

    def can_mark_start(self) -> bool:
        """Check if marking START is allowed in the current state."""
        return self.state == AnnotationState.IDLE

    def can_select_technique(self) -> bool:
        """Check if selecting a technique is allowed in the current state."""
        return self.state == AnnotationState.STARTED

    def can_mark_end(self) -> bool:
        """Check if marking END is allowed in the current state."""
        return self.state == AnnotationState.TECHNIQUE_SELECTED

    def reset(self) -> None:
        """Force-reset the state machine to IDLE, discarding any pending data."""
        self.state = AnnotationState.IDLE
        self.f_start = 0
        self.pending_referee_stop_type = ""
        self.is_referee_stop = False
        self._clear_pending()

    def _clear_pending(self) -> None:
        """Clear all pending technique data."""
        self.pending_technique = ""
        self.pending_level = ""
        self.pending_score = ""
        self.pending_category = ""
        self.pending_subcategory = ""
        self.pending_referee_stop_type = ""
        self.is_referee_stop = False