"""Session persistence manager for KARLOS ANNOTATOR.

Handles auto-saving and restoring annotation sessions to/from JSON files.
Supports the two-pass athlete workflow: AKA complete → AO complete.
"""

from __future__ import annotations

import json
import logging
import os as _os
import shutil
import uuid
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path
from time import time as _time
from typing import Any, Optional

from karlos_core.models.annotation import Annotation
from karlos_core.identidad import CARPETA_POR_DEFECTO


class SessionManager:
    """Persists and restores annotation sessions as JSON snapshot files.

    A session file (.karlos) captures the complete state of an annotation
    session: video path, bout info, fight markers, all annotation records,
    and the current athlete pass.

    Each session gets a unique session_id (UUID4) on first save, and a
    save_counter that increments on each write, allowing the system to
    detect overwrites or restore the latest version.

    Attributes:
        _last_save_time: Monotonic timestamp of last save (debounce).
    """

    SESSION_EXT = ".karlos"

    # ── El cuaderno activo (decisión 0008, Johan 19-10-2026) ──
    # Cada modo tiene sus propias anotaciones del mismo vídeo: «si abro el
    # vídeo con tiempo-movimiento, anoto y salgo, y luego lo abro en
    # técnico-táctico, no tienen que aparecer las del tiempo-movimiento».
    # El completo sigue en el archivo de siempre (<video>__<ev>__<n>.karlos):
    # los combates del estudio y la 1.0 no notan nada. Los otros dos llevan
    # un sufijo: __tm y __tt. Todas las rutas salen de aquí, así que
    # guardar, abrir, el bloqueo y las copias van solos al cuaderno del
    # modo en que se está.
    _cuaderno: str = ""
    _SUFIJOS = {"time_motion": "tm", "technical_tactical": "tt"}

    @staticmethod
    def poner_cuaderno(analisis: str) -> None:
        """El cuaderno de ese análisis pasa a ser el activo."""
        SessionManager._cuaderno = SessionManager._SUFIJOS.get(analisis or "", "")

    @staticmethod
    def cuaderno() -> str:
        """El sufijo del cuaderno activo: "" (completo), "tm" o "tt"."""
        return SessionManager._cuaderno

    @staticmethod
    def migrar_al_cuaderno(video_path: str, evaluator_id: str = "default",
                           occasion: int = 1) -> bool:
        """Las sesiones de antes de los cuadernos, a su cuaderno.

        Hasta el 19-10-2026 un combate de tiempo-movimiento o técnico-táctico
        se guardaba en el archivo de siempre, con
        su análisis escrito en bout_info. Si el cuaderno activo no tiene
        archivo y el de siempre es de ESE análisis, se mueve a su cuaderno,
        dejando antes una copia en backups/. Un archivo de completo (o sin
        análisis escrito, como los del estudio) no se mueve nunca.
        """
        cuaderno = SessionManager._cuaderno
        if not cuaderno:
            return False
        destino = SessionManager._session_path(video_path, evaluator_id, occasion)
        if destino.exists():
            return False
        video = Path(video_path)
        origen = video.parent / ".karlos_sessions" / (
            f"{video.stem}__{evaluator_id}__{occasion}{SessionManager.SESSION_EXT}")
        if not origen.exists():
            return False
        try:
            datos = json.loads(origen.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        analisis = (datos.get("bout_info") or {}).get("analysis", "")
        if SessionManager._SUFIJOS.get(analisis) != cuaderno:
            return False
        # La etiqueta sola no basta: tiene que decirlo también el contenido.
        # ID33 del estudio llevaba «time_motion» escrito (una versión de
        # desarrollo del 15-10 lo ponía por defecto) con sus 160 acciones
        # del completo; moverlo lo habría sacado del cuaderno del completo y
        # de la 1.0 (19-10-2026). Tiempo-movimiento: solo filas PHASE.
        # Técnico-táctico: sin fases y cada fila un instante (inicio = fin).
        filas = datos.get("annotations") or []
        if cuaderno == "tm":
            propio = all(f.get("category") == "PHASE" for f in filas)
        else:
            propio = all(f.get("category") != "PHASE"
                         and f.get("f_start") == f.get("f_end") for f in filas)
        if not propio:
            return False
        SessionManager._backup_version(origen)
        _os.replace(origen, destino)
        return True

    # ── GLOBAL rounds.json path — shared across ALL video folders ──
    _GLOBAL_ROUNDS_DIR = CARPETA_POR_DEFECTO   # la edición pone la suya (decisión 0006)
    _GLOBAL_ROUNDS_PATH = _GLOBAL_ROUNDS_DIR / "rounds.json"

    def __init__(self) -> None:
        """Initialize the session manager."""
        self._last_save_time: float = 0.0
        self._save_counter: int = 0
        self._session_id: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_session(
        self,
        video_path: str,
        bout_info: dict[str, str],
        fight_start: int | None,
        fight_end: int | None,
        records: list[Annotation],
        current_athlete: str = "",
        current_pass: int = 0,
        sequence_counter: int = 0,
        current_sequence_id: str = "",
        last_annotation_end: int = 0,
        last_technique_name: str = "",
        aka_fouls: int = 0,
        ao_fouls: int = 0,
        evaluator_id: str = "default",
        occasion: int = 1,
        concluido: bool | None = None,
        asaltos: list[dict[str, Any]] | None = None,
        fases: list[dict[str, Any]] | None = None,
        asaltos_por_atleta: dict[str, list[dict[str, Any]]] | None = None,
    ) -> str:
        """Persist the current annotation session to a JSON file.

        Each save increments an internal counter and embeds a unique
        session_id (generated once on first write) so consumers can
        detect version conflicts or stale data.

        Args:
            video_path: Path to the loaded video file.
            bout_info: Dict with bout metadata from BoutInfoPopup.
            fight_start: Fight start frame index.
            fight_end: Fight end frame index.
            records: List of Annotation records.
            current_athlete: Currently active athlete label ("AKA" or "AO").
            current_pass: Current analysis pass (1=AKA, 2=AO).
            sequence_counter: Sequence-ID counter for ML temporal grouping.
            current_sequence_id: Active sequence ID string (e.g. "SEQ_003").
            last_annotation_end: End frame of the last annotated technique.
            last_technique_name: Name of the last annotated technique.

        Returns:
            Path to the saved session file.
        """
        if not self._session_id:
            self._session_id = str(uuid.uuid4())
        self._save_counter += 1

        session_path = self._session_path(video_path, evaluator_id, occasion)
        data: dict[str, Any] = {
            "version": "1.0",
            # «version» se queda en "1.0": el lector rechaza cualquier otro
            # valor. Lo que significan los datos lo dice «esquema», que los
            # lectores de antes ignoran (decisión 0008).
            "esquema": __import__("karlos_core.formato", fromlist=["ESQUEMA"]).ESQUEMA,
            "programa": __import__("karlos_core.identidad", fromlist=["programa"]).programa(),
            "session_id": self._session_id,
            "save_counter": self._save_counter,
            "video_path": video_path,
            "bout_info": bout_info,
            "fight_start": fight_start,
            "fight_end": fight_end,
            # Dónde empieza y acaba cada asalto. Son del vídeo: se guardan
            # con la sesión para no volver a marcarlos nunca.
            "asaltos": list(asaltos or []),
            # En el tiempo-movimiento cada atleta marca sus asaltos
            # (el especialista, 12-10-2026): {atleta: [asaltos]}.
            "asaltos_por_atleta": dict(asaltos_por_atleta or {}),
            # Las fases marcadas del tiempo-movimiento (fighting /
            # non-fighting / stoppage), también del vídeo.
            "fases": list(fases or []),
            "current_athlete": current_athlete,
            "current_pass": current_pass,
            "sequence_counter": sequence_counter,
            "current_sequence_id": current_sequence_id,
            "last_annotation_end": last_annotation_end,
            "last_technique_name": last_technique_name,
            "aka_fouls": aka_fouls,
            "ao_fouls": ao_fouls,
            "annotations": [self._annotation_to_dict(r) for r in records],
            "last_saved": datetime.now().isoformat(),
            "evaluator_id": evaluator_id,
            "occasion": occasion,
            # Lo pone quien anota, no el programa: None = dejar lo que haya.
            "concluido": SessionManager._resolver_concluido(
                session_path, concluido),
        }
        session_path.parent.mkdir(parents=True, exist_ok=True)

        # ── Atomic save: write to .tmp first, then os.replace ──
        tmp_path = session_path.with_suffix(session_path.suffix + ".tmp")
        json_text = json.dumps(data, indent=2, ensure_ascii=False)
        tmp_path.write_text(json_text, encoding="utf-8")

        # Backup previous version before replacing (keep last 10)
        if session_path.exists():
            self._backup_version(session_path)

        _os.replace(tmp_path, session_path)  # atomic on POSIX
        return str(session_path)

    def load_session(self, video_path: str) -> dict[str, Any] | None:
        """Load a saved session for the given video, if it exists.

        Tries the new format first, then falls back to the legacy
        format for sessions saved before the multi-evaluator upgrade.

        Args:
            video_path: Path to the video file.

        Returns:
            Dict with session data, or None if no session exists or it's corrupt.
        """
        return self._load_from_path(self._find_session_file(video_path))

    def has_session(self, video_path: str) -> bool:
        """Check whether a saved session exists for the given video.

        Checks both new (<evaluator>__<occasion>) and legacy formats.

        Args:
            video_path: Path to the video file.

        Returns:
            True if a session file exists.
        """
        return self._find_session_file(video_path) is not None

    def delete_session(self, video_path: str) -> None:
        """Delete the session file after a successful export.

        Args:
            video_path: Path to the video file.
        """
        session_path = self._find_session_file(video_path)
        if session_path is not None:
            session_path.unlink()

    # ------------------------------------------------------------------
    # Concluido y borrado, sobre el fichero de la pasada activa
    # ------------------------------------------------------------------

    @staticmethod
    def _resolver_concluido(ruta: Path, valor: bool | None) -> bool:
        """El valor pedido, o el que ya estuviera guardado si no se pide.

        Cada autoguardado pasa por aqui: sin esto, guardar una anotacion
        borraria la marca que puso Johan.
        """
        if valor is not None:
            return bool(valor)
        previo = SessionManager._read_session_json(ruta) if ruta.exists() else None
        return bool((previo or {}).get("concluido", False))

    @staticmethod
    def ruta_de_sesion(video_path: str) -> Path | None:
        """El fichero de la pasada activa, o None si no hay ninguno.

        Misma resolucion que usa el Hub al releer del disco: pasada
        activa, y solo en la primera se mira el formato antiguo.
        """
        activa = SessionManager.get_active_round(video_path)
        if activa is None:
            return None
        ruta = SessionManager._session_path(
            video_path, activa["evaluator_id"], activa["occasion"])
        if ruta.exists():
            return ruta
        if activa["occasion"] == 1:
            antigua = SessionManager._old_session_path(video_path)
            if antigua.exists():
                return antigua
        return None

    @staticmethod
    def _reescribir(ruta: Path, datos: dict[str, Any]) -> None:
        """Sustituir el fichero entero, guardando antes una copia."""
        tmp = ruta.with_suffix(ruta.suffix + ".tmp")
        tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        SessionManager._backup_version(ruta)
        _os.replace(tmp, ruta)

    @staticmethod
    def esta_concluido(video_path: str) -> bool:
        """Si Johan marco este combate como terminado."""
        ruta = SessionManager.ruta_de_sesion(video_path)
        if ruta is None:
            return False
        datos = SessionManager._read_session_json(ruta)
        return bool((datos or {}).get("concluido", False))

    @staticmethod
    def marcar_concluido(video_path: str, valor: bool = True) -> bool:
        """Poner o quitar la marca de terminado. False si no hay fichero."""
        ruta = SessionManager.ruta_de_sesion(video_path)
        if ruta is None:
            return False
        datos = SessionManager._read_session_json(ruta)
        if datos is None:
            return False
        datos["concluido"] = bool(valor)
        SessionManager._reescribir(ruta, datos)
        return True

    @staticmethod
    def borrar_anotaciones(video_path: str,
                           conservar_paradas: bool = False) -> int:
        """Vaciar las anotaciones guardadas. Devuelve cuantas quito.

        Con conservar_paradas se quedan las REFEREE STOP: son del combate
        y valen para cualquier pasada.

        Los limites del combate (fight_start / fight_end) no son
        anotaciones y no se tocan. Las faltas si, porque se cuentan de
        lo anotado, y la marca de concluido tambien: lo que queda ya no
        es lo que Johan dio por terminado.
        """
        ruta = SessionManager.ruta_de_sesion(video_path)
        if ruta is None:
            return 0
        datos = SessionManager._read_session_json(ruta)
        if datos is None:
            return 0
        antes = list(datos.get("annotations", []))
        if conservar_paradas:
            quedan = [a for a in antes if a.get("category") == "REFEREE STOP"]
        else:
            quedan = []
        quitadas = len(antes) - len(quedan)
        if quitadas == 0 and not datos.get("concluido"):
            return 0
        datos["annotations"] = quedan
        datos["aka_fouls"] = 0
        datos["ao_fouls"] = 0
        datos["concluido"] = False
        # Y las pasadas: vaciado, el combate vuelve a la primera. Se
        # quedaba en la que iba, y al reabrirlo la [F] empezaba la
        # segunda.
        datos["current_pass"] = 0
        SessionManager._reescribir(ruta, datos)
        return quitadas

    # ------------------------------------------------------------------
    # Internal: session file resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _find_session_file(video_path: str) -> Path | None:
        """Find the session file for a video, trying new then legacy format.

        Returns the Path if found, or None if no session exists.
        """
        new_path = SessionManager._session_path(video_path)
        if new_path.exists():
            return new_path
        legacy_path = SessionManager._old_session_path(video_path)
        if legacy_path.exists():
            return legacy_path
        return None

    @staticmethod
    def _load_from_path(session_path: Path | None) -> dict[str, Any] | None:
        """Load session data from a specific path.

        If the file exists but is corrupt or unreadable, falls back to
        the most recent readable backup in the sibling backups/ folder
        (written by _backup_version on every save), so an interrupted
        write never loses the whole session.
        """
        if session_path is None:
            return None
        data = SessionManager._read_session_json(session_path)
        if data is not None:
            return data
        if not session_path.exists():
            return None

        # Main file present but corrupt → newest readable backup wins.
        log = logging.getLogger(__name__)
        backups_dir = session_path.parent / "backups"
        candidates = (
            sorted(
                backups_dir.glob(f"{session_path.stem}__*{SessionManager.SESSION_EXT}"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if backups_dir.is_dir()
            else []
        )
        for backup in candidates:
            data = SessionManager._read_session_json(backup)
            if data is not None:
                log.warning(
                    "Session file %s is corrupt — restored from backup %s",
                    session_path.name, backup.name,
                )
                return data
        log.error(
            "Session file %s is corrupt and no readable backup was found",
            session_path.name,
        )
        return None

    @staticmethod
    def _read_session_json(path: Path) -> dict[str, Any] | None:
        """Read one session JSON file; None if missing, corrupt or wrong version."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") != "1.0":
                return None
            return data
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    # ------------------------------------------------------------------
    # Annotation (de)serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _annotation_to_dict(ann: Annotation) -> dict[str, Any]:
        """Serialize an Annotation to a JSON-safe dict.

        Args:
            ann: Annotation instance.

        Returns:
            Dict with all annotation fields.
        """
        return asdict(ann)

    @staticmethod
    def annotation_from_dict(data: dict[str, Any]) -> Annotation:
        """Deserialize a dict back into an Annotation instance.

        Args:
            data: Dict from _annotation_to_dict.

        Returns:
            Reconstructed Annotation.
        """
        # Remove keys that are not dataclass fields (e.g. properties like 'stance', 'target')
        valid_fields = {f.name for f in fields(Annotation)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return Annotation(**filtered)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _session_path(
        video_path: str,
        evaluator_id: str = "default",
        occasion: int = 1,
    ) -> Path:
        """Derive the session file path, scoped by evaluator and occasion.

        Format: .karlos_sessions/<video_stem>__<evaluator_id>__<occasion>.karlos

        Old-format files (just <video_stem>.karlos) are treated as
        evaluator_id="default", occasion=1 for backward compatibility.

        Args:
            video_path: Path to the video file.
            evaluator_id: Normalized evaluator identifier (lowercase, underscores).
            occasion: Occasion number (1-indexed).

        Returns:
            Path to the .karlos session file.
        """
        video = Path(video_path)
        sessions_dir = video.parent / ".karlos_sessions"
        sufijo = f"__{SessionManager._cuaderno}" if SessionManager._cuaderno else ""
        return sessions_dir / f"{video.stem}__{evaluator_id}__{occasion}{sufijo}{SessionManager.SESSION_EXT}"

    @staticmethod
    def _old_session_path(video_path: str) -> Path:
        """Legacy session file path (pre-Fase-1, no evaluator/occasion).

        Used for backward-compat detection only — existing files with
        the old naming scheme are treated as evaluator_id="default",
        occasion=1.
        """
        # El formato viejo es de antes de los cuadernos: solo del completo.
        # Con otro cuaderno activo no hay «viejo» al que volver.
        if SessionManager._cuaderno:
            return SessionManager._session_path(video_path)
        video = Path(video_path)
        sessions_dir = video.parent / ".karlos_sessions"
        return sessions_dir / f"{video.stem}{SessionManager.SESSION_EXT}"

    @staticmethod
    def _normalize_evaluator(evaluator_name: str) -> str:
        """Normalize an evaluator name for use as a filename segment.

        'Johan Robalino' → 'johan_robalino'
        Empty string → 'default'
        """
        if not evaluator_name or not evaluator_name.strip():
            return "default"
        return evaluator_name.strip().lower().replace(" ", "_")

    @staticmethod
    def _backup_version(session_path: Path, max_backups: int = 10) -> None:
        """Copy the current version to a timestamped backup, keeping only the last N."""
        backups_dir = session_path.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)

        stem = session_path.stem
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backups_dir / f"{stem}__{ts}{SessionManager.SESSION_EXT}"
        shutil.copy2(session_path, backup_path)

        # Prune old backups (keep only the most recent max_backups)
        siblings = sorted(
            backups_dir.glob(f"{stem}__*{SessionManager.SESSION_EXT}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in siblings[max_backups:]:
            old.unlink(missing_ok=True)

    @staticmethod
    def session_lock_path(video_path: str, evaluator_id: str = "default", occasion: int = 1) -> Path:
        """Return the path to the lock file for a session."""
        return SessionManager._session_path(video_path, evaluator_id, occasion).with_suffix(".lock")

    @staticmethod
    def acquire_lock(video_path: str, evaluator_id: str, occasion: int) -> bool:
        """Create a lock file. Returns True if lock was acquired."""
        lock_path = SessionManager.session_lock_path(video_path, evaluator_id, occasion)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock_path.write_text(str(int(_time())), encoding="utf-8")
            return True
        except OSError:
            return False

    @staticmethod
    def release_lock(video_path: str, evaluator_id: str, occasion: int) -> None:
        """Remove the lock file."""
        lock_path = SessionManager.session_lock_path(video_path, evaluator_id, occasion)
        lock_path.unlink(missing_ok=True)

    @staticmethod
    def has_stale_lock(video_path: str, evaluator_id: str, occasion: int) -> bool:
        """Check whether a lock file exists (indicating a previous unclean shutdown)."""
        return SessionManager.session_lock_path(video_path, evaluator_id, occasion).exists()

    @staticmethod
    def list_sessions(video_path: str) -> list[dict[str, Any]]:
        """Discover all saved sessions for a video file.

        Scans the .karlos_sessions directory for files matching both the
        new pattern (<stem>__<evaluator>__<occasion>.karlos) and the
        legacy pattern (<stem>.karlos).

        Returns a list of dicts sorted by evaluator_id then occasion:
            evaluator_id, occasion, path, annotation_count, bout_info
        """
        video = Path(video_path)
        sessions_dir = video.parent / ".karlos_sessions"
        if not sessions_dir.exists():
            return []

        results: list[dict[str, Any]] = []
        prefix = f"{video.stem}__"
        legacy_name = f"{video.stem}{SessionManager.SESSION_EXT}"

        for f in sessions_dir.glob("*.karlos"):
            fname = f.name
            sufijo = f"__{SessionManager._cuaderno}" if SessionManager._cuaderno else ""
            if fname == legacy_name and not sufijo:
                # Legacy format → evaluator="default", occasion=1
                results.append({
                    "evaluator_id": "default",
                    "occasion": 1,
                    "path": str(f),
                    "is_legacy": True,
                })
            elif fname.startswith(prefix) and fname.endswith(SessionManager.SESSION_EXT):
                # New format: <stem>__<evaluator>__<occasion>.karlos
                core = fname[len(prefix):-len(SessionManager.SESSION_EXT)]
                # Solo los del cuaderno activo (decisión 0008): en el completo,
                # los que no llevan sufijo; en los otros, los del suyo.
                if sufijo:
                    if not core.endswith(sufijo):
                        continue
                    core = core[:-len(sufijo)]
                elif core.endswith(("__tm", "__tt")):
                    continue
                parts = core.rsplit("__", 1)
                if len(parts) == 2:
                    evaluator, occasion_str = parts
                    try:
                        occasion = int(occasion_str)
                    except ValueError:
                        continue
                    results.append({
                        "evaluator_id": evaluator,
                        "occasion": occasion,
                        "path": str(f),
                        "is_legacy": False,
                    })

        results.sort(key=lambda r: (r["evaluator_id"], r["occasion"]))

        # Enrich with annotation count and bout_info
        for r in results:
            try:
                data = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
                r["annotation_count"] = len(data.get("annotations", []))
                r["bout_info"] = data.get("bout_info", {})
            except (json.JSONDecodeError, OSError):
                r["annotation_count"] = 0
                r["bout_info"] = {}

        return results

    # ------------------------------------------------------------------
    # GLOBAL Round management (multi-evaluator, multi-occasion)
    #
    # rounds.json lives at ~/.karlos_annotator/rounds.json — ONE file
    # shared across ALL video folders. This avoids the per-folder
    # inconsistency problem where switching rounds in folder A leaves
    # folder B still showing the old round's data.
    # ------------------------------------------------------------------

    @staticmethod
    def _load_rounds() -> dict[str, Any]:
        """Load the GLOBAL rounds.json, returning {'rounds': [...], 'active_round_index': 0}.

        If the file does not exist, returns empty defaults.
        """
        rp = SessionManager._GLOBAL_ROUNDS_PATH
        if not rp.exists():
            return {"rounds": [], "active_round_index": -1}
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"rounds": [], "active_round_index": -1}
            return {
                "rounds": data.get("rounds", []),
                "active_round_index": data.get("active_round_index", -1),
            }
        except (json.JSONDecodeError, OSError):
            return {"rounds": [], "active_round_index": -1}

    @staticmethod
    def _save_rounds(rounds_data: dict[str, Any]) -> None:
        """Persist the GLOBAL rounds.json atomically (tmp → rename)."""
        rp = SessionManager._GLOBAL_ROUNDS_PATH
        rp.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = rp.with_suffix(rp.suffix + ".tmp")
        json_text = json.dumps(rounds_data, indent=2, ensure_ascii=False)
        tmp_path.write_text(json_text, encoding="utf-8")
        _os.replace(tmp_path, rp)

    @staticmethod
    def _scan_all_folders_for_rounds() -> set[tuple[str, int]]:
        """Walk all known .karlos_sessions directories to discover evaluator/occasion pairs.

        Searches the parent directory of any video_path we've seen, plus
        common locations. This is used during migration to build the
        initial global rounds list from existing .karlos files.
        """
        seen: set[tuple[str, int]] = set()
        # Start from home directory — walk up to 3 levels deep looking for .karlos_sessions
        home = Path.home()
        for root, dirs, _ in _os.walk(home):
            # Limit depth to 3 levels from home for performance
            depth = len(Path(root).relative_to(home).parts)
            if depth > 3:
                del dirs[:]  # don't recurse deeper
                continue
            sessions_dir = Path(root) / ".karlos_sessions"
            if not sessions_dir.exists():
                continue
            for f in sessions_dir.glob("*.karlos"):
                fname = f.name
                if "__" not in fname.rsplit(".", 1)[0]:
                    # Legacy format
                    seen.add(("default", 1))
                    continue
                core = fname[: -len(SessionManager.SESSION_EXT)]
                parts = core.rsplit("__", 1)
                if len(parts) >= 2:
                    evaluator = parts[-2] if parts[-2] != parts[-1] else parts[-1].rsplit("__", 1)[0]
                    # Actually, let's parse more carefully:
                    # Format: <stem>__<evaluator>__<occasion>.karlos
                    # Splitting by "__" gives at least 3 parts
                    all_parts = core.split("__")
                    if len(all_parts) >= 3:
                        evaluator = all_parts[-2]
                        try:
                            occasion = int(all_parts[-1])
                        except ValueError:
                            continue
                        seen.add((evaluator, occasion))
        return seen

    @staticmethod
    def migrate_rounds(video_path: str) -> dict[str, Any]:
        """Scan existing .karlos sessions and create a default round if none exist.

        IDEMPOTENT: if rounds.json already exists with at least one round,
        this is a no-op — it returns the current state without touching
        anything. This is safe to call every time the app starts or a
        folder is loaded.

        Legacy sessions (evaluator_id="default" or old-format <stem>.karlos)
        are mapped to a round: {"evaluator_id": "default", "occasion": 1,
        "label": "Johan Robalino — Pasada 1"}.

        Returns the rounds data dict after migration.
        """
        rounds_data = SessionManager._load_rounds()
        if rounds_data["rounds"]:
            return rounds_data  # IDEMPOTENT: already has rounds, nothing to migrate

        # Scan for existing sessions to build initial rounds list
        seen = SessionManager._scan_all_folders_for_rounds()

        # Also scan the specific video's folder (for the common case)
        video = Path(video_path)
        sessions_dir = video.parent / ".karlos_sessions"
        if sessions_dir.exists():
            for f in sessions_dir.glob("*.karlos"):
                fname = f.name
                legacy_name = f"{video.stem}{SessionManager.SESSION_EXT}"
                if fname == legacy_name:
                    seen.add(("default", 1))
                    continue
                if "__" not in fname:
                    continue
                core = fname[: -len(SessionManager.SESSION_EXT)]
                all_parts = core.split("__")
                if len(all_parts) >= 3:
                    evaluator = all_parts[-2]
                    try:
                        occasion = int(all_parts[-1])
                    except ValueError:
                        continue
                    seen.add((evaluator, occasion))

        if not seen:
            # No sessions found at all → create a default empty round
            label = "Johan Robalino — Pasada 1"
            rounds_data = {
                "rounds": [{
                    "evaluator_id": "default",
                    "occasion": 1,
                    "label": label,
                    "created": datetime.now().isoformat(),
                }],
                "active_round_index": 0,
            }
            SessionManager._save_rounds(rounds_data)
            return rounds_data

        # Create rounds from discovered pairs
        rounds: list[dict[str, Any]] = []
        for evaluator, occasion in sorted(seen, key=lambda x: (x[0], x[1])):
            label = SessionManager._round_label(evaluator, occasion)
            rounds.append({
                "evaluator_id": evaluator,
                "occasion": occasion,
                "label": label,
                "created": datetime.now().isoformat(),
            })

        rounds_data = {"rounds": rounds, "active_round_index": 0}
        SessionManager._save_rounds(rounds_data)
        return rounds_data

    @staticmethod
    def _round_label(evaluator_id: str, occasion: int) -> str:
        """Generate a human-readable label for a round."""
        display_name = evaluator_id.replace("_", " ").title()
        try:
            from karlos_core.utils.i18n import I18n
            pasada = I18n().t("round.label", n=str(occasion))
        except Exception:                       # noqa: BLE001 — sin Qt a mano
            pasada = f"Passagem {occasion}"
        return f"{display_name} — {pasada}"

    @staticmethod
    def get_active_round(video_path: str) -> dict[str, Any] | None:
        """Return the currently active round dict from the GLOBAL rounds.json, or None.

        video_path is ignored — the active round is global, not per-folder.
        Kept as a parameter for backward compatibility.

        Returns: {"evaluator_id": str, "occasion": int, "label": str, "created": str}
        """
        rounds_data = SessionManager._load_rounds()
        idx = rounds_data.get("active_round_index", -1)
        rounds = rounds_data.get("rounds", [])
        if 0 <= idx < len(rounds):
            return dict(rounds[idx])
        return None

    @staticmethod
    def set_active_round(video_path: str, index: int) -> bool:
        """Set the active round by index. Returns True on success.

        video_path is ignored — the active round is global.
        """
        rounds_data = SessionManager._load_rounds()
        rounds = rounds_data.get("rounds", [])
        if 0 <= index < len(rounds):
            rounds_data["active_round_index"] = index
            SessionManager._save_rounds(rounds_data)
            return True
        return False

    @staticmethod
    def list_rounds(video_path: str) -> list[dict[str, Any]]:
        """Return all known rounds from the GLOBAL rounds.json.

        video_path is ignored — rounds are global.
        """
        rounds_data = SessionManager._load_rounds()
        return list(rounds_data.get("rounds", []))

    @staticmethod
    def create_round(
        video_path: str,
        evaluator_id: str,
        occasion: int,
        label: str,
    ) -> int:
        """Create a new round, set it as active, and return its index.

        If a round with the same evaluator_id + occasion already exists,
        it is set as active without duplication.

        video_path is ignored — rounds are global.
        """
        rounds_data = SessionManager._load_rounds()
        rounds: list[dict[str, Any]] = list(rounds_data.get("rounds", []))

        # Check for duplicate
        for i, r in enumerate(rounds):
            if r.get("evaluator_id") == evaluator_id and r.get("occasion") == occasion:
                rounds_data["active_round_index"] = i
                SessionManager._save_rounds(rounds_data)
                return i

        new_round: dict[str, Any] = {
            "evaluator_id": evaluator_id,
            "occasion": occasion,
            "label": label or SessionManager._round_label(evaluator_id, occasion),
            "created": datetime.now().isoformat(),
        }
        rounds.append(new_round)
        new_index = len(rounds) - 1
        rounds_data["rounds"] = rounds
        rounds_data["active_round_index"] = new_index
        SessionManager._save_rounds(rounds_data)
        return new_index

    @staticmethod
    def delete_round(video_path: str, index: int) -> bool:
        """Remove a round from rounds.json by index. Returns True on success.

        Does NOT delete .karlos files — only removes from the global list.
        If the active round is deleted, the first remaining round is set active.
        """
        rounds_data = SessionManager._load_rounds()
        rounds = rounds_data.get("rounds", [])
        if 0 <= index < len(rounds):
            del rounds[index]
            rounds_data["rounds"] = rounds
            # Adjust active index
            active_idx = rounds_data.get("active_round_index", -1)
            if active_idx == index:
                rounds_data["active_round_index"] = 0 if rounds else -1
            elif active_idx > index:
                rounds_data["active_round_index"] = active_idx - 1
            SessionManager._save_rounds(rounds_data)
            return True
        return False

    @staticmethod
    def update_round_label(video_path: str, index: int, new_label: str) -> bool:
        """Change the label of a round. Returns True on success."""
        rounds_data = SessionManager._load_rounds()
        rounds = rounds_data.get("rounds", [])
        if 0 <= index < len(rounds):
            rounds[index]["label"] = new_label
            SessionManager._save_rounds(rounds_data)
            return True
        return False

    @staticmethod
    def _active_session_path(video_path: str) -> Path | None:
        """Return the session file path for the currently active round, or None.

        This is the single point of truth for which session file the system
        should read from / write to — NO MORE guessing which session is
        "most recent".
        """
        active = SessionManager.get_active_round(video_path)
        if active is None:
            return None
        return SessionManager._session_path(
            video_path,
            active["evaluator_id"],
            active["occasion"],
        )

