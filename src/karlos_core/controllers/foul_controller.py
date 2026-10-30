"""Foul controller for KARLOS ANNOTATOR — la escalera de faltas del deporte.

Cada falta de un atleta sube un peldaño de la escalera de su reglamento.
El controlador no sabe cuál es: se la pide al deporte que se anota
(``catalogo.activo().reglamento``, decisión 0004), igual que la regla de
qué fila es una sanción (``es_sancion``). En karate es la escalera única
del reglamento WKF 2026, en vigor desde el 1 de enero de 2026:

    1ª falta  → CHUI-1
    2ª falta  → CHUI-2
    3ª falta  → CHUI-3
    4ª falta  → HANSOKU-CHUI
    5ª y más  → HANSOKU

(ver ``karlos_karate``). Pasado el último peldaño, se queda en él.

(Note: Hansoku-Chui and Hansoku can also be awarded directly by the
referee for serious infractions without going through the 3 Chui stages,
but for the annotator each button click simply advances one step on the
ladder. The referee's decision overrides are handled through the existing
score override mechanism.)

Source: WKF Kumite Competition Rules, Rules Version 2026.01, §10.2-10.3
(https://www.wkf.net). Effective 1 January 2026.

CREATION DATE: 24 July 2026
AUTHOR: Johan Barthélemy (Cline implementation based on WKF 2026 spec)

This controller is completely independent from AnnotationFlowController —
it does NOT use on_mark_end(), _last_technique, or any state-machine
validation. This isolation prevents the Feint/Referee-Stop bug from
affecting foul annotations.

ARQUITECTURA (21-09-2026): el controlador NO guarda contadores. Los
guardaba, y Johan encontro el fallo inevitable: borro unas faltas
anotadas por error y el contador siguio en su sitio, asi que la
siguiente falta salio con grado de HANSOKU-CHUI. Acumular y derivar
son enemigos: ahora la cuenta se DERIVA de la tabla de anotaciones
con la misma regla que usa el CSV (es_sancion), y borrar, deshacer o
editar la deja bien sin avisar a nadie. resincronizar() reetiqueta
los grados CHUI-N cuando la tabla cambia.

Infraction types (stored in Annotation.subcategory):
    - "Contact"      — excessive contact, uncontrolled techniques
    - "Target"       — attacks to prohibited areas (e.g., throat, back)
    - "Illegal Tech" — prohibited techniques (e.g., elbows, open-hand)
    - "Procedure"    — procedural violations including Jogai (stepping out),
                       clinching, avoiding combat, unsportsmanlike conduct
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal

from karlos_core.models.annotation import Annotation
from karlos_core.controllers.undo_commands import AddAnnotationCommand
from karlos_core import catalogo
from karlos_core.formato import COMPETIDORES, PRIMERO, SEGUNDO


def sanciones_por_competidor(filas) -> tuple[int, int]:
    """Cuántas sanciones hay de cada competidor en esas filas: (primero,
    segundo), con la regla del deporte que se anota.

    Es la cuenta del contador de la pantalla. La del CSV sale de la misma
    regla (``es_sancion`` del deporte), así que no pueden discrepar.
    """
    deporte = catalogo.activo()
    a, b = (c.codigo for c in deporte.competidores)
    cuenta = {a: 0, b: 0}
    for f in filas:
        if deporte.es_sancion(f) and f.athlete in cuenta:
            cuenta[f.athlete] += 1
    return cuenta[a], cuenta[b]


# ══════════════════════════════════════════════════════════════════
# FoulController
# ══════════════════════════════════════════════════════════════════


class FoulController(QObject):
    """Independent controller for progressive foul registration.

    No guarda contadores: la cuenta de cada atleta se deriva de la tabla.
    Each foul registration:
    1. Counts the athlete's sanctions in the table up to this frame
    2. Maps count → the sport's ladder label (``reglamento.grado``)
    3. Creates an Annotation with Category="PENALTY"
    4. Adds it to the table view via AddAnnotationCommand
    5. Emits foul_registered for auto-save

    Signals:
        foul_registered(): Emitted after a foul annotation is added to the
            table, so the orchestrator can trigger auto-save.
    """

    foul_registered = Signal()

    def __init__(
        self,
        table_view,
        undo_stack,
        window,  # MainWindow (for status messages)
        annotation_panel,
        video_manager,
        bout_info: dict[str, str],
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialize the foul controller.

        Args:
            table_view: AnnotationsTableView for adding records.
            undo_stack: QUndoStack for reversible commands.
            window: MainWindow for status bar messages.
            annotation_panel: AnnotationPanelView for athlete/notes.
            video_manager: VideoManager for frame info.
            bout_info: Mutable dict with bout metadata.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._tv = table_view
        self._undo_stack = undo_stack
        self._win = window
        self._ap = annotation_panel
        self._vm = video_manager
        self._bout_info = bout_info

    # ── La cuenta se deriva SIEMPRE de la tabla ──────────────────
    #
    # La regla es es_sancion, la misma del CSV: una falta cuenta tanto
    # anotada sola (PENALTY) como dentro del ataque que la provoco.

    def _sanciones(self):
        """Las filas que suman peldaño, en orden de combate."""
        es_sancion = catalogo.activo().es_sancion
        filas = [r for r in (self._tv.records or []) if es_sancion(r)]
        return sorted(filas, key=lambda r: int(r.f_start or 0))

    def get_count(self, athlete: str) -> int:
        """Cuantas faltas lleva ese atleta, contadas de la tabla."""
        return sum(1 for r in self._sanciones() if r.athlete == athlete)

    @property
    def aka_fouls(self) -> int:
        return self.get_count(PRIMERO)

    @property
    def ao_fouls(self) -> int:
        return self.get_count(SEGUNDO)

    def resincronizar(self) -> int:
        """Reetiquetar los grados tras cualquier cambio en la tabla.

        Si se borra la CHUI-2 de tres, la que era CHUI-3 pasa a ser
        CHUI-2: el grado no es de la falta sino de su posicion en la
        escalera, y la escalera es la tabla. Devuelve cuantas filas
        hubo que corregir.
        """
        grado = catalogo.activo().reglamento.grado
        cuenta = dict.fromkeys(COMPETIDORES, 0)
        corregidas = 0
        for fila in self._sanciones():
            if fila.athlete not in cuenta:
                continue
            cuenta[fila.athlete] += 1
            if fila.category != "PENALTY":
                continue          # la ligada al ataque no lleva rotulo propio
            correcto = grado(cuenta[fila.athlete])
            if fila.technique != correcto:
                fila.technique = correcto
                try:
                    idx = self._tv.records.index(fila)
                    self._tv.replace_record(idx, fila)
                except (ValueError, AttributeError):
                    pass
                corregidas += 1
        return corregidas

    # ── Public API ───────────────────────────────────────────────

    @property
    def descalifica(self) -> int:
        """La falta que acaba el combate: el último peldaño de la escalera
        (en karate, la quinta: HANSOKU)."""
        return len(catalogo.activo().reglamento.escalera_de_faltas)

    def ya_descalificado(self, athlete: str) -> bool:
        """Si ese atleta ya acumula la falta que acaba el combate.

        No impide anotar: si el aviso es falso porque hay un error en una
        falta anterior, bloquear obligaria a deshacer antes de poder
        seguir, y se perderia trabajo por una equivocacion del sistema.
        """
        return self.get_count(athlete) >= self.descalifica

    def register_foul(self, infraction_type: str) -> None:
        """Register a progressive foul for the currently active athlete.

        This is the main entry point, called when the user clicks
        any of the 4 foul buttons (Contact [C], Target [V],
        Illegal Tech [D], Procedure [H]).

        The flow is COMPLETELY INDEPENDENT of on_mark_end() and
        _last_technique — it reads only the active athlete from the
        annotation panel and writes the annotation directly.

        Args:
            infraction_type: One of "Contact", "Target",
                "Illegal Tech", or "Procedure".
        """
        athlete = self._ap.athlete

        # 1. La cuenta sale de la tabla: las sanciones de este atleta
        #    hasta el punto del video donde se anota. Cronologica, para
        #    que insertar una falta hacia atras no herede grados de las
        #    posteriores (resincronizar recoloca esas despues).
        f_aqui = int(self._vm.current_frame)
        count = 1 + sum(1 for r in self._sanciones()
                        if r.athlete == athlete and int(r.f_start or 0) <= f_aqui)

        # 2. Map count → the sport's ladder label
        label = catalogo.activo().reglamento.grado(count)

        # 3. Build ordinal string for status message
        ordinal = self._ordinal(count)

        # 4. Create the Annotation
        current_frame = self._vm.current_frame

        annotation = Annotation(
            athlete=athlete,
            category="PENALTY",
            subcategory=infraction_type,
            technique=label,
            level="",
            score="",
            f_start=current_frame,
            f_end=current_frame,
            duration_s=0.0,
            round=int(self._bout_info.get("current_round", 1) or 1),
            fight_f_start=self._vm.fight_start,
            fight_f_end=self._vm.fight_end,
            fight_dur_s=(
                self._vm.fight_duration_s() if self._vm.fight_start else 0.0
            ),
            active_play_s=None,
            video_file="",
            notes="",
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

        # 5. Add to table via undo stack
        self._undo_stack.push(
            AddAnnotationCommand(annotation, self._tv)
        )

        # 6. Status message
        self._win.set_status_message(
            f"{infraction_type} foul — {athlete}, {ordinal} time → {label}"
        )

        # 7. Si la falta se inserto hacia atras, las posteriores
        #    cambian de grado.
        self.resincronizar()

        # 8. Emit for auto-save
        self.foul_registered.emit()

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _ordinal(n: int) -> str:
        """Return the ordinal string for a number (1st, 2nd, 3rd, etc.)."""
        if n == 1:
            return "1st"
        elif n == 2:
            return "2nd"
        elif n == 3:
            return "3rd"
        return f"{n}th"