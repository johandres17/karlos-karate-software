"""Recorrer el combate: anotaciones, intercambios y lupa.

Parte del controlador principal (``annotation_controller``), separada en la
fase F3.7.
"""

from __future__ import annotations

from karlos_core import catalogo
from karlos_core.utils.i18n import I18n
from karlos_core.utils.app_logging import get_logger

# El mismo nombre que antes de partir el controlador: el log no cambia.
_log = get_logger("karlos_core.controllers.annotation_controller")


def siguiente_anotacion(anotaciones, actual: int, delta: int):
    """La anotacion anterior o posterior al frame actual, o None.

    [Tab] recorre lo que el evaluador YA anoto. Se busca por POSICION y no
    por indice en una lista: asi [Tab] sigue funcionando igual despues de
    arrastrar la lupa a otro punto del combate, que es como se usa de
    verdad.

    Las paradas del arbitro no cuentan: no son acciones del atleta y
    recorrerlas obligaria a pasar por encima de ellas cada vez.
    """
    utiles = sorted(
        (a for a in anotaciones
         if getattr(a, "category", "") not in ("REFEREE STOP",)
         and getattr(a, "technique", "") != "Referee"),
        key=lambda a: int(a.f_start))
    if delta >= 0:
        posteriores = [a for a in utiles if int(a.f_start) > actual + 1]
        return posteriores[0] if posteriores else None
    previos = [a for a in utiles if int(a.f_start) < actual - 1]
    return previos[-1] if previos else None


class RevisionMixin:
    """Recorrer el combate: anotaciones, intercambios y lupa."""

    def _atleta_cambiado(self, *_) -> None:
        """Al cambiar de atleta se empieza su recorrido desde el principio."""
        # Las fases y, en el tiempo-movimiento, los asaltos son de cada
        # atleta: lo que se ve pasa a ser del nuevo.
        cambio = getattr(self, "_al_cambiar_atleta", None)
        if cambio is not None:
            cambio()
        self._pintar_linea_del_atleta()
        self._actualizar_zoom()
        if not self._en_modo_pro():
            return
        self.window.set_status_message(I18n().t(
            "pro.agora", atleta=catalogo.etiqueta(self.window.annotation_panel.athlete),
            pista=I18n().t("pro.pista_marca_inicio")))

    def _pintar_linea_del_atleta(self) -> None:
        """En la anotación guiada la línea de tiempo enseña solo lo del atleta
        de la pasada: pintar los dos a la vez hacía el recorrido confuso, con
        el doble de marcas y sin saber cuál toca."""
        tl = self.window.video_panel.timeline
        tl.set_solo_atleta(self.window.annotation_panel.athlete
                           if self._en_modo_pro() else None)

    def _ir_a_intercambio(self, direccion: int) -> None:
        """[↓] y [↑] — al intercambio siguiente o anterior.

        En un montador estas teclas van al corte siguiente. Aqui el corte
        es la parada del arbitro anotada: la mitad del video de un combate
        es tiempo muerto, y [Tab] va a las anotaciones propias, que en un
        combate sin empezar son ninguna.
        """
        vm = self.video_manager
        if not vm.is_loaded:
            return
        bordes = [int(vm.fight_start or 0)]
        for ini, fin in self._paradas_ordenadas():
            bordes.append(ini)
            bordes.append(fin)
        if vm.fight_end:
            bordes.append(int(vm.fight_end))
        bordes = sorted({b for b in bordes if b >= 0})
        if len(bordes) < 2:
            self.window.set_status_message(
                self._i18n.t("stat.sem_paradas_analisadas"))
            return
        aqui = vm.current_frame
        if direccion > 0:
            siguientes = [b for b in bordes if b > aqui + 1]
            destino = siguientes[0] if siguientes else bordes[-1]
        else:
            previos = [b for b in bordes if b < aqui - 1]
            destino = previos[-1] if previos else bordes[0]
        vm.goto(destino)
        n = bordes.index(destino) + 1
        aviso = f"Intercambio {n} de {len(bordes)}  ·  [J K L] para barrerlo"
        for ini, fin in self._paradas_ordenadas():
            if ini <= destino <= fin:
                seg = (fin - ini) / (vm.fps or 30.0)
                aviso = f"Parada de {seg:.0f} s"
                break
        self.window.set_status_message(aviso)

    def _ir_a_anotacion(self, delta: int) -> None:
        """[Tab] y [Shift+Tab]: moverse entre las anotaciones propias."""
        destino = siguiente_anotacion(
            list(self.window.table_view.records),
            self.video_manager.current_frame, delta)
        if destino is None:
            self.window.set_status_message(
                self._i18n.t("stat.sem_mais_frente") if delta >= 0
                else self._i18n.t("stat.sem_mais_atras"))
            return

        # Descarta cualquier marca pendiente. Una accion contestada que
        # esperaba su [O] solo llega aqui despues del aviso de
        # `_hay_accion_sin_fin`: sin el inicio ya no se podria cerrar.
        self.state_machine.reset()
        self._arbol = None
        self._arbol_listo = None
        self._aviso_sin_fin = None
        self._pro_fin = None
        self.window.guided_panel.ocultar()
        if self.video_manager.is_playing:
            self.video_manager.toggle_play()
        self.video_manager.goto(int(destino.f_start))
        self.window.set_status_message(
            f"{destino.athlete} · {destino.technique} — "
            "[I] y [O] para marcar una nueva")

    def _actualizar_zoom(self, ini=None, fin=None) -> None:
        """Refrescar la lupa con lo anotado del atleta y los limites vigentes."""
        vp = self.window.video_panel
        if not self._video_path:
            vp.show_zoom(False)
            return
        if ini is None:
            ini = self.state_machine.f_start
        if fin is None:
            fin = getattr(self, "_pro_fin", None)
            if fin is None:
                fin = self.video_manager.ann_end
        atleta = self.window.annotation_panel.athlete
        vp.set_zoom_video(self.video_manager.total_frames, self.video_manager.fps)
        vp.set_zoom_atleta(atleta)
        vp.set_zoom_anotadas(self._tramos_anotados(atleta))
        vp.set_zoom_marcas(ini, fin)
        vp.set_zoom_frame(self.video_manager.current_frame)
        vp.show_zoom(True)

    def _tramos_anotados(self, atleta: str) -> list:
        """Lo ya anotado de ese atleta, para dibujarlo en la lupa.

        Solo el suyo: mezclar las dos series haria ilegible justo lo que se
        viene a mirar. Las paradas se incluyen porque anotar dentro de una
        es un error que hasta ahora solo se veia en el análisis.
        """
        tramos = []
        for r in self.window.table_view.records:
            if (r.athlete or "") != atleta:
                continue
            f0, f1 = int(r.f_start), int(r.f_end)
            if f1 < f0:
                continue
            parada = getattr(r, "category", "") == "REFEREE STOP"
            tramos.append((f0, f1, self._etiqueta_corta(r), parada))
        return tramos

    def _tab_accion(self, delta: int) -> None:
        """[Tab] y [Mayús+Tab]: ir a la anotacion siguiente o anterior.

        Pasan por el mismo aviso que [I]: saltar a otra anotacion tambien
        tiraba la accion que esperaba su final.
        """
        if self._hay_accion_sin_fin("Tab"):
            return
        self._ir_a_anotacion(delta)
