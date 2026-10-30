"""Project Hub view — multi-fight session management dashboard.

Displays a fight session table with video metadata, load-folder
and export buttons, per-row Report buttons, a real-time search
filter, status filter chips, summary cards, and progress badges.

v7.0 — Premium interactive Hub with empty-state guidance.
"""

from __future__ import annotations

from typing import Any, Optional

import qtawesome as qta
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from karlos_core.models.technique import AppColors
from karlos_core.views.theme import Palette
from karlos_core import catalogo, identidad
from karlos_core.utils import recientes

_p = Palette()  # module-level defaults for static QSS


class NumericTableItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically by an int stored in UserRole.

    DisplayRole is set to str(value) so text rendering works correctly.
    Qt calls __lt__ for sorting; we compare the int values instead of strings.
    """

    def __init__(self, value: int) -> None:
        super().__init__(str(value))
        self._numeric_value = value

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, NumericTableItem):
            return self._numeric_value < other._numeric_value
        # Fallback: compare display text as strings
        return self.text() < other.text()


class ProjectHubView(QWidget):
    """Fight session management screen (QStackedWidget index 0).

    Signals:
        load_folder_requested: User clicked "Load Video Folder".
        export_dataset_requested: User clicked "Export Unified Dataset".
        session_double_clicked(int): Row index double-clicked.
        session_right_clicked(int): Right-click → View Report.
        session_view_report(int): Per-row report button clicked.
        delete_session_requested(int): Delete action triggered.
    """

    load_folder_requested = Signal()
    load_folder_from_path = Signal(str)       # NEW — drag & drop / open recent
    export_dataset_requested = Signal()
    export_selected_requested = Signal(list)  # NEW — batch export
    session_double_clicked = Signal(int)
    session_right_clicked = Signal(int)
    session_view_report = Signal(int)
    delete_session_requested = Signal(int)
    edit_bout_info_requested = Signal(int)  # NEW — Bout Info button
    compare_evaluators_requested = Signal(int)  # Fase 5 — Compare Evaluators
    round_changed_requested = Signal(int)   # REDISEÑO — Round selector changed
    new_round_requested = Signal()          # REDISEÑO — New evaluation
    manage_rounds_requested = Signal()      # REDISEÑO — Open round management panel
    volver_al_inicio = Signal()             # a la pantalla «¿Qué se analiza?» (decisión 0008)
    cargar_dados = Signal(int)              # abrir un CSV de combate
    marcar_concluido = Signal(int)          # dar por terminado un combate, o no
    borrar_anotaciones = Signal(int)        # tirar lo anotado de un combate

    # ── Column indices (11 columns) ─────────────────────────────
    # Tres columnas se fueron, y las tres por el mismo motivo: no
    # distinguian una fila de otra.
    #   EVENTO      — leia bout_event, vacio en los doce; el evento real
    #                 (WKF Paris 2025) es el mismo para todos y vive en
    #                 la cabecera, no repetido doce veces.
    #   PROGRESSO   — decia «2/2 ✓» al lado de un ESTADO que decia «Em
    #                 progresso». Dos columnas para lo mismo, y ademas
    #                 contradiciendose.
    _ESTILO_MENU = (
        f"QMenu{{background:{_p.surface_2};color:{_p.text_bright};"
        "border:1px solid rgba(255,255,255,0.08);border-radius:8px;"
        "padding:5px;}"
        "QMenu::item{padding:6px 24px 6px 12px;border-radius:5px;}"
        "QMenu::item:selected{background:rgba(255,255,255,0.08);}"
        "QMenu::item:disabled{color:rgba(255,255,255,0.25);}"
        "QMenu::separator{height:1px;background:rgba(255,255,255,0.07);"
        "margin:5px 8px;}"
    )

    COL_ID = 0
    COL_VIDEO = 1
    COL_ATHLETES = 2
    COL_CATEGORY = 3
    COL_DUR = 4
    COL_ANNOTATIONS = 5
    COL_SCORE = 6
    COL_STATUS = 7
    COL_ACTIONS = 8

    _RECENT_KEY = recientes.CLAVE
    # Un icono solo: sin fondo ni borde, se enciende al pasar.
    _ESTILO_ICONO = ("QPushButton{background:transparent;border:none;border-radius:6px;}"
                     "QPushButton:hover{background:rgba(255,255,255,0.06);}"
                     "QPushButton:disabled{background:transparent;}")
    # Los botones de la barra de acciones: solo contorno.
    _ESTILO_BOTON = ("QToolButton{background:transparent;color:#F4F7FB;"
                     "border:1px solid #333B46;border-radius:8px;"
                     "font-size:13px;font-weight:500;padding:5px 12px;}"
                     "QToolButton:hover{border-color:#96A1AF;}")
    _MAX_RECENT = 5

    _STATUS_STYLES: dict[str, dict[str, str]] = {
        "Pending": {"bg": "rgba(255,255,255,0.04)", "fg": None},
        "In Progress": {"bg": "rgba(255,165,0,0.12)", "fg": _p.misc_orange},
        "Completed": {"bg": "rgba(0,200,100,0.12)", "fg": _p.misc_green_bright},
    }

    def __init__(
        self,
        colors: AppColors,
        sport_meta: Optional[dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._colors = colors
        self._sport_meta = sport_meta or {}
        self._sessions: list[Any] = []
        self._active_filter: str = "All"  # "All" | "In Progress" | "Completed"
        self._sort_column: int = -1
        self._sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder

        from karlos_core.utils.i18n import I18n
        self._i18n = I18n()

        self._build_ui()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._table.setFocus()

        # ── Drag & drop support ─────────────────────────────────
        self.setAcceptDrops(True)

        # ── Language change handler ──────────────────────────────
        self._i18n.language_changed.connect(self._refresh_strings)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        c = self._colors
        self.setObjectName("ProjectHub")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"#ProjectHub{{background:{c.background};}}")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Premium Brand Bar ───────────────────────────────────
        brand_bar = QWidget()
        # Sobre el mismo fondo que el resto: la cabecera es una línea, no
        # una barra (Johan, 19-10-2026: «minimalista premium»).
        brand_bar.setStyleSheet(
            f"background:{c.background};"
            f"border-bottom:1px solid {c.border};"
        )
        brand_bar.setFixedHeight(52)
        brand_layout = QHBoxLayout(brand_bar)
        brand_layout.setContentsMargins(24, 8, 24, 8)
        brand_layout.setSpacing(12)

        # Logo + brand text — centerpiece
        import os as _os
        from karlos_core.utils.resource_path import resource_path
        logo_path = str(resource_path(
            "karlos_core", "assets", "logos", "karlitos.png"
        ))
        logo_img = QLabel()
        if _os.path.exists(logo_path):
            from PySide6.QtGui import QPixmap
            pix = QPixmap(logo_path).scaled(
                26, 26,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_img.setPixmap(pix)
        logo_img.setStyleSheet("background:transparent;border:none;")
        # ‹ Inicio: de vuelta a la pantalla «¿Qué se analiza?» para cambiar
        # de modo (Johan, 19-10-2026: los tres botones arriba a la derecha
        # «no deberían estar ahí»). Va delante del logo, donde se busca un
        # «atrás». Sin tiempo-movimiento en el deporte no hay nada que elegir.
        self._btn_inicio = QPushButton(self._i18n.t("analisis.inicio"))
        self._btn_inicio.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_inicio.setToolTip(self._i18n.t("analisis.inicio_tip"))
        self._btn_inicio.setMinimumHeight(28)
        self._btn_inicio.setStyleSheet(
            f"QPushButton{{background:transparent;color:{c.muted};border:none;"
            "font-size:12px;padding:0 8px 0 0;}"
            f"QPushButton:hover{{color:{c.text};}}")
        self._btn_inicio.clicked.connect(self.volver_al_inicio.emit)
        self._btn_inicio.setVisible(bool(catalogo.activo().tiempo_movimiento()))
        brand_layout.addWidget(self._btn_inicio)
        brand_layout.addWidget(logo_img)

        # El nombre de la edición en marcha (decisión 0006), en una línea
        # con el modo en que se está. El deporte y su reglamento ya los
        # dijo la pantalla de inicio: aquí no se repiten.
        self._title_label = QLabel(identidad.en_marcha().nombre.upper())
        self._title_label.setStyleSheet(
            f"color:{c.text};font-size:13px;font-weight:700;"
            "letter-spacing:2px;background:transparent;border:none;"
        )
        brand_layout.addWidget(self._title_label)
        self._etiqueta_analisis = QLabel("")
        self._etiqueta_analisis.setStyleSheet(
            f"color:{c.accent};font-size:11px;font-weight:600;letter-spacing:1.5px;"
            "background:transparent;border:none;padding:0 0 0 8px;")
        self._etiqueta_analisis.setVisible(False)
        brand_layout.addWidget(self._etiqueta_analisis)
        brand_layout.addStretch()

        # ── Pasada activa — antes era una segunda barra entera ────
        #
        # 44 pixeles de alto, cruzando la pantalla, para un desplegable
        # que se toca dos veces en toda la tesis. Lo que hay debajo
        # —los combates— es el motivo de estar aqui, asi que la pasada
        # se viene a la derecha de la cabecera y el sitio se lo queda
        # la tabla.
        etiqueta_pasada = QLabel(self._i18n.t("hub.round_active"))
        etiqueta_pasada.setStyleSheet(
            f"color:{c.muted};font-size:11px;font-weight:500;"
            "background:transparent;border:none;")
        etiqueta_pasada.hide()            # el desplegable ya dice «Passagem 1»
        self._round_label = etiqueta_pasada

        from PySide6.QtWidgets import QComboBox
        self._round_combo = QComboBox()
        self._round_combo.setMinimumWidth(170)
        self._round_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._round_combo.setToolTip(self._i18n.t("hub.round_active"))
        self._round_combo.setStyleSheet(
            f"QComboBox{{background:transparent;color:{c.muted};"
            f"border:none;padding:4px 6px;font-size:12px;}}"
            f"QComboBox:hover{{color:{c.text};}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{"
            f"background:{_p.surface_2};color:{_p.text_bright};"
            f"border:1px solid rgba(255,255,255,0.10);"
            f"border-radius:7px;padding:4px;"
            f"selection-background-color:rgba(255,255,255,0.08);}}"
        )
        self._round_combo.currentIndexChanged.connect(self._on_round_combo_changed)
        brand_layout.addWidget(self._round_combo)

        self._new_round_btn = QPushButton()
        self._new_round_btn.setIcon(qta.icon("fa5s.plus", color=c.yellow))
        self._new_round_btn.setToolTip(self._i18n.t("hub.round_new"))
        self._new_round_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_round_btn.setFixedSize(28, 28)
        self._new_round_btn.setStyleSheet(self._ESTILO_ICONO)
        self._new_round_btn.clicked.connect(self.new_round_requested.emit)
        brand_layout.addWidget(self._new_round_btn)

        self._manage_btn = QPushButton()
        self._manage_btn.setIcon(qta.icon("fa5s.cog", color=c.muted))
        self._manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._manage_btn.setToolTip(self._i18n.t("hub.round_manage"))
        self._manage_btn.setFixedSize(28, 28)
        self._manage_btn.setStyleSheet(self._ESTILO_ICONO)
        self._manage_btn.clicked.connect(self.manage_rounds_requested.emit)
        brand_layout.addWidget(self._manage_btn)

        self._analisis_elegido = "complete"


        root.addWidget(brand_bar)

        # ── Content area ────────────────────────────────────────
        content = QVBoxLayout()
        content.setContentsMargins(24, 16, 24, 20)
        content.setSpacing(12)

        # ── Barra de acciones: dos botones, los filtros y el buscador ──
        #
        # Habia cinco tarjetas de resumen (TOTAL / CONCLUÍDOS / EM
        # PROGRESSO / PENDENTES / ANOTAÇÕES), tres chips de filtro y un
        # pie que repetia los mismos numeros por tercera vez. Ahora los
        # numeros viven en los chips, que es donde ademas sirven para
        # algo: se pulsan.
        #
        # Y de seis botones quedan dos. «Recente» era el desplegable de
        # «Carregar pasta» puesto aparte, y «Exportar Selecionados» lo
        # mismo con «Exportar Dataset»: cada par es un boton con su
        # menu. «Info do Combate» y «Compare Evaluators» actuan sobre
        # UN combate, asi que su sitio es el menu del clic derecho,
        # sobre el combate en cuestion, y no una barra que obliga a
        # seleccionar primero y pulsar despues.
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        from PySide6.QtWidgets import QToolButton

        self._load_btn = QToolButton()
        self._load_btn.setText(self._i18n.t("hub.load_folder"))
        self._load_btn.setIcon(qta.icon("fa5s.folder-open", color=c.muted))
        self._load_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._load_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._load_btn.setMinimumHeight(34)
        self._load_btn.setStyleSheet(self._ESTILO_BOTON + "QToolButton::menu-button{border:none;width:16px;}")
        self._load_btn.clicked.connect(self.load_folder_requested.emit)
        self._recent_menu = QMenu(self)
        self._recent_menu.setStyleSheet(self._ESTILO_MENU)
        self._recent_menu.aboutToShow.connect(self._populate_recent_menu)
        self._load_btn.setMenu(self._recent_menu)
        action_bar.addWidget(self._load_btn)

        self._export_btn = QToolButton()
        self._export_btn.setText(self._i18n.t("hub.export"))
        self._export_btn.setIcon(qta.icon("fa5s.file-export", color=c.muted))
        self._export_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._export_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.setMinimumHeight(34)
        self._export_btn.setStyleSheet(self._ESTILO_BOTON + "QToolButton::menu-indicator{width:0px;}")
        menu_export = QMenu(self)
        menu_export.setStyleSheet(self._ESTILO_MENU)
        self._acc_export_todo = menu_export.addAction(
            self._i18n.t("hub.export_dataset"))
        self._acc_export_todo.triggered.connect(
            self.export_dataset_requested.emit)
        self._acc_export_sel = menu_export.addAction(
            self._i18n.t("hub.export_selected"))
        self._acc_export_sel.setEnabled(False)
        self._acc_export_sel.triggered.connect(self._emit_export_selected)
        self._export_btn.setMenu(menu_export)
        action_bar.addWidget(self._export_btn)

        action_bar.addStretch()

        # ── Filtros, con el recuento dentro ──────────────────────
        self._chip_all = self._make_filter_chip(
            self._i18n.t("hub.status_all"), True, "All")
        self._chip_in_progress = self._make_filter_chip(
            self._i18n.t("hub.status_in_progress"), False, "In Progress")
        self._chip_pending = self._make_filter_chip(
            self._i18n.t("hub.status_pending"), False, "Pending")
        self._chip_completed = self._make_filter_chip(
            self._i18n.t("hub.status_completed"), False, "Completed")
        for chip in (self._chip_all, self._chip_in_progress,
                     self._chip_pending, self._chip_completed):
            action_bar.addWidget(chip)

        action_bar.addStretch()

        # ── Search ───────────────────────────────────────────────
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(
            self._i18n.t("hub.search_placeholder")
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumWidth(200)
        self._search_input.setMaximumWidth(260)
        self._search_input.setMinimumHeight(34)
        self._search_input.setCursor(Qt.CursorShape.IBeamCursor)
        self._search_input.addAction(
            qta.icon("fa5s.search", color=c.muted),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search_input.setStyleSheet(
            f"QLineEdit{{background:transparent;color:{c.text};"
            f"border:1px solid {c.border};border-radius:8px;"
            f"padding:5px 10px 5px 8px;font-size:13px;}}"
            f"QLineEdit:focus{{border:1px solid {c.muted};}}"
            f"QLineEdit::placeholder{{color:{c.muted};}}"
        )
        self._search_input.textChanged.connect(self._apply_all_filters)
        action_bar.addWidget(self._search_input)
        content.addLayout(action_bar)

        # ── Stacked widget: Empty state ↔ Table ─────────────────
        self._content_stack = QStackedWidget()

        # Page 0: Empty state
        self._empty_page = self._build_empty_state()
        self._content_stack.addWidget(self._empty_page)

        # Page 1: Table
        self._table_page = QWidget()
        table_layout = QVBoxLayout(self._table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self._table = QTableWidget(0, 9)
        self._refresh_table_headers()
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(self.COL_ID, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_VIDEO, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_ATHLETES, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_CATEGORY, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_DUR, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_ANNOTATIONS, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_SCORE, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.ResizeMode.Fixed)

        self._table.setColumnWidth(self.COL_ID, 52)
        self._table.setColumnWidth(self.COL_VIDEO, 96)
        self._table.setColumnWidth(self.COL_CATEGORY, 92)
        self._table.setColumnWidth(self.COL_DUR, 84)
        self._table.setColumnWidth(self.COL_ANNOTATIONS, 104)
        self._table.setColumnWidth(self.COL_SCORE, 104)
        self._table.setColumnWidth(self.COL_STATUS, 130)
        self._table.setColumnWidth(self.COL_ACTIONS, 84)
        self._table.verticalHeader().setDefaultSectionSize(44)
        # El orden de carga ya lo da la fila; el combate se reconoce por su
        # ID. La columna sigue existiendo (ordena por ella) pero no se ve.
        self._table.setColumnHidden(self.COL_ID, True)

        self._table.itemDoubleClicked.connect(self._on_item_double_clicked)

        # ── Sortable columns ────────────────────────────────────
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)

        # Sin caja: filas separadas por una línea apenas visible sobre el
        # mismo fondo, y la cabecera como texto pequeño.
        self._table.setStyleSheet(
            f"QTableWidget{{background:{c.background};"
            f"alternate-background-color:{c.background};"
            f"color:{c.text};border:none;"
            f"gridline-color:transparent;font-size:13px;}}"
            f"QTableWidget::item{{padding:0 6px;"
            f"border-bottom:1px solid {c.border};}}"
            f"QTableWidget::item:selected{{"
            f"background:rgba(255,255,255,0.06);color:{c.text};}}"
            "QTableWidget::item:focus{background:transparent;border-bottom:1px solid "
            f"{c.border};}}"
            f"QHeaderView::section{{background:{c.background};"
            f"color:{c.muted};font-size:10px;font-weight:600;"
            f"letter-spacing:1px;text-transform:uppercase;"
            f"padding:8px 6px;border:none;"
            f"border-bottom:1px solid {c.border};}}"
        )
        # Track selection changes to update Export Selected button
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        table_layout.addWidget(self._table)
        self._content_stack.addWidget(self._table_page)
        content.addWidget(self._content_stack, stretch=1)

        root.addLayout(content, stretch=1)

    # ------------------------------------------------------------------
    # Empty State
    # ------------------------------------------------------------------

    def _build_empty_state(self) -> QWidget:
        """Build an empty-state placeholder that guides the user."""
        c = self._colors
        page = QWidget()
        page.setStyleSheet(f"background:{c.background};border:none;")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        self._empty_heading = QLabel(self._i18n.t("hub.empty_heading"))
        self._empty_heading.setStyleSheet(
            f"color:{c.text};font-size:16px;font-weight:600;"
            "background:transparent;border:none;"
        )
        self._empty_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_heading)

        self._empty_hint = QLabel(self._i18n.t("hub.empty_hint"))
        self._empty_hint.setStyleSheet(
            f"color:{c.muted};font-size:13px;background:transparent;border:none;"
        )
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_hint)

        self._empty_formats = QLabel(self._i18n.t("hub.empty_formats"))
        self._empty_formats.setStyleSheet(
            f"color:{c.muted};font-size:11px;"
            "background:transparent;border:none;padding-top:8px;"
        )
        self._empty_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_formats)

        return page

    # ------------------------------------------------------------------
    # Summary cards
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Filter chips
    # ------------------------------------------------------------------

    def _make_filter_chip(self, text: str, active: bool, canonical_label: str) -> QPushButton:
        """Build a toggle-style filter chip button."""
        c = self._colors
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(30)
        self._style_chip(btn, active)
        btn.clicked.connect(lambda: self._on_chip_toggled(canonical_label, btn))
        return btn

    def _style_chip(self, btn: QPushButton, active: bool) -> None:
        """Apply active / inactive styles to a filter chip."""
        c = self._colors
        if active:
            btn.setStyleSheet(
                f"QPushButton{{background:rgba(255,255,255,0.08);"
                f"color:{c.text};border:none;"
                "border-radius:15px;font-size:12px;font-weight:600;"
                "padding:4px 14px;}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{c.muted};"
                f"border:none;border-radius:15px;"
                "font-size:12px;font-weight:500;padding:4px 14px;}"
                f"QPushButton:hover{{color:{c.text};}}"
            )

    def _on_chip_toggled(self, canonical_label: str, sender: QPushButton) -> None:
        """Handle filter chip toggling — only one active at a time."""
        if self._active_filter == canonical_label:
            sender.setChecked(True)
            return
        self._active_filter = canonical_label
        for chip, name in [
            (self._chip_all, "All"),
            (self._chip_in_progress, "In Progress"),
            (self._chip_pending, "Pending"),
            (self._chip_completed, "Completed"),
        ]:
            chip.setChecked(name == canonical_label)
            self._style_chip(chip, name == canonical_label)
        self._apply_all_filters(self._search_input.text())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_sessions(self, sessions: list[Any]) -> None:
        """Llenar la tabla y el recuento de los filtros."""
        self._sessions = sessions
        self._update_summary_cards()

        if not sessions:
            self._content_stack.setCurrentIndex(0)  # empty state
            self._table.setRowCount(0)
            return

        self._content_stack.setCurrentIndex(1)  # table
        # ── Disable sorting during full repopulation to prevent blank cells ──
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._table.setRowCount(len(sessions))

        for row, session in enumerate(sessions):
            meta = getattr(session, "bout_metadata", None) or {}
            annotations: list = getattr(session, "annotations", []) or []

            # ── # ────────────────────────────────────────────────
            id_item = NumericTableItem(session.id)
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self.COL_ID, id_item)

            # ── VIDEO ────────────────────────────────────────────
            # Solo el ID. El nombre entero repetia el peso y el genero,
            # que ya tienen su columna, y los apellidos, que estan al
            # lado: «ID25_-50KG_FEMALE_E.COLLETI ITA X B. IZAGUIRRE .mp4»
            # en una fila donde ya pone «-50 kg» y «E. COLLETTI vs G.
            # IZAGUIRRE». El nombre completo sigue en el tooltip.
            video_item = QTableWidgetItem(self._id_corto(session.video_name))
            video_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            video_item.setToolTip(session.video_name)
            self._table.setItem(row, self.COL_VIDEO, video_item)

            # ── ATHLETES ─────────────────────────────────────────
            aka_name = meta.get("athlete_a_name", "AKA")
            ao_name = meta.get("athlete_b_name", "AO")
            athletes_text = (
                f"{aka_name}  vs  {ao_name}"
                if (aka_name != "AKA" or ao_name != "AO")
                else "—"
            )
            athletes_item = QTableWidgetItem(athletes_text)
            athletes_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self.COL_ATHLETES, athletes_item)

            # ── CATEGORY ─────────────────────────────────────────
            category_text = meta.get("weight_category", "") or "—"
            category_item = QTableWidgetItem(category_text)
            category_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self.COL_CATEGORY, category_item)

            # ── DURATION ─────────────────────────────────────────
            dur_text = self._format_duration(session.duration_s)
            dur_item = QTableWidgetItem(dur_text)
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self.COL_DUR, dur_item)

            # ── ANNOTATIONS count ────────────────────────────────
            ann_count = len(annotations)
            ann_item = QTableWidgetItem(str(ann_count))
            ann_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # Donde el deporte hace tiempo-movimiento, el análisis del
            # combate va al lado: un combate es de un solo análisis y
            # conviene verlo antes de abrirlo (Johan, 8-10-2026).
            sigla = self._sigla_analisis(meta.get("analysis", ""))
            if sigla:
                ann_item.setText(f"{ann_count}  {sigla[0]}")
                ann_item.setToolTip(sigla[1])
            if ann_count > 0:
                ann_item.setForeground(QColor(self._colors.text))
            else:
                ann_item.setForeground(QColor("rgba(255,255,255,0.20)"))
            self._table.setItem(row, self.COL_ANNOTATIONS, ann_item)

            # ── SCORE summary (e.g. "3–1 AKA") ──────────────────
            puntos = catalogo.activo().reglamento.puntos
            aka_score = sum(
                puntos(a.score)
                for a in annotations
                if getattr(a, "athlete", "") == "AKA"
            )
            ao_score = sum(
                puntos(a.score)
                for a in annotations
                if getattr(a, "athlete", "") == "AO"
            )
            if aka_score + ao_score > 0:
                # El color ya dice quién gana: sin flecha.
                if aka_score > ao_score:
                    score_text = f"{aka_score}–{ao_score}  AKA"
                    score_color = self._colors.aka
                elif ao_score > aka_score:
                    score_text = f"{aka_score}–{ao_score}  AO"
                    score_color = _p.ao_dark
                else:
                    score_text = f"{aka_score}–{ao_score} ="
                    score_color = self._colors.muted
            else:
                score_text = "—"
                score_color = "rgba(255,255,255,0.18)"

            score_item = QTableWidgetItem(score_text)
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            score_item.setForeground(QColor(score_color))
            self._table.setItem(row, self.COL_SCORE, score_item)

            # ── STATUS (with quality validation) ─────────────────
            needs_review = (
                session.status == "Completed"
                and getattr(session, "_needs_review_reasons", None)
            )
            if needs_review:
                status_display = f"{self._texto_estado('Completed')} ⚠"
                status_bg = "rgba(255,193,7,0.15)"
                status_fg = _p.accent
            else:
                status_display = self._texto_estado(session.status)
                style = self._STATUS_STYLES.get(session.status, self._STATUS_STYLES["Pending"])
                status_bg = style["bg"]
                status_fg = style["fg"] if style["fg"] else self._colors.muted

            status_item = QTableWidgetItem(status_display)
            status_item.setData(Qt.ItemDataRole.UserRole, session.status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # Solo el color del texto: la pastilla de fondo era ruido.
            del status_bg
            status_item.setForeground(QColor(status_fg))

            # Tooltip with specific reasons
            if needs_review:
                reasons = getattr(session, "_needs_review_reasons", [])
                tooltip = "⚠ Quality checks failed:\n" + "\n".join(f"  • {r}" for r in reasons)
                status_item.setToolTip(tooltip)

            self._table.setItem(row, self.COL_STATUS, status_item)

            # ── Acciones: ver el relatorio y abrir el combate ────
            #
            # Dos arreglos aqui. El de abrir estaba apagado cuando el
            # combate era «Pendente» — justo los que hay que abrir,
            # porque abrirlos es como dejan de estar pendientes. Solo
            # no se notaba porque antes todo salia «Completed».
            #
            # Y los botones apagados no llevaban hoja de estilo, asi
            # que caian al boton gris del sistema: una fila con datos y
            # otra sin ellos se veian distintas por un descuido, no por
            # lo que decian.
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(4)
            actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            estilo_icono = (
                "QPushButton{background:transparent;border:none;padding:2px;}"
                "QPushButton:enabled:hover{background:rgba(255,255,255,0.08);"
                "border-radius:5px;}"
            )
            tiene_datos = len(annotations) > 0

            report_btn = QPushButton()
            report_btn.setToolTip(self._i18n.t("hub.tt_report"))
            report_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            report_btn.setFlat(True)
            report_btn.setStyleSheet(estilo_icono)
            report_btn.setIconSize(report_btn.iconSize().scaled(
                15, 15, Qt.AspectRatioMode.KeepAspectRatio))
            report_btn.setEnabled(tiene_datos)
            report_btn.setIcon(qta.icon(
                "fa5s.chart-bar",
                color=self._colors.muted if tiene_datos
                else "rgba(255,255,255,0.10)"))
            report_btn.clicked.connect(
                lambda checked=None, r=row: self.session_view_report.emit(r)
            )
            actions_layout.addWidget(report_btn)

            edit_btn = QPushButton()
            edit_btn.setToolTip(self._i18n.t("hub.tt_open"))
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setFlat(True)
            edit_btn.setStyleSheet(estilo_icono)
            edit_btn.setIconSize(edit_btn.iconSize().scaled(
                15, 15, Qt.AspectRatioMode.KeepAspectRatio))
            edit_btn.setIcon(qta.icon("fa5s.edit", color=self._colors.muted))
            edit_btn.clicked.connect(
                lambda checked=None, r=row: self.session_double_clicked.emit(r)
            )
            actions_layout.addWidget(edit_btn)

            self._table.setCellWidget(row, self.COL_ACTIONS, actions_widget)

        self._apply_all_filters(self._search_input.text())
        # ── Re-enable sorting after full repopulation ──
        self._table.setSortingEnabled(True)
        # ── Default sort: ascending by # column (1, 2, 3...) ──
        if self._sort_column < 0:
            self._sort_column = self.COL_ID
            self._sort_order = Qt.SortOrder.AscendingOrder
        self._table.sortItems(self._sort_column, self._sort_order)
        # Sin celda «actual»: Qt la pintaba con un recuadro claro en la
        # primera fila aunque nadie la hubiera elegido.
        self._table.setCurrentItem(None)
        # ── Force full viewport repaint to fix lazy-render blank cells ──
        self._table.viewport().update()
        self._table.repaint()

    def refresh_table(self) -> None:
        """Refresh the table and summary from cached sessions."""
        self.set_sessions(self._sessions)

    # ------------------------------------------------------------------
    # Summary cards & footer
    # ------------------------------------------------------------------

    def _update_summary_cards(self) -> None:
        """Escribir el recuento dentro de cada filtro.

        Antes esto llenaba cinco tarjetas que ocupaban una fila entera
        para decir lo que ahora dicen los propios botones del filtro,
        que ademas se pulsan.
        """
        total = len(self._sessions)
        cuenta = {
            "All": total,
            "In Progress": sum(1 for x in self._sessions
                               if x.status == "In Progress"),
            "Completed": sum(1 for x in self._sessions
                             if x.status == "Completed"),
        }
        cuenta["Pending"] = total - cuenta["In Progress"] - cuenta["Completed"]
        for chip, clave, etiqueta in (
                (self._chip_all, "All", "hub.status_all"),
                (self._chip_in_progress, "In Progress", "hub.status_in_progress"),
                (self._chip_pending, "Pending", "hub.status_pending"),
                (self._chip_completed, "Completed", "hub.status_completed")):
            n = cuenta[clave]
            chip.setText(f"{self._i18n.t(etiqueta)}  {n}" if n else
                         self._i18n.t(etiqueta))
            # Un filtro que no puede ensenar nada no se ofrece.
            chip.setEnabled(bool(n) or clave == "All")

    # ------------------------------------------------------------------
    # Filtering (search + status chip combined)
    # ------------------------------------------------------------------

    def _apply_all_filters(self, text: str) -> None:
        """Apply both the search text and the active status chip filter."""
        query = text.strip().lower()
        status_filter = self._active_filter

        for row in range(self._table.rowCount()):
            # Status filter
            if status_filter != "All":
                status_item = self._table.item(row, self.COL_STATUS)
                # Por el estado guardado y no por el texto de la celda:
                # el texto esta traducido, y ademas un «Concluído ⚠»
                # nunca fue igual a «Completed», asi que filtrar por
                # concluidos escondia justo los que pedian revision.
                actual = status_item.data(Qt.ItemDataRole.UserRole) if status_item else None
                if actual != status_filter:
                    self._table.setRowHidden(row, True)
                    continue

            # Text search across multiple columns
            if query:
                if not self._row_matches_query(row, query):
                    self._table.setRowHidden(row, True)
                    continue

            self._table.setRowHidden(row, False)

    def _row_matches_query(self, row: int, query: str) -> bool:
        """Check if any searchable column in the row contains the query."""
        search_cols = [
            self.COL_VIDEO,
            self.COL_ATHLETES,
            self.COL_CATEGORY,
        ]
        for col in search_cols:
            item = self._table.item(row, col)
            if item and query in item.text().lower():
                return True
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _id_corto(nombre: str) -> str:
        """El identificador del combate a partir del nombre del fichero.

        «ID25_-50KG_FEMALE_E.COLLETI ITA X B. IZAGUIRRE .mp4» → «ID25».
        Si el nombre no sigue ese patron se devuelve entero, sin la
        extension: mas vale largo que vacio.
        """
        import re
        base = nombre.rsplit(".", 1)[0] if "." in nombre else nombre
        m = re.match(r"^(ID\d+)", base.strip(), re.IGNORECASE)
        return m.group(1).upper() if m else base

    def _sigla_analisis(self, codigo: str) -> tuple[str, str] | None:
        """(sigla, nombre) del análisis de un combate, solo donde el deporte
        hace tiempo-movimiento; None en los demás, para no tocar su Hub."""
        if not codigo or not catalogo.activo().tiempo_movimiento():
            return None
        siglas = {"technical_tactical": ("TT", "analisis.tt"),
                  "time_motion": ("TM", "analisis.tm"),
                  "complete": ("TT+TM", "analisis.completo")}
        if codigo not in siglas:
            return None
        sigla, clave = siglas[codigo]
        return sigla, self._i18n.t(clave)

    def _texto_estado(self, status: str) -> str:
        """El estado, escrito en el idioma que esta puesto.

        Dentro se guarda en ingles porque lo leen los filtros y la
        exportacion; lo que se ensena no tiene por que estarlo, y ver
        «In Progress» en una fila y «Em Progresso» en el filtro que la
        selecciona no parecia la misma cosa.
        """
        claves = {"Pending": "hub.status_pending",
                  "In Progress": "hub.status_in_progress",
                  "Completed": "hub.status_completed"}
        clave = claves.get(status)
        return self._i18n.t(clave) if clave else status

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds <= 0:
            return "—"
        total_secs = int(seconds)
        minutes = total_secs // 60
        secs = total_secs % 60
        return f"{minutes:02d}:{secs:02d}"

    # ------------------------------------------------------------------
    # Sortable columns
    # ------------------------------------------------------------------

    def _on_header_clicked(self, logical_index: int) -> None:
        """Sort table rows by the clicked column."""
        if logical_index == self.COL_ACTIONS:
            return  # Actions column is not sortable
        if self._sort_column == logical_index:
            self._sort_order = (
                Qt.SortOrder.DescendingOrder
                if self._sort_order == Qt.SortOrder.AscendingOrder
                else Qt.SortOrder.AscendingOrder
            )
        else:
            self._sort_column = logical_index
            self._sort_order = Qt.SortOrder.AscendingOrder
        self._table.sortItems(self._sort_column, self._sort_order)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard shortcuts for the hub table."""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            current_row = self._table.currentRow()
            if current_row >= 0:
                self.session_double_clicked.emit(current_row)
            return
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            current_row = self._table.currentRow()
            if current_row >= 0:
                self.delete_session_requested.emit(current_row)
            return
        if event.key() == Qt.Key.Key_F and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._search_input.setFocus()
            self._search_input.selectAll()
            return
        if event.key() == Qt.Key.Key_Down or event.key() == Qt.Key.Key_Up:
            self._table.setFocus()
            row = self._table.currentRow()
            direction = 1 if event.key() == Qt.Key.Key_Down else -1
            new_row = max(0, min(self._table.rowCount() - 1, row + direction))
            self._table.selectRow(new_row)
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        """Accept folder drops for loading video sessions."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        """Handle folder drop — emit path to controller for loading."""
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.load_folder_from_path.emit(path)
                event.acceptProposedAction()
                return
        event.ignore()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self.session_double_clicked.emit(item.row())

    def _on_bout_info_clicked(self) -> None:
        """Emit edit_bout_info_requested for the current or first visible row."""
        if not self._sessions:
            return

        current = self._table.currentRow()

        # If no row is explicitly selected, find the first visible one
        if current < 0 or current >= len(self._sessions):
            for row in range(self._table.rowCount()):
                if not self._table.isRowHidden(row):
                    current = row
                    self._table.selectRow(current)
                    break

        if 0 <= current < len(self._sessions):
            self.edit_bout_info_requested.emit(current)

    def _on_compare_clicked(self) -> None:
        """Emit compare_evaluators_requested for the current or first visible row."""
        current = self._table.currentRow()
        if current < 0:
            for row in range(self._table.rowCount()):
                if not self._table.isRowHidden(row):
                    current = row
                    self._table.selectRow(current)
                    break
        if 0 <= current < len(self._sessions):
            self.compare_evaluators_requested.emit(current)

    def _on_context_menu(self, pos) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._sessions):
            return
        menu, acciones = self._construir_menu(row)
        elegida = menu.exec(self._table.viewport().mapToGlobal(pos))
        if elegida is None:
            return
        señal = acciones.get(elegida)
        if señal is not None:
            señal.emit(row)

    def _construir_menu(self, fila: int = -1):
        """El menu de clic derecho y que señal dispara cada entrada.

        Separado de _on_context_menu porque exec() abre el menu y espera:
        asi se puede comprobar que lleva lo que debe sin abrir nada.
        """
        menu = QMenu(self)
        menu.setStyleSheet(self._ESTILO_MENU)
        open_action = menu.addAction(
            qta.icon("fa5s.edit", color=self._colors.text), self._i18n.t("hub.ctx_open")
        )
        report_action = menu.addAction(
            qta.icon("fa5s.chart-bar", color=self._colors.text), self._i18n.t("hub.ctx_report")
        )
        acciones = {open_action: self.session_double_clicked,
                    report_action: self.session_right_clicked}
        menu.addSeparator()
        # Bajaron de la barra de arriba: las dos actuan sobre UN
        # combate, y alli obligaban a seleccionar primero y pulsar
        # despues. Aqui el combate ya es el que esta debajo del raton.
        acciones[menu.addAction(
            qta.icon("fa5s.info-circle", color=self._colors.text),
            self._i18n.t("hub.ctx_bout_info"))] = self.edit_bout_info_requested
        acciones[menu.addAction(
            qta.icon("fa5s.users", color=self._colors.text),
            self._i18n.t("hub.ctx_compare"))] = self.compare_evaluators_requested
        menu.addSeparator()
        acciones[menu.addAction(
            qta.icon("fa5s.file-upload", color=self._colors.text),
            self._i18n.t("hub.carregar_dados"))] = self.cargar_dados
        menu.addSeparator()
        # Quien da un combate por terminado es quien lo anota, no el
        # programa: hasta que se pulse esto, el estado es "En Progreso".
        terminado = (0 <= fila < len(self._sessions)
                     and self._sessions[fila].status == "Completed")
        acciones[menu.addAction(
            qta.icon("fa5s.check-circle" if not terminado else "fa5s.undo",
                     color=self._colors.text),
            self._i18n.t("hub.ctx_unmark_done") if terminado
            else self._i18n.t("hub.ctx_mark_done"))] = self.marcar_concluido
        acciones[menu.addAction(
            qta.icon("fa5s.eraser", color=_p.danger),
            self._i18n.t("hub.ctx_clear_annotations"))] = self.borrar_anotaciones
        menu.addSeparator()
        acciones[menu.addAction(
            qta.icon("fa5s.trash-alt", color=_p.danger),
            self._i18n.t("hub.ctx_remove"))] = self.delete_session_requested
        return menu, acciones

    # ------------------------------------------------------------------
    # Open Recent (QSettings-based)
    # ------------------------------------------------------------------

    def add_recent_folder(self, path: str) -> None:
        """Persist a successfully loaded folder path to the recent list."""
        if not path:
            return
        settings = identidad.ajustes()
        recent = recientes.recientes(settings)
        # Remove duplicates and prepend
        recent = [p for p in recent if p != path]
        recent.insert(0, path)
        recent = recent[:self._MAX_RECENT]
        settings.setValue(self._RECENT_KEY, recent)
        self._refresh_recent_button()

    def _populate_recent_menu(self) -> None:
        """Fill the recent menu with up to 5 stored folder paths."""
        self._recent_menu.clear()
        settings = identidad.ajustes()
        recent: list[str] = recientes.recientes(settings)
        if not recent:
            empty = self._recent_menu.addAction(self._i18n.t("hub.no_recent"))
            empty.setEnabled(False)
            return
        for path in recent:
            import os
            basename = os.path.basename(path) or path
            action = self._recent_menu.addAction(
                qta.icon("fa5s.folder", color=self._colors.muted),
                basename,
            )
            action.setToolTip(path)
            action.triggered.connect(
                lambda checked=None, p=path: self.load_folder_from_path.emit(p)
            )
        self._recent_menu.addSeparator()
        clear = self._recent_menu.addAction(self._i18n.t("hub.clear_recent"))
        clear.triggered.connect(self._clear_recent)

    def _clear_recent(self) -> None:
        """Clear all recent folder entries."""
        settings = identidad.ajustes()
        settings.remove(self._RECENT_KEY)
        self._refresh_recent_button()

    def _refresh_recent_button(self) -> None:
        """Las carpetas recientes cuelgan del boton de cargar.

        Se queda como no-op porque el menu se rellena solo al abrirse
        (aboutToShow) y no hay ningun boton aparte que habilitar.
        """
        return

    # ------------------------------------------------------------------
    # Language button (premium — inline version)
    # ------------------------------------------------------------------

    def set_analisis(self, codigo: str) -> None:
        """El modo en que se está: la etiqueta junto al nombre."""
        self._pintar_selector_analisis(codigo)

    def _pintar_selector_analisis(self, codigo: str) -> None:
        self._analisis_elegido = codigo
        clave = {"time_motion": "analisis.tm", "technical_tactical": "analisis.tt"}.get(
            codigo, "analisis.completo")
        texto = self._i18n.t(clave).upper()
        if codigo == "complete":
            # El integrado se anota con el árbol de preguntas: asistido.
            texto += "  ·  " + self._i18n.t("pro.assistido")
        self._etiqueta_analisis.setText(texto)
        self._etiqueta_analisis.setVisible(bool(catalogo.activo().tiempo_movimiento()))

    def _build_lang_button_inline(self, brand_layout: QHBoxLayout) -> None:
        """Build a premium language selector integrated in the brand bar."""
        code = self._i18n.lang
        flag = self._i18n.LANG_FLAGS.get(code, "")
        abbr = code.upper()
        self._lang_btn = QPushButton(f"{flag}  {abbr}  ▾")
        self._lang_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lang_btn.setMinimumHeight(34)
        self._lang_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:rgba(255,255,255,0.45);"
            f"border:none;border-radius:8px;"
            f"font-size:12px;font-weight:500;letter-spacing:0.3px;"
            f"padding:4px 14px;}}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.06);"
            f"color:rgba(255,255,255,0.75);}}"
        )

        self._lang_menu = QMenu(self)
        self._lang_menu.setStyleSheet(
            f"QMenu{{background:{_p.surface_2};color:{_p.text_bright};"
            "border:1px solid rgba(255,255,255,0.10);border-radius:10px;padding:6px;}"
            "QMenu::item{padding:8px 32px 8px 14px;border-radius:6px;font-size:13px;}"
            "QMenu::item:selected{background:rgba(255,255,255,0.08);}"
        )
        for lang_code, lang_name in self._i18n.LANGS.items():
            f = self._i18n.LANG_FLAGS.get(lang_code, "")
            action = self._lang_menu.addAction(f"  {f}  {lang_name}")
            action.setCheckable(True)
            action.setChecked(lang_code == code)
            action.triggered.connect(
                lambda checked=False, c=lang_code: self._i18n.set_lang(c)
            )
        self._lang_btn.setMenu(self._lang_menu)

        brand_layout.addWidget(self._lang_btn)

    # ------------------------------------------------------------------
    # i18n — refresh all translatable strings
    # ------------------------------------------------------------------

    def _refresh_strings(self) -> None:
        """Update every user-facing string in the Project Hub."""
        # Title
        self._title_label.setText(identidad.en_marcha().nombre.upper())
        self._btn_inicio.setText(self._i18n.t("analisis.inicio"))
        self._btn_inicio.setToolTip(self._i18n.t("analisis.inicio_tip"))
        self._pintar_selector_analisis(getattr(self, "_analisis_elegido", "complete"))

        # Buttons
        self._load_btn.setText(self._i18n.t("hub.load_folder"))
        self._export_btn.setText(self._i18n.t("hub.export"))
        self._acc_export_todo.setText(self._i18n.t("hub.export_dataset"))
        self._acc_export_sel.setText(self._i18n.t("hub.export_selected"))

        # Search placeholder
        self._search_input.setPlaceholderText(self._i18n.t("hub.search_placeholder"))

        # Los filtros llevan el recuento dentro
        self._update_summary_cards()

        # Table headers
        self._refresh_table_headers()

        # Empty state
        self._empty_heading.setText(self._i18n.t("hub.empty_heading"))
        self._empty_hint.setText(self._i18n.t("hub.empty_hint"))
        self._empty_formats.setText(self._i18n.t("hub.empty_formats"))

        # Footer

        # Refresh table rows
        if self._sessions:
            self.set_sessions(self._sessions)

        # Marcar el idioma activo en su menu, si es que hay menu.
        #
        # El boton de idioma del Hub (_build_lang_button_inline) no lo
        # llama nadie: se quito de la cabecera y quedo el constructor
        # suelto. Sin esta guarda, cambiar de idioma —que es justo
        # cuando entra aqui— reventaba el Hub buscando un menu que no
        # llego a existir.
        menu_idiomas = getattr(self, "_lang_menu", None)
        if menu_idiomas is None:
            return
        for lang_act in menu_idiomas.actions():
            for lang_code, lang_name in self._i18n.LANGS.items():
                flag = self._i18n.LANG_FLAGS.get(lang_code, "")
                if lang_act.text() == f"  {flag}  {lang_name}":
                    lang_act.setChecked(lang_code == code)

    def _refresh_table_headers(self) -> None:
        """Set table column headers using current language."""
        self._table.setHorizontalHeaderLabels([
            self._i18n.t("hub.col_id"),
            self._i18n.t("hub.col_video"),
            self._i18n.t("hub.col_athletes"),
            self._i18n.t("hub.col_category"),
            self._i18n.t("hub.col_duration"),
            self._i18n.t("hub.col_annotations"),
            self._i18n.t("hub.col_score"),
            self._i18n.t("hub.col_status"),
            self._i18n.t("hub.col_actions"),
        ])

    # ------------------------------------------------------------------
    # Multi-selection + batch export
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        """Update Export Selected button label and state."""
        selected_rows = set(
            idx.row() for idx in self._table.selectedItems()
        )
        count = len(selected_rows)
        base_text = self._i18n.t("hub.export_selected")
        if count > 0:
            completed_count = sum(
                1 for r in selected_rows
                if 0 <= r < len(self._sessions)
                and self._sessions[r].annotations
            )
            self._acc_export_sel.setText(f"{base_text} ({completed_count})")
            self._acc_export_sel.setEnabled(completed_count > 0)
        else:
            self._acc_export_sel.setText(base_text)
            self._acc_export_sel.setEnabled(False)

    def _emit_export_selected(self) -> None:
        """Emit export_selected_requested with the list of selected row indices."""
        selected_rows = sorted(set(
            idx.row() for idx in self._table.selectedItems()
        ))
        if selected_rows:
            self.export_selected_requested.emit(selected_rows)

    # ------------------------------------------------------------------
    # Round Selector (REDISEÑO)
    # ------------------------------------------------------------------

    def _on_round_combo_changed(self, index: int) -> None:
        """User changed the active round in the dropdown — emit signal."""
        if index >= 0:
            self.round_changed_requested.emit(index)

    def set_rounds(self, rounds: list[dict], active_index: int) -> None:
        """Populate the round selector dropdown and highlight the active one.

        Args:
            rounds: List of round dicts from SessionManager.list_rounds().
            active_index: Index of the currently active round.
        """
        self._round_combo.blockSignals(True)
        self._round_combo.clear()
        for rnd in rounds:
            self._round_combo.addItem(rnd.get("label", "Unknown"))
        if 0 <= active_index < len(rounds):
            self._round_combo.setCurrentIndex(active_index)
        self._round_combo.blockSignals(False)
