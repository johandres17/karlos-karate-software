"""Las paradas del árbitro: su tipo y sus tramos.

Parte del controlador principal (``annotation_controller``), separada en la
fase F3.7.
"""

from __future__ import annotations

from karlos_core.controllers.session_manager import SessionManager
from karlos_core.utils.app_logging import get_logger

# El mismo nombre que antes de partir el controlador: el log no cambia.
_log = get_logger("karlos_core.controllers.annotation_controller")


class ParadasMixin:
    """Las paradas del árbitro: su tipo y sus tramos."""

    def _paradas_ordenadas(self) -> list[tuple[int, int]]:
        """Los tramos de parada, sin duplicar el par de cada atleta."""
        tramos: list[tuple[int, int]] = []
        for a in sorted(self.window.table_view.records,
                        key=lambda x: int(x.f_start)):
            if getattr(a, "category", "") != "REFEREE STOP":
                continue
            ini, fin = int(a.f_start), int(a.f_end)
            if tramos and abs(tramos[-1][0] - ini) < 30:
                continue          # la misma parada, la fila del otro atleta
            tramos.append((ini, fin))
        return tramos

    _PARADA_NOMBRE = {"Referee": "paradas.n_referee",
                      "VR": "paradas.n_vr", "Injury": "paradas.n_injury"}

    def _calificar_parada(self, tipo: str, filas: list | None = None) -> bool:
        """Decir de que tipo fue la parada donde esta el video.

        No se crea una anotacion nueva. Cada parada ya son DOS filas, una
        por atleta (24 filas para 11 paradas en ID30); anotarla otra vez
        la dejaria en cuatro y contaria el tiempo muerto por duplicado.
        Se escribe el tipo encima de las que hay.

        Devuelve False si el video no esta dentro de ninguna parada
        anotada, y entonces el recorrido sigue su camino normal.
        """
        tabla = self.window.table_view
        clonada = ""
        if filas is None:
            f = int(self.video_manager.current_frame)
            atleta = self.window.annotation_panel.athlete
            filas = [i for i, a in enumerate(tabla.records)
                     if getattr(a, "category", "") == "REFEREE STOP"
                     and int(a.f_start) <= f <= int(a.f_end)]
            if filas and all(tabla.records[i].athlete != atleta for i in filas):
                # La parada es del combate, no del atleta: el otro ya la
                # tiene y a este le falta su fila. Antes se escribia el
                # tipo encima de la del otro y la de este no se creaba
                # nunca — asi perdio Johan once de doce paradas en la
                # pasada del AO (21-09-2026). Se clona con los mismos
                # frames; el tipo, que es de la pausa, se pone abajo a
                # todas las filas de la pareja.
                import dataclasses
                from karlos_core.controllers.undo_commands import \
                    AddAnnotationCommand
                socio = tabla.records[filas[0]]
                nueva = dataclasses.replace(
                    socio, athlete=atleta, technique=tipo, notes="",
                    sport_specific_data=dict(socio.sport_specific_data or {}))
                self.undo_stack.push(AddAnnotationCommand(nueva, tabla))
                filas = filas + [len(tabla.records) - 1]
                clonada = self._i18n.t("paradas.clonada", atleta=atleta, socio=str(socio.athlete))
        dentro = [i for i in filas if 0 <= i < len(tabla.records)]
        if not dentro:
            return False
        for i in dentro:
            tabla.update_record(i, technique=tipo)
        self._refrescar_log()
        self._save_session()
        nombre = (self._i18n.t(self._PARADA_NOMBRE[tipo])
                  if tipo in self._PARADA_NOMBRE else tipo)
        self.window.set_status_message(self._i18n.t(
            "paradas.marcada", nome=nombre, n=str(len(dentro)),
            filas=self._i18n.t("paradas.filas" if len(dentro) != 1 else "paradas.fila"),
            clonada=clonada))
        return True

    def _paradas_guardadas(self, video: str) -> tuple[int, int]:
        """Cuantas anotaciones hay guardadas y cuantas son paradas."""
        ruta = self.session_manager.ruta_de_sesion(video)
        if ruta is None:
            return 0, 0
        datos = SessionManager._read_session_json(ruta) or {}
        anotaciones = datos.get("annotations", [])
        paradas = sum(1 for a in anotaciones
                      if a.get("category") == "REFEREE STOP")
        return len(anotaciones), paradas
