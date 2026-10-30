"""Main window view for KARLOS ANNOTATOR v1.0.

Orchestrates navigation between the Project Hub (index 0),
Annotation Workspace (index 1), and Match Report (index 2).
Uses a QStackedWidget as the central widget so users can switch
between views without side panels shrinking the video player.

All business logic is delegated to the AnnotationController.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from karlos_core.models.technique import AppColors, TaxonomyConfig
from karlos_core.views.annotation_panel import AnnotationPanelView
from karlos_core.views.annotations_table import AnnotationsTableView
from karlos_core.views.project_hub import ProjectHubView
from karlos_core.views.theme import (
    Palette,
    Spacing,
    Typography,
    build_global_qss,
    marca,
)
from karlos_core.views.video_panel import VideoPanelView
from karlos_core import catalogo, identidad

# ---------------------------------------------------------------------------
# QSettings key for persistent dock layout
# ---------------------------------------------------------------------------
_LAYOUT_KEY = "main_window/layout_state"


class MainWindow(QMainWindow):
    """Top-level application window with a QStackedWidget hub/workspace/report.

    Index 0:  ProjectHubView      — multi-fight session management
    Index 1:  AnnotationWorkspace — video, toolbar, docks
    Index 2:  MatchReportView     — analytics dashboard

    Signals:

    Public attributes:
        video_panel: The video playback panel view.
        annotation_panel: The technique selection panel view.
        table_view: The annotations log table view.
        project_hub: The project hub landing screen.
        match_report: The match analytics report dashboard.
        tech_dock: QDockWidget for the technique panel.
        log_dock: QDockWidget for the annotations log table.
    """

    def __init__(
        self,
        config: TaxonomyConfig,
        sport_meta: Optional[dict[str, str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._colors = config.colors
        self._sport_meta = sport_meta or {}
        self._p = Palette.from_config(config.colors)

        # El nombre y la versión de la edición (decisión 0006); el deporte,
        # solo si la edición trae más de uno. Hasta la 1.0 ponía «Karlos
        # Annotator v1.0» escrito a mano.
        edicion = identidad.en_marcha()
        sport_name = self._sport_meta.get("name", "")
        if sport_name and len(edicion.deportes) > 1:
            self.setWindowTitle(f"{edicion.nombre} v{edicion.version} — {sport_name}")
        else:
            self.setWindowTitle(f"{edicion.nombre} v{edicion.version}")

        # ── Responsive minimum size: never exceed the available screen ──
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        min_w, min_h = 1440, 860
        if avail is not None:
            min_w = min(min_w, int(avail.width() * 0.9))
            min_h = min(min_h, int(avail.height() * 0.9))
        self.setMinimumSize(min_w, min_h)
        self._small_screen = avail is not None and (
            avail.width() < 1440 or avail.height() < 900
        )

        self._toolbar_buttons: dict[str, QPushButton] = {}
        self._close_callback: callable | None = None

        self._apply_theme()
        self._build_stacked_widget()
        self._build_docks_and_statusbar()
        self.restore_layout()

        # Start clean: Hub visible, tech dock hidden
        self.tech_dock.hide()
        self._log_splitter.setVisible(False)

    @property
    def colors(self) -> AppColors:
        return self._colors

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _apply_theme(self) -> None:
        """Apply the centralized Linear Dark theme via theme.py."""
        self.setStyleSheet(build_global_qss(self._p))

    # ------------------------------------------------------------------
    # QStackedWidget — Hub + Workspace + Report
    # ------------------------------------------------------------------

    def _build_stacked_widget(self) -> None:
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Index 0: Project Hub
        self.project_hub = ProjectHubView(
            colors=self._colors,
            sport_meta=self._sport_meta,
            parent=self,
        )
        self._stack.addWidget(self.project_hub)

        # Index 1: Annotation Workspace
        self._workspace_widget = QWidget()
        self._build_workspace(self._workspace_widget)
        self._stack.addWidget(self._workspace_widget)

        # Index 2: Match Report
        # El informe es una salida del deporte (decision 0004).
        self.match_report = catalogo.activo().salidas().vista_informe(
            colors=self._colors,
            sport_meta=self._sport_meta,
            parent=self,
        )
        self._stack.addWidget(self.match_report)

        # Start on the hub
        self._stack.setCurrentIndex(0)

    def _build_workspace(self, workspace: QWidget) -> None:
        c = self._colors

        ml = QVBoxLayout(workspace)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        # ── Premium Brand Bar ───────────────────────────────────
        brand_bar = QWidget()
        p = self._p
        brand_bar.setStyleSheet(
            f"background:{p.surface_1};"
            f"border-bottom:1px solid {p.border_subtle};"
        )
        brand_bar.setFixedHeight(52)
        brand_layout = QHBoxLayout(brand_bar)
        brand_layout.setContentsMargins(12, 6, 12, 6)
        brand_layout.setSpacing(12)

        # Back button — minimalist pill
        from karlos_core.utils.i18n import I18n
        i18n = I18n()
        back_btn = QPushButton(i18n.t("ws.back_btn"))
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFixedHeight(32)
        back_btn.setStyleSheet(
            f"QPushButton{{"
            f"    background:{p.surface_2};"
            f"    color:{p.text_disabled};"
            f"    border:1px solid {p.border_default};"
            f"    border-radius:6px;"
            f"    padding:4px 14px;"
            f"    font-size:12px;"
            f"    font-weight:600;"
            f"}}"
            f"QPushButton:hover{{"
            f"    background:{p.surface_3};"
            f"    color:{p.text_primary};"
            f"    border:1px solid {p.border_hover};"
            f"}}"
        )
        back_btn.clicked.connect(self.navigate_to_hub)
        brand_layout.addWidget(back_btn)

        brand_layout.addStretch()

        # Logo + brand text — centerpiece
        import os as _os
        from karlos_core.utils.resource_path import resource_path
        logo_path = str(resource_path(
            "karlos_core", "assets", "logos", "karlitos.png"
        ))
        logo_container = QHBoxLayout()
        logo_container.setSpacing(10)

        logo_img = QLabel()
        if _os.path.exists(logo_path):
            from PySide6.QtGui import QPixmap
            pix = QPixmap(logo_path).scaled(
                36, 36,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_img.setPixmap(pix)
        logo_img.setStyleSheet("background:transparent;border:none;")
        logo_container.addWidget(logo_img)

        slogans = QVBoxLayout()
        slogans.setSpacing(0)

        # El nombre de la edición en marcha (decisión 0006): «KARLOS KARATE»
        # en Karlos Karate, «KARLOS ANNOTATOR» en la de desarrollo.
        title_lbl = QLabel(marca(identidad.en_marcha().nombre, p.text_primary, p.accent))
        title_lbl.setTextFormat(Qt.TextFormat.RichText)
        title_lbl.setStyleSheet(
            "font-size:16px;font-weight:700;"
            "letter-spacing:1.5px;background:transparent;border:none;"
        )
        self._title_lbl = title_lbl
        slogans.addWidget(title_lbl)

        # El deporte en una línea, la misma de la pantalla de inicio: el
        # karate dice qué se anota y con qué reglamento; los demás, su nombre.
        sport_name = self._sport_meta.get("name", "")
        subtitle_text = (i18n.t("deporte.descripcion", deporte=sport_name)
                         if sport_name else "Elite Combat Intelligence")
        subtitle_lbl = QLabel(subtitle_text)
        subtitle_lbl.setStyleSheet(
            f"color:{p.text_secondary};font-size:10px;font-weight:500;"
            "letter-spacing:0.8px;text-transform:uppercase;"
            "background:transparent;border:none;"
        )
        self._subtitle_lbl = subtitle_lbl
        self._subtitle_base = subtitle_text
        slogans.addWidget(subtitle_lbl)

        logo_container.addLayout(slogans)
        brand_layout.addLayout(logo_container)
        brand_layout.addStretch(1)
        # En PRO los botones de accion se mudan aqui, a la derecha del
        # titulo: la banda ya esta abierta y su fila propia costaba
        # cuarenta y nueve pixeles que se le quitaban al video.
        self._brand_actions = QHBoxLayout()
        self._brand_actions.setSpacing(8)
        brand_layout.addLayout(self._brand_actions)
        self._brand_bar = brand_bar
        self._tb_layout = brand_layout
        ml.addWidget(brand_bar)

        # ── Toolbar row (Open Video, Bout Info, Export, Report) ─
        self._action_bar_widget = QWidget()
        self._action_bar = QHBoxLayout(self._action_bar_widget)
        self._action_bar.setContentsMargins(10, 6, 10, 6)
        self._action_bar.setSpacing(8)
        self._action_bar.addStretch()  # buttons inserted before this
        ml.addWidget(self._action_bar_widget)
        self._botones_barra: list = []
        self._modo_pro = False

        # ── Separator ───────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{p.border_subtle};")
        self._sep_barra = sep
        ml.addWidget(sep)

        # La tabla completa ya no vive debajo del video: el registro que se
        # mira mientras se anota esta en el panel de tecnicas, y el video
        # se queda con todo el alto. La tabla sigue existiendo, con todas
        # sus columnas y su edicion, en una ventana que se abre a peticion.
        self.table_view = AnnotationsTableView(c)
        self._crear_ventana_registro()

        self._log_splitter = QSplitter(Qt.Orientation.Vertical)
        self._log_splitter.setObjectName("LogSplitter")
        self._log_splitter.setStyleSheet(
            f"QSplitter::handle{{"
            f"background:{p.border_subtle};"
            "height:8px;"
            "margin:0 4px;"
            "}"
            "QSplitter::handle:hover{"
            f"background:{p.accent};"
            "}"
        )
        self._log_splitter.setChildrenCollapsible(True)

        video_widget = QWidget()
        video_wrapper = QVBoxLayout(video_widget)
        video_wrapper.setContentsMargins(4, 2, 4, 2)
        self.video_panel = VideoPanelView(c, self._config.video)
        # El panel guiado va AL LADO del video, no debajo ni en una ventana
        # emergente: mientras se decide hay que seguir viendo el bucle, y
        # una ventana encima taparia justo lo que se necesita mirar.
        # El panel de preguntas va al lado derecho, en el hueco que dejan
        # los botones de tecnica al ocultarse en PRO. Estaba junto al
        # video y le robaba ancho, que es justo lo que no sobra: el video
        # es lo que hay que ver.
        from karlos_core.views.guided_panel import GuidedPanel
        self.guided_panel = GuidedPanel(c)
        video_wrapper.addWidget(self.video_panel, stretch=1)

        self._log_splitter.addWidget(video_widget)
        ml.addWidget(self._log_splitter, stretch=1)

    def _build_docks_and_statusbar(self) -> None:
        c = self._colors
        p = self._p

        from karlos_core.utils.i18n import I18n
        self._i18n = I18n()

        self.annotation_panel = AnnotationPanelView(
            self._config, sport_id=self._sport_meta.get("id", "")
        )
        self.annotation_panel.setMinimumWidth(240)

        # Debajo de las tecnicas, el registro breve: mientras se anota la
        # mirada ya esta aqui, y lo unico que hace falta saber es si va
        # cuadrando. La tabla completa sigue debajo del video para revisar.
        from karlos_core.views.log_compacto import LogCompacto
        self.log_compacto = LogCompacto(c)

        self._tech_splitter = QSplitter(Qt.Orientation.Vertical)
        self._tech_splitter.setObjectName("TechSplitter")
        self._tech_splitter.setStyleSheet(
            f"QSplitter::handle{{background:{p.border_subtle};height:6px;margin:0 4px;}}"
            f"QSplitter::handle:hover{{background:{p.accent};}}")
        self._tech_splitter.addWidget(self.annotation_panel)
        self._tech_splitter.addWidget(self.guided_panel)
        self.guided_panel.visibilidad_cambio.connect(
            lambda _v: self.ajustar_columna())
        # El panel de las fases del tiempo-movimiento ocupa el sitio de las
        # técnicas en la pasada de fases; mientras no, no se ve.
        from karlos_core.views.panel_fases import PanelFases
        self.panel_fases = PanelFases(c)
        self.panel_fases.setVisible(False)
        self._tech_splitter.addWidget(self.panel_fases)
        self._tech_splitter.addWidget(self.log_compacto)
        self._tech_splitter.setStretchFactor(0, 2)
        self._tech_splitter.setStretchFactor(1, 0)
        self._tech_splitter.setStretchFactor(2, 2)
        self._tech_splitter.setStretchFactor(3, 3)
        self._tech_splitter.setCollapsible(1, False)
        self._restore_splitter_sizes()

        # El rotulo lo pone `aplicar_modo`: en PRO ahi no hay ninguna
        # tecnica, solo el atleta y el registro.
        self.tech_dock = QDockWidget(self._i18n.t("ws.tech_dock"), self)
        self.tech_dock.setObjectName("Dock_Techniques")
        self.tech_dock.setWidget(self._tech_splitter)
        self.tech_dock.setMinimumWidth(260)
        self.tech_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.tech_dock)

        # Note: table_view is now embedded in _log_splitter (QSplitter)
        # inside _build_workspace instead of a QDockWidget.
        # log_dock removed — user drags the splitter handle instead.

        self.setDockNestingEnabled(True)
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.VerticalTabs
            | QMainWindow.DockOption.GroupedDragging
        )

        view_menu = self.menuBar().addMenu(self._i18n.t("menu.view"))
        view_menu.setObjectName("view_menu")
        self._view_menu = view_menu  # keep reference alive
        view_menu.addAction(self.tech_dock.toggleViewAction())
        view_menu.addSeparator()
        reset_action = view_menu.addAction(self._i18n.t("menu.reset_layout"))
        reset_action.setObjectName("reset_layout")
        reset_action.triggered.connect(self.reset_layout)

        self._status_bar = QStatusBar()
        self._status_bar.setStyleSheet(f"color:{p.text_secondary};font-size:11px;")
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage(self._i18n.t("ws.workflow_hint"))

        self._lbl_pending = QLabel("")
        self._lbl_pending.setStyleSheet(
            f"color:{p.accent};font-weight:bold;font-size:12px;"
        )
        self._status_bar.addPermanentWidget(self._lbl_pending)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_hub(self) -> None:
        self._animate_to(0)

    def navigate_to_workspace(self) -> None:
        self._animate_to(1)

    def navigate_to_report(self) -> None:
        self._animate_to(2)

    def _animate_to(self, target_idx: int) -> None:
        """Perform a smooth fade transition to a QStackedWidget page."""
        if target_idx == self._stack.currentIndex():
            return
        current_widget = self._stack.currentWidget()
        target_widget = self._stack.widget(target_idx)
        if current_widget is None or target_widget is None:
            self._stack.setCurrentIndex(target_idx)
            return

        duration = 180  # ms — premium, not too slow

        # Fade out current
        out_opacity = QGraphicsOpacityEffect()
        current_widget.setGraphicsEffect(out_opacity)
        out_anim = QPropertyAnimation(out_opacity, b"opacity")
        out_anim.setDuration(duration)
        out_anim.setStartValue(1.0)
        out_anim.setEndValue(0.0)
        out_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Fade in target (start hidden)
        in_opacity = QGraphicsOpacityEffect()
        in_opacity.setOpacity(0.0)
        target_widget.setGraphicsEffect(in_opacity)
        self._stack.setCurrentIndex(target_idx)

        in_anim = QPropertyAnimation(in_opacity, b"opacity")
        in_anim.setDuration(duration)
        in_anim.setStartValue(0.0)
        in_anim.setEndValue(1.0)
        in_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def _cleanup() -> None:
            current_widget.setGraphicsEffect(None)
            target_widget.setGraphicsEffect(None)

        in_anim.finished.connect(_cleanup)
        out_anim.start()
        in_anim.start()

    def set_pro_branding(self, activo: bool) -> None:
        """La cabecera de la anotacion guiada: el nombre y «ASSISTIDO»."""
        p = self._p
        nombre = marca(identidad.en_marcha().nombre, p.text_primary, p.accent)
        if activo:
            self._title_lbl.setText(
                f"{nombre} <span style='color:{self._colors.yellow};'>"
                f"{self._i18n.t('pro.assistido')}</span>")
            # El reparto del modo, dicho en cinco palabras: quien juzga que
            # fue cada accion es el evaluador.
            self._subtitle_lbl.setText(self._i18n.t("pro.lema"))
            self._subtitle_lbl.setStyleSheet(
                f"color:{self._colors.yellow};font-size:10px;font-weight:700;"
                "letter-spacing:0.8px;background:transparent;border:none;")
        else:
            self._title_lbl.setText(nombre)
            self._subtitle_lbl.setText(self._subtitle_base)
            self._subtitle_lbl.setStyleSheet(
                f"color:{p.text_secondary};font-size:10px;font-weight:500;"
                "letter-spacing:0.8px;text-transform:uppercase;"
                "background:transparent;border:none;")

    def set_pass_mode(self, modo: str) -> None:
        """Reservado. La anotacion guiada no oculta paneles.

        Ocultar el registro de anotaciones fue un error: el evaluador
        necesita ver lo que lleva anotado mientras avanza.
        """
        return

    def animate_focus_mode(self, enable: bool) -> None:
        """Animate tech_dock, _log_splitter, and menuBar with fade.

        Reuses the same QGraphicsOpacityEffect + QPropertyAnimation
        pattern (180ms, InOutQuad) already used by _animate_to for
        Hub ↔ Workspace ↔ Report transitions.

        Safe against rapid toggling: DeleteWhenStopped ensures no
        orphaned animations, and setGraphicsEffect(None) on fade-in
        cleans any residual effect from a prior fade-out.

        NOTE — macOS native menu bar:
        On macOS, QMenuBar defaults to the native system menu bar
        (top-of-screen, shared across all apps). QGraphicsOpacityEffect
        cannot animate native widgets — the menu will hide/show
        instantly while tech_dock and _log_splitter fade smoothly.
        This is a platform limitation, not a bug. Forcing
        setNativeMenuBar(False) would break macOS HIG consistency
        without adding meaningful visual value.
        """
        widgets: list[QWidget | QDockWidget | QSplitter] = [
            self.tech_dock,
            self._log_splitter,
        ]
        menu = self.menuBar()
        if menu is not None:
            widgets.append(menu)

        duration = 180

        for w in widgets:
            if w is None:
                continue

            if enable:  # entering focus → fade OUT
                if not w.isVisible():
                    continue
                effect = QGraphicsOpacityEffect()
                w.setGraphicsEffect(effect)
                anim = QPropertyAnimation(effect, b"opacity")
                anim.setDuration(duration)
                anim.setStartValue(1.0)
                anim.setEndValue(0.0)
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                # DeletionPolicy must be set BEFORE finished.connect
                anim.finished.connect(
                    lambda widget=w: (
                        widget.hide(),
                        widget.setGraphicsEffect(None),
                    )
                )
                anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            else:  # exiting focus → fade IN
                w.setGraphicsEffect(None)  # clean any residual
                w.show()
                effect = QGraphicsOpacityEffect()
                effect.setOpacity(0.0)
                w.setGraphicsEffect(effect)
                anim = QPropertyAnimation(effect, b"opacity")
                anim.setDuration(duration)
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.finished.connect(
                    lambda widget=w: widget.setGraphicsEffect(None)
                )
                anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # ------------------------------------------------------------------
    # Toolbar helpers
    # ------------------------------------------------------------------

    def mostrar_panel_fases(self, visible: bool) -> None:
        """La pasada de fases enseña los tres botones donde estaban las
        técnicas; la de acciones, al revés. El panel de preguntas lo lleva
        el árbol, que lo enseña cuando hay algo que preguntar."""
        # Con el anotador cerrado (en el Hub), isVisible() es False aunque el
        # panel esté puesto, porque lo oculta la página padre. Al cambiar de
        # modo desde el Hub, esta guarda daba por hecho que ya estaba oculto y
        # no lo quitaba: al abrir el combate salían a la vez las fases del
        # tiempo-movimiento y las técnicas (Johan, ID25, 19-10-2026). Se
        # compara con lo que el panel tiene puesto, no con lo que se ve.
        if visible == self.panel_fases.isVisibleTo(self.panel_fases.parentWidget()):
            return
        # Los botones de atleta se quedan: las fases son de cada atleta
        # (el especialista, 9-10-2026). Lo que se va es la lista de técnicas.
        self.annotation_panel.setVisible(True)
        self.annotation_panel.solo_atletas(visible)
        self.panel_fases.setVisible(visible)
        # El registro se queda en las dos pasadas: en la de fases es donde
        # cada pulsacion aparece como una fila.
        self.log_compacto.setVisible(True)
        if visible:
            self.guided_panel.setVisible(False)
        if getattr(self, "_modo_pro", False):
            self.ajustar_columna()
        else:
            self._restore_splitter_sizes()

    def add_toolbar_button(
        self, text: str, callback, object_name: str = "",
    ) -> QPushButton:
        p = self._p
        btn = QPushButton(text)
        btn.setMinimumHeight(34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton{{background:{p.surface_2};color:{p.text_primary};"
            f"border:1px solid {p.border_default};border-radius:6px;"
            f"padding:5px 16px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{p.surface_3};"
            f"border:1px solid {p.border_hover};}}"
            f"QPushButton:disabled{{color:{p.text_disabled};background:{p.bg_root};}}"
        )
        if object_name:
            btn.setObjectName(object_name)
            self._toolbar_buttons[object_name] = btn
        btn.clicked.connect(callback)
        # Insert before the stretch at the end
        self._action_bar.insertWidget(self._action_bar.count() - 1, btn)
        self._botones_barra.append(btn)
        if getattr(self, "_modo_pro", False):
            self._colocar_botones(True)
        return btn

    # ------------------------------------------------------------------
    # Status bar helpers
    # ------------------------------------------------------------------

    def set_pending_text(self, text: str) -> None:
        self._lbl_pending.setText(text)

    def traducir_teclas(self, mensaje: str) -> str:
        """Ya no traduce nada, y por eso sigue existiendo.

        Cuando PRO delimitaba con [D] y [F] hacia falta reescribir los
        mensajes al vuelo, porque estaban escritos con [I] y [O]. Ahora
        PRO usa [I] y [O] —y [F] volvio a ser el inicio del combate en
        los dos modos— asi que no hay nada que cambiar.

        Se deja como paso por el que se sabe que TODOS los mensajes
        pasan. Si algun dia una tecla vuelve a depender del modo, este
        es el sitio, y no los cuarenta mensajes sueltos.
        """
        return mensaje

    def set_status_message(self, message: str) -> None:
        self._status_bar.showMessage(self.traducir_teclas(message))

    def set_status_state(self, color: str, message: str) -> None:
        self._status_bar.setStyleSheet(f"color:{color};font-size:11px;")
        self._status_bar.showMessage(self.traducir_teclas(message))

    def update_start_button_style(self, active: bool) -> None:
        btn = self._toolbar_buttons.get("btnStart")
        if btn is None:
            return
        p = self._p
        if active:
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{p.success};"
                f"border:1px solid {p.success};border-radius:6px;"
                f"padding:6px 14px;font-size:12px;font-weight:600;}}"
                f"QPushButton:hover{{background:rgba(35,134,54,0.12);}}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton{{background:{p.surface_2};color:{p.text_primary};"
                f"border:1px solid {p.border_default};border-radius:6px;"
                f"padding:6px 14px;font-size:12px;font-weight:600;}}"
                f"QPushButton:hover{{background:{p.surface_3};}}"
            )

    def update_end_button_style(self, enabled: bool) -> None:
        btn = self._toolbar_buttons.get("btnEnd")
        if btn is None:
            return
        p = self._p
        btn.setEnabled(enabled)
        if enabled:
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{p.danger};"
                f"border:1px solid {p.danger};border-radius:6px;"
                f"padding:6px 14px;font-size:12px;font-weight:600;}}"
                f"QPushButton:hover{{background:rgba(229,83,75,0.12);}}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton{{background:{p.bg_root};color:{p.text_disabled};"
                f"border:1px solid {p.border_default};border-radius:6px;"
                f"padding:6px 14px;font-size:12px;font-weight:600;}}"
            )

    # ------------------------------------------------------------------
    # Layout persistence
    # ------------------------------------------------------------------

    def save_layout(self) -> None:
        settings = identidad.ajustes()
        settings.setValue(_LAYOUT_KEY, self.saveState())
        settings.setValue("main_window/geometry", self.saveGeometry())

    def restore_layout(self) -> None:
        settings = identidad.ajustes()
        state = settings.value(_LAYOUT_KEY)
        geometry = settings.value("main_window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        if state is not None:
            self.restoreState(state)

        # ── Sanity check: keep the window inside the current screen ──
        # (Restored geometry may come from another monitor / resolution.)
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            geo = self.geometry()
            if (
                geo.width() > avail.width()
                or geo.height() > avail.height()
                or not avail.intersects(geo)
            ):
                w = min(geo.width(), avail.width())
                h = min(geo.height(), avail.height())
                self.resize(w, h)
                self.move(
                    avail.x() + (avail.width() - w) // 2,
                    avail.y() + (avail.height() - h) // 2,
                )

    def _on_language_changed(self) -> None:
        """Refresh dock titles, menu text, and translatable window elements."""
        self.tech_dock.setWindowTitle(self._i18n.t("ws.tech_dock"))

        # Update menu bar text via saved reference (avoid dangling C++ pointer)
        view_menu = self._view_menu
        if view_menu is not None:
            view_menu.setTitle(self._i18n.t("menu.view"))
            for act in view_menu.actions():
                if act.objectName() == "reset_layout":
                    act.setText(self._i18n.t("menu.reset_layout"))

            # Update language submenu title + checkmarks
            lang_menu = view_menu.findChild(type(view_menu), "lang_submenu")
            if lang_menu is not None:
                lang_menu.setTitle(self._i18n.t("menu.language"))
                for lang_act in lang_menu.actions():
                    for code, name in self._i18n.LANGS.items():
                        if lang_act.text() == name:
                            lang_act.setChecked(code == self._i18n.lang)

    def reset_layout(self) -> None:
        self.tech_dock.setFloating(False)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.tech_dock)
        self.tech_dock.show()
        self._log_splitter.setSizes([500, 200])
        self._log_splitter.setVisible(True)

    # ------------------------------------------------------------------
    # Splitter size persistence
    # ------------------------------------------------------------------

    def _save_splitter_sizes(self) -> None:
        """Guardar el reparto entre tecnicas y registro."""
        splitter = getattr(self, "_tech_splitter", None)
        if splitter is None:
            return
        sizes = splitter.sizes()
        # Cuatro trozos desde el 8-10-2026 (tecnicas, preguntas, fases,
        # registro). El de las fases no se guarda: se enseña solo en la
        # pasada de fases y ahi se reparte a mano.
        if len(sizes) == 4 and sum(sizes) > 0 and not self.panel_fases.isVisible():
            settings = identidad.ajustes()
            settings.setValue("tech_splitter/sizes", [sizes[0], sizes[1], sizes[3]])

    def _restore_splitter_sizes(self) -> None:
        """Recuperar el reparto guardado, o repartir por defecto."""
        settings = identidad.ajustes()
        stored = settings.value("tech_splitter/sizes")
        # Lo guardado son tres (tecnicas, preguntas, registro); el panel de
        # fases va a cero: solo se abre en su pasada. Sin esto el registro
        # se quedaba con altura cero, que fue lo primero que se vio mal.
        if stored is not None and len(stored) == 3:
            a, b, c = (int(v) for v in stored)
            self._tech_splitter.setSizes([a, b, 0, c])
        else:
            self._tech_splitter.setSizes([180, 300, 0, 260])

    def _crear_ventana_registro(self) -> None:
        """Ventana con la tabla completa, para revisar y corregir.

        Se abre solo cuando hace falta. Mientras se anota estorba mas de lo
        que ayuda: son veintiocho columnas para mirar de reojo si el
        recuento cuadra, y eso ya lo dice el registro breve.
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout as _VB
        from karlos_core.utils.i18n import I18n
        self.log_dialog = QDialog(self)
        self.log_dialog.setWindowTitle(I18n().t("ws.ann_log"))
        self.log_dialog.resize(1100, 520)
        lay = _VB(self.log_dialog)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self.table_view)

    def aplicar_modo(self, pro: bool) -> None:
        """Colocar la ventana: con un combate abierto, la anotacion guiada
        (el registro breve en el panel lateral y la tabla en una ventana
        aparte, para dejarle el alto al video); sin combate, la disposicion
        de partida."""
        self._modo_pro = pro
        self.tech_dock.setWindowTitle(
            self._i18n.t("pro.registro") if pro else self._i18n.t("ws.tech_dock"))
        self._colocar_botones(pro)
        self._repartir_panel(pro)
        self.log_compacto.setVisible(pro)
        self.video_panel.aplicar_modo(pro)
        if pro:
            if self.table_view.parent() is not self.log_dialog:
                self.log_dialog.layout().addWidget(self.table_view)
        else:
            self.log_dialog.hide()
            if self.table_view.parent() is not self._log_splitter:
                self._log_splitter.addWidget(self.table_view)
                self._log_splitter.setSizes([560, 220])
            self.table_view.show()

    def _repartir_panel(self, pro: bool) -> None:
        """Dar al registro el alto que el selector de atleta no usa.

        En PRO el panel superior se queda en dos botones —AKA y AO— pero
        seguia ocupando dos quintos de la columna, asi que entre ellos y
        el registro quedaban doscientos pixeles de negro. Ahora se le da
        lo justo y el resto va al registro, que es lo que se mira.

        """
        self.annotation_panel.mostrar_tecnicas(not pro)
        if pro:
            alto = self.annotation_panel.alto_minimo_pro()
            self.annotation_panel.setMaximumHeight(alto)
            self._tech_splitter.setStretchFactor(0, 0)
            self._tech_splitter.setStretchFactor(3, 1)
            self.ajustar_columna()
        else:
            self.annotation_panel.setMaximumHeight(16777215)
            self._tech_splitter.setStretchFactor(0, 2)
            self._tech_splitter.setStretchFactor(3, 3)

    def ajustar_columna(self) -> None:
        """Repartir la columna derecha segun lo que haya a la vista.

        Limitar el panel de arriba no basta: el splitter seguia
        reservando su hueco de siempre y quedaba negro entre los botones
        de atleta y el registro. Hay que darle los tamaños.

        Y hay que rehacerlo cada vez que aparece o se va el panel de
        preguntas: con un reparto fijo se quedaba sin alto y sus
        opciones se pisaban unas a otras.
        """
        if not getattr(self, "_modo_pro", False):
            return
        sp = self._tech_splitter
        # Cuatro trozos: tecnicas, preguntas, fases, registro. En la pasada
        # de fases, las fases arriba y el registro debajo, a medias; si no,
        # lo de siempre y las fases a cero. Con tres tamaños para cuatro
        # trozos el registro se quedaba sin alto (visto el 8-10-2026).
        # Con lo que el panel tiene puesto, no con lo que se ve: al abrir un
        # combate desde el Hub la página del anotador aún no está a la vista
        # e isVisible() decía False con el panel puesto. Al cambiar del
        # integrado al tiempo-movimiento, las fases se quedaban a cero alto
        # (visto en la captura de la Figura 3, 19-10-2026).
        if self.panel_fases.isVisibleTo(self.panel_fases.parentWidget()):
            # Los botones arriba y, debajo, el registro: ahi aparece cada
            # fase marcada como una fila, que es el historico.
            total = max(sp.height(), 600)
            atletas = 40
            arriba = min(330, total // 2)
            sp.setSizes([atletas, 0, arriba, total - arriba - atletas])
            return
        arriba = self.annotation_panel.maximumHeight()
        medio = (max(self.guided_panel.sizeHint().height(),
                     self.guided_panel.minimumSizeHint().height())
                 if self.guided_panel.isVisibleTo(self.guided_panel.parentWidget()) else 0)
        total = max(sp.height(), arriba + medio + 120)
        sp.setSizes([arriba, medio, 0, max(80, total - arriba - medio)])

    def _colocar_botones(self, pro: bool) -> None:
        """Donde viven los botones de accion segun el modo.

        En la anotacion guiada, a la derecha del titulo: la banda ya esta
        abierta y su fila propia costaba cuarenta y nueve pixeles de alto
        que se le quitaban al video, que es lo que se mira.
        """
        destino = self._brand_actions if pro else self._action_bar
        for btn in getattr(self, "_botones_barra", []):
            if btn.parent() is not None:
                btn.setParent(None)
            if destino is self._action_bar:
                destino.insertWidget(destino.count() - 1, btn)
            else:
                destino.addWidget(btn)
            # Un boton que su dueño tiene escondido (el de las fases fuera
            # del analisis completo) sigue escondido al recolocarlo.
            btn.setVisible(not bool(btn.property("oculto")))
        hay = bool(getattr(self, "_botones_barra", []))
        self._action_bar_widget.setVisible(not pro and hay)
        self._sep_barra.setVisible(not pro)
        # La banda se aprieta un poco: en PRO lleva botones dentro y no
        # hace falta el aire que tenia cuando solo llevaba el rotulo.
        self._brand_bar.setFixedHeight(46 if pro else 52)

    def abrir_registro_completo(self) -> None:
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()

    # ------------------------------------------------------------------
    # Lifecycle override
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._save_splitter_sizes()
        self.save_layout()
        # Release session lock on Cmd+Q / direct window close
        if self._close_callback:
            self._close_callback()
        super().closeEvent(event)
