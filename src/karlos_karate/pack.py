"""Karlos Karate: el karate visto a través del contrato SportPack.

El paquete reúne todo lo del karate: su configuración, el árbol de
preguntas WKF, la escalera de faltas 2026, las salidas (el CSV del combate, la exportación y los informes) y sus textos.
Hasta la fase F4 esos módulos vivían en ``karlos_core``; se mudaron sin
cambiar nada, y las pruebas de referencia demuestran que el karate da lo
mismo que en la 1.0 (decisiones 0004 y 0005).

La fuente única de los puntos es la configuración de karate
(``karate_config``): los puntos, la etiqueta, el color y el atajo de cada
puntuación. Todo el programa los pide a ``reglamento.puntos`` (F3.2).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from karlos_core.deporte import (
    Competidor,
    Reglamento,
    Salidas,
    puntuaciones_de_configuracion,
)


@lru_cache(maxsize=1)
def _config_karate() -> dict:
    from karlos_karate import karate_config
    return karate_config.SPORT_CONFIG


# La escalera única del reglamento WKF 2026 (Kumite Competition Rules
# 2026.01, §10.2-10.3, en vigor desde el 1 de enero de 2026): desaparecen
# las categorías 1 y 2 y los grados CHUKOKU y KEIKOKU. Son los nombres que
# el árbitro señaliza en el tatami, para que lo anotado se lea igual que lo
# que se ve. El quinto peldaño descalifica.
ESCALERA_WKF_2026 = ("CHUI-1", "CHUI-2", "CHUI-3", "HANSOKU-CHUI", "HANSOKU")


def _fase(activo_s: float) -> str:
    from karlos_karate import csv_combate
    return csv_combate._fase(activo_s)


class KaratePack:
    """Kumite según el reglamento WKF 2026."""

    id = "karate"
    nombre = "Karate"
    edicion = "Karlos Karate"

    def __init__(self) -> None:
        cfg = _config_karate()
        from karlos_karate import csv_combate
        deporte = cfg["sport"]
        self.competidores = (
            Competidor(codigo=deporte["athlete_a_label"], etiqueta=deporte["athlete_a_label"], color="aka"),
            Competidor(codigo=deporte["athlete_b_label"], etiqueta=deporte["athlete_b_label"], color="ao"),
        )
        self.reglamento = Reglamento(
            puntuaciones=puntuaciones_de_configuracion(cfg["scoring"]),
            escalera_de_faltas=ESCALERA_WKF_2026,
            duracion_s=float(csv_combate.COMBATE_S),
            tipos_de_parada=tuple(p["name"] for p in cfg["referee_stop_types"]),
            fase_de=_fase,
        )

    def configuracion(self) -> dict[str, Any]:
        return _config_karate()

    def taxonomia(self) -> Any:
        from karlos_core.utils.config_loader import load_config
        return load_config(self.id)[0]

    def arbol(self) -> Any:
        from karlos_karate.guided_tree import ArbolGuiado
        return ArbolGuiado()

    def es_sancion(self, anotacion: Any) -> bool:
        from karlos_karate import csv_combate
        return csv_combate.es_sancion(anotacion)

    def tiempo_movimiento(self) -> Optional[dict[str, Any]]:
        """Los cuatro estados del karate (decision 0008).

        Las definiciones de los tres primeros son de Chaabene et al. 2014;
        el cuarto, «no observable», es nuestro. Se marcan con los digitos 1
        a 4: en el modo tiempo-movimiento no hay tecnicas que elegir, asi
        que los numeros quedan libres. C, V y H siguen siendo las faltas de
        la WKF en todos los modos."""
        datos = _config_karate().get("time_motion")
        return dict(datos) if datos else None

    def salidas(self) -> Salidas:
        from karlos_karate.salidas import SALIDAS
        return SALIDAS

    def textos(self) -> dict[str, dict[str, str]]:
        from karlos_karate.textos import TEXTOS
        return TEXTOS
