"""Keyboard shortcut manager for Karlos Karate.

Extracted from AnnotationController to respect the Single
Responsibility Principle. Every keyboard binding of the annotation
workspace lives here; the digits answer the question tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtGui import QUndoStack

from karlos_core.formato import PRIMERO, SEGUNDO

if TYPE_CHECKING:
    from karlos_core.controllers.annotation_flow_controller import (
        AnnotationFlowController,
    )
    from karlos_core.controllers.fight_session_controller import (
        FightSessionController,
    )
    from karlos_core.controllers.video_manager import VideoManager
    from karlos_core.models.technique import TaxonomyConfig
    from karlos_core.views.main_window import MainWindow


class ShortcutController:
    """Manages all keyboard shortcuts for the annotation workspace.

    Instantiate once per workspace session.  Call ``register_all()``
    after construction, and ``unregister()`` when leaving the
    workspace to avoid dangling shortcuts on the Hub.
    """

    def __init__(
        self,
        window: MainWindow,
        flow_controller: AnnotationFlowController,
        fight_controller: FightSessionController,
        video_manager: VideoManager,
        undo_stack: QUndoStack,
        config: TaxonomyConfig,
        on_fight_end: callable,
        on_toggle_focus: callable,
        on_export_xlsx: callable,
        on_open_video: callable,
        on_set_frame_start: callable = None,
        on_set_frame_end: callable = None,
        on_next_annotation: callable = None,
        on_prev_annotation: callable = None,
        on_mark_start: callable = None,
        on_mark_end: callable = None,
        on_split: callable = None,
        on_undo: callable = None,
        on_guided_key: callable = None,
        on_guided_back: callable = None,
        on_marcar_puntuacion: callable = None,
        on_intercambio: callable = None,
        on_fase: callable = None,
        on_quitar_fase: callable = None,
    ) -> None:
        self._win = window
        self._on_intercambio = on_intercambio
        self._on_fase = on_fase
        self._on_quitar_fase = on_quitar_fase
        self._flow = flow_controller
        self._fight = fight_controller
        self._video = video_manager
        self._undo = undo_stack
        self._config = config
        self._on_fight_end = on_fight_end
        self._on_toggle_focus = on_toggle_focus
        self._on_export_xlsx = on_export_xlsx
        self._on_open_video = on_open_video
        self._on_set_frame_start = on_set_frame_start
        self._on_set_frame_end = on_set_frame_end
        self._on_next_annotation = on_next_annotation
        self._on_prev_annotation = on_prev_annotation
        self._on_mark_start = on_mark_start
        self._on_mark_end = on_mark_end
        self._on_split = on_split
        self._on_undo = on_undo
        self._on_guided_key = on_guided_key
        self._on_guided_back = on_guided_back
        self._on_marcar_puntuacion = on_marcar_puntuacion
        self._shortcuts: list[QShortcut] = []
        # Los numeros, que contestan el arbol de preguntas (ver `_registrar_digitos`).
        self._atajos_digito: list[QShortcut] = []
        # La repeticion de las teclas de fotograma la lleva el programa,
        # no el sistema. Ver `paso_sostenido`: sin esto, mantener [L]
        # daba un fotograma, medio segundo de silencio y despues un
        # barrido a tirones que ademas iba distinto en cada maquina.
        from karlos_core.controllers.paso_sostenido import PasoSostenido
        self._paso = PasoSostenido(self._video.step, window)
        self._filtro_soltar = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _despachar_i(self) -> None:
        """[I] — marcar el inicio de la accion, que es lo que [I] hace en
        todos los programas de video."""
        (self._on_mark_start or self._flow.on_mark_start)()

    def _despachar_o(self) -> None:
        """[O] — marcar el final de la accion."""
        (self._on_mark_end or self._flow.on_mark_end)()

    def _despachar_f(self) -> None:
        """[F] — inicio del combate."""
        self._fight.on_fight_start()

    def register_all(self) -> None:
        """Create and activate every shortcut."""
        win = self._win
        ctx = Qt.ShortcutContext.WindowShortcut

        s = self._shortcuts

        # Annotation flow: [I] y [O] delimitan la accion.
        s.append(QShortcut(QKeySequence("I"), win, self._despachar_i, context=ctx))
        s.append(QShortcut(QKeySequence("O"), win, self._despachar_o, context=ctx))
        if self._on_split:
            s.append(QShortcut(QKeySequence("S"), win, self._on_split, context=ctx))
        if self._on_marcar_puntuacion:
            # [P] eleva la ultima anotacion a accion puntuada. Va aparte del
            # arbol a proposito: de 38 ataques anotados en ID30 solo 2
            # puntuaron, asi que preguntarlo en cada uno costaria 38
            # pulsaciones para dos bits de informacion.
            s.append(QShortcut(QKeySequence("P"), win,
                               self._on_marcar_puntuacion, context=ctx))

        # Playback
        s.append(QShortcut(QKeySequence("Space"), win, self._video.toggle_play, context=ctx))
        self._tecla_paso(win, ctx, "Left", -1)
        self._tecla_paso(win, ctx, "Right", 1)
        self._tecla_paso(win, ctx, "Shift+Left", -10)
        self._tecla_paso(win, ctx, "Shift+Right", 10)

        # ── J K L, bajo los dedos ──────────────────────────────────
        # Empezaron siendo el shuttle de velocidad variable de los
        # montadores. Johan lo probo anotando y prefirio que J y L
        # hicieran lo mismo que las flechas: asi la mano derecha no se
        # mueve en toda la faena — [J] [K] [L] en la fila de reposo,
        # [I] y [O] justo encima, el pulgar en la barra.
        #
        # Y no se pierde el barrido: las teclas se repiten solas al
        # mantenerlas, y cada fotograma cuesta ahora 0,93 ms, asi que
        # tener [L] apretada ES avanzar de continuo, al ritmo de uno.
        self._tecla_paso(win, ctx, "J", -1)
        self._tecla_paso(win, ctx, "L", 1)
        self._tecla_paso(win, ctx, "Shift+J", -10)
        self._tecla_paso(win, ctx, "Shift+L", 10)
        # [K] entre las dos, donde el montador para: aqui reproduce y
        # pausa, lo mismo que la barra, para no tener que bajar el pulgar.
        s.append(QShortcut(QKeySequence("K"), win,
                           self._video.toggle_play, context=ctx))

        # ── Intercambio siguiente y anterior ───────────────────────
        # Arriba y abajo van al corte siguiente o anterior, como en
        # cualquier montador. Aqui el corte es la parada del arbitro
        # anotada: la mitad del video es tiempo muerto y esto se lo salta.
        if self._on_intercambio:
            s.append(QShortcut(QKeySequence("Down"), win,
                               lambda: self._on_intercambio(+1), context=ctx))
            s.append(QShortcut(QKeySequence("Up"), win,
                               lambda: self._on_intercambio(-1), context=ctx))

        # I/O
        s.append(QShortcut(QKeySequence("Ctrl+S"), win, self._on_export_xlsx, context=ctx))
        s.append(QShortcut(QKeySequence("Ctrl+O"), win, self._on_open_video, context=ctx))

        # Athlete switching
        s.append(QShortcut(QKeySequence("A"), win, lambda: self._win.annotation_panel.set_athlete(PRIMERO), context=ctx))
        s.append(QShortcut(QKeySequence("B"), win, lambda: self._win.annotation_panel.set_athlete(SEGUNDO), context=ctx))

        # ── [F] y [G] son el combate ───────────────────────────────
        # La accion es [I] y [O], donde descansa la mano derecha —[J K L]
        # debajo, [I] [O] encima— mientras la izquierda vive en los
        # numeros del arbol.
        s.append(QShortcut(QKeySequence("F"), win, self._despachar_f, context=ctx))
        s.append(QShortcut(QKeySequence("G"), win, self._on_fight_end, context=ctx))

        # ── Las fases del tiempo-movimiento ────────────────────────
        # Teclas de estado y ninguna pregunta: los numeros del panel de
        # fases, y las letras que declare el deporte (el karate, ninguna).
        if self._on_fase:
            from karlos_core.tiempo_movimiento import letras_de_fase
            letras = letras_de_fase()
            for tecla, estado in letras:
                s.append(QShortcut(QKeySequence(tecla), win,
                                   lambda e=estado: self._on_fase(e), context=ctx))
            # Quitar la ultima marca: la tecla la dice el deporte
            # (Shift+1 en karate).
            if self._on_quitar_fase:
                from karlos_core.tiempo_movimiento import tecla_de_retirar
                s.append(QShortcut(QKeySequence(tecla_de_retirar()), win,
                                   self._on_quitar_fase, context=ctx))

        # Misc
        s.append(QShortcut(QKeySequence("Ctrl+Shift+F"), win, self._on_toggle_focus, context=ctx))

        # Undo / Redo
        # Ajuste fino del registro seleccionado al frame actual del video:
        # una anotacion con frames aproximados se fija navegando cuadro a
        # cuadro.
        if self._on_set_frame_start:
            s.append(QShortcut(QKeySequence("Shift+I"), win, self._on_set_frame_start, context=ctx))
        if self._on_set_frame_end:
            s.append(QShortcut(QKeySequence("Shift+O"), win, self._on_set_frame_end, context=ctx))

        # ── Anotacion siguiente y anterior ─────────────────────────
        # Tab y Shift+Tab: probados en uso real. Se descarto "." y ","
        # porque no llegaban a la ventana.
        if self._on_next_annotation:
            s.append(QShortcut(QKeySequence("Tab"), win,
                               self._on_next_annotation, context=ctx))
        if self._on_prev_annotation:
            s.append(QShortcut(QKeySequence("Shift+Tab"), win,
                               self._on_prev_annotation, context=ctx))

        s.append(QShortcut(QKeySequence("Ctrl+Z"), win,
                           self._on_undo or self._undo.undo, context=ctx))
        s.append(QShortcut(QKeySequence("Ctrl+Shift+Z"), win, self._undo.redo, context=ctx))

        # Atras en el arbol de preguntas
        if self._on_guided_back:
            s.append(QShortcut(QKeySequence("Backspace"), win,
                               self._on_guided_back, context=ctx))

        self._registrar_digitos()

        self._instalar_vigilante()

    def _registrar_digitos(self) -> None:
        """Los diez numeros van al recorrido: contestan la pregunta del arbol
        y, en el tiempo-movimiento, marcan la fase."""
        if not self._on_guided_key:
            return
        ctx = Qt.ShortcutContext.WindowShortcut
        for digito in "1234567890":
            sh = QShortcut(QKeySequence(digito), self._win, context=ctx)
            sh.activated.connect(lambda d=digito: self._on_guided_key(d))
            self._atajos_digito.append(sh)
            self._shortcuts.append(sh)

    def _tecla_paso(self, win, ctx, tecla: str, delta: int) -> None:
        """Una tecla de fotograma, con la repeticion del sistema apagada.

        `setAutoRepeat(False)` es la mitad del arreglo: sin el, el atajo
        seguiria disparando al ritmo irregular del sistema ademas del
        barrido propio, y los dos se pisarian.
        """
        atajo = QShortcut(QKeySequence(tecla), win,
                          lambda d=delta: self._paso.pulsar(d), context=ctx)
        atajo.setAutoRepeat(False)
        self._shortcuts.append(atajo)

    def _instalar_vigilante(self) -> None:
        """Saber cuando se suelta la tecla, para parar el barrido.

        Un atajo solo avisa de la pulsacion. La subida de la tecla llega
        como evento normal, y tambien hay que parar cuando la ventana
        pierde el foco: si no, cambiar de aplicacion con la tecla abajo
        dejaria el video corriendo solo.

        El filtro va en la APLICACION y no en la ventana. Un filtro de
        ventana solo ve lo que se entrega a esa ventana, y las teclas se
        entregan al widget con el foco: basta con que ese widget acepte
        la subida —la tabla, el campo de notas— para que la ventana no
        se entere y el barrido se quede corriendo solo.
        """
        controlador = self

        class Vigilante(QObject):
            def eventFilter(self, obj, ev):
                tipo = ev.type()
                if tipo == QEvent.Type.KeyRelease and not ev.isAutoRepeat():
                    controlador._paso.soltar()
                elif tipo in (QEvent.Type.WindowDeactivate,
                              QEvent.Type.FocusOut):
                    controlador._paso.soltar()
                return False

        from PySide6.QtWidgets import QApplication
        self._filtro_soltar = Vigilante(self._win)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self._filtro_soltar)
        else:
            self._win.installEventFilter(self._filtro_soltar)

    def unregister(self) -> None:
        """Remove all shortcuts (call when leaving workspace)."""
        for sh in self._shortcuts:
            sh.setEnabled(False)
        self._shortcuts.clear()
        self._atajos_digito.clear()
        self._paso.soltar()
        if self._filtro_soltar is not None:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.removeEventFilter(self._filtro_soltar)
            self._win.removeEventFilter(self._filtro_soltar)
            self._filtro_soltar = None