"""Tests de la lupa temporal.

Lo que importa aqui es la correspondencia entre pixeles y fotogramas: si
se desvia, el evaluador marca un sitio y se guarda otro.
"""

from __future__ import annotations

import pytest

from karlos_core.models.technique import AppColors
from karlos_core.views.zoom_bar import VENTANA_S, ZoomBar


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _colores():
    return AppColors(background="#12141a", panel="#1b1e26", border="#2c313c",
                     text="#e8eaf0", muted="#8c94a8", aka="#e2463f", ao="#3f7fe2",
                     punch="#e2a03f", kick="#3fe2a0", sweep="#a03fe2",
                     state="#3fe2e2", accent="#f0c040", green="#4caf50",
                     yellow="#ffc107")


def _barra(frame=1000, fps=30.0, total=12000, ancho=800):
    z = ZoomBar(_colores())
    z.resize(ancho, 76)
    z.set_video(total, fps)
    z.set_frame(frame)
    return z


class TestEscala:
    def test_el_cursor_queda_centrado(self):
        z = _barra(frame=1000)
        assert z._x(1000) == pytest.approx(z.width() / 2, abs=1.0)

    def test_pixel_y_fotograma_son_reciprocos(self):
        z = _barra(frame=1000)
        for f in (940, 985, 1000, 1015, 1060):
            assert z._frame_en(z._x(f)) == f

    def test_la_ventana_abarca_lo_anunciado(self):
        z = _barra(frame=1000, fps=30.0)
        a, b = z._rango()
        assert (b - a) / 30.0 == pytest.approx(2 * VENTANA_S)

    def test_una_accion_ocupa_pixeles_no_uno(self):
        """El motivo de existir de la lupa: media accion era 1 px."""
        z = _barra(frame=1000)
        ancho_accion = z._x(1015) - z._x(1000)     # medio segundo
        assert ancho_accion > 90

    def test_no_se_sale_del_video(self):
        z = _barra(frame=5, total=12000)
        assert z._frame_en(0.0) == 0
        z = _barra(frame=11995, total=12000)
        assert z._frame_en(float(z.width())) == 11999


class TestTiradores:
    def test_se_agarra_el_tirador_cercano(self):
        z = _barra(frame=1000)
        z.set_marcas(990, 1015)
        assert z._agarre(z._x(990)) == "I"
        assert z._agarre(z._x(1015)) == "O"

    def test_lejos_de_los_tiradores_no_se_agarra_nada(self):
        z = _barra(frame=1000)
        z.set_marcas(990, 1015)
        assert z._agarre(z._x(1005)) is None

    def test_sin_marcas_no_hay_nada_que_agarrar(self):
        z = _barra(frame=1000)
        z.set_marcas(None, None)
        assert z._agarre(z._x(1000)) is None


class TestArrastre:
    """Recorrer el video arrastrando, como el scrub de un editor."""

    def _capturar(self, z):
        vistos = []
        z.frame_pedido.connect(vistos.append)
        return vistos

    def test_a_la_derecha_retrocede(self):
        """Se arrastra la pelicula, no el cursor: empujar a la derecha
        trae hacia atras lo que ya paso."""
        z = _barra(frame=1000)
        v = self._capturar(z)
        z._desplazar(140.0, False)
        assert v and v[-1] < 1000

    def test_a_la_izquierda_avanza(self):
        z = _barra(frame=1000)
        v = self._capturar(z)
        z._desplazar(-140.0, False)
        assert v and v[-1] > 1000

    def test_sigue_al_cursor_a_la_escala_de_la_lupa(self):
        """Arrastrar media barra debe recorrer medio rango visible."""
        z = _barra(frame=1000, fps=30.0, ancho=800)
        v = self._capturar(z)
        z._desplazar(-400.0, False)             # media barra hacia adelante
        a, b = z._rango()
        assert v[-1] - 1000 == pytest.approx((b - a) / 2, rel=0.05)

    def test_un_movimiento_lento_no_se_pierde(self):
        """A 7 px por fotograma, sin acumular el resto no avanzaria nada."""
        z = _barra(frame=1000)
        v = self._capturar(z)
        for _ in range(20):
            z._desplazar(2.0, False)
        assert v, "veinte micromovimientos deberian mover el video"

    def test_shift_recorre_mas(self):
        z = _barra(frame=1000)
        v1 = self._capturar(z)
        z._desplazar(-100.0, False)
        lento = v1[-1] - 1000
        z2 = _barra(frame=1000)
        v2 = self._capturar(z2)
        z2._desplazar(-100.0, True)
        assert v2[-1] - 1000 > lento

    def test_no_se_sale_del_video(self):
        z = _barra(frame=5, total=12000)
        v = self._capturar(z)
        z._desplazar(5000.0, False)
        assert v[-1] == 0
        z = _barra(frame=11990, total=12000)
        v = self._capturar(z)
        z._desplazar(-5000.0, False)
        assert v[-1] == 11999

    def test_arrastrar_no_mueve_las_marcas(self):
        """Recorrer el video y ajustar los limites son cosas distintas."""
        z = _barra(frame=1000)
        z.set_marcas(990, 1015)
        movidas = []
        z.inicio_movido.connect(movidas.append)
        z.fin_movido.connect(movidas.append)
        z._desplazar(200.0, False)
        assert movidas == []


class TestClicFrenteAArrastre:
    """Pulsar y soltar sin moverse salta a ese punto; moverse recorre."""

    def _evento(self, tipo, x, boton=None):
        from PySide6.QtCore import QPointF, Qt as QtC
        from PySide6.QtGui import QMouseEvent
        b = QtC.LeftButton if boton is None else boton
        return QMouseEvent(tipo, QPointF(x, 10.0), QPointF(x, 10.0),
                           b, QtC.LeftButton, QtC.NoModifier)

    def _secuencia(self, z, xs):
        from PySide6.QtCore import QEvent
        z.mousePressEvent(self._evento(QEvent.MouseButtonPress, xs[0]))
        for x in xs[1:]:
            z.mouseMoveEvent(self._evento(QEvent.MouseMove, x))
        z.mouseReleaseEvent(self._evento(QEvent.MouseButtonRelease, xs[-1]))

    def test_un_clic_limpio_salta_a_ese_punto(self):
        z = _barra(frame=1000)
        v = []
        z.frame_pedido.connect(v.append)
        destino = z._x(1040)
        self._secuencia(z, [destino])
        assert v == [1040]

    def test_un_arrastre_no_salta_al_soltar(self):
        """Si saltara, el arrastre terminaria descolocando el video."""
        z = _barra(frame=1000)
        v = []
        z.frame_pedido.connect(v.append)
        x0 = z.width() / 2
        self._secuencia(z, [x0, x0 - 60, x0 - 120, x0 - 200])
        assert v, "el arrastre deberia haber movido el video"
        assert all(f > 1000 for f in v), "arrastrar a la izquierda solo avanza"

    def test_arrastrar_un_tirador_mueve_la_marca_y_no_el_video(self):
        z = _barra(frame=1000)
        z.set_marcas(990, 1015)
        inicios, saltos = [], []
        z.inicio_movido.connect(inicios.append)
        z.frame_pedido.connect(saltos.append)
        self._secuencia(z, [z._x(990), z._x(995), z._x(1000)])
        assert inicios and inicios[-1] == 1000
        assert saltos == []


class TestAcumulacion:
    def test_el_arrastre_avanza_de_forma_sostenida(self):
        """Cada tramo de arrastre parte de donde dejo el anterior."""
        z = _barra(frame=1000)
        v = []
        z.frame_pedido.connect(v.append)
        for _ in range(4):
            z._desplazar(-70.0, False)
        assert v == sorted(v), "el video no puede retroceder arrastrando a la izquierda"
        assert v[-1] - 1000 > 30, "cuatro tramos deberian sumar, no repetirse"

    def test_ida_y_vuelta_regresa_al_punto_de_partida(self):
        z = _barra(frame=1000)
        v = []
        z.frame_pedido.connect(v.append)
        z._desplazar(-210.0, False)
        z._desplazar(210.0, False)
        assert v[-1] == pytest.approx(1000, abs=1)


class TestVisibilidadEnElPanel:
    """La lupa desaparecia sin motivo aparente."""

    def _panel(self):
        from karlos_core.utils.config_loader import load_config
        from karlos_core.views.video_panel import VideoPanelView
        cfg, _ = load_config("karate")
        return VideoPanelView(cfg.colors, cfg.video)

    def test_nace_oculta(self):
        assert self._panel().zoom_bar.isHidden()

    def test_show_zoom_la_saca_y_la_guarda(self):
        vp = self._panel()
        vp.show_zoom(True)
        assert not vp.zoom_bar.isHidden()
        vp.show_zoom(False)
        assert vp.zoom_bar.isHidden()

    def test_los_delegados_llegan_al_widget(self):
        vp = self._panel()
        vp.set_zoom_video(5000, 25.0)
        vp.set_zoom_atleta("AO")
        vp.set_zoom_marcas(100, 140)
        vp.set_zoom_frame(120)
        z = vp.zoom_bar
        assert (z._total, z._fps, z._atleta) == (5000, 25.0, "AO")
        assert (z._ini, z._fin, z._frame) == (100, 140, 120)


class TestLoYaAnotadoSeQueda:
    """Las anotaciones guardadas siguen dibujadas en la lupa.

    Marcar a ciegas es como se duplica una acción sin enterarse y como
    una anotación acaba dentro de una pausa. Dibujarlas debajo de la
    curva, en carriles, hace visible el solape: dos acciones que se
    pisan caen en filas distintas.
    """

    def test_lo_que_no_se_pisa_va_todo_en_la_primera_fila(self):
        z = _barra()
        assert z._carriles([(0, 10, "A", False), (20, 30, "B", False),
                            (40, 50, "C", False)]) == [0, 0, 0]

    def test_lo_que_se_pisa_sube_de_fila(self):
        z = _barra()
        assert z._carriles([(0, 100, "A", False), (50, 150, "B", False),
                            (60, 90, "C", False)]) == [0, 1, 2]

    def test_tras_el_solape_se_vuelve_a_bajar(self):
        """Una fila se reutiliza en cuanto queda libre."""
        z = _barra()
        assert z._carriles([(0, 100, "A", False), (50, 150, "B", False),
                            (200, 250, "C", False)]) == [0, 1, 0]

    def test_tocarse_de_punta_no_es_solaparse(self):
        z = _barra()
        assert z._carriles([(0, 100, "A", False), (101, 200, "B", False)]) == [0, 0]

    def test_se_guardan_y_se_pintan_sin_romper(self):
        z = _barra()
        z.set_anotadas([(940, 960, "TSK", False), (950, 980, "FNT", False),
                        (900, 1100, "YME", True)])
        assert len(z._anotadas) == 3
        z.grab()          # no debe lanzar

    def test_un_tramo_al_reves_se_descarta(self):
        z = _barra()
        z.set_anotadas([(100, 50, "MAL", False), (10, 20, "OK", False)])
        assert [x[2] for x in z._anotadas] == ["OK"]

    def test_sin_nada_anotado_sigue_pintando(self):
        z = _barra()
        z.set_anotadas([])
        z.grab()

    def test_la_franja_queda_encima_de_la_regla(self):
        from karlos_core.views import zoom_bar as zb
        z = _barra()
        assert z._base_franja() == z.height() - 16 - zb.ALTO_FRANJA
