"""El hub y las sesiones: cargar la carpeta, abrir y guardar cada combate, el
final del combate y los asaltos.

Parte del controlador principal (``annotation_controller``), separada en la
fase F3.7.
"""

from __future__ import annotations

from pathlib import Path

import cv2
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from karlos_core.controllers.session_manager import SessionManager
from karlos_core.models.state import FightSession
from karlos_core.utils.app_logging import get_logger
from karlos_core import catalogo
from karlos_core.utils.i18n import I18n
from karlos_core.views.bout_info_popup import BoutInfoPopup
from karlos_core.views.fight_end_popup import FightEndPopup

# El mismo nombre que antes de partir el controlador: el log no cambia.
_log = get_logger("karlos_core.controllers.annotation_controller")


class SesionesMixin:
    """El hub y las sesiones: cargar la carpeta, abrir y guardar cada combate,
    el final del combate y los asaltos."""

    def _borrar_anotaciones(self, fila: int,
                            conservar_paradas: bool | None = None) -> int:
        """Tirar lo anotado de un combate. Devuelve cuantas quito.

        Con conservar_paradas a None se pregunta; el Hub llega asi. Las
        paradas se pueden salvar aparte: son del combate y valen para
        cualquier pasada.
        """
        video = self._video_de_fila(fila)
        if not video:
            return 0
        if fila == self.active_session_idx:
            QMessageBox.information(
                self.window, self._i18n.t("dialog.apagar_titulo"),
                self._i18n.t("dialog.apagar_feche"))
            return 0
        total, paradas = self._paradas_guardadas(video)
        if total == 0:
            QMessageBox.information(
                self.window, self._i18n.t("dialog.apagar_titulo"),
                self._i18n.t("dialog.apagar_nada", nome=Path(video).name))
            return 0
        if conservar_paradas is None:
            conservar_paradas = self._preguntar_borrado(
                total, paradas, self._i18n.t("dialog.apagar_titulo"),
                self._i18n.t("dialog.apagar_pregunta_video", n=str(total), nome=Path(video).name))
            if conservar_paradas is None:
                return 0
        quitadas = self.session_manager.borrar_anotaciones(
            video, bool(conservar_paradas))
        if 0 <= fila < len(self.sessions):
            self._refresh_session_from_disk(self.sessions[fila])
            self.window.project_hub.set_sessions(self.sessions)
        self.window.set_status_message(
            self._i18n.t("stat.apagadas_video", nome=Path(video).name, n=str(quitadas))
            + (self._i18n.t("stat.paradas_mantidas", n=str(paradas)) if conservar_paradas else ""))
        return quitadas

    def _on_analyze_other_status(self, target: str) -> None:
        # Decia «[D] marca el inicio» en modo asistido. [D] dejo de
        # marcar nada cuando se pasaron los controles a los de la
        # industria: ahora es [I] en los dos modos, asi que tampoco
        # hace falta preguntar en cual estamos.
        self.window.set_status_message(I18n().t("pro.analisando_i", target=target))

    def _on_fight_end_handler(self) -> None:
        vm = self.video_manager
        if not vm.is_loaded: return
        # Donde hay asaltos, [G] cierra EL ASALTO en curso. El combate solo
        # termina —y solo entonces se pregunta qué hacer— al cerrar el
        # último (Johan, 7-10-2026).
        if self._asaltos is not None:
            if not self.fight_controller.cerrar_asalto():
                return
            if self._asaltos.marcados < self._asaltos.total:
                return
        else:
            vm.set_fight_end()
        vp = self.window.video_panel
        vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
        dur = vm.fight_duration_s(); dur_str = f"{dur:.1f}s" if dur else "0s"
        self.window.set_status_message(I18n().t("pro.fim_luta", frame=str(vm.fight_end), dur=dur_str))
        # En la pasada de fases, la fase abierta se cierra con el asalto.
        if self._en_modo_fases():
            self._cerrar_fase_abierta(vm.fight_end)
            from karlos_core.tiempo_movimiento import fases_por_atleta
            if not fases_por_atleta():
                # En karate las fases son del combate: una sola pasada y no
                # hay «otro atleta» que ofrecer. La ventana de fin de combate
                # ofrecía pasar a AO y, al aceptar, borraba [F] y [G] (Johan,
                # ID25 en tiempo-movimiento, 19-10-2026).
                self._schedule_save()
                return
        # Donde las fases son de cada atleta (taekwondo), el cierre sigue el
        # camino de siempre y el diálogo ofrece al otro atleta (el especialista, 9-10-2026).
        try: self.window.annotation_panel.lock_athlete(False)
        except AttributeError: pass
        records = self.window.table_view.records
        aka_count = sum(1 for r in records if r.athlete == "AKA")
        ao_count = sum(1 for r in records if r.athlete == "AO")
        fc = self.fight_controller
        both_analyzed = getattr(fc, '_first_pass_complete', False) or (aka_count > 0 and ao_count > 0)
        if both_analyzed and 0 <= self.active_session_idx < len(self.sessions):
            # Anotado por los dos lados no es lo mismo que terminado:
            # quien lo da por terminado es Johan, en el Hub o al cerrar.
            session = self.sessions[self.active_session_idx]; session.annotations = list(records)
        current_athlete = self.window.annotation_panel.athlete
        cr = int(self._bout_info.get("current_round", 1) or 1)
        nr = int(self._bout_info.get("num_rounds", 0) or 0)
        popup = FightEndPopup(
            fight_start=vm.fight_start, fight_end=vm.fight_end, duration=dur,
            aka_count=aka_count, ao_count=ao_count,
            aka_label=self._sport_meta.get("athlete_a_label", "Athlete A (AKA)"),
            ao_label=self._sport_meta.get("athlete_b_label", "Athlete B (AO)"),
            colors=self._colors, parent=self.window, current_athlete=current_athlete,
            current_round=cr, num_rounds=nr,
        )
        popup.analyze_other_athlete_requested.connect(self._on_analyze_other_direct)
        popup.continue_current_requested.connect(self._on_continue_current_pass)
        popup.next_fight_requested.connect(self._on_next_fight)
        popup.finish_and_export_requested.connect(self._on_finish_and_export)
        popup.finished.connect(lambda: self._on_popup_closed(popup))
        popup.exec(); self._schedule_save()

    def _on_analyze_other_direct(self) -> None:
        from karlos_core.formato import PRIMERO, SEGUNDO
        current = self.window.annotation_panel.athlete
        target = SEGUNDO if current == PRIMERO else PRIMERO
        self.window.annotation_panel.set_athlete(target); self.window.annotation_panel.lock_athlete(False)
        self._bout_info["current_round"] = "1"; self._sync_round_label()
        self.video_manager.goto(0)
        vm = self.video_manager
        # Con asaltos, el combate empieza y acaba donde ellos: los del
        # combate en el técnico-táctico (ya marcados), los del atleta nuevo
        # en el tiempo-movimiento (vacíos: los marca él).
        asaltos = getattr(self, "_asaltos", None)
        if asaltos is not None:
            vm.fight_start = asaltos.inicio_del_combate; vm.fight_end = asaltos.fin_del_combate
        elif not self._en_modo_fases():
            vm.fight_start = None; vm.fight_end = None
        # En el tiempo-movimiento del karate las fases y los límites son del
        # combate: cambiar de atleta no los toca (19-10-2026).
        vp = self.window.video_panel; vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps); vp.set_pass_label(0, "")
        if asaltos is not None and asaltos.marcados >= asaltos.total:
            self.window.set_status_message(I18n().t(
                "tm.otro_atleta_asaltos_hechos", target=catalogo.etiqueta(target), total=str(asaltos.total)))
        else:
            self.window.set_status_message(I18n().t("pro.analisando_f", target=catalogo.etiqueta(target)))
        self._update_timeline()

    def _on_next_fight(self) -> None:
        vm = self.video_manager; vm.fight_start = None; vm.fight_end = None; vm.goto(0)
        vp = self.window.video_panel; vp.update_fight_label(None, None, vm.fps); vp.set_pass_label(0, "")
        self.window.annotation_panel.set_athlete("AKA")
        self.window.set_status_message(I18n().t("pro.luta_nova"))
        self._sync_ui_to_state()

    def _on_popup_closed(self, popup) -> None:
        if not hasattr(popup, '_current_round') or not hasattr(popup, '_num_rounds'): return
        nr = popup._num_rounds
        if nr <= 0: return
        if popup.result() == QDialog.DialogCode.Accepted:
            cr = popup._current_round
            if cr < nr:
                next_round = cr + 1
                self._bout_info["current_round"] = str(next_round)
                vm = self.video_manager; vm.set_fight_start()
                vp = self.window.video_panel; vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
                self._sync_round_label()
                self.window.set_status_message(self._i18n.t("stat.passada_iniciada", n=str(next_round), total=str(nr)))
                self._sync_ui_to_state()

    def _on_continue_current_pass(self) -> None:
        vm = self.video_manager
        # «Continuar nesta passagem» borraba el inicio y el fin del combate
        # para poder delimitar otro. En el tiempo-movimiento son los límites
        # sobre los que se calcula todo y se marcan una vez para los dos
        # atletas: seguir anotando no los quita (ID25, 19-10-2026).
        if not self._en_modo_fases():
            vm.fight_start = None; vm.fight_end = None
        vp = self.window.video_panel
        vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps); vp.set_pass_label(0, "")
        self.window.set_status_message(I18n().t("pro.continue"))

    def _on_back_to_hub(self) -> None:
        self._save_session()
        # Sin vídeo abierto (el informe se abrió desde el hub) no hay
        # bloqueo que soltar. Antes se llamaba igual, release_lock(None)
        # se caía y «Back to Hub» no volvía (fallo de la 1.0, visto en la
        # tableta el 12-10-2026).
        if self._video_path:
            active = self.session_manager.get_active_round(self._video_path)
            eid = active["evaluator_id"] if active else "default"; occ = active["occasion"] if active else 1
            self.session_manager.release_lock(self._video_path, eid, occ)
        if 0 <= self.active_session_idx < len(self.sessions):
            session = self.sessions[self.active_session_idx]; session.annotations = list(self.window.table_view.records)
            if session.status != "Completed": session.status = "In Progress"
        for i, session in enumerate(self.sessions):
            if i != self.active_session_idx: self._refresh_session_from_disk(session)
        self.navigation.back_to_hub(sessions=self.sessions, active_session_idx=self.active_session_idx, annotation_panel=self.window.annotation_panel, table_view=self.window.table_view)
        self.active_session_idx = -1; self._video_path = None
        self.window.set_status_message(I18n().t("pro.pronto"))

    def _on_load_folder_from_path(self, folder: str) -> None: self._load_sessions_from_folder(folder)
    def _on_load_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self.window, "Select Video Folder", "")
        if not folder: return
        self._load_sessions_from_folder(folder)

    def _validate_session_quality(self, session: FightSession) -> tuple[bool, list[str]]:
        reasons: list[str] = []; meta = session.bout_metadata or {}
        required_fields = {"athlete_a_name": "Athlete A name", "athlete_b_name": "Athlete B name", "weight_category": "Weight category", "competition_name": "Competition/Event name"}
        for key, label in required_fields.items():
            val = (meta.get(key) or "").strip()
            if not val or val in ("—", "N/A", ""): reasons.append(f"Bout Info incomplete: missing {label}")
        fs = session.fight_start if hasattr(session, 'fight_start') else None
        fe = session.fight_end if hasattr(session, 'fight_end') else None
        if fs is None or fe is None: reasons.append("Fight markers not set (fight_start/fight_end)")
        if session.annotations: reasons.extend(self._validate_annotations_schema(session.annotations))
        return len(reasons) == 0, reasons

    @staticmethod
    def _validate_annotations_schema(annotations: list) -> list[str]:
        import re; errors: list[str] = []; seq_pattern = re.compile(r"^SEQ_\d{3}$")
        for i, ann in enumerate(annotations):
            if ann.level and " | " in ann.level: errors.append(f"Annotation #{i+1}: Level '{ann.level}' is unparsed")
            seq_id = (ann.sport_specific_data or {}).get("sequence_id", "")
            if seq_id and not seq_pattern.match(seq_id): errors.append(f"Annotation #{i+1}: bad Sequence_ID '{seq_id}'")
        return errors

    def _recargar_cuaderno(self) -> None:
        """Los combates del Hub, con lo que hay en el cuaderno activo.

        Al cambiar de análisis cada combate se vacía y se vuelve a leer de
        SU archivo en ese cuaderno: lo del cuaderno anterior no se queda
        pegado (decisión 0008)."""
        for session in self.sessions:
            session.annotations = []
            session.status = "Pending"
            session.asaltos = None
            session.fases = None
            session.bout_metadata = {}
            session.__dict__['_needs_review_reasons'] = []
            self._refresh_session_from_disk(session)
        self.window.project_hub.set_sessions(self.sessions)

    def _refresh_session_from_disk(self, session: FightSession) -> FightSession:
        from pathlib import Path as _Path
        active = self.session_manager.get_active_round(session.video_path)
        if active is None: return session
        # Una sesión de antes de los cuadernos, a su cuaderno (decisión 0008).
        self.session_manager.migrar_al_cuaderno(session.video_path, active["evaluator_id"], active["occasion"])
        session_path = self.session_manager._session_path(session.video_path, active["evaluator_id"], active["occasion"])
        if not session_path.exists():
            # Fallback: ONLY for Pasada 1, check legacy format
            if active["occasion"] == 1:
                legacy = self.session_manager._old_session_path(session.video_path)
                if legacy.exists():
                    session_path = legacy
                else:
                    return session
            else:
                # No session file → blank slate for this pasada
                session.bout_metadata = {}
                session.annotations = []
                session.status = "Pending"
                session.__dict__['_needs_review_reasons'] = []
                return session
        data = SessionManager._load_from_path(session_path)
        if data is None: return session
        session.bout_metadata = data.get("bout_info", {}) or {}
        session.annotations = [self.session_manager.annotation_from_dict(d) for d in data.get("annotations", [])]
        if hasattr(session, 'fight_start'): session.fight_start = data.get("fight_start")
        else: session.__dict__['fight_start'] = data.get("fight_start")
        if hasattr(session, 'fight_end'): session.fight_end = data.get("fight_end")
        else: session.__dict__['fight_end'] = data.get("fight_end")
        # Terminado solo si quien anota lo dijo; empezado si hay algo dentro.
        if data.get("concluido"): session.status = "Completed"
        # Las fases marcadas son trabajo de una persona, aunque no haya acciones.
        elif session.annotations or data.get("fases"): session.status = "In Progress"
        else: session.status = "Pending"
        session.asaltos = data.get("asaltos_por_atleta") or data.get("asaltos") or None
        from karlos_core.tiempo_movimiento import quitar_fases_repetidas, separar_fases
        session.annotations = quitar_fases_repetidas(session.annotations)
        _acc, marcas = separar_fases(session.annotations)
        session.fases = marcas or data.get("fases") or None
        if session.annotations:
            is_clean, reasons = self._validate_session_quality(session)
            session.__dict__['_needs_review_reasons'] = reasons if (session.status == "Completed" and not is_clean) else []
        else: session.__dict__['_needs_review_reasons'] = []
        return session

    def _load_sessions_from_folder(self, folder: str) -> None:
        video_extensions = {".mp4", ".avi", ".mov", ".mkv"}; video_files: list[Path] = []; folder_path = Path(folder)
        for ext in video_extensions:
            video_files.extend(folder_path.rglob(f"*{ext}")); video_files.extend(folder_path.rglob(f"*{ext.upper()}"))
        video_files = sorted(set(video_files), key=lambda p: p.name)
        if not video_files: QMessageBox.information(self.window, self._i18n.t("dialog.no_videos"), self._i18n.t("stat.no_videos")); return
        self._folder_path = folder
        first_video = str(video_files[0]); self.session_manager.migrate_rounds(first_video)
        existing_paths = {s.video_path for s in self.sessions}; new_sessions: list[FightSession] = []; next_id = len(self.sessions) + 1
        for vp in video_files:
            vp_str = str(vp)
            if vp_str not in existing_paths:
                resolution = ""; fps = 0.0; duration_s = 0.0
                cap = cv2.VideoCapture(vp_str)
                if cap.isOpened():
                    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    if w > 0 and h > 0: resolution = f"{w}x{h}"
                    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0; frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if fps > 0: duration_s = frame_count / fps
                    cap.release()
                session = FightSession(id=next_id, video_path=vp_str, video_name=vp.name, status="Pending", resolution=resolution, fps=fps, duration_s=duration_s)
                new_sessions.append(session); next_id += 1
        self.sessions.extend(new_sessions)
        for session in self.sessions: self._refresh_session_from_disk(session)
        self.window.project_hub.set_sessions(self.sessions); self.window.project_hub.add_recent_folder(folder)
        self._update_round_selector()
        self.window.set_status_message(self._i18n.t("stat.loaded", total=str(len(video_files)), new=str(len(new_sessions)), all=str(len(self.sessions))))

    def _on_session_selected(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.sessions): return
        self.active_session_idx = idx; session = self.sessions[idx]; session.status = "In Progress"
        self.window.project_hub.set_sessions(self.sessions)
        self._bout_info = dict(session.bout_metadata or {}); self._video_path = session.video_path
        if not self.video_manager.load(session.video_path):
            QMessageBox.critical(self.window, self._i18n.t("dialog.load_error"), f"{self._i18n.t('dialog.load_error')}:\n{session.video_path}")
            session.status = "Pending"; self.window.project_hub.set_sessions(self.sessions); return
        if session.annotations:
            self.window.table_view.clear_all()
            for ann in session.annotations: self.window.table_view.add_annotation(ann)
            self._update_live_stats()
        self._update_timeline(); self.navigation.show_annotator(); self._sync_corner_colors()
        self.window.set_status_message(self._i18n.t("stat.active_session", name=session.video_name))
        # Con el combate abierto se entra ya en la anotación guiada.
        if not self._en_modo_pro():
            self._entrar_modo_asistido()

    def _on_delete_session(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.sessions): return
        session = self.sessions[idx]; name = session.video_name or "this session"
        reply = QMessageBox.question(self.window, "Remove Session", f"Remove \"{name}\" from the project list?\n\nThis will NOT delete the video or .karlos file — you can re-add it by loading the folder again.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes: return
        if self.session_manager.has_session(session.video_path): self.session_manager.delete_session(session.video_path)
        del self.sessions[idx]
        for i, s in enumerate(self.sessions): s.id = i + 1
        if self.active_session_idx == idx: self.active_session_idx = -1
        elif self.active_session_idx > idx: self.active_session_idx -= 1
        self.window.project_hub.set_sessions(self.sessions)
        self.window.set_status_message(f"Removed \"{name}\" from project.")

    def _on_edit_bout_info_from_hub(self, idx: int) -> None:
        if not self.sessions: QMessageBox.information(self.window, "No Sessions", "No sessions loaded yet."); return
        if idx < 0 or idx >= len(self.sessions): QMessageBox.warning(self.window, "Invalid Session", f"Session index {idx} is out of range."); return
        session = self.sessions[idx]; athlete_a = self._sport_meta.get("athlete_a_label", "Athlete A"); athlete_b = self._sport_meta.get("athlete_b_label", "Athlete B")
        popup = BoutInfoPopup(athlete_a_label=athlete_a, athlete_b_label=athlete_b, parent=self.window, existing_data=session.bout_metadata or {}, sport_id=self._sport_meta.get("id", "karate"), anotaciones=len(getattr(session, "annotations", None) or []))
        if popup.exec() == BoutInfoPopup.Accepted:
            session.bout_metadata = dict(popup.bout_info)
            if idx == self.active_session_idx:
                self._bout_info = popup.bout_info
                self._ajustar_total_de_asaltos()
            self.window.project_hub.set_sessions(self.sessions); self.window.set_status_message(I18n().t("pro.dados_atualizados"))

    def _open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self.window, "Open Video", "", "Videos (*.mp4 *.avi *.mov *.mkv);;All (*)")
        if not path: return
        self._video_path = path
        if not self.video_manager.load(path): QMessageBox.critical(self.window, self._i18n.t("dialog.file_error"), f"{self._i18n.t('dialog.file_error')}:\n{path}")

    def _cargar_datos_de_fila(self, fila: int) -> None:
        """Abrir el video de esa fila y cargarle un CSV encima.

        Desde el hub el evaluador ya eligio el combate, asi que no tiene
        sentido volver a preguntarselo: se abre ese video y solo se pide
        el archivo de datos.
        """
        video = self._video_de_fila(fila)
        if not video:
            return
        self._on_session_selected(fila)
        self._cargar_csv_combate()

    def _edit_bout_info(self) -> None:
        athlete_a = self._sport_meta.get("athlete_a_label", "Athlete A"); athlete_b = self._sport_meta.get("athlete_b_label", "Athlete B")
        popup = BoutInfoPopup(athlete_a_label=athlete_a, athlete_b_label=athlete_b, parent=self.window, existing_data=self._bout_info, sport_id=self._sport_meta.get("id", "karate"), anotaciones=len(self.window.table_view.records))
        if popup.exec() == BoutInfoPopup.Accepted:
            self._bout_info = popup.bout_info
            if 0 <= self.active_session_idx < len(self.sessions): self.sessions[self.active_session_idx].bout_metadata = dict(self._bout_info)
            self._sync_corner_colors(); self.window.set_status_message(I18n().t("pro.dados_atualizados"))
            # El número de asaltos del combate puede haber cambiado.
            self._ajustar_total_de_asaltos()
            # El análisis puede haber cambiado: el panel y las teclas van con él.
            self._aplicar_analisis()

    def _ajustar_total_de_asaltos(self) -> None:
        """Con «Number of Rounds» cambiado, los asaltos pasan a ese número
        sin perder lo marcado (los que sobran se quitan si no tienen marcas;
        con marcas, se quedan hasta que se borren)."""
        if getattr(self, "_asaltos", None) is None:
            return
        from karlos_core.models.asaltos import Asaltos
        total = self._total_de_asaltos()

        def ajustar(a):
            if a is None or a.total == total:
                return a
            lista = a.a_lista()
            marcados = max((f["asalto"] for f in lista if f.get("inicio") is not None
                            or f.get("fin") is not None), default=0)
            return Asaltos.de_lista(lista, max(total, marcados))

        self._asaltos = ajustar(self._asaltos)
        dic = getattr(self, "_asaltos_por_atleta", None) or {}
        for k in list(dic):
            dic[k] = self._asaltos if k == getattr(self, "_atleta_de_asaltos", None) else ajustar(dic[k])
        self._enganchar_asaltos()
        self._update_timeline()
        self._schedule_save()

    def _schedule_save(self) -> None:
        if self._save_timer is not None: self._save_timer.stop()
        else: self._save_timer = QTimer(self); self._save_timer.setSingleShot(True); self._save_timer.timeout.connect(self._save_session)
        self._save_timer.start(2000)

    def _save_session(self) -> None:
        if self._save_timer is not None: self._save_timer.stop()
        if not self._video_path: return
        try:
            fc = self.foul_controller; eid = self._active_evaluator_id(); occ = self._active_occasion()
            self.session_manager.save_session(video_path=self._video_path, bout_info=self._bout_info, fight_start=self.video_manager.fight_start, fight_end=self.video_manager.fight_end, records=self.window.table_view.records, current_athlete=self.window.annotation_panel.athlete, current_pass=self.fight_controller.current_pass, sequence_counter=self.flow_controller.sequence_counter, current_sequence_id=self.flow_controller.current_sequence_id, last_annotation_end=self.flow_controller.last_annotation_end, last_technique_name=self.flow_controller.last_technique_name, aka_fouls=fc.aka_fouls, ao_fouls=fc.ao_fouls, evaluator_id=eid, occasion=occ,
                asaltos=(self._asaltos.a_lista() if self._asaltos is not None else None),
                asaltos_por_atleta=self._asaltos_a_guardar(),
                fases=self._fases_a_lista())
        except OSError:
            # Losing autosaves silently means losing annotations — surface it.
            _log.error("Autosave failed for %s", self._video_path, exc_info=True)
            self.window.set_status_message(self._i18n.t("stat.autosave_falhou"))

    def _on_undo_stack_changed(self, _idx: int) -> None:
        if self._restoring_session or self._doing_save: return
        if 0 <= self.active_session_idx < len(self.sessions): self.sessions[self.active_session_idx].annotations = list(self.window.table_view.records)
        # Deshacer o rehacer una fase cambia las filas PHASE: las marcas van detrás.
        self._sincronizar_fases()
        # La primera anotación deja escrito el análisis en los datos del combate.
        self._fijar_analisis()
        # Borrar o deshacer una falta cambia el grado de las que vienen
        # detras: la escalera se reetiqueta aqui, que es por donde pasa
        # toda mutacion de la tabla.
        self.foul_controller.resincronizar()
        self._schedule_save(); self._update_timeline(); self._update_live_stats(); self._sync_ui_to_state()

    def _restore_session_from_active_round(self) -> None:
        if not self._video_path: return
        active = self.session_manager.get_active_round(self._video_path)
        if active is None: return
        self.session_manager.migrar_al_cuaderno(self._video_path, active["evaluator_id"], active["occasion"])
        session_path = self.session_manager._session_path(self._video_path, active["evaluator_id"], active["occasion"])
        if not session_path.exists():
            # Fallback: ONLY for Pasada 1
            if active["occasion"] == 1:
                legacy = self.session_manager._old_session_path(self._video_path)
                if legacy.exists():
                    session_path = legacy
                else:
                    self.window.set_status_message(self._i18n.t("stat.new_session", label=active["label"])); return
            else:
                self.window.set_status_message(self._i18n.t("stat.new_session", label=active["label"])); return
        self._restoring_session = True
        try:
            data = SessionManager._load_from_path(session_path)
            if data is None: return
            self._bout_info = data.get("bout_info", {})
            if (fs := data.get("fight_start")) is not None: self.video_manager.fight_start = fs
            if (fe := data.get("fight_end")) is not None: self.video_manager.fight_end = fe
            # Los asaltos marcados vuelven tal cual: lo que se marcó una vez
            # no se vuelve a marcar, ni al cambiar de atleta ni al reabrir.
            self._reponer_asaltos(data.get("asaltos"), data.get("asaltos_por_atleta"))
            # Primero el registro, y después las fases: si no, las marcas
            # guardadas se volvían filas y el registro traía esas mismas
            # filas, y cada reapertura las duplicaba (el especialista, 12-10-2026).
            for ann_dict in data.get("annotations", []): self.window.table_view.add_annotation(self.session_manager.annotation_from_dict(ann_dict))
            repetidas = self._quitar_fases_repetidas()
            self._reponer_fases(data.get("fases"))
            if repetidas:
                self._schedule_save()
            current_pass = data.get("current_pass", 0)
            # Sin nada anotado (las paradas no cuentan) no hay pasada que
            # reponer. Las sesiones vaciadas antes de 6.14.12 guardaban la
            # que llevaban, y al reabrirlas la [F] empezaba la segunda.
            if not any(a.get("category") != "REFEREE STOP"
                       for a in data.get("annotations") or []):
                current_pass = 0
            if current_pass: self.fight_controller.restore_pass(current_pass)
            current_athlete = "AO" if current_pass >= 2 else data.get("current_athlete", "AKA")
            self.window.annotation_panel.set_athlete(current_athlete)
            self.flow_controller.restore_sequence_state(sequence_counter=data.get("sequence_counter", 0), current_sequence_id=data.get("current_sequence_id", ""), last_annotation_end=data.get("last_annotation_end", 0), last_technique_name=data.get("last_technique_name", ""))
            # Auto-saneamiento: las sesiones guardadas con el bug de los
            # contadores (antes del 21-09-2026) traen grados CHUI mal
            # puestos. Reetiquetar al abrir las deja bien sin pedir nada.
            if self.foul_controller.resincronizar():
                self._schedule_save()
            self._avisar_acciones_fuera_del_combate()
            if 0 <= self.active_session_idx < len(self.sessions):
                session = self.sessions[self.active_session_idx]; session.annotations = list(self.window.table_view.records); session.status = "In Progress"; session.bout_metadata = dict(self._bout_info)
            vm = self.video_manager; self.window.video_panel.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
            self.window.set_status_message(self._i18n.t(
                "stat.session_restored",
                n=str(len(self.window.table_view.records)),
                athlete=active["label"]))
            self._update_timeline()
            # El recuento solo se refrescaba al CREAR una anotacion, asi
            # que al abrir un combate ya anotado la franja decia 0-0 y
            # cero acciones teniendo 228. Un marcador que miente es peor
            # que no tenerlo.
            self._update_live_stats()
        finally: self._restoring_session = False

    def _update_round_selector(self) -> None:
        first_video = next((s.video_path for s in self.sessions), None)
        if first_video is None: return
        rounds = self.session_manager.list_rounds(first_video)
        rounds_data = self.session_manager._load_rounds()
        active_idx = rounds_data.get("active_round_index", 0)
        self.window.project_hub.set_rounds(rounds, active_idx)

    def _on_round_changed(self, index: int) -> None:
        first_video = next((s.video_path for s in self.sessions), None)
        if first_video is None: return
        self.session_manager.set_active_round(first_video, index)
        for session in self.sessions: self._refresh_session_from_disk(session)
        self.window.project_hub.set_sessions(self.sessions)
        active = self.session_manager.get_active_round(first_video)
        self.window.set_status_message(self._i18n.t("stat.passada_ativa", label=(active['label'] if active else self._i18n.t("stat.passada_desconhecida"))))

    def _on_new_round(self) -> None:
        """Simple dialog: just pick the pass number for a new pasada."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel as QLbl, QSpinBox, QPushButton
        first_video = next((s.video_path for s in self.sessions), None)
        if first_video is None: return
        existing_rounds = self.session_manager.list_rounds(first_video)
        max_occ = max((r.get("occasion", 0) for r in existing_rounds), default=0)
        suggested = max_occ + 1

        dlg = QDialog(self.window)
        dlg.setWindowTitle(self._i18n.t("round.titulo"))
        dlg.setMinimumWidth(360)
        layout = QVBoxLayout(dlg); layout.setSpacing(14); layout.setContentsMargins(24, 20, 24, 24)
        title = QLbl(self._i18n.t("round.cabecalho")); title.setStyleSheet("font-size:18px;font-weight:700;color:#D5A021;")
        layout.addWidget(title)
        layout.addWidget(QLbl(self._i18n.t("round.existem", n=str(max_occ), m=str(suggested))))
        spin = QSpinBox(); spin.setMinimum(1); spin.setMaximum(999); spin.setValue(suggested); spin.setMinimumHeight(36)
        spin.setStyleSheet("font-size:16px;font-weight:600;padding:6px 12px;")
        layout.addWidget(spin)
        preview = QLbl(self._i18n.t("round.preview", n=str(suggested)))
        preview.setStyleSheet("font-size:15px;font-weight:600;color:#D5A021;padding:8px 0;")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.valueChanged.connect(lambda v: preview.setText(self._i18n.t("round.preview", n=str(v))))
        layout.addWidget(preview)
        btn_row = QHBoxLayout(); btn_row.addStretch()
        cancel = QPushButton(self._i18n.t("dialog.cancelar")); cancel.clicked.connect(dlg.reject)
        create = QPushButton(self._i18n.t("round.criar")); create.setDefault(True)
        create.setStyleSheet("QPushButton{padding:8px 20px;font-size:13px;font-weight:600;background:rgba(213,160,33,0.15);color:#D5A021;border:1px solid rgba(213,160,33,0.30);border-radius:6px;}QPushButton:hover{background:rgba(213,160,33,0.25);color:#FFF;}")
        create.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel); btn_row.addWidget(create); layout.addLayout(btn_row)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        occ = spin.value()
        label = self._i18n.t("round.label", n=str(occ))
        self.session_manager.create_round(first_video, "default", occ, label)
        self._update_round_selector()
        for session in self.sessions: self._refresh_session_from_disk(session)
        self.window.project_hub.set_sessions(self.sessions)
        self.window.set_status_message(self._i18n.t("stat.nova_passada", label=label))

    def _on_manage_rounds(self) -> None:
        """Open panel to delete/rename pasadas."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel as QLbl, QPushButton, QInputDialog
        first_video = next((s.video_path for s in self.sessions), None)
        if first_video is None: return
        rounds = self.session_manager.list_rounds(first_video)
        if not rounds:
            QMessageBox.information(self.window, "Sin pasadas", "No hay pasadas creadas todavía.")
            return
        dlg = QDialog(self.window)
        dlg.setWindowTitle("⚙️  Gestionar pasadas")
        dlg.setMinimumWidth(380)
        layout = QVBoxLayout(dlg); layout.setSpacing(10); layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(QLbl("Eliminar o renombrar pasadas. Los archivos .karlos NO se borran."))
        for i, r in enumerate(rounds):
            row = QHBoxLayout()
            lbl = QLbl(f"  {r['label']}")
            row.addWidget(lbl); row.addStretch()
            del_btn = QPushButton("🗑️")
            del_btn.setFixedWidth(32); del_btn.setToolTip("Eliminar esta pasada del selector")
            del_btn.clicked.connect(lambda checked, idx=i: self._delete_round(idx, dlg))
            row.addWidget(del_btn)
            layout.addLayout(row)
        btn_row = QHBoxLayout(); btn_row.addStretch()
        close_btn = QPushButton("Cerrar"); close_btn.clicked.connect(dlg.accept); btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dlg.exec()

    def _delete_round(self, idx: int, dlg: QDialog) -> None:
        first_video = next((s.video_path for s in self.sessions), None)
        if first_video is None: return
        rounds = self.session_manager.list_rounds(first_video)
        if idx >= len(rounds): return
        r = rounds[idx]
        reply = QMessageBox.question(self.window, "Eliminar pasada", f"¿Eliminar \"{r['label']}\" del selector?\n\nLos archivos .karlos quedan en disco.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.session_manager.delete_round(first_video, idx)
            self._update_round_selector()
            for session in self.sessions: self._refresh_session_from_disk(session)
            self.window.project_hub.set_sessions(self.sessions)
            dlg.accept()
