"""Las barras del informe no pueden mentirle al ojo.

En conteos la referencia es el mayor de los dos, que es lo que permite
comparar a los dos atletas de ESTE combate. En porcentajes no: con 0% y
14%, la referencia relativa pinta el 14% de punta a punta y el ojo lee
«acertó todo» donde el número dice «acertó uno de siete».
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    yield QApplication.instance() or QApplication([])


def _ancho_pintado(barra, valor):
    """El ancho que la barra le dará a ese valor, en tanto por uno."""
    barra.resize(620, 100)
    util = max(40, barra.width() - barra.COLUNA_VALOR)
    maximo = (barra._referencia if barra._referencia
              else max(barra._aka, barra._ao, 1.0))
    return (util * (valor / maximo)) / util


def test_en_porcentajes_la_escala_va_de_cero_a_cien():
    from karlos_karate.relatorio_treinador import _Barra
    b = _Barra(0.0, 14.0, "0%", "14%", referencia=100.0)
    assert _ancho_pintado(b, 14.0) == pytest.approx(0.14, abs=0.01), (
        "un 14% no puede ocupar toda la barra")


def test_en_conteos_la_referencia_sigue_siendo_el_mayor():
    """Comparar dos atletas es para lo que sirve, y ahi no cambia."""
    from karlos_karate.relatorio_treinador import _Barra
    b = _Barra(28, 13, "28 ataques", "13 ataques")
    assert _ancho_pintado(b, 28) == pytest.approx(1.0, abs=0.01)
    assert _ancho_pintado(b, 13) == pytest.approx(13 / 28, abs=0.01)


def test_el_cero_deja_un_toco_visible():
    """Sin el, el color del atleta desaparece y no se lee «está en cero»."""
    from karlos_karate.relatorio_treinador import _Barra
    b = _Barra(0.0, 14.0, "0%", "14%", referencia=100.0)
    b.resize(620, 100)
    util = max(40, b.width() - b.COLUNA_VALOR)
    assert max(6.0, util * (0.0 / 100.0)) == 6.0


def test_las_dos_barras_de_porcentaje_del_informe_usan_la_escala_fija():
    import inspect
    from karlos_karate import relatorio_treinador as R
    fuente = inspect.getsource(R.RelatorioTreinador)
    for metodo in ("_aproveitamento", "_defesa"):
        trozo = fuente.split(f"def {metodo}")[1].split("def ")[0]
        assert "referencia=100.0" in trozo, metodo
