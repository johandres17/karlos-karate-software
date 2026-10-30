"""El tiempo-movimiento, de las fases a las salidas.

Lo que hay que saber de las fases está en ``karlos_core.models.fases``: qué
son, cómo se marcan y cómo se derivan de las acciones. Aquí está lo que el
programa hace con ellas de cara afuera, y vive en el núcleo porque no es de
ningún deporte (Johan, 8-10-2026: «muévelo a karlos_core»):

- la hoja «Time-Motion» del Excel y la página del informe en pantalla, que
  el exportador y el informe llaman en una línea cuando el análisis lleva
  tiempo-movimiento;
- las fases como filas del CSV del combate (categoría ``PHASE``), para que
  el dato crudo viaje con el de las acciones, y el camino de vuelta al
  cargar ese CSV.
"""
from __future__ import annotations

from typing import Any, Iterable

from karlos_core.models.fases import ESTADOS, Fases, por_asaltos


def _ajustes() -> dict:
    """Los ajustes de tiempo-movimiento del deporte activo, o {}."""
    from karlos_core import catalogo
    try:
        return catalogo.activo().tiempo_movimiento() or {}
    except Exception:
        return {}


def estados_activos() -> tuple[str, ...]:
    """Los estados que USA el deporte activo, en su orden (decision 0008).

    `ESTADOS` de `models.fases` es el conjunto que vale al LEER, de
    cualquier deporte. Este es el que sale en los informes y en las hojas:
    el karate tiene cuatro y el taekwondo tres, y sin esta diferencia al
    taekwondo le aparecia una columna «unobservable» que no es suya.
    """
    fases = tuple(str(e) for e in (_ajustes().get("phases") or ()) if e in ESTADOS)
    return fases or ESTADOS


def teclas_de_fase() -> dict[str, str]:
    """Digito -> estado, en el orden que diga el deporte: 1, 2, 3 (y 4).

    En el modo tiempo-movimiento no hay tecnicas que elegir, asi que los
    numeros estan libres aunque en karate las diez cifras sean tecnicas en
    los otros modos.
    """
    return {str(i + 1): e for i, e in enumerate(estados_activos())}


def letras_de_fase() -> tuple[tuple[str, str], ...]:
    """(letra, estado) de las letras que el deporte use, o ninguna."""
    letras = [str(x) for x in (_ajustes().get("letters") or ())]
    return tuple(zip(letras, estados_activos()))


def tecla_de_retirar() -> str:
    """La tecla que quita la ultima marca de fase, segun el deporte."""
    return str(_ajustes().get("remove_key") or "Shift+C")


def resumen_de_teclas() -> str:
    """«[1] fighting · [2] preparatory · [3] stoppage · [4] unobservable»,
    con las teclas y los nombres del deporte activo: asi ningun aviso
    escribe a mano las del taekwondo (decision 0008)."""
    return " · ".join(f"[{d}] {rotulo_de_fase(e)}" for d, e in sorted(teclas_de_fase().items()))


def fases_por_atleta() -> bool:
    """Si cada atleta marca sus propias fases (taekwondo y, desde el
    19-10-2026, también karate: la literatura informa por karateka) o las
    fases son del combate (un deporte que lo declare; decisión 0008)."""
    return bool(_ajustes().get("phases_per_athlete", True))


def un_solo_asalto() -> bool:
    """Si el reglamento del deporte activo tiene un solo asalto (karate)."""
    from karlos_core import catalogo
    try:
        return int(catalogo.activo().reglamento.asaltos) <= 1
    except Exception:
        return False


def asaltos_o_combate(asaltos: Any, desde: Any, hasta: Any) -> Any:
    """En un deporte de un solo asalto, el asalto ES el combate.

    Las tablas de tiempo-movimiento van por asalto, porque el asalto es la
    muestra (el especialista). En karate no se marca ningún asalto: [F] y [G] son el
    inicio y el fin del combate. Sin esto la hoja salía en blanco —«No
    complete round marked»— aunque las fases estuvieran bien marcadas.
    Donde hay varios asaltos (taekwondo) no se toca nada: allí un asalto sin
    marcar es un asalto que falta, y se dice.
    """
    if not un_solo_asalto() or desde is None or hasta is None or int(hasta) <= int(desde):
        return asaltos
    combate = [{"asalto": 1, "inicio": int(desde), "fin": int(hasta)}]

    def completo(lista: Any) -> bool:
        return any(isinstance(x, dict) and x.get("inicio") is not None
                   and x.get("fin") is not None for x in (lista or []))

    if isinstance(asaltos, dict):
        return {k: (v if completo(v) else combate) for k, v in asaltos.items()} or combate
    return asaltos if completo(asaltos) else combate


def nota_del_metodo(defecto: str) -> str:
    """Lo que la hoja y el informe dicen del método: el del deporte si lo
    trae (el karate, con Chaabène), y si no el de siempre (el especialista)."""
    return str(_ajustes().get("method_note") or defecto)


def rotulo_de_fase(estado: str) -> str:
    """La palabra del instrumento, sin traducir, con el nombre que le da el
    deporte: el karate llama «preparatory» a lo que el taekwondo llama
    «non-fighting» (Chaabene et al. 2014)."""
    nombre = (_ajustes().get("phase_labels") or {}).get(estado, estado)
    return str(nombre).replace("_", "-")

CATEGORIA_FASE = "PHASE"


def _nombre(estado: str) -> str:
    """La palabra del instrumento, con el nombre que le dé el deporte."""
    return rotulo_de_fase(estado)


def etiquetas_anotadas(filas: Iterable[Any]) -> list[str]:
    """Qué competidores tienen acciones anotadas, con la etiqueta del
    deporte (Chung, Hong) y nunca con el código del formato."""
    from karlos_core import catalogo
    from karlos_core.formato import COMPETIDORES
    filas = list(filas)
    return [catalogo.etiqueta(x) for x in COMPETIDORES
            if any(getattr(r, "athlete", "") == x and getattr(r, "category", "") != "REFEREE STOP"
                   for r in filas)]


# ── El CSV del combate ────────────────────────────────────────────────
def marcas_por_atleta(fases: Any) -> dict[str, list[dict[str, Any]]]:
    """Las marcas de fase de cada atleta (el especialista, 9-10-2026: «mientras
    uno ataca el otro puede estar saltando»; el attack time empieza
    cuando SU pie deja el suelo, así que las fases son de cada uno).

    ``fases`` puede venir como marcas guardadas (``{"fotograma", "fase",
    "atleta"}``) o como filas PHASE del registro. Las marcas de antes, sin
    atleta, caen en la clave ``""``: las del combate entero, que se siguen
    enseñando como tales para no perder nada."""
    salida: dict[str, list[dict[str, Any]]] = {}
    for m in list(fases or []):
        if isinstance(m, dict):
            if m.get("fase") not in ESTADOS:
                continue
            atleta, marca = str(m.get("atleta", "") or ""), {"fotograma": int(m["fotograma"]), "fase": m["fase"]}
        elif getattr(m, "category", "") == CATEGORIA_FASE and getattr(m, "technique", "") in ESTADOS:
            atleta, marca = str(getattr(m, "athlete", "") or ""), {"fotograma": int(m.f_start), "fase": m.technique}
        else:
            continue
        salida.setdefault(atleta, []).append(marca)
    return salida


def atletas_con_fases(fases: Any, filas: Iterable[Any] = ()) -> list[str]:
    """Los atletas que tienen fases marcadas o acciones, en el orden del
    formato; las marcas sin atleta (de antes) van al final como ``""``."""
    from karlos_core.formato import COMPETIDORES
    marcas = marcas_por_atleta(fases)
    filas = list(filas)
    salida = [c for c in COMPETIDORES
              if marcas.get(c) or any(getattr(r, "athlete", "") == c and getattr(r, "category", "")
                                      not in (CATEGORIA_FASE, "REFEREE STOP") for r in filas)]
    if marcas.get(""):
        salida.append("")
    return salida


def asaltos_de(asaltos: Any, atleta: str) -> list[dict[str, Any]]:
    """Los asaltos con que se cortan las fases de ese atleta.

    En el tiempo-movimiento cada atleta marca los suyos (el especialista,
    12-10-2026: al pasar al segundo «no empieza en el Round 1»): llegan
    como ``{atleta: [asaltos]}``. Una lista sola son los del combate, de
    los otros análisis y de las sesiones de antes, y valen para todos."""
    if isinstance(asaltos, dict):
        return list(asaltos.get(atleta) or asaltos.get("") or [])
    return list(asaltos or [])


def filas_de(atleta: str, filas: Iterable[Any]) -> list[Any]:
    """Las acciones de ese atleta y las paradas del árbitro, que son de los
    dos: es de lo que se derivan sus fases. Con ``""`` (marcas sin atleta,
    de antes), todas las acciones, como entonces."""
    filas = [r for r in filas if getattr(r, "category", "") != CATEGORIA_FASE]
    if not atleta:
        return filas
    return [r for r in filas if getattr(r, "athlete", "") == atleta
            or getattr(r, "category", "") == "REFEREE STOP"]


def _por_atleta_y_asalto(intervalos: Iterable[Any]) -> list[tuple[str, int, list[Any]]]:
    """[(atleta, asalto, [intervalos en orden])], en el orden en que vienen."""
    grupos: dict[tuple[str, int], list[Any]] = {}
    for a in intervalos:
        grupos.setdefault((str(getattr(a, "athlete", "") or ""), int(getattr(a, "round", 0) or 0)), []).append(a)
    return [(atleta, ronda, tramos) for (atleta, ronda), tramos in grupos.items()]


def pausas(asaltos: Any, atleta: str, fps: float) -> dict[int, float]:
    """{n: segundos} entre el final del asalto n y el inicio del n+1 de ese
    atleta (el especialista, 15-10-2026: el descanso es de 60 s y casi nunca dura
    eso; él acaba el asalto con la señal del árbitro y empieza el siguiente
    donde empieza, y lo de en medio sale solo)."""
    from karlos_core.models.asaltos import Asaltos
    lista = asaltos_de(asaltos, atleta)
    if not lista:
        return {}
    rondas = Asaltos.de_lista(lista, total=max(1, len(lista)))
    salida = {}
    for n in range(1, rondas.total):
        fin, siguiente = rondas.fin(n), rondas.inicio(n + 1)
        # Solo si hay tiempo entre los dos: un asalto que empieza justo donde
        # acaba el anterior (el descanso marcado como stoppage, como se hacía
        # antes) no tiene pausa que enseñar.
        if fin is not None and siguiente is not None and int(siguiente) - int(fin) > 1:
            salida[n] = (int(siguiente) - int(fin) - 1) / max(float(fps), 1.0)
    return salida


def nombre_de(atleta: str) -> str:
    from karlos_core import catalogo
    return catalogo.etiqueta(atleta) if atleta else "Bout (both)"


def filas_csv(fases: Any, asaltos: Any, fps: float) -> list[Any]:
    """Las fases marcadas como filas: una por intervalo, dentro de los
    asaltos completos, categoría PHASE, con el atleta de la marca."""
    from karlos_core.models.annotation import Annotation
    from karlos_core.models.asaltos import Asaltos

    salida = []
    for atleta, marcas in marcas_por_atleta(fases).items():
        marcadas = Fases.de_lista(marcas)
        lista = asaltos_de(asaltos, atleta)
        if marcadas.vacias or not lista:
            continue
        rondas = Asaltos.de_lista(lista, total=max(1, len(lista)))
        for n in range(1, rondas.total + 1):
            if not rondas.completo(n):
                continue
            for t in marcadas.intervalos(rondas.inicio(n), rondas.fin(n)):
                salida.append(Annotation(
                    athlete=atleta, category=CATEGORIA_FASE, subcategory=CATEGORIA_FASE,
                    technique=t.estado, f_start=t.inicio, f_end=t.fin,
                    duration_s=t.segundos(fps), round=n))
    return salida


def quitar_fases_repetidas(filas: Iterable[Any]) -> list[Any]:
    """La lista sin filas PHASE repetidas (mismo atleta, mismo inicio).
    Las sesiones reabiertas antes del 12-10-2026 las traían dobles."""
    vistos, salida = set(), []
    for r in filas:
        if getattr(r, "category", "") == CATEGORIA_FASE:
            clave = (str(getattr(r, "athlete", "") or ""), int(getattr(r, "f_start", 0)))
            if clave in vistos:
                continue
            vistos.add(clave)
        salida.append(r)
    return salida


def separar_fases(acciones: Iterable[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    """De un CSV leído: (las acciones, las marcas de fase con su atleta).
    Una fila PHASE es un intervalo; su inicio es la marca, y la siguiente
    la cierra."""
    marcas, resto = [], []
    for a in acciones:
        if (getattr(a, "category", "") == CATEGORIA_FASE
                and getattr(a, "technique", "") in ESTADOS):
            marcas.append({"fotograma": int(a.f_start), "fase": a.technique,
                           "atleta": str(getattr(a, "athlete", "") or "")})
        else:
            resto.append(a)
    return resto, marcas


# ── La hoja del Excel ─────────────────────────────────────────────────
def hoja_excel(ws, filas: Iterable[Any], asaltos: Any, fases: Any, fps: float,
               hueco: float, derivar: bool = True) -> None:
    """La hoja «Time-Motion»: por asalto, las fases marcadas con las teclas
    y las derivadas de las acciones, su acuerdo, y debajo los intervalos
    marcados en crudo."""
    from openpyxl.styles import Font

    filas = list(filas)
    marcas = marcas_por_atleta(fases)
    atletas = atletas_con_fases(fases, filas)

    estados = " / ".join(_nombre(e) for e in estados_activos())
    ws.append([f"Time-Motion analysis ({estados}), "
               + ("per athlete" if fases_por_atleta() else "of the bout")])
    ws["A1"].font = Font(bold=True, size=12)
    ws.append([f"Gap that joins two actions into one attack: {hueco:g} s"])
    if not derivar:
        ws.append(["Technical-tactical analysis: the actions are events without duration, "
                   "so no phases are derived from them. The complete analysis gives them."])
    ws.append([nota_del_metodo(
        "The phases are of each athlete: the attack time starts when their foot leaves "
        "the floor. Marked: the phases keyed in by the evaluator (1 / 2 / 3) in that "
        "athlete's pass. Derived: from that athlete's annotated actions and the referee "
        "stops. A feint not followed by an attack is non-fighting; the referee stop ends "
        "the attack.")])
    cabecera = ["Athlete", "Round", "Source", "Round s"]
    for e in estados_activos():
        cabecera += [f"{_nombre(e)} s", f"{_nombre(e)} %"]
    # Con el «unobservable» (karate), además el reparto sobre lo observado,
    # que es el comparable con la literatura (decisión 0008).
    observables = [e for e in estados_activos() if e != "unobservable"] \
        if "unobservable" in estados_activos() else []
    cabecera += [f"{_nombre(e)} % of observed" for e in observables]
    cabecera += ["Attacks", "Mean attack s", "Without phase s", "Agreement %", "Frames compared"]
    hubo = False
    for atleta in atletas:
        tabla = por_asaltos(asaltos_de(asaltos, atleta), filas_de(atleta, filas),
                            marcas.get(atleta, []), fps, hueco, derivar,
                            estados=estados_activos())
        if not tabla:
            continue
        hubo = True
        ws.append([])
        ws.append([nombre_de(atleta)])
        ws[f"A{ws.max_row}"].font = Font(bold=True, size=12)
        ws.append(cabecera)
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
        totales: dict[str, dict] = {}
        for fila in tabla:
            for fuente in ("marcadas", "derivadas"):
                r = fila[fuente]
                if r is None:
                    continue
                datos = [nombre_de(atleta), fila["asalto"],
                         "marked" if fuente == "marcadas" else "derived", round(r["total_s"], 2)]
                for e in estados_activos():
                    datos += [round(r["segundos"][e], 2), round(r["porcentaje"][e], 1)]
                datos += [round(r["porcentaje_observado"].get(e, 0.0), 1) for e in observables]
                datos += [r["ataques"], round(r["ataque_medio_s"], 2), round(r["sin_fase_s"], 2)]
                if fila["acuerdo"] is not None:
                    datos += [round(100.0 * fila["acuerdo"][0], 1), fila["acuerdo"][1]]
                ws.append(datos)
                t = totales.setdefault(fuente, {"total_s": 0.0, "ataques": 0, "ataque_s": 0.0,
                                                "sin_fase_s": 0.0, **{e: 0.0 for e in estados_activos()}})
                t["total_s"] += r["total_s"]
                t["ataques"] += r["ataques"]
                t["ataque_s"] += r["ataque_medio_s"] * r["ataques"]
                t["sin_fase_s"] += r["sin_fase_s"]
                for e in estados_activos():
                    t[e] += r["segundos"][e]
        for fuente, t in totales.items():
            datos = [nombre_de(atleta), "All", "marked" if fuente == "marcadas" else "derived",
                     round(t["total_s"], 2)]
            for e in estados_activos():
                pct = 100.0 * t[e] / t["total_s"] if t["total_s"] else 0.0
                datos += [round(t[e], 2), round(pct, 1)]
            visto = t["total_s"] - t.get("unobservable", 0.0)
            datos += [round(100.0 * t[e] / visto, 1) if visto > 0 else 0.0 for e in observables]
            media = t["ataque_s"] / t["ataques"] if t["ataques"] else 0.0
            datos += [t["ataques"], round(media, 2), round(t["sin_fase_s"], 2)]
            ws.append(datos)
            for cell in ws[ws.max_row]:
                cell.font = Font(bold=True)
    if not hubo:
        ws.append([])
        ws.append(["Mark the start and the end of the bout with F and G first."
                   if un_solo_asalto() else
                   "No complete round marked yet: mark each round with F and G first."])

    # Los intervalos marcados, en crudo: es el dato del tiempo-movimiento.
    # Como en la hoja del especialista (9-10-2026): la muestra es el asalto. Por
    # atleta y por asalto, numerados dentro del asalto, cortados en el
    # cambio de asalto, y una fila de total por asalto.
    intervalos = filas_csv(fases, asaltos, fps)
    if intervalos:
        ws.append([])
        ws.append(["Marked intervals (the round is the sample: numbered within the round, "
                   "cut at the round change, with a total per round)"])
        ws[f"A{ws.max_row}"].font = Font(bold=True, size=12)
        ws.append(["Athlete", "Round", "N° in round", "Phase", "Duration s", "Start s", "End s",
                   "Start frame", "End frame"])
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
        for atleta, ronda, tramos in _por_atleta_y_asalto(intervalos):
            for n, a in enumerate(tramos, start=1):
                ws.append([nombre_de(atleta), ronda, n, _nombre(a.technique), round(a.duration_s, 2),
                           round(a.f_start / fps, 2), round(a.f_end / fps, 2), a.f_start, a.f_end])
            ws.append([nombre_de(atleta), ronda, "", f"Round {ronda} total",
                       round(sum(a.duration_s for a in tramos), 2),
                       round(tramos[0].f_start / fps, 2), round(tramos[-1].f_end / fps, 2),
                       tramos[0].f_start, tramos[-1].f_end])
            for cell in ws[ws.max_row]:
                cell.font = Font(bold=True)
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 12
    for col in "DEFGHIJKLMNO":
        ws.column_dimensions[col].width = 15


# ── La matriz, como la lleva el especialista ─────────────────────────────────
def hoja_matriz(ws, fases: Any, asaltos: Any, fps: float) -> None:
    """La hoja «Time-Motion matrix»: un bloque por atleta, uno al lado del
    otro, como la hoja con que el especialista hace el tiempo-movimiento (12-10-2026):
    Round · N° · Activity · Duration, numerado dentro del asalto y con una
    fila de total, resaltada, al cerrar cada asalto. Cada atleta con sus
    asaltos: los dos bloques no se mezclan."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from karlos_core import catalogo
    from karlos_core.formato import COMPETIDORES

    intervalos = filas_csv(fases, asaltos, fps)
    try:
        colores = catalogo.activo().configuracion().get("colors", {})
    except Exception:            # noqa: BLE001  (un deporte sin configuración)
        colores = {}
    color_de = {COMPETIDORES[0]: colores.get("aka", "#4384E6"),
                COMPETIDORES[1]: colores.get("ao", "#E5534B")}
    amarillo = PatternFill("solid", fgColor="FFF200")
    celeste = PatternFill("solid", fgColor="BDDDE8")
    negrita = Font(bold=True)
    atletas = [a for a in (*COMPETIDORES, "") if any(i.athlete == a for i in intervalos)]
    if not atletas:
        ws.append(["No phases marked inside complete rounds yet: mark each round with F and G, "
                   "and the phases with 1, 2 and 3."])
        return
    ancho = 4                                    # Round · N° · Activity · Duration
    for b, atleta in enumerate(atletas):
        col = 1 + b * (ancho + 1)
        ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + ancho - 1)
        cab = ws.cell(row=1, column=col, value=nombre_de(atleta))
        cab.font = Font(bold=True, color="FFFFFF")
        cab.alignment = Alignment(horizontal="center")
        fondo = (color_de.get(atleta) or "#798394").lstrip("#")
        for c in range(col, col + ancho):
            ws.cell(row=1, column=c).fill = PatternFill("solid", fgColor=fondo)
        for i, titulo in enumerate(("Round", "N° Actions", "Activity", "Duration")):
            celda = ws.cell(row=2, column=col + i, value=titulo)
            celda.font = negrita
            celda.alignment = Alignment(horizontal="center")
        fila = 3
        for ronda_atleta, ronda, tramos in _por_atleta_y_asalto(i for i in intervalos if i.athlete == atleta):
            for n, a in enumerate(tramos, start=1):
                for i, valor in enumerate((ronda, n, _nombre(a.technique), round(a.duration_s, 2))):
                    ws.cell(row=fila, column=col + i, value=valor).alignment = Alignment(horizontal="center")
                fila += 1
            total = round(sum(a.duration_s for a in tramos), 2)
            for i, valor in enumerate((ronda, None, None, total)):
                celda = ws.cell(row=fila, column=col + i, value=valor)
                celda.fill = amarillo
                celda.font = negrita
                celda.alignment = Alignment(horizontal="center")
            fila += 1
            # El descanso hasta el asalto siguiente, en su fila azul.
            pausa = pausas(asaltos, atleta, fps).get(int(ronda))
            if pausa is not None:
                for i, valor in enumerate((None, None, "round pause", round(pausa, 2))):
                    celda = ws.cell(row=fila, column=col + i, value=valor)
                    celda.fill = celeste
                    celda.alignment = Alignment(horizontal="center")
                fila += 1
        for i, w in enumerate((8, 11, 14, 11)):
            ws.column_dimensions[get_column_letter(col + i)].width = w
        ws.column_dimensions[get_column_letter(col + ancho)].width = 3


# ── La página del informe en pantalla ─────────────────────────────────
def html_informe(filas: Iterable[Any], asaltos: Any, fases: Any, fps: float, hueco: float,
                 gris: str, acento: str, derivar: bool = True) -> str:
    """La página «Time-Motion» del informe: por asalto, las fases marcadas,
    las derivadas (con las definiciones del especialista) y su acuerdo."""
    filas = list(filas)
    marcas = marcas_por_atleta(fases)
    atletas = atletas_con_fases(fases, filas)
    defecto = (f"fighting / non-fighting / stoppage, per athlete and per "
               f"round: the attack time starts when that athlete's foot leaves the floor. "
               f"<b>Marked</b>: keyed in with 1, 2 and 3 in that athlete's pass. <b>Derived</b>: "
               f"from that athlete's annotated actions and the referee stops; two actions less "
               f"than {hueco:g} s apart are one attack, a feint not followed by an attack is "
               f"non-fighting, the referee stop ends the attack.")
    html = [f"<h2 style='color:{acento};font-size:15px;margin:0'>Time-Motion</h2>",
            f"<p style='color:{gris}'>{nota_del_metodo(defecto)}</p>"]
    if not derivar:
        html.append(f"<p style='color:{gris}'>Technical-tactical analysis: the actions are "
                    "events without duration, so no phases are derived from them. The "
                    "complete analysis gives them.</p>")
    celda = "padding:4px 10px;border-bottom:1px solid #333;"
    cab = "".join(f"<th style='{celda}text-align:right'>{t}</th>" for t in
                  ["Round", "Source", "Round s"]
                  + [f"{_nombre(e)} s (%)" for e in estados_activos()]
                  + ["Attacks", "Mean attack s", "Agreement"])
    hubo = False
    for atleta in atletas:
        tabla = por_asaltos(asaltos_de(asaltos, atleta), filas_de(atleta, filas),
                            marcas.get(atleta, []), fps, hueco, derivar,
                            estados=estados_activos())
        if not tabla:
            continue
        hubo = True
        cuerpo = []
        for fila in tabla:
            for fuente, nombre in (("marcadas", "marked"), ("derivadas", "derived")):
                r = fila[fuente]
                if r is None:
                    continue
                valores = [str(fila["asalto"]), nombre, f"{r['total_s']:.1f}"]
                valores += [f"{r['segundos'][e]:.1f} ({r['porcentaje'][e]:.0f}%)" for e in estados_activos()]
                valores += [str(r["ataques"]), f"{r['ataque_medio_s']:.1f}"]
                ac = fila["acuerdo"]
                valores.append(f"{100 * ac[0]:.0f}%" if ac else "—")
                cuerpo.append("<tr>" + "".join(
                    f"<td style='{celda}text-align:right'>{v}</td>" for v in valores) + "</tr>")
        html.append(f"<h3 style='color:{acento};font-size:13px;margin:14px 0 4px 0'>{nombre_de(atleta)}</h3>")
        html.append(f"<table cellspacing='0' style='font-size:12px'><tr>{cab}</tr>{''.join(cuerpo)}</table>")
        notas = []
        if all(f["marcadas"] is None for f in tabla):
            notas.append("no phases marked with the keys for this athlete: only the derived ones")
        if all(f["derivadas"] is None for f in tabla):
            notas.append("no actions annotated for this athlete: only the marked phases")
        if notas:
            html.append(f"<p style='color:{gris};margin:2px 0'>{'; '.join(notas)}.</p>")
    if not hubo:
        html.append(f"<p style='color:{gris}'>" + (
            "Mark the start and the end of the bout with F and G first." if un_solo_asalto()
            else "No complete round marked yet: mark each round with F and G first.") + "</p>")
    html.append(html_matriz(fases, asaltos, fps, gris, acento))
    return "".join(html)


def html_matriz(fases: Any, asaltos: Any, fps: float, gris: str, acento: str) -> str:
    """La matriz en el informe y en el PDF, como en la hoja: un luchador a la
    izquierda y el otro a la derecha, Round · N° · Activity · Duration, con
    el total de cada asalto (Johan, 12-10-2026)."""
    from karlos_core.formato import COMPETIDORES
    intervalos = filas_csv(fases, asaltos, fps)
    atletas = [a for a in (*COMPETIDORES, "") if any(i.athlete == a for i in intervalos)]
    if not atletas:
        return ""
    celda = "padding:3px 8px;border-bottom:1px solid #333;text-align:center;"
    bloques = []
    for atleta in atletas:
        filas = [f"<tr><th colspan='4' style='{celda}color:{acento}'>{nombre_de(atleta)}</th></tr>",
                 "<tr>" + "".join(f"<th style='{celda}'>{t}</th>" for t in
                                  ("Round", "N°", "Activity", "Duration")) + "</tr>"]
        for _a, ronda, tramos in _por_atleta_y_asalto(i for i in intervalos if i.athlete == atleta):
            for n, a in enumerate(tramos, start=1):
                filas.append("<tr>" + "".join(f"<td style='{celda}'>{v}</td>" for v in
                                              (ronda, n, _nombre(a.technique), f"{a.duration_s:.2f}")) + "</tr>")
            total = sum(a.duration_s for a in tramos)
            filas.append(f"<tr><td style='{celda}background:#FFF20055'><b>{ronda}</b></td>"
                         f"<td style='{celda}background:#FFF20055'></td><td style='{celda}background:#FFF20055'></td>"
                         f"<td style='{celda}background:#FFF20055'><b>{total:.2f}</b></td></tr>")
            pausa = pausas(asaltos, atleta, fps).get(int(ronda))
            if pausa is not None:
                filas.append(f"<tr><td style='{celda}background:#BDDDE888'></td>"
                             f"<td style='{celda}background:#BDDDE888'></td>"
                             f"<td style='{celda}background:#BDDDE888'>round pause</td>"
                             f"<td style='{celda}background:#BDDDE888'>{pausa:.2f}</td></tr>")
        bloques.append(f"<table cellspacing='0' style='font-size:11px'>{''.join(filas)}</table>")
    columnas = "".join(f"<td valign='top' style='padding-right:28px'>{b}</td>" for b in bloques)
    return (f"<h3 style='color:{acento};font-size:13px;margin:16px 0 4px 0'>Phases per round</h3>"
            f"<p style='color:{gris};margin:0 0 6px 0'>One fighter on the left, the other on the "
            f"right; numbered within the round, with the round total.</p>"
            f"<table cellspacing='0'><tr>{columnas}</tr></table>")
