"""El árbol de preguntas del modo asistido: abrirlo, pintarlo, elegir y
cerrarlo.

Parte del controlador principal (``annotation_controller``), separada en la
fase F3.7.
"""

from __future__ import annotations

from karlos_core import catalogo
from karlos_core.utils.i18n import I18n


class GuiaMixin:
    """El árbol de preguntas del modo asistido: abrirlo, pintarlo, elegir y
    cerrarlo."""

    # ------------------------------------------------------------------
    # Etiquetado guiado
    # ------------------------------------------------------------------

    def _abrir_guia(self) -> None:
        """Arrancar el recorrido de preguntas para la accion marcada.

        El arbol es del deporte que se anota (decision 0004); si no tiene,
        no hay guia.
        """
        self._arbol = catalogo.activo().arbol()
        self._pintar_guia()

    def _pintar_guia(self) -> None:
        panel = self.window.guided_panel
        arbol = getattr(self, "_arbol", None)
        if arbol is None:
            panel.ocultar()
            return
        paso = arbol.paso_actual()
        if paso is None:
            panel.ocultar()
            return
        n, total = arbol.profundidad()
        cabecera = self._i18n.t("guia.accion")
        panel.mostrar_paso(paso.pregunta, paso.opciones, n, total, cabecera,
                           arbol.respuestas(), paso.grupos)

    def _guia_tecla(self, tecla: str) -> bool:
        """Consumir una tecla numerica si hay un recorrido abierto.

        Devuelve True si la tecla se uso aqui, para que no llegue tambien
        al atajo de tecnica del panel lateral.
        """
        # En la pasada de fases los numeros son las fases (1, 2, 3), en
        # los dos modos: no hay arbol abierto ni tecnica que disparar.
        if tecla.isdigit() and self._en_modo_fases():
            return self._tecla_de_fase(tecla)
        if not self._en_modo_pro() or not tecla.isdigit():
            return False
        arbol = getattr(self, "_arbol", None)
        if arbol is None:
            if not self._modo_eventos():
                return False
            # Tecnico-tactico: la accion es un evento. Un numero sin accion
            # abierta la abre aqui mismo y contesta la primera pregunta:
            # una tecla menos por accion, y el fotograma queda registrado.
            self._marcar_inicio()
            arbol = getattr(self, "_arbol", None)
            if arbol is None:
                return False
        clave = self.window.guided_panel.clave_de(int(tecla))
        if clave is None:
            return False
        self._guia_elegir(clave)
        return True

    def _pedir_motivo_escrito(self) -> bool:
        """Preguntar por que no se identifica, cuando no es de la lista.

        Lo tecleado va al campo de notas, que es de donde sale la columna
        `notes` del registro: el motivo escrito es una nota del evaluador
        sobre esa accion, no una variable aparte.
        """
        from PySide6.QtWidgets import QInputDialog
        texto, vale = QInputDialog.getText(
            self.window, I18n().t("pro.no_ident_titulo"), I18n().t("pro.no_ident_pregunta"))
        texto = (texto or "").strip()
        if not vale or not texto:
            return False
        self.window.annotation_panel.set_notes(texto)
        return True

    def _guia_elegir(self, clave: str) -> None:
        """Avanzar el recorrido, venga de una tecla o de un clic."""
        arbol = getattr(self, "_arbol", None)
        if arbol is None or not self._en_modo_pro():
            return
        arbol.elegir(clave)

        if arbol.descartada:
            self._arbol = None
            self.window.guided_panel.ocultar()
            self.window.set_status_message("Segmento descartado")
            self._ir_a_anotacion(1)
            return

        if arbol.completa:
            self._cerrar_guia(arbol)
            return
        self._pintar_guia()

    def _cerrar_guia(self, arbol) -> None:
        """Guardar lo contestado y crear la anotacion si ya hay final."""
        if arbol.pide_motivo_escrito and not self._pedir_motivo_escrito():
            # Se arrepintio de escribirlo: vuelve a la lista de motivos
            # en vez de guardar un «otro» sin decir cual, que no serviria
            # de nada cuando haya que contar por que se pierde imagen.
            arbol.retroceder()
            self._pintar_guia()
            return
        if arbol.es_falta:
            # La falta no necesita inicio ni final: es un suceso, no una
            # accion tecnica. El grado sale del contador del atleta —
            # CHUI-1, 2, 3, HANSOKU-CHUI, HANSOKU — y no se elige.
            #
            # Se registra en el momento de la CONDUCTA, no en el de la
            # sancion. El arbitro para unos segundos despues, y anotar ahi
            # movaria el dato al momento de la decision en vez del de lo
            # que se estudia. Si hay un inicio marcado con [I] se usa ese;
            # si no, donde este el video.
            sm = self.state_machine
            volver = None
            destino = None
            if sm.can_select_technique() and sm.f_start:
                destino = int(sm.f_start)
            if destino is not None:
                volver = self.video_manager.current_frame
                self.video_manager.goto(destino)
            if not self._confirmar_falta_tras_hansoku():
                if volver is not None:
                    self.video_manager.goto(volver)
                self._arbol = None
                self.window.guided_panel.ocultar()
                return
            self.foul_controller.register_foul(arbol.falta_tipo or "Conduct")
            if volver is not None:
                self.video_manager.goto(volver)
                sm.reset()
            self._arbol = None
            self.window.guided_panel.ocultar()
            self._ir_a_anotacion(1)
            return
        tecnica, nivel, categoria, grupo = arbol.resultado()
        # Si el video esta dentro de una parada ya anotada (la de la pasada
        # del otro atleta), lo que falta es de que tipo fue: se escribe
        # encima de la que hay en vez de crear otra.
        if categoria == "REFEREE STOP" and self._calificar_parada(tecnica):
            self._arbol = None
            self.window.guided_panel.ocultar()
            return
        sm = self.state_machine
        if not sm.can_select_technique():
            self.window.set_status_message(I18n().t("pro.sin_inicio"))
            return
        if getattr(self, "_pro_fin", None) is None and self._modo_eventos():
            # Tecnico-tactico: la accion es un evento. Johan, 16-10-2026:
            # «solo debe contar la frecuencia; deja registrado el frame en
            # que se anoto, pero no hay frame de entrada ni de salida».
            #
            # Hasta hoy se cerraba un fotograma DESPUES del inicio, «el
            # minimo que admite la maquina», y eso dejaba en cada fila una
            # duracion de 0,03 s que no significa nada. Ahora la fila
            # empieza y acaba en el mismo fotograma —el del instante
            # anotado— y la duracion queda AUSENTE, que es lo honesto
            # cuando no se han marcado los extremos (decision 0008).
            self._pro_fin = int(sm.f_start)
            self.flow_controller.evento = True
        if getattr(self, "_pro_fin", None) is None:
            # Contestado antes de marcar el final: se retiene y se crea en
            # cuanto se pulse [O], sin volver a preguntar nada. El panel
            # se queda a la vista diciendo que falta el final: si se
            # cerraba, el unico recuerdo era la barra de estado.
            self._arbol_listo = arbol
            self._aviso_sin_fin = None
            self._arbol = None
            self._mostrar_espera_de_fin(arbol)
            self.window.set_status_message(I18n().t("pro.ir_al_fin", tecnica=tecnica))
            return
        # Una parada nueva la crea el mismo codigo que la ventana de paradas,
        # venga del arbol o del boton. Los arboles que no dicen el tipo de
        # parada siguen por el camino de siempre.
        tipo_parada = getattr(arbol, "tipo_de_parada", "")
        if categoria == "REFEREE STOP" and tipo_parada:
            if not self.flow_controller.preparar_parada(tipo_parada):
                return
            self._arbol = None
            self.window.guided_panel.ocultar()
            self.video_manager.goto(int(self._pro_fin))
            self._pro_fin = None
            self.flow_controller.on_mark_end()
            self.window.set_status_message(
                I18n().t("pro.anotada", tecnica=tipo_parada, pista=self._pista_siguiente()))
            return
        # Se reutiliza la maquina de estados: la cadena de nivel combinada es
        # la misma que produce la ventana de detalle, asi que el motor
        # combinatorio (Tsuki + Lead -> Kizami Tsuki) sigue funcionando.
        # La puntuacion no se elige: si el ataque puntuo, el valor sale de
        # la tecnica y el nivel segun las reglas WKF del config.
        puntos = "NONE"
        if arbol.puntuo:
            cat = next((c for c in self._config.categories if c.name == grupo), None)
            from karlos_core.models.technique import resolve_combat_action
            resuelta = resolve_combat_action(
                tecnica, arbol.guardia or "", self._config.combinatorial_map)
            puntos = self._config.scoring_engine.calculate_score(
                resuelta, arbol.nivel or "", cat) or "NONE"
            # Aqui la puntuacion subia a IPPON cuando la tecnica llegaba
            # sobre un rival derribado en el segundo y medio anterior
            # (WKF art. 6). Era otra regla de tiempo que miraba filas de
            # al lado, y se retiro el 24-09-2026 con las demas: la
            # puntuacion sale de la tecnica y el nivel, y el resto lo
            # decide el evaluador. El derribo queda anotado en su fila,
            # asi que la subida se puede aplicar en el tratamiento de
            # datos, donde ademas se puede revisar.
        sm.select_technique(tecnica, nivel, puntos, categoria, grupo)
        self._arbol = None
        self.window.guided_panel.ocultar()
        # Se vuelve al frame que marco [F]: responder las preguntas no debe
        # mover el final de la accion.
        fin = getattr(self, "_pro_fin", None)
        if fin is not None:
            self.video_manager.goto(int(fin))
            self._pro_fin = None
        self.flow_controller.on_mark_end()
        # Si el ataque acabo en falta va en UNA sola fila, la del
        # ataque, y esa fila ya suma peldaño por si misma (es_sancion
        # la cuenta): no hay contador que avisar, la cuenta ES la tabla.
        self.window.set_status_message(
            I18n().t("pro.anotada", tecnica=tecnica, pista=self._pista_siguiente()))

    def _pista_siguiente(self) -> str:
        """Como se va a la siguiente accion: con [I], o con un numero en el
        tecnico-tactico."""
        if getattr(self, "_modo_eventos", lambda: False)():
            return I18n().t("tm.pista_eventos")
        return I18n().t("pro.pista_i")

    def _guia_atras(self) -> None:
        arbol = getattr(self, "_arbol", None)
        if arbol is None:
            return
        if not arbol.retroceder():
            self._arbol = None
            self.window.guided_panel.ocultar()
            self.window.set_status_message(I18n().t("pro.cancelado"))
            return
        self._pintar_guia()
