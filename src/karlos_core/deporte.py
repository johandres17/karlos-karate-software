"""El contrato que cumple cada deporte (SportPack).

El núcleo no sabe de kárate: pregunta al deporte quiénes son los dos
competidores, cuánto vale cada puntuación, cómo escalan las faltas, cuánto
dura el combate, qué paradas hay, qué técnicas existen y qué preguntas se
hacen.

Solo entra aquí lo que el karate puede cumplir hoy sin cambiar su
comportamiento. Los textos del deporte, sus columnas del CSV y sus secciones
del informe se añaden en la fase F3, cuando se separen de ``karlos_core``
(ver docs/decisiones/0003).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class Competidor:
    """Uno de los dos atletas, como lo guarda y lo enseña el programa.

    ``codigo`` es lo que se escribe en la sesión: el del formato común
    (``karlos_core.formato``), AKA el primero y AO el segundo en todos los
    deportes; cambiarlo rompería los datos ya anotados. ``etiqueta`` es lo
    que ve el evaluador y ``color`` la clave del tema con que se pinta.
    """

    codigo: str
    etiqueta: str
    color: str


@dataclass(frozen=True)
class Puntuacion:
    """Un resultado que puntúa (o no): su código, sus puntos y su nombre."""

    codigo: str
    puntos: int
    nombre: str


def puntuaciones_de_configuracion(tabla: dict[str, dict[str, Any]]) -> tuple[Puntuacion, ...]:
    """Las puntuaciones de la sección ``scoring`` de una configuración.

    El nombre es la etiqueta sin los puntos ni el atajo:
    «WAZA-ARI (2 pts)  [2]» → «WAZA-ARI».
    """
    salida = []
    for codigo, datos in tabla.items():
        nombre = str(datos.get("label", codigo)).split("(")[0].split("[")[0].strip()
        salida.append(Puntuacion(codigo=codigo, puntos=int(datos.get("points", 0)),
                                 nombre=nombre or codigo))
    return tuple(salida)


@dataclass(frozen=True)
class Reglamento:
    """Lo mecánico del reglamento de un deporte.

    El programa lo aplica; nunca decide por el evaluador (decisión 0001).
    """

    puntuaciones: tuple[Puntuacion, ...]
    escalera_de_faltas: tuple[str, ...]
    duracion_s: float
    tipos_de_parada: tuple[str, ...]
    fase_de: Callable[[float], str]
    # Cuántos asaltos tiene el combate. Con más de uno, el evaluador marca
    # dónde empieza y acaba cada uno y esas marcas son del vídeo, no de la
    # pasada (``karlos_core.models.asaltos``). El karate tiene uno y sigue
    # con su inicio y su fin de combate de siempre.
    asaltos: int = 1

    @cached_property
    def _puntos_por_clave(self) -> dict[str, int]:
        tabla = {p.nombre.upper(): p.puntos for p in self.puntuaciones}
        tabla.update({p.codigo.upper(): p.puntos for p in self.puntuaciones})  # manda el código
        return tabla

    def puntos(self, codigo: str) -> int:
        """Los puntos de una puntuación; 0 si no puntúa o no existe.

        Todo el programa pregunta aquí lo que vale una puntuación (decisión
        0004). Reconoce el código (WAZA) y el nombre oficial (WAZA-ARI) sin
        distinguir mayúsculas: el programa guarda códigos, pero un dato importado o
        corregido a mano puede traer el nombre.
        """
        return self._puntos_por_clave.get((codigo or "").upper(), 0)

    def grado(self, numero: int) -> str:
        """El grado de la n-ésima falta de un atleta (1 = la primera).

        Pasado el último peldaño, se queda en el último.
        """
        if numero < 1:
            raise ValueError("las faltas se cuentan desde 1")
        return self.escalera_de_faltas[min(numero, len(self.escalera_de_faltas)) - 1]

    def fase(self, activo_s: float) -> str:
        """En qué fase del combate cae un instante de juego efectivo."""
        return self.fase_de(activo_s)


@runtime_checkable
class Salidas(Protocol):
    """Lo que un deporte produce con lo anotado (decisión 0004).

    Hoy las del karate se entregan enteras, con sus ramas para otros
    deportes dentro: lo que compartan dos deportes de verdad se subirá al
    núcleo cuando exista el segundo.
    """

    def csv_del_combate(self) -> Any:
        """El CSV del combate: ``componer``, ``escribir``, ``leer`` y
        ``buscar_video``."""

    def exportador(self) -> Any:
        """Un exportador nuevo de la exportación antigua (XLSX y CSV)."""

    def vista_informe(self, colors: Any, sport_meta: dict, parent: Any = None) -> Any:
        """El informe en pantalla, para la ventana principal. El núcleo le da
        la sesión (``set_session``) y le pide lo que lleva el PDF
        (``datos_para_pdf``)."""

    def informe_pdf(self, **datos: Any) -> str:
        """Escribe el informe PDF y devuelve dónde."""

    def informe_entrenador(self) -> Any:
        """La ventana del informe del entrenador."""

    def probar(self) -> tuple[bool, str]:
        """Una comprobación rápida para el autodiagnóstico: (vale, qué)."""


@runtime_checkable
class SportPack(Protocol):
    """Lo que un deporte aporta al núcleo."""

    id: str
    nombre: str
    edicion: str
    competidores: tuple[Competidor, Competidor]
    reglamento: Reglamento

    def configuracion(self) -> dict[str, Any]:
        """Su configuración en el formato de Karlos (colores, niveles,
        puntuaciones, taxonomía, paradas y vídeo). De ella sale la
        taxonomía."""

    def taxonomia(self) -> Any:
        """Categorías, técnicas y niveles (``TaxonomyConfig``)."""

    def arbol(self) -> Any:
        """Un árbol de preguntas nuevo para anotar una acción, o None si el
        deporte aún no tiene libro de códigos: sin árbol no hay modo
        asistido (decisión 0007), porque preguntaría con las palabras de
        otro deporte."""

    def es_sancion(self, anotacion: Any) -> bool:
        """Si esa anotación suma un peldaño en la escalera de faltas."""

    def tiempo_movimiento(self) -> Optional[dict[str, Any]]:
        """Los ajustes del análisis de tiempo-movimiento, o None si el deporte
        no lo hace.

        Con él, el evaluador marca las fases del combate con tres teclas
        (fighting / non-fighting / stoppage) o las deriva de lo anotado
        (``karlos_core.models.fases``), y el informe y el Excel las cuentan.
        """

    def salidas(self) -> Salidas:
        """El CSV del combate, la exportación y los informes."""

    def textos(self) -> dict[str, dict[str, str]]:
        """Sus textos, clave → {idioma: texto}. Tienen preferencia sobre los
        del programa con la misma clave."""
