"""El informe técnico-táctico: lo que recoge ese análisis, y nada más.

Johan (8-10-2026): «cada modo tiene que generar un reporte diferente basado
en los datos que toma». El técnico-táctico recoge cada acción como un
evento: en qué contexto, con qué técnica, con qué miembro, a qué nivel y
cómo acabó. Eso es lo que se cuenta aquí, y no se habla de duraciones
porque no las hay. En el análisis integrado las acciones tienen duración,
y el informe la añade.

Las dimensiones salen de las respuestas que guarda cada fila
(``Action: … | Stance: … | Target: … | Contact: …``), las mismas que
escriben el árbol de preguntas y la ventana de edición.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Iterable, Optional

from karlos_core import catalogo
from karlos_core.formato import COMPETIDORES
from karlos_core.tiempo_movimiento import CATEGORIA_FASE

PARADA = "REFEREE STOP"

# El contexto táctico del ataque, en el orden de prioridad de su clasificación.
TACTICAS = ["Combination", "Counter", "Anticipation", "Direct"]
RESULTADOS = [("Score", "Scored"), ("NoScore", "No point"), ("Foul", "Penalised")]


_CAMPOS = (("action_type", "Action"), ("stance", "Stance"), ("target", "Target"),
           ("contact", "Contact"), ("sanction", "Sanction"), ("reason", "Reason"),
           ("limb", "Limb"))


def dimensiones(fila: Any) -> dict[str, str]:
    """Las respuestas de una fila, por el nombre de su pregunta.

    Al cerrar la acción el programa reparte la cadena de respuestas en los
    campos de la fila (``sport_specific_data``: action_type, stance, target,
    contact, sanction, reason; las preguntas sin columna, con el prefijo de
    ``formato.PREFIJO_PREGUNTA``). Una fila que todavía lleve la cadena
    entera en el nivel (filas de antes) se lee igual.
    """
    from karlos_core.formato import PREFIJO_PREGUNTA
    salida: dict[str, str] = {}
    for parte in str(getattr(fila, "level", "") or "").split("|"):
        if ":" in parte:
            clave, valor = parte.split(":", 1)
            salida[clave.strip()] = valor.strip()
    datos = getattr(fila, "sport_specific_data", None) or {}
    for campo, nombre in _CAMPOS:
        if datos.get(campo):
            salida[nombre] = str(datos[campo])
    for clave, valor in datos.items():
        if isinstance(clave, str) and clave.startswith(PREFIJO_PREGUNTA) and valor:
            salida[clave[len(PREFIJO_PREGUNTA):]] = str(valor)
    return salida


def es_accion(fila: Any) -> bool:
    return getattr(fila, "category", "") not in (CATEGORIA_FASE, PARADA)


def resumen(filas: Iterable[Any], con_duracion: bool,
            puntos: Optional[Callable[[str], int]] = None) -> dict[str, Any]:
    """Por competidor: cuántas acciones y cómo se reparten en cada
    dimensión; las paradas del árbitro, del combate."""
    filas = list(filas)
    puntos = puntos or (lambda _s: 0)
    atletas: dict[str, dict[str, Any]] = {}
    for codigo in COMPETIDORES:
        suyas = [f for f in filas if getattr(f, "athlete", "") == codigo and es_accion(f)]
        dims = [dimensiones(f) for f in suyas]
        r: dict[str, Any] = {
            "acciones": len(suyas),
            "por_tactica": Counter(d.get("Action", "") for d in dims if d.get("Action")),
            "por_categoria": Counter(getattr(f, "category", "") for f in suyas),
            "por_tecnica": Counter(getattr(f, "technique", "") for f in suyas),
            "por_pierna": Counter(d.get("Stance", "") for d in dims if d.get("Stance")),
            "por_lado": Counter(d.get("Sidedness", "") for d in dims if d.get("Sidedness")),
            "por_zona": Counter(d.get("Target", "") for d in dims if d.get("Target")),
            "por_resultado": Counter(d.get("Contact", "") for d in dims if d.get("Contact")),
            "por_acto": Counter(d.get("Sanction", "") for d in dims if d.get("Sanction")),
            "por_asalto": Counter(int(getattr(f, "round", 0) or 0) for f in suyas),
            "puntuadas": sum(1 for f in suyas if puntos(getattr(f, "score", "") or "") > 0),
            "puntos": sum(puntos(getattr(f, "score", "") or "") for f in suyas),
        }
        if con_duracion:
            dur = [float(getattr(f, "duration_s", 0.0) or 0.0) for f in suyas]
            r["duracion_media_s"] = (sum(dur) / len(dur)) if dur else 0.0
            r["duracion_total_s"] = sum(dur)
        atletas[codigo] = r
    paradas = Counter(getattr(f, "technique", "") for f in filas
                      if getattr(f, "category", "") == PARADA)
    return {"atletas": atletas, "paradas": paradas, "con_duracion": bool(con_duracion)}


def _orden(cuenta_por_atleta: list[Counter], primero: list[str] = ()) -> list[str]:
    """Las claves de varios contadores: primero las del orden dado, luego
    las demás por total descendente."""
    total: Counter = Counter()
    for c in cuenta_por_atleta:
        total.update(c)
    fijas = [k for k in primero if k in total]
    resto = sorted((k for k in total if k not in primero), key=lambda k: (-total[k], k))
    return fijas + resto


def _etiqueta_resultado(valor: str) -> str:
    return dict(RESULTADOS).get(valor, valor)


def _tablas(r: dict[str, Any]) -> list[tuple[str, list[tuple[str, list[Any]]]]]:
    """(título, [(fila, [valor por competidor])]) de cada tabla del informe."""
    a = [r["atletas"][c] for c in COMPETIDORES]
    tablas: list[tuple[str, list[tuple[str, list[Any]]]]] = []
    general = [("Actions", [x["acciones"] for x in a]),
               ("Scored actions", [x["puntuadas"] for x in a]),
               ("Points", [x["puntos"] for x in a]),
               ("Penalties conceded", [x["por_resultado"].get("Foul", 0) + sum(x["por_acto"].values())
                                      - x["por_acto"].get("", 0) for x in a])]
    if r["con_duracion"]:
        general += [("Mean action duration (s)", [round(x["duracion_media_s"], 2) for x in a]),
                    ("Total action time (s)", [round(x["duracion_total_s"], 1) for x in a])]
    tablas.append(("Overview", general))

    def tabla(titulo: str, clave: str, primero: list[str] = (), etiqueta=lambda k: k) -> None:
        cuentas = [x[clave] for x in a]
        filas = [(etiqueta(k), [c.get(k, 0) for c in cuentas]) for k in _orden(cuentas, primero)]
        if filas:
            tablas.append((titulo, filas))

    tabla("Tactical context", "por_tactica", TACTICAS)
    tabla("Category", "por_categoria")
    tabla("Technique", "por_tecnica")
    tabla("Limb", "por_pierna", ["Lead", "Rear"])
    tabla("Side", "por_lado", ["Right", "Left"])
    tabla("Target level", "por_zona", ["Jodan", "Chudan", "Gedan"])
    tabla("Outcome", "por_resultado", [k for k, _ in RESULTADOS], _etiqueta_resultado)
    tabla("Prohibited act", "por_acto")
    rondas = _orden([x["por_asalto"] for x in a])
    if rondas:
        tablas.append(("Actions per round", [(f"Round {k}" if k else "No round",
                                              [x["por_asalto"].get(k, 0) for x in a])
                                             for k in sorted(rondas)]))
    if r["paradas"]:
        tablas.append(("Referee stops", [(k or "Stop", [v, ""]) for k, v in r["paradas"].most_common()]))
    return tablas


def html(filas: Iterable[Any], con_duracion: bool, gris: str, acento: str,
         puntos: Optional[Callable[[str], int]] = None) -> str:
    """La página «Technical-tactical» del informe."""
    r = resumen(filas, con_duracion, puntos)
    nombres = [catalogo.etiqueta(c) for c in COMPETIDORES]
    partes = [f"<h2 style='color:{acento};font-size:15px;margin:0'>Technical-tactical</h2>",
              f"<p style='color:{gris}'>Every action as the evaluator classified it: the tactical "
              f"context, the technique, the limb, the target level and the outcome, "
              f"per competitor."
              + (" In this analysis the action is an event: what and when, not how long."
                 if not con_duracion else
                 " The actions carry their duration: mean and total action time are given.")
              + "</p>"]
    if not any(r["atletas"][c]["acciones"] for c in COMPETIDORES) and not r["paradas"]:
        partes.append(f"<p style='color:{gris}'>No actions annotated yet.</p>")
        return "".join(partes)
    celda = "padding:4px 10px;border-bottom:1px solid #333;"
    for titulo, cuerpo in _tablas(r):
        cab = (f"<tr><th style='{celda}text-align:left'>{titulo}</th>"
               + "".join(f"<th style='{celda}text-align:right'>{n}</th>" for n in nombres) + "</tr>")
        filas_html = "".join(
            f"<tr><td style='{celda}'>{nombre}</td>"
            + "".join(f"<td style='{celda}text-align:right'>{v}</td>" for v in valores) + "</tr>"
            for nombre, valores in cuerpo)
        partes.append(f"<table cellspacing='0' style='font-size:12px;margin-top:10px'>{cab}{filas_html}</table>")
    return "".join(partes)


def hoja_excel(ws, filas: Iterable[Any], con_duracion: bool,
               puntos: Optional[Callable[[str], int]] = None) -> None:
    """La hoja «Technical-Tactical» del Excel, con las mismas tablas."""
    from openpyxl.styles import Font

    r = resumen(filas, con_duracion, puntos)
    nombres = [catalogo.etiqueta(c) for c in COMPETIDORES]
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 16
    ws.append(["Technical-tactical analysis"])
    ws["A1"].font = Font(bold=True, size=12)
    ws.append(["The action is an event: what and when, not how long." if not con_duracion
               else "The actions carry their duration."])
    for titulo, cuerpo in _tablas(r):
        ws.append([])
        ws.append([titulo] + nombres)
        for celda in ws[ws.max_row]:
            celda.font = Font(bold=True)
        for nombre, valores in cuerpo:
            ws.append([nombre] + list(valores))
