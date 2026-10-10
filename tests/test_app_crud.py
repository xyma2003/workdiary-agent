"""Streamlit history CRUD smoke test."""

from pathlib import Path
from unittest.mock import patch

import pytest

import workdiary_agent.storage.export as export_mod
import workdiary_agent.storage.sqlite as sqlite_mod


streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


@pytest.fixture(autouse=True)
def isolated_app(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "SILICONFLOW_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WORKDIARY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))
    # History browsing/deletion must never invoke a model.
    from langchain_core.language_models.chat_models import BaseChatModel
    def forbid_model(*args, **kwargs):
        raise AssertionError("History CRUD must stay offline")
    monkeypatch.setattr(BaseChatModel, "invoke", forbid_model)
    import streamlit as st
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def _seed_report():
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
    return sqlite_mod.get_report("ui-test-report")


def _history_app():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    assert not app.exception
    app.sidebar.radio[0].set_value("历史记录").run()
    assert not app.exception
    return app


def _button(app, label):
    return next(button for button in app.button if button.label == label)


def test_history_page_exposes_edit_and_confirmed_delete():
    record = _seed_report()
    app = _history_app()
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
    assert sqlite_mod.get_report_by_id(record["id"]) is not None

    _button(app, "确认删除").click().run()
    assert not app.exception
    assert any("导出清理已完成" in item.value for item in app.success)
    assert sqlite_mod.get_report_by_id(record["id"]) is None
    assert not Path(record["export_path"]).exists()
    assert sqlite_mod.list_export_cleanups() == []


def test_failed_cleanup_remains_visible_without_history_and_across_sessions():
    record = _seed_report()
    app = _history_app()
    _button(app, "删除").click().run()
    with patch("workdiary_agent.report_service.delete_export_path", side_effect=PermissionError("验收：文件被占用")):
        _button(app, "确认删除").click().run()
    assert not app.exception
    assert not app.success
    assert any("日报记录已删除" in item.value and "尚未完成" in item.value for item in app.warning)
    assert sqlite_mod.get_report_by_id(record["id"]) is None
    assert Path(record["export_path"]).exists()
    assert any("暂无历史记录" in item.value for item in app.info)
    assert _button(app, "重试清理")

    # A fresh session has no success/warning state from the first deletion,
    # but the durable cleanup task must still render above the empty history.
    app = _history_app()
    assert _button(app, "重试清理")
    app.text_input(key="history_query").set_value("无匹配记录").run()
    assert _button(app, "重试清理")
    with patch("workdiary_agent.report_service.delete_export_path", side_effect=PermissionError("仍被占用")):
        _button(app, "重试清理").click().run()
    assert not app.exception
    assert not app.success
    assert any("尚未完成" in item.value for item in app.warning)
    assert len(sqlite_mod.list_export_cleanups()) == 1

    _button(app, "重试清理").click().run()
    assert not app.exception
    assert any("导出清理已完成" in item.value for item in app.success)
    assert not any(button.label == "重试清理" for button in app.button)
    assert sqlite_mod.list_export_cleanups() == []
    assert not Path(record["export_path"]).exists()


def test_unmanaged_export_is_reported_as_preserved(tmp_path):
    record = _seed_report()
    outside = tmp_path / "keep.md"
    outside.write_text("keep", encoding="utf-8")
    sqlite_mod.update_report_by_id(
        record["id"], report_id=record["report_id"], date=record["date"],
        template_type="技术型", raw_input="输入", polished="日报",
        export_path=str(outside),
    )
    app = _history_app()
    _button(app, "删除").click().run()
    _button(app, "确认删除").click().run()
    assert not app.exception
    assert not app.success
    assert any("文件已保留" in item.value for item in app.warning)
    assert outside.read_text(encoding="utf-8") == "keep"
    assert sqlite_mod.list_export_cleanups() == []
