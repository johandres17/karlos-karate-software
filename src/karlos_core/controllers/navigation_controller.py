"""View-navigation orchestrator for KARLOS ANNOTATOR.

Extracted from AnnotationController.  Handles transitions between
the Project Hub, Annotation Workspace, and Match Report, plus all
cleanup logic when leaving the workspace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from karlos_core.formato import PRIMERO

if TYPE_CHECKING:
    from karlos_core.controllers.video_manager import VideoManager
    from karlos_core.models.state import AnnotationStateMachine, FightSession
    from karlos_core.views.annotation_panel import AnnotationPanelView
    from karlos_core.views.annotations_table import AnnotationsTableView
    from karlos_core.views.main_window import MainWindow
    from karlos_core.views.project_hub import ProjectHubView
    from karlos_core.views.video_panel import VideoPanelView


class NavigationController:
    """Manages Hub ↔ Workspace ↔ Report transitions and cleanup.

    Keeps the annotation workspace state tidy when the user navigates
    away (stop video, release resources, reset state machine, clear).
    """

    def __init__(
        self,
        window: MainWindow,
        video_manager: VideoManager,
        state_machine: AnnotationStateMachine,
    ) -> None:
        self._win = window
        self._video = video_manager
        self._sm = state_machine

    # ------------------------------------------------------------------
    # Simple view switching
    # ------------------------------------------------------------------

    def show_hub(self) -> None:
        """Navigate to the Project Hub, hiding annotation docks."""
        self._win.tech_dock.hide()
        self._win._log_splitter.setVisible(False)
        self._win.navigate_to_hub()

    def show_annotator(self) -> None:
        """Navigate to the Annotation Workspace, showing docks."""
        self._win.tech_dock.show()
        self._win._log_splitter.setVisible(True)
        self._win.navigate_to_workspace()
        # ── BUG FIX: Force-refresh fight label when returning to workspace ──
        # The fight_start/fight_end values persist in VideoManager, but the UI
        # label may not repaint if no frame_changed signal fires after navigation.
        # This ensures the label always reflects the current VideoManager state.
        vm = self._video
        self._win.video_panel.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
        self._win.video_panel.update_marks_label(vm.ann_start, vm.ann_end)
        print(f"[DEBUG] show_annotator: fight_start={vm.fight_start}, fight_end={vm.fight_end}")

    def show_report(self) -> None:
        """Navigate to the Match Report, hiding docks."""
        self._win.tech_dock.hide()
        self._win._log_splitter.setVisible(False)
        self._win.navigate_to_report()

    # ------------------------------------------------------------------
    # Full cleanup + return to Hub
    # ------------------------------------------------------------------

    def back_to_hub(
        self,
        sessions: list[FightSession],
        active_session_idx: int,
        annotation_panel: AnnotationPanelView,
        table_view: AnnotationsTableView,
    ) -> None:
        """Save state, release video, reset UI, and return to Hub.

        Returns the updated active_session_idx (will be -1 after
        cleanup) so the caller can propagate it.
        """
        self._video.stop()
        self._video.release()
        self._sm.reset()
        table_view.clear_all()
        annotation_panel.set_athlete(PRIMERO)
        # lock_athlete may not exist on all panel variants
        try:
            annotation_panel.lock_athlete(False)
        except AttributeError:
            pass
        self._win.video_panel.update_info_label(0, 0, 0.0)
        self._win.video_panel.update_fight_label(None, None, None)
        self._win.video_panel.update_marks_label(None, None)
        self._win.project_hub.set_sessions(sessions)
        self.show_hub()
