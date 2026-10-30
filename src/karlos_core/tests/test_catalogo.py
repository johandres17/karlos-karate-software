"""El catálogo de deportes y la edición (fase F3.1 de las ediciones).

El núcleo no importa los deportes: los pide al catálogo. Aquí se
comprueba el catálogo y que la edición pone en él el karate (decisión 0004).
"""
from __future__ import annotations

import pytest

from karlos_core import catalogo
from karlos_core.catalogo import Catalogo
from karlos_core.deporte import Competidor, Reglamento, SportPack


class _Deporte:
    """Un deporte mínimo que cumple el contrato."""

    nombre = "Inventado"
    edicion = "Karlos Inventado"
    competidores = (Competidor("HONG", "Hong", "rojo"), Competidor("CHUNG", "Chung", "azul"))
    reglamento = Reglamento(puntuaciones=(), escalera_de_faltas=("AVISO",), duracion_s=60.0,
                            tipos_de_parada=(), fase_de=lambda s: "")

    def __init__(self, id="inventado"):
        self.id = id

    def configuracion(self):
        return {}

    def taxonomia(self):
        return None

    def arbol(self):
        return None

    def es_sancion(self, anotacion):
        return False

    def lector_marcador(self):
        return None

    def salidas(self):
        return None

    def textos(self):
        return {}


# ----------------------------------------------------------------------
# El catálogo
# ----------------------------------------------------------------------

def test_cada_paquete_se_construye_una_vez_y_solo_si_se_pide():
    c = Catalogo()
    hechos = []
    c.registrar("inventado", lambda: hechos.append(1) or _Deporte())
    assert hechos == [], "registrar no construye"
    assert c.paquete("inventado") is c.paquete("inventado")
    assert hechos == [1]


def test_registrar_dos_veces_el_mismo_deporte_es_un_error():
    c = Catalogo()
    c.registrar("inventado", _Deporte)
    with pytest.raises(ValueError, match="ya está registrado"):
        c.registrar("inventado", _Deporte)


def test_un_deporte_que_no_esta_lo_dice_y_dice_cuales_hay():
    c = Catalogo()
    c.registrar("inventado", _Deporte)
    with pytest.raises(KeyError, match="inventado"):
        c.paquete("sumo")


def test_la_fabrica_tiene_que_devolver_el_deporte_pedido():
    c = Catalogo()
    c.registrar("sumo", _Deporte)          # devuelve «inventado»
    with pytest.raises(ValueError, match="inventado"):
        c.paquete("sumo")


def test_sin_elegir_el_activo_es_el_primero_y_elegido_es_el_elegido():
    c = Catalogo()
    with pytest.raises(LookupError):
        c.activo()
    c.registrar("uno", lambda: _Deporte("uno"))
    c.registrar("dos", lambda: _Deporte("dos"))
    assert c.registrados() == ("uno", "dos")
    assert c.activo().id == "uno"
    assert c.establecer("dos").id == "dos"
    assert c.activo().id == "dos"
    c.olvidar_activo()
    assert c.activo().id == "uno"
    with pytest.raises(KeyError):
        c.establecer("tres")
    assert c.activo().id == "uno", "un deporte que no existe no cambia el activo"


# ----------------------------------------------------------------------
# La edición
# ----------------------------------------------------------------------

def test_la_edicion_trae_el_karate():
    from karlos_core.config import SPORT_LIST
    assert catalogo.registrados() == ("karate",)
    assert [d["id"] for d in SPORT_LIST] == list(catalogo.registrados())
    assert catalogo.activo().id == "karate"
    for id in catalogo.registrados():
        assert isinstance(catalogo.paquete(id), SportPack)


def test_las_configuraciones_las_trae_cada_deporte():
    """config.SPORTS y SPORT_LIST son vistas del catálogo: lo que diga cada
    deporte, en el orden de la edición (decisión 0004, F3.3d)."""
    from karlos_core.config import SPORT_LIST, SPORTS
    assert list(SPORTS) == list(catalogo.registrados())
    for id in SPORTS:
        assert SPORTS[id] is catalogo.paquete(id).configuracion()
    assert [d["id"] for d in SPORT_LIST] == list(catalogo.registrados())
    assert [d["short"] for d in SPORT_LIST] == ["K"]
    assert "sumo" not in SPORTS and SPORTS.get("sumo") is None
    with pytest.raises(TypeError):
        SPORTS["sumo"] = {}


def test_todos_los_deportes_guardan_aka_y_ao():
    """El formato de sesión es común (decisiones 0002 y 0004): un deporte
    pone etiquetas y colores, pero no cambia los códigos que se guardan."""
    from karlos_core.formato import COMPETIDORES, rival
    for id in catalogo.registrados():
        assert tuple(c.codigo for c in catalogo.paquete(id).competidores) == COMPETIDORES, id
    assert (rival("AKA"), rival("AO"), rival("")) == ("AO", "AKA", "AKA")
