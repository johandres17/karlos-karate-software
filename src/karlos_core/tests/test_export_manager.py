"""Tests for ExportManager and the legacy-level migration.

Covers the two real-world failures seen in production:
1. Sessions from old builds stored the raw combined string
   "Stance: X | Target: Y | Action: Z" in Annotation.level, aborting
   every XLSX export ("contains unparsed ' | '").
2. A single bad row blocked the entire export — force=True must still
   produce the workbook, listing issues in a Validation Warnings sheet.

These tests are Qt-free on purpose so they run headless in CI.
"""

from __future__ import annotations

import pytest
from openpyxl import load_workbook

from karlos_karate.export_manager import ExportManager
from karlos_core.models.annotation import Annotation
from karlos_core.utils.merge_utils import (
    migrate_legacy_combined_levels,
    parse_combined_level,
)


def _legacy_row() -> Annotation:
    """A row of an older session: the answers still combined in the level."""
    return Annotation(
        athlete="AKA", category="ATTACK", subcategory="HAND TECHNIQUES",
        technique="Kizami Tsuki",
        level="Stance: Lead | Target: Jodan | Action: Direct",
        score="CONNECTED", f_start=100, f_end=130, duration_s=1.0,
    )


def _clean_row() -> Annotation:
    return Annotation(
        athlete="AO", category="ATTACK", subcategory="KICK TECHNIQUES",
        technique="Mawashi Geri", level="Jodan",
        f_start=200, f_end=230, duration_s=1.0,
        sport_specific_data={"sequence_id": "SEQ_001"},
    )


def _manager(records, sport_id="karate") -> ExportManager:
    em = ExportManager()
    em.set_records(records)
    em.set_sport_id(sport_id)
    em.set_bout_info({"athlete_a_name": "A", "athlete_b_name": "B"})
    return em


# ── Migration (merge_utils) ──────────────────────────────────────────


class TestMigrateLegacyCombinedLevels:
    def test_combined_string_is_split(self):
        ann = _legacy_row()
        assert migrate_legacy_combined_levels([ann]) == 1
        assert ann.stance == "Lead"
        assert ann.target == "Jodan"
        assert ann.sport_specific_data["action_type"] == "Direct"
        assert ann.level == ""

    def test_karate_combined_string_keeps_level(self):
        ann = Annotation(
            athlete="AKA", category="ATTACK", subcategory="HAND",
            technique="Gyaku-tsuki",
            level="Stance: Rear | Level: Jodan | Action: Direct",
        )
        migrate_legacy_combined_levels([ann])
        assert ann.level == "Jodan"
        assert ann.stance == "Rear"

    def test_feint_limb_becomes_level(self):
        ann = Annotation(
            athlete="AO", category="TACTICS", subcategory="TACTICS",
            technique="Feint", level="Stance: Lead | Limb: Lead Leg",
        )
        migrate_legacy_combined_levels([ann])
        assert ann.level == "Lead Leg"

    def test_clean_rows_untouched(self):
        ann = _clean_row()
        assert migrate_legacy_combined_levels([ann]) == 0
        assert ann.level == "Jodan"

    def test_existing_fields_not_overwritten(self):
        ann = _legacy_row()
        ann.stance = "Rear"  # explicit value must win over the parsed one
        migrate_legacy_combined_levels([ann])
        assert ann.stance == "Rear"
        assert ann.target == "Jodan"

    def test_parse_combined_level_components(self):
        parsed = parse_combined_level("Stance: Lead | Target: Jodan | Action: Direct")
        assert parsed == {"stance": "Lead", "target": "Jodan", "action": "Direct"}


# ── Validation ───────────────────────────────────────────────────────


class TestValidation:
    def test_strict_export_aborts_on_combined_level(self, tmp_path):
        em = _manager([_legacy_row()])
        with pytest.raises(ValueError, match="unparsed"):
            em.export_xlsx(str(tmp_path / "out.xlsx"))

    def test_all_issues_collected_not_just_first(self):
        bad = _legacy_row()
        bad.sport_specific_data["sequence_id"] = "BAD_FORMAT"
        em = _manager([bad])
        issues = em._collect_validation_issues()
        assert len(issues) == 2
        assert any("unparsed" in i for i in issues)
        assert any("BAD_FORMAT" in i for i in issues)

    def test_clean_records_have_no_issues(self):
        em = _manager([_clean_row()])
        assert em._collect_validation_issues() == []


# ── XLSX export ──────────────────────────────────────────────────────


class TestExportXlsx:
    def test_plain_export_has_no_technical_tactical_analysis_sheet(self, tmp_path):
        em = _manager([_clean_row()], sport_id="karate")
        wb = load_workbook(em.export_xlsx(str(tmp_path / "karate.xlsx")))
        assert "Technical-Tactical Analysis" not in wb.sheetnames

    def test_force_export_writes_warnings_sheet(self, tmp_path):
        bad = _legacy_row()
        bad.sport_specific_data["sequence_id"] = "BAD_FORMAT"
        em = _manager([bad, _clean_row()])
        saved = em.export_xlsx(str(tmp_path / "forced.xlsx"), force=True)
        wb = load_workbook(saved)
        assert "Validation Warnings" in wb.sheetnames
        rows = list(wb["Validation Warnings"].iter_rows(values_only=True))
        assert rows[0] == ("#", "Issue")
        assert len(rows) == 3  # header + 2 issues

    def test_force_export_clean_data_has_no_warnings_sheet(self, tmp_path):
        em = _manager([_clean_row()])
        wb = load_workbook(em.export_xlsx(str(tmp_path / "clean.xlsx"), force=True))
        assert "Validation Warnings" not in wb.sheetnames

    def test_export_without_records_raises(self, tmp_path):
        em = ExportManager()
        em.set_records([])
        with pytest.raises(ValueError):
            em.export_xlsx(str(tmp_path / "empty.xlsx"))


# ── CSV export ───────────────────────────────────────────────────────


class TestExportCsv:
    def test_csv_written_with_rows(self, tmp_path):
        em = _manager([_clean_row()])
        saved = em.export_csv(str(tmp_path / "out.csv"))
        content = (tmp_path / "out.csv").read_text(encoding="utf-8")
        assert saved.endswith("out.csv")
        assert "Mawashi Geri" in content
