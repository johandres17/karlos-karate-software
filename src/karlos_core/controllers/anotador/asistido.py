"""El modo asistido: la anotación guiada por el árbol de preguntas.

En el análisis integrado y en el técnico-táctico cada acción se clasifica
contestando las preguntas del árbol del deporte; en el tiempo-movimiento
las teclas marcan los estados. Al abrir un combate se entra directamente
en este modo.

Parte del controlador principal (``annotation_controller``), separada en la
fase F3.7.
"""

from __future__ import annotations

from karlos_core import catalogo
from karlos_core.utils.i18n import I18n


class AsistidoMixin:
    """El modo asistido: entrar en él al abrir un combate."""

    def _entrar_modo_asistido(self) -> None:
        """Entrar en la anotación guiada con el combate abierto.

        La técnica se elige contestando, así que los botones de técnica del
        panel no se enseñan: servirían para saltarse el árbol y perder el
        contexto táctico sin aviso.
        """
        if not self._video_path:
            self.window.set_status_message(self._i18n.t("stat.abra_video"))
            return
        self._modo_pro_on = True
        self.window.annotation_panel.mostrar_tecnicas(False)
        self.window.aplicar_modo(True)
        # Las etiquetas de la fila de abajo se escriben con el formato del
        # modo vigente: al entrar hay que repintarlas.
        self._repintar_franja()
        self.window.set_pro_branding(True)
        self._detener_bucle()
        self._arbol = None
        self.window.guided_panel.ocultar()
        self._actualizar_zoom()          # la lupa sirve para marcar a mano
        # En el tiempo-movimiento las teclas son las de los estados.
        if getattr(self, "_en_modo_fases", lambda: False)():
            self._anunciar_analisis()
            return
        teclas = I18n().t("tm.teclas_eventos" if getattr(self, "_modo_eventos", lambda: False)()
                          else "pro.teclas_io")
        self.window.set_status_message(I18n().t(
            "pro.modo_asistido",
            atleta=catalogo.etiqueta(self.window.annotation_panel.athlete), teclas=teclas))

    def aplicar_modo_inicial(self) -> None:
        """El cuaderno con que se empieza: el elegido al abrir (decisión 0008)."""
        from karlos_core.views.dialogo_analisis import analisis_por_defecto
        self._poner_analisis_activo(analisis_por_defecto())
        self.window.aplicar_modo(False)     # el anotador aún no está abierto

    def _en_modo_pro(self) -> bool:
        """Si el anotador está en la anotación guiada (lo está con un combate abierto)."""
        return bool(getattr(self, "_modo_pro_on", False))
