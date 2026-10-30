"""El barrido de fotogramas lo conduce el programa, no el sistema.

Mantener [L] daba un fotograma, medio segundo de silencio y luego un
avance a tirones al ritmo que tuviera configurado cada máquina. Anotando
karate eso impide clavar el frame exacto de inicio y fin de cada acción,
que es el dato del estudio, y hace que dos evaluadores con ordenadores
distintos se muevan distinto.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication

from karlos_core.controllers.paso_sostenido import (
    ESPERA_MS, INTERVALO_MS, INTERVALO_SALTO_MS, PasoSostenido,
)


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    yield QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture()
def paso():
    dados = []
    p = PasoSostenido(dados.append)
    yield p, dados
    p.soltar()


def _esperar(ms: int) -> None:
    """Dejar correr el bucle de eventos el tiempo pedido."""
    import time
    fin = time.monotonic() + ms / 1000
    while time.monotonic() < fin:
        QCoreApplication.processEvents()
        time.sleep(0.002)


class TestUnToque:
    def test_pulsar_da_un_fotograma_al_instante(self, paso):
        p, dados = paso
        p.pulsar(1)
        assert dados == [1]

    def test_un_toque_corto_no_arranca_el_barrido(self, paso):
        """Así se afina un límite: toque, un fotograma, nada más."""
        p, dados = paso
        p.pulsar(1)
        p.soltar()
        _esperar(ESPERA_MS + 60)
        assert dados == [1]
        assert not p.barriendo


class TestMantenerLaTecla:
    def test_pasado_el_margen_barre_solo(self, paso):
        p, dados = paso
        p.pulsar(1)
        _esperar(ESPERA_MS + INTERVALO_MS * 6)
        assert len(dados) > 2, "el barrido no arrancó"
        assert p.barriendo

    def test_el_barrido_va_de_uno_en_uno(self, paso):
        """Sin aceleración: lo que se pide es ir fotograma a fotograma."""
        p, dados = paso
        p.pulsar(1)
        _esperar(ESPERA_MS + INTERVALO_MS * 8)
        assert set(dados) == {1}

    def test_shift_barre_de_diez_en_diez(self, paso):
        p, dados = paso
        p.pulsar(10)
        _esperar(ESPERA_MS + INTERVALO_SALTO_MS * 3)
        assert set(dados) == {10}
        assert len(dados) > 1

    def test_los_saltos_van_mas_despacio_que_los_fotogramas(self, paso):
        """Un salto de diez cuesta hasta 28 ms: a 16 la ventana se atasca."""
        p, _ = paso
        p.pulsar(1)
        _esperar(ESPERA_MS + 20)
        assert p._barrido.interval() == INTERVALO_MS
        p.pulsar(-10)
        _esperar(ESPERA_MS + 20)
        assert p._barrido.interval() == INTERVALO_SALTO_MS

    def test_soltar_para_en_seco(self, paso):
        p, dados = paso
        p.pulsar(-1)
        _esperar(ESPERA_MS + INTERVALO_MS * 4)
        p.soltar()
        cuantos = len(dados)
        _esperar(INTERVALO_MS * 8)
        assert len(dados) == cuantos
        assert not p.barriendo

    def test_cambiar_de_sentido_no_deja_el_anterior_corriendo(self, paso):
        """[J] después de [L]: el barrido nuevo sustituye al viejo."""
        p, dados = paso
        p.pulsar(1)
        _esperar(ESPERA_MS + INTERVALO_MS * 4)
        dados.clear()
        p.pulsar(-1)
        _esperar(ESPERA_MS + INTERVALO_MS * 6)
        assert set(dados) == {-1}


class TestLaRepeticionDelSistemaNoManda:
    """Windows repetía el atajo pese a `setAutoRepeat(False)`.

    Cada repetición daba un fotograma al ritmo irregular del sistema y
    además reiniciaba la espera, así que el barrido propio no arrancaba
    nunca. Un evaluador veía el avance a tirones en Windows y Johan no lo veía
    en macOS, donde el atajo no repite. Ahora una pulsación que llega
    con la tecla ya abajo se ignora.
    """

    def test_las_repeticiones_no_dan_fotogramas_de_mas(self, paso):
        p, dados = paso
        p.pulsar(1)
        assert dados == [1]
        for _ in range(10):          # como repetiría el sistema
            p.pulsar(1)
        assert dados == [1], "la repetición del sistema movió el vídeo"

    def test_y_el_barrido_propio_llega_a_arrancar(self, paso):
        """Lo que reiniciaba la espera impedía el barrido; ya no."""
        p, dados = paso
        p.pulsar(1)
        for _ in range(4):
            p.pulsar(1)
        _esperar(ESPERA_MS + INTERVALO_MS * 6)
        assert p.barriendo
        assert len(dados) > 2

    def test_cambiar_de_sentido_si_cuenta(self, paso):
        """Ignorar repeticiones no puede sordear un cambio de tecla."""
        p, dados = paso
        p.pulsar(1)
        p.pulsar(-1)
        assert dados == [1, -1]

    def test_tras_soltar_la_siguiente_pulsacion_vuelve_a_contar(self, paso):
        p, dados = paso
        p.pulsar(1)
        p.soltar()
        p.pulsar(1)
        assert dados == [1, 1]


class TestElVigilanteDeLaTecla:
    def test_el_atajo_no_repite_por_su_cuenta(self):
        """`setAutoRepeat(False)`: si no, el sistema y el barrido se pisan."""
        import inspect
        from karlos_core.controllers import shortcut_controller as sc
        fuente = inspect.getsource(sc.ShortcutController._tecla_paso)
        assert "setAutoRepeat(False)" in fuente

    def test_soltar_y_perder_el_foco_paran_el_barrido(self):
        import inspect
        from karlos_core.controllers import shortcut_controller as sc
        fuente = inspect.getsource(sc.ShortcutController._instalar_vigilante)
        for evento in ("KeyRelease", "WindowDeactivate", "FocusOut"):
            assert evento in fuente, evento

    def test_el_vigilante_va_en_la_aplicacion_no_en_la_ventana(self):
        """Un filtro de ventana no ve la tecla que suelta el widget con
        el foco, y el barrido se quedaba corriendo solo."""
        import inspect
        from karlos_core.controllers import shortcut_controller as sc
        fuente = inspect.getsource(sc.ShortcutController._instalar_vigilante)
        assert "app.installEventFilter" in fuente
