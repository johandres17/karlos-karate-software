# -*- coding: utf-8 -*-
"""O relatório do combate, escrito para um treinador.

Quem lê isto conhece karate e pode não conhecer estatística. Daí as
três regras que governam cada pixel deste arquivo:

  UMA PERGUNTA POR BLOCO. Nada de painel com vinte números de uma vez.
  O relatório desce respondendo uma pergunta de cada vez, e nunca há
  mais de duas cifras disputando a atenção.

  TODO NÚMERO VEM COM SUA FRASE. "Ea 14,3%" não diz nada a ninguém.
  "AO acertou 2 dos seus 14 ataques" diz tudo. O número grande serve
  para comparar de relance; a frase diz o que significa.

  A ANIMAÇÃO GUIA, NÃO ENFEITA. As barras crescem do zero porque o
  olho compara comprimentos em movimento melhor do que dois números
  parados. Nada pisca nem quica: uma coisa se move de cada vez, devagar,
  e ao terminar a tela fica quieta.

O que entra e o que não entra foi decidido medindo. Num único combate um
atleta lança quatro combinações e três ataques com finta prévia: um
percentual sobre quatro tentativas não é uma medida, é uma anedota com
decimais. Por isso aqui só há percentual onde há base — o aproveitamento
global, entre 9 e 28 tentativas — e o resto vai em contagem.
"""

from __future__ import annotations

from PySide6.QtCore import (Property, QEasingCurve, QParallelAnimationGroup,
                            QPoint, QPropertyAnimation, Qt, QTimer)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

# ── Paleta ───────────────────────────────────────────────────────────
# Calma por decisão: fundo profundo, uma cor por atleta e nada mais.
# Toda cor extra é uma pergunta a mais para quem lê.
_FUNDO = "#0F1114"
_CARTAO = "#1A1F26"
_BORDA = "rgba(255,255,255,0.07)"
_TEXTO = "#F4F7FB"
_TEXTO_2 = "rgba(242,242,247,0.58)"
_TEXTO_3 = "rgba(242,242,247,0.34)"
_AKA = "#FF453A"
_AO = "#0A84FF"
_NEUTRO = "rgba(242,242,247,0.22)"

_LENTO = 900          # ms — o crescimento das barras
_SUAVE = 550          # ms — a entrada dos blocos


def _fonte(tamanho: int, peso: int = 400) -> QFont:
    f = QFont()
    f.setPointSize(tamanho)
    f.setWeight(QFont.Weight(peso))
    return f


class _Barra(QWidget):
    """Duas barras enfrentadas, uma por atleta, que crescem do zero.

    Em contagens — ataques, fintas — a referência é o maior dos dois,
    não um máximo fixo: o que interessa é a comparação entre estes dois
    atletas, e uma escala absoluta esconderia a diferença quando os dois
    números são pequenos.

    Em porcentagens NÃO. Com 0% e 14%, a referência relativa pinta o
    14% de ponta a ponta e o olho lê "acertou tudo" onde o número diz
    "acertou um em sete". A escala vai de 0 a 100 e a barra curta é a
    informação.
    """

    ALTURA = 34

    def __init__(self, aka: float, ao: float, rotulo_aka: str,
                 rotulo_ao: str, parent=None, referencia: float | None = None) -> None:
        super().__init__(parent)
        self._referencia = referencia
        self._aka, self._ao = float(aka), float(ao)
        self._rot_aka, self._rot_ao = rotulo_aka, rotulo_ao
        self._avanco = 0.0
        self.setMinimumHeight(self.ALTURA * 2 + 14)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _get_avanco(self) -> float:
        return self._avanco

    def _set_avanco(self, v: float) -> None:
        self._avanco = v
        self.update()

    avanco = Property(float, _get_avanco, _set_avanco)

    def animar(self, retardo: int = 0) -> QPropertyAnimation:
        a = QPropertyAnimation(self, b"avanco", self)
        a.setDuration(_LENTO)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        # OutCubic: arranca rápido e freia no fim. Sem quique — um quique
        # faz o olho voltar atrás e reler, que é o contrário de calmo.
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        if retardo:
            QTimer.singleShot(retardo, a.start)
        else:
            a.start()
        return a

    # O valor vive numa coluna fixa à direita, nunca em cima da barra:
    # sobre a cor saturada o texto perde contraste justo quando a barra
    # é longa, que é quando mais se olha.
    COLUNA_VALOR = 120

    def paintEvent(self, evento) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        util = max(40, self.width() - self.COLUNA_VALOR)
        maximo = (self._referencia if self._referencia
                  else max(self._aka, self._ao, 1.0))
        for i, (valor, rotulo, cor) in enumerate(
                ((self._aka, self._rot_aka, _AKA),
                 (self._ao, self._rot_ao, _AO))):
            y = i * (self.ALTURA + 14)
            trilho = QPainterPath()
            trilho.addRoundedRect(0, y + 8, util, self.ALTURA - 16, 5, 5)
            p.fillPath(trilho, QColor(255, 255, 255, 12))
            # Um valor zero deixa um toco visível. Sem ele a cor do
            # atleta some da tela e não se lê "está em zero": lê-se
            # "falta alguma coisa aqui".
            largo = max(6.0, util * (valor / maximo)) * self._avanco
            barra = QPainterPath()
            barra.addRoundedRect(0, y + 8, largo, self.ALTURA - 16, 5, 5)
            p.fillPath(barra, QColor(cor))
            p.setPen(QColor(_TEXTO))
            p.setFont(_fonte(13, 600))
            p.drawText(util + 12, y, self.COLUNA_VALOR - 12, self.ALTURA,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       rotulo)
        p.end()


class _LinhaDoTempo(QWidget):
    """O combate inteiro numa linha, com o ponto de virada marcado.

    Antes do ponto de virada os dois atletas são indistinguíveis; depois,
    um domina até o fim (Tabben et al. 2018). Por isso o trecho anterior
    fica apagado e o posterior acende: o olho vai direto para a parte do
    combate que decidiu o resultado.
    """

    ALTURA = 76

    def __init__(self, virada_pct: float, cor_vencedor: str,
                 parent=None) -> None:
        super().__init__(parent)
        self._pct = max(0.0, min(1.0, virada_pct))
        self._cor = cor_vencedor
        self._avanco = 0.0
        self.setMinimumHeight(self.ALTURA)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _get_avanco(self) -> float:
        return self._avanco

    def _set_avanco(self, v: float) -> None:
        self._avanco = v
        self.update()

    avanco = Property(float, _get_avanco, _set_avanco)

    def animar(self, retardo: int = 0) -> QPropertyAnimation:
        a = QPropertyAnimation(self, b"avanco", self)
        a.setDuration(_LENTO + 300)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.InOutCubic)
        if retardo:
            QTimer.singleShot(retardo, a.start)
        else:
            a.start()
        return a

    def paintEvent(self, evento) -> None:      # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        largura, y = self.width(), 34
        corte = largura * self._pct
        visivel = largura * self._avanco

        antes = QPainterPath()
        antes.addRoundedRect(0, y, min(corte, visivel), 10, 5, 5)
        p.fillPath(antes, QColor(_NEUTRO))

        if visivel > corte:
            depois = QPainterPath()
            depois.addRoundedRect(corte, y, visivel - corte, 10, 5, 5)
            p.fillPath(depois, QColor(self._cor))

        if self._avanco > self._pct:
            p.setPen(QColor(self._cor))
            p.setBrush(QColor(self._cor))
            p.drawEllipse(QPoint(int(corte), y + 5), 7, 7)
            p.setPen(QColor(_TEXTO_2))
            p.setFont(_fonte(10, 500))
            p.drawText(0, y + 20, largura, 20,
                       Qt.AlignmentFlag.AlignLeft, "início")
            p.drawText(0, y + 20, largura, 20,
                       Qt.AlignmentFlag.AlignRight, "fim")
        p.end()


class _Bloco(QFrame):
    """Um bloco do relatório: uma pergunta, uma resposta, uma frase."""

    def __init__(self, pergunta: str, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame{{background:{_CARTAO};border:1px solid {_BORDA};"
            "border-radius:14px;}")
        self._caixa = QVBoxLayout(self)
        self._caixa.setContentsMargins(28, 24, 28, 26)
        self._caixa.setSpacing(14)

        titulo = QLabel(pergunta.upper())
        titulo.setStyleSheet(
            f"color:{_TEXTO_3};background:transparent;border:none;"
            "letter-spacing:1.6px;")
        titulo.setFont(_fonte(9, 700))
        self._caixa.addWidget(titulo)

        self._efeito = QGraphicsOpacityEffect(self)
        self._efeito.setOpacity(0.0)
        self.setGraphicsEffect(self._efeito)

    def adicionar(self, w: QWidget) -> None:
        self._caixa.addWidget(w)

    def frase(self, texto: str, destaque: bool = False) -> None:
        """A linha que diz o que o número significa."""
        etiqueta = QLabel(texto)
        etiqueta.setWordWrap(True)
        etiqueta.setStyleSheet(
            f"color:{_TEXTO if destaque else _TEXTO_2};"
            "background:transparent;border:none;line-height:150%;")
        etiqueta.setFont(_fonte(13 if destaque else 12,
                                600 if destaque else 400))
        self._caixa.addWidget(etiqueta)

    def aviso(self, texto: str) -> None:
        """Um alerta sobre a base do dado, em voz baixa mas visível."""
        etiqueta = QLabel("⚠  " + texto)
        etiqueta.setWordWrap(True)
        etiqueta.setStyleSheet(
            f"color:{_TEXTO_3};background:transparent;border:none;")
        etiqueta.setFont(_fonte(11))
        self._caixa.addWidget(etiqueta)

    def aparecer(self, retardo: int) -> None:
        """Entra subindo um pouco e ganhando opacidade."""
        grupo = QParallelAnimationGroup(self)
        fade = QPropertyAnimation(self._efeito, b"opacity", self)
        fade.setDuration(_SUAVE)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        grupo.addAnimation(fade)
        self._grupo = grupo
        QTimer.singleShot(retardo, grupo.start)


class RelatorioTreinador(QScrollArea):
    """O relatório completo de um combate.

    Seis blocos, nesta ordem, porque é a ordem em que um treinador faz
    as perguntas: quem ganhou e quando se decidiu, quem acertava mais,
    o que mudou depois, como cada um se defendeu, o que cada um fez, e
    para que serviram as fintas.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"QScrollArea{{background:{_FUNDO};border:none;}}"
            f"QWidget#folha{{background:{_FUNDO};}}"
            "QScrollBar:vertical{background:transparent;width:8px;margin:0;}"
            "QScrollBar::handle:vertical{background:rgba(255,255,255,0.14);"
            "border-radius:4px;min-height:40px;}"
            "QScrollBar::add-line,QScrollBar::sub-line{height:0;}")
        self._folha = QWidget()
        self._folha.setObjectName("folha")
        self._pilha = QVBoxLayout(self._folha)
        self._pilha.setContentsMargins(36, 32, 36, 48)
        self._pilha.setSpacing(18)
        self.setWidget(self._folha)
        self._blocos: list[_Bloco] = []
        self._animaveis: list = []

    # ── montagem ────────────────────────────────────────────────────
    def mostrar(self, anotacoes, fps: float, nome_aka: str = "AKA",
                nome_ao: str = "AO") -> None:
        """Calcular tudo e montar o relatório."""
        from karlos_karate import metricas_combate as M
        self._limpar()
        aka, ao = nome_aka or "AKA", nome_ao or "AO"
        vencedor, pa, po = M.ganador(anotacoes)
        virada = M.momento_decisivo(anotacoes, vencedor)
        fim = max((int(a.f_end) for a in anotacoes), default=1) or 1
        e_aka, e_ao = M.eficacia(anotacoes, "AKA"), M.eficacia(anotacoes, "AO")

        self._veredicto(aka, ao, vencedor, pa, po, virada, fim, fps)
        self._aproveitamento(aka, ao, e_aka, e_ao)
        if virada is not None:
            self._depois_da_virada(anotacoes, aka, ao, vencedor, virada, fps)
        self._defesa(aka, ao, e_aka, e_ao)
        self._o_que_fizeram(anotacoes, aka, ao)
        self._fintas(anotacoes, aka, ao, fps)

        self._pilha.addStretch(1)
        for i, b in enumerate(self._blocos):
            b.aparecer(120 + i * 130)
        for j, (w, atraso) in enumerate(self._animaveis):
            w.animar(360 + atraso)

    def _limpar(self) -> None:
        while self._pilha.count():
            item = self._pilha.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._blocos.clear()
        self._animaveis.clear()

    def _novo(self, pergunta: str) -> _Bloco:
        b = _Bloco(pergunta, self._folha)
        self._pilha.addWidget(b)
        self._blocos.append(b)
        return b

    @staticmethod
    def _cor(quem: str) -> str:
        return _AKA if quem == "AKA" else _AO

    # ── os blocos ───────────────────────────────────────────────────
    def _veredicto(self, aka, ao, vencedor, pa, po, virada, fim, fps) -> None:
        b = self._novo("O combate")
        placar = QLabel(f"{pa}  –  {po}")
        placar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placar.setStyleSheet(
            f"color:{_TEXTO};background:transparent;border:none;"
            "letter-spacing:4px;")
        placar.setFont(_fonte(44, 200))
        b.adicionar(placar)

        nomes = QLabel(f"{aka}          {ao}")
        nomes.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nomes.setStyleSheet(f"color:{_TEXTO_2};background:transparent;border:none;")
        nomes.setFont(_fonte(12, 500))
        b.adicionar(nomes)

        if vencedor and virada is not None:
            pct = virada / fim
            linha = _LinhaDoTempo(pct, self._cor(vencedor), b)
            b.adicionar(linha)
            self._animaveis.append((linha, 200))
            quem = aka if vencedor == "AKA" else ao
            # Sem fps não há segundos que mostrar, mas a fração do
            # combate continua valendo: é a que diz quando virou.
            quando = (f"aos {virada / fps:.0f} segundos, " if fps else "")
            b.frase(
                f"O combate virou {quando}a {100 * pct:.0f}% da luta. "
                f"A partir daí {quem} nunca mais ficou atrás.",
                destaque=True)
            b.frase("O trecho apagado é a parte em que os dois ainda "
                    "estavam em aberto. O aceso é a parte que decidiu.")
        elif not vencedor:
            b.frase("O combate terminou empatado no placar.", destaque=True)

    def _aproveitamento(self, aka, ao, e_aka, e_ao) -> None:
        b = self._novo("Quem acertava mais")
        barra = _Barra(e_aka.ea, e_ao.ea,
                       f"{e_aka.ea:.0f}%   ({e_aka.ataques})",
                       f"{e_ao.ea:.0f}%   ({e_ao.ataques})", b,
                       referencia=100.0)
        b.adicionar(barra)
        self._animaveis.append((barra, 380))
        for nome, e in ((aka, e_aka), (ao, e_ao)):
            b.frase(f"{nome} acertou {e.ataques.parte} dos seus "
                    f"{e.ataques.total} ataques.")
        mais = aka if e_aka.ataques.total > e_ao.ataques.total else ao
        menos = ao if mais == aka else aka
        d_mais = e_aka if mais == aka else e_ao
        d_menos = e_ao if mais == aka else e_aka
        if d_mais.ataques.total > d_menos.ataques.total and d_mais.puntos < d_menos.puntos:
            b.frase(f"{mais} atacou mais e pontuou menos: "
                    f"{d_mais.ataques.total} ataques para "
                    f"{d_mais.puntos} ponto(s), contra "
                    f"{d_menos.ataques.total} e {d_menos.puntos} de {menos}.",
                    destaque=True)
        if not (e_aka.ataques.fiable and e_ao.ataques.fiable):
            b.aviso("Com menos de dez ataques, um acerto a mais move muito "
                    "o percentual. Leia a contagem, não a porcentagem.")

    def _depois_da_virada(self, anotacoes, aka, ao, vencedor, virada, fps) -> None:
        from karlos_karate import metricas_combate as M
        b = self._novo("O que mudou depois do ponto de virada")
        depois = {q: M.tramo(anotacoes, q, lambda x: int(x.f_start) > virada)
                  for q in ("AKA", "AO")}
        barra = _Barra(depois["AKA"].ataques, depois["AO"].ataques,
                       f"{depois['AKA'].ataques} ataques",
                       f"{depois['AO'].ataques} ataques", b)
        b.adicionar(barra)
        self._animaveis.append((barra, 380))
        for q, nome in (("AKA", aka), ("AO", ao)):
            t = depois[q]
            b.frase(f"{nome}: {t.ataques} ataques e {t.puntos} ponto(s) "
                    f"depois da virada.")
        perdedor = "AO" if vencedor == "AKA" else "AKA"
        t = depois[perdedor]
        if t.ataques and not t.puntos:
            nome = aka if perdedor == "AKA" else ao
            b.frase(f"{nome} atacou {t.ataques} vezes depois da virada "
                    "sem pontuar nenhuma.", destaque=True)

    def _defesa(self, aka, ao, e_aka, e_ao) -> None:
        b = self._novo("Quem se defendeu melhor")
        barra = _Barra(e_aka.eo, e_ao.eo,
                       f"{e_aka.eo:.0f}%", f"{e_ao.eo:.0f}%", b,
                       referencia=100.0)
        b.adicionar(barra)
        self._animaveis.append((barra, 380))
        for nome, e in ((aka, e_aka), (ao, e_ao)):
            r = e.ataques_rival
            b.frase(f"{nome} recebeu {r.total} ataques e encaixou {r.parte}.")

    def _o_que_fizeram(self, anotacoes, aka, ao) -> None:
        from karlos_karate import metricas_combate as M
        b = self._novo("Com o que cada um atacou")
        for q, nome in (("AKA", aka), ("AO", ao)):
            c = M.por_clase(anotacoes, q)
            partes = [(f"{c['mano'].total} de soco", c["mano"].total),
                      (f"{c['pierna'].total} de chute", c["pierna"].total),
                      (f"{c['suelo'].total} de queda", c["suelo"].total)]
            texto = ", ".join(t for t, n in partes if n)
            b.frase(f"{nome}: {texto}." if texto else f"{nome}: sem ataques.")
        b.frase("Contagem, não aproveitamento: num só combate não há "
                "tentativas suficientes por tipo de técnica para que uma "
                "porcentagem signifique algo.")

    def _fintas(self, anotacoes, aka, ao, fps) -> None:
        from karlos_karate import metricas_combate as M
        b = self._novo("Para que serviram as fintas")
        f_aka = M.fintas(anotacoes, "AKA", fps)
        f_ao = M.fintas(anotacoes, "AO", fps)
        if not (f_aka["lanzadas"] or f_ao["lanzadas"]):
            b.frase("Nenhuma finta anotada neste combate.")
            return
        barra = _Barra(f_aka["respondidas"], f_ao["respondidas"],
                       f"{f_aka['respondidas']} de {f_aka['lanzadas']}",
                       f"{f_ao['respondidas']} de {f_ao['lanzadas']}", b)
        b.adicionar(barra)
        self._animaveis.append((barra, 380))
        for nome, f in ((aka, f_aka), (ao, f_ao)):
            if not f["lanzadas"]:
                continue
            pct = 100 * f["respondidas"] / f["lanzadas"]
            b.frase(f"{nome} deu {f['lanzadas']} fintas e "
                    f"{f['respondidas']} fizeram o adversário se mexer "
                    f"({pct:.0f}%).")
        b.frase("Nenhum estudo de karate mediu fintas até hoje, então não "
                "há com o que comparar. Serve para comparar os dois "
                "atletas deste combate entre si.")
