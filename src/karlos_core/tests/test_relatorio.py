"""Tests do relatório do treinador.

O que se vigia aqui é o que o treinador lê. Um relatório que quebra com
um combate empatado, ou que mostra uma porcentagem sobre três
tentativas, engana pior do que não existir: parece um dado.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

from karlos_core.models.annotation import Annotation
from karlos_karate.relatorio_treinador import RelatorioTreinador


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def ataque(quem="AKA", f=100, score="", sub="HAND TECHNIQUES"):
    return Annotation(athlete=quem, category="ATTACK", subcategory=sub,
                      technique="Gyaku Tsuki", level="Jodan", score=score,
                      f_start=f, f_end=f + 10, sport_specific_data={"combo": "1"})


def finta(quem="AKA", f=100):
    return Annotation(athlete=quem, category="TACTICS", subcategory="TACTICS",
                      technique="Feint", f_start=f, f_end=f + 5)


def defesa(quem="AO", f=100, vs=""):
    return Annotation(athlete=quem, category="DEFENSE",
                      subcategory="BLOCKS & EVASIONS", technique="Dodge",
                      f_start=f, f_end=f + 8,
                      sport_specific_data={"vs": vs} if vs else {})


def textos(r) -> str:
    return " ".join(w.text() for b in r._blocos for w in b.findChildren(QLabel))


class TestMonta:
    def test_um_combate_normal(self):
        r = RelatorioTreinador()
        r.mostrar([ataque("AKA", 100), ataque("AO", 500, score="YUKO"),
                   ataque("AKA", 900)], 30.0, "Assemat", "Duarte")
        assert len(r._blocos) == 6

    def test_sem_anotacoes_nao_quebra(self):
        r = RelatorioTreinador()
        r.mostrar([], 30.0)
        assert r._blocos

    def test_um_empate_nao_tem_ponto_de_virada(self):
        """Sem vencedor a definição de Tabben não se aplica."""
        r = RelatorioTreinador()
        r.mostrar([ataque("AKA", 100, score="YUKO"),
                   ataque("AO", 500, score="YUKO")], 30.0)
        assert "empatado" in textos(r)
        assert "ponto de virada" not in textos(r).lower()

    def test_montar_duas_vezes_nao_duplica(self):
        r = RelatorioTreinador()
        dados = [ataque("AO", 500, score="YUKO")]
        r.mostrar(dados, 30.0)
        n = len(r._blocos)
        r.mostrar(dados, 30.0)
        assert len(r._blocos) == n

    def test_fps_zero_nao_quebra(self):
        r = RelatorioTreinador()
        r.mostrar([ataque("AO", 500, score="YUKO")], 0.0)
        assert r._blocos


class TestOQueDiz:
    def test_usa_os_nomes_dos_atletas(self):
        r = RelatorioTreinador()
        r.mostrar([ataque("AO", 500, score="YUKO")], 30.0, "Assemat", "Duarte")
        assert "Assemat" in textos(r) and "Duarte" in textos(r)

    def test_toda_porcentagem_vem_com_a_contagem(self):
        """A regra da casa: ninguém lê 14% sem ver 2 de 14.

        A contagem aparece duas vezes de propósito — no rótulo da barra,
        para quem só olha, e na frase, para quem lê. Aqui se comprova que
        está nas duas.
        """
        r = RelatorioTreinador()
        acoes = [ataque("AKA", 100 + i * 50) for i in range(28)]
        acoes += [ataque("AO", 3000 + i * 50, score="YUKO" if i < 2 else "")
                  for i in range(14)]
        r.mostrar(acoes, 30.0, "Assemat", "Duarte")
        rotulos = " ".join(w._rot_aka + " " + w._rot_ao
                           for w, _ in r._animaveis if hasattr(w, "_rot_aka"))
        assert "0/28" in rotulos and "2/14" in rotulos
        t = textos(r)
        assert "0 dos seus 28 ataques" in t
        assert "2 dos seus 14 ataques" in t

    def test_avisa_quando_a_base_e_curta(self):
        """Com menos de dez ataques a porcentagem não se sustenta."""
        r = RelatorioTreinador()
        r.mostrar([ataque("AKA", 100), ataque("AO", 500, score="YUKO")], 30.0)
        assert "dez ataques" in textos(r)

    def test_nao_avisa_quando_ha_base(self):
        r = RelatorioTreinador()
        acoes = [ataque("AKA", 100 + i * 50) for i in range(15)]
        acoes += [ataque("AO", 3000 + i * 50, score="YUKO" if i < 2 else "")
                  for i in range(15)]
        r.mostrar(acoes, 30.0)
        assert "dez ataques" not in textos(r)

    def test_conta_as_fintas_respondidas(self):
        r = RelatorioTreinador()
        r.mostrar([finta("AKA", 100), defesa("AO", 120, vs="Feint"),
                   finta("AKA", 300), ataque("AO", 900, score="YUKO")],
                  30.0, "Assemat", "Duarte")
        assert "2 fintas" in textos(r) and "1 fizeram" in textos(r)

    def test_diz_que_as_fintas_nao_tem_referencia(self):
        """Marcar o exploratório como exploratório é parte do dado."""
        r = RelatorioTreinador()
        r.mostrar([finta("AKA", 100), ataque("AO", 900, score="YUKO")], 30.0)
        assert "Nenhum estudo de karate mediu fintas" in textos(r)

    def test_explica_por_que_o_tipo_de_tecnica_vai_em_contagem(self):
        r = RelatorioTreinador()
        r.mostrar([ataque("AO", 500, score="YUKO")], 30.0)
        assert "Contagem, não aproveitamento" in textos(r)

    def test_destaca_atacar_mais_e_pontuar_menos(self):
        """A leitura que o treinador precisa ver sem procurar."""
        r = RelatorioTreinador()
        acoes = [ataque("AKA", 100 + i * 50) for i in range(20)]
        acoes += [ataque("AO", 3000, score="YUKO")]
        r.mostrar(acoes, 30.0, "Assemat", "Duarte")
        assert "atacou mais e pontuou menos" in textos(r)


class TestAnimacao:
    def test_os_blocos_entram_escalonados(self):
        """Um de cada vez: o objetivo é ser calmo de ver."""
        r = RelatorioTreinador()
        r.mostrar([ataque("AO", 500, score="YUKO")], 30.0)
        assert all(b._efeito.opacity() == 0.0 for b in r._blocos)

    def test_as_barras_comecam_no_zero(self):
        r = RelatorioTreinador()
        r.mostrar([ataque("AO", 500, score="YUKO")], 30.0)
        assert all(w.avanco == 0.0 for w, _ in r._animaveis)
