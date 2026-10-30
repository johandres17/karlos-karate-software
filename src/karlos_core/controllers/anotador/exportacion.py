"""Las salidas: exportar, cargar el CSV del combate y abrir los informes (las
salidas son del deporte, decisión 0004).

Parte del controlador principal (``annotation_controller``), separada en la
fase F3.7 sin cambiar nada: el código es el mismo, movido de sitio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from karlos_core.models.state import FightSession
from karlos_core.utils.app_logging import get_logger
from karlos_core.utils.merge_utils import migrate_legacy_combined_levels
from karlos_core import catalogo, identidad
from karlos_core.utils.i18n import I18n

# El mismo nombre que antes de partir el controlador: el log no cambia.
_log = get_logger("karlos_core.controllers.annotation_controller")


class ExportacionMixin:
    """Las salidas: exportar, cargar el CSV del combate y abrir los informes
    (las salidas son del deporte, decisión 0004)."""

    def _on_finish_and_export(self) -> None:
        self._save_session()
        if 0 <= self.active_session_idx < len(self.sessions):
            session = self.sessions[self.active_session_idx]; session.annotations = list(self.window.table_view.records); session.status = "Completed"
            self.session_manager.marcar_concluido(session.video_path, True)
        self.video_manager.stop(); self.video_manager.release(); self.state_machine.reset()
        self.window.table_view.clear_all(); self.window.annotation_panel.set_athlete("AKA"); self.window.annotation_panel.lock_athlete(False)
        self.window.video_panel.update_info_label(0, 0, 0.0)
        self.window.video_panel.update_fight_label(None, None, None); self.window.video_panel.update_marks_label(None, None)
        self._video_path = None
        self.window.project_hub.set_sessions(self.sessions); self.navigation.show_hub()
        self.window.set_status_message(self._i18n.t("stat.session_done"))

    def _on_view_report(self, idx: int) -> None:
        """«Ver Relatório». Con la anotación guiada abre el informe del
        entrenador, que responde en el orden en que un entrenador pregunta
        —quien gano y cuando se decidio, quien acertaba mas, que cambio
        despues— y solo enseña lo que tiene base suficiente. Desde el Hub,
        antes de abrir ningun combate, abre el informe de siempre.
        """
        if idx < 0 or idx >= len(self.sessions): return
        session = self.sessions[idx]
        asaltos, fases = self._marcas_del_video(session)
        try:
            session.asaltos, session.fases = asaltos, fases
        except AttributeError:
            pass
        # Una sesión solo de tiempo-movimiento no tiene acciones y sí informe.
        if not session.annotations and not fases:
            QMessageBox.information(self.window, self._i18n.t("dialog.not_completed"), self._i18n.t("dialog.not_completed_msg"))
            return
        if self._en_modo_pro() and session.annotations:
            self._abrir_relatorio(session)
            return
        self.window.match_report.set_session(session, self._colors); self.navigation.show_report()

    def _marcas_del_video(self, session) -> tuple:
        """Los asaltos y las fases de ese combate: los del controlador si es el
        que está abierto; si no, los de su sesión guardada. (None, None)
        donde el deporte no los tiene."""
        video = getattr(session, "video_path", "") or ""
        if video and video == self._video_path:
            return self._asaltos_para_informe(), self._fases_a_lista()
        # Otra sesión: las fases, de sus filas PHASE; si es de antes de que
        # fueran filas, de la lista aparte que se guardaba.
        from karlos_core.tiempo_movimiento import separar_fases
        _acc, marcas = separar_fases(list(getattr(session, "annotations", []) or []))
        if marcas:
            return getattr(session, "asaltos", None), marcas
        if not video:
            return None, None
        try:
            active = self.session_manager.get_active_round(video)
            if active is None:
                return None, None
            ruta = self.session_manager._session_path(video, active["evaluator_id"], active["occasion"])
            data = self.session_manager._load_from_path(ruta) if ruta.exists() else None
        except (OSError, KeyError, TypeError):
            return None, None
        if not data:
            return None, None
        from karlos_core.tiempo_movimiento import asaltos_o_combate
        return (asaltos_o_combate(data.get("asaltos_por_atleta") or data.get("asaltos"),
                                  data.get("fight_start"), data.get("fight_end")),
                data.get("fases"))

    def _abrir_relatorio(self, session) -> None:
        """El informe del entrenador, en su propia ventana.

        Va aparte y no dentro de la navegacion para que se pueda dejar
        abierto al lado del video: lo que un entrenador hace con esto es
        mirarlo mientras comenta el combate, no en vez de verlo.
        """
        bi = self._bout_info
        # Se guarda en el controlador o Qt se lleva la ventana en cuanto
        # termina este metodo.
        rel = getattr(self, "_relatorio", None)
        if rel is None:
            rel = catalogo.activo().salidas().informe_entrenador()
            rel.setWindowTitle(self._i18n.t("dialog.relatorio_titulo", nome=identidad.en_marcha().nombre))
            rel.resize(920, 760)
            self._relatorio = rel
        try:
            rel.mostrar(list(session.annotations), self.video_manager.fps or 30.0,
                        bi.get("athlete_a_name", "") or catalogo.etiqueta("AKA"),
                        bi.get("athlete_b_name", "") or catalogo.etiqueta("AO"))
        except Exception as exc:      # noqa: BLE001
            _log.warning("No se pudo montar el informe", exc_info=True)
            QMessageBox.warning(self.window, "No se pudo montar el informe", str(exc))
            return
        rel.show()
        rel.raise_()
        rel.activateWindow()

    def _on_export_pdf(self) -> None:
        import os as _os; from datetime import datetime
        dt = datetime.now(); default_name = f"karlos_report_{dt.strftime('%Y%m%d_%H%M%S')}.pdf"
        if self._bout_info.get("athlete_a_name"):
            aka_fn = self._bout_info.get("athlete_a_name", catalogo.etiqueta("AKA")); ao_fn = self._bout_info.get("athlete_b_name", catalogo.etiqueta("AO"))
            default_name = f"Report_{aka_fn}_vs_{ao_fn}.pdf"
        import sys as _sys
        # Desde el código fuente, src/exports/reports: un dirname más que
        # cuando vivía en annotation_controller (F3.7), para que sea el mismo.
        base_dir = _os.path.join(_os.path.expanduser("~"), "Documents") if getattr(_sys, "frozen", False) else _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
        reports_dir = _os.path.join(base_dir, "Karlos Reports") if getattr(_sys, "frozen", False) else _os.path.join(base_dir, "exports", "reports")
        try: _os.makedirs(reports_dir, exist_ok=True)
        except OSError: reports_dir = _os.path.expanduser("~")
        default_path = _os.path.join(reports_dir, default_name)
        path, _ = QFileDialog.getSaveFileName(self.window, "Export Report to PDF", default_path, "PDF Files (*.pdf)")
        if not path: return
        sport_id, anns, sesion = self.window.match_report.datos_para_pdf()
        meta = getattr(sesion, 'bout_metadata', None) or self._bout_info
        session_data = {"duration_s": sesion.duration_s if sesion else 0.0, "fps": sesion.fps if sesion and sesion.fps > 0 else 30.0, "video_name": sesion.video_name if sesion else "Unknown"}
        ajustes = catalogo.activo().tiempo_movimiento()
        if ajustes and sesion is not None:
            # El PDF lleva los asaltos y las fases para la página de
            # tiempo-movimiento.
            asaltos, fases = self._marcas_del_video(sesion)
            session_data.update(asaltos=asaltos, fases=fases, gap_s=float(ajustes.get("gap_s", 2.0)),
                                analysis=self._analisis_del_combate())
        try:
            output_path = catalogo.activo().salidas().informe_pdf(output_path=path, bout_metadata=meta, annotations=anns, session_data=session_data, sport_id=sport_id)
            QMessageBox.information(self.window, "PDF Exported Successfully", f"Professional report generated:\n\n{output_path}")
        except Exception as exc:
            QMessageBox.critical(self.window, "Export Error", f"Failed to generate professional report:\n\n{str(exc)}")

    @staticmethod
    def _grab_chart_visible(chart_view, width: int, height: int) -> "PySide6.QtGui.QPixmap":
        from PySide6.QtGui import QPainter, QPixmap; from PySide6.QtCore import QCoreApplication
        w = chart_view
        if w is None: return QPixmap(width, height)
        w.resize(width, height); QCoreApplication.processEvents()
        pixmap = QPixmap(width, height); pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap); w.render(painter); painter.end()
        return pixmap

    def _export_session(self, session: FightSession, output_path: str | Path, *, fight_start: Optional[int] = None, fight_end: Optional[int] = None, fight_duration: Optional[float] = None) -> bool:
        # ── Migrate legacy combined levels before export ──────────────
        # Sessions from old builds stored the raw combined string in
        # ann.level; without migration _validate_schema aborts the export.
        clean_records = list(session.annotations)
        migrated = migrate_legacy_combined_levels(clean_records)
        if migrated:
            _log.info("Migrated %d legacy combined-level annotations before export", migrated)
        self.export_manager.set_bout_info(self._datos_con_analisis(session)); self.export_manager.set_records(clean_records)
        self.export_manager.set_sport_id(self._sport_meta.get("id", "karate"))
        self.export_manager.set_fps(session.fps if session.fps > 0 else 30.0)
        self.export_manager.set_fight_info(fight_start, fight_end, fight_duration)
        # La hoja de tiempo-movimiento, solo donde el deporte lo hace: el
        # karate no la tiene y su Excel no cambia.
        ajustes = catalogo.activo().tiempo_movimiento()
        if ajustes:
            asaltos, fases = self._marcas_del_video(session)
            # El del cuaderno abierto: la lista del Hub es la de ese
            # cuaderno, así que lo que se exporta es de ese análisis.
            analisis = self._analisis_del_combate()
            self.export_manager.set_tiempo_movimiento(
                asaltos, fases, float(ajustes.get("gap_s", 2.0)),
                derivar=analisis != "technical_tactical")
            self.export_manager.set_analisis(analisis)
        else:
            self.export_manager.sin_tiempo_movimiento()
        if str(output_path).lower().endswith(".csv"):
            return self._escribir_csv_combate(session, output_path, fight_start,
                                              fight_end)
        try: self.export_manager.export_xlsx(str(output_path)); return True
        except PermissionError:
            QMessageBox.warning(self.window, self._i18n.t("dialog.export_failed"), self._i18n.t("dialog.export_file_locked"))
            return False
        except ValueError as exc:
            # Validation failed — offer a forced export so the data can
            # always be extracted; issues land in "Validation Warnings".
            reply = QMessageBox.question(
                self.window, self._i18n.t("dialog.export_force_title"),
                f"{exc}\n\n{self._i18n.t('dialog.export_force_question')}",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return False
            try:
                self.export_manager.export_xlsx(str(output_path), force=True)
                QMessageBox.information(self.window, self._i18n.t("dialog.export_complete"), self._i18n.t("dialog.export_forced_note"))
                return True
            except Exception as exc2:
                QMessageBox.warning(self.window, self._i18n.t("dialog.export_failed"), f"Error: {exc2}")
                return False
        except Exception as exc:
            QMessageBox.warning(self.window, self._i18n.t("dialog.export_failed"), f"Error: {exc}")
            return False

    def _datos_con_analisis(self, session) -> dict:
        """Los datos del combate, diciendo el análisis del cuaderno abierto.

        Lo que se exporta es del cuaderno abierto (decisión 0008), y su
        análisis no puede depender de que se haya escrito al anotar: un
        cuaderno de tiempo-movimiento con solo [F] y [G] tampoco es completo.
        El completo no se escribe, como siempre: así sus salidas son las de
        la 1.0."""
        info = dict(session.bout_metadata or {})
        analisis = self._analisis_del_combate()
        if analisis != "complete":
            info["analysis"] = analisis
        else:
            # Una etiqueta vieja mal puesta (ID33 llevaba «time_motion» con
            # sus acciones del completo) no puede decir otro modo.
            info.pop("analysis", None)
        return info

    def _escribir_csv_combate(self, session, ruta, fight_start, fight_end) -> bool:
        """El combate entero en un solo CSV, que es el que se recarga."""
        csv_combate = catalogo.activo().salidas().csv_del_combate()
        # Las fases marcadas ya son filas del registro (categoría PHASE,
        # sin atleta): viajan con las acciones sin añadir nada.
        filas = list(session.annotations)
        try:
            csv_combate.escribir(
                ruta, filas,
                bout_info=self._datos_con_analisis(session),
                video=session.video_path or session.video_name,
                fps=session.fps if session.fps > 0 else 30.0,
                fight_start=fight_start, fight_end=fight_end,
                evaluador=getattr(self, "_evaluator_id", "") or "",
                ocasion=getattr(self, "_occasion", 1) or 1)
            return True
        except PermissionError:
            QMessageBox.warning(self.window, self._i18n.t("dialog.export_failed"),
                                self._i18n.t("dialog.export_file_locked"))
        except Exception as exc:      # noqa: BLE001
            _log.warning("No se pudo escribir %s", ruta, exc_info=True)
            QMessageBox.warning(self.window, self._i18n.t("dialog.export_failed"),
                                f"Error: {exc}")
        return False

    def _on_export_selected(self, indices: list) -> None:
        if not indices: return
        sessions_to_export = [self.sessions[i] for i in indices if 0 <= i < len(self.sessions)]
        if not sessions_to_export: return
        folder = QFileDialog.getExistingDirectory(self.window, "Export Selected Sessions to Folder", "")
        if not folder: return
        count = 0
        for session in sessions_to_export:
            if not session.annotations: continue
            name_base = Path(session.video_name).stem; export_path = Path(folder) / f"{name_base}_karlos.csv"
            fight_start: Optional[int] = None; fight_end: Optional[int] = None; fight_duration: Optional[float] = None
            session_data = self.session_manager.load_session(session.video_path)
            if session_data is not None:
                fight_start = session_data.get("fight_start"); fight_end = session_data.get("fight_end")
                if fight_start is not None and fight_end is not None:
                    fps = session.fps if session.fps > 0 else 30.0; fight_duration = abs(fight_end - fight_start) / fps
            if self._export_session(session, export_path, fight_start=fight_start, fight_end=fight_end, fight_duration=fight_duration): count += 1
        self.window.set_status_message(self._i18n.t("stat.batch_export", n=str(count), total=str(len(sessions_to_export)), folder=str(folder)))

    def _on_export_unified_dataset(self) -> None:
        if not self.sessions: QMessageBox.information(self.window, "Export Dataset", "No sessions loaded. Load a video folder first."); return
        clean = []; needs_review = []
        for s in self.sessions:
            if not s.annotations: continue
            reasons = getattr(s, "_needs_review_reasons", None)
            if reasons: needs_review.append(s)
            else: clean.append(s)
        if not clean and not needs_review: QMessageBox.information(self.window, "Export Dataset", "No annotated sessions to export."); return
        sin_marcar = [s for s in clean + needs_review if s.status != "Completed"]
        if sin_marcar:
            aviso = I18n().t("dialog.export_nao_concluidos", n=str(len(sin_marcar)))
            resp = QMessageBox.question(self.window, "Export Dataset", aviso,
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if resp != QMessageBox.Yes: return
        include_needs_review = False
        if needs_review:
            msg = f"{len(needs_review)} session(s) have quality warnings.\n\nInclude them in the export anyway?"
            reply = QMessageBox.question(self.window, "Quality Warnings", msg, QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.No)
            if reply == QMessageBox.Cancel: return
            include_needs_review = (reply == QMessageBox.Yes)
        sessions_to_export = clean[:]
        if include_needs_review: sessions_to_export.extend(needs_review)
        total_anns = sum(len(s.annotations) for s in sessions_to_export)
        msg = f"Ready to export {len(sessions_to_export)} sessions ({total_anns} annotations total)."
        proceed = QMessageBox.question(self.window, "Export Dataset", msg, QMessageBox.Ok | QMessageBox.Cancel)
        if proceed != QMessageBox.Ok: return
        from datetime import datetime; ts = datetime.now().strftime("%Y%m%d_%H%M%S"); default_name = f"KarlosDataset_{ts}"
        folder = QFileDialog.getExistingDirectory(self.window, "Select Export Folder", "")
        if not folder: return
        base = str(Path(folder) / default_name)
        import csv as _csv; import openpyxl; from openpyxl import Workbook; wb = Workbook()
        ws_summary = wb.active; ws_summary.title = "Summary"
        ws_summary.append(["Video", "Evaluator_ID", "Occasion", "Analysis Date", "Annotations", "Athlete A", "Athlete B", "Category", "Score", "Passed Validation"])
        csv_rows: list[dict] = []
        for session in sessions_to_export:
            data = self.session_manager.load_session(session.video_path)
            evaluator_id = data.get("evaluator_id", "default") if data else "default"
            occasion = data.get("occasion", 1) if data else 1
            meta = session.bout_metadata or {}
            reason_list = getattr(session, "_needs_review_reasons", None); passed = "No" if reason_list else "Yes"
            aka_name = meta.get("athlete_a_name", "—"); ao_name = meta.get("athlete_b_name", "—"); score_str = "—"
            if session.annotations:
                puntos = catalogo.activo().reglamento.puntos
                aka_s = sum(puntos(a.score) for a in session.annotations if getattr(a, "athlete", "") == "AKA")
                ao_s = sum(puntos(a.score) for a in session.annotations if getattr(a, "athlete", "") == "AO")
                score_str = f"{aka_s}–{ao_s}"
            ws_summary.append([session.video_name, evaluator_id, occasion, meta.get("analysis_date", "—"), len(session.annotations), aka_name, ao_name, meta.get("weight_category", "—"), score_str, passed])
            # Detail sheets
            self.export_manager.set_records(list(session.annotations)); self.export_manager.set_bout_info(meta)
            self.export_manager.set_sport_id(self._sport_meta.get("id", "karate")); self.export_manager.set_fps(session.fps if session.fps > 0 else 30.0)
            # El inicio y el fin del combate están en la sesión guardada
            # (FightSession no los lleva), como en «Exportar seleccionados».
            fs = (data or {}).get("fight_start", getattr(session, "fight_start", None))
            fe = (data or {}).get("fight_end", getattr(session, "fight_end", None)); fd = None
            if fs is not None and fe is not None:
                fps = session.fps if session.fps > 0 else 30.0; fd = abs(fe - fs) / fps if fps > 0 else None
            self.export_manager.set_fight_info(fs, fe, fd)
            # Las hojas y las filas las da el exportador: la fila de cada
            # acción es la de su hoja «Data» (antes se pedía a un
            # _annotation_to_row que nunca existió y no se guardaba nada).
            filas = self.export_manager.hojas_del_combate(wb, f"{session.video_name[:25]}_{evaluator_id}_{occasion}")
            for fila in filas:
                row = {col: "" for col in self.export_manager.ANNOTATION_COLUMNS}
                row.update(fila); row["Evaluator_ID"] = evaluator_id; row["Occasion"] = str(occasion)
                csv_rows.append(row)
        xlsx_path = base + ".xlsx"; wb.save(xlsx_path)
        csv_path = base + ".csv"; csv_columns = list(self.export_manager.ANNOTATION_COLUMNS) + ["Evaluator_ID", "Occasion"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=csv_columns, extrasaction="ignore"); writer.writeheader()
            for row in csv_rows: writer.writerow(row)
        QMessageBox.information(self.window, "Export Complete", f"Consolidated dataset exported:\n\n  XLSX: {xlsx_path}\n  CSV:  {csv_path}\n\n  {len(sessions_to_export)} sessions\n  {len(csv_rows)} annotation rows")
        self.window.set_status_message(I18n().t("stat.conjunto_exportado", n=str(len(sessions_to_export)), m=str(len(csv_rows))))

    def _on_view_current_report(self) -> None:
        if self.active_session_idx < 0: QMessageBox.information(self.window, self._i18n.t("dialog.no_sessions"), "No active session."); return
        self._on_view_report(self.active_session_idx)

    def _on_compare_evaluators(self, idx: int) -> None:
        """Compare two evaluator sessions for the same video."""
        if idx < 0 or idx >= len(self.sessions): return
        session = self.sessions[idx]; all_sessions = self.session_manager.list_sessions(session.video_path)
        completed = [s for s in all_sessions if s.get("annotation_count", 0) > 0]
        if len(completed) < 2: QMessageBox.information(self.window, "Compare Evaluators", "This video has only one completed session."); return
        if len(completed) > 2:
            evaluators_seen: set[str] = set(); picked: list[dict] = []
            for s in completed:
                if s["evaluator_id"] not in evaluators_seen: evaluators_seen.add(s["evaluator_id"]); picked.append(s)
                if len(picked) == 2: break
            if len(picked) < 2: picked = completed[:2]
        else: picked = completed[:2]
        from pathlib import Path as _Path; import json as _json
        def load_anns(s): data = _json.loads(_Path(s["path"]).read_text("utf-8")); return [self.session_manager.annotation_from_dict(a) for a in data.get("annotations", [])]
        anns_a = load_anns(picked[0]); anns_b = load_anns(picked[1])
        TOLERANCE = 30; matched_pairs: list[tuple] = []; unmatched_a = list(range(len(anns_a))); unmatched_b = list(range(len(anns_b)))
        for i, aa in enumerate(anns_a):
            best_j = -1; best_dist = TOLERANCE + 1
            for j, bb in enumerate(anns_b):
                if j not in unmatched_b: continue
                dist = abs(aa.f_start - bb.f_start)
                if dist < best_dist: best_dist = dist; best_j = j
            if best_j >= 0: matched_pairs.append((i, best_j, best_dist)); unmatched_a.remove(i); unmatched_b.remove(best_j)
        agreements = {"Athlete": 0, "Category": 0, "Technique": 0, "Level": 0, "Score": 0}; total = len(matched_pairs)
        for ai, bi, _ in matched_pairs:
            aa, bb = anns_a[ai], anns_b[bi]
            if getattr(aa, "athlete", "") == getattr(bb, "athlete", ""): agreements["Athlete"] += 1
            if aa.category == bb.category: agreements["Category"] += 1
            if aa.technique == bb.technique: agreements["Technique"] += 1
            if aa.level == bb.level: agreements["Level"] += 1
            if aa.score == bb.score: agreements["Score"] += 1
        lines = [f"{picked[0]['evaluator_id']} (occ {picked[0]['occasion']}): {len(anns_a)} events",
                 f"{picked[1]['evaluator_id']} (occ {picked[1]['occasion']}): {len(anns_b)} events",
                 f"", f"Matched pairs: {total}", f"Unmatched A: {len(unmatched_a)}", f"Unmatched B: {len(unmatched_b)}", f""]
        for col in ["Athlete", "Category", "Technique", "Level", "Score"]:
            pct = (agreements[col] / total * 100) if total > 0 else 0
            lines.append(f"  {col}: {agreements[col]}/{total} ({pct:.0f}%)")
        QMessageBox.information(self.window, "Evaluator Comparison", "\n".join(lines))

    def _export_xlsx(self) -> None:
        records = self.window.table_view.records
        if not records: QMessageBox.information(self.window, self._i18n.t("dialog.nothing_export"), self._i18n.t("dialog.nothing_export")); return
        aka = self._bout_info.get("athlete_a_name", "").strip(); ao = self._bout_info.get("athlete_b_name", "").strip()
        default_name = f"KarlosReport_{aka}_vs_{ao}.xlsx".replace(" ", "_") if aka and ao else f"KarlosReport_UnnamedBout_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        default_name = Path(default_name).with_suffix(".csv").name
        path, _ = QFileDialog.getSaveFileName(
            self.window, self._i18n.t("dialog.exportar_combate"), default_name, "CSV (*.csv)")
        if not path: return
        if not path.lower().endswith(".csv"): path += ".csv"
        vm = self.video_manager
        session = FightSession(id=self.active_session_idx if self.active_session_idx >= 0 else 0, video_path=self._video_path or "", video_name=Path(self._video_path).name if self._video_path else "workspace_export", status="Completed", bout_metadata=dict(self._bout_info), annotations=list(records), fps=vm.fps)
        ok = self._export_session(session, path, fight_start=vm.fight_start, fight_end=vm.fight_end, fight_duration=vm.fight_duration_s())
        if not ok: return
        # Donde el deporte hace tiempo-movimiento, al lado del CSV (los datos,
        # que se vuelven a cargar) va el Excel del análisis: con la matriz,
        # un luchador a la izquierda y el otro a la derecha. el especialista abrió el
        # CSV y pedía justo eso (12-10-2026); el Excel solo salía del Hub.
        if catalogo.activo().tiempo_movimiento():
            xlsx = str(Path(path).with_suffix(".xlsx"))
            if self._export_session(session, xlsx, fight_start=vm.fight_start, fight_end=vm.fight_end, fight_duration=vm.fight_duration_s()):
                QMessageBox.information(
                    self.window, self._i18n.t("tm.exportado_titulo"),
                    self._i18n.t("tm.exportado_dos", csv=Path(path).name, xlsx=Path(xlsx).name,
                                 n=str(len(records))))
                self.window.set_status_message(f"{Path(path).name} · {Path(xlsx).name}")
                return
        QMessageBox.information(
            self.window, self._i18n.t("dialog.exportado_titulo"),
            self._i18n.t("dialog.exportado_msg", nome=Path(path).name, n=str(len(records))))
        self.window.set_status_message(
            self._i18n.t("stat.exportado", nome=Path(path).name, n=str(len(records))))

    def _cargar_csv_combate(self) -> None:
        """Abrir un CSV de combate y seguir editando sus acciones."""
        csv_combate = catalogo.activo().salidas().csv_del_combate()
        ruta, _ = QFileDialog.getOpenFileName(
            self.window, "Cargar combate", "", "CSV (*.csv)")
        if not ruta:
            return
        try:
            cabecera, acciones = csv_combate.leer(ruta)
        except Exception as exc:      # noqa: BLE001
            _log.warning("No se pudo leer %s", ruta, exc_info=True)
            QMessageBox.warning(self.window, "No se pudo leer",
                                f"{Path(ruta).name}\n\n{exc}")
            return
        if not acciones:
            QMessageBox.warning(self.window, self._i18n.t("dialog.sem_acoes_titulo"),
                                self._i18n.t("dialog.sem_acoes", nome=Path(ruta).name))
            return
        video = csv_combate.buscar_video(ruta, cabecera)
        if not video:
            # Sin el video las acciones no se pueden revisar, que es para
            # lo que se cargan: se pide antes de tocar nada.
            nombre = cabecera.get("video", "")
            QMessageBox.information(
                self.window, self._i18n.t("dialog.onde_video_titulo"),
                self._i18n.t("dialog.onde_video", nome=nombre or self._i18n.t("dialog.um_video")))
            video, _ = QFileDialog.getOpenFileName(
                self.window, self._i18n.t("dialog.video_do_combate"), "",
                self._i18n.t("dialog.filtro_video"))
            if not video:
                return
        # Si el video ya esta abierto no se recarga: recargarlo perderia
        # la posicion y el analisis que ya tiene cargado, y desde el hub
        # se llega aqui con el video puesto.
        if self._video_path != video:
            self._video_path = video
            if not self.video_manager.load(video):
                QMessageBox.critical(
                    self.window, self._i18n.t("dialog.nao_abre_titulo"), video)
                return
        self._bout_info.update(self._bout_info_de_cabecera(cabecera))
        self.window.table_view.clear_all()
        for a in acciones:
            self.window.table_view.add_annotation(a)
        # Las filas PHASE son las fases marcadas: ya están en el registro.
        self._sincronizar_fases()
        self._fijar_analisis()
        self._update_live_stats()
        # Guardar de inmediato. Cargar un CSV y no dejarlo en sesion
        # significa que al cerrar se pierde otra vez todo: es justo el
        # problema que esta funcion viene a resolver, y no resolverlo
        # seria peor que no tenerla, porque el evaluador cree que ya
        # esta a salvo.
        if 0 <= self.active_session_idx < len(self.sessions):
            ses = self.sessions[self.active_session_idx]
            ses.annotations = list(acciones)
            ses.bout_metadata = dict(self._bout_info)
        self._save_session()
        self._update_timeline()
        self._sync_corner_colors()
        self.window.set_status_message(
            self._i18n.t("stat.carregado", nome=Path(ruta).name, n=str(len(acciones)),
                         video=Path(video).name))

    @staticmethod
    def _bout_info_de_cabecera(cabecera: dict) -> dict:
        """Pasar la cabecera del CSV a los campos de Bout Info."""
        import re
        info = {}
        for clave, destino in (("competition", "competition_name"),
                               ("phase", "event_phase"),
                               ("category", "category_type"),
                               ("weight", "weight_category"),
                               ("pool", "pool"), ("tatami", "tatami"),
                               ("bout_number", "bout_number"),
                               ("bout_round", "bout_round"),
                               ("evaluator", "evaluator_name"),
                               ("institution", "evaluator_institution")):
            if cabecera.get(clave):
                info[destino] = cabecera[clave]
        # El modo viaja en el CSV desde la 1.2 y vuelve con él: un combate
        # reimportado sigue siendo del análisis con que se anotó.
        if cabecera.get("analysis") in ("time_motion", "technical_tactical", "complete"):
            info["analysis"] = cabecera["analysis"]
        for lado, campo_n, campo_p in (("aka", "athlete_a_name", "athlete_a_country"),
                                       ("ao", "athlete_b_name", "athlete_b_country")):
            bruto = cabecera.get(lado, "")
            if not bruto:
                continue
            m = re.match(r"^(.*?)\s*\(([A-Z]{3})\)\s*$", bruto)
            if m:
                info[campo_n], info[campo_p] = m.group(1).strip(), m.group(2)
            else:
                info[campo_n] = bruto.strip()
        return info
