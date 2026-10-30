"""Lo que la CI necesita saber de una edición, en formato clave=valor.

Va aquí y no dentro del YAML porque en el YAML no se puede probar: una
comilla mal puesta en PowerShell solo se descubre cuando falla la
compilación, veinte minutos después.

    python scripts/edicion_info.py karate
    edicion=karate
    nombre=Karlos Karate
    version=1.2.0
    zip=KarlosKarate-Windows-v1.2.0.zip
    spec=karlos_karate_windows.spec
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))


def info(edicion: str, sistema: str = "windows") -> dict[str, str]:
    e = importlib.import_module(f"karlos_ediciones.{edicion}").EDICION
    return {"edicion": edicion, "nombre": e.nombre, "version": e.version,
            "zip": f"{e.nombre.replace(' ', '')}-{sistema.capitalize()}-v{e.version}.zip",
            "spec": f"karlos_{edicion}_{sistema}.spec"}


if __name__ == "__main__":
    edicion = (sys.argv[1] if len(sys.argv) > 1 else "").strip() or "karate"
    sistema = (sys.argv[2] if len(sys.argv) > 2 else "windows").strip()
    for clave, valor in info(edicion, sistema).items():
        print(f"{clave}={valor}")
