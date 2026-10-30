"""La interfaz de la anotacion guiada: solo lo que se usa anotando.

La barra se habia ido llenando de botones hasta tener veinticuatro a la
vista mientras se anota. Estos tests fijan los que quedan y, sobre todo,
que los que se fueron no dejaron un camino roto ni un camino duplicado.

Se EJECUTAN. Un test que busca texto en el fuente comprueba que escribi
lo que queria escribir, no que funcione — ya nos costo horas una vez.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QPushButton


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    yield QApplication.instance() or QApplication([])


def _anotador(pro: bool):
    """Un anotador abierto de verdad, en la anotacion guiada si se pide."""
    from karlos_core.utils.config_loader import load_config
    from karlos_core.controllers.annotation_controller import (
        AnnotationController,
    )
    # Entrar en modo asistido lanza los hilos de analisis de verdad, y
    # uno vivo al cerrar el interprete aborta la suite entera (exit
    # 134) aunque todos los tests pasen. Aqui se prueba la interfaz,
    # no el analisis: los hilos no arrancan.
    config, meta = load_config("karate")
    c = AnnotationController(config, meta)
    c.aplicar_modo_inicial()
    c.show()
    c.navigation.show_annotator()
    QApplication.processEvents()
    if pro and not c._en_modo_pro():
        c._video_path = "/tmp/no-existe.mp4"   # basta para entrar en Pro
        c._entrar_modo_asistido()
    QApplication.processEvents()
    return c


def _visibles(c) -> list[str]:
    return [b.text().strip() for b in c.window.findChildren(QPushButton)
            if b.isVisibleTo(c.window) and b.text().strip()]


# ----------------------------------------------------------------------
# Lo que queda a la vista
# ----------------------------------------------------------------------

def test_pro_solo_deja_los_botones_que_se_usan():
    c = _anotador(pro=True)
    assert c._en_modo_pro()
    assert sorted(_visibles(c)) == sorted([
        "▶", "🔊",          # el símbolo, no «Reproduzir/Pausar»
        "Início Luta [F]", "Fim Luta [G]",
        "INÍCIO [I]", "FIM [O]",
        "←  Hub", "Dados do combate", "Importar",
        "Exportar", "Ver relatório",
        # Desde la decisión 0008 el karate tiene tres análisis, así que
        # también tiene el botón para cambiarlo. Antes solo salía en los
        # deportes que hacían tiempo-movimiento.
        "Análise…",
        "AKA", "AO",
    ])


def test_la_etiqueta_de_illegal_dice_la_tecla_que_es():
    """Ponia «Illegal [D]» y [D] es «marcar inicio» en Pro.

    El atajo real siempre fue [Shift+D]; el boton llevaba meses
    anunciando una tecla que hacia otra cosa.
    """
    c = _anotador(pro=False)
    assert "Illegal [⇧D]" in _visibles(c)
    assert "Illegal [D]" not in _visibles(c)


# ----------------------------------------------------------------------
# Lo que se quito no puede dejar un camino roto
# ----------------------------------------------------------------------

def test_abrir_video_sigue_estando_en_ctrl_o():
    """Se quito el boton, no la funcion."""
    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QApplication as _QA
    c = _anotador(pro=True)
    secuencias = [s.key().toString() for s in c.window.findChildren(
        __import__("PySide6.QtGui", fromlist=["QShortcut"]).QShortcut)]
    assert any(QKeySequence(s) == QKeySequence("Ctrl+O") for s in secuencias if s)


# ----------------------------------------------------------------------
# Y sobre todo: un solo camino para anotar una falta
# ----------------------------------------------------------------------

def test_en_pro_no_quedan_botones_de_falta_a_la_vista():
    c = _anotador(pro=True)
    vis = _visibles(c)
    assert not [t for t in vis
                if any(k in t for k in ("Contact", "Target", "Illegal", "Procedure"))]


def test_la_tabla_completa_sigue_teniendo_puerta():
    """Se quito el boton «Registro completo», no la tabla.

    La tabla de 28 columnas se mueve a una ventana aparte
    para dejarle el alto al video. Sin el boton se quedaba sin ninguna
    forma de abrirse: la puerta es ahora el clic derecho en el registro.
    """
    c = _anotador(pro=True)
    assert c.window.table_view.parent() is c.window.log_dialog
    assert not c.window.log_dialog.isVisible()
    c.window.log_compacto.tabla_pedida.emit()
    QApplication.processEvents()
    assert c.window.log_dialog.isVisible()


# ----------------------------------------------------------------------
# El boton y la tecla que lo anuncia tienen que hacer lo mismo
# ----------------------------------------------------------------------

def _con_video(pro: bool = True):
    """Anotador con un video cargado y el combate empezado."""
    c = _anotador(pro=pro)
    c._video_path = "/tmp/falso.mp4"
    c.video_manager.fight_start = 10          # sin esto no deja marcar nada
    return c


def test_el_boton_INICIO_abre_el_arbol_igual_que_la_tecla():
    """El boton iba por el camino del flujo de botones.

    Delimitaba el corte y no abria el arbol: la anotacion salia sin
    guardia, sin nivel y sin contexto tactico, y sin avisar. Es el mismo
    fallo que tenian los botones de tecnica y los de falta, y aqui es
    peor porque el boton se llama «INÍCIO [D]» — anuncia la tecla con la
    que no coincide.
    """
    c = _con_video()
    llamadas = []
    c._marcar_inicio = lambda: llamadas.append("inicio")
    c.window.video_panel.mark_start_requested.emit()
    QApplication.processEvents()
    assert llamadas == ["inicio"]


def test_el_boton_FIM_va_por_donde_va_la_tecla():
    c = _con_video()
    llamadas = []
    c._marcar_fin = lambda: llamadas.append("fin")
    c.window.video_panel.mark_end_requested.emit()
    QApplication.processEvents()
    assert llamadas == ["fin"]


class _SesionFalsa:
    def __init__(self, anotaciones):
        self.annotations = anotaciones


def _una_anotacion():
    from karlos_core.models.annotation import Annotation
    return Annotation(f_start=100, f_end=120, athlete="AKA", category="ATTACK",
                      subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki",
                      level="Jodan")


def test_en_pro_ver_relatorio_abre_el_del_entrenador():
    """Estaba construido y sin conectar.

    El boton seguia llevando al informe de siempre, que era un borrador de
    metricas sueltas. El del entrenador existia entero —seis bloques, en
    portugues, con las metricas que si tienen base— y no habia forma de
    llegar a el desde la aplicacion.
    """
    c = _anotador(pro=True)
    ses = _SesionFalsa([_una_anotacion()])
    c.sessions = [ses]
    abiertos = []
    c._abrir_relatorio = lambda s: abiertos.append(s)
    c._on_view_report(0)
    assert abiertos == [ses]


def test_el_informe_del_entrenador_se_monta_de_verdad():
    """Que se construya sin reventar, con una anotacion minima."""
    c = _anotador(pro=True)
    c._bout_info.update({"athlete_a_name": "A. UNO", "athlete_b_name": "B. DOS"})
    c._abrir_relatorio(_SesionFalsa([_una_anotacion()]))
    QApplication.processEvents()
    rel = getattr(c, "_relatorio", None)
    assert rel is not None and rel.isVisible()


# ----------------------------------------------------------------------
# El vídeo es el foco: que se lleve el alto que pueda
# ----------------------------------------------------------------------

def test_en_pro_los_botones_viven_en_la_banda_del_titulo():
    """Su fila propia costaba 49 px de alto que se le quitaban al vídeo."""
    c = _anotador(pro=True)
    w = c.window
    assert not w._action_bar_widget.isVisible(), "la fila suelta sobra en PRO"
    assert not w._sep_barra.isVisible()
    for btn in w._botones_barra:
        assert btn.isVisibleTo(w), btn.text()


def test_fuera_de_pro_los_botones_vuelven_a_su_fila():
    c = _anotador(pro=False)
    w = c.window
    assert w._action_bar_widget.isVisible()
    for btn in w._botones_barra:
        assert btn.isVisibleTo(w), btn.text()


def test_en_pro_el_cronometro_se_mete_en_la_fila_de_controles():
    """Tenía franja propia de 30 px con todo el ancho vacío en medio."""
    c = _anotador(pro=True)
    vp = c.window.video_panel
    assert not vp._franja.isVisible()
    for w in (vp._fight_timer, vp._live_stats):
        assert w.isVisibleTo(vp), "el dato no puede perderse por el camino"


def test_el_video_se_reescala_al_cambiar_de_tamano():
    """Se escalaba una vez, al pintarlo, y se quedaba con ese tamaño.

    Agrandando la ventana con el vídeo parado la imagen seguía pequeña
    en medio de un marco negro hasta que algo la movía — que es justo
    lo que se hace mirando una acción detenida.
    """
    import numpy as np
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.video_panel import VideoPanelView
    cfg, _ = load_config("karate")
    vp = VideoPanelView(cfg.colors, cfg.video)
    vp.aplicar_modo(True)
    vp.resize(700, 480)
    vp.show()
    QApplication.processEvents()
    vp.update_frame_display(np.zeros((1080, 1920, 3), dtype=np.uint8))
    QApplication.processEvents()
    chico = vp.display.pixmap().height()
    vp.resize(1500, 1000)
    QApplication.processEvents()
    QApplication.processEvents()
    assert vp.display.pixmap().height() > chico + 100, (
        f"seguía en {chico}px tras agrandar el panel")


def test_el_video_se_pinta_con_los_pixeles_reales_de_la_pantalla(monkeypatch):
    """En una pantalla Retina el panel tiene el doble de pixeles que de
    puntos. El fotograma se reducia al tamaño en puntos cogiendo el pixel
    mas cercano y el sistema lo volvia a ampliar: un 1080p se veia con
    ~1200 pixeles de detalle y los bordes dentados. Ahora se pinta a los
    pixeles reales, filtrado, y el pixmap lo dice para que nadie lo
    vuelva a escalar."""
    import numpy as np
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.video_panel import VideoPanelView
    cfg, _ = load_config("karate")
    vp = VideoPanelView(cfg.colors, cfg.video)
    vp.resize(1000, 700)
    vp.show()
    QApplication.processEvents()
    # Se prueba la imagen que se entrega al panel: QLabel.pixmap() la
    # devuelve ya convertida a la densidad de su pantalla, y la de las
    # pruebas (sin pantalla) es 1.
    monkeypatch.setattr(VideoPanelView, "_densidad_de_pantalla", lambda self: 2.0)
    fotograma = np.zeros((1080, 1920, 3), dtype=np.uint8)
    fotograma[:, ::2] = 255                     # rayas de un pixel: el peor caso
    pm = vp._pixmap_para_pantalla(fotograma)
    assert pm.devicePixelRatio() == 2.0
    ancho_puntos = vp.display.width()
    assert pm.width() >= 2 * ancho_puntos - 2 or pm.height() >= 2 * vp.display.height() - 2, (
        f"pintado a {pm.width()}x{pm.height()} px en un panel de {ancho_puntos} puntos a densidad 2")
    # filtrado, no el pixel mas cercano: las rayas no pueden salir en
    # blanco y negro puros a otro tamaño
    img = pm.toImage()
    grises = {img.pixelColor(x, pm.height() // 2).red() for x in range(40, 80)}
    assert any(20 < g < 235 for g in grises), "se escaló sin filtrar"


# ----------------------------------------------------------------------
# El recuento no puede mentir
# ----------------------------------------------------------------------

def test_el_recuento_se_refresca_al_cargar_un_combate():
    """Solo se refrescaba al CREAR una anotación.

    Abriendo un combate ya anotado la franja decía «AKA: 0 · AO: 0 ·
    Total: 0» teniendo 228 acciones y un 0-2 en el marcador. Un dato
    que miente es peor que no tenerlo.
    """
    from karlos_core.models.annotation import Annotation
    c = _anotador(pro=True)
    vistos = []
    c.window.video_panel.update_live_stats = (
        lambda aka, ao, total, elapsed: vistos.append((aka, ao, total)))
    for atleta, score in (("AKA", ""), ("AO", "YUKO"), ("AO", "YUKO")):
        c.window.table_view.add_annotation(Annotation(
            f_start=100, f_end=120, athlete=atleta, category="ATTACK",
            subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki",
            score=score))
    c.video_manager._current_frame = 500      # más allá de las tres
    c._update_live_stats()
    assert vistos and vistos[-1] == (0, 2, 3), vistos[-1]


def test_el_marcador_muestra_como_iba_EN_ESE_PUNTO():
    """No el resultado final: lo que llevaban donde está el vídeo.

    Es lo que enseña el marcador de la pantalla, y con lo que hay que
    poder contrastar mientras se anota.
    """
    from karlos_core.models.annotation import Annotation
    c = _anotador(pro=True)
    vistos = []
    c.window.video_panel.update_live_stats = (
        lambda aka, ao, total, elapsed: vistos.append((aka, ao)))
    for f0, atleta in ((1000, "AO"), (5000, "AO")):
        c.window.table_view.add_annotation(Annotation(
            f_start=f0, f_end=f0 + 20, athlete=atleta, category="ATTACK",
            subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki",
            score="YUKO"))
    c.video_manager._current_frame = 2000     # entre las dos
    c._update_live_stats()
    assert vistos[-1] == (0, 1), f"a mitad debe ir 0-1, va {vistos[-1]}"
    c.video_manager._current_frame = 9000     # después de las dos
    c._update_live_stats()
    assert vistos[-1] == (0, 2)


def test_editar_lleva_el_video_a_la_accion_para_que_se_vea_el_cambio(monkeypatch):
    """Un evaluador editó una técnica para ponerle el punto y el marcador no se movió.

    El marcador cuenta lo que queda POR DETRÁS del vídeo, para poder
    contrastarlo con el marcador de la imagen. Al editar una acción se
    suele estar rebobinado sobre ella, así que el punto recién puesto
    caía por delante y no contaba: parecía que la edición no había
    entrado. Ahora editar lleva el vídeo a la acción.
    """
    from karlos_core.models.annotation import Annotation
    from karlos_core.views.edit_annotation_popup import EditAnnotationPopup
    c = _anotador(pro=True)
    c.window.table_view.add_annotation(Annotation(
        f_start=5000, f_end=5030, athlete="AKA", category="ATTACK",
        subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki", score="NONE"))
    editada = Annotation(
        f_start=5000, f_end=5030, athlete="AKA", category="ATTACK",
        subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki", score="YUKO")
    monkeypatch.setattr(EditAnnotationPopup, "exec",
                        lambda self: EditAnnotationPopup.Accepted)
    original = EditAnnotationPopup.__init__

    def init(self, **kw):
        original(self, **kw)
        self.edited = editada
    monkeypatch.setattr(EditAnnotationPopup, "__init__", init)

    saltos = []
    monkeypatch.setattr(type(c.video_manager), "goto",
                        lambda self, f: saltos.append(int(f)) or True)
    c._on_edit_annotation(0)
    assert saltos and saltos[-1] == 5000, \
        "editar tiene que dejar el vídeo en la acción editada"


def test_las_faltas_tambien_van_por_donde_esta_el_video():
    """El grado de la siguiente falta sale del contador de ESE momento."""
    from karlos_core.models.annotation import Annotation
    c = _anotador(pro=True)
    for f0 in (1000, 3000, 5000):
        c.window.table_view.add_annotation(Annotation(
            f_start=f0, f_end=f0 + 20, athlete="AO", category="ATTACK",
            subcategory="HAND TECHNIQUES", technique="Gyaku Tsuki",
            sport_specific_data={"sanction": "Contact"}))
    cf = c.window.video_panel.contador_faltas
    c.video_manager._current_frame = 3500
    c._update_live_stats()
    assert (cf._aka, cf._ao) == (0, 2), (cf._aka, cf._ao)
    assert "CHUI-2" in cf.toolTip()
    c.video_manager._current_frame = 9000
    c._update_live_stats()
    assert (cf._aka, cf._ao) == (0, 3)
    assert "CHUI-3" in cf.toolTip()


def test_el_boton_de_reproducir_es_un_simbolo_en_pro():
    """«Reproduzir/Pausar» son 17 caracteres donde todo cabe en cuatro.

    El atajo va en el tooltip, que es donde se busca.
    """
    c = _anotador(pro=True)
    b = c.window.video_panel.btn_play
    assert b.text() in ("▶", "⏸"), b.text()
    assert "[K]" in b.toolTip(), b.toolTip()
    c.window.video_panel.update_play_button(True)
    assert c.window.video_panel.btn_play.text() == "⏸"


# ----------------------------------------------------------------------
# Todo el PRO habla portugués
# ----------------------------------------------------------------------

def test_los_mensajes_de_estado_salen_traducidos():
    """La traducción existía y el código escribía el inglés a pelo.

    En la barra de abajo salía «START at frame 1854 — select technique»
    con el resto del programa en portugués.
    """
    from karlos_core.utils.i18n import I18n
    i = I18n(); i.set_lang("pt")
    for clave, kw, debe in (
            ("wf.start", {"frame": "1854"}, "INÍCIO"),
            ("stat.active_session", {"name": "x.mp4"}, "Sessão"),
            ("stat.new_session", {"label": "Passe 1"}, "Sessão"),
            ("stat.session_restored", {"n": "228", "athlete": "Passe 1"}, "anotações")):
        texto = i.t(clave, **kw)
        assert debe in texto, f"{clave}: {texto}"
        assert "at frame" not in texto and "press [" not in texto, texto


def test_ningun_mensaje_de_estado_queda_escrito_en_ingles():
    """El PRO habla portugués: los botones, las preguntas y la barra.

    Estaban en español y en inglés mezclados — «Session completed»,
    «Marque primero el inicio», «Now analyzing» — con el resto en
    portugués. Se comprueba solo con palabras que en portugués no
    existen, para no marcar como inglés un «vídeo» o un «frame».
    """
    import pathlib
    import re
    raiz = pathlib.Path(__file__).resolve().parents[1]
    patron = re.compile(r'set_status_message\(\s*f?"([^"]{10,})"')
    # ninguna de estas es palabra portuguesa
    ingles = re.compile(
        r"\b(press|select|mark|first|session|sessions|annotation|annotations|"
        r"exported|updated|completed|loaded|ready|rounds|awarded|previous|"
        r"repeat|cancelled|pending|videos|folder|Unknown|Auto)\b")
    espanol = re.compile(
        r"\b(pulse|elija|seleccione|primero|despues|después|acción|acciones|"
        r"anotación|anotacion|siguiente|combate|archivos|borrado)\b", re.I)
    malos = []
    # También lo del karate, que se mudó a su paquete (fase F4).
    for ruta in [*raiz.rglob("*.py"), *(raiz.parent / "karlos_karate").rglob("*.py")]:
        if "tests" in ruta.parts:
            continue
        for m in patron.finditer(ruta.read_text(encoding="utf-8")):
            # Fuera lo que va entre llaves: ahi hay codigo, no prosa, y
            # `len(videos)` o `folder` no son ingles dirigido a nadie.
            texto = re.sub(r"\{[^}]*\}", " ", m.group(1))
            if ingles.search(texto):
                malos.append(f"[en] {ruta.name}: {texto[:64]}")
            elif espanol.search(texto):
                malos.append(f"[es] {ruta.name}: {texto[:64]}")
    assert not malos, "la barra de estado no habla portugués:\n  " + "\n  ".join(malos)


