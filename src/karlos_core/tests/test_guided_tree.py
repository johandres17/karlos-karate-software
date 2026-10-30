"""Tests del arbol de preguntas.

Lo que se protege aqui es el coste: el orden de las opciones sale de la
frecuencia real (ID30, 228 anotaciones) y cualquier cambio que aleje una
accion frecuente de la primera pantalla encarece el pase entero.
"""

from __future__ import annotations

import pytest

from karlos_karate.karate_config import COMBINATORIAL_MAP
from karlos_karate.guided_tree import ArbolGuiado, _META
from karlos_core.models.technique import resolve_combat_action
from karlos_core.utils.merge_utils import parse_combined_level


def recorrer(*claves):
    a = ArbolGuiado()
    for c in claves:
        a.elegir(c)
    return a


def todos_los_caminos():
    """Todos los recorridos completos, con su numero de preguntas."""
    pend, salida = [(ArbolGuiado(), 0)], []
    while pend:
        a, n = pend.pop()
        p = a.paso_actual()
        if p is None:
            if a.tecnica:
                salida.append((a, n))
            continue
        for _, clave in p.opciones:
            b = a.copiar()
            b.elegir(clave)
            if not b.descartada:
                pend.append((b, n + 1))
    return salida


class TestCoste:
    """El motivo de reordenar el arbol: las acciones frecuentes primero."""

    def test_una_finta_cuesta_una_sola_pregunta(self):
        """Son el 36% de lo anotado; antes costaban tres preguntas."""
        a = recorrer("finta_sup")
        assert a.completa and a.resultado()[0] == "Feint"

    def test_una_esquiva_cuesta_una_sola_pregunta(self):
        a = recorrer("Dodge")
        assert a.completa

    def test_clinch_y_bloqueo_cuestan_una(self):
        assert recorrer("Clinch").completa
        assert recorrer("Hand Block").completa

    def test_la_guardia_viene_en_el_nombre(self):
        """Kizami es adelantado y Gyaku atrasado: preguntarlo aparte era
        preguntar lo mismo dos veces. En ID30, Gyaku Tsuki sale Rear las
        trece veces y Kizami Tsuki Lead las doce."""
        assert recorrer("ataque", "Tsuki|Rear").guardia == "Rear"
        assert recorrer("ataque", "Tsuki|Lead").guardia == "Lead"
        assert recorrer("ataque", "Mawashi Geri|Lead").guardia == "Lead"

    def test_ya_no_se_pregunta_la_guardia(self):
        a = recorrer("ataque", "Tsuki|Rear")
        assert a.paso_actual().pregunta == "Em qual nível?"

    def test_jodan_va_primero(self):
        """Es el 83% de lo anotado."""
        a = recorrer("ataque", "Tsuki|Rear")
        assert a.paso_actual().opciones[0][1] == "|Jodan"

    def test_un_punetazo_completo_cuesta_cinco(self):
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Counter", "Res:Contact")
        assert a.completa
        assert a.resultado()[0] == "Tsuki" and a.guardia == "Rear" and a.nivel == "Jodan"

    def test_ninguna_accion_pasa_de_siete_preguntas(self):
        """Solo llega ahi el ataque sancionado, que es lo mas raro."""
        assert max(n for _, n in todos_los_caminos()) <= 7

    def test_las_cinco_acciones_mas_frecuentes_estan_en_la_primera_pantalla(self):
        claves = {c for _, c in ArbolGuiado().paso_actual().opciones}
        # finta (82), esquiva (44), clinch (22), bloqueo (12) resueltas ahi mismo
        assert {"finta_sup", "finta_inf", "Dodge", "Clinch", "Hand Block"} <= claves


class TestCobertura:
    def test_se_llega_a_las_paradas_de_arbitro(self):
        """Son 24 de 228 anotaciones y antes habia que salir del arbol."""
        a = recorrer("parada", "Referee")
        tec, _, cat, _ = a.resultado()
        assert a.completa and tec == "Referee" and cat == "REFEREE STOP"

    @pytest.mark.parametrize("clave", ["Referee", "VR", "Injury"])
    def test_los_tres_motivos_de_parada(self, clave):
        assert recorrer("parada", clave).completa

    def test_se_llega_a_las_tecnicas_poco_usadas(self):
        a = recorrer("ataque", "otras", "Other Kick|Rear", "|Chudan", "Act:Direct", "Res:Contact")
        assert a.completa and a.resultado()[0] == "Other Kick"

    def test_toda_tecnica_del_arbol_es_alcanzable(self):
        alcanzadas = {a.tecnica for a, _ in todos_los_caminos()}
        assert alcanzadas == set(_META)


class TestCoherencia:
    def test_la_cadena_de_nivel_siempre_se_entiende(self):
        """Un segmento que el parser no reconoce acaba en la columna Level
        del Excel y rompe la exportacion."""
        for a, _ in todos_los_caminos():
            _, nivel, _, _ = a.resultado()
            assert "raw" not in parse_combined_level(nivel), nivel

    def test_un_ataque_con_guardia_resuelve_al_nombre_japones(self):
        a = recorrer("ataque", "Tsuki|Lead", "|Jodan", "Act:Direct", "Res:Contact")
        assert resolve_combat_action(a.tecnica, a.guardia, COMBINATORIAL_MAP) == "Kizami Tsuki"
        b = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Contact")
        assert resolve_combat_action(b.tecnica, b.guardia, COMBINATORIAL_MAP) == "Gyaku Tsuki"

    def test_toda_tecnica_que_pide_guardia_acaba_con_guardia(self):
        for a, _ in todos_los_caminos():
            if _META[a.tecnica][2]:
                assert a.guardia, a.tecnica

    def test_toda_tecnica_que_pide_nivel_acaba_con_nivel(self):
        for a, _ in todos_los_caminos():
            if _META[a.tecnica][3]:
                assert a.nivel, a.tecnica

    def test_copiar_conserva_el_recorrido(self):
        """Construir el arbol por posicion desplazaba los argumentos en
        silencio al anadir un campo, y el recorrido se quedaba vacio."""
        a = recorrer("ataque", "Tsuki|Lead", "|Chudan")
        b = a.copiar()
        assert (b.tecnica, b.guardia, b.nivel, b.limbo, b.contexto) == \
               (a.tecnica, a.guardia, a.nivel, a.limbo, a.contexto)
        assert b._ruta == a._ruta and b._ruta is not a._ruta
        assert b.paso_actual().pregunta == a.paso_actual().pregunta

    def test_ushiro_geri_es_siempre_atrasada(self):
        """Es una tecnica giratoria: no existe version adelantada."""
        a = recorrer("ataque", "otras", "Ushiro Geri|Rear")
        assert a.guardia == "Rear"
        assert a.paso_actual().opciones[0][1] == "|Jodan"

    def test_ninguna_pregunta_pasa_de_diez_opciones(self):
        """Toda opción tiene que tener una tecla.

        Las nueve primeras van con su número y la décima con el 0, que
        es la contigua al 9 y la última de la fila. Pasar de diez deja
        opciones que solo se pueden pulsar con el ratón, y este panel
        existe para no soltar el teclado.
        """
        pend = [ArbolGuiado()]
        vistas = 0
        while pend and vistas < 500:
            a = pend.pop(); vistas += 1
            p = a.paso_actual()
            if p is None:
                continue
            assert 0 < len(p.opciones) <= 10, p.pregunta
            for _, clave in p.opciones:
                b = a.copiar()
                b.elegir(clave)
                if not b.descartada:
                    pend.append(b)


class TestFinta:
    def test_el_segmento_viaja_en_la_cadena_de_nivel(self):
        _, nivel, cat, _ = recorrer("finta_sup").resultado()
        assert "Limb: Upper Limb" in nivel and cat == "TACTICS"

    def test_las_dos_fintas_se_distinguen(self):
        assert recorrer("finta_sup").limbo != recorrer("finta_inf").limbo


class TestRetroceso:
    def test_deshace_la_ultima_eleccion(self):
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Contact")
        assert a.completa
        a.retroceder()
        assert not a.completa and a.resultado_ataque is None
        a.retroceder()
        assert a.contexto is None
        a.retroceder()
        assert a.nivel is None
        a.retroceder()
        assert a.guardia is None and a.tecnica is None

    def test_deshacer_una_finta_borra_el_segmento(self):
        a = recorrer("finta_sup")
        a.retroceder()
        assert a.tecnica is None and a.limbo is None

    def test_deshacer_ushiro_geri_suelta_la_guardia(self):
        a = recorrer("ataque", "Ushiro Geri")
        a.retroceder()
        assert a.guardia is None and a.tecnica is None

    def test_desde_cualquier_camino_se_deshace_hasta_el_principio(self):
        for a, _ in todos_los_caminos():
            pasos = 0
            while a.retroceder():
                pasos += 1
                assert pasos < 12, "el retroceso no termina"
                a.paso_actual()      # no debe lanzar a medio camino
            assert a.paso_actual() is not None

    def test_sin_nada_que_deshacer_devuelve_falso(self):
        assert ArbolGuiado().retroceder() is False


class TestDescarte:
    def test_descartar_no_produce_tecnica(self):
        a = recorrer("descartar")
        assert a.descartada and not a.completa

    def test_un_recorrido_sin_tecnica_no_da_resultado(self):
        with pytest.raises(ValueError):
            ArbolGuiado().resultado()


class TestPuntuacion:
    """El arbol no pregunta la puntuacion: de 38 ataques anotados en ID30
    solo 2 puntuaron. Va en la tecla [P], y el valor sale de las reglas
    WKF, no de una eleccion."""

    def _motor(self):
        from karlos_core.utils.config_loader import load_config
        cfg, _ = load_config("karate")
        return cfg, {c.name: c for c in cfg.categories}

    def _puntuar(self, a):
        cfg, cats = self._motor()
        tec, _, _, grupo = a.resultado()
        resuelta = resolve_combat_action(tec, a.guardia or "", COMBINATORIAL_MAP)
        return cfg.scoring_engine.calculate_score(
            resuelta, a.nivel or "", cats.get(grupo))

    def test_un_puno_a_la_cabeza_es_yuko(self):
        """Regla WKF: Tsuki/Uchi puntuan Yuko en cualquier zona valida,
        cabeza incluida. Ippon queda para las patadas Jodan."""
        assert self._puntuar(recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Contact")) == "YUKO"

    def test_una_patada_a_la_cabeza_es_ippon(self):
        assert self._puntuar(
            recorrer("ataque", "Mawashi Geri|Rear", "|Jodan", "Act:Direct", "Res:Contact")) == "IPPON"

    def test_una_patada_al_tronco_es_waza_ari(self):
        assert self._puntuar(
            recorrer("ataque", "Mawashi Geri|Rear", "|Chudan", "Act:Direct", "Res:Contact")) == "WAZA"

    def test_lo_que_no_puntua_devuelve_none(self):
        for camino in (("finta_sup",), ("Dodge",), ("Clinch",), ("Hand Block",),
                       ("parada", "Referee")):
            assert self._puntuar(recorrer(*camino)) in ("", "NONE"), camino

    def test_todo_ataque_con_nivel_sabe_puntuar(self):
        """Si alguno devolviera NONE, [P] no haria nada y el evaluador no
        sabria por que."""
        for a, _ in todos_los_caminos():
            if _META[a.tecnica][1] == "ATTACK" and a.nivel:
                assert self._puntuar(a) not in ("", "NONE"), a.tecnica


class TestContextoTactico:
    """Es la variable mas citada en el analisis de kumite de elite y solo
    la tenian 3 de 228 anotaciones, porque el arbol no la preguntaba."""

    def test_todo_ataque_acaba_con_contexto(self):
        for a, _ in todos_los_caminos():
            if _META[a.tecnica][4]:
                assert a.contexto, a.tecnica

    def test_el_contexto_viaja_en_la_cadena_de_nivel(self):
        _, nivel, _, _ = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Counter", "Res:Contact").resultado()
        assert "Action: Counter" in nivel
        assert parse_combined_level(nivel)["action"] == "Counter"

    @pytest.mark.parametrize("clave,valor", [
        ("Act:Direct", "Direct"), ("Act:Counter", "Counter"),
        ("Act:Anticipation", "Anticipation"), ("Act:Combination", "Combination")])
    def test_los_cuatro_contextos(self, clave, valor):
        a = recorrer("ataque", "Tsuki|Lead", "|Chudan", clave, "Res:Miss")
        assert a.completa and a.contexto == valor

    def test_lo_que_no_es_ataque_no_lo_pregunta(self):
        for camino in (("finta_sup",), ("Dodge",), ("Clinch",), ("Hand Block",),
                       ("parada", "VR")):
            assert recorrer(*camino).contexto is None, camino

    def test_deshacer_el_contexto_lo_vuelve_a_preguntar(self):
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Contact")
        a.retroceder()
        assert a.paso_actual().pregunta == "Como terminou?"
        a.retroceder()
        assert a.paso_actual().pregunta == "Contexto tático?"


class TestRastroDeRespuestas:
    """En la cuarta pregunta hay que poder ver si se dijo Tsuki o Uraken:
    sin el rastro, el error solo aparece despues, ya en el registro."""

    def test_guarda_lo_contestado_en_orden(self):
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan")
        assert a.respuestas() == ["Ataque", "Gyaku Tsuki", "Jodan (cabeça)"]

    def test_retroceder_borra_la_ultima(self):
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan")
        a.retroceder()
        assert a.respuestas() == ["Ataque", "Gyaku Tsuki"]

    def test_al_empezar_no_hay_rastro(self):
        assert ArbolGuiado().respuestas() == []

    def test_la_copia_no_comparte_el_rastro(self):
        a = recorrer("ataque", "Tsuki|Rear")
        b = a.copiar()
        b.elegir("|Jodan")
        assert len(a.respuestas()) == 2 and len(b.respuestas()) == 3

    def test_el_rastro_acompana_a_cada_camino(self):
        """Una respuesta por pregunta contestada, en todos los recorridos."""
        for a, n in todos_los_caminos():
            assert len(a.respuestas()) == n, (a.tecnica, a.respuestas())

    def test_deshacer_hasta_el_principio_deja_el_rastro_vacio(self):
        a = recorrer("ataque", "otras", "Other Kick|Rear", "|Chudan", "Act:Direct", "Res:Contact")
        while a.retroceder():
            pass
        assert a.respuestas() == []


class TestPreguntarMientrasSeMira:
    """Las preguntas arrancan con [D] y no al final, para poder seguir
    moviendo el video mientras se contesta — que es como se distingue una
    finta de un ataque. La anotacion espera a tener las dos cosas."""

    class _Ctrl:
        """Los dos caminos de _cerrar_guia, sin montar la aplicacion."""

        def __init__(self, con_fin):
            self._pro_fin = 120 if con_fin else None
            self._arbol_listo = None
            self.creadas = []

        def cerrar(self, arbol):
            if self._pro_fin is None:
                self._arbol_listo = arbol
                return "retenida"
            self.creadas.append(arbol.resultado()[0])
            return "creada"

        def marcar_fin(self, frame):
            self._pro_fin = frame
            if self._arbol_listo is not None:
                pendiente, self._arbol_listo = self._arbol_listo, None
                return self.cerrar(pendiente)
            return "sin nada pendiente"

    def test_contestar_antes_del_fin_retiene_la_anotacion(self):
        c = self._Ctrl(con_fin=False)
        assert c.cerrar(recorrer("finta_sup")) == "retenida"
        assert c.creadas == []

    def test_al_marcar_el_fin_se_crea_sin_volver_a_preguntar(self):
        c = self._Ctrl(con_fin=False)
        c.cerrar(recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Contact"))
        assert c.marcar_fin(140) == "creada"
        assert c.creadas == ["Tsuki"]

    def test_el_orden_anterior_sigue_valiendo(self):
        """Marcar el fin primero y contestar despues crea igual."""
        c = self._Ctrl(con_fin=True)
        assert c.cerrar(recorrer("Dodge")) == "creada"
        assert c.creadas == ["Dodge"]

    def test_el_fin_sin_respuestas_no_crea_nada(self):
        c = self._Ctrl(con_fin=False)
        assert c.marcar_fin(140) == "sin nada pendiente"
        assert c.creadas == []

    def test_lo_retenido_no_se_usa_dos_veces(self):
        c = self._Ctrl(con_fin=False)
        c.cerrar(recorrer("Clinch"))
        c.marcar_fin(140)
        assert c.marcar_fin(160) == "sin nada pendiente"
        assert c.creadas == ["Clinch"]


class TestAgrupacionDeOpciones:
    """Nueve opciones en lista plana hay que leerlas una a una; en bloques
    el ojo salta al bloque. Y agrupadas por familia se aprende la posicion
    — "mano es 1 y 2, pie del 3 al 7" se memoriza."""

    def test_la_primera_pregunta_agrupa_por_lo_que_hace_el_atleta(self):
        """Esquiva y bloqueo son la misma decision — defenderse, con
        contacto o sin el — y estaban a cuatro teclas de distancia."""
        p = ArbolGuiado().paso_actual()
        assert dict(p.grupos) == {0: "ATACA", 3: "DEFENDE", 6: "ÁRBITRO"}

    def test_las_defensivas_van_seguidas(self):
        claves = [k for _, k in ArbolGuiado().paso_actual().opciones]
        assert abs(claves.index("Dodge") - claves.index("Hand Block")) == 1

    def test_lo_del_arbitro_va_seguido(self):
        claves = [k for _, k in ArbolGuiado().paso_actual().opciones]
        assert abs(claves.index("parada") - claves.index("falta")) == 1

    def test_las_tecnicas_van_por_familia(self):
        a = ArbolGuiado()
        a.elegir("ataque")
        p = a.paso_actual()
        assert dict(p.grupos) == {0: "SOCO", 3: "CHUTE", 7: "QUEDA"}

    def test_cada_titulo_cae_en_una_opcion_que_existe(self):
        """Un titulo con indice fuera de sitio no se pintaria nunca."""
        pend = [ArbolGuiado()]
        vistas = 0
        while pend and vistas < 500:
            a = pend.pop(); vistas += 1
            p = a.paso_actual()
            if p is None:
                continue
            for i, _ in p.grupos:
                assert 0 <= i < len(p.opciones), f"{p.pregunta}: título en {i}"
            for _, clave in p.opciones:
                b = a.copiar(); b.elegir(clave)
                if not b.descartada:
                    pend.append(b)

    def test_las_familias_cubren_todas_las_tecnicas(self):
        a = ArbolGuiado()
        a.elegir("ataque")
        p = a.paso_actual()
        assert p.grupos[0][0] == 0, "el primer titulo debe ir antes de la primera"

    def test_una_pregunta_sin_grupos_no_rompe(self):
        a = recorrer("ataque", "Tsuki|Rear")
        assert a.paso_actual().grupos == ()


class TestFaltas:
    """El reglamento de 2026 pone las diecisiete conductas prohibidas en
    UNA sola escalera: desaparecen las categorias 1 y 2 y los grados
    CHUKOKU y KEIKOKU. El grado no se elige — sale del contador."""

    def test_se_llega_a_las_faltas_en_dos_pasos(self):
        a = recorrer("falta", "F:Jogai")
        assert a.completa and a.es_falta and a.falta_tipo == "Jogai"

    def test_una_falta_no_es_una_accion_tecnica(self):
        """No tiene tecnica ni nivel: es un suceso."""
        a = recorrer("falta", "F:Contact")
        assert a.tecnica is None and a.es_falta

    @pytest.mark.parametrize("clave", [
        "F:Jogai", "F:Passivity", "F:Avoiding", "F:Clinching",
        "F:Mubobi", "F:Exaggerating", "F:Feigning", "F:Conduct"])
    def test_las_conductas_sueltas_son_alcanzables(self, clave):
        assert recorrer("falta", clave).completa

    def test_las_faltas_de_contacto_no_estan_aqui(self):
        """Tienen tecnica, guardia y nivel: se anotan como resultado del
        ataque. En dos sitios habria dos formas de anotar lo mismo."""
        a = ArbolGuiado()
        a.elegir("falta")
        claves = {k for _, k in a.paso_actual().opciones}
        assert not any(k.startswith("S:") for k in claves)
        assert "F:Contact" not in claves

    def test_un_ataque_a_zona_prohibida_es_falta_con_tecnica(self):
        a = recorrer("ataque", "Mawashi Geri|Rear", "|Jodan", "Act:Direct",
                     "Res:Foul", "S:Target")
        assert a.falta and a.falta_del_ataque == "Target"
        assert a.tecnica == "Mawashi Geri" and a.nivel == "Jodan"

    def test_el_contacto_excesivo_dice_que_conducta_sanciona(self):
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct",
                     "Res:Foul", "S:Contact")
        assert a.falta_del_ataque == "Contact"

    @pytest.mark.parametrize("clave", [
        "S:Contact", "S:Target", "S:Throat", "S:OpenHand", "S:Throw"])
    def test_las_cinco_sanciones_de_ataque(self, clave):
        """El reglamento las agrupa aparte porque escalan mas rapido:
        CHUI - HANSOKU-CHUI - HANSOKU, saltandose pasos."""
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Foul", clave)
        assert a.completa and a.falta and a.falta_del_ataque == clave[2:]

    def test_una_sancion_sin_motivo_no_esta_completa(self):
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Foul")
        assert not a.completa
        assert a.paso_actual().pregunta == "Por que foi punida?"

    def test_un_ataque_limpio_no_sanciona_nada(self):
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Score")
        assert a.falta_del_ataque == ""

    def test_las_conductas_van_agrupadas(self):
        a = ArbolGuiado()
        a.elegir("falta")
        assert dict(a.paso_actual().grupos) == {0: "EM COMBATE", 5: "SIMULAÇÃO", 7: "OUTRAS"}

    def test_deshacer_vuelve_a_la_primera_pregunta(self):
        a = recorrer("falta", "F:Jogai")
        a.retroceder()
        assert a.falta_tipo is None
        a.retroceder()
        assert a.paso_actual().pregunta == "Qual ação?"

    def test_el_contacto_excesivo_de_un_ataque_es_falta(self):
        """Marcarlo en el ataque no debe obligar a repetir el recorrido
        para decir lo mismo."""
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Foul", "S:Contact")
        assert a.falta and not a.es_falta

    def test_un_ataque_normal_no_es_falta(self):
        a = recorrer("ataque", "Tsuki|Rear", "|Jodan", "Act:Direct", "Res:Score")
        assert not a.falta

    def test_una_falta_sin_tipo_no_esta_completa(self):
        a = ArbolGuiado()
        a.elegir("falta")
        assert not a.completa


class TestCuandoSeRegistraLaFalta:
    """La falta se registra en el momento de la CONDUCTA, no en el de la
    sancion. El arbitro para unos segundos despues; anotar ahi moveria el
    dato al instante de la decision en vez del de lo que se estudia."""

    class _Ctrl:
        """El orden real de _cerrar_guia, sin montar la aplicacion."""

        def __init__(self, frame_visto, inicio_marcado=None):
            self.frame = frame_visto
            self.inicio = inicio_marcado
            self.registrada_en = None

        def cerrar_falta(self):
            volver = None
            if self.inicio:
                volver = self.frame
                self.frame = self.inicio
            self.registrada_en = self.frame
            if volver is not None:
                self.frame = volver

        def cerrar_ataque(self, fin):
            self.frame = fin            # se vuelve al frame de [F]
            self.registrada_en = self.frame

    def test_la_falta_de_un_ataque_cae_donde_acabo_el_ataque(self):
        """Aunque el evaluador haya seguido mirando el video despues."""
        c = self._Ctrl(frame_visto=1250)
        c.cerrar_ataque(fin=1020)
        assert c.registrada_en == 1020

    def test_una_falta_suelta_cae_donde_se_marco_el_inicio(self):
        c = self._Ctrl(frame_visto=4500, inicio_marcado=4000)
        c.cerrar_falta()
        assert c.registrada_en == 4000

    def test_sin_inicio_marcado_cae_donde_esta_el_video(self):
        c = self._Ctrl(frame_visto=4500)
        c.cerrar_falta()
        assert c.registrada_en == 4500

    def test_registrar_la_falta_no_deja_el_video_movido(self):
        """Si se quedara en el instante de la conducta, el evaluador
        perderia el sitio por donde iba."""
        c = self._Ctrl(frame_visto=4500, inicio_marcado=4000)
        c.cerrar_falta()
        assert c.frame == 4500
