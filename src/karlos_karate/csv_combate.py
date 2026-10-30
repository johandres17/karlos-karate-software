# -*- coding: utf-8 -*-
"""El archivo de un combate: una tabla de acciones y nada mas.

El formato anterior sacaba dos archivos por combate y repetia en cada
fila lo que no cambia nunca: el evento, el peso, los dos nombres, el
video. De sus 32 columnas, seis salian siempre vacias, seis eran la
misma constante copiada en cada linea y un par era identico a otro.

Aqui lo que no cambia va arriba, en una cabecera de lineas con '#', y
la tabla solo lleva la accion. Las lineas '#' son comentarios para
pandas (`comment='#'`), para R (`comment.char='#'`) y para el propio
programa, asi que el archivo sigue siendo un CSV corriente.

Y se vuelve a leer: de aqui salen las anotaciones tal cual, con su
video, para seguir editandolas.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from karlos_core.models.annotation import Annotation

VERSION = 2
# Se quitaron 'target' y 'follow_up'. El arbol de PRO no las pregunta y
# nada mas las escribe, asi que salian vacias en TODAS las filas, y una
# columna siempre vacia en un dataset no se lee como "no aplica" sino
# como "aqui falta un dato". Ademas sobran: en karate la zona ES el
# nivel —jodan es la cabeza, chudan el tronco— y lo que vino despues ya
# esta en la propia fila. Las columnas de agrupacion por tiempo (seq,
# combo, vs) se retiraron: el archivo lleva lo observado y agrupar es
# del tratamiento de datos.
COLUMNAS = ["n", "t_s", "active_s", "phase", "f_start", "f_end", "athlete",
            "category", "group", "action", "level", "stance",
            "context", "outcome", "sanction", "reason", "score",
            "pts_aka", "pts_ao",
            "lead", "pen_aka", "pen_ao", "notes"]



def _lado(etiqueta: str) -> str:
    """El nombre de un competidor en las columnas y en la cabecera:
    «AKA» → «aka», «Chung» → «chung», «Red» → «red»."""
    return re.sub(r"[^a-z0-9]+", "_", etiqueta.lower()).strip("_") or "x"


def _columnas(deporte) -> list[str]:
    """Las columnas con los competidores del deporte (decisión 0007): en el
    karate, pts_aka y pen_ao, como siempre; en el taekwondo, pts_chung…"""
    a, b = (_lado(c.etiqueta) for c in deporte.competidores)
    nombres = {"pts_aka": f"pts_{a}", "pts_ao": f"pts_{b}",
               "pen_aka": f"pen_{a}", "pen_ao": f"pen_{b}"}
    return [nombres.get(c, c) for c in COLUMNAS]


def _area(deporte) -> str:
    """Cómo se llama en la cabecera el área de combate: tatami en el
    karate, ring en el boxeo… (lo dice su configuración, «bout_info»)."""
    return str(deporte.configuracion().get("bout_info", {}).get("area", "tatami"))


# El combate de karate dura tres minutos de reloj, que no son tres
# minutos de video: el arbitro lo para. Pasados esos 180 s de juego
# efectivo el informe antiguo marcaba Atoshibaraku, y se mantiene el
# mismo criterio para que lo anotado antes y lo de ahora se comparen.
COMBATE_S = 180.0

# Lo que el arbol guarda dentro de sport_specific_data y su columna. El
# que falta a proposito es base_technique, que sale del nombre de la
# tecnica. Todo lo demas se escribe: una columna vacia cuesta un byte,
# y un dato perdido no se nota hasta que hace falta.
_EXTRA = [("stance", "stance"),
          # La clave interna sigue siendo 'contact' por compatibilidad
          # con lo ya anotado, pero lo que guarda es el dictamen del
          # arbitro, asi que la columna se llama por lo que es.
          ("action_type", "context"), ("contact", "outcome"),
          ("sanction", "sanction"),
          # Por que una accion no se pudo identificar. Va en columna
          # propia y no en las notas: se cuenta, se agrupa y se informa.
          ("reason", "reason")]

# Lo de la cabecera: clave del archivo -> de donde sale en bout_info.
_CABECERA = [("competition", "competition_name"), ("phase", "event_phase"),
             ("category", "category_type"), ("weight", "weight_category"),
             ("pool", "pool"), ("tatami", "tatami"),
             ("bout_number", "bout_number"), ("bout_round", "bout_round"),
             ("evaluator", "evaluator_name"),
             ("institution", "evaluator_institution"),
             # Como acabo: por tiempo, HANSOKU, KIKEN o HANTEI. No es
             # una accion del combate sino un dato sobre el, asi que va
             # con los demas datos y no en la tabla.
             ("ending", "bout_ending"), ("winner", "bout_winner")]

def _fundir(tramos) -> list[tuple[int, int]]:
    """Tramos solapados o contiguos, unidos en uno solo.

    Existe para que restar tiempo parado no cuente dos veces lo que dos
    filas comparten.
    """
    orden = sorted((min(a, b), max(a, b)) for a, b in tramos)
    fundidos: list[list[int]] = []
    for ini, fin in orden:
        if fundidos and ini <= fundidos[-1][1]:
            fundidos[-1][1] = max(fundidos[-1][1], fin)
        else:
            fundidos.append([ini, fin])
    return [(a, b) for a, b in fundidos]


def _juego_efectivo(anotaciones, fps: float, inicio) -> dict:
    """Tiempo de combate real acumulado hasta cada accion, por atleta.

    Las pausas de un atleta solo se descuentan de su propio reloj, que
    es como lo calculaba el informe antiguo.

    De cada pausa se descuenta lo que ya ha transcurrido de ella, no la
    pausa entera: descontarla entera hacia que una accion anotada DENTRO
    de la pausa saliera con menos juego efectivo que otra anterior, y el
    reloj retrocedia.

    Las pausas se FUSIONAN antes de restar. Sin eso, dos filas de parada
    que se pisan restaban su tramo comun dos veces y el reloj retrocedia
    igual: medido en la sesion de ID30, AKA tenia dos paradas solapadas
    (f8177-8676 y f8218-8715) y su juego efectivo caia de 134,7 s a
    121,7 s de una accion a la siguiente, arrastrando tambien la fase.
    La regla de parada unica impide crear hoy ese solape, pero el dato
    ya anotado existe, y un reloj que retrocede no se puede publicar.
    """
    base = int(inicio) if inicio is not None else (
        min((a.f_start for a in anotaciones), default=0))
    fps = fps or 30.0
    crudas: dict[str, list[tuple[int, int]]] = {}
    for a in anotaciones:
        if a.category == "REFEREE STOP":
            crudas.setdefault(a.athlete or "", []).append(
                (int(a.f_start), int(a.f_end)))
    paradas = {at: _fundir(tramos) for at, tramos in crudas.items()}

    salida = {}
    for a in anotaciones:
        hasta = max(base, int(a.f_start))
        parado = sum(
            max(0, min(fin_p, hasta) - max(ini_p, base))
            for ini_p, fin_p in paradas.get(a.athlete or "", []))
        salida[id(a)] = max(0.0, (hasta - base - parado) / fps)
    return salida


def _marcador(anotaciones) -> dict:
    """Como iba el marcador JUSTO ANTES de cada accion.

    Quien va ganando cambia lo que se hace: el que domina espera y el
    que pierde arriesga. Es de las pocas variables de contexto tactico
    que no hay que anotar — sale de las acciones que puntuaron — y sin
    ella no se puede distinguir una decision de un habito.

    Se da antes de la accion a proposito: puesto despues, un ataque que
    puntua vendria con su propio punto ya sumado y cualquier modelo que
    lo use sabria el resultado antes de predecirlo.
    """
    from karlos_core import catalogo
    valor_de = catalogo.activo().reglamento.puntos
    puntos = {"AKA": 0, "AO": 0}
    salida = {}
    for a in anotaciones:
        salida[id(a)] = (puntos["AKA"], puntos["AO"])
        valor = valor_de(a.score)
        if valor and a.athlete in puntos:
            puntos[a.athlete] += valor
    return salida


# La escalera del reglamento 2026: CHUI-1, CHUI-2, CHUI-3,
# HANSOKU-CHUI y HANSOKU. Lo que importa para leer una accion no es el
# nombre de la sancion sino **cuantas lleva encima**: a un atleta en
# CHUI-3 la siguiente le cuesta el combate, y eso le cambia lo que se
# atreve a hacer.
_PELDAÑOS = ("chui", "hansoku", "shikkaku")


def es_sancion(a) -> bool:
    """Si esa anotacion suma un peldaño en la escalera del atleta.

    Vive aqui y no en quien la use porque son dos —el CSV y el contador
    de la pantalla— y dos reglas parecidas acaban discrepando el dia que
    alguien toca una sola.
    """
    texto = f"{a.category} {a.technique}".lower()
    # Una falta cuenta tanto si se anoto sola como si va dentro del
    # ataque que la provoco, que es como se guarda desde que dejo de
    # escribirse dos veces.
    ligada = bool((a.sport_specific_data or {}).get("sanction"))
    return bool(ligada or a.category == "PENALTY"
                or any(p in texto for p in _PELDAÑOS))


def _sanciones(anotaciones, es=None) -> dict:
    """Cuantas sanciones llevaba cada atleta ANTES de cada accion.

    ``es`` dice si una anotación es una sanción; por defecto, la regla del
    karate. El CSV pasa la del deporte que se anota (decisión 0007).
    """
    es = es or es_sancion
    cuenta = {"AKA": 0, "AO": 0}
    salida = {}
    for a in anotaciones:
        salida[id(a)] = (cuenta["AKA"], cuenta["AO"])
        if es(a) and a.athlete in cuenta:
            cuenta[a.athlete] += 1
    return salida


def _fase(activo: float) -> str:
    """En que minuto del combate cae, con el criterio del informe antiguo."""
    if activo <= COMBATE_S:
        return f"Minute_{int(activo // 60) + 1}"
    return "Atoshibaraku"


def componer(anotaciones, *, bout_info=None, video="", fps=30.0,
             fight_start=None, fight_end=None, evaluador="", ocasion=1) -> str:
    """El combate entero como texto CSV (escribir() lo lleva a un fichero)."""
    from karlos_core import catalogo
    deporte = catalogo.activo()
    bout = dict(bout_info or {})
    # Dos acciones pueden empezar en el mismo frame: sin un tercer
    # criterio el desempate es el orden en que llegaron y el numero de
    # secuencia sale hacia atras, que en un archivo que se compara con
    # otro es una diferencia que no significa nada.
    def _clave(a):
        # Dentro del mismo frame manda la secuencia, no la duracion: dos
        # acciones que empiezan a la vez y acaban en distinto sitio se
        # ordenaban por cual acaba antes, y el numero de secuencia salia
        # hacia atras. Pasa en las paradas del arbitro, que se anotan por
        # duplicado para cada atleta con finales que difieren por unos
        # frames.
        return (a.f_start, a.f_end)
    orden = sorted(anotaciones, key=_clave)

    cab = [f"karlos csv v{VERSION}"]
    # Con qué modo y con qué programa se hizo (decisión 0008): sin esto, dos
    # CSV de modos distintos solo se distinguían por lo que traían.
    from karlos_core.formato import ESQUEMA, analisis_de
    from karlos_core.identidad import programa
    cab.append(f"analysis: {analisis_de(bout)}")
    cab.append(f"program: {programa()}")
    cab.append(f"schema: {ESQUEMA}")
    if video:
        cab.append(f"video: {Path(video).name}")
    cab.append(f"fps: {fps:.6g}")
    if fight_start is not None and fight_end is not None:
        cab.append(f"fight: {int(fight_start)}-{int(fight_end)}")
    for clave, origen in _CABECERA:
        valor = str(bout.get(origen, "") or "").strip()
        if valor:
            # El área, con su nombre en el deporte («tatami» en el karate).
            cab.append(f"{_area(deporte) if clave == 'tatami' else clave}: {valor}")
    a_lado, b_lado = (_lado(c.etiqueta) for c in deporte.competidores)
    # En el fichero, cada competidor con su nombre en el deporte (en el
    # karate, AKA y AO); en la sesión se sigue guardando el código.
    nombre_de = {c.codigo: c.etiqueta for c in deporte.competidores}
    for lado, nombre, pais in ((a_lado, "athlete_a_name", "athlete_a_country"),
                               (b_lado, "athlete_b_name", "athlete_b_country")):
        n = str(bout.get(nombre, "") or "").strip()
        p = str(bout.get(pais, "") or "").strip()
        if n or p:
            cab.append(f"{lado}: {n}{f' ({p})' if p else ''}")
    # La guardia de cada uno, si el deporte la pide (decisión 0007).
    for lado, clave in ((a_lado, "athlete_a_guard"), (b_lado, "athlete_b_guard")):
        guardia = str(bout.get(clave, "") or "").strip()
        if guardia:
            cab.append(f"{lado}_guard: {guardia}")
    rondas = {getattr(a, "round", 0) for a in orden} - {0, None}
    if len(rondas) == 1:
        cab.append(f"round: {rondas.pop()}")
    if evaluador:
        cab.append(f"session: {evaluador}/{ocasion}")
    cab.append(f"actions: {len(orden)}")
    # Aqui se escribian tres columnas de agrupacion por tiempo: `seq`
    # (acciones seguidas del mismo atleta), `combo` (posicion en una
    # tanda de ataques) y `vs` (a que accion del rival respondia). Las
    # tres se retiraron el 24-09-2026: el archivo lleva lo observado, y
    # agrupar es del tratamiento de datos, donde el criterio se puede
    # cambiar sin volver a ver los combates.
    cab.append("sem agrupamentos: cada linha é uma ação, e as sequências "
               "montam-se no tratamento dos dados")

    activo = _juego_efectivo(orden, fps or 30.0, fight_start)
    marcador = _marcador(orden)
    sancion = _sanciones(orden, deporte.es_sancion)

    # Las preguntas que no tienen columna propia, cada una en la suya, al
    # final y en el orden en que aparecen. Con el arbol del karate no hay
    # ninguna y el archivo sale con sus columnas de siempre.
    preguntas = _preguntas_extra(orden)

    # Con los asaltos marcados, una fila fuera de todos no es de ninguno.
    # Antes se le daba el asalto que sale del juego efectivo, y pasado el
    # tercero eso es «Round_4» (el especialista, 12-10-2026: «no sé por qué
    # registró algunas acciones como Round_4»). Sin asaltos marcados, la
    # cuenta del juego efectivo sigue siendo lo único que hay.
    asaltos_marcados = deporte.reglamento.asaltos > 1 and any(
        int(getattr(a, "round", 0) or 0) > 0 for a in orden)

    def _fase_de(a) -> str:
        if deporte.reglamento.asaltos > 1 and a.round:
            return f"Round_{a.round}"
        if asaltos_marcados:
            return "Outside_rounds"
        return deporte.reglamento.fase(activo[id(a)])

    # Un combate solo de fases (el análisis de tiempo-movimiento) se escribe
    # por atleta y por asalto: primero todo el de un competidor y después
    # el del otro, como la hoja del especialista, y no mezclados por el tiempo.
    # Los valores se calculan sobre el orden por tiempo (van por id), así
    # que cambiar el orden de escritura no cambia ninguno.
    escritas = orden
    if orden and all(getattr(a, "category", "") == "PHASE" for a in orden):
        lado = {c.codigo: i for i, c in enumerate(deporte.competidores)}
        escritas = sorted(orden, key=lambda a: (lado.get(a.athlete, len(lado)),
                                                int(getattr(a, "round", 0) or 0),
                                                a.f_start, a.f_end))

    buf = io.StringIO()
    for linea in cab:
        buf.write(f"# {linea}\n")
    escritor = csv.writer(buf, lineterminator="\n")
    escritor.writerow(_columnas(deporte) + [_columna_de(k) for k in preguntas])
    for i, a in enumerate(escritas, 1):
        extra = getattr(a, "sport_specific_data", None) or {}
        escritor.writerow([
            i,
            round(a.f_start / fps, 2) if fps else "",
            # Dos decimales, no uno: a 30 fps un fotograma son 0,033 s, y
            # con una decima el archivo no se puede recomprobar contra si
            # mismo. En ID30 una accion caia en 59,96 s, se publicaba
            # como 60,0 y quien recalculara la fase desde la columna leia
            # Minute_2 donde el programa escribio Minute_1.
            round(activo[id(a)], 2),
            # La fase la dice el reglamento del deporte: minutos y
            # Atoshibaraku en el karate, asaltos en los demás. Donde el
            # evaluador marcó dónde empieza y acaba cada asalto, la fase es
            # ESE asalto y no el que sale de dividir el juego efectivo: con
            # tres asaltos de dos minutos la cuenta no sabe de descansos, y
            # el formato del combate puede ser otro (WT art. 7.2).
            _fase_de(a),
            int(a.f_start), int(a.f_end),
            nombre_de.get(a.athlete, a.athlete), a.category,
            # 'group' solo cuando dice algo que 'category' no dice ya:
            # en TACTICS los dos valen "TACTICS", y esa es exactamente la
            # repeticion que este formato viene a quitar.
            "" if a.subcategory == a.category else a.subcategory,
            a.technique,
            a.level or "",
            *[extra.get(k, "") or "" for k, _col in _EXTRA],
            a.score or "",
            marcador[id(a)][0], marcador[id(a)][1],
            # Ventaja del que hace la accion: positiva si va ganando.
            (marcador[id(a)][0] - marcador[id(a)][1])
            * (1 if a.athlete == "AKA" else -1 if a.athlete == "AO" else 0),
            sancion[id(a)][0], sancion[id(a)][1],
            (a.notes or "").replace("\n", " "),
            *[extra.get(k, "") or "" for k in preguntas],
        ])
    return buf.getvalue()


# Columnas que se leen por su nombre: las de ahora y las retiradas que
# puede traer un CSV viejo. Lo demas son preguntas sin columna propia.
_CONOCIDAS = frozenset(COLUMNAS) | {"seq", "combo", "vs"}


def _conocidas() -> frozenset:
    """Las de siempre más las del deporte que se anota (pts_chung…)."""
    from karlos_core import catalogo
    return _CONOCIDAS | frozenset(_columnas(catalogo.activo()))


def _preguntas_extra(orden) -> list[str]:
    from karlos_core.formato import PREFIJO_PREGUNTA
    vistas: list[str] = []
    for a in orden:
        for k in (getattr(a, "sport_specific_data", None) or {}):
            if k.startswith(PREFIJO_PREGUNTA) and k not in vistas:
                vistas.append(k)
    return vistas


def _columna_de(clave: str) -> str:
    """La columna de una pregunta: su nombre, salvo que choque con una fija."""
    from karlos_core.formato import PREFIJO_PREGUNTA
    nombre = clave[len(PREFIJO_PREGUNTA):]
    return f"q_{nombre}" if nombre.lower() in {c.lower() for c in _conocidas()} else nombre


def _clave_de(columna: str) -> str:
    """Lo contrario de `_columna_de`, para leer el CSV."""
    from karlos_core.formato import PREFIJO_PREGUNTA
    nombre = columna
    if columna.startswith("q_") and columna[2:].lower() in {c.lower() for c in _conocidas()}:
        nombre = columna[2:]
    return f"{PREFIJO_PREGUNTA}{nombre}"


def escribir(ruta, anotaciones, **kw) -> str:
    """Escribir el combate entero en un solo CSV."""
    ruta = Path(ruta)
    ruta.write_text(componer(anotaciones, **kw), encoding="utf-8")
    return str(ruta)


def leer(ruta) -> tuple[dict, list[Annotation]]:
    """Leer un combate: (cabecera, anotaciones).

    La cabecera se devuelve tal cual esta escrita; quien la use decide
    que hacer con ella. Una linea de la tabla que no se pueda entender
    se salta en vez de tumbar la carga entera: media sesion recuperada
    vale mas que un error.
    """
    texto = Path(ruta).read_text(encoding="utf-8-sig")
    cabecera: dict[str, str] = {}
    cuerpo: list[str] = []
    for linea in texto.splitlines():
        if linea.startswith("#"):
            limpia = linea.lstrip("#").strip()
            if ":" in limpia:
                k, v = limpia.split(":", 1)
                cabecera[k.strip()] = v.strip()
            elif limpia.lower().startswith("karlos csv"):
                cabecera["version"] = limpia.split("v")[-1]
            continue
        cuerpo.append(linea)

    nombre_video = cabecera.get("video", "")
    conocidas = _conocidas()
    # El fichero nombra a cada competidor como su deporte («Chung»); la
    # sesión guarda el código del formato (AKA/AO).
    from karlos_core import catalogo
    codigo_de = {c.etiqueta: c.codigo for c in catalogo.activo().competidores}
    anotaciones: list[Annotation] = []
    for fila in csv.DictReader(io.StringIO("\n".join(cuerpo))):
        try:
            ini, fin = int(fila["f_start"]), int(fila["f_end"])
        except (KeyError, TypeError, ValueError):
            continue
        extra = {k: fila[col] for k, col in _EXTRA if fila.get(col)}
        for col, valor in fila.items():
            if col and col not in conocidas and (valor or "").strip():
                extra[_clave_de(col)] = valor
        seq = (fila.get("seq") or "").strip()
        if seq:
            extra["sequence_id"] = f"SEQ_{int(seq):03d}" if seq.isdigit() else seq
        anotaciones.append(Annotation(
            athlete=codigo_de.get(fila.get("athlete", "") or "", fila.get("athlete", "") or ""),
            category=fila.get("category", "") or "",
            # 'group' vacio significa "el mismo que category".
            subcategory=(fila.get("group") or fila.get("category") or ""),
            technique=fila.get("action", "") or "",
            level=fila.get("level", "") or "",
            score=fila.get("score", "") or "",
            f_start=ini, f_end=fin,
            # En el técnico-táctico la acción es un suceso y no se midió su
            # duración: vuelve ausente, no a cero (decisión 0008). Se sabe
            # por la cabecera, porque un completo puede tener filas de un
            # fotograma de verdad.
            duration_s=(None if (cabecera.get("analysis") or "").strip() == "technical_tactical"
                        else max(0.0, (fin - ini) / float(cabecera.get("fps", 30) or 30))),
            active_play_s=float(fila["active_s"]) if (
                fila.get("active_s") or "").strip() else None,
            video_file=nombre_video,
            round=int(cabecera["round"]) if str(
                cabecera.get("round", "")).strip().isdigit() else 0,
            notes=fila.get("notes", "") or "",
            sport_specific_data=extra,
        ))
    return cabecera, anotaciones


def buscar_video(ruta_csv, cabecera: dict) -> str:
    """El video al que pertenece ese CSV, si se encuentra.

    Se busca por nombre junto al CSV y en las carpetas de alrededor, que
    es donde suele estar. Si no aparece, se devuelve "" y quien llame
    decide: preguntar o abrir solo la tabla.
    """
    nombre = cabecera.get("video", "").strip()
    if not nombre:
        return ""
    base = Path(ruta_csv).resolve().parent
    for carpeta in (base, base.parent, base.parent / "videos", base / "videos"):
        try:
            candidato = carpeta / nombre
        except (OSError, ValueError):
            continue
        if candidato.is_file():
            return str(candidato)
    # por si el CSV vive en una carpeta de informes al lado de los videos
    for candidato in base.parent.rglob(nombre):
        if candidato.is_file():
            return str(candidato)
    return ""
