"""Las fases del combate: el análisis de tiempo-movimiento.

Cuatro estados por atleta: **fighting** (desde que sale de la guardia hacia
un intercambio hasta que recoge el miembro, el pie vuelve al suelo y cesa el
contacto), **non_fighting** (que el karate rotula «preparatory»: entre
intercambios, o entre una reanudación y el intercambio o la parada
siguientes), **stoppage** (de la interrupción del árbitro a la reanudación)
y **unobservable** (la imagen no permite decidir el estado). Las
definiciones siguen a Chaabène et al. (2014).

Dos caminos a las mismas fases:

1. **Marcadas.** Una tecla por estado, cero preguntas: el evaluador dice en
   qué fase entra el combate y el programa apunta el fotograma. Es el
   análisis de tiempo-movimiento.
2. **Derivadas.** De las acciones anotadas en el análisis integrado. Los
   intervalos de ataques, defensas, acciones tácticas que no son fintas y
   acciones no identificables se agrupan por atleta cuando los separan
   **2 s** o menos; las fintas que preceden a un intercambio dentro de ese
   hueco se incorporan a él y una finta aislada queda como preparación; las
   paradas mandan sobre el combate; y el resto del tiempo es preparación.
   Una acción no identificable por un fallo del vídeo (VideoFault) no es una
   acción sino un tramo en que no se ve el combate, y es **no observable**.

Los fotogramas son inclusivos en los dos extremos, como en las filas y en
los asaltos. El programa no decide nada por el evaluador (decisión 0001):
deriva con sus reglas y las enseña.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

FIGHTING = "fighting"
NON_FIGHTING = "non_fighting"
STOPPAGE = "stoppage"
# El cuarto es una eleccion nuestra, no de la literatura (decision 0008): un
# tramo en el que el video no permite decidir en que estado esta el combate
# no es ninguno de los tres.
UNOBSERVABLE = "unobservable"
# ESTADOS es el conjunto que VALE al leer, de cualquier deporte: lo que no
# este aqui se descarta al cargar una sesion. Los estados que cada deporte
# USA, y que son los que salen en los informes y en las hojas, los dice su
# paquete (karlos_core.tiempo_movimiento.estados_activos).
ESTADOS = (FIGHTING, NON_FIGHTING, STOPPAGE, UNOBSERVABLE)

HUECO_S = 2.0            # dos acciones a menos de esto son el mismo ataque

# Qué filas son acciones (empiezan o alargan un ataque), cuáles son puentes
# (solo cuentan pegadas a un ataque) y cuáles paran el combate.
CATEGORIAS_DE_ACCION = frozenset({"ATTACK", "DEFENSE", "TACTICS", "UNIDENTIFIED"})
# Motivos de una fila no identificable que no describen una accion sino un
# tramo en que el video no deja ver el combate. Medido el 26-10-2026 en 52
# sesiones: VideoFault dura 34 s de mediana y hasta 140 s (ID24, ID27),
# mientras que Occluded, Other, Referee y OutOfFrame son acciones de 0,5 a
# 2 s. Contado como accion, el tramo de 140 s de ID24 daba a AO un 45 % de
# lucha en una pasada y un 6 % en la otra.
MOTIVOS_SIN_VISTA = frozenset({"VideoFault"})
PUENTES = frozenset({"Feint"})
CATEGORIA_PARADA = "REFEREE STOP"


@dataclass(frozen=True)
class Intervalo:
    """Un tramo del combate en una fase, en fotogramas inclusivos."""

    inicio: int
    fin: int
    estado: str

    def fotogramas(self) -> int:
        return max(0, self.fin - self.inicio + 1)

    def segundos(self, fps: float) -> float:
        return self.fotogramas() / max(float(fps), 1.0)


# ── Aritmética de tramos ─────────────────────────────────────────────
def _fusionar(tramos: Iterable[tuple[int, int]], hueco: int = 0) -> list[tuple[int, int]]:
    """Unir los tramos que se solapan, se tocan o distan ``hueco`` o menos."""
    salida: list[tuple[int, int]] = []
    for ini, fin in sorted((int(a), int(b)) for a, b in tramos if b >= a):
        if salida and ini - salida[-1][1] <= hueco + 1:
            salida[-1] = (salida[-1][0], max(salida[-1][1], fin))
        else:
            salida.append((ini, fin))
    return salida


def _restar(tramos: list[tuple[int, int]], quitar: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Los tramos sin lo que haya que quitar."""
    salida: list[tuple[int, int]] = []
    for ini, fin in tramos:
        trozos = [(ini, fin)]
        for qi, qf in quitar:
            nuevos = []
            for ti, tf in trozos:
                if qf < ti or qi > tf:
                    nuevos.append((ti, tf))
                    continue
                if qi > ti:
                    nuevos.append((ti, qi - 1))
                if qf < tf:
                    nuevos.append((qf + 1, tf))
            trozos = nuevos
        salida.extend(trozos)
    return sorted(salida)


def _recortar(tramos: Iterable[tuple[int, int]], desde: int, hasta: int) -> list[tuple[int, int]]:
    salida = []
    for ini, fin in tramos:
        ini, fin = max(ini, desde), min(fin, hasta)
        if fin >= ini:
            salida.append((ini, fin))
    return salida


def _complemento(tramos: list[tuple[int, int]], desde: int, hasta: int) -> list[tuple[int, int]]:
    """Lo que queda de [desde, hasta] fuera de esos tramos."""
    salida, cursor = [], desde
    for ini, fin in sorted(tramos):
        if ini > cursor:
            salida.append((cursor, ini - 1))
        cursor = max(cursor, fin + 1)
    if cursor <= hasta:
        salida.append((cursor, hasta))
    return salida


# ── Las fases marcadas con las teclas ────────────────────────────────
@dataclass
class Fases:
    """Las marcas de fase de un combate: en qué fotograma entra en cada una.

    Una marca vale desde su fotograma hasta la marca siguiente. Volver a
    marcar el mismo fotograma es corregirlo: se queda la última. Son del
    vídeo, como los asaltos: se guardan con la sesión y no se borran al
    cambiar de atleta.
    """

    marcas: list[tuple[int, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.marcas = sorted((int(f), e) for f, e in self.marcas if e in ESTADOS)

    @property
    def vacias(self) -> bool:
        return not self.marcas

    def marcar(self, frame: int, estado: str) -> None:
        if estado not in ESTADOS:
            raise ValueError(f"fase desconocida: {estado!r}")
        frame = int(frame)
        self.marcas = sorted([m for m in self.marcas if m[0] != frame] + [(frame, estado)])

    def quitar_anterior(self, frame: int) -> Optional[tuple[int, str]]:
        """Quitar la última marca puesta en ese fotograma o antes."""
        previas = [m for m in self.marcas if m[0] <= int(frame)]
        if not previas:
            return None
        fuera = previas[-1]
        self.marcas.remove(fuera)
        return fuera

    def quitar(self, frame: int) -> Optional[tuple[int, str]]:
        """Quitar la marca puesta exactamente en ese fotograma, si la hay."""
        for m in self.marcas:
            if m[0] == int(frame):
                self.marcas.remove(m)
                return m
        return None

    def estado_en(self, frame: int) -> Optional[str]:
        """La fase que rige en ese fotograma, o None antes de la primera marca."""
        estado = None
        for f, e in self.marcas:
            if f > int(frame):
                break
            estado = e
        return estado

    def intervalos(self, desde: int, hasta: int) -> list[Intervalo]:
        """Las fases marcadas dentro de [desde, hasta]."""
        salida: list[Intervalo] = []
        if hasta < desde:
            return salida
        puntos = [(desde, self.estado_en(desde))]
        puntos += [(f, e) for f, e in self.marcas if desde < f <= hasta]
        for i, (f, e) in enumerate(puntos):
            fin = puntos[i + 1][0] - 1 if i + 1 < len(puntos) else hasta
            if e is not None and fin >= f:
                salida.append(Intervalo(f, fin, e))
        return salida

    def a_lista(self) -> list[dict[str, Any]]:
        return [{"fotograma": f, "fase": e} for f, e in self.marcas]

    @classmethod
    def de_lista(cls, filas: Any) -> "Fases":
        """Lo guardado, de vuelta; lo que no se entienda se ignora."""
        marcas = []
        for fila in (filas or []):
            try:
                marcas.append((int(fila["fotograma"]), str(fila["fase"])))
            except (TypeError, KeyError, ValueError):
                continue
        return cls(marcas=marcas)

    def resumen(self, fps: float = 30.0) -> str:
        """Lo marcado, en una línea, para la barra de estado."""
        cuenta = {e: sum(1 for _f, x in self.marcas if x == e) for e in ESTADOS}
        return f"{len(self.marcas)} marcas · " + " · ".join(
            f"{e.replace('_', '-')} {n}" for e, n in cuenta.items())


# ── Las fases derivadas de las acciones ───────────────────────────────
def _motivo(fila: Any) -> str:
    """Por que no se pudo identificar la fila: su dato extra o, en sesiones
    de versiones anteriores, el texto «Reason: …» del nivel."""
    extra = getattr(fila, "sport_specific_data", None) or {}
    motivo = str(extra.get("reason", "") or "")
    if not motivo:
        nivel = str(getattr(fila, "level", "") or "")
        for trozo in nivel.split(" | "):
            if trozo.startswith("Reason: "):
                motivo = trozo[len("Reason: "):]
    return motivo.strip()


def derivar(filas: Iterable[Any], desde: int, hasta: int, fps: float,
            hueco_s: float = HUECO_S,
            estados: Iterable[str] = ESTADOS) -> list[Intervalo]:
    """Las fases de [desde, hasta] a partir de las filas anotadas.

    Las filas son las anotaciones (``category``, ``technique``, ``f_start``,
    ``f_end``) de los dos atletas; las de fuera del tramo se recortan o se
    ignoran. Devuelve los tramos ordenados, y cubren el asalto entero.
    """
    fps = max(float(fps), 1.0)
    hueco = int(round(float(hueco_s) * fps))
    acciones, puentes, paradas, sin_vista = [], [], [], []
    for fila in filas:
        try:
            ini, fin = int(fila.f_start), int(fila.f_end)
        except (TypeError, ValueError, AttributeError):
            continue
        if fin < ini or fin < desde or ini > hasta:
            continue
        categoria = str(getattr(fila, "category", "") or "").upper()
        tecnica = str(getattr(fila, "technique", "") or "")
        if categoria == CATEGORIA_PARADA:
            paradas.append((ini, fin))
        elif categoria == "UNIDENTIFIED" and _motivo(fila) in MOTIVOS_SIN_VISTA:
            sin_vista.append((ini, fin))
        elif tecnica in PUENTES:
            puentes.append((ini, fin))
        elif categoria in CATEGORIAS_DE_ACCION:
            acciones.append((ini, fin))

    # 1. Las acciones a menos del hueco son el mismo ataque.
    ataques = _fusionar(acciones, hueco)
    # 2. Una finta pegada por delante alarga el ataque hacia atrás; una
    #    finta suelta no es nada (non-fighting). Varias seguidas, en cadena.
    for _ in range(len(puentes) + 1):
        cambiado = False
        for i, (ini, fin) in enumerate(ataques):
            for pi, pf in puentes:
                if pi < ini and ini - pf <= hueco + 1:
                    ataques[i] = (pi, fin)
                    ini, cambiado = pi, True
        if not cambiado:
            break
    ataques = _fusionar(ataques, hueco)
    # 3. La parada manda: la señal del árbitro acaba el ataque.
    parados = _recortar(_fusionar(paradas), desde, hasta)
    ataques = _recortar(_restar(ataques, parados), desde, hasta)
    # 4. Donde el video no deja ver el combate no hay ataque que contar.
    #    Es no observable si el deporte usa ese estado; si no (taekwondo),
    #    queda como lo demas, non-fighting. La parada sigue mandando.
    ciegos = _recortar(_restar(_fusionar(sin_vista), parados), desde, hasta)
    ataques = _restar(ataques, ciegos)
    if UNOBSERVABLE not in tuple(estados):
        ciegos = []
    # 5. Non-fighting es lo que queda.
    ocupado = _fusionar(ataques + parados + ciegos)
    libres = _complemento(ocupado, desde, hasta)
    salida = ([Intervalo(a, b, FIGHTING) for a, b in ataques]
              + [Intervalo(a, b, STOPPAGE) for a, b in parados]
              + [Intervalo(a, b, UNOBSERVABLE) for a, b in ciegos]
              + [Intervalo(a, b, NON_FIGHTING) for a, b in libres])
    return sorted(salida, key=lambda t: t.inicio)


derivar_fases = derivar     # por si el nombre «derivar» se usa como parámetro


def resumen(intervalos: Iterable[Intervalo], desde: int, hasta: int,
            fps: float, estados: Iterable[str] = ESTADOS) -> dict[str, Any]:
    """Segundos y porcentaje de cada fase, y los ataques, en un tramo.

    ``estados`` son los que lleva la tabla, en su orden. Por defecto los del
    modelo; quien informa pasa los del deporte, porque el karate tiene
    cuatro y el taekwondo tres y a este no le toca una columna que no usa
    (decisión 0008).
    """
    fps = max(float(fps), 1.0)
    total = max(0, hasta - desde + 1)
    fotogramas = {e: 0 for e in estados}
    ataques: list[int] = []
    for t in intervalos:
        ini, fin = max(t.inicio, desde), min(t.fin, hasta)
        if fin < ini or t.estado not in fotogramas:
            continue
        fotogramas[t.estado] += fin - ini + 1
        if t.estado == FIGHTING:
            ataques.append(fin - ini + 1)
    segundos = {e: n / fps for e, n in fotogramas.items()}
    porcentaje = {e: (100.0 * n / total if total else 0.0) for e, n in fotogramas.items()}
    # Sobre lo observado: sin el tiempo «unobservable», que no existe en la
    # literatura. Es la proporción que se compara con Chaabène et al. 2014
    # (decisión 0008). Donde no se usa ese estado, es igual a la de arriba.
    observado = total - fotogramas.get(UNOBSERVABLE, 0)
    porcentaje_observado = {e: (100.0 * n / observado if observado > 0 else 0.0)
                            for e, n in fotogramas.items() if e != UNOBSERVABLE}
    return {
        "total_s": total / fps,
        "segundos": segundos,
        "porcentaje": porcentaje,
        "porcentaje_observado": porcentaje_observado,
        "observado_s": observado / fps,
        "ataques": len(ataques),
        "ataque_medio_s": (sum(ataques) / len(ataques) / fps) if ataques else 0.0,
        "sin_fase_s": max(0, total - sum(fotogramas.values())) / fps,
    }


def por_asaltos(asaltos: Any, filas: Iterable[Any], fases: Any, fps: float,
                hueco_s: float = HUECO_S, derivar: bool = True,
                estados: Iterable[str] = ESTADOS) -> list[dict[str, Any]]:
    """La tabla del combate: una fila por asalto marcado, con las fases
    marcadas (si las hay), las derivadas (si hay acciones) y su acuerdo.

    ``asaltos`` y ``fases`` vienen como van en la sesión guardada (listas), y
    es lo que el informe y el Excel enseñan. Un asalto sin inicio o sin fin
    no se puede contar: no sale. Con ``derivar`` en falso no se deriva nada:
    es el caso del análisis técnico-táctico, donde las acciones son eventos
    sin duración y derivar sería inventar.
    """
    from karlos_core.models.asaltos import Asaltos

    filas = list(filas)
    lista = list(asaltos or [])
    marcadas = Fases.de_lista(fases)
    rondas = Asaltos.de_lista(lista, total=max(1, len(lista)))
    salida: list[dict[str, Any]] = []
    for n in range(1, rondas.total + 1):
        if not rondas.completo(n):
            continue
        desde, hasta = rondas.inicio(n), rondas.fin(n)
        fila: dict[str, Any] = {"asalto": n, "desde": desde, "hasta": hasta,
                                "marcadas": None, "derivadas": None, "acuerdo": None}
        de_marcas = marcadas.intervalos(desde, hasta) if not marcadas.vacias else []
        de_filas = derivar_fases(filas, desde, hasta, fps, hueco_s, estados) if (filas and derivar) else []
        if de_marcas:
            fila["marcadas"] = resumen(de_marcas, desde, hasta, fps, estados)
        if de_filas:
            fila["derivadas"] = resumen(de_filas, desde, hasta, fps, estados)
        if de_marcas and de_filas:
            fila["acuerdo"] = acuerdo(de_marcas, de_filas, desde, hasta)
        salida.append(fila)
    return salida


def acuerdo(unas: Iterable[Intervalo], otras: Iterable[Intervalo],
            desde: int, hasta: int) -> tuple[float, int]:
    """Qué parte de los fotogramas con fase en los dos coincide: (fracción,
    fotogramas comparados). Para comparar lo marcado con lo derivado."""
    def por_fotograma(tramos):
        estado = {}
        for t in tramos:
            for f in range(max(t.inicio, desde), min(t.fin, hasta) + 1):
                estado[f] = t.estado
        return estado
    a, b = por_fotograma(unas), por_fotograma(otras)
    comunes = [f for f in a if f in b]
    if not comunes:
        return 0.0, 0
    iguales = sum(1 for f in comunes if a[f] == b[f])
    return iguales / len(comunes), len(comunes)
