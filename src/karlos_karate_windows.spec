# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Karlos Karate Windows onedir build (decisión 0006).

Replaces the old CLI one-liner in build-windows.yml. Same inputs, plus
the Qt-junk trim below: PySide6 ships QtQml/QtQuick/QtPdf/etc. that this
app never imports — dropping them shrinks the bundle and speeds up
loading on low-end machines (less disk I/O on startup).
"""

from pathlib import Path

block_cipher = None

PROJECT_ROOT = Path(SPECPATH)

# La identidad sale de la edición (karlos_ediciones/karate.py, decisión 0006):
# el nombre, la versión y el identificador no se escriben aquí.
import sys
sys.path.insert(0, str(PROJECT_ROOT))
from karlos_ediciones.karate import EDICION  # noqa: E402

APP_NAME = EDICION.nombre
APP_VERSION = EDICION.version

a = Analysis(
    [str(PROJECT_ROOT / 'arrancar_karlos_karate.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / 'karlos_core' / 'resources'), 'karlos_core/resources'),
        (str(PROJECT_ROOT / 'karlos_core' / 'assets'), 'karlos_core/assets'),
    ],
    hiddenimports=[
        # La edición y todo el karate (parte se importa dentro de funciones).
        'karlos_ediciones',
        'karlos_ediciones.karate',
        'karlos_karate',
        'karlos_karate.pack',
        'karlos_karate.salidas',
        'karlos_karate.textos',
        'karlos_karate.karate_config',
        'karlos_karate.guided_tree',
        'karlos_karate.csv_combate',
        'karlos_karate.export_manager',
        'karlos_karate.match_report',
        'karlos_karate.relatorio_treinador',
        'karlos_karate.metricas_combate',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtCharts',
        'PySide6.QtPrintSupport',
        'cv2',
        'numpy',
        'reportlab',
        'openpyxl',
        'qtawesome',
        # Las reglas del libro de codigos se importan dentro de
        # funciones: sin esto no entran al bundle.
        'karlos_core.models.regras',
        'karlos_core._build_info',
        'karlos_core.config',
        'karlos_core.controllers',
        'karlos_core.models',
        'karlos_core.utils',
        'karlos_core.views',
        'karlos_core.views.wizard_steps',
        'karlos_core.resources',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # NOTE: QtCharts must NOT be excluded — match_report.py uses it.
        # PIL ya no se excluye: reportlab 4.x lo exige y sin el
        # fallaba el informe PDF en el .exe de Windows.
        'tkinter', 'matplotlib', 'scipy', 'pandas',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.QtPdf', 'PySide6.QtDataVisualization',
        'PySide6.QtWebChannel', 'PySide6.QtSql', 'PySide6.QtTest',
    ],
    cipher=block_cipher,
    noarchive=False,
)

# ── Trim Qt libraries/plugins the app never uses ──────────────────────
# Pulled in transitively by PyInstaller's PySide6 hooks (e.g. the
# virtual-keyboard input plugin drags QtQml+QtQuick; the qpdf image
# plugin drags QtPdf). Name-based filter over binaries and datas.
_QT_JUNK = (
    # App uses: QtCore, QtGui, QtWidgets, QtMultimedia, QtPrintSupport,
    # QtCharts (match_report donuts). Never list those here.
    'QtQml', 'QtQuick', 'QtPdf', 'QtVirtualKeyboard',
    'QtDataVisualization', 'QtWebChannel', 'Qt3D', 'QtSensors',
    'QtPositioning', 'QtLocation', 'QtBluetooth', 'QtNfc',
    'QtSerialPort', 'QtSql', 'QtTest', 'QtDesigner', 'QtHelp',
    'QtRemoteObjects', 'QtScxml', 'QtStateMachine', 'QtWebSockets',
    'QtHttpServer', 'QtQuick3D', 'QtShaderTools', 'QtGraphs',
    'qtvirtualkeyboardplugin', 'qpdf',
)


def _keep(entry):
    return not any(pat in entry[0] for pat in _QT_JUNK)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(PROJECT_ROOT / 'karlos_core' / 'assets' / 'karlitos.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
