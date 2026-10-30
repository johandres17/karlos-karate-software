# Karlos Karate Software

Karlos Karate Software is an open-source desktop application for the observational analysis of karate bouts
(kumite). It implements two observation frameworks, time-motion and technical-tactical, that can be used
independently or in a combined annotation mode in which action onset and offset, technical-tactical
classification and referee stoppages are recorded together. Effective bout time and scores are reconstructed
from the annotations under explicit rules.

This repository is the public release of **Karlos Karate 1.2** (internal revision e0053ff, 26 October 2026),
the version described in the accompanying article submitted to SoftwareX. It contains the functions described
in the article. The verification runs reported in the article were archived during development; the test
suite in this repository covers the functions included in the public release.

## Annotation modes

| Mode | Annotation units | Native outputs |
|---|---|---|
| **Time-motion** | State transitions by athlete: fighting, preparatory activity, stoppage and unobservable | Duration and proportion of each state; number and mean duration of fighting periods; individual intervals |
| **Technical-tactical** | Point events: athlete, frame, category, technique, attributes and outcome | Counts by athlete, category, technique, context and outcome; recorded points; duration absent |
| **Combined** (labelled *Integrated* in the interface) | Onset and offset of actions and stoppages, with technical-tactical attributes | Action durations, effective bout time and reconstructed points; technical-tactical summaries and derived temporal states |

The start screen asks which analysis to run. Technical-tactical and combined annotation use the same question
tree, answered from the keyboard. Each mode keeps its own session file for the same video. From a combined
record, the technical-tactical representation keeps each action as an event at its onset frame, and the
time-motion representation groups action intervals by athlete when separated by no more than 2 s, with
stoppages taking precedence.

## Architecture

The application is written in Python, with PySide6 (Qt 6) for the interface and OpenCV for video decoding.
It separates four layers: frame navigation, classification, storage and output calculation.

- **Frame navigation** drives frame stepping from the application and accepts a frame only when the decoder
  confirms its position.
- **Classification** follows the observation instrument of the karate package: categories, conditional
  technique attributes and the 2026 World Karate Federation scoring and penalty rules.
- **Storage** keeps every annotation of a bout, observer and pass in a session file next to the video
  (`.karlos_sessions/`), saved atomically with rolling backups.
- **Output calculation** recalculates scores, penalty counts and effective bout time from the annotation
  table with the same functions for the screen and for the exports. Exports are XLSX workbooks with
  mode-specific sheets and a 23-column CSV that the application can re-import.

## Requirements

- Python 3.11 or later.
- The packages in `requirements.txt`: PySide6 6.11, OpenCV 4.13, NumPy, openpyxl, ReportLab, Pillow and
  qtawesome.
- macOS 12 or later (Apple silicon) or Windows 10 or later. Linux is not tested.

## Run from source

    pip install -r requirements.txt
    cd src
    python -m karlos_ediciones.karate

Session files are written next to each video, in `.karlos_sessions/`. Settings, the log and the pass registry
go to `~/.karlos_karate/`. Installers for macOS (DMG) and Windows (ZIP) are built by the workflows in
`.github/workflows/`; see `INSTALL.md`.

## Tests

    pip install pytest pypdf
    cd src
    QT_QPA_PLATFORM=offscreen python -m pytest karlos_core/tests

The suite covers the annotation rules, the derived variables, the session files, the exports, the keyboard
workflow and the interface. A regression test compares the CSV, the CSV round trip, the export, the workbook
and the PDF report text of synthetic bouts with stored reference outputs (`src/karlos_core/tests/datos`).
Tests that open real bout recordings read their folder from the `KARLOS_VIDEOS` environment variable and are
skipped when it is not set; the broadcast videos are not redistributed.

## Documentation

- `docs/Manual_do_Avaliador_Karlos_Karate_1.2.pdf`: the evaluator manual (in Portuguese). It covers the three
  annotation modes, the karate taxonomy, the operational definitions, the annotation workflow, the keyboard
  shortcuts and the exported variables.
- `INSTALL.md`: installation of the pre-built packages and building from source.

## Repository layout

- `src/karlos_core/`: video navigation, annotation controllers, session storage, time-motion calculations,
  exports and interface.
- `src/karlos_karate/`: the karate package, with the observation instrument (question tree), the competition
  rules, the CSV format, the exports and the reports.
- `src/karlos_ediciones/`: the launcher of the Karlos Karate edition.
- `scripts/`: build helpers used by the workflows and the generator of the regression references.

## Licence and citation

Karlos Karate Software is released under the GNU Affero General Public License v3.0 (see `LICENSE`). To cite
the software, use `CITATION.cff`.

Contact: Johan Robalino, Faculty of Sport, University of Porto (up202310701@up.pt).
