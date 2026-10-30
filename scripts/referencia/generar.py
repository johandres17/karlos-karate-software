"""Salidas de referencia de Karlos Karate para comparar versiones (fase F1).

Genera, para cada combate, lo que Karlos produce a partir de una sesión:

- ``combate.csv``: el CSV del combate (``csv_combate.componer``), con el
  marcador, las faltas, el tiempo de juego y la fase de cada acción;
- ``ida_y_vuelta.txt``: si ese CSV se vuelve a leer y a escribir igual;
- ``exportacion.csv`` y ``exportacion_xlsx.json``: la exportación antigua
  (``ExportManager``), el XLSX como valores de celda;
- ``informe.txt``: el texto del informe PDF.

Las fechas y horas se sustituyen por marcas fijas para que dos ejecuciones
sean comparables. El código que se mide es el que esté en ``PYTHONPATH``:
así el mismo script sirve para la 1.0 y para la rama nueva.

Uso:
    PYTHONPATH=<copia>/src python3 generar.py SALIDA [--real SESION.karlos ...]

Sin ``--real`` solo genera los combates sintéticos (``sintetico.py``), que
son los que van al repositorio. Los combates reales se guardan solo en
local: son datos del estudio.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))

from rutas import poner_la_edicion  # noqa: E402

poner_la_edicion()

FPS = 30000 / 1001
# Fechas y horas que dependen del día en que se generan. Las dos últimas
# formas se añadieron el 6-10-2026, cuando pasar la medianoche hizo fallar
# las referencias: el identificador que el programa inventa para un combate
# sin identificador (BOUT_AAAAMMDD_…) y la fecha del pie del PDF.
_MESES = "January|February|March|April|May|June|July|August|September|October|November|December"
_FECHA = re.compile(
    r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\b\d{1,2}:\d{2}(:\d{2})?\b"
    r"|(?<=BOUT_)\d{8}(?=_)"
    rf"|\b\d{{1,2}} (?:{_MESES}) \d{{4}}\b")


_COMMIT = re.compile(r"commit:[A-Za-z0-9._-]+")


def _sin_fechas(texto: str) -> str:
    # El commit con que se compiló (Export Build) tampoco es una salida de
    # Karlos: depende de la copia que se mide.
    return _COMMIT.sub("commit:<COMMIT>", _FECHA.sub("<FECHA>", texto))


# Con qué modo, programa y esquema se hizo cada exportación: lo dicen desde
# la 1.2 (decisión 0008) y la 1.0 no. Es una diferencia esperada y declarada,
# como el nombre de la edición en el PDF: se quita antes de comparar, y lo
# que se compara —cada acción, el marcador, las faltas, el tiempo y la
# fase— sigue teniendo que salir idéntico a la 1.0.
_IDENTIDAD_CSV = ("# analysis: ", "# program: ", "# schema: ")
_IDENTIDAD_XLSX = ("Analysis mode", "Program", "Data schema")


def _sin_identidad_csv(texto: str) -> str:
    return "".join(l for l in texto.splitlines(keepends=True)
                   if not l.startswith(_IDENTIDAD_CSV))


def _sin_identidad_xlsx(hojas: dict) -> dict:
    if "Bout Info" in hojas:
        hojas["Bout Info"] = [f for f in hojas["Bout Info"]
                              if not (f and f[0] in _IDENTIDAD_XLSX)]
    return hojas


# El nombre y la versión del programa: cambian con cada edición (decisión
# 0006), igual que la fecha con cada día. Añadido el 6-10-2026: el PDF de la
# 1.0 ponía «KARLOS ANNOTATOR v6.0» escrito a mano y el de cada edición pone
# su nombre y su versión.
_PROGRAMA = re.compile(r"\bKARLOS [A-Z]+(?: v\d+(?:\.\d+)*)?")


def _sin_identidad(texto: str) -> str:
    return _PROGRAMA.sub("<PROGRAMA>", texto)


def _celdas_xlsx(ruta: Path) -> dict:
    from openpyxl import load_workbook
    libro = load_workbook(ruta, data_only=True)
    hojas = {}
    for hoja in libro.worksheets:
        filas = []
        for fila in hoja.iter_rows(values_only=True):
            filas.append([_sin_fechas(str(v)) if v is not None else None for v in fila])
        hojas[hoja.title] = filas
    return hojas


def _texto_pdf(ruta: Path) -> str:
    from pypdf import PdfReader
    paginas = [p.extract_text() or "" for p in PdfReader(str(ruta)).pages]
    return _sin_identidad(_sin_fechas("\n\f\n".join(paginas)))


def generar(nombre: str, anotaciones, bout_info: dict, fight_start, fight_end, salida: Path) -> dict:
    from rutas import modulo
    csv_combate = modulo("karlos_karate.csv_combate", "karlos_annotator.controllers.csv_combate")
    ExportManager = modulo("karlos_karate.export_manager",
                           "karlos_annotator.controllers.export_manager").ExportManager
    generate_professional_report = modulo(
        "karlos_karate.pdf_report_generator",
        "karlos_annotator.utils.pdf_report_generator").generate_professional_report

    d = salida / nombre
    d.mkdir(parents=True, exist_ok=True)
    texto = csv_combate.componer(
        anotaciones, bout_info=bout_info, video=f"{nombre}.mp4", fps=FPS,
        fight_start=fight_start, fight_end=fight_end, evaluador="referencia",
        ocasion=1)
    (d / "combate.csv").write_text(_sin_identidad_csv(texto), encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ruta = tmp / "c.csv"
        ruta.write_text(texto, encoding="utf-8")
        _cab, leidas = csv_combate.leer(ruta)
        otra = csv_combate.componer(
            leidas, bout_info=bout_info, video=f"{nombre}.mp4", fps=FPS,
            fight_start=fight_start, fight_end=fight_end, evaluador="referencia",
            ocasion=1)
        (d / "ida_y_vuelta.txt").write_text(
            "igual\n" if otra == texto else "DISTINTO\n" + otra, encoding="utf-8")

        em = ExportManager()
        em.set_bout_info(bout_info)
        em.set_records(list(anotaciones))
        em.set_sport_id("karate")
        em.set_fps(FPS)
        dur = ((fight_end - fight_start) / FPS) if (fight_start is not None and fight_end is not None) else None
        em.set_fight_info(fight_start, fight_end, dur)
        # Un error tambien es comportamiento: se guarda como resultado para
        # que la version nueva tenga que fallar igual.
        try:
            ruta_exp = Path(em.export_csv(tmp / "e.csv") or (tmp / "e.csv"))
            texto_exp = _sin_fechas(ruta_exp.read_text(encoding="utf-8-sig"))
        except Exception as exc:  # noqa: BLE001
            texto_exp = f"ERROR {type(exc).__name__}: {exc}\n"
        (d / "exportacion.csv").write_text(texto_exp, encoding="utf-8")
        try:
            try:
                em.export_xlsx(str(tmp / "e.xlsx"))
                nota = "ok"
            except ValueError:
                em.export_xlsx(str(tmp / "e.xlsx"), force=True)
                nota = "forzado (no pasa la validación)"
            xlsx = {"nota": nota, "hojas": _sin_identidad_xlsx(_celdas_xlsx(tmp / "e.xlsx"))}
        except Exception as exc:  # noqa: BLE001
            xlsx = {"nota": f"ERROR {type(exc).__name__}: {exc}"}
        (d / "exportacion_xlsx.json").write_text(json.dumps(xlsx, ensure_ascii=False, indent=1),
                                                encoding="utf-8")

        try:
            pdf = generate_professional_report(
                output_path=tmp / "i.pdf", bout_metadata=bout_info, annotations=list(anotaciones),
                session_data={"duration_s": dur or 0.0, "fps": FPS, "video_name": f"{nombre}.mp4"},
                sport_id="karate")
            texto_pdf = _texto_pdf(Path(pdf))
        except Exception as exc:  # noqa: BLE001
            texto_pdf = f"ERROR {type(exc).__name__}: {exc}\n"
        (d / "informe.txt").write_text(texto_pdf, encoding="utf-8")
    return {"combate": nombre, "acciones": len(anotaciones)}


def entorno() -> dict:
    """Versiones de las librerías que dan forma a las salidas: el texto del
    PDF depende de reportlab y de pypdf, así que solo se compara con el
    mismo entorno."""
    from importlib import metadata
    v = {"python": sys.version.split()[0]}
    for paquete in ("reportlab", "openpyxl", "pypdf", "PySide6"):
        try:
            v[paquete] = metadata.version(paquete)
        except metadata.PackageNotFoundError:
            v[paquete] = None
    return v


def cargar_sesion(ruta: Path):
    from rutas import modulo
    SessionManager = modulo("karlos_core.controllers.session_manager",
                            "karlos_annotator.controllers.session_manager").SessionManager
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    anotaciones = [SessionManager.annotation_from_dict(a) for a in datos.get("annotations", [])]
    return anotaciones, datos.get("bout_info") or {}, datos.get("fight_start"), datos.get("fight_end")


def main() -> int:
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    ap = argparse.ArgumentParser()
    ap.add_argument("salida", type=Path)
    ap.add_argument("--real", nargs="*", default=[], type=Path)
    a = ap.parse_args()
    import sintetico
    hecho = []
    for nombre, (anotaciones, bout, fs, fe) in sintetico.combates().items():
        hecho.append(generar(nombre, anotaciones, bout, fs, fe, a.salida))
    for ruta in a.real:
        anotaciones, bout, fs, fe = cargar_sesion(ruta)
        hecho.append(generar(ruta.name.split("_")[0], anotaciones, bout, fs, fe, a.salida))
    (a.salida / "indice.json").write_text(json.dumps(hecho, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.salida / "entorno.json").write_text(json.dumps(entorno(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(hecho, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
