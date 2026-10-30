"""Los cuadraditos de faltas dicen la verdad, y la misma que el CSV.

El grado de una sanción no se elige: sale del contador del atleta. Así
que si el contador de la pantalla y el del CSV discrepan, uno de los
dos le está mintiendo a quien anota justo cuando tiene que decidir.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from karlos_core.controllers.foul_controller import sanciones_por_competidor
from karlos_core.models.annotation import Annotation


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    yield QApplication.instance() or QApplication([])


def _falta(atleta, tipo="Contact"):
    return Annotation(f_start=100, f_end=120, athlete=atleta, category="ATTACK",
                      subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki",
                      sport_specific_data={"sanction": tipo})


def _accion(atleta):
    return Annotation(f_start=200, f_end=220, athlete=atleta, category="ATTACK",
                      subcategory="HAND TECHNIQUES", technique="Kizami Tsuki")


def _contador():
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.contador_faltas import ContadorFaltas
    cfg, _ = load_config("karate")
    return ContadorFaltas(cfg.colors)


# ── la cuenta ───────────────────────────────────────────────────────

def test_cuenta_las_faltas_de_cada_atleta():
    anns = [_falta("AKA"), _accion("AO"), _falta("AO"), _falta("AKA")]
    assert sanciones_por_competidor(anns) == (2, 1)


def test_una_accion_normal_no_suma():
    assert sanciones_por_competidor([_accion("AKA"), _accion("AO")]) == (0, 0)


def test_la_falta_suelta_tambien_suma():
    """Se puede anotar sola o colgada del ataque que la provocó."""
    suelta = Annotation(f_start=50, f_end=50, athlete="AO",
                        category="PENALTY", subcategory="PENALTY",
                        technique="Chui (1st)")
    assert sanciones_por_competidor([suelta]) == (0, 1)


def test_la_pantalla_y_el_csv_cuentan_igual():
    """Una sola regla, dos consumidores: no pueden discrepar."""
    from karlos_karate import csv_combate
    anns = [_falta("AKA"), _falta("AKA"), _falta("AO"), _accion("AKA")]
    por_fila = csv_combate._sanciones(anns)
    ultimo = anns[-1]
    # lo que el CSV escribe en la última fila es lo de ANTES de ella
    assert por_fila[id(ultimo)] == (2, 1)
    assert sanciones_por_competidor(anns[:-1]) == (2, 1)


# ── los cuadros ─────────────────────────────────────────────────────

def test_enciende_tantos_cuadros_como_faltas():
    c = _contador()
    c.set_faltas(3, 1)
    assert (c._aka, c._ao) == (3, 1)


def test_no_baja_de_cero_ni_se_sale_de_la_escalera():
    c = _contador()
    c.set_faltas(-4, 99)
    assert c._aka == 0 and c._ao == 99      # se guarda, el pintado lo recorta
    assert c.peldaños == 5, "CHUI 1/2/3, HANSOKU-CHUI, HANSOKU"


def test_el_tooltip_dice_el_grado_y_no_el_numero():
    """Es lo que hace falta saber para anotar la siguiente falta."""
    c = _contador()
    c.set_faltas(4, 0)
    assert "HANSOKU-CHUI" in c.toolTip()
    assert "sem faltas" in c.toolTip()
    c.set_faltas(5, 5)
    assert c.toolTip().count("HANSOKU") == 2


def test_se_pinta_sin_reventar_en_cualquier_estado():
    from PySide6.QtGui import QPixmap
    c = _contador()
    for aka in range(0, 7):
        c.set_faltas(aka, 6 - aka)
        lienzo = QPixmap(c.size())
        c.render(lienzo)            # si el pintado falla, revienta aquí


def test_sale_en_los_dos_modos():
    """Sin ellos habia que contar las faltas en la tabla."""
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.video_panel import VideoPanelView
    cfg, _ = load_config("karate")
    vp = VideoPanelView(cfg.colors, cfg.video)
    vp.aplicar_modo(True)
    assert vp.contador_faltas.isVisibleTo(vp)
    vp.aplicar_modo(False)
    assert vp.contador_faltas.isVisibleTo(vp)
    assert vp._ctrl.indexOf(vp.contador_faltas) >= 0      # en la fila de controles


def test_aka_se_llena_hacia_dentro_como_en_el_marcador():
    """En el overlay de la WKF los dos grupos crecen desde el centro.

    Copiarlo hace que comparar el contador con el vídeo sea mirar dos
    veces la misma forma, no traducir de una a otra.
    """
    from PySide6.QtGui import QPixmap, QImage
    c = _contador()
    PELDAÑOS = c.peldaños
    c.set_faltas(1, 1)
    lienzo = QPixmap(c.size()); lienzo.fill(); c.render(lienzo)
    img: QImage = lienzo.toImage()
    y_aka = c.LADO // 2
    y_ao = c.LADO + c.SEPARACION + c.LADO // 2
    def encendido(col, y):
        """Encendido = color del atleta. Apagado = gris, sea cual sea.

        Mirar el brillo no vale: sobre fondo claro un cuadro apagado es
        casi blanco y da más brillo que uno encendido.
        """
        x = col * (c.LADO + c.HUECO) + c.LADO // 2
        px = img.pixelColor(x, y)
        canales = (px.red(), px.green(), px.blue())
        return max(canales) - min(canales) > 60
    assert encendido(PELDAÑOS - 1, y_aka), "AKA debe encender el de la derecha"
    assert not encendido(0, y_aka), "y no el de la izquierda"
    assert encendido(0, y_ao), "AO debe encender el de la izquierda"
    assert not encendido(PELDAÑOS - 1, y_ao)


def test_los_cuadros_son_los_peldaños_del_deporte():
    """El contador no sabe de karate: pinta la escalera que le den."""
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.contador_faltas import ContadorFaltas
    from karlos_core.deporte import Competidor, Reglamento

    class _Deporte:
        competidores = (Competidor("HONG", "Hong", "aka"), Competidor("CHUNG", "Chung", "ao"))
        reglamento = Reglamento(puntuaciones=(), escalera_de_faltas=("AVISO", "FUERA", "ADIOS"),
                                duracion_s=60.0, tipos_de_parada=(), fase_de=lambda s: "")

    cfg, _ = load_config("karate")
    c = ContadorFaltas(cfg.colors, deporte=_Deporte())
    assert c.peldaños == 3
    assert c.width() == 3 * c.LADO + 2 * c.HUECO
    c.set_faltas(2, 9)
    # El nombre que ve el evaluador, no el código que se guarda.
    assert c.toolTip() == "Hong: FUERA   ·   Chung: ADIOS"
