# -*- coding: utf-8 -*-
"""Las metricas del combate, para que las lea un entrenador.

Que entra y que no entra esta decidido por la literatura, no por lo que
sea facil de calcular. El resumen de esa revision:

  El VOLUMEN no distingue a un ganador de un perdedor. Chaabene et al.
  (2014, IJSPP 9(2):302-308) midio catorce combates oficiales frame a
  frame y comparo ganadores contra perdedores en todas las variables
  tiempo-movimiento —tiempo de lucha, de preparacion, de parada, ratio
  esfuerzo:pausa, acciones de alta intensidad— y no encontro ni una
  diferencia. Tecnicas por combate: 13±4, ganadores 14±5, perdedores
  12±4, no significativo.

  La EFICACIA si. Vidranski et al. (2015, Coll Antropol 39:95-102), 137
  combates del Mundial: los ganadores se separaron en 11 de 21 variables
  de eficacia situacional. Y el 91% de lo que se lanza en un combate no
  puntua nunca.

  El MOMENTO DECISIVO es lo mas fuerte que tiene el campo. Tabben et al.
  (2018, IJSPP 13(8):1000-1004), 120 combates: "el momento a partir del
  cual uno de los dos domina al otro ininterrumpidamente hasta el final".
  ANTES de el, ganadores y perdedores son indistinguibles; DESPUES, los
  ganadores atacan con el tren superior a la cabeza y los perdedores se
  vuelven reactivos. Un informe que promedia el combate entero borra la
  unica ventana donde los dos atletas se diferencian.

  El ESTADO DEL MARCADOR cambia la conducta. Tabben et al. (2019, IJSPP
  14(5):563-568), 120 combates: los ganadores usan mas pierna mientras
  van por delante (1,0 frente a 0,1 acciones, p=,044). Aqui los datos de
  Karlos van mas finos que los publicados: accion por accion en vez de
  por secuencias.

  Las FINTAS no las ha medido nadie. Busqueda especifica en ingles y
  español: ningun estudio de karate publica frecuencia ni eficacia de
  fintas. Vidranski pidio en 2015 que se incluyeran las acciones que no
  puntuan porque son el 91% del combate, y nadie lo ha hecho. Lo que
  salga de aqui es exploratorio y se marca como tal.

Todo lo que este modulo calcula tiene su cuenta cruda al lado del
porcentaje: con cuarenta ataques por combate, un 14% son dos acciones, y
un entrenador que lee "14%" sin ver "2 de 14" cree que hay una tendencia
donde hay dos golpes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from karlos_core import catalogo

ATAQUE, DEFENSA, TACTICA = "ATTACK", "DEFENSE", "TACTICS"
MANO, PIERNA, SUELO = "HAND TECHNIQUES", "FOOT TECHNIQUES", "SWEEPS & TAKEDOWNS"


def _puntos(a) -> int:
    """Valor en puntos de cada marca, reglamento WKF: el del paquete del
    karate, que acepta el código (WAZA) y el nombre (WAZA-ARI)."""
    return catalogo.paquete("karate").reglamento.puntos(getattr(a, "score", "") or "")


def _es(a, categoria) -> bool:
    return getattr(a, "category", "") == categoria


@dataclass
class Proporcion:
    """Un porcentaje que nunca viaja sin la cuenta de la que sale."""

    parte: int = 0
    total: int = 0

    @property
    def pct(self) -> float:
        return 100.0 * self.parte / self.total if self.total else 0.0

    @property
    def fiable(self) -> bool:
        """Si hay base suficiente para que el porcentaje signifique algo.

        Por debajo de diez intentos un porcentaje es anecdota con
        decimales: de 3 a 4 aciertos sobre 8 se pasa del 38% al 50%.
        """
        return self.total >= 10

    def __str__(self) -> str:
        return f"{self.parte}/{self.total}"


@dataclass
class Eficacia:
    """Los indices de Adam et al. (2012), tal como los usa la literatura."""

    ataques: Proporcion = field(default_factory=Proporcion)   # Ea
    puntos: int = 0                                           # Sa
    puntos_encajados: int = 0                                 # So
    ataques_rival: Proporcion = field(default_factory=Proporcion)

    @property
    def ea(self) -> float:
        """Eficacia del ataque: ataques que puntuan / ataques x 100."""
        return self.ataques.pct

    @property
    def eo(self) -> float:
        """Eficacia de la defensa: (1 - ataques del rival que puntuan /
        ataques del rival) x 100."""
        return 100.0 - self.ataques_rival.pct

    @property
    def sk(self) -> int:
        """Eficiencia total: puntos hechos menos puntos encajados."""
        return self.puntos - self.puntos_encajados


@dataclass
class Tramo:
    """Lo que hizo un atleta en una ventana del combate."""

    ataques: int = 0
    puntos: int = 0
    mano: int = 0
    pierna: int = 0
    suelo: int = 0
    fintas: int = 0
    defensas: int = 0

    @property
    def pct_pierna(self) -> float:
        return 100.0 * self.pierna / self.ataques if self.ataques else 0.0


def ganador(anotaciones) -> tuple[str, int, int]:
    """Quien gana y con que marcador."""
    puntos = {"AKA": 0, "AO": 0}
    for a in anotaciones:
        if getattr(a, "athlete", "") in puntos:
            puntos[a.athlete] += _puntos(a)
    if puntos["AKA"] > puntos["AO"]:
        return "AKA", puntos["AKA"], puntos["AO"]
    if puntos["AO"] > puntos["AKA"]:
        return "AO", puntos["AKA"], puntos["AO"]
    return "", puntos["AKA"], puntos["AO"]


def momento_decisivo(anotaciones, quien_gana: str):
    """El frame tras el cual el ganador ya no vuelve a ir por detras.

    Definicion de Tabben et al. (2018): "el momento a partir del cual uno
    de los dos oponentes domina al otro ininterrumpidamente hasta el
    final del combate". En sus 120 combates de elite cayo en el 49% de la
    duracion, con una desviacion de 33 puntos.

    Devuelve None en un empate o si el ganador nunca llega a ir delante,
    que son los casos en que la definicion no aplica.
    """
    if not quien_gana:
        return None
    puntos = {"AKA": 0, "AO": 0}
    rival = "AO" if quien_gana == "AKA" else "AKA"
    ultimo_sin_mando = None
    for a in sorted(anotaciones, key=lambda x: int(x.f_start)):
        if puntos[quien_gana] <= puntos[rival]:
            ultimo_sin_mando = int(a.f_start)
        if getattr(a, "athlete", "") in puntos:
            puntos[a.athlete] += _puntos(a)
    return ultimo_sin_mando


def eficacia(anotaciones, atleta: str) -> Eficacia:
    """Los indices de eficacia de un atleta."""
    rival = "AO" if atleta == "AKA" else "AKA"
    e = Eficacia()
    for a in anotaciones:
        if not _es(a, ATAQUE):
            continue
        quien = getattr(a, "athlete", "")
        acerto = bool(_puntos(a))
        if quien == atleta:
            e.ataques.total += 1
            e.ataques.parte += acerto
            e.puntos += _puntos(a)
        elif quien == rival:
            e.ataques_rival.total += 1
            e.ataques_rival.parte += acerto
            e.puntos_encajados += _puntos(a)
    return e


def por_clase(anotaciones, atleta: str) -> dict:
    """Intentos y aciertos por clase de tecnica.

    En Tokio 2020 (Seyedi et al. 2024, 216 ataques de los finalistas) las
    combinaciones fueron lo MENOS usado y lo MAS eficaz: 10,6% de los
    intentos con 30,4% de acierto, frente a 25,9% de la mano y 15,6% de
    la pierna. Es de los pocos datos directamente accionables que tiene
    la literatura, y por eso la combinacion va como clase aparte y no
    escondida dentro de mano o pierna.
    """
    salida = {"mano": Proporcion(), "pierna": Proporcion(),
              "suelo": Proporcion(), "combinacion": Proporcion()}
    for a in anotaciones:
        if not _es(a, ATAQUE) or getattr(a, "athlete", "") != atleta:
            continue
        acerto = bool(_puntos(a))
        extra = getattr(a, "sport_specific_data", None) or {}
        encadenado = str(extra.get("combo", "")) not in ("", "1")
        clave = {MANO: "mano", PIERNA: "pierna", SUELO: "suelo"}.get(
            getattr(a, "subcategory", ""))
        if clave:
            salida[clave].total += 1
            salida[clave].parte += acerto
        if encadenado:
            salida["combinacion"].total += 1
            salida["combinacion"].parte += acerto
    return salida


def tramo(anotaciones, atleta: str, dentro) -> Tramo:
    """Resumen de lo que hizo un atleta en la ventana que marque 'dentro'."""
    t = Tramo()
    for a in anotaciones:
        if getattr(a, "athlete", "") != atleta or not dentro(a):
            continue
        if _es(a, ATAQUE):
            t.ataques += 1
            t.puntos += _puntos(a)
            sub = getattr(a, "subcategory", "")
            t.mano += sub == MANO
            t.pierna += sub == PIERNA
            t.suelo += sub == SUELO
        elif _es(a, DEFENSA):
            t.defensas += 1
        elif getattr(a, "technique", "") == "Feint":
            t.fintas += 1
    return t


def fintas(anotaciones, atleta: str, fps: float, ventana_s: float = 1.5) -> dict:
    """Todo lo de las fintas. EXPLORATORIO: no hay con que compararlo.

    Ningun estudio de karate publica frecuencia ni eficacia de fintas.
    Vidranski et al. (2015) señalaron que el 91% de lo que ocurre en un
    combate no puntua y pidieron que se midiera; sigue sin medirse. Asi
    que estos numeros no tienen norma: valen para comparar a un atleta
    consigo mismo y con su rival, no contra un valor de referencia.

    - lanzadas: cuantas hizo
    - respondidas: cuantas hicieron moverse al rival (defensa que apunta
      a esa finta)
    - antes_de_atacar: ataques propios que llegaron tras una finta propia
    - eficacia con finta previa contra eficacia sin ella: el test directo
      de si fintar sirve para algo
    """
    rival = "AO" if atleta == "AKA" else "AKA"
    orden = sorted(anotaciones, key=lambda x: int(x.f_start))
    mias = [a for a in orden
            if getattr(a, "technique", "") == "Feint"
            and getattr(a, "athlete", "") == atleta]
    respondidas = sum(
        1 for a in orden
        if _es(a, DEFENSA) and getattr(a, "athlete", "") == rival
        and (getattr(a, "sport_specific_data", None) or {}).get("vs") == "Feint")

    con, sin = Proporcion(), Proporcion()
    for i, a in enumerate(orden):
        if not _es(a, ATAQUE) or getattr(a, "athlete", "") != atleta:
            continue
        primado = False
        for b in reversed(orden[:i]):
            if not fps or (a.f_start - b.f_start) / fps > ventana_s:
                break
            if getattr(b, "athlete", "") != atleta:
                continue
            if getattr(b, "technique", "") == "Feint":
                primado = True
            break
        destino = con if primado else sin
        destino.total += 1
        destino.parte += bool(_puntos(a))
    return {"lanzadas": len(mias), "respondidas": respondidas,
            "con_finta": con, "sin_finta": sin}


def sanciones_por_marcador(anotaciones, atleta: str) -> dict:
    """Faltas cometidas segun se fuera ganando, empatando o perdiendo.

    Frigout et al. (2020, Front Psychol 10:3025, 309 combates) encontro
    que las faltas de categoria 2 estan asociadas POSITIVAMENTE a ganar
    (chi2=20,87, p<=,01): el que domina las acumula para cerrar el
    combate sin pasar del limite. Asi que el numero de faltas por si solo
    no dice nada; lo que dice algo es cuando se cometen.
    """
    salida = {"ganando": 0, "empatado": 0, "perdiendo": 0}
    puntos = {"AKA": 0, "AO": 0}
    rival = "AO" if atleta == "AKA" else "AKA"
    for a in sorted(anotaciones, key=lambda x: int(x.f_start)):
        if getattr(a, "athlete", "") == atleta:
            extra = getattr(a, "sport_specific_data", None) or {}
            if extra.get("sanction") or _es(a, "PENALTY"):
                d = puntos[atleta] - puntos[rival]
                clave = "ganando" if d > 0 else "perdiendo" if d < 0 else "empatado"
                salida[clave] += 1
        if getattr(a, "athlete", "") in puntos:
            puntos[a.athlete] += _puntos(a)
    return salida
