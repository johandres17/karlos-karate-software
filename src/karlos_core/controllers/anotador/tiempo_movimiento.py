"""Las fases del tiempo-movimiento en el anotador: tres análisis, tres
comportamientos (8-10-2026).

- **Técnico-táctico**: el árbol de preguntas; la acción es un evento, sin
  fin que marcar. Las teclas de fase no marcan nada, y lo dicen.
- **Tiempo-movimiento**: los tres botones del especialista —fighting,
  non-fighting, stoppage— y nada más. [1] [2] [3] (o [I] [O] [3]) marcan
  dónde empieza cada fase, y **cada pulsación es una fila del registro**,
  como lo es cada acción en el técnico-táctico: con su fase, su inicio, su
  fin (que lo pone la pulsación siguiente) y su duración. Esa fue la queja
  de Johan la noche del 8-10 («no se crea el histórico, la persona está
  perdida»): las fases vivían en una lista aparte y pulsar un botón no
  dejaba rastro. Ahora las fases son filas (categoría PHASE, sin atleta,
  porque son del combate), con lo que traen las filas: el registro, la
  línea de tiempo, deshacer, la sesión guardada, el CSV y el Excel.
- **Integrado** (``complete``): [I], las preguntas, [O]; los estados del
  tiempo-movimiento se derivan de las acciones.

``self._fases`` (las marcas, ``karlos_core.models.fases.Fases``) se deriva
siempre de las filas PHASE del registro: es la vista que usan el rótulo del
asalto, la línea de tiempo, el informe y el Excel. Solo existe donde el
deporte hace tiempo-movimiento.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


from karlos_core.utils.i18n import I18n

from karlos_core import catalogo

TECNICO_TACTICO = "technical_tactical"
TIEMPO_MOVIMIENTO = "time_motion"
COMPLETO = "complete"
CATEGORIA_FASE = "PHASE"
# Las teclas y los rotulos los dice el deporte (decision 0008): el karate
# tiene cuatro estados y el taekwondo tres. Se piden en cada pulsacion y no
# se cachean, porque el deporte activo cambia dentro de una misma sesion de
# trabajo (y en la suite, entre pruebas).


def _reloj(frame: int, fps: float) -> str:
    s = frame / max(float(fps), 1.0)
    return f"{int(s // 60)}:{s % 60:04.1f}"


class TiempoMovimientoMixin:
    """Lo que el controlador sabe de las fases y del análisis elegido."""

    _modo_fases: bool = False

    # ── Qué se analiza ──────────────────────────────────────────────
    def _hace_tiempo_movimiento(self) -> bool:
        return bool(catalogo.activo().tiempo_movimiento())

    def _analisis_del_combate(self) -> str:
        """El análisis en que se está trabajando.

        Desde el 19-10-2026 cada análisis es un cuaderno aparte del mismo
        vídeo (Johan: «cada modo debería tener su anotación independiente»):
        el análisis no es del combate sino del cuaderno abierto.
        """
        from karlos_core.views.dialogo_analisis import ANALISIS_POSIBLES, analisis_por_defecto
        activo = getattr(self, "_analisis_activo", None)
        return activo if activo in ANALISIS_POSIBLES else analisis_por_defecto()

    def _poner_analisis_activo(self, codigo: str) -> None:
        """Ese análisis pasa a ser el activo: su cuaderno, sus teclas y su
        botón en el Hub."""
        from karlos_core.controllers.session_manager import SessionManager
        if not self._hace_tiempo_movimiento():
            codigo = COMPLETO
        self._analisis_activo = codigo
        SessionManager.poner_cuaderno(codigo)
        hub = getattr(self.window, "project_hub", None)
        if hub is not None and hasattr(hub, "set_analisis"):
            hub.set_analisis(codigo)

    def _cambiar_de_analisis(self, codigo: str) -> bool:
        """Pasar a otro cuaderno, desde el Hub o desde el anotador.

        Lo abierto se guarda en su cuaderno; el Hub se recarga con lo del
        nuevo; y si había un combate abierto se vuelve a abrir, ya con las
        anotaciones de este análisis.
        """
        from karlos_core import identidad
        from karlos_core.views.dialogo_analisis import ANALISIS, ANALISIS_POSIBLES
        if codigo not in ANALISIS_POSIBLES:
            return False
        if codigo == self._analisis_del_combate():
            self._poner_analisis_activo(codigo)
            return True
        abierto = self.active_session_idx if (
            self._video_path and 0 <= self.active_session_idx < len(self.sessions)) else -1
        if self._video_path:
            # Salir al Hub como lo haría el evaluador: guarda en el cuaderno
            # que se deja y VACÍA la tabla. Antes solo se guardaba, y al
            # reabrir un combate sin nada en el cuaderno nuevo la tabla
            # seguía enseñando las anotaciones del otro modo (19-10-2026).
            self._on_back_to_hub()
        identidad.ajustes().setValue(ANALISIS, codigo)
        self._poner_analisis_activo(codigo)
        self._recargar_cuaderno()
        if abierto >= 0:
            self._on_session_selected(abierto)
        self.window.set_status_message(I18n().t(
            "analisis.cuaderno", nome=I18n().t({TIEMPO_MOVIMIENTO: "analisis.tm",
                                                 TECNICO_TACTICO: "analisis.tt"}.get(codigo, "analisis.completo"))))
        return True

    def _en_modo_fases(self) -> bool:
        """Si en este momento las teclas marcan fases y no acciones."""
        return bool(getattr(self, "_modo_fases", False)) and self._hace_tiempo_movimiento()

    def _modo_eventos(self) -> bool:
        """Técnico-táctico: la acción es un evento, sin fin que marcar."""
        return self._hace_tiempo_movimiento() and self._analisis_del_combate() == TECNICO_TACTICO

    # ── Un análisis por combate ─────────────────────────────────────
    # Johan, 8-10-2026 (noche): «no se puede mezclar los tres modos en un
    # mismo análisis; cada lucha se analiza con un modo, y basado en el
    # modo escogido se implementan las anotaciones. No se puede cambiar
    # así de fácil». El análisis se fija en los datos del combate con la
    # primera anotación y no se cambia mientras el combate tenga alguna.
    def _anotaciones_del_combate(self) -> int:
        tabla = getattr(getattr(self, "window", None), "table_view", None)
        return len(getattr(tabla, "records", []) or [])

    def _fijar_analisis(self) -> bool:
        """Con la primera anotación, el análisis queda escrito en los datos
        del combate: a partir de ahí es suyo, no el que se eligió al entrar."""
        if not self._hace_tiempo_movimiento() or not self._anotaciones_del_combate():
            return False
        info = getattr(self, "_bout_info", None)
        analisis = self._analisis_del_combate()
        # El completo no se escribe: es lo que significa no decir nada, y así
        # sus archivos siguen siendo los de siempre (los del estudio, los de
        # la 1.0). Los otros dos sí, para que su archivo diga qué es.
        if info is None or analisis == COMPLETO or info.get("analysis") == analisis:
            return False
        info["analysis"] = analisis
        if 0 <= self.active_session_idx < len(self.sessions):
            self.sessions[self.active_session_idx].bout_metadata = dict(info)
        return True

    def _volver_al_inicio(self) -> None:
        """«‹ Inicio» en el Hub y «Análisis…» en el anotador: de vuelta a la
        pantalla inicial para elegir otro modo (Johan, 19-10-2026).

        Lo abierto se guarda en su cuaderno y se sale al Hub; la pantalla
        inicial pregunta qué se analiza; y el Hub se recarga con el cuaderno
        elegido, que solo tiene lo anotado en ese modo. Cerrarla sin elegir
        deja todo igual.
        """
        if not self._hace_tiempo_movimiento():
            return
        if self._video_path:
            self._on_back_to_hub()
        from karlos_core.views import dialogo_analisis
        analisis = dialogo_analisis.elegir_al_inicio(
            self._colors, parent=self.window, actual=self._analisis_del_combate())
        if analisis is None:
            return
        self._cambiar_de_analisis(analisis)

    # El nombre de antes, por si algo lo llama todavía.
    _abrir_dialogo_analisis = _volver_al_inicio

    def _aplicar_analisis(self) -> None:
        """Al abrir el vídeo y al cambiar los datos del combate: el panel,
        las teclas y el aviso que tocan a este análisis."""
        if not self._hace_tiempo_movimiento():
            return
        analisis = self._analisis_del_combate()
        self._analisis_aplicado = analisis
        # En el tiempo-movimiento, los asaltos que se ven son los del atleta.
        self._poner_asaltos_del_atleta()
        self.fight_controller.asalto_elegido = 0
        if analisis == TIEMPO_MOVIMIENTO:
            self._poner_modo_fases(True)
        else:
            self._poner_modo_fases(False)
        # Técnico-táctico: la acción es un evento y no tiene fin que marcar;
        # el botón FIM se va con él (Johan, 8-10-2026).
        eventos = getattr(self.window.video_panel, "set_modo_eventos", None)
        if eventos is not None:
            eventos(analisis == TECNICO_TACTICO)
        registro = getattr(getattr(self.window, "log_compacto", None), "set_sin_duracion", None)
        if registro is not None:
            registro(analisis == TECNICO_TACTICO)
            self._refrescar_log()
        self._anunciar_analisis()

    def _poner_modo_fases(self, activo: bool) -> None:
        self._modo_fases = bool(activo)
        self.window.mostrar_panel_fases(self._modo_fases)
        poner = getattr(self.window.video_panel, "set_modo_fases", None)
        if poner is not None:
            poner(self._modo_fases)
        self._update_timeline()
        self._refrescar_log()
        # La lupa: unos segundos alrededor del cursor, con las fases del atleta.
        actualizar_lupa = getattr(self, "_actualizar_zoom", None)
        if actualizar_lupa is not None:
            actualizar_lupa()
        if self._modo_fases:
            self._refrescar_panel_fases()

    def _anunciar_analisis(self) -> None:
        """Qué se analiza y con qué teclas, en la barra de estado."""
        if not self._hace_tiempo_movimiento():
            return
        analisis = self._analisis_del_combate()
        if analisis == TIEMPO_MOVIMIENTO:
            clave = "tm.aviso_tm"
        elif analisis == COMPLETO:
            clave = "tm.aviso_completa"
        else:
            clave = "tm.aviso_tt"
        texto = I18n().t(clave)
        # «Fases antiguas» son las de antes del 9-10-2026, sin atleta, en un
        # deporte donde cada atleta marca las suyas. En karate TODAS las
        # fases son sin atleta —son del combate— y no son antiguas.
        from karlos_core.tiempo_movimiento import fases_por_atleta
        antiguas = (len(self._filas_de_fase(""))
                    if analisis != TECNICO_TACTICO and fases_por_atleta() else 0)
        if antiguas:
            texto = I18n().t("tm.fases_antiguas", n=str(antiguas)) + "  " + texto
        self.window.set_status_message(texto)

    # ── Las fases como filas del registro ───────────────────────────
    # Las fases son de cada atleta (el especialista, 9-10-2026: «mientras uno
    # ataca el otro puede estar saltando; el attack time empieza cuando el
    # pie deja el suelo»). Una pasada por competidor, como las acciones:
    # las filas PHASE llevan su atleta, y lo que se ve —el panel, el rótulo,
    # la línea de tiempo— es lo del atleta elegido.
    def _atleta_actual(self) -> str:
        return str(getattr(self.window.annotation_panel, "athlete", "") or "")

    def _atleta_de_fase(self) -> str:
        """De quién son las fases que se marcan ahora: del atleta elegido en
        taekwondo (el especialista: una pasada por competidor), del combate en
        karate ("" — Chaabène et al. 2014: el intercambio es de los dos).
        Decisión 0008."""
        from karlos_core.tiempo_movimiento import fases_por_atleta
        return self._atleta_actual() if fases_por_atleta() else ""

    def _filas_de_fase(self, atleta: Optional[str] = None) -> list[tuple[int, Any]]:
        """(índice, fila) de cada fila PHASE del atleta, en orden."""
        atleta = self._atleta_de_fase() if atleta is None else atleta
        return [(i, r) for i, r in enumerate(self.window.table_view.records)
                if getattr(r, "category", "") == CATEGORIA_FASE
                and str(getattr(r, "athlete", "") or "") == atleta]

    def _fases_a_lista(self) -> Optional[list[dict[str, Any]]]:
        """Las marcas de todos los atletas, con su atleta, para la sesión
        guardada, el informe y el Excel."""
        if not self._hace_tiempo_movimiento():
            return None
        from karlos_core.tiempo_movimiento import separar_fases
        _acciones, marcas = separar_fases(list(self.window.table_view.records))
        return marcas

    # ── Los asaltos de cada atleta ──────────────────────────────────
    # el especialista, 12-10-2026: tras los tres asaltos del atleta azul, al pasar
    # al rojo «no empieza en el Round 1, sino directamente en el Round 3».
    # Los asaltos eran del combate y ya estaban cerrados. En su método
    # (y en su hoja) cada atleta tiene sus asaltos, con sus propios
    # límites: en el tiempo-movimiento cada pasada marca los suyos.
    def _asaltos_por_atleta_activos(self) -> bool:
        from karlos_core.tiempo_movimiento import fases_por_atleta
        return (self._hace_tiempo_movimiento()
                and self._analisis_del_combate() == TIEMPO_MOVIMIENTO
                and fases_por_atleta()
                and getattr(self, "_asaltos", None) is not None)

    def _poner_asaltos_del_atleta(self) -> None:
        """``self._asaltos`` pasa a ser el del atleta elegido. El resto del
        programa (las teclas F y G, el rótulo, la línea de tiempo, el asalto
        de cada fila) sigue usando ``self._asaltos`` y no se entera."""
        if not self._asaltos_por_atleta_activos():
            return
        from karlos_core.models.asaltos import Asaltos
        dic = getattr(self, "_asaltos_por_atleta", None)
        if dic is None:
            dic = self._asaltos_por_atleta = {}
        nuevo = self._atleta_actual()
        previo = getattr(self, "_atleta_de_asaltos", None)
        if previo == nuevo:
            return
        if previo is None:
            # La primera vez, lo que ya hay marcado es de este atleta, salvo
            # que la sesión guardada traiga los suyos.
            dic.setdefault(nuevo, self._asaltos)
        else:
            dic[previo] = self._asaltos
            if nuevo not in dic:
                semilla = getattr(self, "_asaltos_del_combate", None)
                if semilla is not None and getattr(self, "_migrar_asaltos", False):
                    # Sesión de antes: los dos atletas parten de los asaltos
                    # del combate que tenía; F y G dentro los corrigen.
                    dic[nuevo] = Asaltos.de_lista(semilla.a_lista(), semilla.total)
                else:
                    dic[nuevo] = Asaltos(total=self._asaltos.total)
        self._asaltos = dic[nuevo]
        self._atleta_de_asaltos = nuevo
        self._enganchar_asaltos()
        vm = self.video_manager
        vm.fight_start = self._asaltos.inicio_del_combate
        vm.fight_end = self._asaltos.fin_del_combate
        self.window.video_panel.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)

    # ── Delimitar los asaltos sin fallos (Johan, 12-10-2026) ────────
    def _enganchar_reglas_de_asaltos(self) -> None:
        """En la pasada de fases los asaltos van en modo estricto: en orden,
        sin pisar uno cerrado y sin dejar fases fuera de su asalto."""
        fc = self.fight_controller
        fc.estricto = lambda: bool(self._hace_tiempo_movimiento() and self._en_modo_fases())
        fc.validar_asalto = self._validar_asalto
        fc.asalto_rechazado.connect(self.window.set_status_message)

    def _validar_asalto(self, que: str, n: int, frame: int) -> Optional[str]:
        """Que mover un inicio o un fin no deje fuera de su asalto ninguna
        fase del atleta: al mover el inicio más tarde, una fase anterior;
        al mover el fin antes, una posterior."""
        filas = [r for _i, r in self._filas_de_fase()
                 if int(getattr(r, "round", 0) or 0) == int(n)]
        fps = self.video_manager.fps or 30.0
        if que == "inicio":
            fuera = [r for r in filas if int(r.f_start) < int(frame)]
            if fuera:
                return I18n().t("tm.asalto_fases_antes", n=str(n), cuantas=str(len(fuera)),
                                reloj=_reloj(min(int(r.f_start) for r in fuera), fps))
        else:
            fuera = [r for r in filas if int(r.f_start) > int(frame)]
            if fuera:
                return I18n().t("tm.asalto_fases_despues", n=str(n), cuantas=str(len(fuera)),
                                reloj=_reloj(max(int(r.f_start) for r in fuera), fps))
        return None

    def _todos_los_asaltos(self) -> list[Any]:
        """Los asaltos del combate o los de cada atleta, sin repetir."""
        vistos, salida = set(), []
        for a in [getattr(self, "_asaltos", None),
                  *(getattr(self, "_asaltos_por_atleta", None) or {}).values()]:
            if a is not None and id(a) not in vistos:
                vistos.add(id(a)); salida.append(a)
        return salida

    def _elegir_numero_de_asaltos(self, n: int) -> None:
        """El selector 1·2·3 del panel: cuántos asaltos tiene el combate. No
        baja por debajo de un asalto ya marcado (de ningún atleta)."""
        if getattr(self, "_asaltos", None) is None or not 1 <= int(n) <= 9:
            return
        for a in self._todos_los_asaltos():
            for k in range(int(n) + 1, a.total + 1):
                if a.inicio(k) is not None or a.fin(k) is not None:
                    self.window.set_status_message(I18n().t("tm.no_reducir", n=str(k)))
                    return
        self._bout_info["num_rounds"] = str(int(n))
        if 0 <= self.active_session_idx < len(self.sessions):
            self.sessions[self.active_session_idx].bout_metadata = dict(self._bout_info)
        self.fight_controller.asalto_elegido = 0
        self._ajustar_total_de_asaltos()
        self._sync_round_label()
        self._refrescar_panel_fases()
        self.window.set_status_message(I18n().t("tm.numero_elegido", n=str(int(n))))

    def _al_pulsar_asalto(self, n: int) -> None:
        """Pulsar la pastilla de un asalto marcado lo elige para corregirlo
        (y lleva el vídeo a su inicio); pulsarla otra vez lo suelta."""
        a = getattr(self, "_asaltos", None)
        if a is None or not 1 <= int(n) <= a.total:
            return
        fc = self.fight_controller
        if fc.asalto_elegido == n:
            fc.asalto_elegido = 0
            self.window.set_status_message(I18n().t("tm.correccion_hecha", n=str(n)))
        elif a.inicio(n) is None:
            self.window.set_status_message(I18n().t("tm.guia_abrir", n=str(a.en_curso), total=str(a.total)))
        else:
            fc.asalto_elegido = int(n)
            self.video_manager.goto(int(a.inicio(n)))
            self.window.set_status_message(I18n().t("tm.guia_corrigiendo", n=str(n)))
        self._refrescar_panel_fases()

    def _borrar_asalto(self, n: int) -> None:
        """Quitar las marcas de un asalto elegido. Solo si no tiene fases del
        atleta dentro: borrarlo las dejaría sin asalto."""
        a = getattr(self, "_asaltos", None)
        if a is None or not 1 <= int(n) <= a.total:
            return
        dentro = [r for _i, r in self._filas_de_fase() if int(getattr(r, "round", 0) or 0) == int(n)]
        if not self._asaltos_por_atleta_activos():
            dentro += [r for r in self.window.table_view.records
                       if getattr(r, "category", "") != CATEGORIA_FASE
                       and int(getattr(r, "round", 0) or 0) == int(n)]
        if dentro:
            self.window.set_status_message(I18n().t("tm.no_borrar_con_fases", n=str(n), cuantas=str(len(dentro))))
            return
        a.borrar(int(n))
        self.fight_controller.asalto_elegido = 0
        vm = self.video_manager
        vm.fight_start, vm.fight_end = a.inicio_del_combate, a.fin_del_combate
        self.window.video_panel.update_fight_label(vm.fight_start, vm.fight_end, vm.fps)
        self._sincronizar_fases()
        self._update_timeline()
        self._schedule_save()
        self.window.set_status_message(I18n().t("tm.asalto_borrado", n=str(n)))

    def _ajustar_ultima_fase_al_fin(self, n: int) -> None:
        """La última fase de un asalto acaba donde acaba el asalto: cerrada si
        estaba abierta, alargada o recortada si se movió el fin. Así la suma
        de las fases de cada asalto es el asalto, como en la hoja del especialista."""
        from karlos_core.controllers.undo_commands import ExtenderAnotacionCommand
        a = getattr(self, "_asaltos", None)
        fin = a.fin(n) if a is not None else None
        if fin is None:
            return
        inicio = a.inicio(n)
        filas = [(i, r) for i, r in self._filas_de_fase()
                 if int(getattr(r, "round", 0) or 0) == int(n)
                 or (inicio is not None and int(inicio) <= int(r.f_start) <= int(fin))]
        if not filas:
            return
        idx, ultima = max(filas, key=lambda x: int(x[1].f_start))
        if int(ultima.f_end) == int(fin) or int(fin) <= int(ultima.f_start):
            return
        self.undo_stack.push(ExtenderAnotacionCommand(idx, self.window.table_view, int(fin),
                                                      self.video_manager.fps or 30.0))
        self._tras_cambiar_fases()

    def _asaltos_del(self, atleta: str) -> Any:
        """Los asaltos con que se cortan las fases de ese atleta."""
        if not self._asaltos_por_atleta_activos():
            return getattr(self, "_asaltos", None)
        if atleta == getattr(self, "_atleta_de_asaltos", None):
            return self._asaltos
        dic = getattr(self, "_asaltos_por_atleta", None) or {}
        if atleta in dic:
            return dic[atleta]
        return getattr(self, "_asaltos_del_combate", None) if not atleta else None

    def _asaltos_a_guardar(self) -> Optional[dict[str, Any]]:
        """{atleta: asaltos} para la sesión, solo en el tiempo-movimiento."""
        if not self._asaltos_por_atleta_activos():
            return None
        dic = dict(getattr(self, "_asaltos_por_atleta", None) or {})
        actual = getattr(self, "_atleta_de_asaltos", None)
        if actual is not None:
            dic[actual] = self._asaltos
        return {a: x.a_lista() for a, x in dic.items() if x is not None}

    def _asaltos_para_informe(self) -> Any:
        """Lo que el informe, el Excel y el PDF necesitan: {atleta: asaltos}
        en el tiempo-movimiento, la lista del combate en los demás."""
        from karlos_core.tiempo_movimiento import asaltos_o_combate
        vm = self.video_manager
        por_atleta = self._asaltos_a_guardar()
        if por_atleta is not None:
            return asaltos_o_combate(por_atleta, vm.fight_start, vm.fight_end)
        lista = self._asaltos.a_lista() if getattr(self, "_asaltos", None) is not None else None
        # En karate no hay asaltos que marcar: el asalto es el combate.
        return asaltos_o_combate(lista, vm.fight_start, vm.fight_end)

    def _al_cambiar_atleta(self) -> None:
        """Lo que se ve pasa a ser del atleta nuevo: sus fases y, en el
        tiempo-movimiento, sus asaltos."""
        if not self._hace_tiempo_movimiento():
            return
        self.fight_controller.asalto_elegido = 0
        self._poner_asaltos_del_atleta()
        self._sincronizar_fases()
        self._update_timeline()
        self._refrescar_log()
        from karlos_core.tiempo_movimiento import fases_por_atleta
        if self._en_modo_fases() and fases_por_atleta():
            from karlos_core import catalogo
            self.window.set_status_message(I18n().t(
                "tm.agora", atleta=catalogo.etiqueta(self._atleta_actual())))

    @staticmethod
    def _abierta(fila: Any) -> bool:
        """Una fase sin fin todavía: la cierra la pulsación siguiente."""
        return int(fila.f_end) <= int(fila.f_start)

    def _sincronizar_fases(self) -> None:
        """Las marcas (la vista que usan el rótulo, la línea de tiempo, el
        informe y el Excel) se derivan siempre de las filas PHASE."""
        if not self._hace_tiempo_movimiento():
            self._fases = None
            return
        from karlos_core.models.fases import Fases
        from karlos_core.tiempo_movimiento import marcas_por_atleta
        # El asalto de cada fila PHASE sale de los asaltos de su atleta: si
        # se corrige un inicio o un fin, las filas lo siguen (el CSV escribe
        # ese número en la columna de la fase).
        for _i, r in enumerate(self.window.table_view.records):
            if getattr(r, "category", "") != CATEGORIA_FASE:
                continue
            asaltos = self._asaltos_del(str(getattr(r, "athlete", "") or ""))
            if asaltos is None or asaltos.inicio_del_combate is None:
                continue
            n = asaltos.de_fotograma(int(r.f_start))
            if int(getattr(r, "round", 0) or 0) != n:
                r.round = n
        self._fases_por_atleta = {a: Fases.de_lista(ms) for a, ms in
                                  marcas_por_atleta(self.window.table_view.records).items()}
        propias = self._fases_por_atleta.get(self._atleta_de_fase())
        # Lo marcado antes del 9-10 no tiene atleta (era del combate). No se
        # pierde: se ve en el panel y en la línea de tiempo mientras ningún
        # atleta tenga fases suyas, y siempre en el registro y el informe.
        antiguas = self._fases_por_atleta.get("")
        if propias is None and antiguas is not None and not any(
                a for a in self._fases_por_atleta if a):
            propias = antiguas
        self._fases = propias if propias is not None else Fases()
        self._sync_round_label()
        self._refrescar_panel_fases()

    def _quitar_fases_repetidas(self) -> int:
        """Fuera las filas PHASE repetidas (mismo atleta, mismo inicio).

        Hasta el 12-10-2026, al reabrir un combate las marcas guardadas se
        volvían filas ANTES de cargar el registro, que traía esas mismas
        filas: cada reapertura las duplicaba (la hoja del especialista, cada fase
        dos veces). Dos fases del mismo atleta no pueden empezar en el mismo
        fotograma, así que la repetida es una copia y quitarla no pierde
        nada."""
        tabla = self.window.table_view
        vistos, repetidas = set(), []
        for i, r in enumerate(tabla.records):
            if getattr(r, "category", "") != CATEGORIA_FASE:
                continue
            clave = (str(getattr(r, "athlete", "") or ""), int(r.f_start))
            if clave in vistos:
                repetidas.append(i)
            else:
                vistos.add(clave)
        for i in reversed(repetidas):
            tabla.remove_row(i)
        return len(repetidas)

    def _nuevas_fases(self) -> None:
        from karlos_core.models.fases import Fases
        self._fases = Fases() if self._hace_tiempo_movimiento() else None

    def _reponer_fases(self, filas) -> None:
        """Lo que la sesión guardada traía marcado. Las sesiones del 8-10 por
        la mañana guardaban las marcas aparte; si vienen y el registro no
        tiene filas PHASE, se convierten en filas, que es donde viven ahora."""
        if getattr(self, "_fases", None) is None:
            return
        from karlos_core.models.fases import Fases
        from karlos_core.tiempo_movimiento import marcas_por_atleta
        from karlos_core.formato import COMPETIDORES
        if not self._filas_de_fase("") and not any(self._filas_de_fase(a) for a in COMPETIDORES):
            for atleta, lista in marcas_por_atleta(filas).items():
                marcas = Fases.de_lista(lista).marcas
                for i, (f, estado) in enumerate(marcas):
                    fin = marcas[i + 1][0] - 1 if i + 1 < len(marcas) else f
                    self.window.table_view.add_annotation(self._fila_de_fase(estado, f, fin, atleta))
        self._sincronizar_fases()

    def _fila_de_fase(self, estado: str, inicio: int, fin: int,
                      atleta: Optional[str] = None) -> Any:
        from karlos_core.models.annotation import Annotation
        fps = self.video_manager.fps or 30.0
        asalto_de = getattr(self.flow_controller, "asalto_de", None)
        asalto = asalto_de(inicio) if asalto_de else 0
        return Annotation(
            athlete=self._atleta_de_fase() if atleta is None else atleta,
            category=CATEGORIA_FASE, subcategory=CATEGORIA_FASE,
            technique=estado, f_start=int(inicio), f_end=int(fin),
            duration_s=max(0, int(fin) - int(inicio)) / fps,
            video_file=Path(self._video_path).name if self._video_path else "",
            round=int(asalto or 0))

    @staticmethod
    def _rotulo_fase(estado: Optional[str]) -> str:
        """Las fases se enseñan con las palabras del instrumento, sin
        traducir, como las técnicas coreanas. Cada deporte pone las suyas:
        el karate llama «preparatory» a lo que el taekwondo llama
        «non-fighting» (Chaabène et al. 2014, decisión 0008)."""
        from karlos_core.tiempo_movimiento import rotulo_de_fase
        return rotulo_de_fase(estado or "") if estado else ""

    def _fase_en_curso(self) -> str:
        fases = getattr(self, "_fases", None)
        if fases is None or fases.vacias:
            return ""
        return self._rotulo_fase(fases.estado_en(self.video_manager.current_frame))

    def _tecla_de_fase(self, tecla: str) -> bool:
        """Un número en la pasada de fases marca el estado que le toque al
        deporte; los demás no hacen nada, y se dice. Se consume siempre,
        para que no dispare una técnica del panel que no se ve — que es lo
        que deja los dígitos libres en karate, donde las diez cifras son
        técnicas en los otros modos (decisión 0008)."""
        from karlos_core.tiempo_movimiento import teclas_de_fase
        teclas = teclas_de_fase()
        estado = teclas.get(tecla)
        if estado is None:
            self.window.set_status_message(
                I18n().t("tm.solo_digitos", digitos=", ".join(sorted(teclas))))
            return True
        self._marcar_fase(estado)
        return True

    def _marcar_fase(self, estado: str) -> None:
        """El combate entra en esa fase en este fotograma: una fila nueva en
        el registro, y la anterior se cierra justo antes."""
        from karlos_core.controllers.undo_commands import AddAnnotationCommand, ExtenderAnotacionCommand
        vm = self.video_manager
        if getattr(self, "_fases", None) is None or not vm.is_loaded:
            return
        analisis = self._analisis_del_combate()
        if analisis == TECNICO_TACTICO:
            self.window.set_status_message(I18n().t("tm.sin_fases_tt"))
            return
        if analisis == COMPLETO and not self._en_modo_fases():
            self.window.set_status_message(I18n().t("tm.pasada_acciones"))
            return
        frame, fps = int(vm.current_frame), vm.fps or 30.0
        asaltos = getattr(self, "_asaltos", None)
        if asaltos is not None and not asaltos.de_fotograma(frame):
            # El asalto es la muestra (el especialista): una fase fuera de los
            # asaltos no es de ninguno, y en el CSV salía como «Round_4».
            atleta = catalogo.etiqueta(self._atleta_actual())
            if asaltos.marcados < asaltos.total:
                n = asaltos.en_curso
                self.window.set_status_message(I18n().t(
                    "tm.fuera_de_asalto", n=str(n), atleta=atleta))
            else:
                self.window.set_status_message(I18n().t("tm.fuera_de_los_asaltos", atleta=atleta))
            return
        rotulo = self._rotulo_fase(estado)
        filas = self._filas_de_fase()
        tabla = self.window.table_view
        if filas:
            idx, ultima = filas[-1]
            if frame <= int(ultima.f_start):
                self.window.set_status_message(I18n().t(
                    "tm.anterior_empieza", fase=self._rotulo_fase(ultima.technique),
                    reloj=_reloj(ultima.f_start, fps)))
                return
            if ultima.technique == estado and self._abierta(ultima):
                self.window.set_status_message(I18n().t("tm.ya_esta", fase=rotulo))
                return
        self.undo_stack.beginMacro(I18n().t("tm.macro_fase", fase=rotulo))
        try:
            if filas and self._abierta(filas[-1][1]):
                # La fase anterior acaba justo antes de que empiece esta.
                self.undo_stack.push(ExtenderAnotacionCommand(filas[-1][0], tabla, frame - 1, fps))
            self.undo_stack.push(AddAnnotationCommand(self._fila_de_fase(estado, frame, frame), tabla))
        finally:
            self.undo_stack.endMacro()
        self._tras_cambiar_fases()
        self.window.set_status_message(I18n().t(
            "tm.marcada", n=str(len(self._filas_de_fase())), fase=rotulo, reloj=_reloj(frame, fps)))

    def _cerrar_fase_abierta(self, frame: int) -> None:
        """Cerrar la última fase en ese fotograma, si sigue abierta: al cerrar
        el asalto, la fase no puede quedar colgando."""
        from karlos_core.controllers.undo_commands import ExtenderAnotacionCommand
        filas = self._filas_de_fase()
        if not filas or frame is None or not self._abierta(filas[-1][1]):
            return
        idx, ultima = filas[-1]
        if int(frame) <= int(ultima.f_start):
            return
        self.undo_stack.push(ExtenderAnotacionCommand(idx, self.window.table_view, int(frame),
                                                      self.video_manager.fps or 30.0))
        self._tras_cambiar_fases()

    def _quitar_fase(self) -> None:
        """Shift+C: retirar la última fase del registro; la anterior vuelve a
        quedar abierta, como estaba antes de marcarla."""
        filas = self._filas_de_fase()
        if getattr(self, "_fases", None) is None or not filas:
            self.window.set_status_message(I18n().t("tm.nada_que_retirar"))
            return
        from karlos_core.controllers.undo_commands import BorrarAnotacionCommand, ExtenderAnotacionCommand
        idx, ultima = filas[-1]
        tabla = self.window.table_view
        fps = self.video_manager.fps or 30.0
        # Por la pila de deshacer, como marcarla: así Shift+C y Ctrl+Z no se
        # pisan, y la fase retirada se puede rehacer.
        self.undo_stack.beginMacro(f"Retirar fase {self._rotulo_fase(ultima.technique)}")
        try:
            self.undo_stack.push(BorrarAnotacionCommand(idx, tabla))
            if len(filas) > 1:
                idx_prev, previa = filas[-2]
                # La anterior vuelve a quedar abierta (fin = inicio).
                self.undo_stack.push(ExtenderAnotacionCommand(idx_prev, tabla, int(previa.f_start), fps))
        finally:
            self.undo_stack.endMacro()
        self._tras_cambiar_fases()
        self.window.set_status_message(
            f"Retirada: {self._rotulo_fase(ultima.technique)} de "
            f"{_reloj(ultima.f_start, self.video_manager.fps or 30.0)}"
            + (f"  —  volta a {self._rotulo_fase(filas[-2][1].technique)}" if len(filas) > 1 else ""))

    def _tras_cambiar_fases(self) -> None:
        self._sincronizar_fases()
        self._update_timeline()
        self._refrescar_log()
        if 0 <= self.active_session_idx < len(self.sessions):
            self.sessions[self.active_session_idx].annotations = list(self.window.table_view.records)
        self._schedule_save()

    def _refrescar_panel_fases(self) -> None:
        """El panel, visto desde este fotograma. Solo si se ve."""
        panel = getattr(self.window, "panel_fases", None)
        if panel is None or not panel.isVisible():
            return
        panel.actualizar(getattr(self, "_fases", None), getattr(self, "_asaltos", None),
                         self.video_manager.current_frame, self.video_manager.fps or 30.0,
                         self._atleta_de_fase(), self._asaltos_por_atleta_activos(),
                         int(getattr(self.fight_controller, "asalto_elegido", 0) or 0))

    def _intervalos_de_fase(self) -> list[tuple[int, int, str]]:
        """Para la línea de tiempo: (inicio, fin, estado) de lo marcado."""
        fases = getattr(self, "_fases", None)
        if fases is None or fases.vacias:
            return []
        total = max(self.video_manager.total_frames - 1, 0)
        return [(t.inicio, t.fin, t.estado) for t in fases.intervalos(0, total)]

    # (Hasta el 8-10 las fases eran del combate y al cerrar el último asalto
    # se preguntaba si concluir. Ahora son de cada atleta y el cierre sigue
    # el camino de las acciones: el diálogo ofrece al otro atleta.)
