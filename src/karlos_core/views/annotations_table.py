"""Annotations table view for KARLOS ANNOTATOR.

Displays the annotation log as a table with columns for athlete, category,
technique, level, score, frame range, and status. Supports row deletion.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from karlos_core.models.annotation import Annotation
from karlos_core.models.technique import AppColors
from karlos_core.views.theme import Palette


class AnnotationsTableView(QWidget):
    """Table widget displaying all annotation records.

    Signals:
        delete_requested(indices): Emitted when user requests deletion
            of selected rows, with a list of row indices.
    """

    delete_requested = Signal(list)
    seek_requested = Signal(int)  # frame index
    edit_requested = Signal(int)  # row index — double-click to edit
    # Avisa de cualquier cambio en los registros. Que lo emita la tabla y
    # no quien la modifica evita que una vista derivada se quede desfasada
    # porque alguien anadio una via nueva y olvido refrescarla.
    registros_cambiaron = Signal()

    # Columns displayed in the table (Karate default)
    COLUMNS_KARATE = [
        "#", "R", "Athlete", "Category", "Subcategory",
        "Technique", "Level", "Score",
        "F.Start", "F.End", "Status",
    ]

    # Columns displayed for Kickboxing (Stance + Target split)
    COLUMNS_KB = [
        "#", "R", "Athlete", "Category", "Subcategory",
        "Technique", "Stance", "Target", "Score",
        "F.Start", "F.End", "Status",
    ]

    @property
    def COLUMNS(self) -> list[str]:
        """Return the correct column headers for the current sport."""
        return self.COLUMNS_KB if getattr(self, '_sport_id', 'karate') == 'kickboxing' else self.COLUMNS_KARATE

    def __init__(
        self,
        colors: AppColors,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the annotations table view.

        Args:
            colors: Application color palette.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._colors = colors
        p = Palette.from_config(colors)
        # Map score codes to colors (resolved from Palette at init)
        self.SCORE_COLORS: dict[str, str] = {
            "IPPON": p.chart_orange,
            "WAZA": p.warning,
            "YUKO": p.chart_green,
            "NONE": p.text_secondary,
            "FOUL": p.aka,
        }
        self._records: list[Annotation] = []
        self._build()

    @property
    def records(self) -> list[Annotation]:
        """All annotation records currently in the table."""
        return self._records

    # ------------------------------------------------------------------
    # Visual order helpers (newest-first display)
    # ------------------------------------------------------------------
    # The table shows the NEWEST annotation at the TOP for easier control
    # during live annotation, while self._records stays in chronological
    # order (used by export, session save, and reports — unchanged).

    def _visual_to_record(self, visual_row: int) -> int:
        """Convert a visual table row (0 = top/newest) to a record index."""
        return len(self._records) - 1 - visual_row

    def _record_to_visual(self, record_idx: int) -> int:
        """Convert a record index to its visual table row."""
        return len(self._records) - 1 - record_idx

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def set_sport_id(self, sport_id: str) -> None:
        """Set the sport ID for sport-specific column layout."""
        self._sport_id = sport_id
        # Rebuild the table with the correct columns
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)

    def add_annotation(self, annotation: Annotation) -> None:
        """Add a single annotation record to the table.

        Args:
            annotation: The annotation to add.
        """
        self._records.append(annotation)
        # Chronological number (1-based) — matches export order
        seq_num = len(self._records)
        # Newest entry is displayed at the TOP (visual row 0)
        row = 0
        self._table.insertRow(row)

        ac = (
            self._colors.aka
            if annotation.athlete == "AKA"
            else self._colors.ao
        )
        sc_color = self.SCORE_COLORS.get(annotation.score, self._colors.muted)

        current_round = getattr(annotation, "round", 0) or 0
        cols = self.COLUMNS

        # Build values dynamically from column names
        _level = annotation.level
        _stance = getattr(annotation, "stance", "") or ""
        _target = getattr(annotation, "target", "") or ""
        if self._sport_id == "kickboxing" and _stance and _target:
            _level = ""  # hide generic level when split columns exist

        # ── Athlete display: corner name for Kickboxing, AKA/AO for Karate ─
        athlete_label = annotation.athlete
        is_kb = getattr(self, '_sport_id', 'karate') == 'kickboxing'
        if is_kb:
            if annotation.athlete == "AKA":
                corner_name = getattr(self, '_corner_name_a', '') or 'Fighter A'
                athlete_label = f"{corner_name} (A)"
                corner_hex = getattr(self, '_color_a', self._colors.aka)
            else:
                corner_name = getattr(self, '_corner_name_b', '') or 'Fighter B'
                athlete_label = f"{corner_name} (B)"
                corner_hex = getattr(self, '_color_b', self._colors.ao)
            ac = corner_hex  # Use corner color for athlete column
            # Row tint from corner color
            try:
                r = int(corner_hex[1:3], 16)
                g = int(corner_hex[3:5], 16)
                b = int(corner_hex[5:7], 16)
                row_bg = f"rgba({r},{g},{b},0.06)"
            except (ValueError, IndexError):
                row_bg = "rgba(128,128,128,0.06)"

        col_values: dict[str, str] = {
            "#": str(seq_num),
            "R": str(current_round) if current_round else "",
            "Athlete": athlete_label,
            "Category": annotation.category,
            "Subcategory": annotation.subcategory,
            "Technique": annotation.technique,
            "Level": _level,
            "Stance": _stance,
            "Target": _target,
            "Score": annotation.score,
            "F.Start": str(annotation.f_start),
            "F.End": str(annotation.f_end),
            "Status": annotation.status,
        }

        values = [col_values.get(c, "") for c in cols]

        # ── Row background tint by athlete (Karate only; KB set above) ─
        if not is_kb:
            row_bg = (
                "rgba(211,47,47,0.06)" if annotation.athlete == "AKA"
                else "rgba(25,118,210,0.06)"
            )

        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            item.setBackground(QColor(row_bg))

            col_name = cols[col] if col < len(cols) else ""
            if col_name == "Athlete":
                item.setForeground(QColor(ac))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            elif col_name == "Score":
                item.setForeground(QColor(sc_color))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            elif col_name == "Technique":
                f = item.font()
                f.setItalic(True)
                item.setFont(f)

            self._table.setItem(row, col, item)

        self._table.scrollToTop()
        self._update_count()

    def set_corner_colors(self, color_a: str, color_b: str, name_a: str = "", name_b: str = "") -> None:
        """Store corner colors and labels for row tinting and athlete display.
        
        Args:
            color_a: Hex color for athlete A (e.g., "p.timeline_aka").
            color_b: Hex color for athlete B (e.g., "p.ao_dark").
            name_a: Corner name for athlete A (e.g., "Red", only Kickboxing).
            name_b: Corner name for athlete B (e.g., "Blue", only Kickboxing).
        """
        self._color_a = color_a
        self._color_b = color_b
        self._corner_name_a = name_a
        self._corner_name_b = name_b

    def remove_row(self, row_idx: int) -> None:
        """Remove a single record by RECORD index (chronological).

        Args:
            row_idx: 0-based record index to remove.
        """
        if 0 <= row_idx < len(self._records):
            visual_row = self._record_to_visual(row_idx)
            self._records.pop(row_idx)
            self._table.removeRow(visual_row)
            self._update_count()

    def clear_all(self) -> None:
        """Remove all records from the table."""
        self._records.clear()
        self._table.setRowCount(0)
        self._update_count()

    def update_record_count(self, count: int) -> None:
        """Update the displayed record count.

        Args:
            count: Number of records.
        """
        self._lbl_count.setText(f"{count} entries")

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Construct the table UI."""
        c = self._colors
        p = Palette.from_config(c)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Header row
        hdr = QHBoxLayout()
        lbl = QLabel("ANNOTATION LOG")
        lbl.setStyleSheet(
            f"color:{p.text_disabled};font-size:11px;font-weight:700;"
            "letter-spacing:1px;text-transform:uppercase;"
            "background:transparent;border:none;"
        )
        hdr.addWidget(lbl)
        hdr.addStretch()

        self._lbl_count = QLabel("0 entries")
        self._lbl_count.setStyleSheet(
            f"color:{c.muted};font-size:12px;font-weight:400;"
            "background:transparent;border:none;"
        )
        hdr.addWidget(self._lbl_count)
        lay.addLayout(hdr)

        # Table
        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            f"QTableWidget{{background:{p.bg_alt};color:{p.text_bright};"
            "gridline-color:transparent;"
            f"border:1px solid {p.border_default};"
            "border-radius:6px;font-size:12px;outline:none;"
            "selection-background-color:rgba(255,107,53,0.15);"
            f"selection-color:{p.text_bright};"
            f"alternate-background-color:{p.bg_table_alt};}}"
            "QTableWidget::item{padding:4px 8px;border:none;"
            f"border-bottom:1px solid {p.surface_2};}}"
            f"QHeaderView::section{{background:{p.surface_2};"
            f"color:{p.text_disabled};font-weight:600;padding:8px 6px;font-size:11px;"
            f"border:none;border-bottom:1px solid {p.border_default};border-right:none;"
            "text-transform:uppercase;letter-spacing:0.5px;}"
            "QTableWidget::item:selected{background:rgba(255,107,53,0.15);"
            f"color:{p.text_bright};outline:none;border:none;}}"
            f"QTableCornerButton::section{{background:{p.surface_2};border:none;}}"
        )
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        lay.addWidget(self._table)

        # Button row: Edit + Delete
        btn_row = QHBoxLayout()
        
        edit_btn = QPushButton("Edit Selected")
        edit_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{p.accent_blue};"
            f"border:1px solid {p.accent_blue};"
            "border-radius:4px;padding:5px 12px;font-size:12px;"
            "font-weight:500;}"
            "QPushButton:hover{background:rgba(47,129,247,0.12);}"
        )
        edit_btn.clicked.connect(self._on_edit)
        btn_row.addWidget(edit_btn)
        
        del_btn = QPushButton("Delete Selected")
        del_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{p.aka};"
            f"border:1px solid {p.aka};"
            "border-radius:4px;padding:5px 12px;font-size:12px;"
            "font-weight:500;}"
            "QPushButton:hover{background:rgba(229,83,75,0.12);}"
        )
        del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        """Open edit popup for the double-clicked annotation row."""
        record_idx = self._visual_to_record(row)
        if 0 <= record_idx < len(self._records):
            self.edit_requested.emit(record_idx)

    def _update_count(self) -> None:
        """Refresh the record count label."""
        self._lbl_count.setText(f"{len(self._records)} entries")
        self.registros_cambiaron.emit()

    def update_record(self, row_idx: int, technique: str = "", level: str = "", score: str = "") -> None:
        """Update fields of an existing annotation record and refresh row."""
        if 0 <= row_idx < len(self._records):
            record = self._records[row_idx]
            if technique:
                record.technique = technique
            if level:
                record.level = level
            if score:
                record.score = score
            self._refresh_row(row_idx)

    def _refresh_row(self, row: int) -> None:
        """Re-render a single row (by RECORD index) from the records list."""
        self.registros_cambiaron.emit()
        if row < 0 or row >= len(self._records):
            return
        a = self._records[row]
        visual_row = self._record_to_visual(row)
        ac = self._colors.aka if a.athlete == "AKA" else self._colors.ao
        sc = self.SCORE_COLORS.get(a.score, self._colors.muted)
        self._table.item(visual_row, 5).setText(a.technique)
        self._table.item(visual_row, 6).setText(a.level)
        score_item = self._table.item(visual_row, 7)
        score_item.setText(a.score)
        score_item.setForeground(QColor(sc))

    def replace_record(self, row_idx: int, annotation: Annotation) -> None:
        """Replace an annotation record entirely and refresh the row.

        Args:
            row_idx: 0-based row index to replace.
            annotation: New Annotation instance.
        """
        if 0 <= row_idx < len(self._records):
            self._records[row_idx] = annotation
            # Remove the old visual row and rebuild with new data
            visual_row = self._record_to_visual(row_idx)
            self._table.removeRow(visual_row)
            self._rebuild_row(row_idx)
            self.registros_cambiaron.emit()

    def _rebuild_row(self, row: int) -> None:
        """Rebuild a single row from scratch using the records list.

        Args:
            row: RECORD index (chronological). The visual position is
                derived via _record_to_visual().
        """
        if row < 0 or row >= len(self._records):
            return
        annotation = self._records[row]
        visual_row = self._record_to_visual(row)
        self._table.insertRow(visual_row)

        ac = (
            self._colors.aka
            if annotation.athlete == "AKA"
            else self._colors.ao
        )
        sc_color = self.SCORE_COLORS.get(annotation.score, self._colors.muted)
        current_round = getattr(annotation, "round", 0) or 0
        cols = self.COLUMNS

        _level = annotation.level
        _stance = getattr(annotation, "stance", "") or ""
        _target = getattr(annotation, "target", "") or ""
        if self._sport_id == "kickboxing" and _stance and _target:
            _level = ""

        athlete_label = annotation.athlete
        is_kb = getattr(self, '_sport_id', 'karate') == 'kickboxing'
        if is_kb:
            if annotation.athlete == "AKA":
                corner_name = getattr(self, '_corner_name_a', '') or 'Fighter A'
                athlete_label = f"{corner_name} (A)"
                corner_hex = getattr(self, '_color_a', self._colors.aka)
            else:
                corner_name = getattr(self, '_corner_name_b', '') or 'Fighter B'
                athlete_label = f"{corner_name} (B)"
                corner_hex = getattr(self, '_color_b', self._colors.ao)
            ac = corner_hex
            try:
                r = int(corner_hex[1:3], 16)
                g = int(corner_hex[3:5], 16)
                b = int(corner_hex[5:7], 16)
                row_bg = f"rgba({r},{g},{b},0.06)"
            except (ValueError, IndexError):
                row_bg = "rgba(128,128,128,0.06)"
        else:
            row_bg = (
                "rgba(211,47,47,0.06)" if annotation.athlete == "AKA"
                else "rgba(25,118,210,0.06)"
            )

        col_values: dict[str, str] = {
            "#": str(row + 1),
            "R": str(current_round) if current_round else "",
            "Athlete": athlete_label,
            "Category": annotation.category,
            "Subcategory": annotation.subcategory,
            "Technique": annotation.technique,
            "Level": _level,
            "Stance": _stance,
            "Target": _target,
            "Score": annotation.score,
            "F.Start": str(annotation.f_start),
            "F.End": str(annotation.f_end),
            "Status": annotation.status,
        }

        values = [col_values.get(c, "") for c in cols]

        for col, val in enumerate(values):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            item.setBackground(QColor(row_bg))

            col_name = cols[col] if col < len(cols) else ""
            if col_name == "Athlete":
                item.setForeground(QColor(ac))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            elif col_name == "Score":
                item.setForeground(QColor(sc_color))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            elif col_name == "Technique":
                f = item.font()
                f.setItalic(True)
                item.setFont(f)

            self._table.setItem(visual_row, col, item)

    def select_record(self, record_idx: int) -> bool:
        """Seleccionar una fila por su indice de registro.

        Hace falta para que [⇧I] y [⇧O] —que recolocan el inicio y el
        fin de la fila seleccionada— puedan apuntar a algo sin que el
        evaluador tenga que buscarlo en la tabla con el raton.
        """
        if not (0 <= record_idx < len(self._records)):
            return False
        visual = self._record_to_visual(record_idx)
        if visual < 0:
            return False
        self._table.selectRow(visual)
        self._table.scrollToItem(self._table.item(visual, 0))
        return True

    def selected_record_index(self) -> int:
        """Return the record index of the first selected row, or -1 if none."""
        selected_rows = {idx.row() for idx in self._table.selectedItems()}
        if not selected_rows:
            return -1
        record_idx = self._visual_to_record(sorted(selected_rows)[0])
        return record_idx if 0 <= record_idx < len(self._records) else -1

    def _on_edit(self) -> None:
        """Handle edit button click — emit edit_requested for selected row."""
        selected_rows = {idx.row() for idx in self._table.selectedItems()}
        if not selected_rows:
            return
        # Edit the first selected (visual) row → map to record index
        visual_row = sorted(selected_rows)[0]
        record_idx = self._visual_to_record(visual_row)
        if 0 <= record_idx < len(self._records):
            self.edit_requested.emit(record_idx)

    def _on_delete(self) -> None:
        """Handle delete button click — remove selected rows."""
        selected_visual = sorted(
            {idx.row() for idx in self._table.selectedItems()},
        )
        if not selected_visual:
            return

        # Map visual rows → record indices (descending so pops are safe)
        record_indices = sorted(
            (self._visual_to_record(v) for v in selected_visual),
            reverse=True,
        )

        self.delete_requested.emit(record_indices)

        for rec_idx in record_indices:
            if 0 <= rec_idx < len(self._records):
                visual_row = self._record_to_visual(rec_idx)
                self._records.pop(rec_idx)
                self._table.removeRow(visual_row)

        self._update_count()
