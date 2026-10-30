"""Panel de etiquetado guiado: una pregunta a la vez, junto al video.

Va al lado del video y no en una ventana emergente a proposito: mientras
se decide hay que seguir viendo el bucle, y una ventana encima taparia
justo lo que se necesita mirar.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QLabel, QPushButton, QVBoxLayout,
                               QWidget)

from karlos_core.models.technique import AppColors
from karlos_core.views.theme import Palette


class GuidedPanel(QWidget):
    """Muestra la pregunta vigente y sus opciones numeradas."""

    # Se puede contestar con las teclas 1-9 o pulsando la opcion. Los dos
    # caminos acaban en la misma senal: unos evaluadores van mas rapido de
    # memoria y otros prefieren leer y pulsar.
    opcion_elegida = Signal(str)     # clave de la opcion
    # Aparecer o irse cambia lo que cabe en la columna derecha: quien la
    # reparte necesita enterarse. Se avisa desde aqui y no desde los doce
    # sitios que llaman a `ocultar()`.
    visibilidad_cambio = Signal(bool)

    def __init__(self, colors: AppColors, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._colors = colors
        self._claves: list[str] = []
        self._build()

    def _build(self) -> None:
        c = self._colors
        p = Palette.from_config(c)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        self._progreso = QLabel("")
        self._progreso.setStyleSheet(
            f"color:{c.muted};font-size:11px;background:transparent;border:none;")
        lay.addWidget(self._progreso)

        self._rastro = QLabel("")
        self._rastro.setWordWrap(True)
        self._rastro.setStyleSheet(
            f"color:{c.accent};font-size:11px;font-weight:600;"
            "background:transparent;border:none;")
        lay.addWidget(self._rastro)

        self._pregunta = QLabel("")
        self._pregunta.setWordWrap(True)
        self._pregunta.setStyleSheet(
            f"color:{c.text};font-size:15px;font-weight:700;"
            "background:transparent;border:none;")
        lay.addWidget(self._pregunta)

        self._opciones = QVBoxLayout()
        self._opciones.setSpacing(4)
        lay.addLayout(self._opciones)

        # Lo que no se puede pasar por alto: una accion contestada que
        # se perderia si se sigue sin cerrarla.
        self._aviso = QLabel("")
        self._aviso.setWordWrap(True)
        self._aviso.setStyleSheet(
            f"color:{c.yellow};font-size:12px;font-weight:600;"
            "background:transparent;border:none;")
        self._aviso.setVisible(False)
        lay.addWidget(self._aviso)
        lay.addStretch(1)

        from karlos_core.utils.i18n import I18n
        self._pie = QLabel(I18n().t("guia.retroceso"))
        self._pie.setStyleSheet(
            f"color:{c.muted};font-size:11px;background:transparent;border:none;")
        lay.addWidget(self._pie)

        self.setStyleSheet(
            f"background:{p.surface_2};border:1px solid {c.accent};border-radius:6px;")
        self.setMinimumWidth(230)
        # Sin minimo, el divisor lo aplasta a cero y las preguntas
        # desaparecen sin que se vea por que.
        self.setMinimumHeight(240)
        self.setVisible(False)

    # ------------------------------------------------------------------
    def mostrar_paso(self, pregunta: str, opciones: list[tuple[str, str]],
                     paso: int, total: int, cabecera: str,
                     respuestas: Optional[list[str]] = None,
                     grupos: tuple = ()) -> None:
        c = self._colors
        from karlos_core.utils.i18n import I18n
        self._progreso.setText(I18n().t("guia.paso", cabecera=cabecera, n=paso, total=total))
        self._rastro.setText("  ›  ".join(respuestas or []))
        self._rastro.setVisible(bool(respuestas))
        self._pregunta.setText(pregunta)
        self._aviso.setVisible(False)
        self._limpiar_opciones()
        self._claves = [clave for _, clave in opciones]
        titulos = dict(grupos or ())
        for i, (etiqueta, _) in enumerate(opciones, start=1):
            if (i - 1) in titulos:
                cab = QLabel(titulos[i - 1])
                cab.setStyleSheet(
                    f"color:{c.muted};font-size:9px;font-weight:700;"
                    "letter-spacing:1.2px;padding:4px 2px 0 2px;"
                    "background:transparent;border:none;")
                self._opciones.addWidget(cab)
            clave = opciones[i - 1][1]
            # La decima se teclea con el 0, que esta justo al lado del 9.
            # Sin esto la opcion existia pero no habia tecla para ella.
            fila = QPushButton(f"  {i if i < 10 else 0}\u2003 {etiqueta}")
            fila.setCursor(Qt.PointingHandCursor)
            fila.setMinimumHeight(30)
            fila.setStyleSheet(
                f"QPushButton{{color:{c.text};font-size:13px;padding:6px 8px;"
                f"border:1px solid {c.muted}55;border-radius:4px;"
                "background:transparent;text-align:left;}"
                f"QPushButton:hover{{background:{c.accent}22;"
                f"border:1px solid {c.accent};}}"
                f"QPushButton:pressed{{background:{c.accent}44;}}")
            fila.clicked.connect(lambda _=False, k=clave: self.opcion_elegida.emit(k))
            self._opciones.addWidget(fila)
        self.setVisible(True)

    def mostrar_espera(self, cabecera: str, respuestas: list[str], texto: str,
                       aviso: str = "") -> None:
        """Lo contestado espera su final, y se queda a la vista hasta el [O].

        Antes el panel se cerraba al contestar la ultima pregunta y el
        unico recuerdo de que faltaba el final era la barra de estado.
        """
        self._progreso.setText(cabecera)
        self._rastro.setText("  ›  ".join(respuestas or []))
        self._rastro.setVisible(bool(respuestas))
        self._pregunta.setText(texto)
        self._limpiar_opciones()
        self._claves = []
        self._aviso.setText(aviso)
        self._aviso.setVisible(bool(aviso))
        self.setVisible(True)

    def _limpiar_opciones(self) -> None:
        while self._opciones.count():
            w = self._opciones.takeAt(0).widget()
            if w is not None:
                # setParent(None) lo quita ya; con deleteLater solo se
                # programa el borrado y hasta que gira el bucle de eventos
                # el widget viejo sigue dibujandose encima del nuevo.
                # Oculto antes de soltarlo: sin bucle de eventos (pruebas,
                # capturas) el boton suelto seguia vivo y visible como
                # ventana propia hasta que algo lo borrara.
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def clave_de(self, numero: int) -> Optional[str]:
        """Clave asociada a la tecla pulsada, o None si no aplica.

        Las nueve primeras van con su numero; la decima con el 0, que es
        la tecla contigua al 9 y la unica que queda en la fila.
        """
        if numero == 0:
            return self._claves[9] if len(self._claves) >= 10 else None
        if 1 <= numero <= min(9, len(self._claves)):
            return self._claves[numero - 1]
        return None

    def showEvent(self, evento):
        super().showEvent(evento)
        self.visibilidad_cambio.emit(True)

    def hideEvent(self, evento):
        super().hideEvent(evento)
        self.visibilidad_cambio.emit(False)

    def ocultar(self) -> None:
        self.setVisible(False)
