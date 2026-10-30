"""Tests de la pantalla de combates despues de quitarle lo que sobraba.

La queja era «existen muchas cosas y parece confuso». Lo que se quito
no se quito por gusto: cada cosa o repetia otra, o decia lo mismo en
las doce filas, o estaba vacia. Estos tests vigilan que no vuelva, y
sobre todo que lo que se quedo siga funcionando.

Dos fallos reales salieron al hacerlo y tienen test propio:

- filtrar por «concluidos» escondia justo los combates marcados para
  revisar, porque comparaba el texto de la celda («Concluído ⚠») con
  la etiqueta interna («Completed»);
- el boton de abrir estaba apagado en los combates pendientes, que son
  justo los que hay que abrir.
"""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class _Sesion:
    def __init__(self, id=1, nombre="ID30_-75KG_MALE_ASSEMAT X DUARTE POR.mp4",
                 estado="Pending", n=0, ruta=None):
        from karlos_core.models.annotation import Annotation
        self.id = id
        self.video_path = ruta or f"/v/{nombre}"
        self.video_name = nombre
        self.status = estado
        self.annotations = [
            Annotation(athlete="AKA", category="ATTACK", subcategory="",
                       technique="Gyaku Tsuki") for _ in range(n)]
        self.bout_metadata = {"athlete_a_name": "H. ASSEMAT",
                              "athlete_b_name": "T. DUARTE",
                              "weight_category": "-75 kg"}
        self.resolution = ""
        self.fps = 30.0
        self.duration_s = 407.0


def _hub(sesiones=None):
    from karlos_core.utils.config_loader import load_config
    from karlos_core.views.project_hub import ProjectHubView
    cfg, _ = load_config("karate")
    h = ProjectHubView(cfg.colors, {"id": "karate", "name": "Karate"})
    h.resize(1500, 700)
    h.set_sessions(sesiones if sesiones is not None else [_Sesion()])
    return h


# ======================================================================
# Lo que se fue
# ======================================================================

class TestLasColumnasQueNoDecianNada:
    def test_evento_y_progresso_ya_no_estan(self):
        """EVENTO salia vacía en los doce; PROGRESSO repetia ESTADO."""
        from karlos_core.views.project_hub import ProjectHubView
        assert not hasattr(ProjectHubView, "COL_EVENT")
        assert not hasattr(ProjectHubView, "COL_PROGRESS")

    def test_quedan_nueve_columnas(self):
        h = _hub()
        assert h._table.columnCount() == 9

    def test_las_que_quedan_no_se_pisan(self):
        """Dos columnas con el mismo indice y una tapa a la otra."""
        from karlos_core.views.project_hub import ProjectHubView as P
        indices = [P.COL_ID, P.COL_VIDEO, P.COL_ATHLETES, P.COL_CATEGORY,
                   P.COL_DUR, P.COL_ANNOTATIONS, P.COL_SCORE, P.COL_STATUS,
                   P.COL_ACTIONS]
        assert sorted(indices) == list(range(9))


class TestLoQueSeFueDeLaBarra:
    def test_no_quedan_las_cinco_tarjetas(self):
        """Repetian en cinco cajas lo que ahora dicen los filtros."""
        h = _hub()
        for nombre in ("_card_total", "_card_completed", "_card_in_progress",
                       "_card_pending", "_card_annotations", "_summary_bar"):
            assert not hasattr(h, nombre), nombre

    def test_ni_el_pie_que_lo_repetia_otra_vez(self):
        h = _hub()
        assert not hasattr(h, "_footer")

    def test_ni_los_cuatro_botones_de_mas(self):
        h = _hub()
        for nombre in ("_recent_btn", "_export_selected_btn",
                       "_bout_info_btn", "_compare_btn"):
            assert not hasattr(h, nombre), nombre

    def test_cargar_y_exportar_siguen(self):
        h = _hub()
        assert h._load_btn.menu() is not None      # las recientes
        assert h._export_btn.menu() is not None    # todo / seleccionados

    def test_traducir_no_revienta(self):
        """Tocaba las tarjetas y el pie; si quedara una referencia, peta."""
        h = _hub()
        h._refresh_strings()
        assert h._table.columnCount() == 9


# ======================================================================
# El identificador del combate
# ======================================================================

class TestElNombreCorto:
    @pytest.mark.parametrize("entrada,esperado", [
        ("ID30_-75KG_MALE_ASSEMAT X DUARTE POR.mp4", "ID30"),
        ("ID25_-50KG_FEMALE_E.COLLETI ITA X B. IZAGUIRRE .mp4", "ID25"),
        ("ID01_Orges(ALB)_Florin(ROU).mp4", "ID01"),
        ("id03_algo.mp4", "ID03"),
    ])
    def test_saca_el_id(self, entrada, esperado):
        from karlos_core.views.project_hub import ProjectHubView as P
        assert P._id_corto(entrada) == esperado

    def test_sin_patron_devuelve_el_nombre_sin_extension(self):
        """Mas vale largo que vacio."""
        from karlos_core.views.project_hub import ProjectHubView as P
        assert P._id_corto("AN_AO.mp4") == "AN_AO"

    def test_el_nombre_entero_sigue_en_el_tooltip(self):
        """Se acorta lo que se ve, no se pierde el dato."""
        h = _hub()
        celda = h._table.item(0, h.COL_VIDEO)
        assert celda.text() == "ID30"
        assert celda.toolTip() == "ID30_-75KG_MALE_ASSEMAT X DUARTE POR.mp4"


# ======================================================================
# El estado: se lee traducido, se filtra por lo de dentro
# ======================================================================

class TestElEstadoSeLeeEnElIdiomaDelPrograma:
    def test_la_celda_va_traducida(self):
        h = _hub([_Sesion(estado="In Progress", n=5)])
        texto = h._table.item(0, h.COL_STATUS).text()
        assert texto == h._i18n.t("hub.status_in_progress")
        assert texto != "In Progress" or h._i18n.lang == "en"

    def test_por_dentro_sigue_la_etiqueta_de_siempre(self):
        """La exportacion y los filtros leen esto, no el texto."""
        from PySide6.QtCore import Qt
        h = _hub([_Sesion(estado="In Progress", n=5)])
        guardado = h._table.item(0, h.COL_STATUS).data(Qt.ItemDataRole.UserRole)
        assert guardado == "In Progress"


class TestFiltrarPorEstado:
    def _tres(self):
        return [_Sesion(1, "ID01_a.mp4", "Pending"),
                _Sesion(2, "ID02_b.mp4", "In Progress", n=3),
                _Sesion(3, "ID03_c.mp4", "Completed", n=9)]

    def test_cada_filtro_ensena_lo_suyo(self):
        h = _hub(self._tres())
        for etiqueta, visible in (("Pending", 0), ("In Progress", 1),
                                  ("Completed", 2)):
            h._on_chip_toggled(etiqueta, h._chip_all)
            h._apply_all_filters("")
            vistas = [r for r in range(3) if not h._table.isRowHidden(r)]
            assert vistas == [visible], (etiqueta, vistas)

    def test_todas_las_ensena_todas(self):
        h = _hub(self._tres())
        h._on_chip_toggled("All", h._chip_all)
        h._apply_all_filters("")
        assert all(not h._table.isRowHidden(r) for r in range(3))

    def test_un_concluido_marcado_para_revisar_sigue_saliendo(self):
        """El fallo: la celda pone «Concluído ⚠», que nunca fue igual a
        «Completed», asi que el filtro escondia justo esos."""
        s = _Sesion(1, "ID30_x.mp4", "Completed", n=9)
        s._needs_review_reasons = ["algo raro"]
        h = _hub([s])
        assert "⚠" in h._table.item(0, h.COL_STATUS).text()
        h._on_chip_toggled("Completed", h._chip_all)
        h._apply_all_filters("")
        assert not h._table.isRowHidden(0)


class TestElRecuentoVaEnLosFiltros:
    def test_cada_chip_lleva_su_numero(self):
        h = _hub([_Sesion(1, "ID01_a.mp4", "Pending"),
                  _Sesion(2, "ID02_b.mp4", "Pending"),
                  _Sesion(3, "ID03_c.mp4", "In Progress", n=2)])
        assert h._chip_all.text().endswith("3")
        assert h._chip_pending.text().endswith("2")
        assert h._chip_in_progress.text().endswith("1")

    def test_un_filtro_vacio_no_se_puede_pulsar(self):
        """Pulsarlo dejaria la tabla en blanco sin decir por que."""
        h = _hub([_Sesion(estado="Pending")])
        assert h._chip_completed.isEnabled() is False
        assert h._chip_pending.isEnabled() is True
        assert h._chip_all.isEnabled() is True


# ======================================================================
# Los botones de cada fila
# ======================================================================

class TestLosBotonesDeLaFila:
    def _botones(self, h, fila=0):
        from PySide6.QtWidgets import QPushButton
        w = h._table.cellWidget(fila, h.COL_ACTIONS)
        return w.findChildren(QPushButton)

    def test_abrir_funciona_en_un_combate_pendiente(self):
        """El fallo: estaba apagado justo en los que hay que abrir."""
        h = _hub([_Sesion(estado="Pending")])
        _relatorio, abrir = self._botones(h)
        assert abrir.isEnabled() is True

    def test_el_relatorio_se_apaga_si_no_hay_datos(self):
        h = _hub([_Sesion(estado="Pending", n=0)])
        relatorio, _abrir = self._botones(h)
        assert relatorio.isEnabled() is False

    def test_y_se_enciende_en_cuanto_los_hay(self):
        h = _hub([_Sesion(estado="In Progress", n=4)])
        relatorio, _abrir = self._botones(h)
        assert relatorio.isEnabled() is True

    def test_la_papelera_ya_no_esta_en_la_fila(self):
        """Estaba a dos pixeles de editar y borraba la sesion."""
        h = _hub()
        assert len(self._botones(h)) == 2

    def test_pero_sigue_en_el_menu(self):
        h = _hub()
        _menu, acciones = h._construir_menu(0)
        assert h.delete_session_requested in acciones.values()


class TestElMenuRecogeLoQueBajoDeLaBarra:
    def test_datos_del_combate_y_comparar(self):
        h = _hub()
        _menu, acciones = h._construir_menu(0)
        assert h.edit_bout_info_requested in acciones.values()
        assert h.compare_evaluators_requested in acciones.values()

    def test_sin_entradas_repetidas(self):
        h = _hub()
        _menu, acciones = h._construir_menu(0)
        textos = [a.text() for a in acciones]
        assert len(textos) == len(set(textos)), textos


# ======================================================================
# ======================================================================

