"""Ninguna hoja de estilo puede estar rota.

Un `}}` dentro de un literal SIN prefijo f no se colapsa: queda un `}`
de mas y Qt **descarta la hoja entera**, asi que el widget sale sin
estilo y nadie se entera, porque el aviso va al stderr entre otros mil.

Habia ocho: dos en el hub, dos en el popup de parada y cuatro en el
selector de deporte.
"""

from __future__ import annotations

import io
import pathlib
import tokenize

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
# Lo del karate se mudó a su paquete (fase F4): se vigila igual.
KARATE = RAIZ.parent / "karlos_karate"


def _literales_sin_f(ruta: pathlib.Path):
    src = ruta.read_text(encoding="utf-8")
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.STRING:
            continue
        crudo = tok.string
        resto = crudo.lstrip("rbufRBUF")
        pref = crudo[:len(crudo) - len(resto)].lower()
        if "f" in pref:
            continue          # ahi las llaves dobles son correctas
        yield tok.start[0], crudo


@pytest.mark.parametrize("ruta", sorted(
    p for raiz in (RAIZ, KARATE) for p in raiz.rglob("*.py") if "tests" not in p.parts))
def test_ningun_literal_sin_f_lleva_llaves_dobles_de_css(ruta):
    malos = []
    for linea, crudo in _literales_sin_f(ruta):
        if '"""' in crudo or "'''" in crudo:
            continue          # docstrings: sus llaves son prosa
        if ("}}" in crudo or "{{" in crudo) and (";" in crudo or "px" in crudo):
            malos.append(f"{ruta.name}:{linea}  {crudo.strip()[:70]}")
    assert not malos, (
        "llaves dobles en un literal sin f — Qt descarta la hoja entera:\n  "
        + "\n  ".join(malos))


def test_las_hojas_de_estilo_del_anotador_se_leen(qt_app=None):
    """Y la comprobacion de verdad: que Qt no rechace ninguna."""
    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication, QPushButton, QWidget
    QApplication.instance() or QApplication([])
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.main_window import MainWindow
    cfg, _ = load_config("karate")
    w = MainWindow(cfg, {"id": "karate", "name": "Karate"})
    rotas = []
    for hijo in w.findChildren(QWidget):
        css = hijo.styleSheet()
        if not css:
            continue
        avisos: list[str] = []
        qInstallMessageHandler(lambda t, c, m: avisos.append(m))
        sonda = QPushButton()
        sonda.setStyleSheet(css)
        sonda.ensurePolished()
        qInstallMessageHandler(None)
        if any("Could not parse" in a for a in avisos):
            rotas.append(f"{type(hijo).__name__}: {css[:70]}")
    assert not rotas, "hojas que Qt rechaza:\n  " + "\n  ".join(dict.fromkeys(rotas))
