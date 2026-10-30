"""Edit annotation popup dialog for KARLOS ANNOTATOR.

Allows editing an existing annotation's fields: athlete, category,
subcategory, technique, level/score, notes, and frame range.
Opens as a modal dialog pre-filled with the current annotation values.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from karlos_core.models.annotation import Annotation
from karlos_core.models.technique import AppColors, TaxonomyConfig, Technique
from karlos_core.utils.i18n import I18n
from karlos_core.views.theme import Palette
from karlos_core.views.animaciones import aparecer

# Donde guarda el programa la respuesta a cada pregunta de una tecnica.
# El nivel y el miembro van en la columna del nivel; las preguntas que el
# programa no conoce, con el prefijo q:.
_CLAVE_DE_PREGUNTA = {"Stance": "stance", "Action": "action_type",
                      "Follow-up": "follow_up", "Target": "target",
                      "Contact": "contact", "Sanction": "sanction",
                      "Reason": "reason"}

# Lo que depende de la tecnica elegida: al cambiarla se rehace. La
# secuencia o una sancion son de la accion, no de la tecnica, y se quedan.
_RESPUESTAS = frozenset({"stance", "target", "action_type", "follow_up",
                         "base_technique", "reason"})


class EditAnnotationPopup(QDialog):
    """Modal dialog for editing an existing annotation record.

    Pre-fills all fields from the given Annotation and allows the user
    to modify athlete, category, subcategory, technique, level, score,
    notes, and frame start/end.

    Attributes:
        edited: A new Annotation instance with the modified values,
            or None if the user cancelled.
    """

    def __init__(
        self,
        annotation: Annotation,
        config: TaxonomyConfig,
        colors: AppColors,
        sport_id: str = "karate",
        fps: float = 30.0,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize the edit popup.

        Args:
            annotation: The existing annotation to edit.
            config: Taxonomy configuration for technique/level/score lists.
            colors: Application color palette.
            sport_id: Sport identifier ("karate", "kickboxing", etc.).
            fps: Frames per second of the video (for duration recalculation).
            parent: Optional parent widget.
        """
        super().__init__(parent)
        aparecer(self)
        self._annotation = annotation
        self._config = config
        self._colors = colors
        self._sport_id = sport_id
        self._fps = fps
        self._i18n = I18n()
        self.edited: Optional[Annotation] = None

        self.setWindowTitle(self._i18n.t("edit.title", technique=annotation.technique))
        self.setMinimumWidth(480)
        self.setMinimumHeight(520)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._build()

    # ------------------------------------------------------------------
    # Show animation
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Fade-in the popup when it first appears.

        Same pattern as BoutInfoPopup.showEvent — 150ms InOutQuad
        opacity animation, triggered from showEvent (not __init__)
        because the widget is not yet on screen during construction.
        """
        super().showEvent(event)
        if not hasattr(self, "_fade_done"):
            self._fade_done = True
            effect = QGraphicsOpacityEffect()
            effect.setOpacity(0.0)
            self.setGraphicsEffect(effect)
            self._fade_anim = QPropertyAnimation(effect, b"opacity")
            self._fade_anim.setDuration(150)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self._fade_anim.finished.connect(lambda: self.setGraphicsEffect(None))
            self._fade_anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        """Construct the dialog UI with all editable fields."""
        c = self._colors
        a = self._annotation
        is_kb = self._sport_id == "kickboxing"
        i18n = self._i18n

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        # ── Header ────────────────────────────────────────────────
        hdr = QLabel(i18n.t("edit.header", technique=a.technique, athlete=a.athlete))
        athlete_color = c.aka if a.athlete == "AKA" else c.ao
        hdr.setStyleSheet(
            f"color:{athlete_color};font-size:16px;font-weight:700;"
            "background:transparent;border:none;"
        )
        root.addWidget(hdr)

        # ── Form ──────────────────────────────────────────────────
        self._form_layout = QFormLayout()
        form = self._form_layout
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        # Cada desplegable arranca en lo que la anotacion YA tiene, aunque
        # no este en su lista: una falta (PENALTY), el tipo de una parada,
        # un nombre por guardia (Gyaku Tsuki) o una puntuacion vacia. Un
        # QComboBox que no encuentra el texto se queda en el primero, y al
        # guardar sin tocar nada eso se escribia: la falta pasaba a ser un
        # ataque, la parada perdia su tipo y la finta su miembro. Ver
        # `_elegir` y `test_editar_sin_tocar`.
        self._iniciales: dict[str, str] = {}

        # Athlete
        self._athlete_combo = QComboBox()
        self._athlete_combo.addItems(["AKA", "AO"])
        self._elegir(self._athlete_combo, a.athlete, "athlete")
        self._style_combo(self._athlete_combo)
        form.addRow(i18n.t("edit.athlete") + ":", self._athlete_combo)

        # Category
        self._category_combo = QComboBox()
        categories = self._get_categories()
        self._category_combo.addItems(categories)
        self._elegir(self._category_combo, a.category, "category")
        self._category_combo.currentTextChanged.connect(self._on_category_changed)
        self._style_combo(self._category_combo)
        form.addRow(i18n.t("edit.category") + ":", self._category_combo)

        # Subcategory
        self._subcategory_combo = QComboBox()
        self._refresh_subcategories(a.category)
        self._elegir(self._subcategory_combo, a.subcategory, "subcategory")
        self._subcategory_combo.currentTextChanged.connect(self._on_subcategory_changed)
        self._style_combo(self._subcategory_combo)
        form.addRow(i18n.t("edit.subcategory") + ":", self._subcategory_combo)

        # Technique: la lista tiene las tecnicas como se eligen (Tsuki), y
        # el nombre por guardia (Gyaku Tsuki) sale de la guardia al guardar.
        self._technique_combo = QComboBox()
        self._refresh_techniques(a.category, a.subcategory)
        self._elegir(self._technique_combo, self._tecnica_de_la_lista(a), "technique")
        self._technique_combo.currentTextChanged.connect(self._on_technique_changed)
        self._style_combo(self._technique_combo)
        form.addRow(i18n.t("edit.technique") + ":", self._technique_combo)

        # El contexto de un ataque de karate va en su propio desplegable
        # (mas abajo); la pregunta «Action» de la tecnica es el mismo dato
        # y no se repite.
        self._con_contexto = not is_kb and a.category == "ATTACK"
        self._dim_combos: dict[str, QComboBox] = {}
        self._level_combo: Optional[QComboBox] = None

        # Level (or Stance/Target for Kickboxing, or custom levels_config)
        tech_config = self._get_technique_config(
            self._technique_combo.currentText(), a.category, a.subcategory)
        custom_levels = self._get_custom_level_options(tech_config)
        # Clean level value: strip "Limb: " prefix from legacy annotations
        clean_level = self._clean_custom_level(a.level, tech_config)

        if is_kb:
            if custom_levels:
                # Technique with custom levels_config (e.g. Feint with Limb)
                self._level_combo = QComboBox()
                levels = [""] + custom_levels
                self._level_combo.addItems(levels)
                self._elegir(self._level_combo, clean_level, "level")
                self._style_combo(self._level_combo)
                form.addRow(i18n.t("edit.level") + ":", self._level_combo)
            # Stance/Target
            self._stance_combo = QComboBox()
            self._stance_combo.addItems(["", "Lead", "Rear"])
            self._elegir(self._stance_combo, a.stance or "", "stance")
            self._style_combo(self._stance_combo)
            form.addRow(i18n.t("edit.stance") + ":", self._stance_combo)
            self._target_combo = QComboBox()
            self._target_combo.addItems(["", "High", "Middle", "Low"])
            self._elegir(self._target_combo, a.target or "", "target")
            self._style_combo(self._target_combo)
            form.addRow(i18n.t("edit.target") + ":", self._target_combo)
        elif tech_config and tech_config.levels_config:
            # ── Una fila por pregunta de la tecnica, con lo anotado ──
            self._crear_dimensiones(tech_config, self._respuestas_guardadas(a, tech_config))
            for dim, combo in self._dim_combos.items():
                self._iniciales[f"dim:{dim}"] = combo.currentText()
        else:
            self._level_combo = QComboBox()
            if custom_levels:
                levels = [""] + custom_levels
            else:
                levels = [""] + list(self._config.levels)
            self._level_combo.addItems(levels)
            self._elegir(self._level_combo, clean_level, "level")
            self._style_combo(self._level_combo)
            form.addRow(i18n.t("edit.level") + ":", self._level_combo)

        # Contacto y contexto: lo que el arbol pregunta de un ataque de
        # karate y esta pantalla no dejaba corregir. Sin ellos, una
        # anotacion a la que le falta el contacto solo se podia completar
        # borrandola y volviendola a hacer entera.
        self._contact_combo = self._context_combo = None
        if not is_kb and a.category == "ATTACK":
            # El dictamen (como acaba el ataque) lo pregunta el árbol: donde
            # no hay árbol de preguntas el campo está siempre vacío, y
            # ofrecerlo invita a rellenar a mano una variable que no existe
            # en esos datos.
            from karlos_core import catalogo
            if catalogo.asistido_disponible():
                self._contact_combo = QComboBox()
                self._contact_combo.addItems(["", "NoScore", "Score", "Foul"])
                self._elegir(self._contact_combo,
                             (a.sport_specific_data or {}).get("contact", ""), "contact")
                self._style_combo(self._contact_combo)
                form.addRow("Dictamen:", self._contact_combo)
            # El contexto es el criterio táctico del deporte: los cuatro del
            # karate, los siete del taekwondo. Sale de la pregunta «Action»
            # de la técnica; escrito aquí, un combate de taekwondo se
            # corregía con las palabras del karate.
            tacticas = list((tech_config.levels_config or {}).get("Action", [])) \
                if tech_config else []
            self._context_combo = QComboBox()
            self._context_combo.addItems(
                [""] + (tacticas or ["Direct", "Counter", "Anticipation", "Combination"]))
            self._elegir(self._context_combo,
                         (a.sport_specific_data or {}).get("action_type", ""), "context")
            self._style_combo(self._context_combo)
            form.addRow("Contexto:", self._context_combo)

        # Score
        self._score_combo = QComboBox()
        scores = [rule.code for rule in self._config.scoring_rules]
        self._score_combo.addItems(scores)
        self._elegir(self._score_combo, a.score or "", "score")
        self._style_combo(self._score_combo)
        form.addRow(i18n.t("edit.score") + ":", self._score_combo)

        # Frame Start / End
        self._f_start_input = QLineEdit(str(a.f_start))
        self._f_start_input.setStyleSheet(self._input_style(c))
        form.addRow(i18n.t("edit.frame_start") + ":", self._f_start_input)

        self._f_end_input = QLineEdit(str(a.f_end))
        self._f_end_input.setStyleSheet(self._input_style(c))
        form.addRow(i18n.t("edit.frame_end") + ":", self._f_end_input)

        # Notes
        self._notes_edit = QTextEdit()
        self._notes_edit.setPlainText(a.notes)
        self._notes_edit.setMaximumHeight(80)
        self._notes_edit.setStyleSheet(
            f"background:{c.panel};color:{c.text};"
            f"border:1px solid rgba(255,255,255,0.08);"
            f"border-radius:6px;font-size:12px;padding:4px 6px;"
        )
        form.addRow(i18n.t("edit.notes") + ":", self._notes_edit)

        root.addLayout(form)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton(i18n.t("edit.cancel"))
        cancel_btn.setStyleSheet(
            f"QPushButton{{background:{c.panel};color:{c.muted};"
            f"border:1px solid rgba(255,255,255,0.08);border-radius:8px;"
            f"padding:8px 20px;font-size:13px;font-weight:600;}}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.08);}}"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton(i18n.t("edit.save_changes"))
        save_btn.setStyleSheet(
            f"QPushButton{{background:{c.green};color:#fff;"
            f"border-radius:8px;padding:8px 20px;"
            f"font-size:13px;font-weight:600;border:none;}}"
            f"QPushButton:hover{{background:{c.green}DD;}}"
        )
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_categories(self) -> list[str]:
        """Get unique category names from the taxonomy."""
        cats: list[str] = []
        seen: set[str] = set()
        for tech in self._config.techniques:
            if tech.group not in seen:
                seen.add(tech.group)
                cats.append(tech.group)
        return cats

    def _get_subcategories(self, category: str) -> list[str]:
        """Get unique subcategory names for a given category."""
        subs: list[str] = []
        seen: set[str] = set()
        for tech in self._config.techniques:
            if tech.group == category and tech.category not in seen:
                seen.add(tech.category)
                subs.append(tech.category)
        return subs

    def _get_techniques(self, category: str, subcategory: str) -> list[str]:
        """Get technique names for a given category + subcategory."""
        return [
            tech.name
            for tech in self._config.techniques
            if tech.group == category and tech.category == subcategory
        ]

    def _on_category_changed(self, category: str) -> None:
        """Otra categoria: sus grupos, y las tecnicas del primero.

        Se llama a mano a lo siguiente en vez de esperar a la senal del
        grupo: al rellenarse la lista ya queda en el primero, asi que
        `setCurrentIndex(0)` no cambiaba nada, la senal no saltaba y la
        lista de tecnicas seguia siendo la de la categoria anterior.
        """
        self._refresh_subcategories(category)
        self._on_subcategory_changed(self._subcategory_combo.currentText())

    def _on_subcategory_changed(self, subcategory: str) -> None:
        """Refresh technique list when subcategory changes."""
        category = self._category_combo.currentText()
        self._refresh_techniques(category, subcategory)
        self._on_technique_changed(self._technique_combo.currentText())

    def _on_technique_changed(self, technique_name: str) -> None:
        """Otra tecnica: sus preguntas, con lo ya marcado en las que se
        llaman igual (de Tsuki a Uraken se conservan guardia y nivel)."""
        category = self._category_combo.currentText()
        subcategory = self._subcategory_combo.currentText()
        tech_config = self._get_technique_config(technique_name, category, subcategory)
        custom_levels = self._get_custom_level_options(tech_config)

        if self._sport_id == "kickboxing":
            if self._level_combo is not None:
                self._level_combo.blockSignals(True)
                self._level_combo.clear()
                self._level_combo.addItems([""] + (custom_levels or list(self._config.levels)))
                self._level_combo.blockSignals(False)
            return

        previos = {dim: combo.currentText() for dim, combo in self._dim_combos.items()}
        for combo in self._dim_combos.values():
            self._form_layout.removeRow(combo)
        self._dim_combos = {}
        if self._level_combo is not None:
            previos.setdefault("Level", self._level_combo.currentText())
            self._form_layout.removeRow(self._level_combo)
            self._level_combo = None

        if tech_config and tech_config.levels_config:
            self._crear_dimensiones(tech_config, previos)
            return
        self._level_combo = QComboBox()
        self._level_combo.addItems([""] + (custom_levels or list(self._config.levels)))
        anterior = previos.get("Level", "")
        if self._level_combo.findText(anterior) >= 0:
            self._level_combo.setCurrentText(anterior)
        self._style_combo(self._level_combo)
        self._form_layout.insertRow(self._fila_tras_tecnica(),
                                    self._i18n.t("edit.level") + ":", self._level_combo)

    def _crear_dimensiones(self, tech_config: Technique, valores: dict[str, str]) -> None:
        """Una fila por pregunta de la tecnica, debajo de la tecnica."""
        fila = self._fila_tras_tecnica()
        for dim, opciones in tech_config.levels_config.items():
            if dim == "Action" and self._con_contexto:
                continue
            combo = QComboBox()
            combo.addItems([""] + list(opciones))
            self._elegir(combo, valores.get(dim, ""))
            self._style_combo(combo)
            self._dim_combos[dim] = combo
            self._form_layout.insertRow(fila, f"{dim}:", combo)
            fila += 1

    def _fila_tras_tecnica(self) -> int:
        fila, _rol = self._form_layout.getWidgetPosition(self._technique_combo)
        return fila + 1

    def _elegir(self, combo: QComboBox, valor, clave: str | None = None) -> None:
        """Dejar el desplegable en `valor`, anadiendolo si no esta en la lista.

        Y apuntar con que valor empezo: al guardar, lo que no se toco se
        devuelve tal cual estaba, sin pasar por el desplegable.
        """
        valor = "" if valor is None else str(valor)
        if combo.findText(valor) < 0:
            combo.addItem(valor)
        combo.setCurrentIndex(combo.findText(valor))
        if clave:
            self._iniciales[clave] = valor

    def _tocado(self, clave: str, combo: Optional[QComboBox]) -> bool:
        return combo is not None and combo.currentText() != self._iniciales.get(clave)

    def _tecnica_de_la_lista(self, a: Annotation) -> str:
        """Lo que se marca en la lista de tecnicas para esta anotacion.

        Un nombre por guardia (Gyaku Tsuki) no esta en la lista: esta su
        tecnica (Tsuki), y la guardia va en su propia pregunta.
        """
        lista = [self._technique_combo.itemText(i) for i in range(self._technique_combo.count())]
        if a.technique in lista:
            return a.technique
        mapa = getattr(self._config, "combinatorial_map", None) or {}
        base = (a.sport_specific_data or {}).get("base_technique", "")
        if not base:
            base = next((b for b, por_guardia in mapa.items()
                         if a.technique in (por_guardia or {}).values()), "")
        return base if base in lista else a.technique

    def _respuestas_guardadas(self, a: Annotation, tech_config: Technique) -> dict[str, str]:
        """Lo que la anotacion tiene contestado a cada pregunta de su tecnica."""
        datos = a.sport_specific_data or {}
        nivel = a.level or ""
        combinado: dict[str, str] = {}
        if ": " in nivel:
            for segmento in nivel.split(" | "):
                if ": " in segmento:
                    dim, valor = segmento.split(": ", 1)
                    combinado[dim.strip()] = valor.strip()
        salida: dict[str, str] = {}
        for dim in tech_config.levels_config:
            if dim in ("Level", "Limb"):
                salida[dim] = combinado.get(dim, "") if ": " in nivel else nivel
            else:
                clave = _CLAVE_DE_PREGUNTA.get(dim, f"q:{dim}")
                salida[dim] = datos.get(clave, "") or combinado.get(dim, "")
        return salida

    @staticmethod
    def _guardar_respuesta(dim: str, valor: str, datos: dict, nivel: str) -> str:
        """Llevar una respuesta a su sitio; devuelve el nivel resultante."""
        if dim in ("Level", "Limb"):
            return valor
        clave = _CLAVE_DE_PREGUNTA.get(dim, f"q:{dim}")
        if valor:
            datos[clave] = valor
        else:
            datos.pop(clave, None)
        return nivel

    def _refresh_subcategories(self, category: str) -> None:
        """Populate subcategory combo for the given category."""
        self._subcategory_combo.blockSignals(True)
        self._subcategory_combo.clear()
        subs = self._get_subcategories(category)
        self._subcategory_combo.addItems(subs)
        self._subcategory_combo.blockSignals(False)

    def _refresh_techniques(self, category: str, subcategory: str) -> None:
        """Populate technique combo for the given category + subcategory."""
        self._technique_combo.blockSignals(True)
        self._technique_combo.clear()
        techs = self._get_techniques(category, subcategory)
        self._technique_combo.addItems(techs)
        self._technique_combo.blockSignals(False)

    def _on_save(self) -> None:
        """Validate and save the edited annotation."""
        a = self._annotation

        # Parse frame values
        try:
            f_start = int(self._f_start_input.text().strip())
        except ValueError:
            f_start = a.f_start
        try:
            f_end = int(self._f_end_input.text().strip())
        except ValueError:
            f_end = a.f_end

        is_kb = self._sport_id == "kickboxing"
        category = self._category_combo.currentText()
        subcategory = self._subcategory_combo.currentText()
        elegida = self._technique_combo.currentText()
        sport_data = dict(a.sport_specific_data or {})  # shallow copy
        technique, level = a.technique, a.level

        if is_kb:
            # Check if this technique has custom levels (e.g. Feint with Limb)
            tech_config = self._get_technique_config(elegida, category, subcategory)
            custom_levels = self._get_custom_level_options(tech_config)
            if custom_levels and self._level_combo is not None:
                level = self._level_combo.currentText()
            else:
                level = ""
            technique = elegida
            stance = self._stance_combo.currentText()
            target = self._target_combo.currentText()
            if stance:
                sport_data["stance"] = stance
            elif "stance" in sport_data:
                del sport_data["stance"]
            if target:
                sport_data["target"] = target
            elif "target" in sport_data:
                del sport_data["target"]
        else:
            from karlos_core.models.technique import resolve_combat_action
            mapa = getattr(self._config, "combinatorial_map", None) or {}
            otra_tecnica = (self._tocado("category", self._category_combo)
                            or self._tocado("subcategory", self._subcategory_combo)
                            or self._tocado("technique", self._technique_combo))
            if otra_tecnica:
                # Otra tecnica: sus respuestas son las que se ven ahora. Lo
                # que no es una respuesta (la secuencia, la sancion) se queda.
                for clave in list(sport_data):
                    if clave in _RESPUESTAS or clave.startswith("q:"):
                        del sport_data[clave]
                level = ""
                for dim, combo in self._dim_combos.items():
                    level = self._guardar_respuesta(dim, combo.currentText(), sport_data, level)
                if self._level_combo is not None:
                    level = self._level_combo.currentText()
                technique = elegida
                guardia = sport_data.get("stance", "")
                if elegida in mapa and guardia:
                    technique = resolve_combat_action(elegida, guardia, mapa)
                    if technique != elegida:
                        sport_data["base_technique"] = elegida
                if category != "ATTACK":
                    sport_data.pop("contact", None)
                    sport_data.pop("action_type", None)
            else:
                # La misma tecnica: solo cambia lo que se toco.
                for dim, combo in self._dim_combos.items():
                    if self._tocado(f"dim:{dim}", combo):
                        level = self._guardar_respuesta(dim, combo.currentText(), sport_data, level)
                if self._tocado("level", self._level_combo):
                    level = self._level_combo.currentText()
                # Otra guardia es otro nombre: Tsuki adelantada es Kizami.
                if self._tocado("dim:Stance", self._dim_combos.get("Stance")):
                    base = sport_data.get("base_technique") or (elegida if elegida in mapa else "")
                    if base:
                        technique = resolve_combat_action(base, sport_data.get("stance", ""), mapa)
                        if technique != base:
                            sport_data["base_technique"] = base
                        else:
                            sport_data.pop("base_technique", None)
            # En karate la guardia SI se usa: el arbol la guarda al elegir
            # la tecnica (Kizami es Lead, Gyaku es Rear). Borrarla aqui
            # hacia que editar una anotacion para arreglar otra cosa la
            # perdiera en silencio.
            if category == "ATTACK":
                for combo, clave, inicial in ((self._contact_combo, "contact", "contact"),
                                              (self._context_combo, "action_type", "context")):
                    if combo is None or not (otra_tecnica or self._tocado(inicial, combo)):
                        continue
                    valor = combo.currentText()
                    if valor:
                        sport_data[clave] = valor
                    else:
                        sport_data.pop(clave, None)

        # Recompute duration if frames changed
        duration_s = a.duration_s
        if f_end > f_start:
            if f_end != a.f_end or f_start != a.f_start:
                duration_s = (f_end - f_start) / self._fps

        notas = self._notes_edit.toPlainText()
        notes = a.notes if notas == (a.notes or "") else notas.strip()
        score = (self._score_combo.currentText()
                 if self._tocado("score", self._score_combo) else a.score)

        self.edited = Annotation(
            athlete=self._athlete_combo.currentText(),
            category=category,
            subcategory=subcategory,
            technique=technique,
            level=level,
            score=score,
            f_start=f_start,
            f_end=f_end,
            duration_s=duration_s,
            fight_f_start=a.fight_f_start,
            fight_f_end=a.fight_f_end,
            fight_dur_s=a.fight_dur_s,
            active_play_s=a.active_play_s,
            video_file=a.video_file,
            timestamp=a.timestamp,
            notes=notes,
            status=a.status,
            features=a.features,
            bout_id=a.bout_id,
            bout_event=a.bout_event,
            bout_number=a.bout_number,
            bout_round=a.bout_round,
            athlete_a_name=a.athlete_a_name,
            athlete_a_origin=a.athlete_a_origin,
            athlete_b_name=a.athlete_b_name,
            athlete_b_origin=a.athlete_b_origin,
            weight_category=a.weight_category,
            round=a.round,
            sport_specific_data=sport_data,
        )
        self.accept()

    def _get_technique_config(self, technique_name: str, category: str, subcategory: str) -> Optional[Technique]:
        """Get the Technique dataclass for a given technique name, category and subcategory.

        Args:
            technique_name: Name of the technique (e.g., "Feint").
            category: Group name (e.g., "TACTICS").
            subcategory: Category name (e.g., "TACTICS").

        Returns:
            The Technique dataclass or None if not found.
        """
        for tech in self._config.techniques:
            if (tech.name == technique_name
                    and tech.group == category
                    and tech.category == subcategory):
                return tech
        return None

    @staticmethod
    def _get_custom_level_options(tech_config: Optional[Technique]) -> list[str]:
        """Extract custom level options from a technique's levels_config.

        For example, if levels_config is {"Limb": ["Upper Limb", "Lower Limb"]},
        this returns ["Upper Limb", "Lower Limb"].

        Args:
            tech_config: The Technique dataclass (or None).

        Returns:
            List of custom level option strings, or empty list if none.
        """
        if tech_config is None or not tech_config.levels_config:
            return []
        options: list[str] = []
        for label, values in tech_config.levels_config.items():
            options.extend(values)
        return options

    @staticmethod
    def _clean_custom_level(level: str, tech_config: Optional[Technique]) -> str:
        """Clean a level value by stripping dimension prefixes (e.g. 'Limb: ').

        Legacy annotations may have been saved with the full multi-level string
        like "Limb: Upper Limb" instead of just "Upper Limb". This method
        strips the dimension prefix if the technique has a levels_config.

        Args:
            level: The raw level string from the annotation.
            tech_config: The Technique dataclass (or None).

        Returns:
            Cleaned level value, or the original if no cleaning needed.
        """
        if not level or tech_config is None or not tech_config.levels_config:
            return level
        # Check if level starts with any dimension label from levels_config
        for label in tech_config.levels_config:
            prefix = f"{label}: "
            if level.startswith(prefix):
                return level[len(prefix):]
        return level

    @staticmethod
    def _style_combo(combo: QComboBox) -> None:
        """Apply dark theme styling to a QComboBox."""
        combo.setStyleSheet(
            "QComboBox{background:p.misc_grey_card;color:p.misc_offwhite;"
            "border:1px solid rgba(255,255,255,0.08);border-radius:6px;"
            "padding:6px 10px;font-size:12px;min-height:20px;}"
            "QComboBox:hover{border:1px solid rgba(255,255,255,0.15);}"
            "QComboBox::drop-down{border:none;width:24px;}"
            "QComboBox QAbstractItemView{background:p.misc_grey_card;color:p.misc_offwhite;"
            "border:1px solid rgba(255,255,255,0.08);selection-background-color:rgba(255,255,255,0.12);}"
        )

    @staticmethod
    def _input_style(colors: AppColors) -> str:
        """Generate stylesheet for QLineEdit inputs."""
        return (
            f"background:{colors.panel};color:{colors.text};"
            f"border:1px solid rgba(255,255,255,0.08);"
            f"border-radius:6px;font-size:12px;padding:6px 10px;"
        )
