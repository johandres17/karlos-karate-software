"""Karlos Karate tiene que dar lo mismo que la 1.0 (fase F1 de las ediciones).

La 1.0 es la versión del estudio (6.14.14). Mientras el código se separa en
núcleo y paquete de karate, cada salida que depende del reglamento —el CSV
del combate con su marcador, faltas, tiempo de juego y fase; la ida y vuelta
del CSV; la exportación antigua y el XLSX; el texto del informe PDF— tiene
que salir idéntica a la que daba la 1.0.

Las referencias de ``datos/referencia_1_0`` se generaron con el código de la
1.0 (``scripts/referencia/generar.py``) a partir de combates sintéticos. Con
la variable ``KARLOS_REFERENCIAS`` apuntando a la carpeta local de
referencias, se comparan también los combates reales, que no están en el
repositorio porque son datos del estudio.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
REFERENCIA = Path(__file__).parent / "datos" / "referencia_1_0"
_GEN = RAIZ / "scripts" / "referencia" / "generar.py"


def _generador():
    sys.path.insert(0, str(_GEN.parent))
    spec = importlib.util.spec_from_file_location("generar_referencia", _GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _comparar(ref: Path, nueva: Path, mismo_entorno: bool) -> list[str]:
    distintos = []
    for f in sorted(p for p in ref.rglob("*") if p.is_file()):
        if f.name in ("entorno.json", "indice.json"):
            continue          # datos de la generación, no salidas de Karlos
        if f.name == "informe.txt" and not mismo_entorno:
            continue
        g = nueva / f.relative_to(ref)
        if not g.exists() or g.read_text(encoding="utf-8") != f.read_text(encoding="utf-8"):
            distintos.append(str(f.relative_to(ref)))
    return distintos


@pytest.fixture(scope="module")
def generador():
    if not _GEN.exists():
        pytest.skip("el generador de referencias no está en esta copia")
    return _generador()


def _mismo_entorno(gen, carpeta: Path) -> bool:
    guardado = json.loads((carpeta / "entorno.json").read_text(encoding="utf-8"))
    actual = gen.entorno()
    return all(guardado.get(k) == actual.get(k) for k in ("reportlab", "pypdf"))


def test_los_combates_sinteticos_salen_como_en_la_1_0(generador, tmp_path):
    import sintetico
    for nombre, (anotaciones, bout, fs, fe) in sintetico.combates().items():
        generador.generar(nombre, anotaciones, bout, fs, fe, tmp_path)
    mismo = _mismo_entorno(generador, REFERENCIA)
    distintos = _comparar(REFERENCIA, tmp_path, mismo)
    assert distintos == [], f"cambió respecto a la 1.0: {distintos}"


def test_los_combates_reales_salen_como_en_la_1_0(generador, tmp_path):
    local = os.environ.get("KARLOS_REFERENCIAS")
    if not local:
        pytest.skip("sin KARLOS_REFERENCIAS: los combates reales solo están en local")
    local = Path(local)
    for sesion in sorted((local / "entradas").glob("*.karlos")):
        anotaciones, bout, fs, fe = generador.cargar_sesion(sesion)
        generador.generar(sesion.name.split("_")[0], anotaciones, bout, fs, fe, tmp_path)
    ref = local / "1.0"
    mismo = _mismo_entorno(generador, ref)
    reales = [d.name for d in ref.iterdir() if d.is_dir() and not d.name.startswith("SINT")]
    distintos = []
    for nombre in reales:
        distintos += _comparar(ref / nombre, tmp_path / nombre, mismo)
    assert distintos == [], f"cambió respecto a la 1.0: {distintos}"
