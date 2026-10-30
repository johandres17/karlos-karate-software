"""Paquete de karate (kumite, reglamento WKF 2026) para el núcleo de Karlos.

``KaratePack`` se carga al pedirlo: importar un módulo del karate (el CSV
del combate, por ejemplo) no carga el paquete entero, y el núcleo y el
karate se pueden importar en cualquier orden.
"""

__all__ = ["KaratePack"]


def __getattr__(nombre: str):
    if nombre == "KaratePack":
        from karlos_karate.pack import KaratePack
        return KaratePack
    raise AttributeError(f"module 'karlos_karate' has no attribute {nombre!r}")
