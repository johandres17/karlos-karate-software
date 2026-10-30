"""El formato de sesión común a todas las ediciones (decisiones 0002 y 0004).

En la sesión los dos competidores se guardan siempre con los mismos
códigos, sea cual sea el deporte: AKA el primero y AO el segundo. Vienen
del karate, donde nació el formato, y no cambian por deporte para que una
sesión se abra con cualquier edición y los datos ya anotados sigan valiendo.
Cada deporte pone la etiqueta y el color de cada uno
(``SportPack.competidores``), y sus salidas pueden nombrarlos a su manera.

El primero es el de rojo, como AKA en el karate.
"""
from __future__ import annotations

PRIMERO = "AKA"
SEGUNDO = "AO"
COMPETIDORES = (PRIMERO, SEGUNDO)


def rival(codigo: str) -> str:
    """El otro competidor (de cualquier código que no sea el primero, el
    primero, como hacía el programa)."""
    return SEGUNDO if codigo == PRIMERO else PRIMERO


# La versión del esquema de los datos (decisión 0008). NO es el «version» del
# .karlos, que tiene que seguir siendo "1.0": el lector rechaza cualquier
# otro valor y cambiarlo dejaría ilegibles todas las sesiones de antes. Este
# número dice qué significan los datos: desde el 1.2 una fila puede ser un
# suceso (inicio = fin, sin duración), un intervalo o un estado (PHASE), y
# el combate lleva su análisis (time_motion / technical_tactical / complete).
ESQUEMA = "1.2"

# El análisis de un combate que no lo dice: los de antes de los tres modos
# se anotaron todos con el completo.
ANALISIS_SIN_DECIR = "complete"


def analisis_de(bout_info: dict | None) -> str:
    """El análisis con que se anotó el combate (decisión 0008)."""
    valor = str((bout_info or {}).get("analysis") or "")
    return valor if valor in ("time_motion", "technical_tactical", "complete") else ANALISIS_SIN_DECIR

# Respuestas a preguntas sin columna propia: van con este prefijo en
# `sport_specific_data`, y de ahí a su propia columna en el CSV.
PREFIJO_PREGUNTA = "q:"
