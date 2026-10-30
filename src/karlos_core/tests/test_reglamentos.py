"""Los datos del combate y la ventana de edición del karate.

La ventana de los datos del combate guarda el peso al reabrirla, y la
ventana de edición corrige un ataque con los contextos del karate.
"""
from __future__ import annotations

from karlos_core import catalogo


def test_el_karate_guarda_su_peso_al_reabrir():
    """El mismo arreglo, por el otro camino: el del karate va por la
    categoría (Kumite Male) y no por el sexo."""
    from PySide6.QtWidgets import QApplication

    from karlos_core.views.bout_info_popup import BoutInfoPopup
    QApplication.instance() or QApplication([])
    catalogo.establecer("karate")
    v = BoutInfoPopup("AKA", "AO", sport_id="karate", existing_data={
        "category_type": "Kumite Male", "weight_category": "-67 kg"})
    assert v._combos["weight_category"].currentData() == "-67 kg"


def test_el_karate_sigue_corrigiendo_igual():
    """El mismo camino en karate: sus cuatro contextos y su dictamen."""
    from PySide6.QtWidgets import QApplication

    from karlos_core.models.annotation import Annotation
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.edit_annotation_popup import EditAnnotationPopup
    QApplication.instance() or QApplication([])
    catalogo.establecer("karate")
    cfg, _ = load_config("karate")
    puno = Annotation(athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
                      technique="Gyaku Tsuki", level="Chudan", f_start=10, f_end=40,
                      sport_specific_data={"base_technique": "Tsuki", "stance": "Rear"})
    v = EditAnnotationPopup(annotation=puno, config=cfg, colors=cfg.colors,
                            sport_id="karate", fps=30.0)
    opciones = [v._context_combo.itemText(i) for i in range(v._context_combo.count())]
    assert opciones == ["", "Direct", "Counter", "Anticipation", "Combination"]
    assert v._contact_combo is not None
