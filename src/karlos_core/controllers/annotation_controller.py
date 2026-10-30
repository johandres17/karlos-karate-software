"""Annotation controller — Main orchestrator.

Orchestrates AnnotationFlowController, FightSessionController,
VideoManager, ExportManager, and SessionManager. Handles wiring,
video I/O, toolbar, keyboard shortcuts, session persistence, and
XLSX export.

Desde la fase F3.7 (decisión 0004) la clase reúne mixins por
responsabilidad, cada uno en ``controllers/anotador/``: el árbol de
preguntas, el modo asistido, las paradas, los combates concluidos, la
revisión, la anotación, las sesiones y las salidas. Aquí quedan la construcción y el
cableado de la ventana.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QUndoStack

from karlos_core.controllers.annotation_flow_controller import (
    AnnotationFlowController,
)
from karlos_core.controllers.anotador.anotacion import AnotacionMixin
from karlos_core.controllers.anotador.asistido import AsistidoMixin
from karlos_core.controllers.anotador.estudio import EstudioMixin
from karlos_core.controllers.anotador.exportacion import ExportacionMixin
from karlos_core.controllers.anotador.guia import GuiaMixin
from karlos_core.controllers.anotador.paradas import ParadasMixin
from karlos_core.controllers.anotador.revision import RevisionMixin
from karlos_core.controllers.anotador.sesiones import SesionesMixin
from karlos_core.controllers.anotador.tiempo_movimiento import TiempoMovimientoMixin
from karlos_core.controllers.fight_session_controller import FightSessionController
from karlos_core.controllers.foul_controller import FoulController
from karlos_core.controllers.navigation_controller import NavigationController
from karlos_core.controllers.session_manager import SessionManager
from karlos_core.controllers.shortcut_controller import ShortcutController
from karlos_core.controllers.video_manager import VideoManager
from karlos_core.models.state import AnnotationStateMachine, FightSession
from karlos_core.models.technique import TaxonomyConfig
from karlos_core.utils.app_logging import get_logger
from karlos_core.views.main_window import MainWindow
from karlos_core import catalogo, identidad

# Lo que vivía en este módulo y se movió al partirlo (F3.7) se sigue
# pudiendo importar desde aquí.
from karlos_core.controllers.anotador.revision import siguiente_anotacion  # noqa: F401

_log = get_logger(__name__)


class AnnotationController(
        TiempoMovimientoMixin, GuiaMixin, AsistidoMixin, ParadasMixin, EstudioMixin,
        RevisionMixin, AnotacionMixin, SesionesMixin, ExportacionMixin, QObject):
    """Orchestrator wiring all MVC components.

    Delegates annotation flow to AnnotationFlowController and fight
    session management to FightSessionController. This class focuses
    on initialization, signal wiring, toolbar, shortcuts, video I/O,
    session persistence, and XLSX export.
    """

    def __init__(
        self,
        config: TaxonomyConfig,
        sport_meta: Optional[dict[str, str]] = None,
        bout_info: Optional[dict[str, str]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._colors = config.colors
        self._sport_meta = sport_meta or {}
        # El deporte que se anota, para todo lo que lo pide al catálogo
        # (decisión 0004).
        catalogo.establecer(self._sport_meta.get("id", "karate"))
        self.__bout_info: dict[str, str] = bout_info or {}

        self.video_manager = VideoManager(config.video)
        self.state_machine = AnnotationStateMachine()
        # Las salidas son del deporte (decision 0004).
        self.export_manager = catalogo.activo().salidas().exportador()
        self.session_manager = SessionManager()
        self.undo_stack = QUndoStack(self)
        self._save_timer: Optional[QTimer] = None

        self.sessions: list[FightSession] = []
        self.active_session_idx: int = -1
        self._restoring_session: bool = False
        self._doing_save: bool = False
        self._focus_mode: bool = False
        self._folder_path: str = ""  # set by _load_sessions_from_folder

        self.window = MainWindow(config, self._sport_meta)
        self._video_path: Optional[str] = None

        # Wire closeEvent → save + release session lock (Cmd+Q / window close button)
        def _on_close() -> None:
            if not self._video_path:
                return
            self._save_session()  # guaranteed synchronous, waits for write
            active = self.session_manager.get_active_round(self._video_path)
            eid = active["evaluator_id"] if active else "default"
            occ = active["occasion"] if active else 1
            self.session_manager.release_lock(
                self._video_path, eid, occ
            )
        self.window._close_callback = _on_close

        self.flow_controller = AnnotationFlowController(
            video_manager=self.video_manager,
            state_machine=self.state_machine,
            window=self.window,
            annotation_panel=self.window.annotation_panel,
            table_view=self.window.table_view,
            undo_stack=self.undo_stack,
            bout_info=self.__bout_info,
            colors=self._colors,
            config=config,
            video_path_callback=lambda: self._video_path,
            parent=self,
        )
        self.fight_controller = FightSessionController(
            video_manager=self.video_manager,
            video_panel=self.window.video_panel,
            annotation_panel=self.window.annotation_panel,
            table_view=self.window.table_view,
            sport_meta=self._sport_meta,
            parent=self,
        )

        self.flow_controller.annotation_created.connect(self._on_annotation_created)
        self.flow_controller.set_sport_id(self._sport_meta.get("id", "karate"))
        self.window.table_view.set_sport_id(self._sport_meta.get("id", "karate"))
        self.fight_controller.fight_markers_changed.connect(self._schedule_save)
        self.fight_controller.fight_markers_changed.connect(self._sync_ui_to_state)
        self.fight_controller.asalto_marcado.connect(self._al_marcar_asalto)
        self.fight_controller.falta_el_inicio.connect(self._avisar_sin_inicio)
        self._enganchar_reglas_de_asaltos()

        # ── Undo/Redo → auto-save & FightSession sync ────────────
        self.undo_stack.indexChanged.connect(self._on_undo_stack_changed)

        # ── Foul Controller (WKF progressive penalties) ─────────
        self.foul_controller = FoulController(
            table_view=self.window.table_view,
            undo_stack=self.undo_stack,
            window=self.window,
            annotation_panel=self.window.annotation_panel,
            video_manager=self.video_manager,
            bout_info=self.__bout_info,
            parent=self,
        )
        self.foul_controller.foul_registered.connect(self._schedule_save)

        # ── Sub-controllers (extracted from this God Object) ───
        self._asaltos = None          # los marca el evaluador al abrir el vídeo
        self._fases = None            # y las fases del tiempo-movimiento, donde las hay
        self._arbol_listo = None
        self._aviso_sin_fin: tuple | None = None   # (tecla, pendiente) que ya aviso de una accion sin [O]
        self._arbol = None
        self._pro_fin = None
        self.shortcuts = ShortcutController(
            window=self.window,
            flow_controller=self.flow_controller,
            fight_controller=self.fight_controller,
            video_manager=self.video_manager,
            undo_stack=self.undo_stack,
            config=config,
            on_fight_end=self._on_fight_end_handler,
            on_toggle_focus=self._toggle_focus_mode,
            on_export_xlsx=self._export_xlsx,
            on_open_video=self._open_video,
            on_set_frame_start=lambda: self._set_selected_frame("start"),
            on_set_frame_end=lambda: self._set_selected_frame("end"),
            on_next_annotation=lambda: self._tab_accion(1),
            on_prev_annotation=lambda: self._tab_accion(-1),
            on_mark_start=self._marcar_inicio,
            on_mark_end=self._marcar_fin,
            on_split=self._dividir_aqui,
            on_undo=self._deshacer,
            on_guided_key=self._guia_tecla,
            on_guided_back=self._guia_atras,
            on_marcar_puntuacion=self._marcar_puntuacion,
            on_intercambio=self._ir_a_intercambio,
            on_fase=self._marcar_fase if self._hace_tiempo_movimiento() else None,
            on_quitar_fase=self._quitar_fase,
        )
        self.navigation = NavigationController(
            window=self.window,
            video_manager=self.video_manager,
            state_machine=self.state_machine,
        )

        self._wire_project_hub()
        self._wire_video_panel()
        self._wire_annotation_panel()
        self._wire_toolbar()
        self.shortcuts.register_all()
        self._wire_seek_bindings()
        self._wire_edit_binding()
        self._wire_match_report()

        # Wire "Back to Hub" button → cleanup + navigation
        self.window._tb_layout.itemAt(0).widget().clicked.disconnect()
        self.window._tb_layout.itemAt(0).widget().clicked.connect(self._on_back_to_hub)

        self.video_manager.frame_changed.connect(self._on_frame_changed)
        self.video_manager.playback_toggled.connect(self.window.video_panel.update_play_button)
        self.video_manager.video_loaded.connect(self._on_video_loaded)
        self.video_manager.video_error.connect(self._on_video_error)


    # ------------------------------------------------------------------
    # Active Round helpers (replaces self._evaluator_id / self._occasion)
    # ------------------------------------------------------------------

    def _active_evaluator_id(self) -> str:
        if not self._video_path:
            return "default"
        active = self.session_manager.get_active_round(self._video_path)
        return active["evaluator_id"] if active else "default"

    def _active_occasion(self) -> int:
        if not self._video_path:
            return 1
        active = self.session_manager.get_active_round(self._video_path)
        return active["occasion"] if active else 1

    @property
    def _bout_info(self) -> dict[str, str]:
        return self.__bout_info

    @_bout_info.setter
    def _bout_info(self, value: dict[str, str]) -> None:
        self.__bout_info = value
        if hasattr(self, 'flow_controller') and self.flow_controller is not None:
            self.flow_controller._bout_info = value

    def _wire_match_report(self) -> None:
        self.window.project_hub.session_right_clicked.connect(self._on_view_report)
        self.window.project_hub.session_view_report.connect(self._on_view_report)
        self.window.match_report.back_to_hub_requested.connect(self._on_back_to_hub)
        self.window.match_report.export_pdf_requested.connect(self._on_export_pdf)

    def _wire_project_hub(self) -> None:
        hub = self.window.project_hub
        hub.load_folder_requested.connect(self._on_load_folder)
        hub.export_dataset_requested.connect(self._on_export_unified_dataset)
        hub.session_double_clicked.connect(self._on_session_selected)
        hub.delete_session_requested.connect(self._on_delete_session)
        hub.load_folder_from_path.connect(self._on_load_folder_from_path)
        hub.export_selected_requested.connect(self._on_export_selected)
        hub.edit_bout_info_requested.connect(self._on_edit_bout_info_from_hub)
        hub.compare_evaluators_requested.connect(self._on_compare_evaluators)
        hub.round_changed_requested.connect(self._on_round_changed)
        hub.new_round_requested.connect(self._on_new_round)
        hub.manage_rounds_requested.connect(self._on_manage_rounds)
        hub.volver_al_inicio.connect(self._volver_al_inicio)
        hub.cargar_dados.connect(self._cargar_datos_de_fila)
        hub.marcar_concluido.connect(self._marcar_concluido)
        hub.borrar_anotaciones.connect(self._borrar_anotaciones)

    def _wire_video_panel(self) -> None:
        vp = self.window.video_panel
        vp.play_toggled.connect(self.video_manager.toggle_play)
        vp.speed_changed.connect(self.video_manager.set_speed)
        self.window.annotation_panel.athlete_changed.connect(self._atleta_cambiado) \
            if hasattr(self.window.annotation_panel, "athlete_changed") else None
        vp.volume_changed.connect(self.video_manager.set_volume)
        vp.mute_toggled.connect(self.video_manager.set_muted)
        vp.slider_moved.connect(self.video_manager.goto)
        vp.step_requested.connect(self.video_manager.step)
        vp.mark_start_requested.connect(self._on_mark_start_with_ui)
        vp.mark_end_requested.connect(self._on_mark_end_with_ui)
        vp.fight_start_requested.connect(self._on_fight_start_with_ui)
        vp.fight_end_requested.connect(self._on_fight_end_handler)
        vp.wheel_scrolled.connect(self.video_manager.accumulate_wheel)
        # Arrastrando la lupa llegan decenas de posiciones por segundo y
        # cada una costaba un salto de 80 ms: se encolaban y la imagen
        # iba detras del raton. `arrastrar` atiende solo la ultima.
        vp.zoom_bar.frame_pedido.connect(self.video_manager.arrastrar)
        self.window.guided_panel.opcion_elegida.connect(self._guia_elegir)

    def _wire_annotation_panel(self) -> None:
        self.window.annotation_panel.technique_clicked.connect(self.flow_controller.on_technique_clicked)
        self.window.annotation_panel.foul_requested.connect(self.foul_controller.register_foul)

    def _wire_toolbar(self) -> None:
        """Los botones de la barra que se usan anotando.

        Se quitaron tres que no llevaban a ningun sitio nuevo:

        - «Abrir Vídeo» — al anotador se entra desde el hub, con el video
          ya elegido. Queda [Ctrl+O] para el caso raro.
        - «Registro completo» — abria en una ventana aparte el mismo log
          que ya esta acoplado a la derecha.
        """
        i18n = self._i18n
        self.window.add_toolbar_button(i18n.t("toolbar.bout_info"), self._edit_bout_info)
        # «Análise…» vuelve a la pantalla inicial para elegir qué se analiza.
        if self._hace_tiempo_movimiento():
            self.window.add_toolbar_button(i18n.t("toolbar.analise"), self._volver_al_inicio)
            panel = self.window.panel_fases
            panel.fase_pedida.connect(self._marcar_fase)
            panel.quitar_pedido.connect(self._quitar_fase)
            panel.numero_de_asaltos.connect(self._elegir_numero_de_asaltos)
            panel.asalto_pulsado.connect(self._al_pulsar_asalto)
            panel.inicio_pedido.connect(self._on_fight_start_with_ui)
            panel.fin_pedido.connect(self._on_fight_end_handler)
            panel.borrar_asalto_pedido.connect(self._borrar_asalto)
        self.window.add_toolbar_button(i18n.t("pro.importar"), self._cargar_csv_combate)
        self.window.add_toolbar_button(i18n.t("pro.exportar"), self._export_xlsx)
        self.window.add_toolbar_button(i18n.t("toolbar.view_report"), self._on_view_current_report)

    def _wire_seek_bindings(self) -> None:
        self.window.table_view.seek_requested.connect(self.video_manager.goto)

    def _wire_edit_binding(self) -> None:
        self.window.table_view.edit_requested.connect(self._on_edit_annotation)
        self.window.table_view.registros_cambiaron.connect(self._refrescar_log)
        self.window.log_compacto.fila_pedida.connect(self._ir_a_registro)
        self.window.log_compacto.editar_pedida.connect(self._on_edit_annotation)
        self.window.log_compacto.borrar_pedida.connect(self._borrar_anotacion)
        self.window.log_compacto.tabla_pedida.connect(
            self.window.abrir_registro_completo)
        self.window.log_compacto.limpiar_pedida.connect(self._limpiar_registro)

    @property
    def _i18n(self):
        from karlos_core.utils.i18n import I18n
        return I18n()

    def show(self) -> None:
        self.window.show()
        self._auto_load_recent_folder()

    def _auto_load_recent_folder(self) -> None:
        # La misma que anuncia la pantalla de inicio (utils/recientes), en
        # los ajustes de la edición (decisión 0006).
        import os as _os1
        from karlos_core.utils import recientes
        folder = recientes.carpeta_de_arranque(identidad.ajustes())
        if folder is not None:
            self._load_sessions_from_folder(folder)
            self.window.set_status_message(f"Carregado automaticamente: {_os1.path.basename(folder)}")

    def close(self) -> None:
        self.video_manager.release(); self.window.close()
