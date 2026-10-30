"""Annotation log compacto, para vigilar el avance de un vistazo.

La tabla completa esta en su ventana y tiene las veintiocho columnas, que
es lo que hace falta para revisar y corregir. Esto va al lado de las
tecnicas, donde ya esta la mirada mientras se anota, y responde a otra
pregunta: por donde voy y si va cuadrando.

Cada entrada se pinta a mano en vez de como texto plano porque en esta
anchura hay que alinear columnas y meter distintivos, y con una cadena de
texto no se puede: las tecnicas tienen nombres de largo muy distinto y
todo bailaria.
"""

from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMenu, QStyle,
                               QStyledItemDelegate, QVBoxLayout, QWidget)

from karlos_core.models.technique import AppColors


def _rotulo_de_fase(estado: str) -> str:
    """El nombre que le da el deporte: el karate llama «preparatory» a lo
    que el taekwondo llama «non-fighting» (decisión 0008). Sin esto, el
    panel decía una palabra y el registro otra."""
    from karlos_core.tiempo_movimiento import rotulo_de_fase
    return rotulo_de_fase(estado)
from karlos_core.utils.i18n import I18n

DATOS = Qt.UserRole + 1

ALTO_FILA = 40
BARRA = 3          # franja de color del atleta, a la izquierda
MARGEN = 8

# Las categorias no caben enteras y hacen falta: el criterio es anotarlo
# todo, asi que lo que dice si el registro va cuadrando es la mezcla.
CATEGORIA = {"ATTACK": "ATAQUE", "DEFENSE": "DEFESA", "TACTICS": "TÁCTICA",
             "REFEREE STOP": "ÁRBITRO", "PENALTY": "PENALIZAÇÃO", "PHASE": "FASE"}
# Las fases del tiempo-movimiento, con su color: son del combate, no de un
# atleta, y la franja de la izquierda lo dice.
COLOR_FASE = {"fighting": "#F58732", "non_fighting": "#798394", "stoppage": "#3866C2"}

def _categoria(cat: str) -> str:
    """El rotulo de la categoria: el del deporte si lo trae (el taekwondo
    los tiene en portugues), si no el de siempre."""
    from karlos_core.utils.i18n import I18n
    if not cat:
        return ""
    clave = "log.cat." + cat.lower().replace(" ", "_")
    texto = I18n().t(clave)
    return texto if texto != clave else CATEGORIA.get(cat, cat.title())


PUNTUACION = {"IPPON": "IPPON", "WAZA": "WAZA-ARI", "WAZA-ARI": "WAZA-ARI",
              "YUKO": "YUKO", "FOUL": "FALTA"}


class _Pintor(QStyledItemDelegate):
    """Dibuja cada entrada: orden, tecnica, distintivo y contexto."""

    def __init__(self, colors: AppColors, parent=None) -> None:
        super().__init__(parent)
        self._c = colors

    def sizeHint(self, option, index) -> QSize:  # noqa: ARG002
        return QSize(0, ALTO_FILA)

    def _color_marca(self, score: str) -> Optional[str]:
        c = self._c
        return {"IPPON": c.green, "WAZA": c.accent, "WAZA-ARI": c.accent,
                "YUKO": c.yellow, "FOUL": c.aka}.get(score.upper())

    def paint(self, p: QPainter, option, index) -> None:
        d = index.data(DATOS) or {}
        c = self._c
        r = option.rect
        p.save()
        p.setRenderHint(QPainter.Antialiasing)

        seleccion = bool(option.state & QStyle.State_Selected)
        fondo = QColor(c.border) if seleccion else QColor(c.panel if index.row() % 2 else c.background)
        p.fillRect(r, fondo)

        # franja del atleta: dice de quien es sin gastar una columna
        color_at = COLOR_FASE.get(d.get("fase", ""), None) or (
            c.aka if d.get("athlete") == "AKA" else (
                c.ao if d.get("athlete") == "AO" else c.muted))
        p.fillRect(QRect(r.left(), r.top() + 2, BARRA, r.height() - 4), QColor(color_at))

        x = r.left() + BARRA + MARGEN
        ancho = r.width() - (x - r.left()) - MARGEN

        # ── linea 1: numero de orden, tecnica y puntuacion ──
        f_num = QFont(option.font)
        f_num.setPointSizeF(max(8.0, option.font.pointSizeF() - 1.5))
        p.setFont(f_num)
        num = f"{d.get('orden', 0)}"
        ancho_num = max(20, p.fontMetrics().horizontalAdvance("999"))
        p.setPen(QPen(QColor(c.muted)))
        p.drawText(QRect(x, r.top() + 4, ancho_num, 15), Qt.AlignLeft | Qt.AlignVCenter, num)

        marca = PUNTUACION.get((d.get("score") or "").upper(), "")
        ancho_marca = 0
        if marca:
            col = self._color_marca(d.get("score") or "") or c.muted
            f_m = QFont(option.font)
            f_m.setPointSizeF(max(7.5, option.font.pointSizeF() - 2.5))
            f_m.setBold(True)
            p.setFont(f_m)
            ancho_marca = p.fontMetrics().horizontalAdvance(marca) + 10
            caja = QRect(r.right() - MARGEN - ancho_marca, r.top() + 5, ancho_marca, 15)
            p.setPen(Qt.NoPen)
            fondo_m = QColor(col)
            fondo_m.setAlpha(46)
            p.setBrush(fondo_m)
            p.drawRoundedRect(caja, 3, 3)
            p.setPen(QPen(QColor(col)))
            p.drawText(caja, Qt.AlignCenter, marca)

        f_t = QFont(option.font)
        f_t.setPointSizeF(max(9.0, option.font.pointSizeF() - 0.5))
        p.setFont(f_t)
        p.setPen(QPen(QColor(c.text)))
        x_tec = x + ancho_num + 6
        ancho_tec = ancho - ancho_num - 6 - (ancho_marca + 6 if marca else 0)
        tecnica = p.fontMetrics().elidedText(
            d.get("technique") or "—", Qt.ElideRight, max(20, ancho_tec))
        p.drawText(QRect(x_tec, r.top() + 4, max(20, ancho_tec), 15),
                   Qt.AlignLeft | Qt.AlignVCenter, tecnica)

        # ── linea 2: minuto, categoria, nivel y duracion ──
        f_c = QFont(option.font)
        f_c.setPointSizeF(max(7.5, option.font.pointSizeF() - 2.5))
        p.setFont(f_c)
        p.setPen(QPen(QColor(c.muted)))
        partes = [d.get("reloj", ""), d.get("categoria", "")]
        if d.get("level"):
            partes.append(d["level"])
        if d.get("dur"):
            partes.append(d["dur"])
        pie = p.fontMetrics().elidedText(
            "  ·  ".join(x for x in partes if x), Qt.ElideRight, max(20, ancho))
        p.drawText(QRect(x, r.top() + 20, ancho, 14), Qt.AlignLeft | Qt.AlignVCenter, pie)

        p.setPen(QPen(QColor(c.border)))
        p.drawLine(r.left() + BARRA, r.bottom(), r.right(), r.bottom())
        p.restore()


class LogCompacto(QWidget):
    """Annotation log breve, con el orden de cada accion."""

    fila_pedida = Signal(int)          # indice del registro
    editar_pedida = Signal(int)        # abrir la ficha
    borrar_pedida = Signal(int)        # quitar la anotacion
    tabla_pedida = Signal()            # abrir la tabla de 28 columnas
    limpiar_pedida = Signal()          # tirar todo lo anotado del combate

    def __init__(self, colors: AppColors, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Técnico-táctico del taekwondo: la acción es un evento y su «0,0 s»
        # no dice nada; el controlador lo apaga (Johan, 8-10-2026).
        self._sin_duracion = False
        self._c = colors
        self._build()

    def _build(self) -> None:
        c = self._c
        self.setAutoFillBackground(True)
        self.setStyleSheet(f"background:{c.panel};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 6)
        lay.setSpacing(4)

        cab = QHBoxLayout()
        cab.setContentsMargins(2, 0, 2, 0)
        from karlos_core.utils.i18n import I18n
        titulo = QLabel(I18n().t("log.titulo"))
        self._titulo = titulo
        titulo.setStyleSheet(
            f"color:{c.text};font-size:10px;font-weight:700;"
            "letter-spacing:1.2px;background:transparent;border:none;")
        self._cuenta = QLabel("")
        self._cuenta.setAlignment(Qt.AlignRight)
        self._cuenta.setStyleSheet(
            f"color:{c.muted};font-size:10px;background:transparent;border:none;")
        cab.addWidget(titulo)
        cab.addStretch(1)
        cab.addWidget(self._cuenta)
        lay.addLayout(cab)

        self._lista = QListWidget()
        self._lista.setItemDelegate(_Pintor(c, self._lista))
        self._lista.setSelectionMode(QAbstractItemView.SingleSelection)
        self._lista.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._lista.setUniformItemSizes(True)
        self._lista.setSpacing(0)
        self._lista.setStyleSheet(
            f"QListWidget{{background:{c.background};border:1px solid {c.border};"
            "border-radius:5px;outline:none;}"
            "QListWidget::item{border:none;}"
            "QScrollBar:vertical{width:9px;background:transparent;margin:2px;}"
            f"QScrollBar::handle:vertical{{background:{c.border};border-radius:4px;"
            "min-height:26px;}"
            f"QScrollBar::handle:vertical:hover{{background:{c.muted};}}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        self._lista.itemClicked.connect(self._al_pulsar)
        self._lista.itemDoubleClicked.connect(self._al_doble_pulsar)
        self._lista.setContextMenuPolicy(Qt.CustomContextMenu)
        self._lista.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self._lista, stretch=1)

    # ── datos ────────────────────────────────────────────────────────
    def set_registros(self, registros: Sequence, fps: float,
                      solo_atleta: Optional[str] = None) -> None:
        """Repinta la lista entera. Son cientos de filas, no miles.

        Con ``solo_atleta`` enseña solo las de ese atleta (la pasada de fases
        del tiempo-movimiento: cada luchador por separado, Johan 12-10-2026);
        cada fila sigue apuntando a su registro de verdad."""
        from karlos_core.utils.i18n import I18n as _I18n
        from karlos_core import catalogo as _cat
        self._titulo.setText(_I18n().t("log.titulo") + (f"  ·  {_cat.etiqueta(solo_atleta)}"
                                                         if solo_atleta else ""))
        self._lista.clear()
        fps = fps if fps and fps > 0 else 30.0
        aka = ao = 0
        reparto: dict[str, int] = {}
        for i, r in enumerate(registros):
            atleta = getattr(r, "athlete", "") or ""
            if atleta == "AKA":
                aka += 1
            elif atleta == "AO":
                ao += 1
            cat = getattr(r, "category", "") or ""
            reparto[cat] = reparto.get(cat, 0) + 1
            if solo_atleta and atleta != solo_atleta:
                continue
            it = QListWidgetItem()
            it.setData(Qt.UserRole, i)
            it.setData(DATOS, self._datos(r, i, fps))
            self._lista.insertItem(0, it)          # lo ultimo, arriba
        # Con el nombre de cada competidor: en taekwondo el recuento decía
        # «AKA 3  AO 0» (decisión 0007, el código del formato no se enseña).
        from karlos_core import catalogo
        self._cuenta.setText(
            f"{len(registros)}   ·   {catalogo.etiqueta('AKA')} {aka}  "
            f"{catalogo.etiqueta('AO')} {ao}")
        self.setToolTip(self._resumen(reparto))

    def set_sin_duracion(self, activo: bool) -> None:
        """Las filas de acción sin su duración (el técnico-táctico)."""
        self._sin_duracion = bool(activo)

    def _datos(self, r, i: int, fps: float) -> dict:
        seg = int(getattr(r, "f_start", 0) / fps)
        dur = getattr(r, "duration_s", 0.0) or 0.0
        cat = getattr(r, "category", "") or ""
        fase = (getattr(r, "technique", "") or "") if cat == "PHASE" else ""
        abierta = bool(fase) and int(getattr(r, "f_end", 0)) <= int(getattr(r, "f_start", 0))
        return {
            "orden": i + 1,
            "athlete": getattr(r, "athlete", "") or "",
            "technique": (_rotulo_de_fase(fase) if fase else getattr(r, "technique", "") or cat or "—"),
            # Las fases llevan su atleta en el texto: la barra de color es la
            # de la fase y no la del atleta, como en las acciones.
            "categoria": (f"{_categoria(cat)} · {__import__('karlos_core.catalogo', fromlist=['etiqueta']).etiqueta(getattr(r, 'athlete', ''))}"
                          if fase and getattr(r, "athlete", "") else _categoria(cat)),
            "level": getattr(r, "level", "") or "",
            "score": getattr(r, "score", "") or "",
            "reloj": f"{seg // 60:02d}:{seg % 60:02d}",
            "dur": (I18n().t("pro.em_curso") if abierta
                    else "" if (self._sin_duracion and not fase)
                    else (f"{dur:.1f}s" if dur else "")),
            "fase": fase,
        }

    @staticmethod
    def _resumen(reparto: dict) -> str:
        if not reparto:
            return "Sin anotaciones"
        orden = sorted(reparto.items(), key=lambda kv: -kv[1])
        return "\n".join(f"{CATEGORIA.get(k, k or '—')}: {v}" for k, v in orden)

    def _al_pulsar(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.UserRole)
        if idx is not None:
            self.fila_pedida.emit(int(idx))

    def _al_doble_pulsar(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.UserRole)
        if idx is not None:
            self.editar_pedida.emit(int(idx))

    def _menu(self, punto) -> None:
        """Clic derecho: ir, editar o borrar esa anotacion.

        «Ver tabela completa» vive aqui y no en un boton. La tabla de 28
        columnas se mira de higos a brevas —para comprobar una columna
        antes de exportar— y tenerla siempre en la barra costaba un boton
        permanente por un uso ocasional. Sobre el registro breve se
        encuentra sola: es la version larga de lo que ya se esta mirando.

        Con el registro vacio no se abre nada: una tabla sin filas no
        tiene nada que ensenar.
        """
        if self._lista.count() == 0:
            return                      # sin anotaciones no hay nada que ver
        item = self._lista.itemAt(punto)
        idx = item.data(Qt.UserRole) if item is not None else None
        c = self._c
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{c.panel};color:{c.text};border:1px solid {c.border};"
            "border-radius:5px;padding:4px;font-size:12px;}"
            "QMenu::item{padding:5px 18px;border-radius:3px;}"
            f"QMenu::item:selected{{background:{c.border};}}")
        ir = editar = borrar = None
        if idx is not None:
            ir = menu.addAction(I18n().t("log.ir_acao"))
            editar = menu.addAction(I18n().t("log.editar"))
            borrar = menu.addAction(I18n().t("log.excluir"))
            menu.addSeparator()
        tabla = menu.addAction(I18n().t("log.tabela"))
        menu.addSeparator()
        limpiar = menu.addAction(I18n().t("hub.ctx_clear_annotations"))
        elegido = menu.exec(self._lista.mapToGlobal(punto))
        if elegido is None:
            return
        if elegido is limpiar:
            self.limpiar_pedida.emit()
        elif elegido is tabla:
            self.tabla_pedida.emit()
        elif elegido is ir:
            self.fila_pedida.emit(int(idx))
        elif elegido is editar:
            self.editar_pedida.emit(int(idx))
        elif elegido is borrar:
            self.borrar_pedida.emit(int(idx))
