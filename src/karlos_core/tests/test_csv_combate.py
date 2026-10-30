"""Tests del archivo de combate: un solo CSV que se vuelve a leer.

La propiedad que importa no es que escriba bonito, es que lo escrito se
pueda **volver a cargar y seguir editando**. Por eso casi todos estos
tests son de ida y vuelta: se escribe, se lee y se compara.
"""

from __future__ import annotations

import csv

import pytest

from karlos_karate import csv_combate
from karlos_core.models.annotation import Annotation


def _accion(**kw):
    base = dict(athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
                technique="Gyaku Tsuki", level="Chudan", f_start=219, f_end=279,
                sport_specific_data={"base_technique": "Tsuki", "stance": "Rear",
                                     "action_type": "Direct",
                                     "sequence_id": "SEQ_001"})
    base.update(kw)
    return Annotation(**base)


BOUT = {"competition_name": "WKF Paris 2025", "category_type": "Male Kumite",
        "weight_category": "-75 kg", "athlete_a_name": "H. ASSEMAT",
        "athlete_a_country": "FRA", "athlete_b_name": "T. DUARTE",
        "athlete_b_country": "POR"}


class TestIdaYVuelta:
    def test_lo_escrito_se_vuelve_a_leer(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion()], bout_info=BOUT,
                             video="/v/ID30.mp4", fps=29.97)
        cab, acc = csv_combate.leer(r)
        assert len(acc) == 1
        a = acc[0]
        assert (a.athlete, a.category, a.technique, a.level) == \
               ("AKA", "ATTACK", "Gyaku Tsuki", "Chudan")
        assert (a.f_start, a.f_end) == (219, 279)
        assert a.sport_specific_data["stance"] == "Rear"
        # `sequence_id` ya no se escribe: el archivo no agrupa nada.
        assert "sequence_id" not in a.sport_specific_data

    def test_conserva_el_orden_cronologico(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion(f_start=900, f_end=950),
                                 _accion(f_start=100, f_end=150),
                                 _accion(f_start=500, f_end=560)], fps=30)
        _cab, acc = csv_combate.leer(r)
        assert [a.f_start for a in acc] == [100, 500, 900]

    def test_sin_acciones_se_escribe_igual(self, tmp_path):
        """Un combate sin anotar tambien es un estado valido."""
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [], bout_info=BOUT, video="/v/ID30.mp4")
        cab, acc = csv_combate.leer(r)
        assert acc == []
        assert cab["video"] == "ID30.mp4"

    def test_un_texto_con_comas_no_parte_la_fila(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion(notes="rapido, limpio, al cuerpo")],
                             fps=30)
        _cab, acc = csv_combate.leer(r)
        assert acc[0].notes == "rapido, limpio, al cuerpo"


class TestLaCabecera:
    def test_lleva_el_video_y_los_atletas(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion()], bout_info=BOUT,
                             video="/carpeta/ID30.mp4", fps=29.97)
        cab, _ = csv_combate.leer(r)
        assert cab["video"] == "ID30.mp4"
        assert cab["aka"] == "H. ASSEMAT (FRA)"
        assert cab["ao"] == "T. DUARTE (POR)"
        assert cab["competition"] == "WKF Paris 2025"

    def test_los_campos_vacios_no_ocupan_linea(self, tmp_path):
        """El motivo de todo esto: no escribir lo que no hay."""
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion()], bout_info={"competition_name": "X"})
        cab, _ = csv_combate.leer(r)
        assert "pool" not in cab and "tatami" not in cab and "phase" not in cab

    def test_nada_constante_se_repite_en_la_tabla(self, tmp_path):
        """Ni el evento ni los nombres ni el video bajan a las filas."""
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion(), _accion(f_start=400, f_end=430)],
                             bout_info=BOUT, video="/v/ID30.mp4")
        cuerpo = [l for l in r.read_text(encoding="utf-8").splitlines()
                  if not l.startswith("#")]
        for prohibido in ("WKF Paris 2025", "ASSEMAT", "DUARTE", "ID30.mp4",
                          "-75 kg"):
            assert all(prohibido not in l for l in cuerpo), prohibido


class TestSigueSiendoUnCsvNormal:
    def test_pandas_y_R_lo_leen_saltando_las_almohadillas(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion()], bout_info=BOUT, fps=30)
        cuerpo = [l for l in r.read_text(encoding="utf-8").splitlines()
                  if not l.startswith("#")]
        filas = list(csv.DictReader(cuerpo))
        assert list(filas[0]) == csv_combate.COLUMNAS
        assert filas[0]["action"] == "Gyaku Tsuki"

    def test_la_cabecera_va_toda_arriba(self, tmp_path):
        """Si se colara una '#' en medio, pandas la leeria como dato."""
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion()], bout_info=BOUT)
        lineas = r.read_text(encoding="utf-8").splitlines()
        primera_tabla = next(i for i, l in enumerate(lineas)
                             if not l.startswith("#"))
        assert all(not l.startswith("#") for l in lineas[primera_tabla:])


class TestAguantaLoRoto:
    def test_una_fila_ilegible_no_tumba_la_carga(self, tmp_path):
        """Media sesion recuperada vale mas que un error."""
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion(), _accion(f_start=400, f_end=430)],
                             fps=30)
        lineas = r.read_text(encoding="utf-8").splitlines()
        lineas.insert(-1, "2,x,no_es_un_numero,,AKA,ATTACK,,,,,,,,")
        r.write_text("\n".join(lineas), encoding="utf-8")
        _cab, acc = csv_combate.leer(r)
        assert len(acc) == 2

    def test_un_csv_sin_cabecera_se_lee_igual(self, tmp_path):
        r = tmp_path / "c.csv"
        r.write_text("n,t_s,f_start,f_end,athlete,category,group,action,"
                     "level,stance,context,result,seq,notes\n"
                     "1,7.3,219,279,AKA,ATTACK,,Gyaku Tsuki,Chudan,,,,,\n",
                     encoding="utf-8")
        cab, acc = csv_combate.leer(r)
        assert cab == {} and len(acc) == 1


class TestEncontrarElVideo:
    def test_lo_encuentra_al_lado(self, tmp_path):
        (tmp_path / "ID30.mp4").write_bytes(b"x")
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion()], video=str(tmp_path / "ID30.mp4"))
        cab, _ = csv_combate.leer(r)
        assert csv_combate.buscar_video(r, cab) == str(tmp_path / "ID30.mp4")

    def test_lo_encuentra_una_carpeta_mas_arriba(self, tmp_path):
        (tmp_path / "ID30.mp4").write_bytes(b"x")
        informes = tmp_path / "informes"
        informes.mkdir()
        r = informes / "c.csv"
        csv_combate.escribir(r, [_accion()], video="ID30.mp4")
        cab, _ = csv_combate.leer(r)
        assert csv_combate.buscar_video(r, cab) == str(tmp_path / "ID30.mp4")

    def test_si_no_esta_lo_dice_en_vez_de_inventar(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion()], video="NO_EXISTE.mp4")
        cab, _ = csv_combate.leer(r)
        assert csv_combate.buscar_video(r, cab) == ""


class TestGrupoSinRepetir:
    def test_no_se_escribe_si_es_igual_a_la_categoria(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion(category="TACTICS",
                                         subcategory="TACTICS",
                                         technique="Feint")], fps=30)
        cuerpo = [l for l in r.read_text(encoding="utf-8").splitlines()
                  if not l.startswith("#")]
        assert cuerpo[1].count("TACTICS") == 1

    def test_al_leerlo_vuelve_a_estar(self, tmp_path):
        """Vacio significa 'el mismo que category', no 'no hay'."""
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion(category="TACTICS",
                                         subcategory="TACTICS")], fps=30)
        _cab, acc = csv_combate.leer(r)
        assert acc[0].subcategory == "TACTICS"

    def test_cuando_dice_algo_distinto_se_conserva(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion(category="ATTACK",
                                         subcategory="HAND TECHNIQUES")], fps=30)
        _cab, acc = csv_combate.leer(r)
        assert acc[0].subcategory == "HAND TECHNIQUES"


class TestNoSePierdeNadaEnElCamino:
    """El test que faltaba.

    El primero comparaba unos cuantos campos elegidos a mano, asi que
    pasaba mientras el CSV se dejaba fuera el score, el contacto, la
    zona y el follow-up. Este compara TODO lo que distingue una accion
    de otra: si manana se añade un campo al arbol y no a la tabla, este
    test falla y nadie exporta trabajo a medias sin enterarse.
    """

    # Lo que NO tiene que sobrevivir, y por que.
    DERIVABLES = {
        "duration_s",        # f_end - f_start
        "base_technique",    # sale del nombre de la tecnica
        "timestamp",         # cuando se anoto, no que se anoto
        "status", "features",
        # constantes del combate: viven en la cabecera, no en la fila
        "fight_f_start", "fight_f_end", "fight_dur_s", "active_play_s",
        "video_file", "bout_id", "bout_event", "bout_number", "bout_round",
        "athlete_a_name", "athlete_a_origin", "athlete_b_name",
        "athlete_b_origin", "weight_category",
    }

    # Lo que se dejo de llevar a proposito, y por que.
    #
    # El arbol de PRO no pregunta ni la zona ni el encadenamiento, y
    # nada mas los escribe, asi que salian vacios en TODAS las filas.
    # Una columna siempre vacia en un dataset no se lee como "no
    # aplica" sino como "aqui falta un dato". Y ademas sobran: en
    # karate la zona ES el nivel —jodan la cabeza, chudan el tronco.
    RETIRADOS = {"target", "follow_up"}

    def _completa(self):
        return Annotation(
            athlete="AO", category="ATTACK", subcategory="FOOT TECHNIQUES",
            technique="Mawashi Geri", level="Jodan", score="WAZA-ARI",
            f_start=1022, f_end=1041, round=2,
            notes="entro limpio por encima del brazo",
            sport_specific_data={
                "base_technique": "Mawashi Geri", "stance": "Rear",
                "target": "Jodan", "action_type": "Counter",
                "contact": "Score", "follow_up": "Gyaku Tsuki",
                "sanction": "Contact", "follow_up": "Gyaku Tsuki"})

    def test_sobrevive_cada_campo_de_la_anotacion(self, tmp_path):
        r = tmp_path / "c.csv"
        original = self._completa()
        csv_combate.escribir(r, [original], bout_info=BOUT, fps=29.97,
                             video="/v/ID30.mp4")
        _cab, (vuelta,) = csv_combate.leer(r)
        perdidos = []
        for campo, esperado in vars(original).items():
            if campo in self.DERIVABLES or campo == "sport_specific_data":
                continue
            if getattr(vuelta, campo) != esperado:
                perdidos.append(f"{campo}: {esperado!r} -> "
                                f"{getattr(vuelta, campo)!r}")
        assert not perdidos, "campos perdidos en la ida y vuelta:\n  " + \
                             "\n  ".join(perdidos)

    def test_sobrevive_cada_clave_de_sport_specific_data(self, tmp_path):
        r = tmp_path / "c.csv"
        original = self._completa()
        csv_combate.escribir(r, [original], fps=29.97)
        _cab, (vuelta,) = csv_combate.leer(r)
        perdidos = [f"{k}={v!r}"
                    for k, v in original.sport_specific_data.items()
                    if k not in self.DERIVABLES and k not in self.RETIRADOS
                    and vuelta.sport_specific_data.get(k) != v]
        assert not perdidos, "claves perdidas: " + ", ".join(perdidos)

    def test_las_columnas_retiradas_no_estan_ni_vacias(self, tmp_path):
        """Se quitaron: no basta con que salgan en blanco."""
        import csv as _csv
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [self._completa()], fps=29.97)
        cabeceras = next(_csv.reader(
            [l for l in open(r, encoding="utf-8") if not l.startswith("#")]))
        for col in self.RETIRADOS:
            assert col not in cabeceras, f"{col} sigue en el CSV"

    def test_un_csv_antiguo_con_esas_columnas_se_sigue_leyendo(self, tmp_path):
        """Los exportados de antes no pueden dejar de abrirse."""
        r = tmp_path / "viejo.csv"
        r.write_text(
            "# karlos csv v2\n# fps: 30\n"
            "n,t_s,f_start,f_end,athlete,category,group,action,level,"
            "stance,target,context,outcome,follow_up,sanction,score,notes\n"
            "1,1.0,30,45,AKA,ATTACK,HAND TECHNIQUES,Gyaku Tsuki,Jodan,"
            "Rear,Jodan,Direct,Score,Kizami,,YUKO,\n", encoding="utf-8")
        _cab, anns = csv_combate.leer(r)
        assert len(anns) == 1
        a = anns[0]
        assert a.technique == "Gyaku Tsuki" and a.score == "YUKO"
        assert a.sport_specific_data.get("stance") == "Rear"

    def test_el_score_llega(self, tmp_path):
        """El resultado de la accion, que es de lo que va el karate."""
        r = tmp_path / "c.csv"
        for marca in ("YUKO", "WAZA-ARI", "IPPON", "NONE", ""):
            csv_combate.escribir(r, [_accion(score=marca)], fps=30)
            _cab, (v,) = csv_combate.leer(r)
            assert v.score == marca, marca

    def test_el_dictamen_del_arbitro_llega(self, tmp_path):
        """Lo que decide si una accion puntuo: la decision arbitral."""
        r = tmp_path / "c.csv"
        for contacto in ("NoScore", "Score", "Foul"):
            csv_combate.escribir(r, [_accion(
                sport_specific_data={"contact": contacto})], fps=30)
            _cab, (v,) = csv_combate.leer(r)
            assert v.sport_specific_data.get("contact") == contacto

    def test_toda_columna_de_la_tabla_se_vuelve_a_leer(self, tmp_path):
        """Una columna que se escribe y nadie lee es peor que no tenerla.

        Se comprueba sobre un combate con las tres clases de accion, no
        sobre una fila: hay columnas que solo aplican a una clase — el
        contexto y el resultado al ataque, el motivo a lo no
        identificable — y exigirlas en todas obligaria a relajar el
        test hasta que dejara de servir.
        """
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [
            self._completa(),
            _accion(athlete="AKA", category="DEFENSE",
                    subcategory="BLOCKS & EVASIONS", technique="Dodge",
                    level="", f_start=1030, f_end=1040,
                    sport_specific_data={"sequence_id": "SEQ_043"}),
            _accion(athlete="AKA", category="ATTACK", f_start=1050,
                    f_end=1060, score="YUKO",
                    sport_specific_data={"sequence_id": "SEQ_044"}),
            # Lo que se ve pasar pero no se deja leer: el motivo es la
            # columna que lo hace contable en vez de un agujero.
            _accion(athlete="AO", category="UNIDENTIFIED",
                    subcategory="UNIDENTIFIED", technique="Unidentifiable",
                    level="Reason: Occluded", f_start=1070, f_end=1080,
                    sport_specific_data={"reason": "Occluded",
                                         "sequence_id": "SEQ_045"}),
        ], bout_info=BOUT, fps=29.97, video="/v/ID30.mp4")
        cuerpo = [l for l in r.read_text(encoding="utf-8").splitlines()
                  if not l.startswith("#")]
        filas = list(csv.DictReader(cuerpo))
        nunca = [c for c in csv_combate.COLUMNAS
                 if c != "notes" and not any(f[c] for f in filas)]
        assert not nunca, f"columnas que no se llenaron nunca: {nunca}"


class TestElRelojNoRetrocede:
    """El juego efectivo tiene que crecer siempre. Es un reloj.

    Encontrado en la sesión real de ID30: AKA tenía dos filas de parada
    solapadas (f8177-8676 y f8218-8715, IoU 0,85) y el tramo común se
    restaba dos veces, así que su reloj caía de 134,7 s a 121,7 s de una
    acción a la siguiente, arrastrando también la fase del combate.
    """

    def _pausa(self, athlete, f0, f1):
        return _accion(athlete=athlete, category="REFEREE STOP",
                       subcategory="MATCH STATES", technique="Referee",
                       level="", f_start=f0, f_end=f1)

    def test_dos_paradas_solapadas_no_restan_dos_veces(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [
            _accion(athlete="AKA", f_start=100, f_end=110),
            self._pausa("AKA", 200, 800),
            self._pausa("AKA", 250, 850),          # la misma, mal anotada
            _accion(athlete="AKA", f_start=900, f_end=910),
        ], fps=30.0, fight_start=0)
        filas = [f for f in csv.DictReader(
            [l for l in r.read_text(encoding="utf-8").splitlines()
             if not l.startswith("#")]) if f["athlete"] == "AKA"]
        v = [float(f["active_s"]) for f in filas]
        assert v == sorted(v), f"el reloj retrocedió: {v}"
        # 900 frames menos los 650 parados (200-850 fundidos) = 250
        assert float(filas[-1]["active_s"]) == pytest.approx(250 / 30.0, abs=0.05)

    def test_fundir_une_lo_que_se_pisa_y_deja_lo_separado(self):
        assert csv_combate._fundir([(0, 10), (5, 20)]) == [(0, 20)]
        assert csv_combate._fundir([(0, 10), (10, 20)]) == [(0, 20)]
        assert csv_combate._fundir([(0, 10), (30, 40)]) == [(0, 10), (30, 40)]
        assert csv_combate._fundir([(30, 40), (0, 10)]) == [(0, 10), (30, 40)]
        assert csv_combate._fundir([]) == []


class TestLaFaseSeRecomprueba:
    """Quien lea el archivo tiene que poder recalcular la fase con él.

    `active_s` se publicaba con una décima, más basta que un fotograma
    (0,033 s a 30 fps). En ID30 una acción caía en 59,96 s, salía como
    60,0 y la fase recalculada desde la columna decía Minute_2 donde el
    programa había escrito Minute_1.
    """

    def test_la_fase_sale_de_la_columna_publicada(self, tmp_path):
        r = tmp_path / "c.csv"
        # 1798 frames a 30 fps son 59,93 s: justo antes del minuto.
        csv_combate.escribir(r, [_accion(athlete="AKA", f_start=1798,
                                         f_end=1808)],
                             fps=30.0, fight_start=0)
        f = list(csv.DictReader(
            [l for l in r.read_text(encoding="utf-8").splitlines()
             if not l.startswith("#")]))[0]
        a = float(f["active_s"])
        assert f["phase"] == f"Minute_{int(a // 60) + 1}"

    def test_dos_decimales_distinguen_fotogramas(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [_accion(athlete="AKA", f_start=31, f_end=41)],
                             fps=30.0, fight_start=0)
        f = list(csv.DictReader(
            [l for l in r.read_text(encoding="utf-8").splitlines()
             if not l.startswith("#")]))[0]
        assert float(f["active_s"]) == pytest.approx(31 / 30.0, abs=0.005)


class TestElRelojDelCombate:
    """El juego efectivo y el minuto en que cae cada accion.

    El informe antiguo los traia mal: 16 filas de ID30 se quedaban
    congeladas en 47,4 s mientras el video avanzaba cuarenta segundos,
    66 de 228 atrapadas en valores repetidos, y el maximo llegaba a
    192,6 s en un combate que dura 180. Sus diez 'Atoshibaraku' eran ese
    desbordamiento. Estos tests fijan lo que tiene que cumplirse.
    """

    def _combate(self):
        """Dos minutos de video con una pausa de 30 s en medio."""
        acciones = []
        for f in (300, 600, 900):
            acciones.append(_accion(athlete="AKA", f_start=f, f_end=f + 20))
        for atleta in ("AKA", "AO"):
            acciones.append(_accion(athlete=atleta, category="REFEREE STOP",
                                    subcategory="REFEREE STOP",
                                    technique="Referee",
                                    f_start=1200, f_end=2100))
        for f in (2400, 2700):
            acciones.append(_accion(athlete="AKA", f_start=f, f_end=f + 20))
        return acciones

    def _leer(self, tmp_path, acciones, fps=30.0, inicio=0):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, acciones, fps=fps, fight_start=inicio,
                             fight_end=3000)
        cuerpo = [l for l in r.read_text(encoding="utf-8").splitlines()
                  if not l.startswith("#")]
        return list(csv.DictReader(cuerpo))

    def test_la_pausa_se_descuenta(self, tmp_path):
        filas = self._leer(tmp_path, self._combate())
        por_frame = {int(f["f_start"]): float(f["active_s"]) for f in filas}
        # f2400 son 80 s de video menos los 30 s de pausa
        assert por_frame[2400] == pytest.approx(50.0, abs=0.1)

    def test_el_reloj_nunca_retrocede(self, tmp_path):
        """Lo que le pasaba al informe antiguo."""
        filas = self._leer(tmp_path, self._combate())
        for atleta in ("AKA", "AO"):
            v = [float(f["active_s"]) for f in filas if f["athlete"] == atleta]
            assert all(b >= a for a, b in zip(v, v[1:])), f"{atleta}: {v}"

    def test_una_accion_dentro_de_la_pausa_no_hace_retroceder(self, tmp_path):
        """El caso exacto que rompia la monotonia: solo se descuenta la
        parte de la pausa ya transcurrida, no la pausa entera."""
        acciones = self._combate()
        acciones.append(_accion(athlete="AKA", f_start=1500, f_end=1520))
        filas = self._leer(tmp_path, acciones)
        v = [float(f["active_s"]) for f in filas if f["athlete"] == "AKA"]
        assert all(b >= a for a, b in zip(v, v[1:])), v

    def test_la_pausa_de_uno_no_para_el_reloj_del_otro(self, tmp_path):
        acciones = [_accion(athlete="AKA", category="REFEREE STOP",
                            subcategory="REFEREE STOP", technique="Referee",
                            f_start=300, f_end=1200),
                    _accion(athlete="AO", f_start=1500, f_end=1520)]
        filas = self._leer(tmp_path, acciones)
        ao = next(f for f in filas if f["athlete"] == "AO")
        assert float(ao["active_s"]) == pytest.approx(50.0, abs=0.1)

    def test_el_minuto_sale_del_juego_efectivo_no_del_video(self, tmp_path):
        """Una accion a los 80 s de video pero 50 de combate es Minute_1."""
        filas = self._leer(tmp_path, self._combate())
        f2400 = next(f for f in filas if f["f_start"] == "2400")
        assert f2400["phase"] == "Minute_1"

    def test_pasados_los_tres_minutos_es_atoshibaraku(self, tmp_path):
        acciones = [_accion(athlete="AKA", f_start=6000, f_end=6020)]
        filas = self._leer(tmp_path, acciones)
        assert filas[0]["phase"] == "Atoshibaraku"

    def test_los_minutos_van_en_orden(self, tmp_path):
        acciones = [_accion(athlete="AKA", f_start=f, f_end=f + 10)
                    for f in (30, 1830, 3630, 5430)]
        filas = self._leer(tmp_path, acciones)
        assert [f["phase"] for f in filas] == [
            "Minute_1", "Minute_2", "Minute_3", "Atoshibaraku"]


class TestElOrdenEsDeterminista:
    def test_dos_acciones_en_el_mismo_frame_salen_por_orden_de_llegada(self, tmp_path):
        """Se ordenaba por número de secuencia; ya no hay ninguno.

        El orden queda por inicio y fin, y entre iguales por el orden en
        que llegaron. Lo que importa es que sea estable: comparar dos
        exportaciones de lo mismo tiene que dar el mismo archivo.
        """
        r = tmp_path / "c.csv"
        a = _accion(f_start=500, f_end=520, technique="Gyaku Tsuki")
        b = _accion(f_start=500, f_end=520, technique="Kizami Tsuki")
        csv_combate.escribir(r, [a, b], fps=30)
        cuerpo = [l for l in r.read_text(encoding="utf-8").splitlines()
                  if not l.startswith("#")]
        assert [f["action"] for f in csv.DictReader(cuerpo)] == \
            ["Gyaku Tsuki", "Kizami Tsuki"]
        assert "seq" not in csv.DictReader(cuerpo).fieldnames

    def test_el_mismo_contenido_da_el_mismo_archivo(self, tmp_path):
        """Dos exportaciones de lo mismo tienen que ser byte a byte
        iguales, o comparar dos versiones es imposible."""
        acciones = [_accion(f_start=f, f_end=f + 20,
                            sport_specific_data={"sequence_id": f"SEQ_{i:03d}"})
                    for i, f in enumerate((900, 100, 500, 100), 1)]
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        csv_combate.escribir(a, acciones, fps=30)
        csv_combate.escribir(b, list(reversed(acciones)), fps=30)
        assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")


class TestElMarcador:
    """Como iba el combate en el momento de cada accion.

    Es contexto tactico que no hay que anotar: sale de las acciones que
    puntuaron. Sin el no se distingue una decision de un habito.
    """

    def _puntos(self, tmp_path, acciones):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, acciones, fps=30)
        cuerpo = [l for l in r.read_text(encoding="utf-8").splitlines()
                  if not l.startswith("#")]
        return list(csv.DictReader(cuerpo))

    def test_empieza_a_cero(self, tmp_path):
        f = self._puntos(tmp_path, [_accion(f_start=100, f_end=120)])[0]
        assert (f["pts_aka"], f["pts_ao"]) == ("0", "0")

    def test_suma_segun_el_valor_wkf(self, tmp_path):
        """YUKO 1, WAZA-ARI 2, IPPON 3."""
        filas = self._puntos(tmp_path, [
            _accion(athlete="AKA", f_start=100, f_end=120, score="YUKO"),
            _accion(athlete="AKA", f_start=200, f_end=220, score="WAZA"),
            _accion(athlete="AKA", f_start=300, f_end=320, score="IPPON"),
            _accion(athlete="AKA", f_start=400, f_end=420)])
        assert [f["pts_aka"] for f in filas] == ["0", "1", "3", "6"]

    def test_el_punto_no_se_cuenta_en_su_propia_fila(self, tmp_path):
        """Si se contara, un modelo sabria el resultado antes de predecirlo."""
        filas = self._puntos(tmp_path, [
            _accion(athlete="AKA", f_start=100, f_end=120, score="YUKO"),
            _accion(athlete="AO", f_start=200, f_end=220)])
        assert filas[0]["pts_aka"] == "0"
        assert filas[1]["pts_aka"] == "1"

    def test_cada_atleta_lleva_su_cuenta(self, tmp_path):
        filas = self._puntos(tmp_path, [
            _accion(athlete="AO", f_start=100, f_end=120, score="WAZA"),
            _accion(athlete="AKA", f_start=200, f_end=220)])
        assert (filas[1]["pts_aka"], filas[1]["pts_ao"]) == ("0", "2")

    def test_la_ventaja_es_del_que_hace_la_accion(self, tmp_path):
        """AKA ganando 2-0: para AKA la ventaja es +2 y para AO es -2."""
        filas = self._puntos(tmp_path, [
            _accion(athlete="AKA", f_start=100, f_end=120, score="WAZA"),
            _accion(athlete="AKA", f_start=200, f_end=220),
            _accion(athlete="AO", f_start=300, f_end=320)])
        assert filas[1]["lead"] == "2"
        assert filas[2]["lead"] == "-2"

    def test_una_accion_sin_puntuar_no_mueve_nada(self, tmp_path):
        filas = self._puntos(tmp_path, [
            _accion(athlete="AKA", f_start=100, f_end=120, score="NONE"),
            _accion(athlete="AKA", f_start=200, f_end=220, score=""),
            _accion(athlete="AKA", f_start=300, f_end=320)])
        assert [f["pts_aka"] for f in filas] == ["0", "0", "0"]


class TestLasSanciones:
    """Cuantas lleva encima cada atleta antes de cada accion.

    El reglamento 2026 encadena CHUI-1, CHUI-2, CHUI-3, HANSOKU-CHUI y
    HANSOKU: a un atleta en CHUI-3 la siguiente le cuesta el combate, y
    eso cambia lo que se atreve a hacer. El nombre de la sancion esta en
    la fila; cuantas lleva, no.
    """

    def _falta(self, **kw):
        base = dict(category="PENALTY", subcategory="Procedure",
                    technique="Chui (1st)", level="")
        base.update(kw)
        return _accion(**base)

    def _leer(self, tmp_path, acciones):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, acciones, fps=30)
        cuerpo = [l for l in r.read_text(encoding="utf-8").splitlines()
                  if not l.startswith("#")]
        return list(csv.DictReader(cuerpo))

    def test_empieza_a_cero(self, tmp_path):
        f = self._leer(tmp_path, [_accion(f_start=100, f_end=120)])[0]
        assert (f["pen_aka"], f["pen_ao"]) == ("0", "0")

    def test_van_sumando(self, tmp_path):
        filas = self._leer(tmp_path, [
            self._falta(athlete="AKA", f_start=100, f_end=100),
            _accion(athlete="AKA", f_start=200, f_end=220),
            self._falta(athlete="AKA", f_start=300, f_end=300,
                        technique="Chui (2nd)"),
            _accion(athlete="AKA", f_start=400, f_end=420)])
        assert [f["pen_aka"] for f in filas] == ["0", "1", "1", "2"]

    def test_la_sancion_no_se_cuenta_en_su_propia_fila(self, tmp_path):
        filas = self._leer(tmp_path, [
            self._falta(athlete="AO", f_start=100, f_end=100),
            _accion(athlete="AKA", f_start=200, f_end=220)])
        assert filas[0]["pen_ao"] == "0"
        assert filas[1]["pen_ao"] == "1"

    def test_cada_atleta_lleva_la_suya(self, tmp_path):
        filas = self._leer(tmp_path, [
            self._falta(athlete="AO", f_start=100, f_end=100),
            _accion(athlete="AKA", f_start=200, f_end=220)])
        assert (filas[1]["pen_aka"], filas[1]["pen_ao"]) == ("0", "1")

    def test_una_accion_normal_no_suma(self, tmp_path):
        filas = self._leer(tmp_path, [
            _accion(athlete="AKA", f_start=100, f_end=120),
            _accion(athlete="AKA", f_start=200, f_end=220)])
        assert [f["pen_aka"] for f in filas] == ["0", "0"]


class TestLaSancionVaConElAtaque:
    """Un ataque sancionado es UNA accion, no dos.

    Se guardaba dos veces —la tecnica y la sancion en el mismo frame— y
    como la sancion ordenaba primero, el propio ataque salia con la
    falta que el mismo habia provocado ya contada encima.
    """

    def _leer(self, tmp_path, acciones):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, acciones, fps=30)
        cuerpo = [l for l in r.read_text(encoding="utf-8").splitlines()
                  if not l.startswith("#")]
        return list(csv.DictReader(cuerpo))

    def _sancionado(self, **kw):
        base = dict(sport_specific_data={"sanction": "Contact",
                                         "contact": "Excessive"})
        base.update(kw)
        return _accion(**base)

    def test_el_ataque_no_se_cuenta_su_propia_falta(self, tmp_path):
        filas = self._leer(tmp_path, [
            self._sancionado(athlete="AKA", f_start=100, f_end=120),
            _accion(athlete="AKA", f_start=300, f_end=320)])
        assert filas[0]["pen_aka"] == "0", "se cuenta a si mismo"
        assert filas[1]["pen_aka"] == "1", "no se cuenta despues"

    def test_el_motivo_queda_en_la_fila(self, tmp_path):
        filas = self._leer(tmp_path, [self._sancionado()])
        assert filas[0]["sanction"] == "Contact"
        assert filas[0]["category"] == "ATTACK", "sigue siendo un ataque"
        assert filas[0]["action"] == "Gyaku Tsuki", "y conserva su tecnica"

    def test_sobrevive_la_ida_y_vuelta(self, tmp_path):
        r = tmp_path / "c.csv"
        csv_combate.escribir(r, [self._sancionado()], fps=30)
        _cab, (v,) = csv_combate.leer(r)
        assert v.sport_specific_data["sanction"] == "Contact"

    def test_una_falta_suelta_sigue_contando(self, tmp_path):
        """Las que no vienen de un ataque no cambian."""
        filas = self._leer(tmp_path, [
            _accion(athlete="AO", category="PENALTY", subcategory="Procedure",
                    technique="Chui (1st)", f_start=100, f_end=100,
                    sport_specific_data={}),
            _accion(athlete="AKA", f_start=300, f_end=320)])
        assert filas[1]["pen_ao"] == "1"

    def test_las_dos_clases_suman_a_la_misma_cuenta(self, tmp_path):
        filas = self._leer(tmp_path, [
            self._sancionado(athlete="AKA", f_start=100, f_end=120),
            _accion(athlete="AKA", category="PENALTY", subcategory="Procedure",
                    technique="Chui (2nd)", f_start=200, f_end=200,
                    sport_specific_data={}),
            _accion(athlete="AKA", f_start=400, f_end=420)])
        assert filas[2]["pen_aka"] == "2"


class TestCargarDejaEnSesion:
    """Cargar un CSV y no guardarlo es peor que no poder cargarlo.

    El evaluador ve sus anotaciones en la tabla, cree que estan a salvo,
    cierra, y las pierde otra vez — que es exactamente el problema que
    la funcion viene a resolver.
    """

    def test_el_controlador_guarda_al_cargar(self):
        """Que guarde, y que guarde DESPUES de poner las anotaciones.

        Mirar el fuente solo vale para esto —el orden de dos llamadas—
        y no para saber si funciona: que los metodos existan y hagan lo
        suyo lo comprueba test_camino_real, ejecutandolos.
        """
        import inspect
        from karlos_core.controllers.annotation_controller import \
            AnnotationController as AC
        cuerpo = inspect.getsource(AC._cargar_csv_combate)
        assert "_save_session" in cuerpo, (
            "cargar un CSV tiene que dejarlo guardado en la sesion")
        assert cuerpo.index("add_annotation") < cuerpo.index("_save_session"), (
            "se guarda despues de poner las anotaciones, no antes")

    def test_tambien_pasa_los_datos_del_combate(self):
        import inspect
        from karlos_core.controllers.annotation_controller import \
            AnnotationController as AC
        cuerpo = inspect.getsource(AC._cargar_csv_combate)
        assert "bout_metadata" in cuerpo
