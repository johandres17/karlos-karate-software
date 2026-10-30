"""Tests for SessionManager persistence: atomic saves, versioned
backups, and recovery from a corrupt session file.

A .karlos session file holds an entire evaluation (hundreds of
annotations); these tests guarantee an interrupted write can never
lose it silently.
"""

from __future__ import annotations

import json

import pytest

from karlos_core.controllers.session_manager import SessionManager
from karlos_core.models.annotation import Annotation


@pytest.fixture()
def video_path(tmp_path):
    video = tmp_path / "bout.mp4"
    video.write_bytes(b"fake video")
    return str(video)


def _records() -> list[Annotation]:
    return [
        Annotation(
            athlete="AKA", category="ATTACK", subcategory="PUNCHES",
            technique="Jab", level="High", f_start=10, f_end=40,
            duration_s=1.0,
        )
    ]


def _save(sm: SessionManager, video_path: str, technique: str = "Jab") -> str:
    records = _records()
    records[0].technique = technique
    return sm.save_session(
        video_path=video_path, bout_info={"athlete_a_name": "A"},
        fight_start=0, fight_end=1000, records=records,
    )


class TestSaveAndLoad:
    def test_round_trip(self, video_path):
        sm = SessionManager()
        _save(sm, video_path)
        data = sm.load_session(video_path)
        assert data is not None
        assert data["annotations"][0]["technique"] == "Jab"

    def test_no_tmp_file_left_behind(self, video_path):
        sm = SessionManager()
        saved = _save(sm, video_path)
        from pathlib import Path
        assert not list(Path(saved).parent.glob("*.tmp"))

    def test_second_save_creates_backup(self, video_path):
        sm = SessionManager()
        saved = _save(sm, video_path, "Jab")
        _save(sm, video_path, "Hook")
        from pathlib import Path
        backups = list((Path(saved).parent / "backups").glob("*"))
        assert len(backups) == 1


class TestCorruptRecovery:
    def test_corrupt_file_falls_back_to_backup(self, video_path):
        sm = SessionManager()
        saved = _save(sm, video_path, "Jab")
        _save(sm, video_path, "Hook")  # snapshots "Jab" into backups/

        from pathlib import Path
        Path(saved).write_text("{ this is not json", encoding="utf-8")

        data = sm.load_session(video_path)
        assert data is not None, "corrupt session must recover from backup"
        assert data["annotations"][0]["technique"] == "Jab"

    def test_corrupt_file_without_backup_returns_none(self, video_path):
        sm = SessionManager()
        saved = _save(sm, video_path)
        from pathlib import Path
        Path(saved).write_text("garbage", encoding="utf-8")
        assert sm.load_session(video_path) is None

    def test_missing_file_returns_none_without_backup_resurrection(self, video_path):
        # After a deliberate delete_session, backups must NOT resurrect
        # the session — deleted means deleted.
        sm = SessionManager()
        _save(sm, video_path, "Jab")
        _save(sm, video_path, "Hook")
        sm.delete_session(video_path)
        assert sm.load_session(video_path) is None

    def test_wrong_version_treated_as_unreadable(self, video_path):
        sm = SessionManager()
        saved = _save(sm, video_path)
        from pathlib import Path
        payload = json.loads(Path(saved).read_text(encoding="utf-8"))
        payload["version"] = "99.0"
        Path(saved).write_text(json.dumps(payload), encoding="utf-8")
        assert sm.load_session(video_path) is None
