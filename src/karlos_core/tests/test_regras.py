"""Las reglas del libro de codigos, una a una.

Cada test es un caso del arbitraje de ID30 (21-09-2026) convertido en
regla: lo que alli fue un desacuerdo aqui es un comportamiento fijo.
"""

from __future__ import annotations


from karlos_core.models import regras
from karlos_core.models.annotation import Annotation

FPS = 30.0


def _a(atleta, categoria, tecnica, f0, f1, nivel=""):
    return Annotation(athlete=atleta, category=categoria, subcategory="",
                      technique=tecnica, level=nivel, score="",
                      f_start=f0, f_end=f1, duration_s=(f1 - f0) / FPS, round=1)


def _parada(atleta, f0, f1):
    return _a(atleta, "REFEREE STOP", "Referee", f0, f1)


# ── las reglas retiradas ────────────────────────────────────────────

class TestLasReglasRetiradas:
    """El 24-09-2026 el programa dejó de decidir por el evaluador.

    Se fueron cinco reglas, todas del mismo tipo: miraban el reloj o las
    filas de al lado para juntar, rechazar o corregir lo que el
    evaluador acababa de marcar. El criterio es ahora que cada entrada
    es una línea y que agrupar o filtrar es del tratamiento de datos,
    donde se puede rehacer sin volver a ver los combates.
    """

    def test_ninguna_de_las_cinco_sigue_en_pie(self):
        for retirada in ("finta_a_extender",      # juntaba la tanda
                         "finta_corta",           # rechazaba la finta breve
                         "ataque_rival_reciente",  # exigía algo que esquivar
                         "prohibida_en_pausa",    # rechazaba dentro de una parada
                         "parada_que_contiene",
                         "parada_solapada"):      # fundía dos filas de una pausa
            assert not hasattr(regras, retirada), retirada

    def test_los_numeros_de_la_calibracion_se_quedan_como_referencia(self):
        """Siguen existiendo porque el manual los cita, no porque manden."""
        assert regras.TANDA_S == 1.5
        assert regras.FINTA_MIN_REFERENCIA == 8
        assert regras.ESQUIVA_JANELA_S == 1.0

    def test_tampoco_queda_la_auditoria_de_huecos(self):
        """El registro es manual: no hay auditoria automatica de huecos."""
        assert not hasattr(regras, "lacunas")


# ── 1. el programa no junta nada ────────────────────────────────────

class TestNadaSeJunta:
    """Cada registro es una fila. Las tandas se arman después.

    Hasta el 24-09-2026 dos fintas seguidas del mismo miembro dentro de
    1,5 s salían en una sola fila: la segunda alargaba la primera. Johan
    lo retiró porque agrupar al anotar decide por adelantado un criterio
    que después no se puede cambiar sin volver a ver los combates. El
    programa registra lo observado; agrupar es del procesamiento.
    """

    def test_la_regla_de_juntar_fintas_ya_no_existe(self):
        assert not hasattr(regras, "finta_a_extender")

    def test_el_flujo_no_alarga_ninguna_anotacion(self):
        import inspect
        from karlos_core.controllers import annotation_flow_controller as afc
        fuente = inspect.getsource(afc)
        assert "finta_a_extender" not in fuente
        assert "ExtenderAnotacionCommand" not in fuente


# ── 2. la finta corta ya no se rechaza ──────────────────────────────

class TestNingunaFintaSeRechaza:
    """El mínimo de ocho fotogramas dejó de ser una regla.

    Preguntaba, con un cuadro que había que contestar, si una finta más
    corta se anotaba igual. Cortaba el trabajo justo en la acción más
    frecuente del combate: en ID30, 82 de 228 anotaciones eran fintas.
    La duración está en el registro, así que filtrar por ella es cosa
    del análisis, no del momento de anotar.
    """

    def test_ya_no_hay_regla_que_juzgue_la_duracion(self):
        assert not hasattr(regras, "finta_corta")
        assert not hasattr(regras, "FINTA_MIN_FRAMES")

    def test_el_ocho_sigue_como_referencia_de_la_calibracion(self):
        assert regras.FINTA_MIN_REFERENCIA == 8
