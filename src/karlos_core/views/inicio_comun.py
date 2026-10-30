"""Lo que comparten las pantallas de inicio.

La pantalla por la que se entra («¿Qué se analiza?») y las que se abren
desde ella comparten lienzo, marca arriba a la izquierda y botón de seguir
abajo a la derecha. Aquí viven los estilos, la cabecera y la tarjeta de
cada opción para que ninguna los redefina a su manera.

La regla visual (Johan, 19-10-2026: «minimalista premium»): fondo
único, sin paneles dentro de paneles; la jerarquía la hace el tamaño
del texto y el espacio, no las cajas; y el oro es solo para lo que hay
que pulsar o para lo que está elegido. Lo demás calla.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout)

from karlos_core import identidad
from karlos_core.models.technique import AppColors
from karlos_core.utils.i18n import I18n
from karlos_core.views.theme import Palette, marca

ANCHO, ALTO = 820, 440          # las pantallas de elegir, todas del mismo tamaño


def tamano() -> tuple[int, int]:
    """El de las pantallas de inicio, sin pasarse nunca de la pantalla."""
    ancho, alto = ANCHO, ALTO
    pantalla = QGuiApplication.primaryScreen()
    if pantalla is not None:
        libre = pantalla.availableGeometry()
        ancho = min(ancho, int(libre.width() * 0.92))
        alto = min(alto, int(libre.height() * 0.92))
    return ancho, alto


def qss_primario(c: AppColors) -> str:
    """El único botón de color: seguir adelante."""
    p = Palette()
    return (f"QPushButton{{background:{c.accent};color:{p.bg_deeper};font-size:13px;"
            "font-weight:600;border:none;border-radius:8px;padding:0 22px;min-height:38px;}"
            f"QPushButton:hover{{background:{p.ippon_glow};}}"
            "QPushButton:disabled{background:rgba(255,255,255,0.06);"
            "color:rgba(255,255,255,0.25);}")


def qss_fantasma(c: AppColors) -> str:
    """Salir, volver, no aceptar: solo texto, y se enciende al pasar."""
    return (f"QPushButton{{color:{c.muted};font-size:13px;background:transparent;"
            "border:none;padding:0 10px;min-height:38px;}"
            f"QPushButton:hover{{color:{c.text};}}")


def qss_idioma(c: AppColors) -> str:
    return (f"QComboBox{{background:transparent;color:{c.muted};border:none;"
            "padding:4px 6px;font-size:12px;}"
            f"QComboBox:hover{{color:{c.text};}}"
            "QComboBox::drop-down{border:none;width:14px;}"
            f"QComboBox QAbstractItemView{{background:{c.panel};color:{c.text};"
            f"border:1px solid {c.border};border-radius:6px;padding:4px;"
            f"selection-background-color:{c.border};}}")


def etiqueta(texto: str, color: str, tamano: int, peso: int = 400,
             tracking: float = 0.0) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(f"color:{color};font-size:{tamano}px;font-weight:{peso};"
                      f"letter-spacing:{tracking}px;background:transparent;border:none;")
    return lbl


def boton_primario(texto: str, c: AppColors) -> QPushButton:
    b = QPushButton(texto)
    b.setCursor(Qt.PointingHandCursor)
    b.setDefault(True)
    b.setStyleSheet(qss_primario(c))
    return b


def boton_fantasma(texto: str, c: AppColors) -> QPushButton:
    b = QPushButton(texto)
    b.setCursor(Qt.PointingHandCursor)
    b.setAutoDefault(False)
    b.setStyleSheet(qss_fantasma(c))
    return b


class Cabecera:
    """La marca a la izquierda y el idioma a la derecha, en una línea.

    ``nombre`` y ``linea`` son los rótulos (la pantalla los traduce);
    ``idioma`` el desplegable, o None si la pantalla no lo lleva.
    """

    def __init__(self, c: AppColors, i18n: I18n, con_idioma: bool = True) -> None:
        self.layout = QHBoxLayout()
        self.layout.setSpacing(12)
        self.nombre = etiqueta(marca(identidad.en_marcha().nombre, c.text, c.accent),
                               c.text, 13, 700, 2.0)
        self.nombre.setTextFormat(Qt.RichText)
        self.layout.addWidget(self.nombre, 0, Qt.AlignVCenter)
        self.linea = etiqueta("", c.muted, 12)
        self.layout.addWidget(self.linea, 0, Qt.AlignVCenter)
        self.layout.addStretch(1)
        self.idioma: QComboBox | None = None
        if con_idioma:
            self.idioma = QComboBox()
            self.idioma.setCursor(Qt.PointingHandCursor)
            # Que las flechas y los números sean de la pantalla, no del idioma.
            self.idioma.setFocusPolicy(Qt.ClickFocus)
            for codigo, nombre in i18n.LANGS.items():
                self.idioma.addItem(f"{i18n.LANG_FLAGS.get(codigo, '')}  {nombre}", codigo)
            self.idioma.setCurrentIndex(max(0, self.idioma.findData(i18n.lang)))
            self.idioma.setStyleSheet(qss_idioma(c))
            self.layout.addWidget(self.idioma, 0, Qt.AlignVCenter)


class Tarjeta(QFrame):
    """Una opción: su nombre, una línea que la explica y la tecla que la
    elige."""

    def __init__(self, tecla: str, colors: AppColors, parent=None) -> None:
        super().__init__(parent)
        self._c = colors
        self.elegida = False
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.setFixedHeight(168)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(8)

        cabeza = QHBoxLayout()
        cabeza.setSpacing(8)
        self.titulo = QLabel()
        cabeza.addWidget(self.titulo)
        cabeza.addStretch(1)
        self.tecla = QLabel(tecla)
        self.tecla.setAlignment(Qt.AlignCenter)
        self.tecla.setFixedSize(22, 22)
        cabeza.addWidget(self.tecla)
        lay.addLayout(cabeza)

        self.subtitulo = QLabel()
        self.subtitulo.setWordWrap(True)
        self.subtitulo.setTextFormat(Qt.PlainText)
        lay.addWidget(self.subtitulo)
        lay.addStretch(1)
        self._pintar()

    def poner_textos(self, titulo: str, subtitulo: str) -> None:
        self.titulo.setText(titulo)
        self.subtitulo.setText(subtitulo)
        self._pintar()

    def marcar(self, elegida: bool) -> None:
        self.elegida = elegida
        self._pintar()

    def _pintar(self) -> None:
        c = self._c
        titulo = c.accent if self.elegida else c.text
        self.titulo.setStyleSheet(f"color:{titulo};font-size:17px;font-weight:600;"
                                  "letter-spacing:0.5px;background:transparent;border:none;")
        self.subtitulo.setStyleSheet(f"color:{c.text};font-size:13px;"
                                     "background:transparent;border:none;")
        self.tecla.setStyleSheet(
            f"color:{c.accent if self.elegida else c.muted};font-size:11px;font-weight:600;"
            f"background:transparent;border:1px solid {c.accent if self.elegida else c.border};"
            "border-radius:5px;")
        if self.elegida:
            self.setStyleSheet(f"Tarjeta{{background:{c.panel};"
                               f"border:1px solid {c.accent};border-radius:12px;}}")
        else:
            self.setStyleSheet(f"Tarjeta{{background:transparent;"
                               f"border:1px solid {c.border};border-radius:12px;}}"
                               f"Tarjeta:hover{{border:1px solid {c.muted};}}")

    def mousePressEvent(self, event) -> None:  # noqa: ARG002
        self.clicked()

    def clicked(self) -> None:
        """Lo asigna la pantalla."""
