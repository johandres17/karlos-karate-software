"""Fight session sub-controller for KARLOS ANNOTATOR.

Handles fight start/end marking and the two-pass athlete workflow
(AKA complete → AO complete). Enforces strict pass ordering:
you MUST finish analyzing one athlete before switching to the other.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal


class FightSessionController(QObject):
    """Controls fight segment marking and the two-pass athlete workflow.

    Signals:
        fight_markers_changed(): Emitted after fight_start/end or
            analyze-other, so the orchestrator can auto-save.
        fight_ended(start, end, duration, pass_num, aka_count, ao_count):
            Emitted when [G] is pressed, so the orchestrator can open
            the FightEndPopup with full context.
        analyze_other_requested(athlete): Emitted when the user chooses
            to analyze the other athlete from the popup.
        pass_changed(pass_num, athlete): Emitted when the analysis pass
            changes (e.g., "PASS 1/2 — Analyzing AKA").
    """

    fight_markers_changed = Signal()
    # El asalto n se acaba de marcar («inicio» o «fin»), y el aviso de que
    # falta marcar el inicio de uno antes de cerrarlo.
    asalto_marcado = Signal(int, str)
    falta_el_inicio = Signal(int)
    # F o G rechazados, con el porqué (el texto ya va traducido).
    asalto_rechazado = Signal(str)
    fight_ended = Signal(int, int, float, int, int, int)
    # start, end, duration_s, pass_num, aka_count, ao_count
    analyze_other_requested = Signal(str)
    pass_changed = Signal(int, str)

    def __init__(
        self,
        video_manager,
        video_panel,
        annotation_panel,
        table_view,
        sport_meta: dict[str, str],
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._vm = video_manager
        self._vp = video_panel
        self._ap = annotation_panel
        self._tv = table_view
        self._sport_meta = sport_meta

        # Two-pass state
        self._current_pass: int = 0  # 0=no fight started, 1=AKA, 2=AO
        self._athlete_locked: bool = False
        self._first_pass_complete: bool = False
        # Los asaltos del combate, si el deporte tiene más de uno. Son del
        # vídeo y no de la pasada: ni se borran al cambiar de atleta ni se
        # vuelven a marcar en la segunda vuelta (Johan, 7-10-2026).
        self._asaltos = None
        # El modo estricto de los asaltos (la pasada de fases del
        # tiempo-movimiento, Johan 12-10-2026: «piensa bien cómo
        # delimitarlos sin fallos»): F abre el siguiente y solo después del
        # final del anterior, G cierra el abierto, y un asalto cerrado solo
        # se corrige eligiéndolo antes (``asalto_elegido``). Lo decide el
        # controlador de la ventana; ``validar_asalto`` le deja vetar un
        # cambio que dejaría fases fuera de su asalto.
        self.estricto = lambda: False
        self.validar_asalto = None
        self.asalto_elegido: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_pass(self) -> int:
        return self._current_pass

    @property
    def is_athlete_locked(self) -> bool:
        return self._athlete_locked

    @property
    def is_two_pass_complete(self) -> bool:
        return self._first_pass_complete and self._current_pass == 2

    # ------------------------------------------------------------------
    # Public handlers (wired by orchestrator)
    # ------------------------------------------------------------------

    def on_fight_start(self) -> None:
        """Handle Fight START [F]."""
        vm = self._vm
        if not vm.is_loaded:
            return

        # Lock the athlete but DON'T force which one — user chooses freely
        current_athlete = self._ap.athlete
        anterior = self._current_pass
        if not self._first_pass_complete:
            self._current_pass = 1
        else:
            self._current_pass = 2
        self._ap.lock_athlete(True)
        self._athlete_locked = True
        self._vp.set_pass_label(self._current_pass, current_athlete)
        # Solo al CAMBIAR de pasada: volver a pulsar [F] para corregir el
        # inicio no es empezar otro atleta.
        if self._current_pass != anterior:
            self.pass_changed.emit(self._current_pass, current_athlete)

        if self._asaltos is not None:
            if self.estricto():
                n, error = self._asalto_estricto("inicio", vm.current_frame)
                if error:
                    self.asalto_rechazado.emit(error)
                    return
            else:
                n = self._asalto_a_marcar(vm.current_frame)
            if not n:
                # Todos cerrados y el vídeo fuera de ellos: no hay nada que
                # marcar, y se dice en vez de pisar el último.
                self.asalto_marcado.emit(0, "completos")
                return
            self._asaltos.marcar_inicio(n, vm.current_frame)
            self._sincronizar_marcas()
            self.asalto_marcado.emit(n, "inicio")
        else:
            vm.set_fight_start()
        self._vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
        self.fight_markers_changed.emit()

    # ── Los asaltos ─────────────────────────────────────────────────
    def poner_asaltos(self, asaltos) -> None:
        """Los asaltos de este combate, o None si el deporte tiene uno."""
        self._asaltos = asaltos

    @property
    def asaltos(self):
        return self._asaltos

    def _asalto_a_marcar(self, frame: int) -> int:
        """Cuál se está marcando: el del fotograma donde está el vídeo si
        cae dentro de alguno —así se corrige uno ya marcado— y si no, el
        que toca. 0 si ya están todos cerrados y el vídeo no cae en
        ninguno: antes daba el último, y [F] al principio del vídeo movía
        el inicio del asalto 3 al del 1 (el especialista, 12-10-2026: «al pasar al
        atleta rojo empieza directamente en el Round 3»)."""
        n = self._asaltos.de_fotograma(frame)
        if n:
            return n
        if self._asaltos.marcados >= self._asaltos.total:
            return 0
        return self._asaltos.en_curso

    def cerrar_asalto(self) -> bool:
        """[G] con asaltos: cerrar el que toca. False si no tiene inicio.

        El combate no termina hasta que se cierra el último: quien llama
        mira ``asaltos.marcados`` para saber si ya están todos.
        """
        vm = self._vm
        if self.estricto():
            n, error = self._asalto_estricto("fin", vm.current_frame)
            if error:
                self.asalto_rechazado.emit(error)
                return False
        else:
            n = self._asalto_a_marcar(vm.current_frame)
        if not n:
            self.asalto_marcado.emit(0, "completos")
            return False
        if self._asaltos.inicio(n) is None:
            self.falta_el_inicio.emit(n)
            return False
        self._asaltos.marcar_fin(n, vm.current_frame)
        self._sincronizar_marcas()
        self._vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
        self.asalto_marcado.emit(n, "fin")
        self.fight_markers_changed.emit()
        return True

    def asalto_abierto(self) -> int:
        """El asalto empezado y sin cerrar, o 0."""
        a = self._asaltos
        if a is None:
            return 0
        return next((n for n in range(1, a.total + 1)
                     if a.inicio(n) is not None and a.fin(n) is None), 0)

    def _asalto_estricto(self, que: str, frame: int) -> tuple[int, str]:
        """Qué asalto marca F («inicio») o G («fin») en el modo estricto, o
        por qué no se puede. (n, "") si vale; (0, "") si están todos
        marcados; (0, texto) si se rechaza.

        - Con un asalto elegido (su pastilla pulsada), F mueve su inicio y
          G su final.
        - Si no, G cierra el asalto abierto; y F abre el siguiente sin
          empezar, o, con uno abierto, solo adelanta su inicio (pulsado
          tarde): más adelante, F diría que antes hay que cerrarlo.
        - Siempre en orden: un asalto empieza después de que acabe el
          anterior, acaba después de empezar y antes de que empiece el
          siguiente.
        """
        from karlos_core.utils.i18n import I18n
        t = I18n().t
        a = self._asaltos
        fps = self._vm.fps or 30.0

        def reloj(f: int) -> str:
            s = max(0, int(f)) / max(float(fps), 1.0)
            return f"{int(s // 60)}:{int(s % 60):02d}"

        frame = int(frame)
        elegido = int(self.asalto_elegido or 0)
        abierto = self.asalto_abierto()
        if elegido and 1 <= elegido <= a.total:
            n = elegido
        elif que == "fin":
            if not abierto:
                dentro = a.de_fotograma(frame)
                if dentro:
                    return 0, t("tm.asalto_cerrado_elegir", n=str(dentro))
                if a.marcados >= a.total:
                    return 0, ""
                return 0, t("pro.asalto_sin_inicio", n=str(a.en_curso))
            n = abierto
        else:
            if abierto:
                if frame >= int(a.inicio(abierto)):
                    return 0, t("tm.asalto_abierto_cerrar", n=str(abierto))
                n = abierto           # pulsado tarde: el inicio se adelanta
            else:
                n = next((k for k in range(1, a.total + 1) if a.inicio(k) is None), 0)
                if not n:
                    dentro = a.de_fotograma(frame)
                    return 0, (t("tm.asalto_cerrado_elegir", n=str(dentro)) if dentro else "")
        # El orden de los asaltos.
        previo_fin = a.fin(n - 1) if n > 1 else None
        siguiente = a.inicio(n + 1) if n < a.total else None
        if que == "inicio":
            if n > 1 and a.inicio(n - 1) is not None and previo_fin is None:
                return 0, t("tm.asalto_abierto_cerrar", n=str(n - 1))
            if previo_fin is not None and frame <= int(previo_fin):
                return 0, t("tm.asalto_despues_de", n=str(n), previo=str(n - 1), reloj=reloj(previo_fin))
            if a.fin(n) is not None and frame >= int(a.fin(n)):
                return 0, t("tm.asalto_inicio_antes_fin", n=str(n), reloj=reloj(a.fin(n)))
        else:
            if a.inicio(n) is None:
                return 0, t("pro.asalto_sin_inicio", n=str(n))
            if frame <= int(a.inicio(n)):
                return 0, t("tm.asalto_fin_despues_inicio", n=str(n), reloj=reloj(a.inicio(n)))
        if siguiente is not None and frame >= int(siguiente):
            return 0, t("tm.asalto_antes_del_siguiente", n=str(n), siguiente=str(n + 1),
                        reloj=reloj(siguiente))
        if self.validar_asalto is not None:
            error = self.validar_asalto(que, n, frame)
            if error:
                return 0, error
        return n, ""

    def _sincronizar_marcas(self) -> None:
        """El combate empieza donde el primer asalto y acaba donde el
        último: lo que mide el tiempo efectivo y escribe el CSV sigue
        siendo lo mismo."""
        vm = self._vm
        vm.fight_start = self._asaltos.inicio_del_combate
        vm.fight_end = self._asaltos.fin_del_combate

    def on_fight_end(self) -> None:
        """Handle Fight END [G] — marks fight end, emits full context."""
        vm = self._vm
        if not vm.is_loaded:
            return
        vm.set_fight_end()
        self._vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)

        dur = vm.fight_duration_s()
        counts = self._athlete_counts()
        self._athlete_locked = False
        self._ap.lock_athlete(False)

        self.fight_ended.emit(
            vm.fight_start or 0,
            vm.fight_end or 0,
            dur or 0.0,
            self._current_pass,
            counts["AKA"],
            counts["AO"],
        )
        self.fight_markers_changed.emit()

    def on_analyze_other_athlete(self) -> None:
        """Switch to the second pass — AO analysis."""
        self._first_pass_complete = True
        self._ap.lock_athlete(False)

        # Las marcas del combate se borraban para que la segunda pasada
        # las volviera a poner. Donde hay asaltos NO: son del vídeo, y el
        # segundo competidor pelea los mismos (Johan, 7-10-2026).
        if self._asaltos is None:
            self._vm.fight_start = None
            self._vm.fight_end = None
        self._vp.update_fight_label(self._vm.fight_start, self._vm.fight_end,
                                    self._vm.fps)
        self._vp.set_pass_label(0, "")  # clear pass label until [F] pressed

        # Announce intent
        self.analyze_other_requested.emit("AO")
        self.fight_markers_changed.emit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _athlete_counts(self) -> dict[str, int]:
        aka = sum(1 for r in self._tv.records if r.athlete == "AKA")
        ao = sum(1 for r in self._tv.records if r.athlete == "AO")
        return {"AKA": aka, "AO": ao}

    def athlete_counts(self) -> dict[str, int]:
        return self._athlete_counts()

    def reiniciar(self) -> None:
        """Cada combate empieza sin pasadas.

        El estado vivia en el controlador, que es uno para toda la
        sesion de trabajo: tras un combate en la segunda pasada, el
        siguiente video heredaba la primera por terminada, y su [F]
        abria la segunda. Lo que haya guardado lo repone despues
        `restore_pass`.
        """
        self._current_pass = 0
        self._first_pass_complete = False
        self._athlete_locked = False
        self.asalto_elegido = 0
        self._ap.lock_athlete(False)
        self._vp.set_pass_label(0, "")

    def restore_pass(self, pass_num: int) -> None:
        """Restore two-pass state from a saved session.

        La primera pasada solo esta terminada si la sesion ya iba por la
        segunda. Con `>= 1` una sesion guardada a mitad de la primera se
        reabria como terminada, y la [F] siguiente empezaba la segunda
        (Johan, 28-09: «Na pasada de AO há 34 momentos...» al marcar el
        inicio de un combate).

        Args:
            pass_num: 1 or 2, from session data.
        """
        self._first_pass_complete = pass_num >= 2
        if pass_num == 2:
            self._current_pass = 2
            self._vp.set_pass_label(2, "AO")
        elif pass_num == 1:
            self._current_pass = 1
            self._vp.set_pass_label(1, "AKA")