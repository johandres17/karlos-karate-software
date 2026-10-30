"""Dar un combate por concluido.

Parte del controlador principal (``annotation_controller``), separada en la
fase F3.7.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from karlos_core.utils.app_logging import get_logger

# El mismo nombre que antes de partir el controlador: el log no cambia.
_log = get_logger("karlos_core.controllers.annotation_controller")


class EstudioMixin:
    """Combates concluidos: lo decide quien anota, no el programa."""

    def _marcar_concluido(self, fila: int, valor: bool | None = None) -> bool:
        """Poner o quitar la marca de terminado de un combate.

        Sin valor, alterna. La marca vive en el fichero de la sesión, así
        que sobrevive a cerrar el programa y a cada autoguardado.
        """
        video = self._video_de_fila(fila)
        if not video:
            return False
        if valor is None:
            valor = not self.session_manager.esta_concluido(video)
        if not self.session_manager.marcar_concluido(video, valor):
            QMessageBox.information(
                self.window, self._i18n.t("dialog.concluido_titulo"),
                self._i18n.t("dialog.concluido_nada", nome=Path(video).name))
            return False
        if 0 <= fila < len(self.sessions):
            self._refresh_session_from_disk(self.sessions[fila])
            self.window.project_hub.set_sessions(self.sessions)
        nombre = Path(video).name
        self.window.set_status_message(
            self._i18n.t("stat.concluido", nome=nombre) if valor
            else self._i18n.t("stat.nao_concluido", nome=nombre))
        return True

    def _video_de_fila(self, fila: int) -> str:
        if 0 <= fila < len(self.sessions):
            return self.sessions[fila].video_path or ""
        return ""
