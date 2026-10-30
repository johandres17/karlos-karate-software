"""Anotar: marcar inicio y fin, puntuar, editar y borrar, faltas fuera de
sitio, y tener la pantalla al día con el vídeo.

Parte del controlador principal (``annotation_controller``), separada en la
fase F3.7.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from karlos_core.controllers.foul_controller import sanciones_por_competidor
from karlos_core.models.state import AnnotationState
from karlos_core.views.edit_annotation_popup import EditAnnotationPopup
from karlos_core import catalogo
from karlos_core.utils.i18n import I18n


class AnotacionMixin:
    """Anotar: marcar inicio y fin, puntuar, editar y borrar, faltas fuera de
    sitio, y tener la pantalla al día con el vídeo."""

    def _deshacer(self) -> None:
        """[Ctrl+Z] — deshace la ultima anotacion."""
        self.undo_stack.undo()

    def _confirmar_falta_tras_hansoku(self) -> bool:
        """Avisar si se anota otra falta a un atleta ya descalificado.

        La quinta falta es HANSOKU y el combate termina ahi, asi que una
        sexta suele significar que hay un error en las anteriores. Se
        avisa pero se deja seguir: bloquear obligaria a deshacer para
        poder anotar, y se perderia trabajo por una sospecha.
        """
        atleta = self.window.annotation_panel.athlete
        if not self.foul_controller.ya_descalificado(atleta):
            return True
        from PySide6.QtWidgets import QMessageBox
        # El nombre del atleta y el último peldaño de su deporte: HANSOKU en
        # el karate, «DISQUALIFICATION» o el quinto gam-jeom en otros.
        ultimo = catalogo.activo().reglamento.escalera_de_faltas[-1]
        resp = QMessageBox.question(
            self.window, self._i18n.t("dialog.descalificado_titulo"),
            self._i18n.t("dialog.descalificado", atleta=catalogo.etiqueta(atleta), ultimo=str(ultimo)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        return resp == QMessageBox.StandardButton.Yes

    @staticmethod
    def acciones_fuera_del_combate(anotaciones, inicio, fin) -> list:
        """Las anotaciones que caen fuera del combate declarado.

        Las anotaciones son la verdad y los limites del combate una ayuda,
        asi que esto no corrige nada solo: lo enseña.
        """
        if inicio is None or fin is None:
            return []
        return [a for a in anotaciones
                if int(a.f_start) < int(inicio) or int(a.f_end) > int(fin)]

    def _avisar_acciones_fuera_del_combate(self) -> None:
        """Si hay acciones fuera del rango, ofrecer estirarlo."""
        vm = self.video_manager
        fuera = self.acciones_fuera_del_combate(
            list(self.window.table_view.records), vm.fight_start, vm.fight_end)
        if not fuera:
            return
        ultima = max(int(a.f_end) for a in fuera)
        primera = min(int(a.f_start) for a in fuera)
        from PySide6.QtWidgets import QMessageBox
        resp = QMessageBox.question(
            self.window, "Acciones fuera del combate",
            f"Hay {len(fuera)} anotaciones fuera del combate marcado "
            f"(f{vm.fight_start}–f{vm.fight_end}).\n\n"
            f"Van de f{primera} a f{ultima}.\n\n"
            "¿Estirar el combate para incluirlas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if resp != QMessageBox.StandardButton.Yes:
            return
        vm.fight_start = min(int(vm.fight_start), primera)
        vm.fight_end = max(int(vm.fight_end), ultima)
        self._schedule_save()
        self.window.set_status_message(
            self._i18n.t("stat.luta_ajustada", inicio=str(vm.fight_start), fim=str(vm.fight_end)))

    def _marcar_puntuacion(self) -> None:
        """[P] — la ultima accion anotada si puntuo.

        El arbol no pregunta la puntuacion. Sobre ID30, de 38 ataques
        anotados solo 2 puntuaron: preguntarlo en cada uno costaria 38
        pulsaciones para registrar dos. Con la tecla aparte se pulsa las
        dos veces que hace falta.

        El valor no se elige: sale de la tecnica y el nivel segun las
        reglas WKF del config — un puño es YUKO, una patada a Chudan es
        WAZA-ARI y a Jodan IPPON.
        """
        registros = self.window.table_view.records
        if not registros:
            self.window.set_status_message(I18n().t("pro.sin_accion_puntuar"))
            return
        idx = len(registros) - 1
        ann = registros[idx]
        categoria = next((c for c in self._config.categories
                          if c.name == ann.subcategory), None)
        score = self._config.scoring_engine.calculate_score(
            ann.technique, ann.level or "", categoria)
        if score in ("", "NONE"):
            self.window.set_status_message(I18n().t("pro.no_puntua", tecnica=ann.technique))
            return
        ann.score = score
        ann.action_result = "Scored"
        self.window.table_view.replace_record(idx, ann)
        self._sync_ui_to_state()
        self.window.set_status_message(f"{ann.technique} → {score}")

    def _borrar_anotacion(self, idx: int) -> None:
        """Quitar una anotacion del registro, con confirmacion."""
        registros = self.window.table_view.records
        if not (0 <= idx < len(registros)):
            return
        ann = registros[idx]
        seg = int(getattr(ann, "f_start", 0) / max(1.0, self.video_manager.fps))
        respuesta = QMessageBox.question(
            self.window, "Eliminar anotación",
            f"¿Eliminar «{ann.technique}» de {ann.athlete} "
            f"en {seg // 60:02d}:{seg % 60:02d}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if respuesta != QMessageBox.Yes:
            return
        from karlos_core.controllers.undo_commands import BorrarAnotacionCommand
        self.undo_stack.push(BorrarAnotacionCommand(idx, self.window.table_view))
        self._update_timeline()
        self.window.set_status_message(
            f"{ann.technique} excluída — [Ctrl+Z] desfaz")

    def _preguntar_borrado(self, total: int, paradas: int,
                           titulo: str, texto: str) -> bool | None:
        """Tres salidas: borrar todo, salvar las paradas, o nada.

        Devuelve True (conservar paradas), False (borrar todo) o None
        (cancelar). Separado del borrado para poder probar las dos ramas
        sin abrir el dialogo.
        """
        caja = QMessageBox(self.window)
        caja.setWindowTitle(titulo)
        caja.setIcon(QMessageBox.Icon.Warning)
        caja.setText(texto)
        t = self._i18n.t
        cola = t("dialog.apagar_cola")
        caja.setInformativeText(
            t("dialog.apagar_paradas_info", n=str(paradas), cola=cola) if paradas else cola)
        b_todo = caja.addButton(t("dialog.apagar_tudo"),
                                QMessageBox.ButtonRole.DestructiveRole)
        b_paradas = (caja.addButton(t("dialog.manter_paradas"),
                                    QMessageBox.ButtonRole.AcceptRole)
                     if paradas else None)
        b_no = caja.addButton(t("dialog.cancelar"), QMessageBox.ButtonRole.RejectRole)
        caja.setDefaultButton(b_no)
        caja.exec()
        pulsado = caja.clickedButton()
        if pulsado is b_no or pulsado is None:
            return None
        return pulsado is b_paradas

    def _limpiar_registro(self, conservar_paradas: bool | None = None) -> int:
        """Tirar todo lo anotado del combate abierto. Devuelve cuantas quito.

        Con [Ctrl+Z] vuelve: una pasada entera es mucho que perder por un
        clic, aunque el dialogo ya avise.
        """
        registros = self.window.table_view.records
        total = len(registros)
        if total == 0:
            self.window.set_status_message(self._i18n.t("stat.nada_que_apagar"))
            return 0
        paradas = sum(1 for r in registros
                      if getattr(r, "category", "") == "REFEREE STOP")
        if conservar_paradas is None:
            conservar_paradas = self._preguntar_borrado(
                total, paradas, self._i18n.t("dialog.apagar_titulo"),
                self._i18n.t("dialog.apagar_pregunta_combate", n=str(total)))
            if conservar_paradas is None:
                return 0
        from karlos_core.controllers.undo_commands import BorrarTodoCommand
        self.undo_stack.push(
            BorrarTodoCommand(self.window.table_view, bool(conservar_paradas)))
        quedan = len(self.window.table_view.records)
        self.state_machine.reset()
        # Borrar todo es empezar de nuevo: tambien las pasadas. Si no, la
        # [F] siguiente seguia en la segunda.
        self.fight_controller.reiniciar()
        self._update_timeline()
        self._update_live_stats()
        self._save_session()
        self.window.set_status_message(
            self._i18n.t("stat.apagadas", n=str(total - quedan))
            + (self._i18n.t("stat.paradas_mantidas", n=str(quedan)) if conservar_paradas else ""))
        return total - quedan

    def _refrescar_log(self) -> None:
        """Volcar los registros al log breve del panel de tecnicas."""
        # En la pasada de fases, solo el atleta que se anota: cada luchador
        # por separado, y el otro no se mezcla en lo que se está haciendo.
        # En karate las fases son del combate (decisión 0008): no hay atleta
        # que filtrar, y filtrar por el elegido escondía TODAS las fases
        # (el registro decía «6» y no enseñaba ninguna).
        from karlos_core.tiempo_movimiento import fases_por_atleta
        solo = (self.window.annotation_panel.athlete
                if getattr(self, "_en_modo_fases", lambda: False)() and fases_por_atleta()
                else None)
        self.window.log_compacto.set_registros(
            self.window.table_view.records, self.video_manager.fps, solo_atleta=solo)

    def _ir_a_registro(self, idx: int) -> None:
        """Pulsar una entrada del log lleva el video a su inicio."""
        registros = self.window.table_view.records
        if 0 <= idx < len(registros):
            self.video_manager.goto(int(registros[idx].f_start))

    def _etiqueta_corta(self, registro) -> str:
        """La abreviatura de la técnica, que es lo que cabe en la lupa."""
        nombre = getattr(registro, "technique", "") or ""
        for t in self._config.techniques:
            if t.name == nombre:
                return t.abbr or nombre[:3].upper()
        return nombre[:3].upper()

    def _marcar_inicio(self) -> None:
        """[D] — marcar el inicio y empezar ya las preguntas.

        Se pregunta desde el principio y no al final a proposito: asi se
        puede seguir moviendo el video mientras se contesta, que es como
        se distingue una finta de un ataque. La anotacion no se crea hasta
        que esten las dos cosas — las respuestas y el final.
        """
        if self._en_modo_fases():
            # En la pasada de fases [I] es «empieza el intercambio»: la
            # misma tecla que en las acciones, con el mismo gesto.
            self._marcar_fase("fighting")
            return
        if self._hay_accion_sin_fin("I"):
            return
        self.flow_controller.on_mark_start()
        self._actualizar_zoom()
        if self._en_modo_pro() and self.state_machine.can_select_technique():
            self._arbol_listo = None
            self._abrir_guia()

    def _hay_accion_sin_fin(self, tecla: str) -> bool:
        """Una accion contestada espera su [O]: avisar antes de perderla.

        Una [I] nueva la tiraba sin decir nada. Johan lo vio con dos
        faltas (28-09): la de contacto excesivo va dentro del ataque y
        el ataque necesita su final, pero la otra —pasividad, jogai— es
        un suceso y se guarda al contestar. Tras la primera paso a la
        segunda sin [O], la [I] descarto el ataque con su falta, y en
        los cuadros quedo una sola.

        La primera vez se avisa y no se hace nada: la accion sigue
        esperando. Si se repite la misma tecla, se descarta a sabiendas.
        Devuelve True cuando quien llama tiene que pararse.
        """
        if self._en_modo_pro():
            pendiente = getattr(self, "_arbol_listo", None)
            if pendiente is None:
                return False
            quien = id(pendiente)
            descripcion = self._describir_pendiente(pendiente)
        else:
            sm = self.state_machine
            if sm.state != AnnotationState.TECHNIQUE_SELECTED:
                return False
            pendiente = None
            quien = (sm.f_start, sm.pending_technique)
            descripcion = self._describir_pendiente_clasico()
        if getattr(self, "_aviso_sin_fin", None) == (tecla, quien):
            self._arbol_listo = None
            self._aviso_sin_fin = None
            self.window.guided_panel.ocultar()
            self.state_machine.reset()
            if pendiente is None:
                self.video_manager.clear_annotation_markers()
                self.window.set_pending_text("")
            self.window.set_status_message(I18n().t("pro.descartada", descripcion=descripcion))
            return False
        # La tecla y lo que esta pendiente: si entretanto se elige otra
        # tecnica, el aviso vuelve a empezar en vez de descartarla a ciegas.
        self._aviso_sin_fin = (tecla, quien)
        aviso = I18n().t("pro.aviso_sin_fin", tecla=tecla)
        if pendiente is not None:
            self._mostrar_espera_de_fin(pendiente, aviso)
        else:
            self.window.set_pending_text(I18n().t("pro.pendiente_sin_fin", descripcion=descripcion))
        self.window.set_status_message(
            I18n().t("pro.estado_sin_fin", descripcion=descripcion, tecla=tecla))
        return True

    def _describir_pendiente_clasico(self) -> str:
        """La tecnica elegida en el modo clasico, sin la cadena de niveles."""
        sm = self.state_machine
        if sm.is_referee_stop:
            return sm.pending_technique or self._i18n.t("pro.parada_arbitro")
        tecnica = getattr(self.flow_controller, "_last_technique", None)
        return getattr(tecnica, "name", "") or sm.pending_technique or self._i18n.t("pro.acao")

    @staticmethod
    def _describir_pendiente(arbol) -> str:
        """Lo contestado, en corto: la tecnica y la falta si la hay."""
        respuestas = [r for r in arbol.respuestas() if r]
        tecnica = respuestas[1] if len(respuestas) > 1 else (
            respuestas[0] if respuestas else I18n().t("pro.acao"))
        if arbol.falta:
            return f"{tecnica} (falta: {respuestas[-1]})"
        return tecnica

    def _mostrar_espera_de_fin(self, arbol, aviso: str = "") -> None:
        sm = self.state_machine
        inicio = (I18n().t("pro.espera_desde", frame=str(sm.f_start))
                  if sm.f_start is not None else "")
        self.window.guided_panel.mostrar_espera(
            I18n().t("pro.espera_titulo",
                     atleta=catalogo.etiqueta(self.window.annotation_panel.athlete), inicio=inicio),
            arbol.respuestas(),
            I18n().t("pro.espera_pista"),
            aviso)

    def _marcar_fin(self) -> None:
        """[O] — marcar el final de la accion.

        Las preguntas se contestan entre [I] y [O], o despues de [O]. La
        maquina de estados exige la tecnica antes del fin, asi que aqui se
        retiene el frame final y se crea la anotacion al terminar las
        preguntas.
        """
        if self._en_modo_fases():
            # Y [O] es «acabó el intercambio»: non-fighting desde aquí.
            self._marcar_fase("non_fighting")
            return
        if self._modo_eventos():
            # Técnico-táctico (Johan, 8-10-2026): «solo cuenta el número de
            # ataques, no necesariamente incluye los tiempos; no es
            # necesario colocar inicio y final». Un [O] a medias de las
            # preguntas retenía el fin y la fila salía con duración.
            self.window.set_status_message(I18n().t("tm.evento_sin_fin"))
            return
        if self._en_modo_pro() and self.state_machine.can_select_technique():
            fin = self.video_manager.current_frame
            if fin <= self.state_machine.f_start:
                self.window.set_status_message(I18n().t(
                    "pro.fin_antes_inicio", fin=str(fin), inicio=str(self.state_machine.f_start)))
                return
            self._pro_fin = fin
            self._actualizar_zoom()
            pendiente = getattr(self, "_arbol_listo", None)
            if pendiente is not None:
                self._arbol_listo = None
                self._aviso_sin_fin = None
                self._cerrar_guia(pendiente)
                return
            if getattr(self, "_arbol", None) is None:
                self._abrir_guia()
            return
        if self._en_modo_pro():
            self.window.set_status_message(I18n().t("pro.marque_inicio"))
            return
        self._aviso_sin_fin = None
        self.flow_controller.on_mark_end()

    def _dividir_aqui(self) -> None:
        """[S] — cerrar la accion en curso y empezar otra en el mismo frame.

        En una combinacion real las acciones son contiguas (finta + tecnica,
        o dos golpes encadenados): esto las separa sin dejar hueco.
        """
        if not self.state_machine.can_mark_end():
            self.window.set_status_message(
                self._i18n.t("stat.dividir_tecnica"))
            return
        frame = self.video_manager.current_frame
        self.flow_controller.on_mark_end()
        self.video_manager.goto(frame)
        self.flow_controller.on_mark_start()
        self._actualizar_zoom()
        self.window.set_status_message(
            self._i18n.t("stat.dividido", frame=str(frame)))

    def _detener_bucle(self) -> None:
        """Parar la reproduccion."""
        if self.video_manager.is_playing:
            self.video_manager.toggle_play()

    def _set_selected_frame(self, which: str) -> None:
        """Fijar f_start o f_end del registro seleccionado al frame actual.

        Una anotacion con frames aproximados se corrige navegando cuadro a
        cuadro y pulsando Shift+I / Shift+O, sin abrir ningun dialogo.
        """
        table = self.window.table_view
        idx = table.selected_record_index()
        if idx < 0:
            self.window.set_status_message(
                self._i18n.t("stat.selecione_anotacao"))
            return
        ann = table.records[idx]
        frame = self.video_manager.current_frame
        f_start = frame if which == "start" else ann.f_start
        f_end = frame if which == "end" else ann.f_end
        if f_end <= f_start:
            self.window.set_status_message(
                f"Frame inválido: o fim ({f_end}) tem de ser maior que o início ({f_start})")
            return
        fps = self.video_manager.fps or 30.0
        # Una parada son DOS filas, una por atleta. Corregir solo la
        # seleccionada las separa, y entonces cuentan como dos paradas
        # distintas: la navegacion por intercambios pararia dos veces en
        # la misma y el tiempo muerto saldria doble.
        pareja = []
        if getattr(ann, "category", "") == "REFEREE STOP":
            antes = int(ann.f_start)
            pareja = [i for i, a in enumerate(table.records)
                      if i != idx
                      and getattr(a, "category", "") == "REFEREE STOP"
                      and abs(int(a.f_start) - antes) < 30]
        ann.f_start, ann.f_end = f_start, f_end
        ann.duration_s = (f_end - f_start) / fps
        table.replace_record(idx, ann)
        for j in pareja:
            otra = table.records[j]
            if which == "start":
                otra.f_start = f_start
            else:
                otra.f_end = f_end
            if otra.f_end > otra.f_start:
                otra.duration_s = (int(otra.f_end) - int(otra.f_start)) / fps
                table.replace_record(j, otra)
        if 0 <= self.active_session_idx < len(self.sessions):
            self.sessions[self.active_session_idx].annotations = list(table.records)
        self._schedule_save()
        self._update_timeline()
        etiqueta = self._i18n.t("stat.etiqueta_inicio" if which == "start" else "stat.etiqueta_fim")
        self.window.set_status_message(
            self._i18n.t("stat.anotacao_fixada", n=str(idx + 1), etiqueta=etiqueta,
                         frame=str(frame), dur=f"{ann.duration_s:.2f}"))

    def _on_edit_annotation(self, row_idx: int) -> None:
        records = self.window.table_view.records
        if row_idx < 0 or row_idx >= len(records): return
        annotation = records[row_idx]
        if getattr(annotation, "category", "") == "PHASE":
            self.window.set_status_message(
                "As fases marcam-se com as teclas (1, 2, 3); Shift+C retira a última.")
            return
        popup = EditAnnotationPopup(annotation=annotation, config=self._config, colors=self._colors, sport_id=self._sport_meta.get("id", "karate"), fps=self.video_manager.fps, parent=self.window)
        if popup.exec() == EditAnnotationPopup.Accepted and popup.edited is not None:
            if not popup.edited.sport_specific_data and annotation.sport_specific_data:
                object.__setattr__(popup.edited, 'sport_specific_data', dict(annotation.sport_specific_data))
            self.window.table_view.replace_record(row_idx, popup.edited)
            if 0 <= self.active_session_idx < len(self.sessions):
                self.sessions[self.active_session_idx].annotations = list(records)
            # Editar atleta o categoria puede mover peldaños de la escalera.
            self.foul_controller.resincronizar()
            self._schedule_save()
            self._update_timeline()
            # El marcador de abajo cuenta lo que queda POR DETRAS del
            # video, para poder contrastarlo con el marcador que se ve
            # en la imagen. Si se edita una accion estando el video
            # antes de ella —lo normal: se rebobina para revisarla y
            # luego se corrige— el punto recien puesto cae por delante
            # y el marcador no se movia. Parecia que la edicion no habia
            # entrado. Se lleva el video a la accion editada, que ademas
            # es donde uno quiere estar despues de tocarla.
            self.video_manager.goto(int(popup.edited.f_start))
            self._update_live_stats()
            self.window.set_status_message(self._i18n.t("stat.anotacao_atualizada", n=str(row_idx + 1), tecnica=str(popup.edited.technique), atleta=str(popup.edited.athlete)))

    def _on_frame_changed(self, frame_idx: int) -> None:
        # La fase que rige cambia con el fotograma: el rótulo la sigue. Solo
        # cuando hay fases marcadas; si no, no hay nada que repintar.
        fases = getattr(self, "_fases", None)
        if fases is not None and not fases.vacias:
            self._sync_round_label()
        self._refrescar_panel_fases()
        self._update_live_stats()
        vm = self.video_manager; vp = self.window.video_panel; sm = self.state_machine
        recording = sm.state in (AnnotationState.STARTED, AnnotationState.TECHNIQUE_SELECTED)
        athlete = self.window.annotation_panel.athlete
        start_frame = sm.f_start if recording else 0
        vp.set_hud_state(recording, athlete, start_frame)
        if vm.current_bgr is not None: vp.update_frame_display(vm.current_bgr, frame_idx)
        vp.update_info_label(frame_idx, vm.total_frames, vm.fps)
        vp.update_slider(frame_idx, vm.total_frames)
        vp.timeline.set_position(frame_idx)
        vp.set_zoom_frame(frame_idx)
        vp.set_zoom_marcas(
            self.state_machine.f_start,
            getattr(self, "_pro_fin", None) or vm.ann_end)
        vp.update_marks_label(vm.ann_start, vm.ann_end)
        vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
        vp.update_fight_timer(frame_idx, vm.fight_start, vm.fps)

    def _on_video_loaded(self) -> None:
        vm = self.video_manager; vp = self.window.video_panel
        vp.update_info_label(0, vm.total_frames, vm.fps)
        vp.update_slider(0, vm.total_frames)
        vp.update_marks_label(vm.ann_start, vm.ann_end)
        vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
        self._actualizar_zoom()
        if vm.current_bgr is not None: vp.update_frame_display(vm.current_bgr)
        self._sync_ui_to_state()
        # Las pasadas son de cada combate: sin esto el siguiente video
        # heredaba las del anterior. La sesion guardada repone las suyas.
        self.fight_controller.reiniciar()
        self._nuevos_asaltos()
        self._restore_session_from_active_round()
        self._sync_corner_colors()
        self._sync_round_label()
        self._aplicar_analisis()
        self._pintar_linea_del_atleta()

    def _on_video_error(self, message: str) -> None:
        QMessageBox.critical(self.window, self._i18n.t("dialog.video_error"), message)

    def _on_mark_start_with_ui(self) -> None:
        """Los botones INÍCIO y FIM van por donde van las teclas.

        Iban por `flow_controller` directamente: eso delimitaba el corte y
        NO abria el arbol, y daba una anotacion sin guardia, sin nivel y
        sin contexto tactico, sin avisar de que faltaban.

        Que una tecla y el boton que anuncia esa misma tecla hagan cosas
        distintas es una trampa, porque el que la pisa no tiene forma de
        notarlo.
        """
        self._marcar_inicio()
        self._sync_ui_to_state()

    def _on_mark_end_with_ui(self) -> None:
        self._marcar_fin()
        self._sync_ui_to_state()
    def _on_fight_start_with_ui(self) -> None: self.fight_controller.on_fight_start(); self._sync_ui_to_state()

    def _sync_ui_to_state(self) -> None:
        i18n = self._i18n; c = self._colors; vm = self.video_manager; sm = self.state_machine; win = self.window
        fight_active = vm.fight_start is not None and vm.fight_end is None and vm.is_loaded
        win.video_panel.set_recording_indicator(fight_active)
        if fight_active: win.set_status_state(c.green, i18n.t("stat.fight_active"))
        elif sm.state == AnnotationState.IDLE: win.set_status_state(c.muted, i18n.t("stat.ready"))
        elif sm.state == AnnotationState.STARTED: win.set_status_state(c.green, i18n.t("stat.start_marked"))
        elif sm.state == AnnotationState.TECHNIQUE_SELECTED: win.set_status_state(c.accent, i18n.t("stat.tech_selected"))
        else: win.set_status_state(c.muted, "")

    def _update_timeline(self) -> None:
        records = self.window.table_view.records
        total = max(self.video_manager.total_frames, 1)
        self.window.video_panel.timeline.set_data(list(records), total)
        # Los asaltos, con su número: dónde empieza y acaba cada uno.
        asaltos = getattr(self, "_asaltos", None)
        poner = getattr(self.window.video_panel.timeline, "set_asaltos", None)
        if poner is not None:
            poner([(n, asaltos.inicio(n), asaltos.fin(n))
                   for n in range(1, asaltos.total + 1) if asaltos.inicio(n) is not None]
                  if asaltos is not None else [])
        self.window.video_panel.timeline.set_fases(self._intervalos_de_fase(),
                                                   fuerte=self._en_modo_fases())
        # La lupa dibuja lo ya anotado, así que cambia con la tabla:
        # crear, borrar, deshacer y editar pasan todos por aquí.
        if self._video_path:
            self.window.video_panel.set_zoom_anotadas(
                self._tramos_anotados(self.window.annotation_panel.athlete))

    def _sync_corner_colors(self) -> None:
        color_a = self._bout_info.get("athlete_a_color", self._colors.aka)
        color_b = self._bout_info.get("athlete_b_color", self._colors.ao)
        # Sin esquina elegida, los colores son los de las esquinas del deporte:
        # así se corrigen los combates de taekwondo guardados con Chung en
        # rojo (el defecto del karate). En el karate da lo mismo que antes.
        if "athlete_a_color" in self._bout_info and not self._bout_info.get("athlete_a_corner"):
            from karlos_core.views.bout_info_popup import colores_de_esquinas
            color_a, color_b = colores_de_esquinas(self._bout_info, self._sport_meta.get("id", "karate"))
            self._bout_info["athlete_a_color"], self._bout_info["athlete_b_color"] = color_a, color_b
        name_a = self._bout_info.get("athlete_a_corner", "")
        name_b = self._bout_info.get("athlete_b_corner", "")
        self.window.annotation_panel.set_corner_colors(color_a, color_b, name_a, name_b)
        self.window.video_panel.set_corner_colors(color_a, color_b)
        self.window.table_view.set_corner_colors(color_a, color_b, name_a, name_b)
        self.window.video_panel.timeline.set_corner_colors(color_a, color_b)

    # ── Los asaltos del combate ─────────────────────────────────────
    #
    # Donde el deporte tiene más de uno, el evaluador marca con [F] dónde
    # empieza cada asalto y con [G] dónde acaba. Las marcas son del vídeo:
    # se guardan con la sesión, no se borran al cambiar de atleta y no hay
    # que volver a ponerlas (Johan, 7-10-2026).

    def _total_de_asaltos(self) -> int:
        """Cuántos asaltos tiene ESTE combate: los de sus datos («Number of
        Rounds»), o los del reglamento. el especialista, 12-10-2026: «¿se puede
        elegir 2 para que reconozca dos asaltos en vez de tres?». La ventana
        lo guardaba y el programa no lo miraba."""
        regla = int(catalogo.activo().reglamento.asaltos)
        if regla <= 1:
            return regla
        try:
            n = int(str((getattr(self, "_bout_info", None) or {}).get("num_rounds", "") or 0))
        except ValueError:
            n = 0
        return n if 1 <= n <= 9 else regla

    def _nuevos_asaltos(self) -> None:
        """Los asaltos vacíos del deporte, al abrir un vídeo. Y las fases
        vacías, que van con el vídeo igual que ellos."""
        from karlos_core.models.asaltos import Asaltos
        hay_asaltos = catalogo.activo().reglamento.asaltos > 1
        self._asaltos = Asaltos(total=self._total_de_asaltos()) if hay_asaltos else None
        self._asaltos_por_atleta = {}
        self._asaltos_del_combate = None
        self._atleta_de_asaltos = None
        self._migrar_asaltos = False
        self._nuevas_fases()
        self._enganchar_asaltos()

    def _reponer_asaltos(self, filas, por_atleta=None) -> None:
        """Lo que la sesión guardada traía marcado: los asaltos del combate
        y, en el tiempo-movimiento, los de cada atleta."""
        if getattr(self, "_asaltos", None) is None:
            return
        from karlos_core.models.asaltos import Asaltos
        total = self._total_de_asaltos()
        self._asaltos = Asaltos.de_lista(filas, total)
        self._asaltos_del_combate = Asaltos.de_lista(filas, total)
        self._asaltos_por_atleta = {str(k): Asaltos.de_lista(v, total)
                                    for k, v in (por_atleta or {}).items()}
        self._atleta_de_asaltos = None
        # Una sesión de antes no traía los de cada atleta: los dos parten de
        # los del combate que tenía.
        self._migrar_asaltos = not por_atleta and bool(filas)
        self._enganchar_asaltos()
        vm = self.video_manager
        if self._asaltos.inicio_del_combate is not None:
            vm.fight_start = self._asaltos.inicio_del_combate
        if self._asaltos.fin_del_combate is not None:
            vm.fight_end = self._asaltos.fin_del_combate

    def _enganchar_asaltos(self) -> None:
        """Quien tiene que saber de ellos: el combate y las anotaciones."""
        self.fight_controller.poner_asaltos(self._asaltos)
        asaltos = self._asaltos
        self.flow_controller.asalto_de = (
            (lambda f: asaltos.de_fotograma(f)) if asaltos is not None else None)
        self._sync_round_label()

    def _al_marcar_asalto(self, n: int, que: str) -> None:
        """Decir qué quedó marcado, y dejarlo guardado."""
        a = self._asaltos
        if a is None:
            return
        if que == "completos":
            # F o G con todos los asaltos cerrados y el vídeo fuera de ellos.
            estricto = bool(getattr(self.fight_controller, "estricto", lambda: False)())
            self.window.set_status_message(I18n().t(
                "tm.asaltos_completos", total=str(a.total),
                atleta=catalogo.etiqueta(self.window.annotation_panel.athlete),
                pista=I18n().t("tm.pista_corregir_pastilla" if estricto else "tm.pista_corregir_dentro")))
            return
        if que == "fin" and getattr(self, "_en_modo_fases", lambda: False)():
            # La última fase acaba con el asalto: así el total de cada
            # asalto es la suma de sus fases, como en la hoja del especialista, y
            # ninguna fase cruza el descanso.
            self._ajustar_ultima_fase_al_fin(n)
        # Corregido un asalto elegido, se suelta: lo siguiente vuelve a ser
        # abrir o cerrar en orden.
        if getattr(self.fight_controller, "asalto_elegido", 0) == n and que in ("inicio", "fin"):
            self._refrescar_panel_fases()
        sincronizar = getattr(self, "_sincronizar_fases", None)
        if sincronizar is not None:
            sincronizar()
        self._sync_round_label()
        self._update_timeline()
        self._schedule_save()
        self._update_timeline()
        if que == "inicio":
            self.window.set_status_message(I18n().t(
                "pro.asalto_inicio", n=str(n), resumen=a.resumen(self.video_manager.fps)))
        elif a.marcados < a.total:
            self.window.set_status_message(I18n().t(
                "pro.asalto_cerrado", n=str(n), siguiente=str(n + 1),
                resumen=a.resumen(self.video_manager.fps)))

    def _avisar_sin_inicio(self, n: int) -> None:
        self.window.set_status_message(I18n().t("pro.asalto_sin_inicio", n=str(n)))

    def _sync_round_label(self) -> None:
        """El asalto en curso, donde el deporte tiene más de uno, y la fase
        del tiempo-movimiento que rige en el fotograma, si se marcan."""
        asaltos = getattr(self, "_asaltos", None)
        if asaltos is None:
            self.window.video_panel.set_round_label(0, 0)
            return
        self.window.video_panel.set_round_label(
            asaltos.en_curso, asaltos.total, fase=self._fase_en_curso())
        # Las pastillas de asalto del panel de fases van con esto: marcar
        # un inicio o un fin se tiene que ver en el acto.
        self._refrescar_panel_fases()

    def _repintar_franja(self) -> None:
        """Volver a escribir la fila de abajo con el formato del modo."""
        vm, vp = self.video_manager, self.window.video_panel
        self._update_live_stats()
        vp.update_info_label(vm.current_frame, vm.total_frames, vm.fps)
        vp.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
        vp.update_marks_label(vm.ann_start, vm.ann_end)
        vp.set_pass_label(self.fight_controller.current_pass,
                          self.window.annotation_panel.athlete)

    def _update_live_stats(self) -> None:
        """El marcador y las faltas, tal como estarian AHI.

        No el total del combate: lo que cada atleta lleva en el punto
        donde esta el video, que es lo que muestra el marcador de la
        pantalla y lo que hace falta para decidir el grado de la
        siguiente falta — el grado no se elige, sale del contador.

        Las faltas se cuentan desde las anotaciones y no desde el
        contador del controlador de faltas: asi deshacer un borrado o
        editar una accion las deja bien sin avisar a nadie, y coinciden
        siempre con el CSV porque la regla es la misma.
        """
        records = self.window.table_view.records
        f = int(self.video_manager.current_frame)
        hasta_aqui = [r for r in records if int(r.f_start) <= f]
        self.window.video_panel.update_faltas(*sanciones_por_competidor(hasta_aqui))
        puntos = catalogo.activo().reglamento.puntos
        aka_score = sum(puntos(r.score) for r in hasta_aqui if r.athlete == "AKA")
        ao_score = sum(puntos(r.score) for r in hasta_aqui if r.athlete == "AO")
        elapsed = f / max(self.video_manager.fps, 1.0)
        self.window.video_panel.update_live_stats(
            aka_score, ao_score, len(records), elapsed)

    def _on_annotation_created(self, annotation) -> None:
        self._schedule_save(); self._sync_ui_to_state()
        if 0 <= self.active_session_idx < len(self.sessions):
            self.sessions[self.active_session_idx].annotations = list(self.window.table_view.records)
        self._update_timeline(); self._update_live_stats()

    def _toggle_focus_mode(self) -> None:
        self._focus_mode = not self._focus_mode
        self.window.animate_focus_mode(self._focus_mode)
        if self._focus_mode: self.window.set_status_message(self._i18n.t("stat.focus_mode"))
        else: self.window.set_status_message(self._i18n.t("stat.focus_off"))
