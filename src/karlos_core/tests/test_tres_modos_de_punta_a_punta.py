"""Los tres modos del karate, de punta a punta, como los usa un evaluador.

Decisión 0008. Johan, 19-10-2026: «verifica uno a uno los modos para que
funcione perfecto, como si estuviera analizando un combate». Cada prueba:

1. elige el análisis donde lo elige el programa (los ajustes que deja la
   pantalla «¿Qué se analiza?») y abre el combate desde el Hub;
2. marca el combate con [F] y [G] y anota con las TECLAS de verdad
   (QTest.keyClick sobre la ventana, nunca llamando al manejador);
3. guarda, vuelve al Hub, reabre, y comprueba que nada se pierde ni se
   duplica;
4. exporta el Excel y comprueba lo que trae ese modo y lo que NO trae.

Corre sobre el vídeo real de ID25, por enlace simbólico en una carpeta
limpia: junto al original viven las sesiones del estudio, y estas pruebas
escriben sesiones. Sin el vídeo, se saltan.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from karlos_core import catalogo
from karlos_core.utils.i18n import I18n

VIDEO = Path(os.environ.get("KARLOS_VIDEOS", "/nonexistent/karlos_videos") + "/"
             "ID25_-50KG_FEMALE_E.COLLETI ITA X B. IZAGUIRRE .mp4")

INICIO, FIN = 1000, 9000          # [F] y [G]: el combate que se analiza


def _pulsar(c, tecla, mod=Qt.NoModifier):
    QTest.keyClick(c.window, tecla, mod)
    QApplication.processEvents()


def _ir(c, frame):
    c.video_manager.goto(frame)
    QApplication.processEvents()


def _filas(c, categoria=None):
    return [r for r in c.window.table_view.records
            if categoria is None or getattr(r, "category", "") == categoria]


def _abrir(c, tmp_path):
    """El combate en el Hub y abierto por el camino de verdad."""
    from karlos_core.models.state import FightSession
    video = tmp_path / VIDEO.name
    if not video.exists():
        video.symlink_to(VIDEO.resolve())
    c.sessions = [FightSession(id=1, video_path=str(video), video_name=video.name,
                               status="Pending", fps=c.video_manager.fps or 29.97)]
    c._on_session_selected(0)
    QApplication.processEvents()
    return video


def _reabrir(c):
    c._save_session(); c._on_back_to_hub(); c._on_session_selected(0)
    QApplication.processEvents()


def _marcar_combate(c):
    _ir(c, INICIO); _pulsar(c, Qt.Key_F)
    _ir(c, FIN); _pulsar(c, Qt.Key_G)
    assert (c.video_manager.fight_start, c.video_manager.fight_end) == (INICIO, FIN)


def _contestar(c, primera):
    """Contesta el árbol con teclas: la primera dice qué fue; las demás
    preguntas (técnica, nivel, contexto, resultado) se contestan con [1]."""
    _pulsar(c, primera)
    for _ in range(8):
        if getattr(c, "_arbol", None) is None:
            break
        _pulsar(c, Qt.Key_1)


def _exportar(c, tmp_path, nombre):
    from openpyxl import load_workbook
    ruta = tmp_path / f"{nombre}.xlsx"
    from karlos_core.utils.merge_utils import migrate_legacy_combined_levels
    migrate_legacy_combined_levels(c.window.table_view.records)
    em = catalogo.activo().salidas().exportador()
    vm = c.video_manager
    em.set_bout_info(dict(c._bout_info)); em.set_analisis(c._analisis_del_combate())
    em.set_records(list(c.window.table_view.records)); em.set_fps(vm.fps)
    em.set_fight_info(fight_start=vm.fight_start, fight_end=vm.fight_end,
                      fight_duration=(vm.fight_end - vm.fight_start) / vm.fps)
    asaltos, fases = c._marcas_del_video(c.sessions[0])
    em.set_tiempo_movimiento(asaltos, fases, 2.0, c._analisis_del_combate() != "technical_tactical")
    em.export_xlsx(output_path=str(ruta))
    return load_workbook(ruta)


def _identidad(wb):
    """Las filas «con qué se hizo» de la hoja Bout Info."""
    return {f[0]: f[1] for f in wb["Bout Info"].iter_rows(values_only=True)
            if f and f[0] in ("Analysis mode", "Program", "Data schema")}


def _texto(hoja):
    return "\n".join(" | ".join("" if v is None else str(v) for v in fila)
                     for fila in hoja.iter_rows(values_only=True))


@pytest.fixture()
def k(monkeypatch, tmp_path):
    """El anotador de Karlos Karate, en asistido, con el análisis que diga
    cada prueba (se pone después, como la pantalla de inicio)."""
    if not VIDEO.exists():
        pytest.skip("sin los vídeos")
    from karlos_core.controllers.annotation_controller import AnnotationController
    from karlos_core.utils.config_loader import load_config
    from karlos_core.utils.i18n import I18n
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **kw: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **kw: None))
    # [G] abre la ventana de fin de combate, que es modal: sin esto la
    # prueba se queda esperando a que alguien la cierre.
    from karlos_core.views.fight_end_popup import FightEndPopup
    monkeypatch.setattr(FightEndPopup, "exec", lambda self: 0)
    from karlos_core.views.bout_info_popup import BoutInfoPopup
    monkeypatch.setattr(BoutInfoPopup, "exec", lambda self: 0)
    QApplication.instance() or QApplication([])
    I18n().set_lang("pt")
    catalogo.establecer("karate")
    cfg, meta = load_config("karate")
    ctl = AnnotationController(cfg, meta)
    ctl.aplicar_modo_inicial()
    ctl.show()
    yield ctl
    ctl.shortcuts.unregister()


def _desde_el_inicio(k, monkeypatch, analisis):
    """«‹ Inicio» y elegir en la pantalla inicial (su diálogo es modal:
    aquí se contesta por él)."""
    from karlos_core.views import dialogo_analisis
    monkeypatch.setattr(dialogo_analisis, "elegir_al_inicio",
                        lambda *a, **kw: analisis)
    k.window.project_hub._btn_inicio.click(); QApplication.processEvents()


def _elegir(k, cual):
    """Lo que hace elegir el análisis al abrir el programa: el valor
    recordado y el cuaderno activo."""
    from karlos_core import identidad
    from karlos_core.views.dialogo_analisis import ANALISIS
    identidad.ajustes().setValue(ANALISIS, cual)
    k._poner_analisis_activo(cual)


# ══════════════════════════════════════════════════════════════════
# 1 · Tiempo-movimiento
# ══════════════════════════════════════════════════════════════════

def test_tiempo_movimiento_como_lo_anota_un_evaluador(k, tmp_path, monkeypatch):
    _elegir(k, "time_motion")
    _abrir(k, tmp_path)
    assert k._analisis_del_combate() == "time_motion"
    assert k._en_modo_fases(), "entra directamente en la pasada de fases"
    # Cada atleta marca sus fases, una pasada por atleta (Johan, 19-10-2026).
    # [F] y [G] son del combate: al pasar a AO se quedan (antes la rama de
    # asaltos por atleta los borraba: ID25, 19-10-2026).
    k.window.annotation_panel.set_athlete("AKA"); QApplication.processEvents()
    _marcar_combate(k)
    k._on_analyze_other_direct(); QApplication.processEvents()
    assert (k.video_manager.fight_start, k.video_manager.fight_end) == (INICIO, FIN)
    k.window.annotation_panel.set_athlete("AKA"); QApplication.processEvents()

    # Un combate: preparación, intercambio, parada, preparación,
    # intercambio, un tramo que no se ve, y preparación hasta el final.
    secuencia = [(1000, Qt.Key_2), (1600, Qt.Key_1), (1650, Qt.Key_3),
                 (2400, Qt.Key_2), (3100, Qt.Key_1), (3160, Qt.Key_4), (3300, Qt.Key_2)]
    for frame, tecla in secuencia:
        _ir(k, frame); _pulsar(k, tecla)

    fases = sorted(_filas(k, "PHASE"), key=lambda r: r.f_start)
    assert [(r.f_start, r.technique) for r in fases] == [
        (1000, "non_fighting"), (1600, "fighting"), (1650, "stoppage"),
        (2400, "non_fighting"), (3100, "fighting"), (3160, "unobservable"),
        (3300, "non_fighting")]
    assert _filas(k) == fases, "solo fases: ni un Tsuki por pulsar 1, ni un Mawashi por pulsar 3"
    # Cada estado cierra el anterior justo antes: sin huecos ni solapes.
    for a, b in zip(fases, fases[1:]):
        assert a.f_end == b.f_start - 1, f"hueco o solape entre {a.technique} y {b.technique}"
    assert {r.athlete for r in fases} == {"AKA"}, "las fases son del atleta que se anota"
    assert k.window.log_compacto._lista.count() == len(fases), "el registro enseña las fases de AKA"

    # AO empieza de cero y marca las suyas; las de AKA no se tocan.
    k.window.annotation_panel.set_athlete("AO"); QApplication.processEvents()
    assert k._filas_de_fase() == [], "AO no tiene fases todavía"
    _ir(k, 1000); _pulsar(k, Qt.Key_2); _ir(k, 1700); _pulsar(k, Qt.Key_1)
    assert len(k._filas_de_fase()) == 2 and all(r.athlete == "AO" for _i, r in k._filas_de_fase())
    assert len([r for r in _filas(k, "PHASE") if r.athlete == "AKA"]) == len(fases)
    # Shift+1 retira la última de AO, no de AKA.
    _pulsar(k, Qt.Key_1, Qt.ShiftModifier)
    assert len(k._filas_de_fase()) == 1
    _pulsar(k, Qt.Key_1, Qt.ShiftModifier)
    assert k._filas_de_fase() == [] and len([r for r in _filas(k, "PHASE") if r.athlete == "AKA"]) == len(fases)
    k.window.annotation_panel.set_athlete("AKA"); QApplication.processEvents()
    assert len(k._filas_de_fase()) == len(fases)

    # Shift+1 retira la última y la anterior vuelve a quedar abierta.
    _pulsar(k, Qt.Key_1, Qt.ShiftModifier)
    assert len(_filas(k, "PHASE")) == len(fases) - 1
    _ir(k, 3300); _pulsar(k, Qt.Key_2)
    assert len(_filas(k, "PHASE")) == len(fases)

    # «Continuar nesta passagem», tras [G], no quita los límites del combate:
    # los borraba, y la sesión se guardaba sin ellos (ID25, 19-10-2026).
    k._on_continue_current_pass(); QApplication.processEvents()
    assert (k.video_manager.fight_start, k.video_manager.fight_end) == (INICIO, FIN)

    # Guardar y reabrir dos veces: nada se pierde ni se duplica.
    for _ in range(2):
        _reabrir(k)
        assert len(_filas(k, "PHASE")) == len(fases), "cada fase una vez, también al reabrir"

    wb = _exportar(k, tmp_path, "tm")
    ident = _identidad(wb)
    assert ident["Analysis mode"] == "time_motion", "el Excel dice con qué modo se anotó"
    assert ident["Data schema"] == "1.2" and str(ident["Program"]).startswith("Karlos")
    assert wb.sheetnames == ["Bout Info", "Annotations", "Time-Motion", "Time-Motion matrix"]
    tm = _texto(wb["Time-Motion"])
    assert "preparatory" in tm and "unobservable" in tm, "los cuatro estados, con su nombre de karate"
    assert "per athlete" in tm and "AKA" in tm, "la hoja es por atleta"
    assert "No complete round" not in tm and "Mark the start" not in tm, \
        "con [F] y [G] el combate es el asalto: la tabla no sale en blanco"
    assert "Chaabène" in tm, "el método que se describe es el del karate"
    assert "% of observed" in tm, "el reparto comparable con la literatura, sin lo que no se ve"
    assert "marked" in tm


# ══════════════════════════════════════════════════════════════════
# 2 · Técnico-táctico
# ══════════════════════════════════════════════════════════════════

def test_tecnico_tactico_como_lo_anota_un_evaluador(k, tmp_path):
    _elegir(k, "technical_tactical")
    _abrir(k, tmp_path)
    assert k._analisis_del_combate() == "technical_tactical"
    assert k._modo_eventos() and not k._en_modo_fases()
    _marcar_combate(k)

    # Cada acción: una pulsación, contestar qué fue, y ya. Sin [O].
    acciones = [("AKA", 2000, Qt.Key_4), ("AO", 2600, Qt.Key_5),
                ("AKA", 3300, Qt.Key_4), ("AO", 4100, Qt.Key_6)]
    for atleta, frame, tecla in acciones:
        k.window.annotation_panel.set_athlete(atleta); QApplication.processEvents()
        _ir(k, frame)
        _pulsar(k, Qt.Key_I)
        _contestar(k, tecla)

    hechas = [r for r in _filas(k) if r.category != "PHASE"]
    assert len(hechas) == len(acciones), "cada respuesta es una fila, sin pedir [O]"
    for r, (atleta, frame, _t) in zip(sorted(hechas, key=lambda r: r.f_start), acciones):
        assert r.athlete == atleta
        assert (r.f_start, r.f_end) == (frame, frame), "el fotograma en que se anotó, y nada más"
        assert r.duration_s is None, "sin extremos no hay duración, y cero sería mentira"
    assert _filas(k, "PHASE") == [], "en el técnico-táctico no se marcan fases"

    # Aquí un número no es una fase: es la respuesta a «¿Qué acción?». Sin
    # [I] abre la acción en ese fotograma y la contesta —[1], finta
    # superior—, igual que las demás: un evento más, sin fase ninguna.
    _ir(k, 5000); _contestar(k, Qt.Key_1)
    assert _filas(k, "PHASE") == []
    hechas = [r for r in _filas(k) if r.category != "PHASE"]
    assert len(hechas) == len(acciones) + 1
    finta = max(hechas, key=lambda r: r.f_start)
    assert (finta.technique, finta.f_start, finta.f_end, finta.duration_s) == ("Feint", 5000, 5000, None)

    _reabrir(k)
    hechas = [r for r in _filas(k) if r.category != "PHASE"]
    assert len(hechas) == len(acciones) + 1, "nada se pierde ni se duplica al reabrir"
    assert all(r.duration_s is None for r in hechas), "la duración ausente sobrevive al disco"

    wb = _exportar(k, tmp_path, "tt")
    ident = _identidad(wb)
    assert ident["Analysis mode"] == "technical_tactical", "el Excel dice con qué modo se anotó"
    assert ident["Data schema"] == "1.2" and str(ident["Program"]).startswith("Karlos")
    assert wb.sheetnames == ["Bout Info", "Annotations", "Technical-Tactical"]
    ann = wb["Annotations"]
    from karlos_karate.export_manager import ExportManager
    col = ExportManager.ANNOTATION_COLUMNS.index("duration_s") + 1
    duraciones = [ann.cell(r, col).value for r in range(2, ann.max_row + 1)]
    assert duraciones and all(d is None for d in duraciones), "celda vacía, no cero"
    tt = _texto(wb["Technical-Tactical"])
    assert "Actions" in tt


# ══════════════════════════════════════════════════════════════════
# 3 · Completo
# ══════════════════════════════════════════════════════════════════

def test_completo_es_el_programa_de_siempre(k, tmp_path):
    _elegir(k, "complete")
    _abrir(k, tmp_path)
    assert k._analisis_del_combate() == "complete"
    assert not k._modo_eventos() and not k._en_modo_fases()
    _marcar_combate(k)

    # [I], las preguntas, [O]: la acción con su duración.
    k.window.annotation_panel.set_athlete("AKA"); QApplication.processEvents()
    _ir(k, 2000); _pulsar(k, Qt.Key_I)
    _contestar(k, Qt.Key_4)
    assert not [r for r in _filas(k) if r.category != "PHASE"], "sin [O] todavía no hay fila"
    _ir(k, 2030); _pulsar(k, Qt.Key_O)
    hechas = [r for r in _filas(k) if r.category != "PHASE"]
    assert len(hechas) == 1
    r = hechas[0]
    assert (r.f_start, r.f_end) == (2000, 2030)
    assert r.duration_s == pytest.approx(30 / k.video_manager.fps, abs=1e-6)

    # Los dígitos son técnicas o respuestas, nunca fases: no se marca nada.
    _ir(k, 3000); _pulsar(k, Qt.Key_3)
    assert _filas(k, "PHASE") == []

    _reabrir(k)
    assert len([r for r in _filas(k) if r.category != "PHASE"]) == 1

    wb = _exportar(k, tmp_path, "completo")
    ident = _identidad(wb)
    assert ident["Analysis mode"] == "complete", "el Excel dice con qué modo se anotó"
    assert ident["Data schema"] == "1.2" and str(ident["Program"]).startswith("Karlos")
    assert wb.sheetnames == ["Bout Info", "Annotations", "Technical-Tactical",
                             "Time-Motion", "Time-Motion matrix"]
    tm = _texto(wb["Time-Motion"])
    assert "derived" in tm, "el tiempo-movimiento sale derivado de las acciones"
    assert "Mark the start" not in tm


def test_el_modo_viaja_en_el_csv_y_vuelve_al_reimportar(tmp_path):
    """Exportar el CSV del combate y volver a cargarlo: el combate sigue
    siendo del análisis con que se anotó (decisión 0008)."""
    from karlos_core.controllers.anotador.exportacion import ExportacionMixin
    from karlos_core.models.annotation import Annotation
    catalogo.establecer("karate")
    csv = catalogo.activo().salidas().csv_del_combate()
    for modo in ("time_motion", "technical_tactical", "complete"):
        texto = csv.componer([Annotation(athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
                                         technique="Gyaku Tsuki", level="Chudan", score="YUKO",
                                         f_start=100, f_end=100, duration_s=None)],
                             bout_info={"analysis": modo}, video="x.mp4", fps=30.0,
                             fight_start=50, fight_end=900)
        assert f"# analysis: {modo}\n" in texto and "# schema: 1.2\n" in texto
        ruta = tmp_path / f"{modo}.csv"; ruta.write_text(texto, encoding="utf-8")
        cabecera, filas = csv.leer(ruta)
        assert ExportacionMixin._bout_info_de_cabecera(cabecera)["analysis"] == modo
        # La duración que no se midió vuelve ausente del CSV, no a cero; en los
        # otros modos se recalcula de los fotogramas (V2 de la v19, 19-10-2026).
        assert filas[0].duration_s == (None if modo == "technical_tactical" else 0.0)




# ══════════════════════════════════════════════════════════════════
# Cada modo, su cuaderno
# ══════════════════════════════════════════════════════════════════

def _huella(ruta: Path) -> str:
    import hashlib
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def test_cada_modo_tiene_sus_anotaciones_y_no_ve_las_de_los_otros(k, tmp_path, monkeypatch):
    """Johan, 19-10-2026: «si abro el vídeo 1 con el modo tiempo-movimiento
    y hago algunas anotaciones, salgo, y luego hago anotaciones con el
    técnico-táctico, no me tienen que aparecer las del tiempo-movimiento».

    El mismo vídeo pasa por los tres modos; cada uno guarda en su archivo y
    al volver a él encuentra lo suyo y nada más."""
    # El completo, como un combate del estudio: una acción con [I] y [O].
    _elegir(k, "complete")
    video = _abrir(k, tmp_path)
    _marcar_combate(k)
    k.window.annotation_panel.set_athlete("AKA"); QApplication.processEvents()
    _ir(k, 2000); _pulsar(k, Qt.Key_I); _contestar(k, Qt.Key_4)
    _ir(k, 2030); _pulsar(k, Qt.Key_O)
    assert len(_filas(k)) == 1
    k._save_session()
    sesiones = video.parent / ".karlos_sessions"
    completo = sesiones / f"{video.stem}__default__1.karlos"
    assert completo.exists(), "el completo guarda donde siempre: el estudio y la 1.0 lo leen"

    # Tiempo-movimiento, con el combate abierto: sale vacío.
    assert k._cambiar_de_analisis("time_motion")
    assert k._analisis_del_combate() == "time_motion" and k._en_modo_fases()
    assert _filas(k) == [], "la acción del completo no aparece en el tiempo-movimiento"
    _marcar_combate(k)
    for frame, tecla in ((1000, Qt.Key_2), (1600, Qt.Key_1), (1650, Qt.Key_3)):
        _ir(k, frame); _pulsar(k, tecla)
    assert len(_filas(k, "PHASE")) == 3 and len(_filas(k)) == 3

    # Salir al Hub, volver a la pantalla inicial y elegir técnico-táctico.
    k._save_session(); k._on_back_to_hub(); QApplication.processEvents()
    _desde_el_inicio(k, monkeypatch, "technical_tactical")
    assert k._analisis_del_combate() == "technical_tactical"
    k._on_session_selected(0); QApplication.processEvents()
    assert _filas(k) == [], "ni las fases del tiempo-movimiento ni la acción del completo"
    _marcar_combate(k)
    k.window.annotation_panel.set_athlete("AO"); QApplication.processEvents()
    for frame in (2600, 3300):
        _ir(k, frame); _pulsar(k, Qt.Key_I); _contestar(k, Qt.Key_4)
    assert len(_filas(k)) == 2 and _filas(k, "PHASE") == []

    # Volver al tiempo-movimiento: sus tres fases, y solo ellas.
    assert k._cambiar_de_analisis("time_motion")
    assert len(_filas(k)) == 3 and len(_filas(k, "PHASE")) == 3, \
        "el tiempo-movimiento encuentra lo suyo y no los eventos del técnico-táctico"
    assert (k.video_manager.fight_start, k.video_manager.fight_end) == (INICIO, FIN)

    # Y el completo, su acción: intacto, también en el disco.
    assert k._cambiar_de_analisis("complete")
    hechas = _filas(k)
    assert len(hechas) == 1 and (hechas[0].f_start, hechas[0].f_end) == (2000, 2030)
    assert _filas(k, "PHASE") == []
    k._save_session()
    assert {p.name for p in sesiones.glob("*.karlos")} == {
        f"{video.stem}__default__1.karlos",
        f"{video.stem}__default__1__tm.karlos",
        f"{video.stem}__default__1__tt.karlos"}, "un archivo por modo"
    import json
    assert [r["category"] for r in json.loads(completo.read_text())["annotations"]] == \
        [hechas[0].category], "el archivo del completo no recibió nada de los otros modos"

    # Cada exportación sale de su cuaderno.
    assert k._cambiar_de_analisis("technical_tactical")
    wb = _exportar(k, tmp_path, "tt_cuaderno")
    assert _identidad(wb)["Analysis mode"] == "technical_tactical"
    assert wb["Annotations"].max_row == 1 + 2, "las dos acciones del técnico-táctico, nada más"


def test_un_combate_del_estudio_no_aparece_en_los_modos_nuevos(k, tmp_path):
    """Los 20 combates están en el archivo de siempre, sin modo escrito: son
    del completo. Abiertos en tiempo-movimiento o técnico-táctico salen
    vacíos y su archivo no se toca."""
    import json
    _elegir(k, "complete")
    video = _abrir(k, tmp_path)
    _marcar_combate(k)
    _ir(k, 2000); _pulsar(k, Qt.Key_I); _contestar(k, Qt.Key_4)
    _ir(k, 2030); _pulsar(k, Qt.Key_O)
    k._save_session(); k._on_back_to_hub(); QApplication.processEvents()
    completo = video.parent / ".karlos_sessions" / f"{video.stem}__default__1.karlos"
    datos = json.loads(completo.read_text())
    datos["bout_info"].pop("analysis", None)          # como los del estudio
    completo.write_text(json.dumps(datos), encoding="utf-8")
    huella = _huella(completo)

    for modo in ("time_motion", "technical_tactical"):
        assert k._cambiar_de_analisis(modo)
        k._on_session_selected(0); QApplication.processEvents()
        assert _filas(k) == [], f"en {modo} el combate del estudio sale vacío"
        k._on_back_to_hub(); QApplication.processEvents()
    assert _huella(completo) == huella, "el archivo del estudio no se movió ni se tocó"
    assert completo.exists()


def test_las_sesiones_de_antes_de_los_cuadernos_pasan_al_suyo(tmp_path):
    """Hasta el 19-10 un combate de tiempo-movimiento se guardaba en el
    archivo de siempre con su análisis escrito.
    Al abrirlo en su modo pasa a su cuaderno, con copia en backups/."""
    import json
    from karlos_core.controllers.session_manager import SessionManager
    video = tmp_path / "combate.mp4"; video.write_bytes(b"")
    sesiones = tmp_path / ".karlos_sessions"; sesiones.mkdir()
    plano = sesiones / "combate__default__1.karlos"
    plano.write_text(json.dumps({"version": "1.0", "bout_info": {"analysis": "time_motion"},
                                 "annotations": []}), encoding="utf-8")

    # En otro cuaderno no se mueve: no es suyo.
    SessionManager.poner_cuaderno("technical_tactical")
    assert not SessionManager.migrar_al_cuaderno(str(video))
    assert plano.exists()
    # En el completo tampoco: el completo es el archivo de siempre.
    SessionManager.poner_cuaderno("complete")
    assert not SessionManager.migrar_al_cuaderno(str(video))

    SessionManager.poner_cuaderno("time_motion")
    assert SessionManager.migrar_al_cuaderno(str(video))
    assert not plano.exists()
    assert (sesiones / "combate__default__1__tm.karlos").exists()
    assert list((sesiones / "backups").glob("combate__default__1__*.karlos")), "antes, una copia"
    # Y una sola vez: con el cuaderno ya escrito no se vuelve a mover nada.
    assert not SessionManager.migrar_al_cuaderno(str(video))

    # Con la etiqueta pero no el contenido (ID33 del estudio: «time_motion»
    # escrito y 160 acciones del completo) tampoco se mueve.
    accion = {"category": "ATTACK", "f_start": 100, "f_end": 130}
    plano.write_text(json.dumps({"version": "1.0", "bout_info": {"analysis": "time_motion"},
                                 "annotations": [accion]}), encoding="utf-8")
    (sesiones / "combate__default__1__tm.karlos").unlink()
    SessionManager.poner_cuaderno("time_motion")
    assert not SessionManager.migrar_al_cuaderno(str(video)) and plano.exists()
    plano.write_text(json.dumps({"version": "1.0", "bout_info": {"analysis": "technical_tactical"},
                                 "annotations": [accion]}), encoding="utf-8")
    SessionManager.poner_cuaderno("technical_tactical")
    assert not SessionManager.migrar_al_cuaderno(str(video)) and plano.exists(), \
        "una acción con duración no es del técnico-táctico"

    # Uno sin modo escrito (los del estudio) no se mueve nunca.
    plano.write_text(json.dumps({"version": "1.0", "bout_info": {}, "annotations": []}),
                     encoding="utf-8")
    SessionManager.poner_cuaderno("technical_tactical")
    assert not SessionManager.migrar_al_cuaderno(str(video)) and plano.exists()


def test_se_cambia_de_modo_volviendo_a_la_pantalla_inicial(k, tmp_path, monkeypatch):
    """Johan, 19-10-2026: los tres botones arriba a la derecha «no deberían
    estar ahí»; se vuelve a la primera página para elegir otro modo, y al
    elegirlo se cargan solo las anotaciones de ese modo."""
    hub = k.window.project_hub
    assert not hasattr(hub, "_btns_analisis"), "ya no hay selector de tres botones"
    assert not hub._btn_inicio.isHidden()
    for modo in ("time_motion", "technical_tactical", "complete", "time_motion"):
        _desde_el_inicio(k, monkeypatch, modo)
        assert k._analisis_del_combate() == modo
        assert hub._etiqueta_analisis.text().startswith(I18n().t(
            {"time_motion": "analisis.tm", "technical_tactical": "analisis.tt"}.get(
                modo, "analisis.completo")).upper()), "el Hub dice en qué modo se está"
        # En el integrado la etiqueta dice que se anota con el árbol.
        assert ("ASSISTIDO" in hub._etiqueta_analisis.text()) == (modo == "complete")
    # Cerrar la pantalla inicial sin elegir no cambia nada.
    from karlos_core.views import dialogo_analisis
    monkeypatch.setattr(dialogo_analisis, "elegir_al_inicio", lambda *a, **kw: None)
    hub._btn_inicio.click(); QApplication.processEvents()
    assert k._analisis_del_combate() == "time_motion", "se queda en el último elegido"

    # Desde el anotador, «Análisis…» hace lo mismo: guarda, sale al Hub y
    # vuelve a la pantalla inicial.
    _elegir(k, "time_motion")
    _abrir(k, tmp_path); _marcar_combate(k)
    _ir(k, 1000); _pulsar(k, Qt.Key_2)
    monkeypatch.setattr(dialogo_analisis, "elegir_al_inicio",
                        lambda *a, **kw: "technical_tactical")
    k._volver_al_inicio(); QApplication.processEvents()
    assert k._analisis_del_combate() == "technical_tactical"
    assert k.navigation is not None and not k._video_path, "se queda en el Hub, como al arrancar"
    k._on_session_selected(0); QApplication.processEvents()
    assert _filas(k) == [], "en técnico-táctico no aparece la fase del tiempo-movimiento"


def test_cada_modo_ensena_solo_su_panel(k, tmp_path, monkeypatch):
    """Johan, ID25, 19-10-2026: «se abrieron las opciones del análisis
    tiempo-movimiento y técnico-táctico al mismo tiempo».

    Al cambiar de modo desde el Hub, el anotador está oculto y el panel de
    fases decía no estar visible aunque lo estuviera puesto; la guarda de
    `mostrar_panel_fases` daba el cambio por hecho y no lo quitaba. Al abrir
    el combate salían los dos paneles a la vez."""
    from karlos_core.views import dialogo_analisis

    def paneles():
        w = k.window
        return (w.panel_fases.isVisibleTo(w.panel_fases.parentWidget()),
                w.annotation_panel._scroll_tecnicas.isVisibleTo(w.annotation_panel))

    _elegir(k, "time_motion")
    _abrir(k, tmp_path)
    assert paneles() == (True, False), "en tiempo-movimiento, las cuatro teclas y ninguna técnica"
    for modo, esperado in (("technical_tactical", (False, True)),
                           ("complete", (False, True)),
                           ("time_motion", (True, False))):
        monkeypatch.setattr(dialogo_analisis, "elegir_al_inicio", lambda *a, _m=modo, **kw: _m)
        k._volver_al_inicio(); QApplication.processEvents()
        k._on_session_selected(0); QApplication.processEvents()
        assert paneles() == esperado, f"paneles de {modo}"
        if modo == "time_motion":
            # Y con alto: al repartir la columna, `ajustar_columna` miraba
            # isVisible() con la página del anotador aún oculta y dejaba las
            # fases a cero (visto al capturar la Figura 3, 19-10-2026).
            assert k.window._tech_splitter.sizes()[2] > 0, "las fases vuelven con alto"


def test_la_pantalla_inicial_pregunta_el_analisis(monkeypatch):
    from PySide6.QtWidgets import QDialog
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views import dialogo_analisis as da
    catalogo.establecer("karate")
    cfg, _meta = load_config("karate")
    vistas = []

    def contestar(analisis):
        def exec_(self):
            vistas.append("analisis"); self.analisis = analisis
            return QDialog.DialogCode.Accepted
        return exec_
    for analisis in ("time_motion", "technical_tactical", "complete"):
        vistas.clear()
        monkeypatch.setattr(da.DialogoAnalisis, "exec", contestar(analisis))
        assert da.elegir_al_inicio(cfg.colors) == analisis
        assert vistas == ["analisis"], "una sola pantalla"
    # Cerrarla es salir sin elegir.
    monkeypatch.setattr(da.DialogoAnalisis, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert da.elegir_al_inicio(cfg.colors) is None


