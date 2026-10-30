"""Tests de las metricas del combate.

Lo que se vigila aqui no es que las cuentas sumen, sino que las
definiciones sean las de la literatura: el momento decisivo de Tabben,
los indices de Adam, la combinacion como clase aparte. Si alguien las
cambia sin querer, el informe seguiria pareciendo correcto y estaria
midiendo otra cosa.
"""

from __future__ import annotations

import pytest

from karlos_core.models.annotation import Annotation
from karlos_karate import metricas_combate as M


def at(athlete="AKA", f=100, score="", sub=M.MANO, combo="1"):
    return Annotation(athlete=athlete, category=M.ATAQUE, subcategory=sub,
                      technique="Gyaku Tsuki", level="Jodan", score=score,
                      f_start=f, f_end=f + 10,
                      sport_specific_data={"combo": combo})


def defensa(athlete="AO", f=100, vs=""):
    return Annotation(athlete=athlete, category=M.DEFENSA,
                      subcategory="BLOCKS & EVASIONS", technique="Dodge",
                      f_start=f, f_end=f + 8,
                      sport_specific_data={"vs": vs} if vs else {})


def finta(athlete="AKA", f=100):
    return Annotation(athlete=athlete, category=M.TACTICA, subcategory="TACTICS",
                      technique="Feint", f_start=f, f_end=f + 5)


class TestProporcion:
    def test_el_porcentaje_nunca_viaja_solo(self):
        p = M.Proporcion(2, 14)
        assert f"{p}" == "2/14" and round(p.pct) == 14

    def test_sin_intentos_no_revienta(self):
        assert M.Proporcion(0, 0).pct == 0.0

    def test_avisa_cuando_la_base_es_corta(self):
        """Con 8 intentos, un acierto mas mueve el dato 12 puntos."""
        assert not M.Proporcion(3, 8).fiable
        assert M.Proporcion(3, 10).fiable


class TestGanador:
    def test_suma_por_el_valor_wkf(self):
        assert M.ganador([at(score="YUKO"), at(score="IPPON")]) == ("AKA", 4, 0)

    def test_empate_no_tiene_ganador(self):
        assert M.ganador([at("AKA", score="YUKO"),
                          at("AO", score="YUKO")])[0] == ""

    def test_sin_puntos_es_empate(self):
        assert M.ganador([at(), at("AO")])[0] == ""


class TestMomentoDecisivo:
    """Tabben et al. (2018): el instante tras el cual el ganador ya no
    vuelve a ir por detras."""

    def test_el_punto_que_decide(self):
        acciones = [at("AKA", f=100), at("AO", f=500, score="YUKO"),
                    at("AKA", f=900)]
        assert M.momento_decisivo(acciones, "AO") == 500

    def test_si_remonta_manda_el_ultimo_cambio(self):
        """AKA se pone 1-0, AO empata y luego se va: decide el segundo."""
        acciones = [at("AKA", f=100, score="YUKO"),
                    at("AO", f=300, score="YUKO"),
                    at("AO", f=700, score="YUKO"),
                    at("AKA", f=900)]
        assert M.momento_decisivo(acciones, "AO") == 700

    def test_un_empate_no_tiene_momento_decisivo(self):
        assert M.momento_decisivo([at()], "") is None

    def test_el_orden_de_llegada_no_importa(self):
        desordenado = [at("AKA", f=900), at("AO", f=500, score="YUKO"),
                       at("AKA", f=100)]
        assert M.momento_decisivo(desordenado, "AO") == 500


class TestEficacia:
    """Los indices de Adam et al. (2012), como los usa la literatura."""

    def _combate(self):
        return [at("AKA", f=100), at("AKA", f=200, score="YUKO"),
                at("AKA", f=300), at("AKA", f=400),
                at("AO", f=500, score="IPPON"), at("AO", f=600)]

    def test_ea_es_aciertos_entre_intentos(self):
        e = M.eficacia(self._combate(), "AKA")
        assert e.ataques.parte == 1 and e.ataques.total == 4
        assert round(e.ea) == 25

    def test_eo_mira_los_ataques_del_rival(self):
        """AO acerto 1 de 2, asi que AKA defendio el 50%."""
        assert round(M.eficacia(self._combate(), "AKA").eo) == 50

    def test_una_defensa_perfecta_es_cien(self):
        e = M.eficacia([at("AKA"), at("AO", f=200)], "AKA")
        assert e.eo == 100.0

    def test_sk_son_los_puntos_netos(self):
        e = M.eficacia(self._combate(), "AKA")
        assert e.puntos == 1 and e.puntos_encajados == 3 and e.sk == -2

    def test_las_defensas_no_cuentan_como_ataques(self):
        e = M.eficacia([at("AKA"), defensa("AKA"), finta("AKA")], "AKA")
        assert e.ataques.total == 1


class TestPorClase:
    """La combinacion va aparte: en Tokio 2020 fue lo menos usado y lo
    mas eficaz (Seyedi et al. 2024)."""

    def test_separa_mano_pierna_y_suelo(self):
        c = M.por_clase([at(sub=M.MANO), at(sub=M.PIERNA, f=200),
                         at(sub=M.SUELO, f=300)], "AKA")
        assert c["mano"].total == c["pierna"].total == c["suelo"].total == 1

    def test_la_combinacion_cuenta_ademas_de_su_clase(self):
        """Un encadenado de mano es mano Y combinacion: son dos preguntas
        distintas, con que golpeo y si venia encadenado."""
        c = M.por_clase([at(sub=M.MANO, combo="2", score="YUKO")], "AKA")
        assert c["mano"].total == 1 and c["combinacion"].total == 1
        assert c["combinacion"].parte == 1

    def test_un_ataque_suelto_no_es_combinacion(self):
        c = M.por_clase([at(combo="1")], "AKA")
        assert c["combinacion"].total == 0


class TestFintas:
    """Exploratorio: ningun estudio de karate las ha medido."""

    def test_cuenta_las_lanzadas(self):
        f = M.fintas([finta("AKA"), finta("AKA", f=300), finta("AO")],
                     "AKA", 30.0)
        assert f["lanzadas"] == 2

    def test_cuenta_las_que_hicieron_reaccionar(self):
        f = M.fintas([finta("AKA", f=100), defensa("AO", f=120, vs="Feint")],
                     "AKA", 30.0)
        assert f["respondidas"] == 1

    def test_separa_ataques_con_finta_previa_de_los_demas(self):
        acciones = [finta("AKA", f=100), at("AKA", f=120, score="YUKO"),
                    at("AKA", f=900)]
        f = M.fintas(acciones, "AKA", 30.0)
        assert str(f["con_finta"]) == "1/1"
        assert str(f["sin_finta"]) == "0/1"

    def test_la_finta_del_rival_no_prima_mi_ataque(self):
        f = M.fintas([finta("AO", f=100), at("AKA", f=120)], "AKA", 30.0)
        assert f["con_finta"].total == 0 and f["sin_finta"].total == 1

    def test_una_finta_lejana_no_prima(self):
        f = M.fintas([finta("AKA", f=100), at("AKA", f=900)], "AKA", 30.0)
        assert f["sin_finta"].total == 1


class TestSancionesPorMarcador:
    """Frigout et al. (2020): las faltas del que domina estan asociadas a
    ganar. Lo que informa no es cuantas, es cuando."""

    def test_distingue_ganando_de_perdiendo(self):
        acciones = [
            at("AKA", f=100, score="YUKO"),
            Annotation(athlete="AKA", category="PENALTY", subcategory="Procedure",
                       technique="Chui (1st)", f_start=200, f_end=200),
            at("AO", f=300, score="WAZA"),
            Annotation(athlete="AKA", category="PENALTY", subcategory="Procedure",
                       technique="Chui (2nd)", f_start=400, f_end=400)]
        s = M.sanciones_por_marcador(acciones, "AKA")
        assert s == {"ganando": 1, "empatado": 0, "perdiendo": 1}

    def test_la_sancion_dentro_del_ataque_tambien_cuenta(self):
        a = at("AKA", f=100)
        a.sport_specific_data["sanction"] = "Contact"
        assert M.sanciones_por_marcador([a], "AKA")["empatado"] == 1


class TestTramo:
    def test_resume_una_ventana(self):
        acciones = [at("AKA", f=100), at("AKA", f=200, sub=M.PIERNA),
                    finta("AKA", f=150), defensa("AKA", f=180),
                    at("AKA", f=9000)]
        t = M.tramo(acciones, "AKA", lambda x: int(x.f_start) < 1000)
        assert (t.ataques, t.pierna, t.fintas, t.defensas) == (2, 1, 1, 1)
        assert round(t.pct_pierna) == 50
