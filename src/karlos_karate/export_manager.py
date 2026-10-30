"""Export manager for KARLOS ANNOTATOR.

Handles exporting Annotation records and bout metadata into a single
Excel (.xlsx) workbook with two sheets:
  - "Bout Info"   → bout metadata + fight segment overview + time totals
  - "Annotations" → temporal annotation columns + bout_id foreign key
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side

from karlos_core.models.annotation import Annotation


def _puntua(sport_id: str, score: str) -> bool:
    """Si esa puntuación puntúa en ese deporte: lo dice su reglamento
    (decisión 0007), no una lista de códigos escrita aquí."""
    from karlos_core import catalogo
    try:
        return catalogo.paquete(sport_id).reglamento.puntos(score) > 0
    except KeyError:
        return False


def _zonas(sport_id: str) -> list[str]:
    """Las zonas del deporte, las de su configuración."""
    from karlos_core import catalogo
    try:
        return list(catalogo.paquete(sport_id).configuracion().get("levels", []))
    except KeyError:
        return []


# ------------------------------------------------------------------
# Build info — embedded in every export for traceability
# ------------------------------------------------------------------
# Import from _build_info.py (generated at build time by the build script).
# If the module doesn't exist (e.g. running from source without a build),
# fall back to "dev" to distinguish from a failed build capture.
try:
    from karlos_core._build_info import BUILD_COMMIT, BUILD_TIMESTAMP  # type: ignore[import-untyped]
except ImportError:
    BUILD_COMMIT: str = "dev"
    BUILD_TIMESTAMP: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ------------------------------------------------------------------
# Styling constants — clean Apple-dark inspired header look
# ------------------------------------------------------------------
_HEADER_FONT = Font(name="Inter", bold=True, size=11, color="FFFFFF")
_HEADER_FILL = PatternFill(start_color="2C2C2E", end_color="2C2C2E", fill_type="solid")
_HEADER_ALIGN = Alignment(horizontal="center", vertical="center")
_CELL_ALIGN = Alignment(vertical="center")
_THIN_BORDER = Border(
    left=Side(style="thin", color="CECED2"),
    right=Side(style="thin", color="CECED2"),
    top=Side(style="thin", color="CECED2"),
    bottom=Side(style="thin", color="CECED2"),
)
_META_LABEL_FONT = Font(name="Inter", bold=True, size=11, color="1C1C1E")
_META_VALUE_FONT = Font(name="Inter", size=11, color="1C1C1E")
_SECTION_FONT = Font(name="Inter", bold=True, size=11, color="D5A021")
_SEPARATOR_BORDER = Border(
    top=Side(style="medium", color="2C2C2E"),
)


class ExportManager:
    """Manages XLSX export of annotation records and bout metadata.

    Attributes:
        records: List of annotations to export.
        _bout_info: Dict with bout metadata for the "Bout Info" sheet.
    """

    # Column order for the "Annotations" sheet — denormalized flat dataset.
    # Bout metadata columns are injected at the beginning so every row is
    # self-contained for Data Science / Machine Learning workflows.
    #
    # **FASE 3 REFACTOR**: This list now serves as the BASE column order.
    # Dynamic Sport_* columns from sport_specific_data are appended at runtime
    # by _collect_dynamic_columns() to ensure all sport-specific fields are exported.
    ANNOTATION_COLUMNS = [
        "Export_Build",              # commit:hash | timestamp (traceability)
        "Bout_Event",                # Competition Name
        "Bout_Phase",                # Event Phase
        "Weight_Category",           # Weight Category
        "AKA_Name",                  # Fighter AKA Name (Athlete A)
        "AO_Name",                   # Fighter AO Name (Athlete B)
        "Timestamp",
        "Match_Time_s",              # Tiempo relativo desde la 1ª anotación
        "Active_Play_Cumulative_s",  # Tiempo real de combate acumulado (sin Referee Stops)
        "Phase",                     # Minute_1, Minute_2, Minute_3, Atoshibaraku
        "Athlete",
        "Category",
        "Technique",
        "Level",
        "Modifier",                  # Mapea stance (guardia/postura)
        "Score",
        "Sequence_ID",               # Algoritmo de ventana temporal < 1.5s
        "Action_Result",             # "Scored" / "No_Score"
        "subcategory",
        "target",
        "f_start",
        "f_end",
        "duration_s",
        "notes",
        "round",
        "bout_id",
        "video_file",
        "id",
    ]

    # Temporal window for sequence grouping (milliseconds).
    # If the time difference between two consecutive annotations by the
    # same athlete is ≤ SEQUENCE_WINDOW_MS, they belong to the same sequence.
    SEQUENCE_WINDOW_MS: int = 1500

    # Keys & friendly labels for the "Bout Info" sheet (Karate WKF default).
    _BOUT_META_KEYS_KARATE = [
        ("bout_id", "Bout ID"),
        ("competition_name", "Competition Name"),
        ("event_phase", "Event Phase"),
        ("category_type", "Category Type"),
        ("weight_category", "Weight Category"),
        ("pool", "Pool / Group"),
        ("tatami", "Tatami"),
        ("athlete_a_name", "Athlete A Name"),
        ("athlete_a_country", "Athlete A Country"),
        ("athlete_a_club", "Athlete A Club / Dojo"),
        ("athlete_b_name", "Athlete B Name"),
        ("athlete_b_country", "Athlete B Country"),
        ("athlete_b_club", "Athlete B Club / Dojo"),
        ("bout_number", "Bout Number"),
        ("bout_round", "Round"),
        ("evaluator_name", "Evaluator Name"),
        ("evaluator_institution", "Evaluator Institution"),
        ("analysis_date", "Analysis Date"),
    ]

    # Keys & friendly labels for the "Bout Info" sheet (Kickboxing WAKO).
    _BOUT_META_KEYS_KB = [
        ("competition_name", "Competition Name"),
        ("event_phase", "Event Phase"),
        ("gender", "Gender"),
        ("weight_category", "Weight Category"),
        ("num_rounds", "Number of Rounds"),
        ("round_duration", "Round Duration"),
        ("competition_type", "Type of Competition"),
        ("discipline", "Discipline"),
        ("age_category", "Age Category"),
        ("athlete_a_name", "Athlete A Name"),
        ("athlete_a_country", "Athlete A Country"),
        ("athlete_a_club", "Athlete A Club"),
        ("athlete_a_corner", "Athlete A Corner"),
        ("athlete_a_color", "Athlete A Corner Color"),
        ("athlete_b_name", "Athlete B Name"),
        ("athlete_b_country", "Athlete B Country"),
        ("athlete_b_club", "Athlete B Club"),
        ("athlete_b_corner", "Athlete B Corner"),
        ("athlete_b_color", "Athlete B Corner Color"),
        ("evaluator_name", "Evaluator Name"),
        ("evaluator_institution", "Evaluator Institution"),
        ("analysis_date", "Analysis Date"),
    ]

    def __init__(self) -> None:
        """Initialize the export manager."""
        self.records: list[Annotation] = []
        self._bout_info: dict[str, str] = {}
        self._fight_start: int | None = None
        self._fight_end: int | None = None
        self._fight_duration: float | None = None
        self._sport_id: str = "karate"
        # El tiempo-movimiento (asaltos, fases marcadas, hueco), solo donde
        # el deporte lo hace: sin él la hoja no existe y el karate no cambia.
        self._tiempo_movimiento: tuple | None = None
        # El análisis del combate (taekwondo): decide qué hojas lleva el
        # Excel. None en el karate, cuyo Excel no cambia.
        self._analisis: str | None = None

    def set_analisis(self, analisis: str | None) -> None:
        """Técnico-táctico, tiempo-movimiento o completo: cada uno lleva las
        hojas de lo que recoge (Johan, 8-10-2026)."""
        self._analisis = analisis or None

    def set_tiempo_movimiento(self, asaltos: list | None, fases: list | None,
                              hueco_s: float = 2.0, derivar: bool = True) -> None:
        """Lo que hace falta para la hoja «Time-Motion», o None para que no
        la haya: los asaltos y las fases tal como van en la sesión, y si las
        acciones tienen duración de la que derivar."""
        # Los asaltos pueden venir por atleta ({atleta: [...]}): se guardan tal cual.
        asaltos = dict(asaltos) if isinstance(asaltos, dict) else list(asaltos or [])
        self._tiempo_movimiento = (asaltos, list(fases or []), float(hueco_s), bool(derivar))

    def sin_tiempo_movimiento(self) -> None:
        self._tiempo_movimiento = None
        self._analisis = None

    @staticmethod
    def _merged_stopped_duration(records: list[Annotation], fps: float) -> float:
        """Union of REFEREE STOP frame intervals across both athletes.

        Delegates to the shared utility function in merge_utils to avoid
        duplicating the merge logic.
        """
        from karlos_core.utils.merge_utils import merge_referee_stop_intervals
        return merge_referee_stop_intervals(records, fps)

    def set_fps(self, fps: float) -> None:
        """Set the frames-per-second rate for time calculations.

        Args:
            fps: Frames per second (e.g. 30.0, 60.0).
        """
        self._fps = fps if fps > 0 else 30.0

    def set_sport_id(self, sport_id: str) -> None:
        """Set the sport ID for sport-specific export formatting.

        Args:
            sport_id: e.g. "karate" or "kickboxing".
        """
        self._sport_id = sport_id

    @property
    def _BOUT_META_KEYS(self) -> list[tuple[str, str]]:
        """Return the correct metadata keys for the current sport.

        Fuera del kickboxing, las del karate con el área y el club como los
        nombra cada deporte (decisión 0007): «Tatami» y «Club / Dojo» en el
        karate, «Ring» y «Club / Gym» en el boxeo…
        """
        if self._sport_id == "kickboxing":
            return self._BOUT_META_KEYS_KB + self._resultado_y_guardias()
        area, club = self._en_ingles("bout.tatami", "Tatami"), self._en_ingles("bout.club", "Club / Dojo")
        nombres = {"tatami": area, "athlete_a_club": f"Athlete A {club}",
                   "athlete_b_club": f"Athlete B {club}"}
        return ([(k, nombres.get(k, v)) for k, v in self._BOUT_META_KEYS_KARATE]
                + self._resultado_y_guardias())

    def _resultado_y_guardias(self) -> list[tuple[str, str]]:
        """El resultado y la guardia de cada uno, si el deporte los trae en
        su configuración (decisión 0007); el karate no los trae."""
        from karlos_core import catalogo
        try:
            datos = catalogo.paquete(self._sport_id).configuracion().get("bout_info", {})
        except KeyError:
            return []
        extra = []
        if datos.get("decisions"):
            extra += [("bout_winner", "Winner"), ("bout_ending", "Decision")]
        if datos.get("guards"):
            extra += [("athlete_a_guard", "Athlete A Guard"), ("athlete_b_guard", "Athlete B Guard")]
        return extra

    def _en_ingles(self, clave: str, defecto: str) -> str:
        """Un texto del deporte en inglés, la lengua del Excel."""
        from karlos_core import catalogo
        try:
            propio = catalogo.paquete(self._sport_id).textos().get(clave, {})
        except KeyError:
            propio = {}
        return propio.get("en", defecto)

    def _fase(self, activo_s) -> str:
        from karlos_core import catalogo
        return catalogo.paquete(self._sport_id).reglamento.fase(float(activo_s or 0.0))

    def _nombres_de_columna(self) -> dict[str, str]:
        """Las columnas con el nombre de cada competidor en este deporte; en
        el karate («AKA_Name», «AO_Name») no cambia nada."""
        from karlos_core import catalogo
        try:
            a, b = (c.etiqueta for c in catalogo.paquete(self._sport_id).competidores)
        except KeyError:
            return {}
        nombres = {"AKA_Name": f"{a}_Name", "AO_Name": f"{b}_Name"}
        return {k: v for k, v in nombres.items() if k != v}

    def set_records(self, records: list[Annotation]) -> None:
        """Set the records to be exported.

        Args:
            records: List of Annotation instances.
        """
        self.records = records

    def set_bout_info(self, bout_info: dict[str, str]) -> None:
        """Set bout metadata to be written into the "Bout Info" sheet.

        Args:
            bout_info: Dict with bout metadata from BoutInfoPopup.
        """
        self._bout_info = bout_info or {}

    def set_fight_info(
        self,
        fight_start: int | None,
        fight_end: int | None,
        fight_duration: float | None,
    ) -> None:
        """Set fight segment data from VideoManager for the bout info sheet.

        Args:
            fight_start: Fight start frame index.
            fight_end: Fight end frame index.
            fight_duration: Fight duration in seconds.
        """
        self._fight_start = fight_start
        self._fight_end = fight_end
        self._fight_duration = fight_duration

    # ------------------------------------------------------------------
    # Schema validation (pre-export guard)
    # ------------------------------------------------------------------

    def _collect_validation_issues(self) -> list[str]:
        """Collect every schema problem without aborting.

        Returns:
            One message per issue found; empty list when the data is clean.
        """
        import re

        issues: list[str] = []
        if not self.records:
            return ["No records to export."]

        fps = 30.0
        if (self._fight_start is not None and self._fight_end is not None
                and self._fight_duration and self._fight_duration > 0):
            total_frames = self._fight_end - self._fight_start
            if total_frames > 0:
                fps = total_frames / self._fight_duration

        seq_pattern = re.compile(r"^SEQ_\d{3}$")

        for i, ann in enumerate(self.records):
            # 1. Level must not contain unparsed " | "
            if ann.level and " | " in ann.level:
                issues.append(
                    f"Row {i}: Level '{ann.level}' contains unparsed ' | '. "
                    "This indicates a combined level string that was not "
                    "parsed by parse_combined_level()."
                )

            # 2. Sequence_ID format (if present in sport_specific_data)
            seq_id = (ann.sport_specific_data or {}).get("sequence_id", "")
            if seq_id and not seq_pattern.match(seq_id):
                issues.append(
                    f"Row {i}: Sequence_ID '{seq_id}' does not match "
                    "pattern SEQ_\\d{3}."
                )

        # 3. Total Active Time + Total Stopped Time ≈ fight_duration
        if self._fight_duration and self._fight_duration > 0:
            from karlos_core.utils.merge_utils import merge_referee_stop_intervals
            total_stopped = merge_referee_stop_intervals(self.records, fps)
            total_active = max(0.0, self._fight_duration - total_stopped)
            combined = total_active + total_stopped
            tolerance = 1.0  # 1 second tolerance for rounding
            if abs(combined - self._fight_duration) > tolerance:
                issues.append(
                    f"Time validation failed: Total Active ({total_active:.2f}s) + "
                    f"Total Stopped ({total_stopped:.2f}s) = {combined:.2f}s, "
                    f"but fight_duration = {self._fight_duration:.2f}s "
                    f"(tolerance={tolerance}s)."
                )

        return issues

    def _validate_schema(self) -> None:
        """Validate annotation data before writing the export file.

        Raises:
            ValueError: If any validation check fails, listing every issue
                found so corrupt data is never silently exported.
        """
        issues = self._collect_validation_issues()
        if issues:
            raise ValueError("\n".join(issues) + "\nAborting export.")

    # ------------------------------------------------------------------
    # XLSX Export
    # ------------------------------------------------------------------

    def export_xlsx(
        self,
        output_path: Optional[str | Path] = None,
        *,
        force: bool = False,
    ) -> str:
        """Export records and metadata to an Excel workbook with two sheets.

        If no output path is provided, generates a default filename with
        timestamp in the current working directory.

        When ``force`` is True, validation problems no longer abort the
        export: the workbook is written anyway and every issue found is
        listed in an extra "Validation Warnings" sheet so the data can
        always be extracted and audited afterwards.

        Sheet 1 — "Bout Info":
            - Bout metadata (Field | Value)
            - Separator
            - Fight segment overview (Fight Start Frame, Fight End Frame,
              Fight Duration)
            - Total Active Time (sum of all annotation durations)
            - Total Stopped Time (fight duration - active)

        Sheet 2 — "Annotations": temporal annotation columns + bout_id

        Args:
            output_path: Optional destination file path (.xlsx).

        Returns:
            The path where the XLSX was saved.

        Raises:
            ValueError: If there are no records to export.
        """
        if not self.records:
            raise ValueError("No records to export.")

        # Validate schema before writing — catch corrupt data early.
        # In force mode the issues are collected instead of aborting and
        # reported inside the workbook itself.
        validation_issues: list[str] = []
        if force:
            validation_issues = self._collect_validation_issues()
        else:
            self._validate_schema()

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"karlos_labels_{timestamp}.xlsx"

        output_path = Path(output_path)

        wb = Workbook()

        # ---- Sheet 1: Bout Info -----------------------------------------
        ws_meta = wb.active
        ws_meta.title = "Bout Info"
        self._write_bout_info_sheet(ws_meta)

        # ---- Sheet 2: Annotations ---------------------------------------
        ws_data = wb.create_sheet("Annotations")
        self._write_annotations_sheet(ws_data)

        if self._analisis:
            # Las hojas de su análisis y nada más. El técnico-táctico recoge
            # acciones como eventos; el tiempo-movimiento, fases; el
            # integrado, las dos cosas.
            if self._analisis != "time_motion":
                self._write_tecnico_sheet(wb.create_sheet("Technical-Tactical"))
            if self._analisis != "technical_tactical" and self._tiempo_movimiento is not None:
                self._write_time_motion_sheet(wb.create_sheet("Time-Motion"))
                # La matriz del especialista: un bloque por atleta, lado a lado.
                self._write_time_motion_matrix(wb.create_sheet("Time-Motion matrix"))
        else:
            # ---- Sheet 3: Athlete Comparison -----------------------------
            ws_comp = wb.create_sheet("Athlete Comparison")
            self._write_comparison_sheet(ws_comp)

            # ---- Sheet 4: Technical-Tactical Analysis (Kickboxing only) -
            if self._sport_id == "kickboxing":
                ws_tech = wb.create_sheet("Technical-Tactical Analysis")
                self._write_technical_tactical_sheet(ws_tech)

            # ---- Time-Motion: solo donde el deporte lo hace --------------
            if self._tiempo_movimiento is not None:
                self._write_time_motion_sheet(wb.create_sheet("Time-Motion"))

        # ---- Sheet 5: Validation Warnings (forced exports only) ---------
        if force and validation_issues:
            ws_warn = wb.create_sheet("Validation Warnings")
            ws_warn.append(["#", "Issue"])
            for cell in ws_warn[1]:
                cell.font = Font(bold=True)
            for n, issue in enumerate(validation_issues, start=1):
                ws_warn.append([n, issue])
            ws_warn.column_dimensions["B"].width = 100

        wb.save(output_path)
        return str(output_path)

    # ------------------------------------------------------------------
    # CSV Export (Scientific)
    # ------------------------------------------------------------------

    def export_csv(self, output_path: Optional[str | Path] = None) -> str:
        """Export annotations to a CSV file with temporal sequence grouping.

        The Sequence_ID algorithm groups consecutive annotations by the same
        athlete if the time difference (in milliseconds) between their
        f_start frames is ≤ SEQUENCE_WINDOW_MS (1500 ms by default).

        The CSV contains only annotation data (no repeated bout metadata).
        Bout context is encoded in the filename (e.g. "KarlosReport_AKA_vs_AO.csv")
        and stored separately in the companion metadata JSON for XLSX exports.

        Args:
            output_path: Optional destination file path (.csv).

        Returns:
            The path where the CSV was saved.

        Raises:
            ValueError: If there are no records to export.
        """
        if not self.records:
            raise ValueError("No records to export.")

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"karlos_labels_{timestamp}.csv"

        output_path = Path(output_path)

        # ── REGLA 1: Ordenación Cronológica Absoluta ──────────────────
        # Mezclar AKA y AO en un flujo temporal continuo para que el APC
        # sea monótono estrictamente creciente.
        self.records.sort(key=lambda x: x.f_start)

        # Compute sequence IDs
        sequence_ids = self._compute_sequence_ids()

        # ── Calcular FPS desde fight_start/fight_end ──────────────────
        fps = 30.0
        if (self._fight_start is not None and self._fight_end is not None
                and self._fight_duration):
            total_frames = self._fight_end - self._fight_start
            if total_frames > 0 and self._fight_duration > 0:
                fps = total_frames / self._fight_duration

        # Build denormalized flat rows — bout metadata is injected into
        # every annotation row so the dataset is self-contained for DS/ML.
        rows = []

        # ── Pre-calcular: Referee Stops INDIVIDUALES por atleta ────
        # En Karate WKF, cada atleta (AKA/AO) marca sus propios Referee Stops.
        # El tiempo de pausa de AKA solo se resta al Active_Play de AKA,
        # y el tiempo de pausa de AO solo se resta al Active_Play de AO.
        aka_stops = sorted(
            [r for r in self.records if r.category == "REFEREE STOP" and r.athlete == "AKA"],
            key=lambda r: r.f_start,
        )
        ao_stops = sorted(
            [r for r in self.records if r.category == "REFEREE STOP" and r.athlete == "AO"],
            key=lambda r: r.f_start,
        )

        # ── Calcular tiempo activo total para detectar Atoshibaraku ──
        total_stopped = (sum(r.duration_s or 0.0 for r in aka_stops)
                         + sum(r.duration_s or 0.0 for r in ao_stops))
        if self._fight_start is not None and self._fight_end is not None:
            total_active_play = max(
                0.0, (self._fight_end - self._fight_start) / fps - total_stopped
            )
        else:
            total_active_play = 0.0

        # ── Fase 1: Extracción Segura de Metadatos del Combate ──────────
        bout_event = self._bout_info.get("competition_name", "") or ""
        bout_phase = self._bout_info.get("event_phase", "") or ""
        weight_category = self._bout_info.get("weight_category", "") or ""
        aka_name = self._bout_info.get("athlete_a_name", "") or ""
        ao_name = self._bout_info.get("athlete_b_name", "") or ""

        # ── PARCHE 2: Inicializar prev_apc para blindaje de monotonía ──
        prev_apc = 0.0

        for i, ann in enumerate(self.records):
            row = ann.to_csv_row(i + 1, sequence_ids[i])

            # ── Fase 3: Inyección de Metadatos al Principio de cada Fila ──
            row["Export_Build"] = f"commit:{BUILD_COMMIT} | {BUILD_TIMESTAMP}"
            row["Bout_Event"] = bout_event
            row["Bout_Phase"] = bout_phase
            row["Weight_Category"] = weight_category
            row["AKA_Name"] = aka_name
            row["AO_Name"] = ao_name

            # ── REGLA 3: Purificación Biomecánica de Técnicas ────
            # Stripear niveles quemados (Jodan/Chudan/Gedan) para
            # evitar contaminación categórica — el nivel ya existe
            # en la columna independiente "Level".
            tech_raw = ann.technique
            for suffix in (" Jodan", " Chudan", " Gedan"):
                tech_raw = tech_raw.replace(suffix, "")

            # ── REGLA 4: Limpieza de Pausas de Árbitro ──────────
            # Extraer el motivo real tras " - " (Doctor, Coach, End of bout, etc.)
            if ann.category == "REFEREE STOP":
                parts = tech_raw.split(" - ")
                tech_raw = parts[-1].strip() if len(parts) > 1 else tech_raw.strip()
            row["Technique"] = tech_raw.strip()

            # ── PARCHE 1: Limpieza Absoluta del Árbitro ─────────
            # Forzar "Referee" en la técnica si la categoría es REFEREE STOP,
            # para eliminar cualquier nombre residual de golpe.
            if row.get("Category") == "REFEREE STOP":
                row["Technique"] = "Referee"

            # ── REGLA 6: Inyección de la Llave Relacional (bout_id) ──
            if not row.get("bout_id"):
                aka = self._bout_info.get("athlete_a_name", "Unknown")
                ao = self._bout_info.get("athlete_b_name", "Unknown")
                date = datetime.now().strftime("%Y%m%d")
                row["bout_id"] = f"BOUT_{date}_{aka}_vs_{ao}"

            # ── REGLA 5: Estandarización de Valores Nulos en Score ──
            if row.get("Score") in ("NONE", None, ""):
                row["Score"] = ""

            # ── ETL: Calcular Match_Time_s desde fight_start ────
            # Tiempo transcurrido desde fight_start (o primer frame de
            # anotación si fight_start es 0/None) hasta f_start
            # de esta técnica, dividido por FPS.
            if fps > 0:
                base_frame = self._fight_start if (self._fight_start is not None and self._fight_start > 0) else self.records[0].f_start
                row["Match_Time_s"] = round((ann.f_start - base_frame) / fps, 1)
            else:
                row["Match_Time_s"] = 0.0

            # ── ETL: Active_Play_Cumulative_s ──────────────────
            # Tiempo real de combate cronometrado (WKF Karate: 3 min netos).
            # Desde fight_start hasta f_start de esta técnica, restando
            # SOLO los Referee Stops del MISMO atleta que ya TERMINARON
            # antes de f_start. Cada atleta tiene su propio contador de pausas.
            if self._fight_start is not None and self._fight_start > 0 and fps > 0:
                elapsed_from_start = (ann.f_start - self._fight_start) / fps
                # Seleccionar los RS del mismo atleta que esta anotación
                athlete_stops = aka_stops if ann.athlete == "AKA" else ao_stops
                stopped_before = sum(
                    rs.duration_s
                    for rs in athlete_stops
                    if rs.f_end < ann.f_start
                )
                active_play_cumulative = max(0.0, elapsed_from_start - stopped_before)
            else:
                active_play_cumulative = 0.0
            # ── PARCHE 2: Blindaje Matemático del Tiempo (Monotonía) ──
            # Garantizar que APC nunca retroceda respecto a la fila anterior.
            final_apc = max(active_play_cumulative, prev_apc)
            row["Active_Play_Cumulative_s"] = round(final_apc, 1)
            prev_apc = final_apc

            # ── REGLA 2: Cálculo Dinámico de Minuto (Phase) ────
            # Calcular el minuto real a partir del tiempo activo acumulado
            # (Active_Play_Cumulative_s), que excluye los Referee Stops.
            # En Karate WKF el combate dura 3 min de tiempo activo cronometrado.
            active_time_s = row.get("Active_Play_Cumulative_s", 0.0)
            # La del reglamento del deporte (decisión 0007): en el karate,
            # Minute_N y Atoshibaraku con los mismos 180 s; en los demás,
            # sus asaltos.
            row["Phase"] = self._fase(active_time_s)

            rows.append(row)

        # ── FASE 3: Collect dynamic Sport_* columns from all rows ────────
        # Scan all rows to discover Sport_* columns added by to_csv_row()
        dynamic_columns = self._collect_dynamic_columns(rows)
        
        # Build final column list: base columns + dynamic Sport_* columns
        final_columns = self.ANNOTATION_COLUMNS + dynamic_columns
        nombres = self._nombres_de_columna()
        if nombres:
            final_columns = [nombres.get(c, c) for c in final_columns]
            rows = [{nombres.get(k, k): v for k, v in r.items()} for r in rows]
            # Y cada competidor con su nombre en el deporte, no el código.
            from karlos_core import catalogo
            nombre_de = {c.codigo: c.etiqueta for c in catalogo.paquete(self._sport_id).competidores}
            for r in rows:
                r["Athlete"] = nombre_de.get(r.get("Athlete", ""), r.get("Athlete", ""))

        # Write CSV with extended column set
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=final_columns)
            writer.writeheader()
            for row in rows:
                # Fill missing Sport_* columns with empty strings for symmetry
                for col in dynamic_columns:
                    if col not in row:
                        row[col] = ""
                writer.writerow(row)

        return str(output_path)

    def _compute_sequence_ids(self) -> list[str]:
        """Compute temporal sequence IDs for all records.

        Algorithm:
            Iterate over records sorted by f_start (chronologically).
            If the time difference (ms) between current and previous
            annotation by the SAME athlete is ≤ SEQUENCE_WINDOW_MS,
            they belong to the same sequence. Otherwise, start a new
            sequence.

        Returns:
            List of sequence_id strings (e.g. "SEQ_001") parallel to self.records.
        """
        if not self.records:
            return []

        # Sort by f_start to ensure chronological order
        sorted_indices = sorted(
            range(len(self.records)),
            key=lambda i: self.records[i].f_start,
        )

        sequence_ids: list[str] = [""] * len(self.records)
        seq_counter = 0

        for idx_in_sorted, i in enumerate(sorted_indices):
            if idx_in_sorted == 0:
                # First annotation always starts a new sequence
                seq_counter += 1
                sequence_ids[i] = f"SEQ_{seq_counter:03d}"
                continue

            prev_i = sorted_indices[idx_in_sorted - 1]
            curr = self.records[i]
            prev = self.records[prev_i]

            # Calculate time difference in milliseconds
            time_diff_ms = (curr.f_start - prev.f_start) / (curr.fight_dur_s or 1.0) * 1000
            # More robust: use fps from duration_s and f_start/f_end
            # Since we don't have fps directly, use f_start difference
            # and estimate time from duration_s / (f_end - f_start)
            if curr.f_end > curr.f_start and prev.f_end > prev.f_start:
                curr_fps = (curr.f_end - curr.f_start) / curr.duration_s if curr.duration_s > 0 else 30.0
                prev_fps = (prev.f_end - prev.f_start) / prev.duration_s if prev.duration_s > 0 else 30.0
                fps = (curr_fps + prev_fps) / 2  # average fps
            else:
                fps = 30.0  # fallback

            time_diff_ms = (curr.f_start - prev.f_start) / fps * 1000

            same_athlete = curr.athlete == prev.athlete
            within_window = time_diff_ms <= self.SEQUENCE_WINDOW_MS

            if same_athlete and within_window:
                # Same sequence as previous
                sequence_ids[i] = sequence_ids[prev_i]
            else:
                # New sequence
                seq_counter += 1
                sequence_ids[i] = f"SEQ_{seq_counter:03d}"

        return sequence_ids

    # ------------------------------------------------------------------
    # Sheet writers
    # ------------------------------------------------------------------

    def _write_bout_info_sheet(self, ws) -> None:
        """Populate the 'Bout Info' sheet.

        Sections:
            1. Bout metadata (Field | Value)
            2. Separator row
            3. Fight segment overview (frames + duration)
            4. Total active / stopped time

        Args:
            ws: openpyxl Worksheet for bout info.
        """
        # Column widths
        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 40

        # ---- Header row ----
        for col_idx, header in enumerate(["Field", "Value"], start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.alignment = _HEADER_ALIGN
            cell.border = _THIN_BORDER

        row = 2

        # ---- Section 0: con qué se hizo (decisión 0008) ----
        # El modo, el programa y el esquema de los datos, lo primero: un
        # Excel de tiempo-movimiento y uno técnico-táctico del mismo combate
        # no se distinguían más que por las hojas que traían.
        from karlos_core.formato import ESQUEMA, analisis_de
        from karlos_core.identidad import programa
        for label, value in (("Analysis mode", analisis_de(self._bout_info)),
                             ("Program", programa()), ("Data schema", ESQUEMA)):
            ws.cell(row=row, column=1, value=label).font = _META_LABEL_FONT
            ws.cell(row=row, column=2, value=value).font = _META_VALUE_FONT
            for col in (1, 2):
                ws.cell(row=row, column=col).alignment = _CELL_ALIGN
                ws.cell(row=row, column=col).border = _THIN_BORDER
            row += 1

        # ---- Section 1: Bout metadata ----
        first = self.records[0] if self.records else None
        for key, label in self._BOUT_META_KEYS:
            # Prefer _bout_info from popup; fallback to annotation record
            value = self._bout_info.get(key, "")
            if not value and first is not None:
                value = getattr(first, key, "")

            label_cell = ws.cell(row=row, column=1, value=label)
            label_cell.font = _META_LABEL_FONT
            label_cell.alignment = _CELL_ALIGN
            label_cell.border = _THIN_BORDER

            val_cell = ws.cell(row=row, column=2, value=value)
            val_cell.font = _META_VALUE_FONT
            val_cell.alignment = _CELL_ALIGN
            val_cell.border = _THIN_BORDER

            row += 1

        # ---- Export Build info (traceability) ----
        build_label = ws.cell(row=row, column=1, value="Export Build")
        build_label.font = _META_LABEL_FONT
        build_label.alignment = _CELL_ALIGN
        build_label.border = _THIN_BORDER
        build_val = ws.cell(row=row, column=2, value=f"commit:{BUILD_COMMIT} | {BUILD_TIMESTAMP}")
        build_val.font = _META_VALUE_FONT
        build_val.alignment = _CELL_ALIGN
        build_val.border = _THIN_BORDER
        row += 1

        # ---- Separator ----
        row += 1  # blank row
        section_cell = ws.cell(row=row, column=1, value="Fight Overview")
        section_cell.font = _SECTION_FONT
        section_cell.alignment = _CELL_ALIGN
        section_cell.border = _SEPARATOR_BORDER
        ws.cell(row=row, column=2).border = _SEPARATOR_BORDER
        row += 1

        # ---- Section 2: Fight segment overview (from VideoManager, via set_fight_info) ----
        overview_rows = [
            ("Fight Start Frame", _fmt_int(self._fight_start)),
            ("Fight End Frame", _fmt_int(self._fight_end)),
            ("Fight Duration (s)", _fmt_float(self._fight_duration)),
        ]
        for label, value in overview_rows:
            label_cell = ws.cell(row=row, column=1, value=label)
            label_cell.font = _META_LABEL_FONT
            label_cell.alignment = _CELL_ALIGN
            label_cell.border = _THIN_BORDER

            val_cell = ws.cell(row=row, column=2, value=value)
            val_cell.font = _META_VALUE_FONT
            val_cell.alignment = _CELL_ALIGN
            val_cell.border = _THIN_BORDER

            row += 1

        # ---- Section 3: Time totals ----
        # BUG FIX v6.4: Use _merged_stopped_duration() to avoid double-counting
        # referee stops that are tagged by both athletes for the same pause.
        fps = 30.0
        if (self._fight_start is not None and self._fight_end is not None
                and self._fight_duration and self._fight_duration > 0):
            total_frames = self._fight_end - self._fight_start
            if total_frames > 0:
                fps = total_frames / self._fight_duration

        total_stopped = self._merged_stopped_duration(self.records, fps)
        fight_dur = self._fight_duration or 0.0
        total_active = max(0.0, fight_dur - total_stopped)

        # Tiempos INDIVIDUALES por atleta (cada uno usa solo sus propias pausas)
        aka_stops = [r for r in self.records if r.category == "REFEREE STOP" and r.athlete == "AKA"]
        ao_stops = [r for r in self.records if r.category == "REFEREE STOP" and r.athlete == "AO"]
        aka_stopped_time = sum(r.duration_s for r in aka_stops)
        ao_stopped_time = sum(r.duration_s for r in ao_stops)
        aka_active_time = max(0.0, fight_dur - aka_stopped_time)
        ao_active_time = max(0.0, fight_dur - ao_stopped_time)

        row += 1  # blank row
        section_cell2 = ws.cell(row=row, column=1, value="Time Summary")
        section_cell2.font = _SECTION_FONT
        section_cell2.alignment = _CELL_ALIGN
        section_cell2.border = _SEPARATOR_BORDER
        ws.cell(row=row, column=2).border = _SEPARATOR_BORDER
        row += 1

        # Cada competidor con su nombre en el deporte (AKA y AO en el karate).
        from karlos_core import catalogo
        try:
            a_rotulo, b_rotulo = (c.etiqueta for c in catalogo.paquete(self._sport_id).competidores)
        except KeyError:
            a_rotulo, b_rotulo = "AKA", "AO"
        time_rows = [
            ("Total Active Time (s)", _fmt_float(total_active)),
            ("Total Stopped Time (s)", _fmt_float(total_stopped)),
            ("", ""),
            (f"{a_rotulo} Active Time (s)", _fmt_float(aka_active_time)),
            (f"{a_rotulo} Stopped Time (s)", _fmt_float(aka_stopped_time)),
            (f"{b_rotulo} Active Time (s)", _fmt_float(ao_active_time)),
            (f"{b_rotulo} Stopped Time (s)", _fmt_float(ao_stopped_time)),
        ]
        for label, value in time_rows:
            label_cell = ws.cell(row=row, column=1, value=label)
            label_cell.font = _META_LABEL_FONT
            label_cell.alignment = _CELL_ALIGN
            label_cell.border = _THIN_BORDER

            val_cell = ws.cell(row=row, column=2, value=value)
            val_cell.font = _META_VALUE_FONT
            val_cell.alignment = _CELL_ALIGN
            val_cell.border = _THIN_BORDER

            row += 1

    def _write_annotations_sheet(self, ws) -> list[dict]:
        """Populate the 'Annotations' sheet with temporal annotation data.

        Bout metadata is stored separately in the "Bout Info" sheet.
        This sheet contains only the clean annotation dataset.

        Las filas las da ``filas_de_anotaciones`` (las mismas que se
        escribían aquí) y se devuelven. La hoja empieza en la fila 2 y la 1
        queda vacía, como en la 1.0: así lo fijan las salidas de referencia.

        Args:
            ws: openpyxl Worksheet for annotation rows.
        """
        filas = self.filas_de_anotaciones()
        for row_idx, row in enumerate(filas, start=2):
            for col_idx, col_name in enumerate(self.ANNOTATION_COLUMNS, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=row.get(col_name, ""))
                cell.alignment = _CELL_ALIGN
                cell.border = _THIN_BORDER
        return filas

    def hojas_del_combate(self, wb, nombre: str) -> list[dict]:
        """Las hojas de este combate en un libro con varios («Exportar
        Dataset» del hub): sus datos («… - Info») y sus acciones («… -
        Data», con la fila de títulos). Devuelve las filas de las acciones.

        Excel no abre un libro con un nombre de hoja de más de 31
        caracteres, con ``[]:*?/\\`` o repetido: se recorta, se limpia y se
        numera."""
        self._write_bout_info_sheet(wb.create_sheet(_titulo_de_hoja(wb, nombre, " - Info")))
        ws = wb.create_sheet(_titulo_de_hoja(wb, nombre, " - Data"))
        filas = self._write_annotations_sheet(ws)
        for col_idx, col_name in enumerate(self.ANNOTATION_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = Font(bold=True)
            cell.border = _THIN_BORDER
        return filas

    def filas_de_anotaciones(self) -> list[dict]:
        """Las acciones como filas de la hoja «Annotations»: una por acción,
        en orden, con las columnas de ``ANNOTATION_COLUMNS`` (y las Sport_*
        de cada deporte). Ordena ``self.records`` por su inicio, como
        siempre.
        """
        filas: list[dict] = []
        from karlos_core import catalogo
        try:
            nombre_de = {c.codigo: c.etiqueta for c in catalogo.paquete(self._sport_id).competidores}
        except KeyError:
            nombre_de = {}

        # ── REGLA 1: Ordenación Cronológica Absoluta ──────────────────
        # Mezclar AKA y AO en un flujo temporal continuo para que el APC
        # sea monótono estrictamente creciente.
        self.records.sort(key=lambda x: x.f_start)

        # Compute sequence IDs for XLSX export too
        sequence_ids = self._compute_sequence_ids()

        # ── Calcular FPS desde fight_start/fight_end ──────────────────
        fps = 30.0
        if (self._fight_start is not None and self._fight_end is not None
                and self._fight_duration):
            total_frames = self._fight_end - self._fight_start
            if total_frames > 0 and self._fight_duration > 0:
                fps = total_frames / self._fight_duration

        # ── Pre-calcular: Referee Stops INDIVIDUALES por atleta (XLSX) ──
        aka_stops = sorted(
            [r for r in self.records if r.category == "REFEREE STOP" and r.athlete == "AKA"],
            key=lambda r: r.f_start,
        )
        ao_stops = sorted(
            [r for r in self.records if r.category == "REFEREE STOP" and r.athlete == "AO"],
            key=lambda r: r.f_start,
        )

        # ── Calcular tiempo activo total para detectar Atoshibaraku ──
        total_stopped = sum(r.duration_s for r in aka_stops) + sum(r.duration_s for r in ao_stops)
        if self._fight_start is not None and self._fight_end is not None:
            total_active_play = max(
                0.0, (self._fight_end - self._fight_start) / fps - total_stopped
            )
        else:
            total_active_play = 0.0

        # ── Fase 1: Extracción Segura de Metadatos del Combate ──────────
        # Valores por defecto (fallback) para evitar celdas vacías.
        bout_event = self._bout_info.get("competition_name", "") or ""
        bout_phase = self._bout_info.get("event_phase", "") or ""
        weight_category = self._bout_info.get("weight_category", "") or ""
        aka_name = self._bout_info.get("athlete_a_name", "") or ""
        ao_name = self._bout_info.get("athlete_b_name", "") or ""

        # Data rows — denormalized flat rows with bout metadata injected
        # into every annotation row for DS/ML readiness.

        # ── PARCHE 2: Inicializar prev_apc para blindaje de monotonía ──
        prev_apc = 0.0

        for i in range(len(self.records)):
            ann = self.records[i]
            row = ann.to_csv_row(i + 1, sequence_ids[i])

            # ── Fase 3: Inyección de Metadatos al Principio de cada Fila ──
            row["Export_Build"] = f"commit:{BUILD_COMMIT} | {BUILD_TIMESTAMP}"
            row["Bout_Event"] = bout_event
            row["Bout_Phase"] = bout_phase
            row["Weight_Category"] = weight_category
            row["AKA_Name"] = aka_name
            row["AO_Name"] = ao_name

            # ── REGLA 3: Purificación Biomecánica de Técnicas ────
            # Stripear niveles quemados (Jodan/Chudan/Gedan) para
            # evitar contaminación categórica — el nivel ya existe
            # en la columna independiente "Level".
            tech_raw = ann.technique
            for suffix in (" Jodan", " Chudan", " Gedan"):
                tech_raw = tech_raw.replace(suffix, "")

            # ── REGLA 4: Limpieza de Pausas de Árbitro ──────────
            # Extraer el motivo real tras " - " (Doctor, Coach, End of bout, etc.)
            if ann.category == "REFEREE STOP":
                parts = tech_raw.split(" - ")
                tech_raw = parts[-1].strip() if len(parts) > 1 else tech_raw.strip()
            row["Technique"] = tech_raw.strip()

            # ── PARCHE 1: Limpieza Absoluta del Árbitro ─────────
            # Forzar "Referee" en la técnica si la categoría es REFEREE STOP,
            # para eliminar cualquier nombre residual de golpe.
            if row.get("Category") == "REFEREE STOP":
                row["Technique"] = "Referee"

            # ── REGLA 6: Inyección de la Llave Relacional (bout_id) ──
            if not row.get("bout_id"):
                aka = self._bout_info.get("athlete_a_name", "Unknown")
                ao = self._bout_info.get("athlete_b_name", "Unknown")
                date = datetime.now().strftime("%Y%m%d")
                row["bout_id"] = f"BOUT_{date}_{aka}_vs_{ao}"

            # ── REGLA 5: Estandarización de Valores Nulos en Score ──
            if row.get("Score") in ("NONE", None, ""):
                row["Score"] = ""

            # ── ETL: Calcular Match_Time_s desde fight_start ────
            # Tiempo transcurrido desde fight_start (o primer frame de
            # anotación si fight_start es 0/None) hasta f_start
            # de esta técnica, dividido por FPS.
            if fps > 0:
                base_frame = self._fight_start if (self._fight_start is not None and self._fight_start > 0) else self.records[0].f_start
                row["Match_Time_s"] = round((ann.f_start - base_frame) / fps, 1)
            else:
                row["Match_Time_s"] = 0.0

            # ── ETL: Active_Play_Cumulative_s ──────────────────
            # Tiempo real de combate cronometrado (WKF Karate: 3 min netos).
            # Desde fight_start hasta f_start de esta técnica, restando
            # SOLO los Referee Stops del MISMO atleta que ya TERMINARON
            # antes de f_start. Cada atleta tiene su propio contador de pausas.
            if self._fight_start is not None and self._fight_start > 0 and fps > 0:
                elapsed_from_start = (ann.f_start - self._fight_start) / fps
                athlete_stops = aka_stops if ann.athlete == "AKA" else ao_stops
                stopped_before = sum(
                    rs.duration_s
                    for rs in athlete_stops
                    if rs.f_end < ann.f_start
                )
                active_play_cumulative = max(0.0, elapsed_from_start - stopped_before)
            else:
                active_play_cumulative = 0.0
            # ── PARCHE 2: Blindaje Matemático del Tiempo (Monotonía) ──
            final_apc = max(active_play_cumulative, prev_apc)
            row["Active_Play_Cumulative_s"] = round(final_apc, 1)
            prev_apc = final_apc

            # ── REGLA 2: Cálculo Dinámico de Minuto (Phase) ────
            active_time_s = row.get("Active_Play_Cumulative_s", 0.0)
            # La del reglamento del deporte (decisión 0007): en el karate,
            # Minute_N y Atoshibaraku con los mismos 180 s; en los demás,
            # sus asaltos.
            row["Phase"] = self._fase(active_time_s)

            # Cada competidor con su nombre en el deporte (en el karate, el
            # mismo código): la sesión guarda AKA/AO, el fichero no.
            row["Athlete"] = nombre_de.get(row.get("Athlete", ""), row.get("Athlete", ""))
            filas.append(row)
        return filas

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def record_count(self) -> int:
        """Number of records available for export."""
        return len(self.records)

    # ------------------------------------------------------------------
    # Athlete Comparison Sheet
    # ------------------------------------------------------------------

    def _write_comparison_sheet(self, ws) -> None:
        """Populate the 'Athlete Comparison' sheet with AKA vs AO metrics.

        Args:
            ws: openpyxl Worksheet for comparison data.
        """
        # Column widths
        ws.column_dimensions["A"].width = 32
        ws.column_dimensions["B"].width = 24
        ws.column_dimensions["C"].width = 24

        # Header
        from karlos_core import catalogo
        for col_idx, header in enumerate(["Metric", catalogo.etiqueta("AKA"), catalogo.etiqueta("AO")],
                                         start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.alignment = _HEADER_ALIGN
            cell.border = _THIN_BORDER

        # Split records by athlete
        aka_records = [r for r in self.records if r.athlete == "AKA"]
        ao_records = [r for r in self.records if r.athlete == "AO"]

        # Count helper
        def _score_count(records, score):
            return sum(1 for r in records if r.score == score)

        row = 2

        # Total techniques
        self._write_comparison_row(ws, row, "Total Techniques",
                                   len(aka_records), len(ao_records))
        row += 1

        # Techniques per minute (using fight duration)
        fight_minutes = (self._fight_duration or 0.0) / 60.0
        if fight_minutes > 0:
            aka_rate = round(len(aka_records) / fight_minutes, 1)
            ao_rate = round(len(ao_records) / fight_minutes, 1)
        else:
            aka_rate = 0.0
            ao_rate = 0.0
        self._write_comparison_row(ws, row, "Techniques / min",
                                   aka_rate, ao_rate)
        row += 1

        # Scores — sport-dependent
        if self._sport_id == "kickboxing":
            from karlos_core import catalogo
            for p in catalogo.paquete(self._sport_id).reglamento.puntuaciones:
                self._write_comparison_row(ws, row, p.nombre,
                                           _score_count(aka_records, p.codigo),
                                           _score_count(ao_records, p.codigo))
                row += 1
            # Scoring Efficiency (% scored of total ATTACKS only)
            aka_attacks_only = [r for r in aka_records if r.category == "ATTACK"]
            ao_attacks_only = [r for r in ao_records if r.category == "ATTACK"]
            aka_total_att = max(len(aka_attacks_only), 1)
            ao_total_att = max(len(ao_attacks_only), 1)
            aka_eff = round(sum(1 for r in aka_attacks_only if _puntua(self._sport_id, r.score))
                            / aka_total_att * 100, 1)
            ao_eff = round(sum(1 for r in ao_attacks_only if _puntua(self._sport_id, r.score))
                           / ao_total_att * 100, 1)
            self._write_comparison_row(ws, row, "Scoring Efficiency (%)",
                                       f"{aka_eff}%", f"{ao_eff}%", as_str=True)
            row += 1
        elif self._sport_id == "karate":
            for score_label, score_code in [("IPPON", "IPPON"), ("WAZA", "WAZA"),
                                              ("YUKO", "YUKO")]:
                self._write_comparison_row(ws, row, score_label,
                                           _score_count(aka_records, score_code),
                                           _score_count(ao_records, score_code))
                row += 1
        else:
            # Las puntuaciones del reglamento del deporte, con su nombre: las
            # que puntúan o, si solo puntúa una, todas (decisión 0007).
            from karlos_core import catalogo
            reparto = catalogo.paquete(self._sport_id).reglamento.puntuaciones
            filas = [p for p in reparto if p.puntos > 0]
            for p in (filas if len(filas) > 1 else reparto):
                self._write_comparison_row(ws, row, p.nombre,
                                           _score_count(aka_records, p.codigo),
                                           _score_count(ao_records, p.codigo))
                row += 1

        # Referee Stops
        aka_stops = sum(1 for r in aka_records if r.category == "REFEREE STOP")
        ao_stops = sum(1 for r in ao_records if r.category == "REFEREE STOP")
        self._write_comparison_row(ws, row, "Referee Stops",
                                   aka_stops, ao_stops)
        row += 1

        # Total Stopped Time
        aka_stopped = round(sum(r.duration_s for r in aka_records
                                if r.category == "REFEREE STOP"), 2)
        ao_stopped = round(sum(r.duration_s for r in ao_records
                                if r.category == "REFEREE STOP"), 2)
        self._write_comparison_row(ws, row, "Total Stopped Time (s)",
                                   aka_stopped, ao_stopped)
        row += 1

        # Fight Duration (from set_fight_info, shared for both athletes)
        fight_dur = round(self._fight_duration, 2) if self._fight_duration else 0.0
        self._write_comparison_row(ws, row, "Fight Duration (s)",
                                   fight_dur, fight_dur)
        row += 1

        # Active Time per athlete (fight_duration - individual stopped time)
        fight_dur = self._fight_duration or 0.0
        aka_active = round(fight_dur - aka_stopped, 2)
        ao_active = round(fight_dur - ao_stopped, 2)
        self._write_comparison_row(ws, row, "Active Time (s)",
                                   aka_active, ao_active)
        row += 1

        # Stopped Time per athlete (individual referee stops)
        self._write_comparison_row(ws, row, "Stopped Time (s)",
                                   aka_stopped, ao_stopped)
        row += 1

        # Total Fouls (all sports)
        # In Kickboxing, fouls are stored as r.category == "FOUL".
        # In Karate, fouls appear as r.score == "FOUL" on ATTACK rows.
        # NOTE: WKF progressive penalties (Category="PENALTY") are NOT
        # counted here — they are tracked separately below as
        # "Cat.1 Fouls (highest)" and "Cat.2 Fouls (highest)".
        # This keeps backward compatibility with existing Total Fouls
        # counts from the old system.
        aka_fouls = sum(
            1 for r in aka_records
            if r.category == "FOUL" or r.score == "FOUL"
        )
        ao_fouls = sum(
            1 for r in ao_records
            if r.category == "FOUL" or r.score == "FOUL"
        )
        self._write_comparison_row(ws, row, "Total Fouls",
                                   aka_fouls, ao_fouls)
        row += 1

        # WKF 2026 Unified Fouls (Category="PENALTY")
        # WKF unified Category 1/2 penalties into a single CHUI ladder,
        # effective 1.1.2026 (Rules Version 2026.01, §10.2-10.3).
        # A single counter per athlete tracks all infractions regardless
        # of type (Contact, Target, Illegal Tech, Procedure).
        # These are NOT summed into "Total Fouls" above — they are a
        # separate metric tracking the WKF 2026 progressive penalty system.
        # Decision: keep as separate metric to avoid conflating old-style
        # FOUL annotations with the new WKF unified penalty system.
        aka_penalties = [r for r in aka_records if r.category == "PENALTY"]
        ao_penalties = [r for r in ao_records if r.category == "PENALTY"]

        aka_highest = max(
            (r.technique for r in aka_penalties), default="—"
        )
        ao_highest = max(
            (r.technique for r in ao_penalties), default="—"
        )
        self._write_comparison_row(
            ws, row, "Fouls (highest penalty reached)",
            aka_highest, ao_highest, as_str=True
        )
        row += 1

        # Most used technique (excludes PENALTY category to avoid
        # showing "Chukoku"/"Keikoku" etc. as a "technique")
        aka_top = self._most_used(
            [r for r in aka_records if r.category != "PENALTY"]
        )
        ao_top = self._most_used(
            [r for r in ao_records if r.category != "PENALTY"]
        )
        self._write_comparison_row(ws, row, "Most Used Technique",
                                   aka_top, ao_top, as_str=True)

    @staticmethod
    def _write_comparison_row(ws, row, label, aka_val, ao_val, as_str=False):
        """Write a single comparison row."""
        label_cell = ws.cell(row=row, column=1, value=label)
        label_cell.font = _META_LABEL_FONT
        label_cell.alignment = _CELL_ALIGN
        label_cell.border = _THIN_BORDER

        aka_cell = ws.cell(row=row, column=2, value=str(aka_val) if as_str else aka_val)
        aka_cell.font = _META_VALUE_FONT
        aka_cell.alignment = _CELL_ALIGN
        aka_cell.border = _THIN_BORDER

        ao_cell = ws.cell(row=row, column=3, value=str(ao_val) if as_str else ao_val)
        ao_cell.font = _META_VALUE_FONT
        ao_cell.alignment = _CELL_ALIGN
        ao_cell.border = _THIN_BORDER

    @staticmethod
    def _most_used(records):
        """Find the most frequently used technique in a list of records."""
        if not records:
            return ""
        from collections import Counter
        counter = Counter(r.technique for r in records)
        top = counter.most_common(1)
        return top[0][0] if top else ""

    # ------------------------------------------------------------------
    # Technical-Tactical Analysis Sheet (Kickboxing only)
    # ------------------------------------------------------------------

    def _write_technical_tactical_sheet(self, ws) -> None:
        """Populate the 'Technical-Tactical Analysis' sheet with professional kickboxing metrics.

        This sheet provides scientific-level analysis for kickboxing:
        - Target zone distribution (the sport's zones: Head, Torso, Legs)
        - Stance analysis (Lead vs Rear)
        - Technical efficiency metrics
        - Temporal analysis (attacks per round, fatigue indicators)

        Args:
            ws: openpyxl Worksheet for technical-tactical analysis.
        """
        from collections import Counter, defaultdict

        # Column widths
        ws.column_dimensions["A"].width = 35
        ws.column_dimensions["B"].width = 20
        ws.column_dimensions["C"].width = 20

        # Header
        from karlos_core import catalogo
        for col_idx, header in enumerate(["Metric", catalogo.etiqueta("AKA"), catalogo.etiqueta("AO")],
                                         start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = _HEADER_FONT
            cell.fill = _HEADER_FILL
            cell.alignment = _HEADER_ALIGN
            cell.border = _THIN_BORDER

        # Split records by athlete (only ATTACK category for offensive metrics)
        aka_attacks = [r for r in self.records if r.athlete == "AKA" and r.category == "ATTACK"]
        ao_attacks = [r for r in self.records if r.athlete == "AO" and r.category == "ATTACK"]

        row = 2

        # ══════════════════════════════════════════════════════════════
        # SECTION A: Target Zone Distribution
        # ══════════════════════════════════════════════════════════════
        self._write_section_header(ws, row, "A. TARGET ZONE DISTRIBUTION")
        row += 1

        # Count by target zone: the level, or the old «Target» field.
        zonas = _zonas(self._sport_id)
        aka_targets = Counter(r.target or r.level for r in aka_attacks if r.target or r.level)
        ao_targets = Counter(r.target or r.level for r in ao_attacks if r.target or r.level)
        aka_total_targeted = sum(aka_targets.values())
        ao_total_targeted = sum(ao_targets.values())

        for target_zone in zonas:
            aka_count = aka_targets.get(target_zone, 0)
            ao_count = ao_targets.get(target_zone, 0)
            aka_pct = (aka_count / aka_total_targeted * 100) if aka_total_targeted > 0 else 0.0
            ao_pct = (ao_count / ao_total_targeted * 100) if ao_total_targeted > 0 else 0.0
            self._write_comparison_row(ws, row, f"{target_zone} Attacks (%)",
                                       f"{aka_pct:.1f}%", f"{ao_pct:.1f}%", as_str=True)
            row += 1

        # Scored strikes by zone
        aka_connected_by_zone = Counter(r.target or r.level for r in aka_attacks
                                        if (r.target or r.level) and _puntua(self._sport_id, r.score))
        ao_connected_by_zone = Counter(r.target or r.level for r in ao_attacks
                                       if (r.target or r.level) and _puntua(self._sport_id, r.score))

        row += 1
        self._write_section_header(ws, row, "Scored Strikes by Zone")
        row += 1

        for target_zone in zonas:
            aka_conn = aka_connected_by_zone.get(target_zone, 0)
            ao_conn = ao_connected_by_zone.get(target_zone, 0)
            self._write_comparison_row(ws, row, f"{target_zone} Scored",
                                       aka_conn, ao_conn)
            row += 1

        # ══════════════════════════════════════════════════════════════
        # SECTION B: Stance Analysis
        # ══════════════════════════════════════════════════════════════
        row += 1
        self._write_section_header(ws, row, "B. STANCE ANALYSIS")
        row += 1

        aka_stances = Counter(r.stance for r in aka_attacks if r.stance)
        ao_stances = Counter(r.stance for r in ao_attacks if r.stance)
        aka_total_stance = sum(aka_stances.values())
        ao_total_stance = sum(ao_stances.values())

        for stance_type in ["Lead", "Rear"]:
            aka_count = aka_stances.get(stance_type, 0)
            ao_count = ao_stances.get(stance_type, 0)
            aka_pct = (aka_count / aka_total_stance * 100) if aka_total_stance > 0 else 0.0
            ao_pct = (ao_count / ao_total_stance * 100) if ao_total_stance > 0 else 0.0
            self._write_comparison_row(ws, row, f"{stance_type} Stance (%)",
                                       f"{aka_pct:.1f}%", f"{ao_pct:.1f}%", as_str=True)
            row += 1

        # Effectiveness by stance
        row += 1
        self._write_section_header(ws, row, "Effectiveness by Stance (% Scored)")
        row += 1

        for stance_type in ["Lead", "Rear"]:
            aka_stance_attacks = [r for r in aka_attacks if r.stance == stance_type]
            ao_stance_attacks = [r for r in ao_attacks if r.stance == stance_type]
            aka_stance_connected = sum(1 for r in aka_stance_attacks if _puntua(self._sport_id, r.score))
            ao_stance_connected = sum(1 for r in ao_stance_attacks if _puntua(self._sport_id, r.score))
            aka_eff = (aka_stance_connected / len(aka_stance_attacks) * 100) if aka_stance_attacks else 0.0
            ao_eff = (ao_stance_connected / len(ao_stance_attacks) * 100) if ao_stance_attacks else 0.0
            self._write_comparison_row(ws, row, f"{stance_type} Effectiveness",
                                       f"{aka_eff:.1f}%", f"{ao_eff:.1f}%", as_str=True)
            row += 1

        # ══════════════════════════════════════════════════════════════
        # SECTION C: Technical Efficiency
        # ══════════════════════════════════════════════════════════════
        row += 1
        self._write_section_header(ws, row, "C. TECHNICAL EFFICIENCY")
        row += 1

        # Most effective technique (highest connection rate)
        aka_tech_stats = self._calculate_technique_efficiency(aka_attacks, self._sport_id)
        ao_tech_stats = self._calculate_technique_efficiency(ao_attacks, self._sport_id)

        aka_best_tech = max(aka_tech_stats.items(), key=lambda x: x[1]["efficiency"]) if aka_tech_stats else ("—", {"efficiency": 0.0})
        ao_best_tech = max(ao_tech_stats.items(), key=lambda x: x[1]["efficiency"]) if ao_tech_stats else ("—", {"efficiency": 0.0})

        self._write_comparison_row(ws, row, "Most Effective Technique",
                                   f"{aka_best_tech[0]} ({aka_best_tech[1]['efficiency']:.1f}%)",
                                   f"{ao_best_tech[0]} ({ao_best_tech[1]['efficiency']:.1f}%)", as_str=True)
        row += 1

        # Attack/Defense ratio
        aka_def = sum(1 for r in self.records if r.athlete == "AKA" and r.category == "DEFENSE")
        ao_def = sum(1 for r in self.records if r.athlete == "AO" and r.category == "DEFENSE")
        aka_ratio = len(aka_attacks) / max(aka_def, 1)
        ao_ratio = len(ao_attacks) / max(ao_def, 1)
        self._write_comparison_row(ws, row, "Attack/Defense Ratio",
                                   f"{aka_ratio:.2f}", f"{ao_ratio:.2f}", as_str=True)
        row += 1

        # Punches vs Kicks distribution
        aka_punches = sum(1 for r in aka_attacks if r.subcategory == "PUNCHES")
        aka_kicks = sum(1 for r in aka_attacks if r.subcategory == "KICKS")
        ao_punches = sum(1 for r in ao_attacks if r.subcategory == "PUNCHES")
        ao_kicks = sum(1 for r in ao_attacks if r.subcategory == "KICKS")

        aka_punch_pct = (aka_punches / len(aka_attacks) * 100) if aka_attacks else 0.0
        ao_punch_pct = (ao_punches / len(ao_attacks) * 100) if ao_attacks else 0.0
        self._write_comparison_row(ws, row, "Punches (%)",
                                   f"{aka_punch_pct:.1f}%", f"{ao_punch_pct:.1f}%", as_str=True)
        row += 1

        aka_kick_pct = (aka_kicks / len(aka_attacks) * 100) if aka_attacks else 0.0
        ao_kick_pct = (ao_kicks / len(ao_attacks) * 100) if ao_attacks else 0.0
        self._write_comparison_row(ws, row, "Kicks (%)",
                                   f"{aka_kick_pct:.1f}%", f"{ao_kick_pct:.1f}%", as_str=True)
        row += 1

        # ══════════════════════════════════════════════════════════════
        # SECTION D: Temporal Analysis
        # ══════════════════════════════════════════════════════════════
        row += 1
        self._write_section_header(ws, row, "D. TEMPORAL ANALYSIS")
        row += 1

        # Attacks per round
        aka_by_round = defaultdict(int)
        ao_by_round = defaultdict(int)
        for r in aka_attacks:
            aka_by_round[r.round] += 1
        for r in ao_attacks:
            ao_by_round[r.round] += 1

        max_round = max(max(aka_by_round.keys(), default=1), max(ao_by_round.keys(), default=1))
        for round_num in range(1, max_round + 1):
            self._write_comparison_row(ws, row, f"Round {round_num} Attacks",
                                       aka_by_round.get(round_num, 0),
                                       ao_by_round.get(round_num, 0))
            row += 1

        # Fatigue indicator (Round 1 vs Last Round)
        if max_round >= 2:
            aka_r1 = aka_by_round.get(1, 0)
            aka_rn = aka_by_round.get(max_round, 0)
            ao_r1 = ao_by_round.get(1, 0)
            ao_rn = ao_by_round.get(max_round, 0)
            aka_fatigue = ((aka_r1 - aka_rn) / aka_r1 * 100) if aka_r1 > 0 else 0.0
            ao_fatigue = ((ao_r1 - ao_rn) / ao_r1 * 100) if ao_r1 > 0 else 0.0
            row += 1
            self._write_comparison_row(ws, row, "Fatigue Index (% drop from R1)",
                                       f"{aka_fatigue:.1f}%", f"{ao_fatigue:.1f}%", as_str=True)
            row += 1

        # Average time between attacks
        fight_dur = self._fight_duration or 1.0
        aka_avg_interval = fight_dur / len(aka_attacks) if aka_attacks else 0.0
        ao_avg_interval = fight_dur / len(ao_attacks) if ao_attacks else 0.0
        self._write_comparison_row(ws, row, "Avg Time Between Attacks (s)",
                                   f"{aka_avg_interval:.2f}", f"{ao_avg_interval:.2f}", as_str=True)

    def _write_tecnico_sheet(self, ws) -> None:
        """La hoja «Technical-Tactical»: las acciones por competidor en cada
        dimensión; con duración solo en el análisis integrado."""
        from karlos_core import catalogo
        from karlos_core.informe_tecnico import hoja_excel
        hoja_excel(ws, self.records, self._analisis != "technical_tactical",
                   catalogo.paquete(self._sport_id).reglamento.puntos)

    def _write_time_motion_matrix(self, ws) -> None:
        """Las fases de cada atleta en su bloque, uno al lado del otro."""
        from karlos_core.tiempo_movimiento import asaltos_o_combate, hoja_matriz
        asaltos, fases, _hueco, _derivar = self._tiempo_movimiento
        asaltos = asaltos_o_combate(asaltos, getattr(self, "_fight_start", None),
                                    getattr(self, "_fight_end", None))
        hoja_matriz(ws, fases, asaltos, self._fps if getattr(self, "_fps", 0) else 30.0)

    def _write_time_motion_sheet(self, ws) -> None:
        """La hoja «Time-Motion»: por asalto, las fases marcadas con las
        teclas y las derivadas de las acciones, y su acuerdo.

        Con las definiciones del especialista de taekwondo (8-10-2026): fighting /
        non-fighting / stoppage, dos acciones a menos del hueco son el mismo
        ataque, la finta sola es non-fighting. Las derivadas miran las filas
        de los dos atletas: con uno solo anotado salen a medias, y se dice.
        """
        from karlos_core.tiempo_movimiento import asaltos_o_combate, hoja_excel

        asaltos, fases, hueco, derivar = self._tiempo_movimiento
        asaltos = asaltos_o_combate(asaltos, getattr(self, "_fight_start", None),
                                    getattr(self, "_fight_end", None))
        hoja_excel(ws, self.records, asaltos, fases,
                   self._fps if getattr(self, "_fps", 0) else 30.0, hueco, derivar)

    def _write_section_header(self, ws, row: int, title: str) -> None:
        """Write a section header spanning 3 columns."""
        cell = ws.cell(row=row, column=1, value=title)
        cell.font = _SECTION_FONT
        cell.alignment = _CELL_ALIGN
        cell.border = _SEPARATOR_BORDER
        ws.cell(row=row, column=2).border = _SEPARATOR_BORDER
        ws.cell(row=row, column=3).border = _SEPARATOR_BORDER

    @staticmethod
    def _calculate_technique_efficiency(attacks: list, sport_id: str = "kickboxing") -> dict:
        """Calculate efficiency (% scored, per the sport's rules) for each technique.

        Args:
            attacks: List of attack annotations.

        Returns:
            Dict mapping technique name to stats dict with 'total', 'connected', 'efficiency'.
        """
        from collections import defaultdict
        stats = defaultdict(lambda: {"total": 0, "connected": 0, "efficiency": 0.0})

        for attack in attacks:
            tech = attack.technique
            stats[tech]["total"] += 1
            if _puntua(sport_id, attack.score):
                stats[tech]["connected"] += 1

        # Calculate efficiency percentages
        for tech, data in stats.items():
            if data["total"] > 0:
                data["efficiency"] = (data["connected"] / data["total"]) * 100

        return dict(stats)

    @staticmethod
    def _collect_dynamic_columns(rows: list[dict]) -> list[str]:
        """Collect all Sport_* columns from annotation rows.

        **FASE 3 REFACTOR**: Scans all rows to discover dynamic Sport_* columns
        added by Annotation.to_csv_row() from sport_specific_data. This ensures
        the CSV/XLSX exports include all sport-specific fields without hardcoding.

        Args:
            rows: List of annotation row dictionaries.

        Returns:
            Sorted list of unique Sport_* column names found across all rows.
        """
        dynamic_cols = set()
        for row in rows:
            for key in row.keys():
                if key.startswith("Sport_"):
                    dynamic_cols.add(key)
        return sorted(dynamic_cols)


# ------------------------------------------------------------------
# Module-level formatting helpers
# ------------------------------------------------------------------

def _fmt_int(value: int | None) -> int | str:
    """Format an optional int for display."""
    return value if value is not None else ""


def _fmt_float(value: float | None) -> float | str:
    """Format an optional float to 2 decimals for display."""
    if value is None:
        return ""
    return round(value, 2)

def _titulo_de_hoja(wb, base: str, sufijo: str) -> str:
    """Un nombre de hoja que Excel acepta: hasta 31 caracteres, sin
    ``[]:*?/\\`` ni comillas en los bordes, y que no esté ya en el libro
    (Excel no distingue mayúsculas)."""
    limpio = "".join("_" if ch in '[]:*?/\\' else ch for ch in base).strip("' ") or "Bout"
    usados = {t.lower() for t in wb.sheetnames}
    titulo = limpio[:31 - len(sufijo)] + sufijo
    n = 2
    while titulo.lower() in usados:
        marca = f" ({n})"
        titulo = limpio[:31 - len(sufijo) - len(marca)] + marca + sufijo
        n += 1
    return titulo
