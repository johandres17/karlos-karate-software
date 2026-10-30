"""«¿Qué se analiza?»: la primera pantalla del programa.

Tiempo-movimiento, técnico-táctico o integrado (decisión 0008). Es la
primera pregunta porque decide todo lo demás: el tiempo-movimiento son
cuatro estados y ninguna pregunta; el técnico-táctico es el árbol sin
delimitar la acción; el integrado delimita cada acción y la clasifica con
el mismo árbol.

Desde el 19-10-2026 cada análisis es un cuaderno aparte del mismo vídeo:
elegir aquí es abrir ese cuaderno, sin bloqueos, porque lo anotado en cada
uno se queda en el suyo. Y a esta misma pantalla se vuelve desde el Hub
(«‹ Inicio») para cambiar de modo.

Cada tarjeta dice su nombre y una línea. Las teclas y los detalles de cada
modo están en la guía, no aquí (Johan, 19-10-2026: «minimalista premium»).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget

from karlos_core import catalogo, identidad
from karlos_core.models.technique import AppColors
from karlos_core.utils.i18n import I18n
from karlos_core.views import inicio_comun as ic
from karlos_core.views.animaciones import aparecer

# El análisis elegido, en los ajustes de la edición.
ANALISIS = "inicio/analisis"
TECNICO_TACTICO = "technical_tactical"
TIEMPO_MOVIMIENTO = "time_motion"
COMPLETO = "complete"
ANALISIS_POSIBLES = (TECNICO_TACTICO, TIEMPO_MOVIMIENTO, COMPLETO)


def analisis_por_defecto() -> str:
    """El de la última vez; si no hay, el de fábrica del deporte."""
    valor = identidad.ajustes().value(ANALISIS, "")
    return valor if valor in ANALISIS_POSIBLES else _de_fabrica()


def _de_fabrica() -> str:
    """Lo que el deporte declara en ``default_analysis``; sin tiempo-
    movimiento, el completo (es lo único que existe)."""
    ajustes = catalogo.activo().tiempo_movimiento() or {}
    valor = ajustes.get("default_analysis", COMPLETO)
    return valor if valor in ANALISIS_POSIBLES else COMPLETO


class DialogoAnalisis(QDialog):
    """Tres tarjetas, una tecla cada una, y Enter para seguir."""

    def __init__(self, colors: AppColors, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        aparecer(self)
        self._c = colors
        self._i18n = I18n()
        self.analisis = analisis_por_defecto()
        self.setWindowTitle(identidad.en_marcha().nombre)
        self.setModal(True)
        self.setFixedSize(*ic.tamano())
        self.setStyleSheet(f"QDialog{{background:{colors.background};}}")
        self._build()
        self._traducir()
        self._marcar(self.analisis)

    def _build(self) -> None:
        c = self._c
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 26)
        root.setSpacing(0)

        cab = ic.Cabecera(c, self._i18n)
        self._nombre = cab.nombre
        self._linea_deporte = cab.linea
        self._idioma = cab.idioma
        self._idioma.currentIndexChanged.connect(self._cambiar_idioma)
        root.addLayout(cab.layout)
        root.addSpacing(40)

        self._pregunta = ic.etiqueta("", c.text, 24, 600)
        root.addWidget(self._pregunta)
        root.addSpacing(22)

        fila = QHBoxLayout()
        fila.setSpacing(16)
        self._tarjetas: dict[str, ic.Tarjeta] = {}
        # El orden lo puso Johan el 16-10-2026: del instrumento más
        # acotado al más completo.
        for tecla, codigo in (("1", TIEMPO_MOVIMIENTO), ("2", TECNICO_TACTICO),
                              ("3", COMPLETO)):
            tarjeta = ic.Tarjeta(tecla, c)
            tarjeta.clicked = (lambda cod=codigo: self._elegir(cod))
            fila.addWidget(tarjeta, 1)
            self._tarjetas[codigo] = tarjeta
        root.addLayout(fila)
        root.addStretch(1)

        pie = QHBoxLayout()
        pie.setSpacing(6)
        pie.addStretch(1)
        # Con padre es «Volver» (se abrió desde el Hub); sin padre es la
        # primera pantalla del programa y cierra: dice «Salir».
        self._volver = ic.boton_fantasma("", c)
        self._volver.clicked.connect(self.reject)
        pie.addWidget(self._volver)
        self._entrar = ic.boton_primario("", c)
        self._entrar.clicked.connect(lambda: self._elegir(self.analisis))
        pie.addWidget(self._entrar)
        root.addLayout(pie)

    def _traducir(self) -> None:
        t = self._i18n.t
        self._linea_deporte.setText(
            f"{t('deporte.descripcion', deporte=catalogo.activo().nombre)}  ·  "
            f"{t('inicio.version', version=identidad.en_marcha().version)}")
        self._pregunta.setText(t("analisis.pregunta"))
        for codigo, clave in ((TIEMPO_MOVIMIENTO, "tm"), (TECNICO_TACTICO, "tt"),
                              (COMPLETO, "completo")):
            self._tarjetas[codigo].poner_textos(t(f"analisis.{clave}"),
                                                t(f"analisis.{clave}_sub"))
        self._volver.setText(t("analisis.voltar" if self.parent() is not None
                               else "analisis.salir"))
        self._entrar.setText(t("analisis.entrar"))

    def _cambiar_idioma(self) -> None:
        codigo = self._idioma.currentData()
        if codigo and codigo != self._i18n.lang:
            self._i18n.set_lang(codigo)
            self._traducir()

    def _marcar(self, codigo: str) -> None:
        self.analisis = codigo
        for cod, tarjeta in self._tarjetas.items():
            tarjeta.marcar(cod == codigo)

    def _elegir(self, codigo: str) -> None:
        self._marcar(codigo)
        identidad.ajustes().setValue(ANALISIS, codigo)
        self.accept()

    def keyPressEvent(self, evento) -> None:
        """[1] [2] [3] como sus tarjetas; las flechas mueven la marca."""
        tecla = evento.key()
        teclas = {Qt.Key_1: TIEMPO_MOVIMIENTO, Qt.Key_2: TECNICO_TACTICO, Qt.Key_3: COMPLETO}
        orden = (TIEMPO_MOVIMIENTO, TECNICO_TACTICO, COMPLETO)
        if tecla in teclas:
            self._elegir(teclas[tecla])
        elif tecla in (Qt.Key_Left, Qt.Key_Right):
            i = orden.index(self.analisis)
            i = max(0, i - 1) if tecla == Qt.Key_Left else min(len(orden) - 1, i + 1)
            self._marcar(orden[i])
        else:
            super().keyPressEvent(evento)


def elegir_al_inicio(colors: AppColors, parent: Optional[QWidget] = None,
                     actual: Optional[str] = None) -> Optional[str]:
    """La pantalla inicial: «¿Qué se analiza?».

    La usa el arranque y la usa el programa para volver a ella (Johan,
    19-10-2026: «hay que regresar a la primera página para volver a
    seleccionar el modo»). Devuelve el análisis elegido, o None si se
    cierra sin elegir.
    """
    if not catalogo.activo().tiempo_movimiento():
        return COMPLETO
    pregunta = DialogoAnalisis(colors, parent)
    if actual in ANALISIS_POSIBLES:
        pregunta._marcar(actual)
    if pregunta.exec() != QDialog.DialogCode.Accepted:
        return None
    return pregunta.analisis
