"""Las dependencias van en un solo sentido (decisiones 0004 y 0006).

- El núcleo (``karlos_core``) no importa ningún paquete de deporte ni
  ninguna edición: pide el deporte al catálogo, y la edición que arranca
  pone los suyos. Solo ``karlos_ediciones`` nombra paquetes.
- El contrato (deporte, catálogo y formato) no depende del resto del
  programa.

Lo que todavía no cumple la regla está en ``PENDIENTES``, y la lista solo
puede encoger: la prueba falla si aparece una importación nueva y también
si una pendiente desaparece del código y sigue en la lista (así la lista
dice siempre la verdad sobre lo que queda de la fase F3).

Cuentan también las importaciones dentro de funciones: diferir una
importación no quita la dependencia.

Lo mismo con los «AKA» y «AO» escritos a mano en el núcleo: son los
códigos del formato de sesión y se nombran con ``karlos_core.formato``
(F3.5). Los que quedan están contados por módulo en ``LITERALES_AKA_AO``,
y la cuenta solo puede bajar. Y con las ramas que preguntan por un deporte
concreto (``RAMAS_POR_DEPORTE``, F4.3).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]
ANOTADOR = SRC / "karlos_core"

# Lo que vive fuera del núcleo y el núcleo no puede importar: el paquete del
# deporte y la edición.
FUERA_DEL_NUCLEO = ("karlos_karate", "karlos_ediciones")

# (módulo del núcleo, módulo de fuera que importa) que quedan por invertir.
# F3 los quitó todos; la lista se queda para que la prueba diga la verdad.
PENDIENTES: set[tuple[str, str]] = set()

# Los módulos del karate que la fase F4 mudó a karlos_karate (decisión 0005),
# con su ruta de antes en el núcleo.
MUDADOS = {
    "config/karate_config": "karate_config",
    "models/guided_tree": "guided_tree",
    "controllers/csv_combate": "csv_combate",
    "controllers/export_manager": "export_manager",
    "views/match_report": "match_report",
    "utils/pdf_report_generator": "pdf_report_generator",
    "views/relatorio_treinador": "relatorio_treinador",
    "utils/metricas_combate": "metricas_combate",
}

# Ramas del tipo `if deporte == "karate"` que quedan en el núcleo: los campos
# de los datos del combate, la guardia y lo que solo tiene el karate (el
# panel). Se van cuando el contrato tenga con qué sustituirlas; hasta
# entonces la cuenta solo puede bajar.
RAMAS_POR_DEPORTE = {
    "karlos_core.controllers.annotation_flow_controller": 1,
    # El 7-10-2026 se fue la del rótulo del asalto: los asaltos son del
    # reglamento de cada deporte (`Reglamento.asaltos`), no del kickboxing.
    "karlos_core.controllers.anotador.anotacion": 0,
    "karlos_core.views.annotation_panel": 1,
    "karlos_core.views.annotations_table": 5,
    "karlos_core.views.bout_info_popup": 6,
    "karlos_core.views.edit_annotation_popup": 3,
}

# Textos «AKA»/«AO» que quedan en cada módulo del núcleo (6-10-2026, 161).
# Se quitan al tocar cada módulo: usar PRIMERO, SEGUNDO o rival() de
# karlos_core.formato, o la etiqueta del deporte si es para enseñarla.
# Los 30 del controlador principal se repartieron al partirlo (F3.7).
LITERALES_AKA_AO = {
    "karlos_core.controllers.anotador.anotacion": 2,
    "karlos_core.controllers.anotador.exportacion": 7,
    "karlos_core.controllers.anotador.sesiones": 7,
    "karlos_core.controllers.fight_session_controller": 9,
    "karlos_core.models.technique": 2,
    "karlos_core.utils.config_loader": 2,
    "karlos_core.views.annotation_panel": 8,
    "karlos_core.views.annotations_table": 7,
    "karlos_core.views.detail_popup": 4,
    "karlos_core.views.edit_annotation_popup": 3,
    "karlos_core.views.fight_end_popup": 4,
    "karlos_core.views.log_compacto": 6,
    "karlos_core.views.project_hub": 8,
    "karlos_core.views.referee_stop_popup": 1,
    "karlos_core.views.timeline_overlay": 7,
    "karlos_core.views.video_panel": 1,
    "karlos_core.views.zoom_bar": 2,
}


def _nombre(fichero: Path) -> str:
    partes = list(fichero.relative_to(SRC).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes.pop()
    return ".".join(partes)


def _importa(fichero: Path) -> set[str]:
    """Todos los módulos que importa un fichero, también dentro de funciones.

    ``from paquete import x`` cuenta como ``paquete`` y como ``paquete.x``
    (x puede ser un módulo); lo que no exista como módulo no molesta.
    """
    yo = _nombre(fichero)
    paquete = yo if fichero.name == "__init__.py" else yo.rpartition(".")[0]
    salida = set()
    for n in ast.walk(ast.parse(fichero.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            salida.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if n.level:
                raiz = paquete.split(".")
                raiz = raiz[:len(raiz) - (n.level - 1)]
                base = ".".join(raiz + ([base] if base else []))
            salida.add(base)
            salida.update(f"{base}.{a.name}" for a in n.names)
    return salida


def _modulos(raiz: Path):
    for f in sorted(raiz.rglob("*.py")):
        if "tests" not in f.relative_to(SRC).parts:
            yield _nombre(f), f


def _es_de_fuera(modulo: str) -> bool:
    return modulo.split(".")[0] in FUERA_DEL_NUCLEO


def _violaciones() -> set[tuple[str, str]]:
    salida = set()
    for yo, f in _modulos(ANOTADOR):
        for m in _importa(f):
            if _es_de_fuera(m):
                salida.add((yo, m))
    return salida


# El contrato que comparten el núcleo y los paquetes de deporte.
CONTRATO = {"karlos_core.deporte", "karlos_core.catalogo", "karlos_core.formato"}


def test_el_contrato_no_depende_del_resto_del_programa():
    """Deporte, catálogo y formato solo se importan entre sí: un paquete de
    deporte los usa sin arrastrar el programa entero (decisión 0006)."""
    malas = {(yo, m) for yo, f in _modulos(ANOTADOR) if yo in CONTRATO for m in _importa(f)
             if m.split(".")[0] in ("karlos_core", *FUERA_DEL_NUCLEO)
             and m != "karlos_core" and m not in CONTRATO and m.rpartition(".")[0] not in CONTRATO}
    assert not malas, f"el contrato importa: {sorted(malas)}"


def test_ninguna_importacion_nueva_del_karate_en_el_nucleo():
    nuevas = _violaciones() - PENDIENTES
    assert not nuevas, (
        "El núcleo importa algo de un paquete o de una edición; pídeselo al catálogo "
        f"(karlos_core.catalogo): {sorted(nuevas)}")


def test_la_lista_de_pendientes_dice_la_verdad():
    resueltas = PENDIENTES - _violaciones()
    assert not resueltas, f"Ya no existen; quítalas de PENDIENTES: {sorted(resueltas)}"


def test_el_nucleo_no_registra_deportes_por_su_cuenta():
    """Los pone la edición que arranca (decisión 0006): ninguna llamada a
    registrar() en el núcleo salvo la que hace la propia edición."""
    llamadas = []
    for yo, f in _modulos(ANOTADOR):
        if yo in ("karlos_core.catalogo", "karlos_core.identidad"):
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
                continue
            receptor = n.func.value.id if isinstance(n.func.value, ast.Name) else ""
            if n.func.attr in ("registrar_en", "poner_en_marcha") or (
                    n.func.attr == "registrar" and receptor in ("catalogo", "CATALOGO")):
                llamadas.append(f"{yo}:{n.lineno}")
    assert not llamadas, llamadas


def _literales_aka_ao(fichero: Path) -> int:
    """Textos del código (no docstrings) con AKA o AO como palabra."""
    arbol = ast.parse(fichero.read_text(encoding="utf-8"))
    docs = {id(n.body[0].value) for n in ast.walk(arbol)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and n.body and isinstance(n.body[0], ast.Expr)
            and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
    return sum(1 for n in ast.walk(arbol)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and id(n) not in docs and re.search(r"\b(AKA|AO)\b", n.value))


def test_los_aka_ao_escritos_a_mano_solo_bajan():
    actual = {}
    for yo, f in _modulos(ANOTADOR):
        # formato es donde se definen: ahí sí van escritos.
        if yo == "karlos_core.formato":
            continue
        n = _literales_aka_ao(f)
        if n:
            actual[yo] = n
    suben = {m: (LITERALES_AKA_AO.get(m, 0), n) for m, n in actual.items()
             if n > LITERALES_AKA_AO.get(m, 0)}
    assert not suben, ("AKA/AO nuevos en el núcleo (antes, ahora); usa "
                       f"karlos_core.formato: {suben}")
    bajan = {m: (n, actual.get(m, 0)) for m, n in LITERALES_AKA_AO.items()
             if actual.get(m, 0) < n}
    assert not bajan, f"Han bajado; apunta la cuenta nueva en LITERALES_AKA_AO: {bajan}"


def test_el_karate_vive_en_su_paquete():
    """Nada de lo que F4 mudó vuelve a karlos_core."""
    for viejo, nuevo in MUDADOS.items():
        assert not (ANOTADOR / f"{viejo}.py").exists(), f"{viejo}.py ha vuelto al núcleo"
        assert (SRC / "karlos_karate" / f"{nuevo}.py").exists(), nuevo


def _ramas_por_deporte(fichero: Path) -> int:
    """Comparaciones con el id de un deporte («== "karate"», «in ("kickboxing", …)»)."""
    deportes = {"karate", "kickboxing", "taekwondo", "box"}

    def nombra(n) -> bool:
        if isinstance(n, ast.Constant):
            return n.value in deportes
        if isinstance(n, (ast.Tuple, ast.List, ast.Set)):
            return any(isinstance(e, ast.Constant) and e.value in deportes for e in n.elts)
        return False

    return sum(1 for n in ast.walk(ast.parse(fichero.read_text(encoding="utf-8")))
               if isinstance(n, ast.Compare)
               and any(isinstance(o, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for o in n.ops)
               and any(nombra(x) for x in (n.left, *n.comparators)))


def test_las_ramas_por_deporte_del_nucleo_solo_bajan():
    actual = {}
    for yo, f in _modulos(ANOTADOR):
        n = _ramas_por_deporte(f)
        if n:
            actual[yo] = n
    suben = {m: (RAMAS_POR_DEPORTE.get(m, 0), n) for m, n in actual.items()
             if n > RAMAS_POR_DEPORTE.get(m, 0)}
    assert not suben, ("Ramas nuevas por deporte en el núcleo (antes, ahora); lo del "
                       f"deporte va en su paquete: {suben}")
    bajan = {m: (n, actual.get(m, 0)) for m, n in RAMAS_POR_DEPORTE.items()
             if actual.get(m, 0) < n}
    assert not bajan, f"Han bajado; apunta la cuenta nueva en RAMAS_POR_DEPORTE: {bajan}"
