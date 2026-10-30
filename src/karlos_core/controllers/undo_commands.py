"""Undo/Redo commands for KARLOS ANNOTATOR.

Provides QUndoCommand subclasses for reversible annotation operations.
Integrates with PySide6's QUndoStack for Ctrl+Z / Ctrl+Shift+Z support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

if TYPE_CHECKING:
    from karlos_core.models.annotation import Annotation
    from karlos_core.views.annotations_table import AnnotationsTable


class AddAnnotationCommand(QUndoCommand):
    """Reversible command that adds an annotation to the table.

    Supports undo (remove) and redo (re-add) with full annotation
    data preservation. Only operates on annotations belonging to
    the currently active athlete pass.

    Attributes:
        _annotation: The Annotation instance to add/remove.
        _table: Reference to the AnnotationsTable view.
        _row_id: The assigned row ID after insertion (set on first redo).
    """

    def __init__(
        self,
        annotation: Annotation,
        table: AnnotationsTable,
        parent: QUndoCommand | None = None,
    ) -> None:
        """Initialize the add-annotation command.

        Args:
            annotation: The annotation to manage.
            table: The target annotations table.
            parent: Optional parent undo command for macro grouping.
        """
        super().__init__(
            f"Add {annotation.technique} [{annotation.athlete}]",
            parent,
        )
        self._annotation = annotation
        self._table = table
        self._row_id: int = 0

    def redo(self) -> None:
        """Execute or re-execute: add the annotation to the table."""
        self._table.add_annotation(self._annotation)
        self._row_id = len(self._table.records)

    def undo(self) -> None:
        """Reverse: remove the annotation from the table by row index."""
        if self._row_id <= 0:
            return
        # Remove the last-added annotation that matches our athlete
        records = self._table.records
        for i in range(len(records) - 1, -1, -1):
            if records[i].athlete == self._annotation.athlete:
                self._table.remove_row(i)
                break

class BorrarAnotacionCommand(QUndoCommand):
    """Quitar una anotacion, con vuelta atras.

    Borrar es lo unico del flujo que no se puede rehacer mirando otra vez
    el video: si el evaluador se equivoca de fila pierde el trabajo. Por
    eso pasa por la pila de deshacer como todo lo demas.
    """

    def __init__(
        self,
        row_idx: int,
        table: AnnotationsTable,
        parent: QUndoCommand | None = None,
    ) -> None:
        registros = table.records
        ann = registros[row_idx] if 0 <= row_idx < len(registros) else None
        nombre = getattr(ann, "technique", "?") if ann else "?"
        super().__init__(f"Eliminar {nombre}", parent)
        self._row = row_idx
        self._table = table
        self._annotation = ann

    def redo(self) -> None:
        if self._annotation is not None and 0 <= self._row < len(self._table.records):
            self._table.remove_row(self._row)

    def undo(self) -> None:
        """Devolver la anotacion a su sitio, no al final de la lista."""
        if self._annotation is None:
            return
        self._table.add_annotation(self._annotation)
        registros = self._table.records
        if self._row < len(registros) - 1:
            devuelta = registros.pop()
            registros.insert(self._row, devuelta)
            if hasattr(self._table, "refresh_all"):
                self._table.refresh_all()


class BorrarTodoCommand(QUndoCommand):
    """Vaciar el registro entero, con vuelta atras.

    Existe porque una pasada mal hecha se tira de una vez, no anotacion a
    anotacion. Las paradas del arbitro se pueden salvar: son
    del combate y valen para cualquier pasada.
    """

    def __init__(
        self,
        table: AnnotationsTable,
        conservar_paradas: bool = False,
        parent: QUndoCommand | None = None,
    ) -> None:
        from karlos_core.utils.i18n import I18n
        super().__init__(I18n().t("undo.apagar_todas"), parent)
        self._table = table
        self._antes = list(table.records)
        self._quedan = (
            [a for a in self._antes
             if getattr(a, "category", "") == "REFEREE STOP"]
            if conservar_paradas else [])

    def _poner(self, registros: list) -> None:
        self._table.clear_all()
        for ann in registros:
            self._table.add_annotation(ann)

    def redo(self) -> None:
        self._poner(self._quedan)

    def undo(self) -> None:
        self._poner(self._antes)


class ExtenderAnotacionCommand(QUndoCommand):
    """Alargar el final de una anotacion existente, con vuelta atras.

    Es como se aplica la regla de la tanda: una segunda finta del mismo
    atleta y miembro a menos de 1,5 s no crea fila, alarga la anterior.
    Deshacer devuelve el final donde estaba.
    """

    def __init__(self, row_idx: int, table: AnnotationsTable, nuevo_fin: int,
                 fps: float, parent: QUndoCommand | None = None) -> None:
        registros = table.records
        ann = registros[row_idx] if 0 <= row_idx < len(registros) else None
        super().__init__(f"Alargar {getattr(ann, 'technique', '?')}", parent)
        self._row = row_idx
        self._table = table
        self._fin_antes = int(ann.f_end) if ann is not None else 0
        self._fin_despues = int(nuevo_fin)
        self._fps = fps if fps and fps > 0 else 30.0

    def _poner_fin(self, fin: int) -> None:
        registros = self._table.records
        if not (0 <= self._row < len(registros)):
            return
        ann = registros[self._row]
        ann.f_end = int(fin)
        ann.duration_s = (int(fin) - int(ann.f_start)) / self._fps
        if hasattr(self._table, "replace_record"):
            self._table.replace_record(self._row, ann)

    def redo(self) -> None:
        self._poner_fin(self._fin_despues)

    def undo(self) -> None:
        self._poner_fin(self._fin_antes)
