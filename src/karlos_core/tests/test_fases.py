"""Las fases del combate (tiempo-movimiento): fighting / non-fighting /
stoppage / unobservable, dos acciones a ≤ 2 s son el mismo intercambio, la
finta sola es non-fighting."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from karlos_core.models.fases import (FIGHTING, NON_FIGHTING, STOPPAGE, UNOBSERVABLE, Fases, Intervalo,
                                      acuerdo, derivar, resumen)

FPS = 30.0


def fila(ini, fin, categoria="ATTACK", tecnica="Bandal-chagi", atleta="AKA"):
    return SimpleNamespace(f_start=ini, f_end=fin, category=categoria,
                           technique=tecnica, athlete=atleta)


def tramos(intervalos, estado):
    return [(t.inicio, t.fin) for t in intervalos if t.estado == estado]


def cubre_entero(intervalos, desde, hasta):
    return sum(t.fotogramas() for t in intervalos) == hasta - desde + 1


class TestLasMarcas:
    def test_una_marca_vale_hasta_la_siguiente(self):
        f = Fases()
        f.marcar(100, FIGHTING)
        f.marcar(250, NON_FIGHTING)
        f.marcar(400, STOPPAGE)
        assert f.estado_en(99) is None, "antes de la primera marca no hay fase"
        assert f.estado_en(100) == FIGHTING and f.estado_en(249) == FIGHTING
        assert f.estado_en(250) == NON_FIGHTING and f.estado_en(1000) == STOPPAGE
        assert f.intervalos(0, 500) == [Intervalo(100, 249, FIGHTING),
                                        Intervalo(250, 399, NON_FIGHTING),
                                        Intervalo(400, 500, STOPPAGE)]

    def test_volver_a_marcar_el_mismo_fotograma_es_corregirlo(self):
        f = Fases([(100, FIGHTING)])
        f.marcar(100, STOPPAGE)
        assert f.marcas == [(100, STOPPAGE)]

    def test_quitar_la_marca_anterior(self):
        f = Fases([(100, FIGHTING), (200, NON_FIGHTING)])
        assert f.quitar_anterior(150) == (100, FIGHTING)
        assert f.marcas == [(200, NON_FIGHTING)]
        assert f.quitar_anterior(50) is None

    def test_una_fase_desconocida_no_entra(self):
        with pytest.raises(ValueError):
            Fases().marcar(1, "descanso")
        assert Fases([(1, "descanso"), (2, FIGHTING)]).marcas == [(2, FIGHTING)]

    def test_se_guardan_y_vuelven(self):
        f = Fases([(10, FIGHTING), (20, STOPPAGE)])
        assert Fases.de_lista(f.a_lista()) == f
        assert Fases.de_lista([{"fotograma": "x"}, {"fase": FIGHTING}, None]).vacias

    def test_el_tramo_empieza_con_la_fase_que_rige(self):
        f = Fases([(100, FIGHTING)])
        assert f.intervalos(150, 200) == [Intervalo(150, 200, FIGHTING)]


class TestLaDerivacion:
    """Las reglas del especialista, una a una."""

    def test_dos_acciones_a_menos_de_dos_segundos_son_el_mismo_ataque(self):
        # 1 s de hueco (30 fotogramas) a 30 fps
        fases = derivar([fila(100, 130), fila(160, 190)], 0, 600, FPS)
        assert tramos(fases, FIGHTING) == [(100, 190)]
        assert cubre_entero(fases, 0, 600)

    def test_dos_acciones_a_mas_de_dos_segundos_son_dos_ataques(self):
        fases = derivar([fila(100, 130), fila(230, 260)], 0, 600, FPS)   # 3,3 s
        assert tramos(fases, FIGHTING) == [(100, 130), (230, 260)]
        assert tramos(fases, NON_FIGHTING) == [(0, 99), (131, 229), (261, 600)]

    def test_el_hueco_es_un_ajuste(self):
        filas = [fila(100, 130), fila(230, 260)]
        assert len(tramos(derivar(filas, 0, 600, FPS, hueco_s=4.0), FIGHTING)) == 1

    def test_la_finta_seguida_de_ataque_es_parte_del_ataque_y_lo_empieza(self):
        fases = derivar([fila(80, 95, "TACTICS", "Feint"), fila(110, 140)], 0, 600, FPS)
        assert tramos(fases, FIGHTING) == [(80, 140)]

    def test_la_finta_sola_es_non_fighting(self):
        fases = derivar([fila(80, 95, "TACTICS", "Feint"), fila(300, 330)], 0, 600, FPS)
        assert tramos(fases, FIGHTING) == [(300, 330)]
        assert (80, 95) not in tramos(fases, FIGHTING)

    def test_la_finta_detras_del_ataque_no_lo_alarga(self):
        """«If the feint is not followed by an attack, it is considered
        non-fighting time»: solo alarga hacia atrás."""
        fases = derivar([fila(100, 130), fila(140, 155, "TACTICS", "Feint")], 0, 600, FPS)
        assert tramos(fases, FIGHTING) == [(100, 130)]

    def test_la_parada_del_arbitro_acaba_el_ataque(self):
        fases = derivar([fila(100, 200), fila(150, 400, "REFEREE STOP", "Kal-yeo", "—")],
                        0, 600, FPS)
        assert tramos(fases, STOPPAGE) == [(150, 400)]
        assert tramos(fases, FIGHTING) == [(100, 149)]
        assert tramos(fases, NON_FIGHTING) == [(0, 99), (401, 600)]
        assert cubre_entero(fases, 0, 600)

    def test_las_fases_son_del_combate_y_miran_a_los_dos_atletas(self):
        fases = derivar([fila(100, 130, atleta="AKA"), fila(140, 170, atleta="AO")],
                        0, 600, FPS)
        assert tramos(fases, FIGHTING) == [(100, 170)]

    def test_la_defensa_el_clinch_y_lo_no_identificable_son_accion(self):
        fases = derivar([fila(100, 120, "DEFENSE", "Dodge"),
                         fila(300, 320, "TACTICS", "Clinch"),
                         fila(500, 520, "UNIDENTIFIED", "Unidentifiable")], 0, 600, FPS)
        assert tramos(fases, FIGHTING) == [(100, 120), (300, 320), (500, 520)]

    def test_lo_de_fuera_del_asalto_se_recorta_o_se_ignora(self):
        fases = derivar([fila(50, 120), fila(900, 950)], 100, 600, FPS)
        assert tramos(fases, FIGHTING) == [(100, 120)]
        assert cubre_entero(fases, 100, 600)

    def test_sin_acciones_todo_es_non_fighting(self):
        assert derivar([], 0, 599, FPS) == [Intervalo(0, 599, NON_FIGHTING)]


class TestElResumen:
    def test_segundos_porcentaje_y_ataques(self):
        fases = [Intervalo(0, 299, FIGHTING), Intervalo(300, 599, NON_FIGHTING),
                 Intervalo(600, 899, STOPPAGE), Intervalo(900, 1199, FIGHTING)]
        r = resumen(fases, 0, 1199, FPS)
        assert r["total_s"] == 40.0
        # Por defecto, todo el vocabulario del modelo: los tres de siempre
        # y el «unobservable» del karate (decisión 0008), que aquí vale 0.
        assert r["segundos"] == {FIGHTING: 20.0, NON_FIGHTING: 10.0,
                                 STOPPAGE: 10.0, UNOBSERVABLE: 0.0}
        # Y con los estados de un deporte de tres, solo esos tres.
        tres = resumen(fases, 0, 1199, FPS, (FIGHTING, NON_FIGHTING, STOPPAGE))
        assert tres["segundos"] == {FIGHTING: 20.0, NON_FIGHTING: 10.0, STOPPAGE: 10.0}
        assert r["porcentaje"][FIGHTING] == 50.0
        assert r["ataques"] == 2 and r["ataque_medio_s"] == 10.0
        assert r["sin_fase_s"] == 0.0

    def test_lo_no_marcado_se_dice(self):
        r = resumen([Intervalo(300, 599, FIGHTING)], 0, 599, FPS)
        assert r["sin_fase_s"] == 10.0


class TestElAcuerdo:
    def test_iguales_opuestas_y_sin_nada_que_comparar(self):
        a = [Intervalo(0, 99, FIGHTING), Intervalo(100, 199, NON_FIGHTING)]
        assert acuerdo(a, a, 0, 199) == (1.0, 200)
        b = [Intervalo(0, 99, NON_FIGHTING), Intervalo(100, 199, FIGHTING)]
        assert acuerdo(a, b, 0, 199) == (0.0, 200)
        assert acuerdo(a, [], 0, 199) == (0.0, 0)

    def test_solo_cuenta_donde_hay_fase_en_los_dos(self):
        a = [Intervalo(0, 199, FIGHTING)]
        b = [Intervalo(100, 199, FIGHTING)]
        assert acuerdo(a, b, 0, 199) == (1.0, 100)


class TestQuitarUnaMarca:
    def test_se_quita_la_marca_exacta_y_no_otra(self):
        f = Fases([(100, FIGHTING), (200, NON_FIGHTING), (300, STOPPAGE)])
        assert f.quitar(200) == (200, NON_FIGHTING)
        assert f.marcas == [(100, FIGHTING), (300, STOPPAGE)]
        assert f.quitar(250) is None, "sin marca en ese fotograma no se quita nada"


def test_el_reparto_sobre_lo_observado_no_cuenta_lo_que_no_se_ve():
    """Decisión 0008. «unobservable» es nuestro y no está en la literatura:
    para comparar con Chaabène et al. 2014, el reparto se calcula también
    sin él. Aquí 10 s de 40 no se ven, y los 30 restantes se reparten."""
    fases = [Intervalo(0, 299, FIGHTING), Intervalo(300, 599, NON_FIGHTING),
             Intervalo(600, 899, UNOBSERVABLE), Intervalo(900, 1199, STOPPAGE)]
    r = resumen(fases, 0, 1199, FPS)
    assert r["porcentaje"][UNOBSERVABLE] == 25.0, "sobre el combate entero, cuenta"
    assert r["observado_s"] == 30.0
    obs = r["porcentaje_observado"]
    assert UNOBSERVABLE not in obs
    assert obs == {FIGHTING: pytest.approx(100 / 3), NON_FIGHTING: pytest.approx(100 / 3),
                   STOPPAGE: pytest.approx(100 / 3)}
    assert sum(obs.values()) == pytest.approx(100.0)


class TestElVideoQueNoSeVe:
    """ID24 (26-10-2026): un tramo de 140 s marcado como no identificable
    por fallo del vídeo se contaba como lucha, y daba a AO un 45 % de lucha
    en una pasada y un 6 % en la otra."""

    def _ciego(self, ini, fin, motivo="VideoFault", nivel=""):
        return SimpleNamespace(f_start=ini, f_end=fin, category="UNIDENTIFIED",
                               technique="Unidentifiable", athlete="AO", level=nivel,
                               sport_specific_data={"reason": motivo} if motivo else {})

    def test_fallo_de_video_es_no_observable(self):
        fases = derivar([self._ciego(1000, 5200)], 0, 6000, FPS)
        assert tramos(fases, UNOBSERVABLE) == [(1000, 5200)]
        assert tramos(fases, FIGHTING) == []
        assert cubre_entero(fases, 0, 6000)

    def test_corta_el_ataque_que_lo_toca(self):
        fases = derivar([fila(900, 1100), self._ciego(1000, 5200)], 0, 6000, FPS)
        assert tramos(fases, FIGHTING) == [(900, 999)]
        assert tramos(fases, UNOBSERVABLE) == [(1000, 5200)]

    def test_la_parada_sigue_mandando(self):
        fases = derivar([self._ciego(1000, 2000),
                         fila(1500, 2500, "REFEREE STOP", "Referee")], 0, 6000, FPS)
        assert tramos(fases, STOPPAGE) == [(1500, 2500)]
        assert tramos(fases, UNOBSERVABLE) == [(1000, 1499)]

    def test_sin_estado_no_observable_queda_como_non_fighting(self):
        """Un deporte que no use ese estado: lo que no se ve tampoco es lucha."""
        fases = derivar([self._ciego(1000, 5200)], 0, 6000, FPS,
                        estados=(FIGHTING, NON_FIGHTING, STOPPAGE))
        assert tramos(fases, FIGHTING) == []
        assert tramos(fases, UNOBSERVABLE) == []
        assert tramos(fases, NON_FIGHTING) == [(0, 6000)]

    def test_una_accion_ocluida_sigue_siendo_lucha(self):
        """Pasó, aunque no se pueda leer: la regla de siempre."""
        fases = derivar([self._ciego(1000, 1015, "Occluded")], 0, 6000, FPS)
        assert tramos(fases, FIGHTING) == [(1000, 1015)]

    def test_motivo_escrito_en_el_nivel_de_una_sesion_antigua(self):
        fases = derivar([self._ciego(1000, 5200, motivo="", nivel="Reason: VideoFault")],
                        0, 6000, FPS)
        assert tramos(fases, UNOBSERVABLE) == [(1000, 5200)]
