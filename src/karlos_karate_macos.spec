# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Karlos Karate macOS .app bundle (decisión 0006)."""

import sys
from pathlib import Path

block_cipher = None

# Project root (where this spec file lives)
PROJECT_ROOT = Path(SPECPATH)  # SPECPATH = directory containing this .spec


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
        # Icons and resources
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
        'karlos_core',
        'karlos_core.config',
        'karlos_core.controllers',
        'karlos_core.models',
        'karlos_core.utils',
        'karlos_core.views',
        'karlos_core.views.wizard_steps',
        'karlos_core.utils.merge_utils',
        'karlos_core.utils.config_loader',
        'karlos_core.utils.i18n',
        'karlos_core.utils.resource_path',
        'karlos_core.utils._build_info',
        # Las reglas del libro de codigos se importan dentro de
        # funciones: sin esto no entran al bundle.
        'karlos_core.models.regras',
        # QtMultimedia for audio playback
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        # QtCharts for match_report donut charts
        'PySide6.QtCharts',
        'PySide6.QtPrintSupport',
        # Ensure numpy / cv2 are included
        'cv2',
        'numpy',
        'openpyxl',
        # PIL ya no se excluye: reportlab 4.x lo exige.
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # NOTE: QtCharts must NOT be excluded — match_report.py uses it.
        'tkinter', 'matplotlib', 'scipy', 'pandas',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
        'PySide6.QtPdf', 'PySide6.QtDataVisualization',
        'PySide6.QtWebChannel', 'PySide6.QtSql', 'PySide6.QtTest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
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
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / 'karlos_core' / 'assets' / 'karlitos.icns'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

app = BUNDLE(
    coll,
    name=f'{APP_NAME}.app',
    icon=str(PROJECT_ROOT / 'karlos_core' / 'assets' / 'karlitos.icns'),
    bundle_identifier=EDICION.identificador,
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '12.0',
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'NSMicrophoneUsageDescription': f'{APP_NAME} does not use the microphone.',
    },
)