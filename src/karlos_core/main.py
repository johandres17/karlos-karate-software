"""Entry point for KARLOS ANNOTATOR — Multisport Platform.

Shows the start screen (and, in an edition with several sports, the sport
launcher before it), loads the sport configuration dynamically, then opens
the main annotator window with the correct taxonomy, scoring rules, and
technique buttons.
"""

import os
import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from karlos_core import __version__
from karlos_core.utils.app_logging import get_logger, setup_logging
from karlos_core.utils.config_loader import load_config
from karlos_core.views.theme import Palette, build_global_qss

# NOTE: AnnotationController is imported lazily inside main(), AFTER the
# sport launcher is shown. Its import chain pulls the heavy stack (cv2,
# numpy, openpyxl, qtawesome, every view) — on slow disks that is several
# seconds during which the user would otherwise stare at nothing.


def diagnostico() -> int:
    """Comprobar que el ejecutable lleva dentro todo lo que necesita.

    Un empaquetado falla de otra manera que el codigo fuente: una
    dependencia que no entro no da error al compilar, lo da el dia que
    se usa. Esto lo ejercita desde dentro del propio ejecutable.

        Karlos Annotator.app/Contents/MacOS/Karlos Annotator --diagnostico
    """
    from karlos_core import identidad
    fallos = []
    lineas = [f"{identidad.en_marcha().nombre.upper()} — diagnostico", ""]

    def decir(texto):
        # En un ejecutable sin consola (Windows, console=False) print
        # no llega a ningun sitio: KARLOS_DIAG_FILE recoge el informe.
        lineas.append(texto)
        try:
            print(texto)
        except OSError:
            pass

    def probar(nombre, funcion):
        try:
            bien, detalle = funcion()
        except Exception as exc:                   # noqa: BLE001
            bien, detalle = False, str(exc)[:90]
        decir(f"  {'OK  ' if bien else 'FALLA'}  {nombre}"
              + (f"  — {detalle}" if detalle else ""))
        if not bien:
            fallos.append(nombre)

    def leer_video():
        import cv2
        import numpy as np
        import tempfile
        from pathlib import Path as _P
        d = _P(tempfile.mkdtemp()) / "v.mp4"
        w = cv2.VideoWriter(str(d), cv2.VideoWriter_fourcc(*"mp4v"), 10.0,
                            (64, 48))
        for i in range(5):
            w.write(np.full((48, 64, 3), i * 20, dtype=np.uint8))
        w.release()
        cap = cv2.VideoCapture(str(d))
        ok_, _f = cap.read()
        cap.release()
        return ok_, "escribe y lee vídeo"

    probar("OpenCV", leer_video)

    def lectores():
        # Los videos del estudio son H.264: los lee FFMPEG (una DLL
        # aparte en Windows) o, si falta, Media Foundation. Saber cual
        # hay dentro es la mitad del diagnostico de "no carga nada".
        import cv2 as _cv
        reg = _cv.videoio_registry
        nombres = sorted({reg.getBackendName(b) for b in reg.getBackends()})
        ffmpeg = bool(reg.hasBackend(_cv.CAP_FFMPEG))
        return ffmpeg, ("FFMPEG " + ("dentro" if ffmpeg else "FALTA")
                        + "; lectores: " + ", ".join(nombres))

    probar("lectores de vídeo", lectores)


    def video_real():
        # Un video de fuera (H.264 en CI): prueba la DLL de ffmpeg que
        # decodifica los videos reales del estudio.
        ruta = os.environ.get("KARLOS_DIAG_VIDEO")
        if not ruta:
            return True, "sin vídeo externo (se salta)"
        import cv2 as _cv
        cap = _cv.VideoCapture(ruta)
        abierto = cap.isOpened()
        lector = cap.getBackendName() if abierto else "ninguno"
        n = int(cap.get(_cv.CAP_PROP_FRAME_COUNT)) if abierto else 0
        ok_, frame = cap.read() if abierto else (False, None)
        cap.release()
        return bool(ok_ and frame is not None), (
            f"{'abre' if abierto else 'NO abre'} con {lector}, {n} frames, "
            f"primer frame {'leído' if ok_ else 'NO leído'}")

    probar("vídeo externo", video_real)

    def fotograma_exacto():
        # La prueba que importa en la maquina del evaluador: pedir
        # fotogramas sueltos y comprobar que el decodificador entrega
        # EXACTAMENTE los pedidos. Si aqui sale que no, el problema no
        # es el programa sino la compilacion de ffmpeg de esa maquina, y
        # se sabe sin tener que estar delante.
        ruta = os.environ.get("KARLOS_DIAG_VIDEO")
        if not ruta:
            return True, "sin vídeo externo (se salta)"
        import cv2 as _cv
        cap = _cv.VideoCapture(ruta)
        if not cap.isOpened():
            return False, "no abre"
        total = int(cap.get(_cv.CAP_PROP_FRAME_COUNT))
        puntos = [p for p in (100, total // 3, total // 2, total - 200)
                  if 0 < p < total]
        fallos = []
        for pedido in puntos:
            cap.set(_cv.CAP_PROP_POS_FRAMES, pedido)
            quedo = int(cap.get(_cv.CAP_PROP_POS_FRAMES))
            ok_, _f = cap.read()
            if not ok_ or quedo != pedido:
                fallos.append(f"{pedido}→{quedo}")
        cap.release()
        return not fallos, (f"{len(puntos)} saltos exactos"
                            if not fallos
                            else "NO cae donde se pide: " + ", ".join(fallos))

    probar("fotograma exacto", fotograma_exacto)


    def reglas():
        from karlos_core.models import regras
        return regras.ESQUIVA_JANELA_S > 0, (
            f"esquiva ≤{regras.ESQUIVA_JANELA_S:.0f}s · não junta ações "
            f"· não recusa fintas curtas")

    probar("livro de códigos", reglas)


    def informe():
        # Las salidas son del deporte (decision 0004): se prueban las suyas.
        from karlos_core import catalogo
        return catalogo.activo().salidas().probar()

    probar("informe PDF", informe)

    def hojas():
        import openpyxl                                        # noqa: F401
        return True, "openpyxl dentro"

    probar("exportar xlsx", hojas)

    def interfaz():
        from PySide6.QtWidgets import QApplication
        from karlos_core import catalogo
        from karlos_core.utils.config_loader import load_config
        from karlos_core.views.main_window import MainWindow
        QApplication.instance() or QApplication([])
        # El deporte de la edición.
        cfg, meta = load_config(catalogo.activo().id)
        w = MainWindow(cfg, meta)
        return w.project_hub is not None, "la ventana se construye"

    probar("interfaz", interfaz)

    decir(f"\n{'Todo en orden.' if not fallos else 'FALLOS: ' + ', '.join(fallos)}")
    destino = os.environ.get("KARLOS_DIAG_FILE")
    if destino:
        from pathlib import Path as _P
        _P(destino).write_text("\n".join(lineas), encoding="utf-8")
    return 1 if fallos else 0


def deporte_de_arranque() -> Optional[str]:
    """El deporte con el que arranca el programa: el de la edición."""
    from karlos_core import catalogo
    deportes = catalogo.registrados()
    return deportes[0] if deportes else None


def main() -> None:
    """Launch the KARLOS ANNOTATOR application flow.

    1. The sport of the edition.
    2. Load the selected sport's configuration.
    3. The start screen: the annotation mode (and the language).
    4. Open the main window (Bout Info available via toolbar button).

    Lo arranca una edición (karlos_ediciones), que pone sus deportes y su
    identidad antes (decisión 0006).
    """
    from karlos_core import identidad
    try:
        edicion = identidad.en_marcha()
    except LookupError:
        # Sin edición no hay deportes que elegir: mejor decirlo que abrir
        # un selector vacío.
        sys.stderr.write("Karlos se arranca desde una edición: "
                         "python -m karlos_ediciones.karate\n")
        sys.exit(2)
    setup_logging()
    log = get_logger(__name__)
    try:
        from karlos_core._build_info import BUILD_COMMIT, BUILD_TIMESTAMP
    except ImportError:
        BUILD_COMMIT = BUILD_TIMESTAMP = "unknown"
    log.info(
        "%s v%s starting (build %s, %s)",
        edicion.nombre.upper(), edicion.version, BUILD_COMMIT, BUILD_TIMESTAMP,
    )

    # ── Packaged-build smoke test (CI) ────────────────────────────
    # KARLOS_SMOKE_TEST=1 imports the FULL heavy chain — exactly what
    # loads after sport selection — and exits. Catches modules missing
    # from a PyInstaller bundle (e.g. an over-eager Qt exclude) that a
    # launcher-only smoke test cannot see, because the heavy import is
    # deferred until after the launcher.
    if os.environ.get("KARLOS_SMOKE_TEST") == "1":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from karlos_core.controllers.annotation_controller import (  # noqa: F401
            AnnotationController,
        )
        log.info("SMOKE OK: full import chain loads")
        print("SMOKE OK")
        return

    if "--diagnostico" in sys.argv:
        sys.exit(diagnostico())

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName(edicion.nombre)
    app.setApplicationVersion(edicion.version)
    app.setFont(QFont("Inter", 11))

    # ── Apply Premium Dark Pro Theme ──────────────────────────────
    app.setStyleSheet(build_global_qss(Palette()))

    # Step 1 — El deporte de la edición.
    sport_id = deporte_de_arranque()
    if sport_id is None:
        sys.exit(0)
    from karlos_core import catalogo
    catalogo.establecer(sport_id)

    # Step 2 — Load configuration
    config, sport_meta = load_config(sport_id)

    # Step 3 — Qué se analiza: tiempo-movimiento, técnico-táctico o el
    # integrado (decisión 0008). Cerrar la pantalla es salir.
    from karlos_core.views.dialogo_analisis import elegir_al_inicio
    if elegir_al_inicio(config.colors) is None:
        sys.exit(0)

    # Step 4 — Launch main window (heavy import deferred until here)
    from karlos_core.controllers.annotation_controller import (
        AnnotationController,
    )
    controller = AnnotationController(config, sport_meta)
    controller.aplicar_modo_inicial()
    controller.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()