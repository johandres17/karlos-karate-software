"""Arbol de decision para etiquetar una accion paso a paso.

En vez de presentar los dieciseis botones de tecnica mas una ventana con
guardia, nivel, contexto y puntuacion a la vez, se pregunta de lo general
a lo concreto.

El orden de las opciones no es tematico sino de frecuencia, medido sobre
las 228 anotaciones de ID30: fintas 82, esquivas 44, ataques 38, paradas
de arbitro 24, clinch 22, bloqueos 12. Poner lo mas frecuente arriba y a
un solo paso es lo que baja el coste: con el arbol tematico anterior una
finta costaba tres preguntas y era el 41% del esfuerzo total del pase.

El arbol no crea la anotacion: produce el nombre de la tecnica y la cadena
de nivel combinada que ya entiende el resto de la aplicacion, de modo que
el motor combinatorio (Tsuki + Lead -> Kizami Tsuki) sigue haciendo su
trabajo sin cambios.
"""

from __future__ import annotations

from karlos_core.models.no_identificable import MOTIVOS
from karlos_core.utils.i18n import I18n


def _t(clave: str) -> str:
    """El texto de una clave en el idioma activo.

    Se pide al construir cada paso, no al importar el modulo: asi
    cambiar de idioma no obliga a reiniciar el programa.
    """
    return I18n().t(clave)

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Paso:
    """Una pregunta con sus respuestas.

    `grupos` pone un titulillo antes de la opcion indicada. Nueve opciones
    en lista plana hay que leerlas una a una; en bloques el ojo salta al
    bloque. Y agrupadas por familia se aprende la posicion — "mano es 1 y
    2, pie del 3 al 7" se memoriza, "la tercera mas frecuente" no.
    """
    pregunta: str
    opciones: list[tuple[str, str]]        # (etiqueta, clave)
    grupos: tuple[tuple[int, str], ...] = ()   # (indice de opcion, titulo)


# ── Metadatos por tecnica ────────────────────────────────────────────
# (grupo, categoria, pregunta guardia, pregunta nivel, pregunta contexto)
#
# El contexto tactico (directo, contraataque, anticipacion, combinacion)
# es la variable mas citada en el analisis tecnico-tactico de kumite de
# elite. Estaba configurada en diez tecnicas y el arbol no la preguntaba,
# asi que solo la tenian 3 de 228 anotaciones.
_META = {
    "Tsuki":        ("HAND TECHNIQUES", "ATTACK", True, True, True),
    "Uraken":       ("HAND TECHNIQUES", "ATTACK", True, True, True),
    "Other Punch":  ("HAND TECHNIQUES", "ATTACK", True, True, True),
    "Mawashi Geri": ("FOOT TECHNIQUES", "ATTACK", True, True, True),
    "Ura Mawashi":  ("FOOT TECHNIQUES", "ATTACK", True, True, True),
    "Mae Geri":     ("FOOT TECHNIQUES", "ATTACK", True, True, True),
    "Yoko Geri":    ("FOOT TECHNIQUES", "ATTACK", True, True, True),
    "Ushiro Geri":  ("FOOT TECHNIQUES", "ATTACK", False, True, True),  # siempre atrasada
    "Other Kick":   ("FOOT TECHNIQUES", "ATTACK", True, True, True),
    "Ashi-barai":   ("SWEEPS & TAKEDOWNS", "ATTACK", False, False, True),
    "Takedown":     ("SWEEPS & TAKEDOWNS", "ATTACK", False, False, False),
    "Hand Block":   ("BLOCKS & EVASIONS", "DEFENSE", False, False, False),
    "Dodge":        ("BLOCKS & EVASIONS", "DEFENSE", False, False, False),
    "Feint":        ("TACTICS", "TACTICS", False, False, False),
    _t("tree.clinch"):       ("TACTICS", "TACTICS", False, False, False),
    # Paradas de arbitro: el nombre de la tecnica es el motivo de la parada,
    # que es como quedan en el registro exportado.
    # Lo que pasa delante de la camara pero no se puede leer. No lleva
    # nivel, guardia ni contexto: si no se identifica la tecnica, mucho
    # menos sus atributos, y ofrecerlos invitaria a rellenarlos a ojo.
    "Unidentifiable": ("UNIDENTIFIED", "UNIDENTIFIED", False, False, False),
    "Referee":      ("MATCH STATES", "REFEREE STOP", False, False, False),
    "VR":           ("MATCH STATES", "REFEREE STOP", False, False, False),
    "Injury":       ("MATCH STATES", "REFEREE STOP", False, False, False),
}

# Tecnicas de ataque, ordenadas por uso real
# Se ofrecen los nombres YA RESUELTOS, con la guardia dentro.
#
# "Kizami" significa adelantado y "Gyaku" atrasado: la guardia va en el
# propio nombre japones. Preguntar la tecnica base y despues la guardia
# era preguntar lo mismo dos veces y volver a componer lo que el
# evaluador ya sabia. Sobre ID30 se ve perfecto: Gyaku Tsuki sale Rear
# las trece veces, Kizami Tsuki Lead las doce, Kizami Mawashi Lead las
# seis. No es una tendencia, es la definicion.
#
# La lista cubre las ocho tecnicas que aparecen de verdad en ID30; el
# resto queda detras de _t("tree.otra") para no pasar de nueve teclas.
_ATAQUES = [
    ("Gyaku Tsuki", "Tsuki|Rear"),
    ("Kizami Tsuki", "Tsuki|Lead"),
    ("Uraken", "Uraken|Rear"),
    ("Kizami Mawashi", "Mawashi Geri|Lead"),
    ("Mawashi Geri", "Mawashi Geri|Rear"),
    ("Kizami Ura Mawashi", "Ura Mawashi|Lead"),
    ("Ura Mawashi", "Ura Mawashi|Rear"),
    ("Ashi-barai", "Ashi-barai|"),
    (_t("tree.otra"), "otras"),
]
_ATAQUES_GRUPOS = ((0, _t("tree.g_puno")), (3, _t("tree.g_pierna")), (7, _t("tree.g_suelo")))

_OTRAS_RESUELTAS = [
    ("Kizami Mae Geri", "Mae Geri|Lead"),
    ("Mae Geri", "Mae Geri|Rear"),
    ("Kizami Yoko Geri", "Yoko Geri|Lead"),
    ("Yoko Geri", "Yoko Geri|Rear"),
    ("Ushiro Geri (giro)", "Ushiro Geri|Rear"),
    ("Kizami Uraken", "Uraken|Lead"),
    (_t("tree.otro_puno"), "Other Punch|Rear"),
    (_t("tree.otra_pat"), "Other Kick|Rear"),
    (_t("tree.proyeccion"), "Takedown|"),
]


_PARADAS = [(_t("tree.p_decision"), "Referee"), (_t("tree.p_video"), "VR"),
            (_t("tree.p_lesion"), "Injury")]

# Los motivos de «Não identificável» son del programa, no del karate:
# viven en el núcleo (decisión 0004).
_MOTIVOS = MOTIVOS

# Conductas prohibidas, agrupadas. El reglamento de 2026 lista diecisiete
# tipos y los pone todos en UNA sola escalera — desaparecen las categorias
# 1 y 2 y los grados CHUKOKU y KEIKOKU ("SINGLE LINE OF WARNINGS &
# PENALTIES / SINGLE CATEGORY"). Diecisiete opciones en pantalla no se
# leen, asi que se agrupan en ocho que las cubren.
#
# El grado NO se elige: sale del contador del atleta — Chui 1ª, 2ª, 3ª,
# Hansoku-Chui, Hansoku.
#
# Aqui estan SOLO las faltas que no son un ataque. El contacto excesivo y
# la zona prohibida tienen tecnica, guardia y nivel como cualquier golpe:
# se registran como el resultado del ataque, no por aqui. Si estuvieran en
# los dos sitios habria dos formas de anotar lo mismo y los datos saldrian
# distintos segun el camino elegido.
# Conductas que no son un ataque. Los nombres son los del reglamento,
# con la traduccion al lado donde el termino japones no se explica solo.
# El orden sigue al reglamento: primero las que ocurren combatiendo y
# despues las de simulacion, que escalan mas rapido.
_FALTAS = [
    (_t("tree.f_jogai"), "F:Jogai"),
    (_t("tree.f_pasiv"), "F:Passivity"),
    (_t("tree.f_evitar"), "F:Avoiding"),
    (_t("tree.f_agarre"), "F:Clinching"),
    (_t("tree.f_mubobi"), "F:Mubobi"),
    (_t("tree.f_exagera"), "F:Exaggerating"),
    (_t("tree.f_simula"), "F:Feigning"),
    (_t("tree.f_conducta"), "F:Conduct"),
]
_FALTAS_GRUPOS = ((0, _t("tree.g_combate")), (5, _t("tree.g_simula")), (7, _t("tree.g_otras")))

# Guardia y nivel en una sola pregunta: eran dos pasos seguidos de dos
# opciones cada uno, y las cuatro combinaciones caben en una sola tecla.
_GUARDIA_NIVEL = [
    ("Adelantada · Jodan (cabeza)", "Lead|Jodan"),
    ("Adelantada · Chudan (tronco)", "Lead|Chudan"),
    ("Atrasada · Jodan (cabeza)", "Rear|Jodan"),
    ("Atrasada · Chudan (tronco)", "Rear|Chudan"),
]
_SOLO_NIVEL = [(_t("tree.jodan"), "|Jodan"), (_t("tree.chudan"), "|Chudan")]

# Como acaba un ataque: lo que el arbitro dictamina, y nada mas.
#
# Antes habia una cuarta salida, "toco pero no puntua". Se quito porque
# no se puede observar con fiabilidad — con la espalda del atleta de por
# medio no se ve si llego — y porque el reglamento no la usa: el Art. 6
# define la distancia correcta como "entre el roce de piel y 5 cm", asi
# que rozar y quedarse a cuatro centimetros valen igual. Lo que separa
# un punto de un no-punto es la decision arbitral sobre los seis
# criterios, no el contacto.
#
# Una variable que dos evaluadores codificarian distinto mete ruido en
# todo lo que toque y no se defiende. En ID30 salio vacia en los 42
# ataques.
_RESULTADO = [
    (_t("tree.no_puntuo"), "Res:NoScore"),
    (_t("tree.puntuo"), "Res:Score"),
    (_t("tree.sancionada"), "Res:Foul"),
]

# Conductas que sancionan una tecnica. El reglamento las agrupa aparte
# porque escalan mas rapido que el resto: CHUI - HANSOKU-CHUI - HANSOKU,
# saltandose pasos.
# Como acaba un BARRIDO o una PROYECCION. Un barrido no puntua por si
# solo: segun el Art. 6 lo que vale IPPON es la tecnica que llega sobre
# el rival derribado. Ofrecer aqui "Puntuo" era dejar decir que puntuo
# algo a lo que el motor no le da puntos, y el punto se evaporaba.
#
# Lo que hay que saber es si DERRIBO, porque de eso depende que el
# golpe siguiente valga 3 o valga 1.
_RESULTADO_SUELO = [
    (_t("tree.no_derribo"), "Res:Miss"),
    (_t("tree.derribo"), "Res:Down"),
    (_t("tree.sancionada"), "Res:Foul"),
]

_SANCION_ATAQUE = [
    (_t("tree.s_contacto"), "S:Contact"),
    (_t("tree.s_zona"), "S:Target"),
    (_t("tree.s_garganta"), "S:Throat"),
    (_t("tree.s_mano"), "S:OpenHand"),
    (_t("tree.s_proyec"), "S:Throw"),
]

# Contexto tactico, ordenado como aparece en la literatura de kumite:
# el ataque directo es el mas frecuente y el contraataque el segundo.
_CONTEXTO = [
    (_t("tree.directo"), "Act:Direct"),
    (_t("tree.contra"), "Act:Counter"),
    (_t("tree.anticipa"), "Act:Anticipation"),
    (_t("tree.combina"), "Act:Combination"),
]


@dataclass
class ArbolGuiado:
    """Estado del recorrido para una accion."""
    tecnica: str | None = None
    guardia: str | None = None
    nivel: str | None = None
    limbo: str | None = None          # solo para la finta
    contexto: str | None = None       # directo, contraataque, anticipacion...
    resultado_ataque: str | None = None   # Miss, Contact, Score, Excess
    falta_tipo: str | None = None         # conducta prohibida sancionada
    motivo: str | None = None             # por que no se identifica la accion
    _ruta: list[str] = field(default_factory=list)
    # Etiquetas de lo ya contestado. Sin verlas, en la cuarta pregunta no se
    # sabe si se dijo Tsuki o Uraken, y el error solo aparece en el registro.
    _elegido: list[str] = field(default_factory=list)

    def copiar(self) -> "ArbolGuiado":
        """Una copia independiente del recorrido.

        Existe para que nadie construya el arbol por posicion: anadir un
        campo nuevo antes de `_ruta` desplazaba los argumentos en silencio
        y el recorrido se quedaba vacio sin que saltara nada.
        """
        return ArbolGuiado(self.tecnica, self.guardia, self.nivel,
                           self.limbo, self.contexto, self.resultado_ataque,
                           self.falta_tipo, self.motivo,
                           list(self._ruta), list(self._elegido))

    # ── Consulta ────────────────────────────────────────────────────
    def paso_actual(self) -> Paso | None:
        """Pregunta pendiente, o None si ya hay datos suficientes."""
        if not self._ruta:
            # Agrupadas por lo que hace el atleta, no por frecuencia
            # suelta: esquiva y bloqueo son la misma decision (defenderse,
            # con contacto o sin el) y estaban a cuatro teclas de
            # distancia; parada y falta son las dos veces que interviene el
            # arbitro y tambien estaban separadas. Dentro de cada grupo si
            # manda la frecuencia real de ID30.
            return Paso(_t("tree.q_accion"), [
                (_t("tree.finta_sup"), "finta_sup"),
                (_t("tree.finta_inf"), "finta_inf"),
                (_t("tree.ataque"), "ataque"),
                (_t("tree.esquiva"), "Dodge"),
                (_t("tree.bloqueo"), "Hand Block"),
                (_t("tree.clinch"), _t("tree.clinch")),
                (_t("tree.parada"), "parada"),
                (_t("tree.falta"), "falta"),
                (_t("tree.descartar"), "descartar"),
                (_t("tree.no_ident"), "no_ident"),
            ], ((0, _t("tree.g_ataca")), (3, _t("tree.g_defiende")), (6, _t("tree.g_arbitro"))))

        rama = self._ruta[0]
        if rama == "ataque" and self.tecnica is None:
            if self._ruta[-1] == "otras":
                return Paso(_t("tree.q_cual"), list(_OTRAS_RESUELTAS))
            return Paso(_t("tree.q_tecnica"), list(_ATAQUES), _ATAQUES_GRUPOS)
        if rama == "parada" and self.tecnica is None:
            return Paso(_t("tree.q_parada"), list(_PARADAS))
        if rama == "falta" and self.falta_tipo is None:
            return Paso(_t("tree.q_falta"), list(_FALTAS), _FALTAS_GRUPOS)
        if rama == "no_ident" and self.motivo is None:
            return Paso(_t("tree.q_motivo"), list(_MOTIVOS))

        if self.resultado_ataque == "Foul" and self.falta_tipo is None:
            return Paso(_t("tree.q_sancion"), list(_SANCION_ATAQUE))

        if self.tecnica and self.necesita_guardia_o_nivel():
            # Jodan primero: es el 83% de lo anotado en ID30.
            return Paso(_t("tree.q_nivel"), list(_SOLO_NIVEL))

        if self.tecnica and _META[self.tecnica][4] and self.contexto is None:
            return Paso(_t("tree.q_contexto"), list(_CONTEXTO))

        if (self.tecnica and _META[self.tecnica][1] == "ATTACK"
                and self.resultado_ataque is None):
            suelo = _META[self.tecnica][0] == "SWEEPS & TAKEDOWNS"
            return Paso(_t("tree.q_final"),
                        list(_RESULTADO_SUELO if suelo else _RESULTADO))
        return None

    def necesita_guardia_o_nivel(self) -> bool:
        """Solo queda el nivel: la guardia viene con el nombre elegido."""
        if not self.tecnica:
            return False
        return _META[self.tecnica][3] and self.nivel is None

    @property
    def descartada(self) -> bool:
        return self._ruta[:1] == ["descartar"]

    @property
    def completa(self) -> bool:
        if self._ruta[:1] == ["falta"]:
            return self.falta_tipo is not None
        if self._ruta[:1] == ["no_ident"]:
            return self.motivo is not None
        return self.tecnica is not None and self.paso_actual() is None

    @property
    def no_identificable(self) -> bool:
        """El recorrido registra que la accion no se puede leer."""
        return self._ruta[:1] == ["no_ident"]

    @property
    def pide_motivo_escrito(self) -> bool:
        """El motivo elegido es «otro», que hay que escribir."""
        return self.motivo == "Other"

    @property
    def es_falta(self) -> bool:
        """El recorrido registra una falta, no una accion tecnica."""
        return self._ruta[:1] == ["falta"]

    def profundidad(self) -> tuple[int, int]:
        """(paso actual, pasos previstos) para la barra de progreso."""
        if self._ruta[:1] == ["ataque"]:
            previstos = 2                      # acción + técnica
            if "otras" in self._ruta:
                previstos += 1
            if self.tecnica:
                meta = _META[self.tecnica]
                previstos += int(meta[2] or meta[3])   # guardia y nivel van juntos
                previstos += int(meta[4])              # contexto táctico
            else:
                previstos += 2                 # lo que suele faltar
        elif self._ruta[:1] in (["parada"], ["no_ident"]):
            previstos = 2
        else:
            previstos = 1
        return min(len(self._ruta) + 1, previstos), previstos

    # ── Avance ──────────────────────────────────────────────────────
    @property
    def puntuo(self) -> bool:
        """Si el ataque puntuo. El valor lo pone el motor de puntuacion."""
        return self.resultado_ataque == "Score"

    @property
    def falta(self) -> bool:
        """El ataque acabo en falta: hubo tecnica Y hay sancion."""
        return self.resultado_ataque == "Foul"

    @property
    def falta_del_ataque(self) -> str:
        """Que conducta sanciona el ataque, para la escalera."""
        return self.falta_tipo or "" if self.falta else ""

    def respuestas(self) -> list[str]:
        """Lo ya contestado, en el orden en que se contesto."""
        return list(self._elegido)

    def elegir(self, clave: str) -> None:
        paso = self.paso_actual()
        if paso is not None:
            for etiqueta, k in paso.opciones:
                if k == clave:
                    self._elegido.append(etiqueta)
                    break
        self._ruta.append(clave)
        if clave == "no_ident":
            self.tecnica = "Unidentifiable"
        elif clave.startswith("Mot:"):
            self.motivo = clave[4:]
        elif clave == "finta_sup":
            self.tecnica, self.limbo = "Feint", "Upper Limb"
        elif clave == "finta_inf":
            self.tecnica, self.limbo = "Feint", "Lower Limb"
        elif "|" in clave and clave.split("|", 1)[0] in _META:
            base, guardia = clave.split("|", 1)
            self.tecnica = base
            self.guardia = guardia or None
        elif clave in _META:
            self.tecnica = clave
        elif clave.startswith(("F:", "S:")):
            self.falta_tipo = clave[2:]
        elif clave.startswith("Res:"):
            self.resultado_ataque = clave[4:]
        elif clave.startswith("Act:"):
            self.contexto = clave[4:]
        elif "|" in clave:
            guardia, nivel = clave.split("|", 1)
            if guardia:
                self.guardia = guardia
            self.nivel = nivel

    def retroceder(self) -> bool:
        if not self._ruta:
            return False
        fuera = self._ruta.pop()
        if self._elegido:
            self._elegido.pop()
        if fuera == "no_ident":
            self.tecnica = None
        elif fuera.startswith("Mot:"):
            self.motivo = None
        elif fuera in ("finta_sup", "finta_inf"):
            self.tecnica = self.limbo = None
        elif "|" in fuera and fuera.split("|", 1)[0] in _META:
            self.tecnica = None
            self.guardia = None
        elif fuera in _META:
            self.tecnica = None
        elif fuera.startswith(("F:", "S:")):
            self.falta_tipo = None
        elif fuera.startswith("Res:"):
            self.resultado_ataque = None
        elif fuera.startswith("Act:"):
            self.contexto = None
        elif "|" in fuera:
            guardia, _ = fuera.split("|", 1)
            if guardia:
                self.guardia = None
            self.nivel = None
        return True

    # ── Resultado ───────────────────────────────────────────────────
    def resultado(self) -> tuple[str, str, str, str]:
        """(tecnica, cadena_de_nivel, categoria, grupo) para la aplicacion.

        La cadena de nivel usa el mismo formato combinado que produce la
        ventana de detalle, para que el motor combinatorio la interprete.
        """
        if not self.tecnica:
            raise ValueError("el recorrido no ha llegado a ninguna tecnica")
        grupo, categoria, _, _, _ = _META[self.tecnica]
        partes = []
        if self.guardia:
            partes.append(f"Stance: {self.guardia}")
        if self.nivel:
            partes.append(f"Level: {self.nivel}")
        if self.limbo:
            partes.append(f"Limb: {self.limbo}")
        if self.contexto:
            partes.append(f"Action: {self.contexto}")
        if self.resultado_ataque:
            partes.append(f"Contact: {self.resultado_ataque}")
        if self.falta_tipo:
            # El motivo viaja con el ataque: es un hecho sobre ESA accion,
            # no una anotacion aparte en el mismo instante.
            partes.append(f"Sanction: {self.falta_tipo}")
        if self.motivo:
            partes.append(f"Reason: {self.motivo}")
        return self.tecnica, " | ".join(partes), categoria, grupo
