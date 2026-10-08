"""Streamlit history CRUD smoke test."""

from pathlib import Path

import pytest

import workdiary_agent.storage.export as export_mod
import workdiary_agent.storage.sqlite as sqlite_mod


streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def test_history_page_exposes_edit_and_confirmed_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKDIARY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))
    export_path = export_mod.save_markdown(
        "已保存日报",
        "2026-04-24",
        "ui-test-report",
    )
    sqlite_mod.save_report({
        "report_id": "ui-test-report",
        "date": "2026-04-24",
        "template_type": "技术型",
        "raw_input": "完成 CRUD",
        "polished": "已保存日报",
        "export_path": export_path,
    })

    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    assert not app.exception

    app.sidebar.radio[0].set_value("历史记录").run()
    assert not app.exception
    labels = [button.label for button in app.button]
    assert "编辑" in labels
    assert "删除" in labels

    next(button for button in app.button if button.label == "编辑").click().run()
    assert not app.exception
    assert any(area.label == "日报内容" for area in app.text_area)

    # Cancel edit, then verify delete uses an explicit confirmation step.
    next(button for button in app.button if button.label == "取消").click().run()
    next(button for button in app.button if button.label == "删除").click().run()
    assert not app.exception
    assert any(button.label == "确认删除" for button in app.button)
