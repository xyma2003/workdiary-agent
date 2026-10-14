"""Offline history acceptance for immutable generation-time source snapshots."""

import json
from pathlib import Path
import socket
import sqlite3

import pytest

import workdiary_agent.storage.export as export_mod
import workdiary_agent.storage.sqlite as sqlite_mod


streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

RAW_INPUT = "完成订单看板，核对支付链路。\n待办：继续处理超时重试。"
DATA_INPUT = "请求量：1,234；成功率：98.7%。\n耗时由 200ms 降为 45ms。"
GIT_LOG = "a1b2c3d 修复支付超时\ne4f5a6b 添加订单看板"
BODY = "## 今日工作\n完成支付链路核对与订单看板。"


@pytest.fixture(autouse=True)
def isolated_app(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    for key in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
        "SILICONFLOW_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WORKDIARY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))

    def forbid_external_call(*args, **kwargs):
        raise AssertionError("Source history must never call a model or network")

    from langchain_core.language_models.chat_models import BaseChatModel
    import httpx
    import streamlit as st

    for method in ("invoke", "ainvoke", "stream", "astream"):
        monkeypatch.setattr(BaseChatModel, method, forbid_external_call)
    monkeypatch.setattr(httpx.Client, "send", forbid_external_call)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbid_external_call)
    monkeypatch.setattr(socket.socket, "connect", forbid_external_call)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid_external_call)
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def _snapshot():
    return {
        "schema_version": 1,
        "captured_at": "2026-10-14T18:02:03+08:00",
        "capture_status": "complete",
        "raw_input": RAW_INPUT,
        "data_input": DATA_INPUT,
        "git": {
            "status": "captured",
            "repo_path": "/synthetic/订单服务",
            "requested_author": "测试同学",
            "resolved_author": "测试同学 <demo@example.invalid>",
            "timezone": "Asia/Shanghai",
            "report_date": "2026-10-14",
            "since": "2026-10-14T00:00:00+08:00",
            "until": "2026-10-15T00:00:00+08:00",
            "log": GIT_LOG,
        },
    }


def _model_usage():
    return [
        {
            "stage": "extract",
            "provider": "openai",
            "model": "snapshot-extract-demo",
            "endpoint": "https://models.example.invalid/v1",
            "temperature": 0.2,
            "timeout_seconds": 30,
            "max_retries": 2,
        },
        {
            "stage": "polish",
            "provider": "anthropic",
            "model": "snapshot-polish-demo",
            "endpoint": "https://review.example.invalid",
            "temperature": 0.4,
            "timeout_seconds": 45,
            "max_retries": 1,
        },
    ]


def _seed_report(*, snapshot=True):
    report_id = "source-snapshot-ui"
    export_path = export_mod.save_markdown(BODY, "2026-10-14", report_id)
    state = {
        "report_id": report_id,
        "date": "2026-10-14",
        "template_type": "技术型",
        "raw_input": RAW_INPUT,
        "polished": BODY,
        "export_path": export_path,
    }
    if snapshot:
        state["source_snapshot"] = _snapshot()
        state["model_usage"] = _model_usage()
    sqlite_mod.save_report(state)
    return sqlite_mod.get_report(report_id)


def _history_app():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path)).run()
    assert not app.exception
    app.sidebar.radio[0].set_value("历史记录").run()
    assert not app.exception
    return app


def _button(app, label):
    return next(button for button in app.button if button.label == label)


def _rendered_text(app):
    parts = []
    for kind in ("text", "markdown", "code", "caption", "info", "warning", "error"):
        parts.extend(str(element.value) for element in getattr(app, kind))
    for kind in ("dataframe", "table"):
        for element in getattr(app, kind):
            parts.append(element.value.to_string(index=False))
    return "\n".join(parts)


def _stored_snapshot(record_id):
    with sqlite3.connect(sqlite_mod.DB_PATH) as conn:
        return conn.execute(
            "SELECT source_snapshot_json FROM reports WHERE id = ?", (record_id,)
        ).fetchone()[0]


def test_new_session_displays_original_sources_git_filters_and_each_model_stage():
    _seed_report()
    # This session is created after storage, with no in-memory graph state.
    app = _history_app()
    assert any(item.label == "生成时的来源快照" for item in app.expander)
    rendered = _rendered_text(app)
    for expected in (
        RAW_INPUT, DATA_INPUT, GIT_LOG, BODY, "2026-10-14T18:02:03+08:00",
        "/synthetic/订单服务", "测试同学", "demo@example.invalid", "Asia/Shanghai",
        "2026-10-14T00:00:00+08:00", "2026-10-15T00:00:00+08:00",
        "extract", "openai", "snapshot-extract-demo", "polish", "anthropic",
        "snapshot-polish-demo", "https://models.example.invalid",
        "https://review.example.invalid",
    ):
        assert expected in rendered
    model_rows = app.table[0].value.to_dict(orient="records")
    assert [row["temperature"] for row in model_rows] == [0.2, 0.4]
    assert [row["超时（秒）"] for row in model_rows] == [30, 45]
    assert [row["重试上限"] for row in model_rows] == [2, 1]
    assert not app.text_area  # Source viewing does not expose editable controls.
    assert not app.error


def test_editing_current_input_and_body_preserves_generation_snapshot():
    record = _seed_report()
    before = _stored_snapshot(record["id"])
    assert before is not None
    assert json.loads(before)["raw_input"] == RAW_INPUT
    app = _history_app()
    _button(app, "编辑").click().run()
    assert not app.exception
    assert "修改不会改写生成时的来源快照" in _rendered_text(app)
    next(area for area in app.text_area if area.label == "原始输入").set_value(
        "人工补充：更新了订单接口。"
    )
    next(area for area in app.text_area if area.label == "日报内容").set_value(
        "## 修订后的日报\n更新订单接口并完成复核。"
    )
    _button(app, "保存修改").click().run()
    assert not app.exception
    updated = sqlite_mod.get_report_by_id(record["id"])
    assert updated["raw_input"] == "人工补充：更新了订单接口。"
    assert updated["polished"] == "## 修订后的日报\n更新订单接口并完成复核。"
    assert _stored_snapshot(record["id"]) == before
    assert updated["polished"] in Path(updated["export_path"]).read_text(encoding="utf-8")

    # A fresh page must show both edited report and unchanged generation input.
    app = _history_app()
    rendered = _rendered_text(app)
    for expected in (updated["raw_input"], updated["polished"], RAW_INPUT, DATA_INPUT, GIT_LOG):
        assert expected in rendered


@pytest.mark.parametrize(
    ("stored", "message"),
    [
        (None, "来源未保存"),
        ("{broken-json", "来源快照损坏"),
        (json.dumps({"schema_version": 99, "raw_input": "未知版本中的内容"}), "来源快照版本暂不支持"),
    ],
    ids=["legacy", "corrupt", "unsupported-version"],
)
def test_unavailable_snapshot_keeps_body_and_history_crud_usable(stored, message):
    record = _seed_report(snapshot=False)
    with sqlite3.connect(sqlite_mod.DB_PATH) as conn:
        conn.execute(
            "UPDATE reports SET source_snapshot_json = ? WHERE id = ?", (stored, record["id"])
        )
    app = _history_app()
    rendered = _rendered_text(app)
    assert message in rendered
    assert BODY in rendered
    assert RAW_INPUT in rendered
    assert _button(app, "编辑")
    assert _button(app, "删除")
    _button(app, "编辑").click().run()
    assert not app.exception
    assert any(area.label == "日报内容" for area in app.text_area)
    _button(app, "取消").click().run()
    _button(app, "删除").click().run()
    assert not app.exception
    assert sqlite_mod.get_report_by_id(record["id"]) is not None
    _button(app, "确认删除").click().run()
    assert not app.exception
    assert sqlite_mod.get_report_by_id(record["id"]) is None
