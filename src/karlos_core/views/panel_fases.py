"""Los tres botones del especialista: fighting, non-fighting, stoppage.

Johan, 8-10-2026: «tiene que estar con los botones que recomendó el especialista,
y que se cree el histórico». Así que la columna de la pasada de fases es:

1. La fase que rige ahora, en grande y con su color, con el cronómetro de
   esa fase corriendo.
2. Los tres botones, que se llaman como sus fases —fighting,
   non-fighting, stoppage— con su número (1, 2, 3) y, debajo, qué quiere
   decir cada uno con palabras.
3. Debajo de este panel, el **registro** de siempre, donde cada pulsación
   aparece como una fila (fase, minuto, duración): el histórico, igual que
   las acciones en el técnico-táctico.

Lo demás lo lleva el controlador (``anotador/tiempo_movimiento``).
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from karlos_core.models.fases import FIGHTING, NON_FIGHTING, STOPPAGE, UNOBSERVABLE
from karlos_core.models.technique import AppColors
from karlos_core.utils.i18n import I18n

COLORES = {FIGHTING: "#F58732", NON_FIGHTING: "#798394", STOPPAGE: "#3866C2",
           UNOBSERVABLE: "#8A7462"}


def _estados() -> tuple[str, ...]:
    """Los estados del deporte activo, en su orden: tres en taekwondo y
    cuatro en karate (decisión 0008)."""
    from karlos_core.tiempo_movimiento import estados_activos
    return estados_activos()


def _asaltos_del_deporte() -> int:
    """Cuántos asaltos admite el reglamento del deporte activo."""
    from karlos_core import catalogo
    try:
        return int(catalogo.activo().reglamento.asaltos)
    except Exception:
        return 3


def _teclas() -> dict[str, str]:
    """Estado -> dígito, del deporte activo."""
    from karlos_core.tiempo_movimiento import teclas_de_fase
    return {e: d for d, e in teclas_de_fase().items()}


def _que_es(estado: str) -> str:
    """Qué quiere decir cada fase, en el idioma del programa. El nombre de
    la fase no se traduce; la explicación sí. Cada deporte puede poner la
    suya con la misma clave en sus textos."""
    return I18n().t(f"tm.que_{estado}")


def _nombre(estado: Optional[str]) -> str:
    """La palabra del instrumento, con el nombre que le dé el deporte."""
    if not estado:
        return ""
    from karlos_core.tiempo_movimiento import rotulo_de_fase
    return rotulo_de_fase(estado)


def _reloj(frames: int, fps: float) -> str:
    s = max(0, frames) / max(float(fps), 1.0)
    return f"{int(s // 60)}:{s % 60:04.1f}"


def _reloj_absoluto(frame: int, fps: float) -> str:
    s = max(0, frame) / max(float(fps), 1.0)
    return f"{int(s // 60)}:{int(s % 60):02d}"


class PanelFases(QWidget):
    """La fase que rige y los tres botones."""

    fase_pedida = Signal(str)       # el evaluador pulsó un botón
    quitar_pedido = Signal()        # «retirar a última»
    ir_a = Signal(int)              # (sin uso aquí; lo conserva el controlador)
    # Los asaltos (Johan, 12-10-2026: «piensa bien el sistema para
    # seleccionar el número de rounds y cómo delimitarlos sin fallos»).
    numero_de_asaltos = Signal(int)     # 1, 2 o 3
    asalto_pulsado = Signal(int)        # su pastilla: elegirlo para corregirlo
    inicio_pedido = Signal()            # el botón F
    fin_pedido = Signal()               # el botón G
    borrar_asalto_pedido = Signal(int)

    def __init__(self, colors: AppColors, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._c = colors
        self._botones: dict[str, QPushButton] = {}
        self._build()

    def _build(self) -> None:
        c = self._c
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 6)
        root.setSpacing(8)

        cab = QHBoxLayout()
        titulo = QLabel(I18n().t("tm.titulo"))
        titulo.setStyleSheet(f"color:{c.muted};font-size:11px;font-weight:700;"
                             "letter-spacing:1px;background:transparent;border:none;")
        cab.addWidget(titulo)
        # De qué atleta son las fases: una pasada por competidor.
        self._atleta = QLabel("")
        self._atleta.setStyleSheet(f"color:{c.text};font-size:11px;font-weight:700;"
                                   "background:transparent;border:none;")
        cab.addWidget(self._atleta)
        cab.addStretch(1)
        self._asalto = QLabel("")
        self._asalto.setStyleSheet(f"color:{c.muted};font-size:11px;background:transparent;border:none;")
        cab.addWidget(self._asalto)
        root.addLayout(cab)

        # Cuántos asaltos tiene el combate: 1, 2 o 3, aquí mismo. En un
        # deporte de un solo asalto (el karate: 3 minutos y se acabó) no hay
        # nada que elegir y la fila no sale (decisión 0008).
        self._numeros: dict[int, QPushButton] = {}
        if _asaltos_del_deporte() > 1:
            fila_n = QHBoxLayout()
            fila_n.setSpacing(4)
            etiqueta_n = QLabel(I18n().t("tm.asaltos_del_combate"))
            etiqueta_n.setStyleSheet(f"color:{c.muted};font-size:10px;background:transparent;border:none;")
            fila_n.addWidget(etiqueta_n)
            for n in (1, 2, 3):
                b = QPushButton(str(n))
                b.setFixedSize(30, 22)
                b.setCursor(Qt.PointingHandCursor)
                b.setFocusPolicy(Qt.NoFocus)
                b.clicked.connect(lambda _=False, k=n: self.numero_de_asaltos.emit(k))
                self._numeros[n] = b
                fila_n.addWidget(b)
            fila_n.addStretch(1)
            root.addLayout(fila_n)

        # Los asaltos, uno por pastilla: sin empezar, en curso o cerrado,
        # con su duración. Johan (9-10-2026): «no está tan intuitivo
        # colocar el inicio y el final de los rounds; tiene que aparecer
        # algo que los identifique y que quede claro». Pulsar una pastilla
        # la elige para corregirla (y lleva el vídeo a su inicio).
        self._fila_asaltos = QHBoxLayout()
        self._fila_asaltos.setSpacing(6)
        self._pastillas: list[QPushButton] = []
        root.addLayout(self._fila_asaltos)

        # F y G, también con el ratón, diciendo qué asalto abren o cierran.
        fila_fg = QHBoxLayout()
        fila_fg.setSpacing(6)
        self._boton_f = QPushButton()
        self._boton_g = QPushButton()
        self._boton_borrar = QPushButton()
        for b, senal in ((self._boton_f, self.inicio_pedido), (self._boton_g, self.fin_pedido)):
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setMinimumHeight(26)
            b.clicked.connect(senal.emit)
            fila_fg.addWidget(b, 1)
        self._boton_borrar.setCursor(Qt.PointingHandCursor)
        self._boton_borrar.setFocusPolicy(Qt.NoFocus)
        self._boton_borrar.setMinimumHeight(26)
        self._boton_borrar.clicked.connect(lambda: self.borrar_asalto_pedido.emit(self._elegido))
        fila_fg.addWidget(self._boton_borrar)
        root.addLayout(fila_fg)
        self._elegido = 0
        self._guia = QLabel("")
        self._guia.setWordWrap(True)
        self._guia.setStyleSheet(f"color:{c.accent};font-size:11px;font-weight:700;"
                                 "background:transparent;border:none;")
        root.addWidget(self._guia)

        # 1. La fase que rige, en grande.
        self._tarjeta = QFrame()
        self._tarjeta.setObjectName("tarjetaFase")
        tl = QHBoxLayout(self._tarjeta)
        tl.setContentsMargins(14, 10, 14, 10)
        self._fase_grande = QLabel("—")
        self._fase_grande.setStyleSheet("color:#ffffff;font-size:20px;font-weight:800;"
                                        "letter-spacing:1px;background:transparent;border:none;")
        tl.addWidget(self._fase_grande, 1)
        self._crono = QLabel("0:00.0")
        self._crono.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._crono.setStyleSheet("color:#ffffff;font-size:26px;font-weight:300;"
                                  "background:transparent;border:none;")
        tl.addWidget(self._crono)
        root.addWidget(self._tarjeta)

        # 2. Un botón por estado del deporte, con el nombre de su fase.
        teclas = _teclas()
        for estado in _estados():
            b = QPushButton()
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(52)
            b.setFocusPolicy(Qt.NoFocus)       # las teclas son de la ventana
            b.setText(f"{teclas.get(estado, '')}    {_nombre(estado)}\n       {_que_es(estado)}")
            b.clicked.connect(lambda _=False, e=estado: self.fase_pedida.emit(e))
            self._botones[estado] = b
            root.addWidget(b)

        pie = QLabel(I18n().t("tm.pie") + "  " + I18n().t("tm.pie_atletas"))
        pie.setWordWrap(True)
        pie.setStyleSheet(f"color:{c.muted};font-size:10px;background:transparent;border:none;")
        root.addWidget(pie)
        self._pintar_estado(None)

    # ── Los asaltos ─────────────────────────────────────────────────
    def _pastilla(self, n: int) -> QPushButton:
        boton = QPushButton()
        boton.setMinimumHeight(26)
        boton.setCursor(Qt.PointingHandCursor)
        boton.setFocusPolicy(Qt.NoFocus)
        boton.clicked.connect(lambda _=False, k=n: self.asalto_pulsado.emit(k))
        return boton

    def _estilo_boton(self, boton: QPushButton, activo: bool, color: str) -> None:
        c = self._c
        boton.setEnabled(activo)
        if activo:
            boton.setStyleSheet(f"QPushButton{{background:{c.panel};color:{c.text};"
                                f"border:1px solid {color};border-radius:6px;font-size:11px;"
                                "font-weight:700;padding:2px 8px;}"
                                f"QPushButton:hover{{background:{c.border};}}")
        else:
            boton.setStyleSheet(f"QPushButton{{background:transparent;color:{c.muted};"
                                f"border:1px dashed {c.border};border-radius:6px;font-size:11px;"
                                "padding:2px 8px;}")

    def _pintar_asaltos(self, asaltos: Any, frame: int, fps: float,
                        atleta: str = "", propios: bool = False, elegido: int = 0) -> None:
        """El número de asaltos, una pastilla por asalto —sin empezar, en
        curso, cerrado, o elegido para corregirlo—, los botones F y G con el
        asalto que tocan, y la línea que dice qué hacer."""
        c = self._c
        total = int(getattr(asaltos, "total", 0) or 0) if asaltos is not None else 0
        for n, b in self._numeros.items():
            marcado = n == total
            b.setStyleSheet(f"QPushButton{{background:{c.accent if marcado else 'transparent'};"
                            f"color:{'#000000' if marcado else c.text};border:1px solid "
                            f"{c.accent if marcado else c.border};border-radius:5px;font-size:11px;"
                            "font-weight:700;padding:0px;min-width:26px;max-width:30px;}")
        while len(self._pastillas) < total:
            p = self._pastilla(len(self._pastillas) + 1)
            self._pastillas.append(p)
            self._fila_asaltos.addWidget(p)
        for i, p in enumerate(self._pastillas):
            p.setVisible(i < total)
        self._elegido = elegido if 1 <= elegido <= total else 0
        if total == 0:
            self._guia.setText("")
            for b in (self._boton_f, self._boton_g, self._boton_borrar):
                b.setVisible(False)
            return
        for b in (self._boton_f, self._boton_g):
            b.setVisible(True)
        abierto = next((n for n in range(1, total + 1)
                        if asaltos.inicio(n) is not None and asaltos.fin(n) is None), 0)
        siguiente = next((n for n in range(1, total + 1) if asaltos.inicio(n) is None), 0)
        for n in range(1, total + 1):
            p = self._pastillas[n - 1]
            ini, fin = asaltos.inicio(n), asaltos.fin(n)
            nombre = I18n().t("tm.asalto_corto", n=str(n))
            if ini is not None and fin is not None:
                p.setText(f"{nombre}  ✓ {_reloj(fin - ini + 1, fps)}")
                fondo, borde, color = c.green + "33", c.green, c.text
            elif ini is not None:
                p.setText(f"{nombre}  ● {_reloj(max(0, frame - ini + 1), fps)}")
                fondo, borde, color = c.accent + "33", c.accent, c.text
            else:
                p.setText(f"{nombre}  {I18n().t('tm.asalto_tecla_f')}")
                fondo, borde, color = "transparent", c.border, c.muted
            grosor = 3 if n == self._elegido else 1
            if n == self._elegido:
                borde = "#FFFFFF"
            p.setStyleSheet(f"QPushButton{{background:{fondo};border:{grosor}px solid {borde};"
                            f"border-radius:8px;color:{color};font-size:11px;font-weight:700;"
                            "padding:3px 8px;}")
        t = I18n().t
        if self._elegido:
            n = self._elegido
            self._boton_f.setText(t("tm.boton_mover_inicio", n=str(n)))
            self._boton_g.setText(t("tm.boton_mover_fin", n=str(n)))
            self._boton_borrar.setText(t("tm.boton_borrar", n=str(n)))
            self._estilo_boton(self._boton_f, True, c.accent)
            self._estilo_boton(self._boton_g, asaltos.inicio(n) is not None, c.accent)
            self._estilo_boton(self._boton_borrar, True, c.red if hasattr(c, "red") else "#E5534B")
            self._boton_borrar.setVisible(True)
            self._guia.setText(t("tm.guia_corrigiendo", n=str(n)))
            return
        self._boton_borrar.setVisible(False)
        # El número solo donde hay algo que abrir o cerrar; si no, un guion.
        self._boton_f.setText(t("tm.boton_abrir", n=str(siguiente) if siguiente and not abierto else "–"))
        self._boton_g.setText(t("tm.boton_cerrar", n=str(abierto) if abierto else "–"))
        self._estilo_boton(self._boton_f, bool(siguiente) and not abierto, c.green)
        self._estilo_boton(self._boton_g, bool(abierto), c.accent)
        if abierto:
            self._guia.setText(t("tm.guia_cerrar", n=str(abierto),
                                 desde=_reloj_absoluto(asaltos.inicio(abierto), fps)))
        elif siguiente:
            self._guia.setText(t("tm.guia_abrir", n=str(siguiente), total=str(total)))
        elif propios:
            from karlos_core import catalogo
            self._guia.setText(t("tm.guia_hechos_atleta", total=str(total),
                                 atleta=catalogo.etiqueta(atleta)))
        else:
            self._guia.setText(t("tm.guia_hechos", total=str(total)))

    # ── Pintar ──────────────────────────────────────────────────────
    def _pintar_estado(self, activo: Optional[str]) -> None:
        c = self._c
        color = COLORES.get(activo, c.border)
        self._tarjeta.setStyleSheet(f"QFrame#tarjetaFase{{background:{color};border:none;border-radius:10px;}}")
        self._fase_grande.setText(_nombre(activo) if activo else I18n().t("tm.sin_fase"))
        for estado, b in self._botones.items():
            col = COLORES[estado]
            if estado == activo:
                b.setStyleSheet(f"QPushButton{{background:{col};color:#ffffff;border:none;"
                                "border-radius:10px;font-size:14px;font-weight:700;text-align:left;"
                                "padding:4px 14px;}")
            else:
                b.setStyleSheet(f"QPushButton{{background:{c.panel};color:{c.text};"
                                f"border:2px solid {col};border-radius:10px;font-size:14px;"
                                "font-weight:600;text-align:left;padding:4px 14px;}"
                                f"QPushButton:hover{{background:{c.border};}}")

    def actualizar(self, fases: Any, asaltos: Any, frame: int, fps: float,
                   atleta: str = "", asaltos_propios: bool = False, elegido: int = 0) -> None:
        """Lo que hay, visto desde este fotograma. Se llama a cada fotograma
        y solo repinta dos etiquetas y el color de los botones."""
        from karlos_core import catalogo
        from karlos_core.formato import PRIMERO
        c = self._c
        if atleta:
            self._atleta.setText(f"·  {catalogo.etiqueta(atleta)}")
            self._atleta.setStyleSheet(f"color:{c.aka if atleta == PRIMERO else c.ao};font-size:11px;"
                                       "font-weight:700;background:transparent;border:none;")
        activo = fases.estado_en(frame) if fases is not None else None
        self._pintar_estado(activo)
        self._pintar_asaltos(asaltos, frame, fps, atleta, asaltos_propios, elegido)
        if asaltos is not None:
            n = asaltos.de_fotograma(frame) or asaltos.en_curso
            self._asalto.setText(I18n().t("tm.asalto", n=str(n), total=str(asaltos.total)))
        if fases is None or fases.vacias:
            self._crono.setText("0:00.0")
            return
        desde = max((f for f, _e in fases.marcas if f <= frame), default=None)
        self._crono.setText(_reloj(frame - desde + 1, fps) if desde is not None else "0:00.0")
