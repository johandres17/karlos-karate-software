"""Configuracion comun de la suite.

El idioma se fija aqui a proposito. Los textos que ve el evaluador
pasaron al sistema de traduccion, asi que sin fijarlo los tests
dependerian de la configuracion guardada en la maquina de quien los
corre: pasarian en la de Johan y fallarian en la de cualquier otro.
"""

import os
import tempfile

# La carpeta personal de quien corre la suite no se toca: la edición guarda
# sus ajustes, su log y sus pasadas en ~/.karlos_karate, y Path.home() se
# resuelve al importar la edición. Se desvía antes de importar nada del
# programa.
_CASA = tempfile.mkdtemp(prefix="karlos_casa_")
os.environ["HOME"] = _CASA
os.environ["USERPROFILE"] = _CASA

import pytest  # noqa: E402
from PySide6 import QtCore  # noqa: E402

# Los ajustes de Karlos (idioma, carpetas recientes, tamaño de ventana) se
# guardan con QSettings("Karlitos", "KarlosAnnotator") en la cuenta de quien
# corre la suite. Sin desviarlos, cada prueba que carga una carpeta o fija
# el idioma escribia en los ajustes de verdad de Johan: el 29-09 una
# carpeta temporal quedo la primera de sus recientes, y Karlos abre al
# arrancar la mas reciente.
#
# setDefaultFormat() NO sirve: ese constructor usa siempre el formato
# nativo (lo dice la documentacion de Qt, y se comprobo). Se sustituye la
# clase: QSettings(organizacion, aplicacion) va a un INI temporal. Tiene
# que ir aqui, antes de que se importe ningun modulo de Karlos.
_AJUSTES = tempfile.mkdtemp(prefix="karlos_ajustes_")
_QSettingsReal = QtCore.QSettings


class _QSettingsDePrueba(_QSettingsReal):
    def __init__(self, *args, **kwargs):
        if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], str):
            ruta = os.path.join(_AJUSTES, f"{args[0]}__{args[1]}.ini")
            super().__init__(ruta, _QSettingsReal.Format.IniFormat, *args[2:], **kwargs)
        else:
            super().__init__(*args, **kwargs)


QtCore.QSettings = _QSettingsDePrueba

# El idioma, puesto ya en esos ajustes: algunas etiquetas (las del arbol
# de preguntas) se traducen al importar el modulo, antes de que corra
# ningun fixture. Antes salian en portugues solo porque los ajustes
# reales de Johan lo tenian guardado.
for _app in ("KarlosAnnotator", "KarlosKarate"):
    _QSettingsDePrueba("Karlitos", _app).setValue("i18n/language", "pt")

# La edicion con la que corre la suite: Karlos Karate (decision 0006).
# Despues de desviar los ajustes y antes de que ninguna prueba importe nada
# del programa.
from karlos_ediciones import karate as _karate  # noqa: E402

_karate.poner_en_marcha()


@pytest.fixture(scope="session", autouse=True)
def idioma_fijo():
    """Portugues de Brasil, que es el idioma con el que sale el Pro."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from karlos_core.utils.i18n import I18n
    I18n().set_lang("pt")
    yield


@pytest.fixture(autouse=True)
def deporte_por_defecto():
    """Cada prueba empieza con el deporte por defecto de la edicion.

    El deporte activo es estado global (el programa anota uno a la vez):
    una prueba que lo cambia no puede dejarselo puesto a la siguiente.
    """
    from karlos_core import catalogo
    catalogo.olvidar_activo()
    yield
    catalogo.olvidar_activo()


@pytest.fixture(autouse=True)
def sin_ventanas_de_otras_pruebas():
    """Las ventanas que una prueba deja abiertas no capturan las teclas de
    la siguiente.

    Varias fixtures construyen el anotador y no lo cierran, asi que al
    acabar la prueba la ventana sigue viva con TODOS sus atajos
    registrados a nivel de aplicacion. `test_pantalla_de_inicio` ya lo
    documentaba: «en la suite quedan vivas ventanas de otras pruebas con
    atajos que abren avisos modales; la suite se quedo colgada asi».

    Se noto el 16-10-2026 al dar teclas de fase al karate (decision 0008):
    el [1] de las fases llegaba tambien a una ventana que habia quedado
    abierta, y la suite se quedaba dando vueltas al 4 %. Cada archivo por
    separado pasaba.
    """
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    yield
    app = QApplication.instance()
    if app is None:
        return
    for w in list(app.topLevelWidgets()):
        try:
            # Ocultar y destruir, NUNCA close(): close() dispara el
            # closeEvent de la ventana, y varias pruebas tienen ahi dobles
            # (SimpleNamespace, grabadoras) que revientan al recibirlo.
            # Lo que hace falta es destruirla, que es lo que se lleva por
            # delante el filtro de eventos.
            w.hide()
            w.deleteLater()
        except RuntimeError:
            pass          # ya destruida por su propia prueba
    # OJO: processEvents() NO procesa los borrados diferidos. Sin esta
    # linea las ventanas siguen vivas, y con ellas el filtro de eventos
    # que cada anotador instala EN LA APLICACION (shortcut_controller,
    # `_instalar_vigilante`): se iban acumulando uno por prueba y al cabo
    # de cien cada tecla pasaba por cien filtros. Eso es lo que dejaba la
    # suite al 100 % de CPU sin avanzar.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


@pytest.fixture(autouse=True)
def cuaderno_del_completo():
    """Cada prueba empieza en el cuaderno del completo (decisión 0008).

    El cuaderno activo es estado global del gestor de sesiones, como el
    rounds.json: una prueba que se quedaba en tiempo-movimiento hacía que la
    siguiente guardara y leyera en archivos __tm sin saberlo."""
    from karlos_core.controllers.session_manager import SessionManager
    SessionManager._cuaderno = ""
    yield
    SessionManager._cuaderno = ""


@pytest.fixture(autouse=True)
def analisis_limpio():
    """Que se analiza NO se hereda de la prueba anterior.

    Vive en los QSettings, que son unos solos para toda la suite, asi que
    una prueba que elegia «time_motion» se lo dejaba puesto a la
    siguiente: `test_accion_sin_fin` fallaba o pasaba segun el orden. Se
    borra antes y despues, y cada prueba ve el de fabrica de su deporte
    (decision 0008: el karate, el integrado).
    """
    from karlos_core import identidad
    from karlos_core.views.dialogo_analisis import ANALISIS

    def _borrar():
        # `test_sin_edicion_el_programa_no_arranca` quita la edición a
        # propósito, y sin edición no hay ajustes que tocar.
        try:
            identidad.ajustes().remove(ANALISIS)
        except LookupError:
            pass

    _borrar()
    yield
    _borrar()


@pytest.fixture(autouse=True)
def pasadas_aisladas(tmp_path, monkeypatch):
    """Ninguna prueba toca el registro de pasadas de quien corre la suite.

    El rounds.json es GLOBAL (uno solo para todas las carpetas de video, en
    la carpeta de la edicion), asi que sin esto la suite escribiria en el de
    verdad: le anadiria pasadas y le cambiaria la activa. Y es el fichero
    que decide que sesion se abre y cual se guarda.

    Al desviarlo hay que sembrarlo: en el programa siempre hay una pasada
    activa (migrate_rounds la crea al arrancar) y, sin ninguna,
    get_active_round devuelve None y al abrir un combate NO se restaura
    nada de lo guardado en disco.
    """
    carpeta = tmp_path / "pasadas"
    from karlos_core.controllers.session_manager import SessionManager
    monkeypatch.setattr(SessionManager, "_GLOBAL_ROUNDS_DIR", carpeta)
    monkeypatch.setattr(SessionManager, "_GLOBAL_ROUNDS_PATH",
                        carpeta / "rounds.json")
    SessionManager._save_rounds({
        "rounds": [{"evaluator_id": "default", "occasion": 1,
                    "label": "Passagem 1", "created": "2026-01-01"}],
        "active_round_index": 0,
    })
    yield


@pytest.fixture
def como_karlos_karate():
    """La suite ya corre con Karlos Karate: devuelve su edición."""
    def poner():
        from karlos_ediciones import karate
        return karate.EDICION
    return poner
