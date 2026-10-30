
"""Annotation flow sub-controller for KARLOS ANNOTATOR.

Handles the core annotation workflow: mark START, select technique,
mark END, and referee stops. Extracted from the main AnnotationController
to keep it focused and testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from karlos_core.controllers.undo_commands import AddAnnotationCommand
from karlos_core.utils.merge_utils import parse_combined_level
from karlos_core.models.annotation import Annotation
from karlos_core.models.state import StateTransitionError
from karlos_core.models.technique import (
    ScoringEngine,
    TaxonomyConfig,
    Technique,
    TechniqueCategory,
    resolve_combat_action,
)
from karlos_core.views.detail_popup import DetailPopup
from karlos_core.views.referee_stop_popup import RefereeStopPopup
from karlos_core import catalogo
from karlos_core.formato import rival

# ── Kickboxing: techniques with inherent stance ──────────────────
# NOTE: As of v6.3, all kickboxing attacks show Stance (Lead/Rear) and
# Target (High/Middle/Low) in the DetailPopup, so the user selects the
# stance manually. No auto-stance override is needed.
# Aqui vivia la agrupacion automatica en secuencias: las tecnicas
# anotadas a menos de 45 fotogramas de la anterior heredaban su SEQ_xxx,
# salvo las que empezaban secuencia. Retirada el 24-09-2026 con todas
# las demas reglas de tiempo: el programa no agrupa entradas.
#
# Los campos `sequence_counter`, `current_sequence_id` y
# `last_annotation_end` siguen en la sesion guardada para poder abrir
# sesiones antiguas, pero ya no se actualizan ni se usan.




def _t(clave: str, **kw) -> str:
    """El mensaje en el idioma elegido.

    Estaba escrito en ingles a pelo aunque la traduccion existiera, asi
    que en la barra de estado salia «START at frame 1854 — select
    technique» con el resto del programa en portugues.
    """
    from karlos_core.utils.i18n import I18n
    return I18n().t(clave, **kw)


class AnnotationFlowController(QObject):
    """Controls the I→technique→O annotation workflow.

    Signals:
        annotation_created(Annotation): Emitted after a complete annotation
            is added to the table, so the orchestrator can auto-save.
    """

    annotation_created = Signal(object)  # Annotation

    def __init__(
        self,
        video_manager,
        state_machine,
        window,  # MainWindow (for status messages + QMessageBox parent)
        annotation_panel,
        table_view,
        undo_stack,
        bout_info: dict[str, str],
        colors,
        config: TaxonomyConfig,
        video_path_callback,  # callable → str | None
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialize the annotation flow controller.

        Args:
            video_manager: VideoManager instance.
            state_machine: AnnotationStateMachine instance.
            window: MainWindow for status bar and dialog parenting.
            annotation_panel: AnnotationPanelView for athlete/notes.
            table_view: AnnotationsTableView for adding records.
            undo_stack: QUndoStack for reversible commands.
            bout_info: Mutable dict with bout metadata (shared with orchestrator).
            colors: AppColors palette.
            config: Full TaxonomyConfig.
            video_path_callback: Callable returning current video path or None.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._vm = video_manager
        self._sm = state_machine
        self._win = window
        self._ap = annotation_panel
        self._tv = table_view
        self._undo_stack = undo_stack
        self._bout_info = bout_info
        self._colors = colors
        self._config = config
        self._get_video_path = video_path_callback
        self._sport_id: str = "karate"
        # Lo pone el controlador cuando el deporte tiene asaltos: el de una
        # acción es el del fotograma en que empieza, no «el asalto en
        # curso» (se puede volver atrás a completar el primero).
        self.asalto_de = None
        self._fps: float = 30.0

        # ── Last technique cache for "R" repeat ─────────────────
        self._last_technique: Optional[Technique] = None
        self._last_level: str = ""
        self._last_score: str = ""

        # ══════════════════════════════════════════════════════════
        # SEQUENCE_ID Auto-Assignment State (v6.2 — ML-ready)
        # ══════════════════════════════════════════════════════════
        self._sequence_counter: int = 0       # Incremental sequence ID
        self._current_sequence_id: str = ""   # Active sequence ID (e.g., "SEQ_001")
        self._last_annotation_end: int = 0    # End frame of last annotation
        self._last_technique_name: str = ""   # Name of last annotated technique

    # ── Public properties for session persistence ────────────────
    @property
    def sequence_counter(self) -> int:
        return self._sequence_counter

    @property
    def current_sequence_id(self) -> str:
        return self._current_sequence_id

    @property
    def last_annotation_end(self) -> int:
        return self._last_annotation_end

    @property
    def last_technique_name(self) -> str:
        return self._last_technique_name

    def restore_sequence_state(
        self,
        sequence_counter: int = 0,
        current_sequence_id: str = "",
        last_annotation_end: int = 0,
        last_technique_name: str = "",
    ) -> None:
        """Restore sequence-ID state after session recovery.

        Args:
            sequence_counter: The counter value to resume from.
            current_sequence_id: The active sequence ID string.
            last_annotation_end: End frame of the last annotated technique.
            last_technique_name: Name of the last annotated technique.
        """
        self._sequence_counter = sequence_counter
        self._current_sequence_id = current_sequence_id
        self._last_annotation_end = last_annotation_end
        self._last_technique_name = last_technique_name

    def set_sport_id(self, sport_id: str) -> None:
        """Set the sport ID for sport-specific technique formatting."""
        self._sport_id = sport_id

    # ------------------------------------------------------------------
    # Public handlers (wired by orchestrator)
    # ------------------------------------------------------------------

    def on_repeat_last_technique(self) -> None:
        """Repeat last technique with same level/score [R] — skips popup."""
        if self._last_technique is None:
            from karlos_core.utils.i18n import I18n
            self._win.set_status_message(I18n().t("pro.sin_tecnica_anterior"))
            return

        sm = self._sm
        if not sm.can_select_technique():
            QMessageBox.warning(
                self._win, "Missing START", self._teclas("Press [I] to mark START first.")
            )
            return

        technique = self._last_technique
        level = self._last_level
        score = self._last_score

        full_name = (
            f"{technique.name} {level}".strip()
            if level else technique.name
        )

        try:
            sm.select_technique(
                technique=full_name,
                level=level,
                score=score,
                category=technique.group,
                subcategory=technique.category,
            )
        except StateTransitionError as exc:
            self._win.set_status_message(str(exc))
            return

        self._win.set_pending_text(f"Pending END: {full_name}")
        self._win.set_status_message(
            f"Repetir: {full_name} "
            f"[{catalogo.etiqueta(self._ap.athlete)}] — press [O] to confirm"
        )
        self._ap.clear_notes()

    def _teclas(self, mensaje: str) -> str:
        """Las teclas del modo vigente, tambien en las ventanas emergentes."""
        traductor = getattr(self._win, "traducir_teclas", None)
        return traductor(mensaje) if traductor else mensaje

    def on_mark_start(self) -> None:
        """Handle mark START [I] action."""
        vm = self._vm
        sm = self._sm

        if not vm.is_loaded:
            return

        if vm.fight_start is None:
            QMessageBox.warning(
                self._win,
                "Fight Start Required",
                self._teclas(
                    "Please press [F] to mark Fight Start before annotating techniques."),
            )
            return

        vm.mark_annotation_start()
        sm.reset()
        sm.mark_start(vm.current_frame)
        vp = self._win.video_panel
        vp.update_marks_label(vm.ann_start, vm.ann_end)
        self._win.set_pending_text("")
        self._win.set_status_message(
            _t("wf.start", frame=str(vm.ann_start))
        )

    def on_technique_clicked(self, technique: Technique) -> None:
        """Handle technique button click from AnnotationPanelView.

        Args:
            technique: The Technique dataclass instance that was clicked.
        """
        if technique.name == "Referee Stop":
            self._handle_referee_stop()
            return

        sm = self._sm
        if not sm.can_select_technique():
            QMessageBox.warning(
                self._win, "Missing START", self._teclas("Press [I] to mark START first.")
            )
            return

        motivo_escrito = ""
        if technique.name == "Unidentifiable":
            # Con motivo, como en el arbol: por que se pierde imagen es
            # justo lo que se estudia.
            elegido = self._pedir_motivo_no_identificable()
            if elegido is None:
                return
            motivo, motivo_escrito = elegido
            level, score = f"Reason: {motivo}", "NONE"
        elif technique.has_level:
            mode = "technique" if technique.group in ("DEFENSE", "TACTICS", "FOUL") else "full"
            # ── Use ScoringEngine to get auto-score suggestion ──────
            scoring_engine = self._config.scoring_engine
            dlg = DetailPopup(
                tech_name=technique.name,
                has_level=True,
                athlete=self._ap.athlete,
                colors=self._colors,
                levels=self._config.levels,
                scoring_rules=self._config.scoring_rules,
                parent=self._win,
                mode=mode,
                levels_config=technique.levels_config,
                scoring_engine=scoring_engine,
            )
            if dlg.exec() != DetailPopup.Accepted:
                return
            level = dlg.level
            score = dlg.score
        else:
            level = ""
            score = "NONE"

        full_name = (
            f"{technique.name} {level}".strip()
            if level
            else technique.name
        )

        try:
            sm.select_technique(
                technique=full_name,
                level=level,
                score=score,
                category=technique.group,
                subcategory=technique.category,
            )
        except StateTransitionError as exc:
            self._win.set_status_message(str(exc))
            return

        # ── Cache for repeat ────────────────────────────────────
        self._last_technique = technique
        self._last_level = level
        self._last_score = score

        self._win.set_pending_text(f"Pending END: {full_name}")
        self._win.set_status_message(
            _t("stat.tecnica_pendente", tecnica=full_name,
               atleta=catalogo.etiqueta(self._ap.athlete))
        )
        self._ap.clear_notes()
        if motivo_escrito:
            # El «outro» escrito va a las notas, igual que en el asistido.
            self._ap.set_notes(motivo_escrito)

    def _pedir_motivo_no_identificable(self):
        """(motivo, texto) para «Não identificável», o None si se cancela."""
        from PySide6.QtWidgets import QInputDialog
        from karlos_core.models.no_identificable import motivos_no_identificable
        opciones = motivos_no_identificable()
        from karlos_core.utils.i18n import I18n
        pregunta = I18n().t("pro.no_ident_pregunta")
        etiqueta, vale = QInputDialog.getItem(
            self._win, I18n().t("pro.no_ident_titulo"), pregunta,
            [e for e, _ in opciones], 0, False)
        if not vale or not etiqueta:
            return None
        motivo = dict(opciones).get(etiqueta)
        if motivo is None:
            return None
        texto = ""
        if motivo == "Other":
            texto, vale = QInputDialog.getText(
                self._win, I18n().t("pro.no_ident_titulo"), pregunta)
            texto = (texto or "").strip()
            if not vale or not texto:
                return None
        return motivo, texto

    def on_mark_end(self) -> None:
        """Handle mark END [O] action.

        Validates the annotation (END > START) and creates an
        Annotation record if a technique is pending.
        """
        vm = self._vm
        sm = self._sm

        if not vm.is_loaded:
            return

        vm.mark_annotation_end()

        if not sm.can_mark_end():
            self._win.set_status_message(
                _t("stat.fim_sem_tecnica", frame=str(vm.ann_end))
            )
            vm.clear_annotation_markers()
            return

        if vm.ann_start is None or vm.ann_end is None:
            return

        # Un evento empieza y acaba en el mismo fotograma: no hay rango
        # que validar (decision 0008). Lo pone el arbol en el analisis
        # tecnico-tactico, justo antes de cerrar.
        evento = bool(getattr(self, "evento", False))
        self.evento = False          # se consume aqui: vale para esta fila
        if vm.ann_start >= vm.ann_end and not (evento and vm.ann_start == vm.ann_end):
            QMessageBox.warning(
                self._win, "Invalid Range",
                "END frame must be after START frame.",
            )
            return

        # Sin extremos marcados no hay duracion: AUSENTE, no cero (Johan,
        # 16-10-2026). Lo que si queda es el fotograma en que se anoto.
        dur = None if evento else ((vm.ann_end - vm.ann_start) / vm.fps if vm.fps > 0 else 0.0)
        fight_dur = vm.fight_duration_s()

        notes = self._ap.get_notes()
        video_path = self._get_video_path()
        video_filename = Path(video_path).name if video_path else ""

        current_round = int(self._bout_info.get("current_round", 1) or 1)
        if self.asalto_de is not None:
            current_round = self.asalto_de(vm.ann_start or vm.current_frame) or current_round

        # ── Clean technique name & level ─────────────────────
        tech_name = sm.pending_technique
        tech_level = sm.pending_level

        # ── Referee Stop: skip technique-specific validation ──
        # The state machine already set is_referee_stop=True and
        # pending_technique = "Referee Stop - {type}". We must NOT
        # override tech_name with self._last_technique (which may
        # be a Feint from an earlier click), and must NOT run
        # Feint validation or combinatorial resolution.
        motivo_ni = ""
        parsed: dict = {}
        if not sm.is_referee_stop:
            # Use cached technique name (clean, no level suffixes)
            if self._last_technique is not None:
                tech_name = self._last_technique.name
            # Parse combined level string using shared utility
            parsed = parse_combined_level(tech_level)
            # El nivel de la fila sale de las preguntas que SON un nivel (la
            # zona, el miembro de la finta); si la acción no tiene ninguna,
            # se queda sin nivel. La cadena entera no es un nivel. Una cadena
            # sin preguntas dentro («Jodan» a secas) sí lo es, y esa viaja
            # en «raw».
            if parsed and "raw" not in parsed:
                tech_level = ""
            kb_stance = parsed.get("stance", "")
            kb_target = parsed.get("target", "")
            combat_level = parsed.get("level", "")
            combat_action = parsed.get("action", "")
            contacto = parsed.get("contact", "")
            sancion = parsed.get("sanction", "")
            motivo_ni = parsed.get("reason", "")
            # Limb override: Feint stores limb in tech_level
            if parsed.get("limb"):
                tech_level = parsed["limb"]
            # La zona («Target») es el nivel de la fila en cualquier deporte:
            # así llega a la columna de nivel del CSV (decisión 0007). Antes
            # el kickboxing la guardaba solo aparte y el CSV no la tenía.
            if kb_target:
                tech_level = kb_target
            elif kb_stance and self._sport_id == "kickboxing":
                tech_level = ""

            # ── Combinatorial Engine (v6.1): resolve official name ───
            # Karate: base technique + stance → official Japanese name
            # (e.g., Tsuki + Lead → "Kizami Tsuki"). Resolution happens
            # BEFORE persistence so all reports see the resolved name.
            base_technique = ""
            if self._config.combinatorial_map and kb_stance:
                resolved = resolve_combat_action(
                    tech_name, kb_stance, self._config.combinatorial_map
                )
                if resolved != tech_name:
                    base_technique = tech_name
                    tech_name = resolved
            # Karate combinatorial: store clean Jodan/Chudan in level column
            if combat_level:
                tech_level = combat_level

            # ── Validate Feint requires a limb selection ─────────
            if tech_name == "Feint" and not tech_level:
                QMessageBox.warning(
                    self._win, "Missing Limb",
                    "Feint requires specifying the limb: select "
                    "\"Upper Limb\" or \"Lower Limb\".",
                )
                vm.clear_annotation_markers()
                return
        else:
            # Referee Stop: no combinatorial resolution, no Feint validation
            kb_stance = ""
            kb_target = ""
            combat_level = ""
            combat_action = ""
            contacto = ""
            sancion = ""
            base_technique = ""

        # ── Extract Follow-up from Ashi-barai level string ────────
        # Ashi-barai has levels_config with "Action" and "Follow-up".
        # Store the follow-up technique in sport_specific_data for ML.
        ashi_follow_up = ""
        if tech_name == "Ashi-barai" and tech_level:
            for segment in tech_level.split(" | "):
                if segment.startswith("Follow-up: "):
                    ashi_follow_up = segment[len("Follow-up: "):]
                    # Remove Follow-up from the level string (keep only Action)
                    tech_level = tech_level.replace(f" | {segment}", "").replace(segment, "").strip()
                    break

        # ══════════════════════════════════════════════════════════
        # Las reglas del libro de codigos (models/regras.py). Salen del
        # arbitraje de ID30: lo mecanico se hace cumplir aqui, igual
        # para los dos evaluadores; el juicio sigue siendo suyo.
        # ══════════════════════════════════════════════════════════
        if not self._cumple_reglas(sm, vm, tech_name, tech_level, kb_stance):
            return

        # Aqui se agrupaban las anotaciones en secuencias: las tecnicas
        # anotadas a menos de 45 fotogramas de la anterior heredaban su
        # SEQ_xxx. Retirado el 24-09-2026. Era la ultima regla de tiempo
        # que unia entradas, y la mas dificil de ver: no cambiaba las
        # filas, les ponia la misma etiqueta, asi que al exportar salian
        # agrupadas sin que nadie lo hubiera decidido.
        #
        # Ninguna entrada se agrupa con otra. El evaluador marca, el
        # programa registra, y las secuencias se arman despues.

        # ── Build sport_specific_data with ML-ready fields ────────
        sport_data = {
            k: v
            for k, v in {
                "base_technique": base_technique,
                "stance": kb_stance,
                "target": kb_target,
                "action_type": combat_action,
                "contact": contacto,
                "sanction": sancion,
                "reason": motivo_ni,
                "follow_up": ashi_follow_up,
            }.items()
            if v
        }
        # Las respuestas a preguntas sin columna propia: antes se perdian
        # aqui sin avisar.
        from karlos_core.utils.merge_utils import guardar_respuestas_extra
        guardar_respuestas_extra(sport_data, parsed)

        annotation = Annotation(
            athlete=self._ap.athlete,
            category=sm.pending_category,
            subcategory=sm.pending_subcategory,
            technique=tech_name,
            level=tech_level,
            sport_specific_data=sport_data,
            score=sm.pending_score,
            f_start=vm.ann_start,
            f_end=vm.ann_end,
            duration_s=dur,
            round=current_round,
            fight_f_start=vm.fight_start,
            fight_f_end=vm.fight_end,
            fight_dur_s=fight_dur,
            active_play_s=self._compute_active_play(dur or 0.0),
            video_file=video_filename,
            notes=notes,
            status="Ready",
            bout_id=self._bout_info.get("bout_id", ""),
            bout_event=self._bout_info.get("bout_event", ""),
            bout_number=self._bout_info.get("bout_number", ""),
            bout_round=self._bout_info.get("bout_round", ""),
            athlete_a_name=self._bout_info.get("athlete_a_name", ""),
            athlete_a_origin=self._bout_info.get("athlete_a_origin", ""),
            athlete_b_name=self._bout_info.get("athlete_b_name", ""),
            athlete_b_origin=self._bout_info.get("athlete_b_origin", ""),
            weight_category=self._bout_info.get("weight_category", ""),
        )

        self._undo_stack.push(
            AddAnnotationCommand(annotation, self._tv)
        )
        self._ap.clear_notes()

        try:
            sm.mark_end()
        except StateTransitionError:
            pass

        vm.clear_annotation_markers()
        vp = self._win.video_panel
        vp.update_marks_label(vm.ann_start, vm.ann_end)
        self._win.set_pending_text("")
        # Un evento no tiene duracion que enseñar: se dice DONDE quedo
        # anotado, que es el dato que si existe (decision 0008).
        if dur is None:
            s_ = annotation.f_start / vm.fps if vm.fps > 0 else 0.0
            cola = f"(f{annotation.f_start} · {int(s_ // 60)}:{s_ % 60:04.1f})"
        else:
            cola = f"({dur:.2f}s)"
        self._win.set_status_message(
            f"#{len(self._tv.records)} "
            f"{annotation.technique} [{catalogo.etiqueta(annotation.athlete)}] "
            f"{cola}"
        )

        self.annotation_created.emit(annotation)

    # ------------------------------------------------------------------
    # Las reglas del libro de codigos
    # ------------------------------------------------------------------

    def _cumple_reglas(self, sm, vm, tech_name: str, tech_level: str,
                       kb_stance: str) -> bool:
        """Aplicar las reglas mecanicas antes de crear la anotacion.

        Devuelve False cuando la anotacion NO debe crearse (porque se
        rechazo, o porque en vez de crearla se alargo otra). Cada regla
        dice por que, en la barra de estado o en un dialogo con dos
        salidas: nunca un «no» mudo.
        """
        from karlos_core.models import regras

        registros = list(self._tv.records)
        atleta = self._ap.athlete
        f0, f1 = int(vm.ann_start), int(vm.ann_end)
        categoria = sm.pending_category

        def cancelar(mensaje: str) -> bool:
            sm.reset()
            vm.clear_annotation_markers()
            self._win.video_panel.update_marks_label(vm.ann_start, vm.ann_end)
            self._win.set_pending_text("")
            self._win.set_status_message(mensaje)
            return False

        # Aqui se fundian las paradas repetidas y se rechazaba lo
        # anotado dentro de una pausa. Retirado el 24-09-2026: el
        # programa no decide que se anota ni junta filas. Cada marcacion
        # es un registro y el criterio lo pone el evaluador.

        # ── Tsuki sin guardia no existe: es Kizami o Gyaku ──
        if tech_name == "Tsuki" and not kb_stance:
            return cancelar("Tsuki precisa de guarda: Lead → Kizami Tsuki, "
                            "Rear → Gyaku Tsuki. Volte a marcar com a guarda.")

        # ── Fintas ──
        # Aqui habia dos reglas y las dos se retiraron el 24-09-2026, por
        # la misma razon: el programa registra lo observado y no lo juzga
        # ni lo resume.
        #
        # La primera alargaba la finta anterior cuando esta caia dentro
        # de la tanda, y las dos salian en una sola fila. Agrupar al
        # anotar fija por adelantado un criterio que luego no se puede
        # revisar sin volver a ver los combates; agrupar al analizar deja
        # el dato crudo intacto.
        #
        # La segunda preguntaba, con un cuadro que habia que contestar,
        # si una finta de menos de ocho fotogramas se anotaba igual.
        # Cortaba el trabajo en la accion mas frecuente del combate —en
        # ID30, 82 de 228 anotaciones eran fintas— para preguntar algo
        # que el propio dato ya responde: la duracion esta en el
        # registro y filtrar por ella es cosa del analisis.

        # Aqui se preguntaba por la esquiva sin ataque del rival en el
        # segundo anterior. Era otra regla de tiempo y otra
        # interrupcion: retirada por lo mismo.
        return True

    def _handle_referee_stop(self) -> None:
        """Handle Referee Stop technique via state machine with START/END."""
        vm = self._vm
        sm = self._sm

        if not vm.is_loaded:
            return

        if sm.state.value == sm.state.IDLE.value:
            vm.mark_annotation_start()
            sm.reset()
            sm.mark_start(vm.current_frame)
            vp = self._win.video_panel
            vp.update_marks_label(vm.ann_start, vm.ann_end)

        dlg = RefereeStopPopup(
            athlete=self._ap.athlete,
            colors=self._colors,
            stop_types=self._config.referee_stop_types,
            parent=self._win,
        )
        if dlg.exec() != RefereeStopPopup.Accepted or dlg.selected is None:
            sm.reset()
            vm.clear_annotation_markers()
            vp = self._win.video_panel
            vp.update_marks_label(vm.ann_start, vm.ann_end)
            self._win.set_pending_text("")
            from karlos_core.utils.i18n import I18n
            self._win.set_status_message(I18n().t("pro.parada_cancelada"))
            return

        if not self.preparar_parada(dlg.selected):
            sm.reset()
            vm.clear_annotation_markers()

    def preparar_parada(self, tipo: str) -> bool:
        """Dejar lista una parada del árbitro de ese tipo, a falta del [O].

        Es lo que hacía la ventana de paradas una vez elegido el tipo, y
        ahora lo usa también el árbol de preguntas: la parada se crea por el
        mismo camino venga del botón o de las preguntas.
        """
        sm = self._sm
        try:
            sm.select_referee_stop(tipo)
        except StateTransitionError as exc:
            self._win.set_status_message(str(exc))
            return False

        self._win.set_pending_text(f"Pending END: Referee Stop - {tipo}")
        from karlos_core.utils.i18n import I18n
        self._win.set_status_message(I18n().t(
            "pro.parada_pendiente", tipo=tipo, atleta=catalogo.etiqueta(self._ap.athlete)))
        self._ap.clear_notes()
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # ══════════════════════════════════════════════════════════════════
    # SEQUENCE_ID Auto-Assignment (v6.2 — ML-ready temporal grouping)
    # ══════════════════════════════════════════════════════════════════
    def _compute_active_play(self, current_duration: float) -> Optional[float]:
        """Compute active play time up to the current annotation's end.

        Active play = elapsed time from fight_start to current annotation's
        end frame, minus the merged duration of all REFEREE STOP intervals
        that ended before this annotation.

        Delegates the merge logic to the shared utility function in
        merge_utils to avoid duplicating the algorithm.
        """
        from karlos_core.utils.merge_utils import merge_referee_stop_intervals

        vm = self._vm
        if not vm.is_loaded or vm.fight_start is None:
            return None

        fps = self._fps if self._fps > 0 else (vm.fps if vm.fps > 0 else 30.0)
        elapsed = (vm.ann_end - vm.fight_start) / fps if vm.ann_end else 0.0

        stopped_before = merge_referee_stop_intervals(
            self._tv.records,
            fps,
            end_before=vm.ann_end,
        )

        return max(0.0, elapsed - stopped_before)
