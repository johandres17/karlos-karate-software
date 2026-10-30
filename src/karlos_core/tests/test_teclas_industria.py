"""Los controles del oficio: J-K-L, [I]/[O] y el salto de corte.

No es capricho de coherencia. Medido en este proyecto, el 90% del
trabajo de anotar es mover el vídeo, y los 11 combates que quedan están
vírgenes: [Tab] va a las anotaciones propias y allí no hay ninguna, así
que sin esto la única forma de avanzar son las flechas.

[I] y [O] marcan entrada y salida en cualquier montador desde hace
treinta años. [J] [K] [L] empezaron siendo el shuttle de velocidad
variable de esos mismos montadores; Johan lo probó anotando y prefirió
que [J] y [L] hicieran lo de las flechas, para no mover la mano derecha
en toda la faena. El barrido no se pierde: las teclas se repiten solas.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

VIDEO = Path(os.environ.get("KARLOS_VIDEOS", "/nonexistent/karlos_videos") + "/"
             "ID25_-50KG_FEMALE_E.COLLETI ITA X B. IZAGUIRRE .mp4")

# Los tests navegan un video REAL, pero junto al original pueden vivir
# sesiones que cambian mientras se anota. Un enlace simbolico en un
# directorio limpio da el mismo video sin .karlos_sessions al lado.
if VIDEO.exists():
    import tempfile as _tmp
    _limpio = Path(_tmp.mkdtemp(prefix="karlos_test_")) / VIDEO.name
    _limpio.symlink_to(VIDEO)
    VIDEO = _limpio


@pytest.fixture(scope="module")
def vm():
    QApplication.instance() or QApplication([])
    if not VIDEO.exists():
        pytest.skip("sin los vídeos")
    from karlos_core.utils.config_loader import load_config
    from karlos_core.controllers.video_manager import VideoManager
    cfg, _ = load_config("karate")
    v = VideoManager(cfg.video)
    assert v.load(str(VIDEO))
    yield v
    v.release()


# ── J y L se portan como las flechas ────────────────────────────────

def test_J_y_L_mueven_un_fotograma(vm):
    """Johan lo probó anotando: prefiere que hagan lo de las flechas.

    Así la mano derecha no se mueve en toda la faena. Y no se pierde el
    barrido: las teclas se repiten solas al mantenerlas, y un fotograma
    cuesta 0,93 ms, así que tener [L] apretada es avanzar de continuo.
    """
    vm.goto(4000)
    vm.step(1);  assert vm.current_frame == 4001
    vm.step(-1); assert vm.current_frame == 4000


def test_con_shift_van_de_diez_en_diez(vm):
    vm.goto(4000)
    vm.step(10);  assert vm.current_frame == 4010
    vm.step(-10); assert vm.current_frame == 4000


def test_el_shuttle_ya_no_existe(vm):
    """Se retiró entero: código que no alcanza nadie es peor que nada."""
    for nombre in ("shuttle", "parar_shuttle", "shuttle_speed", "_rebobinar"):
        assert not hasattr(vm, nombre), nombre


# ── [I] y [O] marcan tambien en PRO ─────────────────────────────────

def _anotador_pro():
    from karlos_core.utils.i18n import I18n
    from karlos_core.utils.config_loader import load_config
    from karlos_core.controllers.annotation_controller import AnnotationController
    QApplication.instance() or QApplication([])
    I18n().set_lang("pt")
    cfg, meta = load_config("karate")
    c = AnnotationController(cfg, meta)
    c.aplicar_modo_inicial()
    c.show()
    c.navigation.show_annotator()
    if not c._en_modo_pro():
        c._video_path = "/tmp/falso.mp4"
        c._entrar_modo_asistido()
    QApplication.processEvents()
    return c


def test_en_pro_la_I_marca_en_vez_de_regañar():
    """Antes solo avisaba de que se usara [D]."""
    c = _anotador_pro()
    llamadas = []
    c.shortcuts._on_mark_start = lambda: llamadas.append("I")
    c.shortcuts._despachar_i()
    assert llamadas == ["I"]


def test_en_pro_la_O_cierra_la_accion():
    c = _anotador_pro()
    llamadas = []
    c.shortcuts._on_mark_end = lambda: llamadas.append("O")
    c.shortcuts._despachar_o()
    assert llamadas == ["O"]


def test_la_F_es_el_inicio_del_combate_en_los_dos_modos():
    """Con [F] libre, el inicio del combate deja de necesitar Shift."""
    for pro in (True, False):
        c = _anotador_pro() if pro else None
        if c is None:
            break
        llamadas = []
        c.fight_controller.on_fight_start = lambda: llamadas.append("combate")
        c.shortcuts._fight = c.fight_controller
        c.shortcuts._despachar_f()
        assert llamadas == ["combate"]


def test_el_boton_de_inicio_de_combate_anuncia_F_sin_shift():
    c = _anotador_pro()
    assert "[F]" in c.window.video_panel.btn_fight_start.text()
    assert "⇧" not in c.window.video_panel.btn_fight_start.text()


def test_los_botones_anuncian_la_tecla_de_la_industria():
    c = _anotador_pro()
    from PySide6.QtWidgets import QPushButton
    vis = [b.text() for b in c.window.findChildren(QPushButton) if b.text().strip()]
    assert any("[I]" in t for t in vis), vis
    assert any("[O]" in t for t in vis), vis


# ── el salto de intercambio ─────────────────────────────────────────

def test_bajar_lleva_al_siguiente_intercambio():
    """[Tab] va a lo anotado; en un combate virgen no hay nada."""
    c = _anotador_pro()
    if not VIDEO.exists():
        pytest.skip("sin los vídeos")
    assert c.video_manager.load(str(VIDEO))
    c.video_manager.fight_start = 100
    c.video_manager.fight_end = 9000
    # Los cortes salen de las paradas anotadas.
    for f0, f1 in ((1000, 1500), (3000, 3600)):
        for atleta in ("AKA", "AO"):
            c.window.table_view.add_annotation(_parada_anotada(f0, f1, atleta))
    c.video_manager.goto(0)
    for esperado in (100, 1000, 1500, 3000, 3600):
        c._ir_a_intercambio(+1)
        assert c.video_manager.current_frame == esperado, (
            f"esperaba f{esperado}, está en f{c.video_manager.current_frame}")
    c._ir_a_intercambio(-1)
    assert c.video_manager.current_frame == 3000


def test_sin_paradas_analizadas_lo_dice_en_vez_de_no_hacer_nada():
    c = _anotador_pro()
    if not VIDEO.exists():
        pytest.skip("sin los vídeos")
    c.video_manager.load(str(VIDEO))
    c.video_manager.fight_start = None
    c.video_manager.fight_end = None
    c._descansos = []
    avisos = []
    c.window.set_status_message = lambda m: avisos.append(m)
    c._ir_a_intercambio(+1)
    assert avisos and "parada" in avisos[0].lower()


# ── calificar una parada sin duplicarla ─────────────────────────────

def _parada(n, f0, f1, atleta):
    from karlos_core.models.annotation import Annotation
    return Annotation(f_start=f0, f_end=f1, athlete=atleta,
                      category="REFEREE STOP", subcategory="REFEREE STOP",
                      technique="Referee")


def test_calificar_una_parada_no_crea_filas_nuevas():
    """Cada parada ya son DOS filas, una por atleta.

    En ID30 hay 24 filas de parada para 11 paradas detectadas. Anotar
    encima crearía una tercera y una cuarta, y el tiempo muerto se
    contaría por duplicado.
    """
    c = _anotador_pro()
    for a in (_parada(1, 1000, 1500, "AKA"), _parada(2, 1000, 1495, "AO")):
        c.window.table_view.add_annotation(a)
    antes = len(c.window.table_view.records)
    c.video_manager._current_frame = 1200          # dentro de la parada
    assert c._calificar_parada("VR") is True
    assert len(c.window.table_view.records) == antes, "no debe añadir filas"
    tec = [a.technique for a in c.window.table_view.records]
    assert tec.count("VR") == 2, f"las dos filas de la parada: {tec}"


def test_califica_las_dos_filas_de_la_misma_parada():
    c = _anotador_pro()
    c.window.table_view.add_annotation(_parada(1, 2000, 2400, "AKA"))
    c.window.table_view.add_annotation(_parada(2, 2000, 2390, "AO"))
    c.video_manager._current_frame = 2100
    c._calificar_parada("Injury")
    for a in c.window.table_view.records:
        assert a.technique == "Injury"


def test_no_toca_las_paradas_de_otro_momento():
    c = _anotador_pro()
    c.window.table_view.add_annotation(_parada(1, 1000, 1500, "AKA"))
    c.window.table_view.add_annotation(_parada(2, 5000, 5400, "AKA"))
    c.video_manager._current_frame = 1200
    c._calificar_parada("VR")
    tec = [a.technique for a in c.window.table_view.records]
    assert tec == ["VR", "Referee"], tec


def test_fuera_de_una_parada_devuelve_falso_y_sigue_el_camino_normal():
    """Sin esto, contestar «parada» lejos de una no haría nada en silencio."""
    c = _anotador_pro()
    c.window.table_view.add_annotation(_parada(1, 1000, 1500, "AKA"))
    c.video_manager._current_frame = 8000
    assert c._calificar_parada("VR") is False


# ── las dos filas de cada parada ───────────────────────────────────

def _parada_anotada(f0, f1, atleta):
    from karlos_core.models.annotation import Annotation
    return Annotation(f_start=f0, f_end=f1, athlete=atleta,
                      category="REFEREE STOP", subcategory="REFEREE STOP",
                      technique="Referee")


def _con_parada():
    c = _anotador_pro()
    c.window.table_view.add_annotation(_parada_anotada(1000, 1500, "AKA"))
    c.window.table_view.add_annotation(_parada_anotada(1000, 1495, "AO"))
    return c


def test_el_aviso_no_cuenta_dos_veces_la_misma_parada():
    """Cada parada son dos filas, una por atleta."""
    c = _con_parada()
    assert len(c._paradas_ordenadas()) == 1


def test_ajustar_el_inicio_mueve_las_dos_filas_de_la_parada():
    """Si solo se mueve una, cuentan como dos paradas distintas.

    La navegación por intercambios pararía dos veces en la misma y el
    tiempo muerto saldría doble.
    """
    c = _con_parada()
    c.window.table_view.select_record(0)
    c.video_manager._current_frame = 1054      # el corte real, 54 más tarde
    c._set_selected_frame("start")
    inicios = [int(a.f_start) for a in c.window.table_view.records]
    assert inicios == [1054, 1054], inicios
    assert len(c._paradas_ordenadas()) == 1, "sigue siendo UNA parada"


def test_ajustar_el_fin_tambien_mueve_las_dos():
    c = _con_parada()
    c.window.table_view.select_record(0)
    c.video_manager._current_frame = 1600
    c._set_selected_frame("end")
    assert [int(a.f_end) for a in c.window.table_view.records] == [1600, 1600]


def test_una_accion_normal_no_arrastra_a_nadie():
    """El emparejado es cosa SOLO de las paradas."""
    from karlos_core.models.annotation import Annotation
    c = _anotador_pro()
    for atleta in ("AKA", "AO"):
        c.window.table_view.add_annotation(Annotation(
            f_start=1000, f_end=1050, athlete=atleta, category="ATTACK",
            subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki"))
    c.window.table_view.select_record(0)
    c.video_manager._current_frame = 1020
    c._set_selected_frame("start")
    assert [int(a.f_start) for a in c.window.table_view.records] == [1020, 1000]


# ── la parada es del combate: cada pasada tiene su fila ─────────────
# El bug del 21-09-2026: en la pasada del AO, calificar una parada que
# el AKA ya tenia escribia el tipo ENCIMA de la fila del AKA y no
# creaba la del AO. ID30 quedo con 12 paradas de AKA y 1 de AO.

def _parada_manual(f0, f1, atleta, tipo="Referee"):
    from karlos_core.models.annotation import Annotation
    return Annotation(f_start=f0, f_end=f1, athlete=atleta,
                      category="REFEREE STOP", subcategory="REFEREE STOP",
                      technique=tipo)


def test_en_la_pasada_del_ao_la_parada_del_aka_se_clona_para_el_ao():
    c = _anotador_pro()
    c.window.table_view.add_annotation(_parada_manual(1000, 1500, "AKA", "Injury"))
    c.window.annotation_panel.set_athlete("AO")
    c.video_manager._current_frame = 1200
    assert c._calificar_parada("Referee") is True
    filas = c.window.table_view.records
    # El tipo es de la PAUSA, no del atleta: la ultima respuesta vale
    # para la pareja entera, y la fila del AO nace con los frames del AKA.
    assert [(a.athlete, a.technique, a.f_start, a.f_end) for a in filas] == [
        ("AKA", "Referee", 1000, 1500),
        ("AO", "Referee", 1000, 1500),
    ]


def test_calificar_retipa_la_pareja_entera_sin_crear_filas():
    c = _anotador_pro()
    c.window.table_view.add_annotation(_parada_manual(1000, 1500, "AKA"))
    c.window.table_view.add_annotation(_parada_manual(1000, 1500, "AO"))
    c.window.annotation_panel.set_athlete("AO")
    c.video_manager._current_frame = 1200
    assert c._calificar_parada("VR") is True
    assert [a.technique for a in c.window.table_view.records] == ["VR", "VR"], \
        "la pausa es una: sus dos filas llevan el mismo tipo"
    assert len(c.window.table_view.records) == 2, "y no se crea ninguna mas"


def test_fuera_de_toda_parada_sigue_el_camino_normal():
    c = _anotador_pro()
    c.window.table_view.add_annotation(_parada_manual(1000, 1500, "AKA"))
    c.window.annotation_panel.set_athlete("AO")
    c.video_manager._current_frame = 5000
    assert c._calificar_parada("Referee") is False
    assert len(c.window.table_view.records) == 1


def test_clonar_la_parada_se_puede_deshacer():
    c = _anotador_pro()
    c.window.table_view.add_annotation(_parada_manual(1000, 1500, "AKA"))
    c.window.annotation_panel.set_athlete("AO")
    c.video_manager._current_frame = 1200
    c._calificar_parada("Referee")
    c.undo_stack.undo()
    assert [a.athlete for a in c.window.table_view.records] == ["AKA"]


# ── las franjas son referencia: las filas «auto:» pasan a datos ─────

