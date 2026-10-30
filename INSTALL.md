# Installation

Karlos Karate Software runs on macOS (Apple silicon) and Windows. It can be installed from the pre-built
packages attached to a release, or run from source with Python.

## macOS (Apple silicon)

1. Download `KarlosKarate-macOS-v<version>-AppleSilicon.dmg` from the
   [Releases](https://github.com/johandres17/karlos-karate-software/releases) page and open it.
2. Drag **Karlos Karate** to the **Applications** folder.
3. **First launch.** macOS shows *"Apple cannot verify that Karlos Karate is free of malware"*: the application is
   not notarised by Apple (notarisation requires a paid developer account). It is not damaged. Unlock it once:
   - **Option A**: double-click the app, press **OK** on the warning, open **System Settings → Privacy &
     Security**, scroll to *"Karlos Karate was blocked…"* and press **Open Anyway**. (On macOS 13 or earlier,
     right-click the app → **Open** → **Open** also works.)
   - **Option B** (Terminal): `xattr -cr "/Applications/Karlos Karate.app"`
4. Requirements: a Mac with Apple silicon (M1 or later) and macOS 12 or later. Intel Macs are not supported.

The DMG includes this guide as a PDF.

### Building the .app and the DMG from source

```bash
cd src
python -m PyInstaller karlos_karate_macos.spec --noconfirm
```

The name, version and bundle identifier come from the edition module, `src/karlos_ediciones/karate.py`; the
spec, the interface and the DMG guide read them from there. Before building, regenerate
`src/karlos_core/_build_info.py` with the current commit and timestamp (`python scripts/generate_build_info.py`).

To check the packaged program:

```bash
"dist/Karlos Karate.app/Contents/MacOS/Karlos Karate" --diagnostico
```

## Windows

### Portable ZIP (recommended)

1. Download `KarlosKarate-Windows-v<version>.zip` from the
   [Releases](https://github.com/johandres17/karlos-karate-software/releases) page.
2. Unzip it into any folder (for example `C:\KarlosKarate`).
3. Run `Karlos Karate.exe` inside that folder.
4. Windows SmartScreen may show a warning: click **More info** and then **Run anyway**.
5. No installation is required; the folder can be moved anywhere.

### From source (Python)

Requirements: Python 3.11 or later ([download](https://www.python.org/downloads/)); tick **Add Python to PATH**
during the installation.

```cmd
git clone https://github.com/johandres17/karlos-karate-software.git
cd karlos-karate-software
pip install -r requirements.txt
cd src
python -m karlos_ediciones.karate
```

## Notes

- Annotations are saved automatically in a `.karlos_sessions` folder next to each video.
- Settings, the pass registry and the application log live in `~/.karlos_karate` (on Windows,
  `%USERPROFILE%\.karlos_karate`).
- Reports (PDF, Excel, CSV) are produced with the **Export** button inside the application.
