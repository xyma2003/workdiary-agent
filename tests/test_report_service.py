"""Saved-report CRUD and export synchronization tests."""

import os
from unittest.mock import patch

import pytest

import workdiary_agent.storage.export as export_mod
import workdiary_agent.storage.sqlite as sqlite_mod
from workdiary_agent.report_service import delete_saved_report, update_saved_report


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))
    return tmp_path


def _create_report(*, report_id="report-1", date="2026-04-24") -> dict:
    export_path = export_mod.save_markdown("旧日报", date, report_id)
    sqlite_mod.save_report({
        "report_id": report_id,
        "date": date,
        "template_type": "技术型",
        "raw_input": "旧输入",
        "polished": "旧日报",
        "export_path": export_path,
    })
    return sqlite_mod.get_report(report_id)


def test_update_saved_report_updates_all_fields_and_moves_export(isolated_storage):
    old = _create_report()

    updated = update_saved_report(
        old["id"],
        date="2026-04-25",
        template_type="业务型",
        raw_input="新输入",
        polished="新日报内容",
    )

    assert updated["date"] == "2026-04-25"
    assert updated["template_type"] == "业务型"
    assert updated["raw_input"] == "新输入"
    assert updated["polished"] == "新日报内容"
    assert updated["updated_at"]
    assert os.path.exists(updated["export_path"])
    assert "新日报内容" in open(updated["export_path"], encoding="utf-8").read()
    assert not os.path.exists(old["export_path"])


def test_update_saved_report_restores_export_when_database_update_fails(
    isolated_storage,
):
    old = _create_report()

    with patch(
        "workdiary_agent.report_service.update_report_by_id",
        side_effect=RuntimeError("database unavailable"),
    ):
        with pytest.raises(RuntimeError, match="database unavailable"):
            update_saved_report(
                old["id"],
                date=old["date"],
                template_type="技术型",
                raw_input="新输入",
                polished="不应保留的新内容",
            )

    assert "旧日报" in open(old["export_path"], encoding="utf-8").read()
    assert sqlite_mod.get_report_by_id(old["id"])["polished"] == "旧日报"


def test_update_saved_report_rejects_invalid_or_sensitive_content(isolated_storage):
    old = _create_report()

    with pytest.raises(ValueError, match="日期"):
        update_saved_report(
            old["id"],
            date="2026-02-30",
            template_type="技术型",
            raw_input="输入",
            polished="内容",
        )
    with pytest.raises(ValueError, match="凭证"):
        update_saved_report(
            old["id"],
            date="2026-04-24",
            template_type="技术型",
            raw_input="输入",
            polished="密钥 sk-abcdefghijklmnopqrstuvwxyz",
        )


def test_delete_saved_report_removes_database_row_and_managed_export(
    isolated_storage,
):
    record = _create_report()

    deleted = delete_saved_report(record["id"])

    assert deleted["report_id"] == "report-1"
    assert sqlite_mod.get_report_by_id(record["id"]) is None
    assert not os.path.exists(record["export_path"])
    assert delete_saved_report(record["id"]) is None


def test_delete_saved_report_never_removes_file_outside_export_dir(
    isolated_storage,
):
    outside = isolated_storage / "outside.md"
    outside.write_text("keep", encoding="utf-8")
    sqlite_mod.save_report({
        "report_id": "external-path",
        "date": "2026-04-24",
        "template_type": "技术型",
        "raw_input": "输入",
        "polished": "日报",
        "export_path": str(outside),
    })
    record = sqlite_mod.get_report("external-path")

    delete_saved_report(record["id"])

    assert outside.exists()
    assert sqlite_mod.get_report("external-path") is None
