"""Offline review acceptance using real checkpoint, revision, and save paths.

Only the SDK client and Git reader are replaced. All application state, SQLite
files, and Markdown exports are temporary; external calls are forbidden.
"""

from __future__ import annotations

import copy
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

import workdiary_agent.graph as graph_mod
import workdiary_agent.nodes.enrich as enrich_mod
import workdiary_agent.storage.export as export_mod
import workdiary_agent.storage.sqlite as sqlite_mod
from workdiary_agent.report_service import update_saved_report
from workdiary_agent.state import StructuredInfo


AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
RAW = "完成订单链路验证，检查重试策略。"
DATA = "请求耗时：15ms；验证用例：8 条。"
GIT = "abc1234 fix: verify retry behavior"
BODY = "完成订单链路验证，请求耗时为 15ms，验证了 8 条用例。"
REVISED = "完成订单链路验证和重试策略复核，验证了 8 条用例。"


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    for key in (
        "OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_BASE_URL", "OPENAI_MODEL",
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_CUSTOM_HEADERS",
        "SILICONFLOW_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY",
        "LLM_TIMEOUT_SECONDS", "LLM_MAX_RETRIES",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-review-placeholder")
    monkeypatch.setenv("OPENAI_API_BASE", "https://offline-review.example.invalid/v1")
    monkeypatch.setenv("OPENAI_MODEL", "offline-review-model")
    monkeypatch.setenv("WORKDIARY_TIMEZONE", "Asia/Shanghai")
    monkeypatch.setenv("WORKDIARY_DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))

    def forbidden(*args, **kwargs):
        raise AssertionError("Review acceptance must never contact a model or network")

    import httpx
    import langchain_openai
    from langchain_core.language_models.chat_models import BaseChatModel
    import streamlit as st

    for method in ("invoke", "ainvoke", "stream", "astream"):
        monkeypatch.setattr(BaseChatModel, method, forbidden)
    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)

    fixture = SimpleNamespace(
        summary="请求耗时为 15ms，验证了 8 条用例。",
        reports=[BODY, REVISED],
        polish_inputs=[],
        git_reads=[],
        model_calls=[],
        graphs=[],
        repo_path=str(tmp_path / "synthetic-repository"),
    )

    class OfflineClient:
        def __init__(self, **kwargs):
            self.model_name = kwargs.get("model")
            self.openai_api_base = kwargs.get("base_url")

        def with_structured_output(self, schema):
            def invoke(messages):
                fixture.model_calls.append("extract")
                return StructuredInfo(
                    tasks=[RAW], outputs=["完成订单链路验证"], progress="已完成",
                )
            return SimpleNamespace(invoke=invoke)

        def invoke(self, messages):
            system = str(messages[0].content)
            fixture.model_calls.append(system)
            if "数据指标提取助手" in system:
                return SimpleNamespace(content=fixture.summary)
            if "日报类型分类助手" in system:
                return SimpleNamespace(content="技术型")
            if "内容分析助手" in system:
                return SimpleNamespace(content="已完成订单链路和重试策略验证。")
            if "资深职场写作顾问" in system:
                fixture.polish_inputs.append(str(messages[-1].content))
                index = min(len(fixture.polish_inputs) - 1, len(fixture.reports) - 1)
                return SimpleNamespace(content=fixture.reports[index])
            return SimpleNamespace(content=BODY)

    def git_reader(repo_path, *, git_author=None, timezone_name=None,
                   report_date=None, _details=None):
        fixture.git_reads.append(repo_path)
        if _details is not None:
            _details.update(
                status="captured", repo_path=repo_path,
                requested_author=git_author, resolved_author="review@example.invalid",
                timezone=timezone_name, report_date=report_date,
                since=f"{report_date}T00:00:00+08:00",
                until=f"{report_date}T23:59:59+08:00",
            )
        return GIT

    original_build = graph_mod.build_graph

    def tracked_build(*args, **kwargs):
        graph = original_build(*args, **kwargs)
        fixture.graphs.append(graph)
        return graph

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", OfflineClient)
    monkeypatch.setattr(enrich_mod, "_read_git_log", git_reader)
    monkeypatch.setattr(graph_mod, "build_graph", tracked_build)
    st.cache_resource.clear()
    yield fixture
    st.cache_resource.clear()
    for graph in fixture.graphs:
        connection = getattr(graph.checkpointer, "conn", None)
        if connection is not None:
            connection.close()


def _app():
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert not app.exception
    return app


def _generate(runtime):
    app = _app()
    app.text_area(key="raw_input_field").set_value(RAW)
    app.text_area(key="data_input_field").set_value(DATA)
    app.text_input(key="repo_path_field").set_value(runtime.repo_path)
    app.text_input(key="git_author_field").set_value("review@example.invalid")
    app.selectbox(key="template_choice_field").set_value("技术型")
    next(button for button in app.button if button.label == "生成日报").click().run()
    assert not app.exception
    assert app.session_state.app_state == "reviewing"
    assert len(runtime.git_reads) == 1
    return app


def _editor(app):
    return next(area for area in app.text_area if (area.key or "").startswith("edit_area_"))


def _text(tree):
    parts = []
    for kind in ("text", "markdown", "code", "caption", "info", "warning", "error"):
        parts.extend(str(element.value) for element in tree.get(kind))
    return "\n".join(parts)


def _sources_column(app):
    """Find the rendered source column by content rather than a layout index."""
    return next(column for column in app.get("column") if RAW in _text(column) and DATA in _text(column))


def test_review_uses_frozen_sources_and_flags_model_summary_after_form_changes(runtime):
    runtime.summary = "模型推测增长达到 9876%。"
    runtime.reports = ["完成订单链路验证，增长达到 9876%。"]
    app = _generate(runtime)
    snapshot = copy.deepcopy(app.session_state.result["source_snapshot"])
    source_column = _sources_column(app)
    assert GIT in _text(source_column)
    assert not source_column.get("text_area")  # Evidence is read-only beside the editor.
    summary = next(item for item in app.expander if "非原始证据" in item.label)
    assert runtime.summary in _text(summary)
    assert not summary.proto.expanded
    form = next(item for item in app.expander if item.label == "重新填写并生成新日报")
    assert not form.proto.expanded

    # Editing the collapsed form is not a new submission or new evidence.
    app.text_area(key="raw_input_field").set_value("另一任务：增长为 9876%。")
    app.text_area(key="data_input_field").set_value("新表单指标：9876%。")
    app.text_input(key="repo_path_field").set_value("/another/repository")
    app.run()
    assert not app.exception
    assert app.session_state.result["source_snapshot"] == snapshot
    assert len(runtime.git_reads) == 1
    assert RAW in _text(_sources_column(app))
    assert "新表单指标" not in _text(app)
    assert "模型整理" in _text(app)
    assert "原始材料中未找到的数字：9876" in _text(app)
    assert "来源材料中未找到的数字：9876" in _text(app)
    assert app.button(key="accept_btn").disabled

    acknowledgment = next(box for box in app.checkbox if (box.key or "").startswith("quality_ack_"))
    acknowledgment.check().run()
    assert not app.button(key="accept_btn").disabled
    _editor(app).set_value("完成订单链路验证，增长达到 9876%，另有 555 条记录。").run()
    assert app.button(key="accept_btn").disabled  # Editing must invalidate the acknowledgment.


def test_inline_accept_saves_edited_report_with_the_original_snapshot(runtime):
    app = _generate(runtime)
    report_id = app.session_state.result["report_id"]
    captured = copy.deepcopy(app.session_state.result["source_snapshot"])
    edited = "人工复核：完成订单链路验证，共检查 8 条用例。"
    app.text_area(key="raw_input_field").set_value("下一份日报的描述")
    _editor(app).set_value(edited).run()
    assert not app.button(key="accept_btn").disabled
    app.button(key="accept_btn").click().run()
    assert not app.exception
    assert app.session_state.app_state == "done"
    saved = sqlite_mod.get_report(report_id)
    assert saved["polished"] == edited
    assert saved["raw_input"] == RAW
    for field in ("raw_input", "data_input", "git", "captured_at"):
        assert saved["source_snapshot"][field] == captured[field]
    assert edited in Path(saved["export_path"]).read_text(encoding="utf-8")
    assert sqlite_mod.count_reports() == 1


def test_revision_keeps_inline_edits_and_uses_a_new_editor_without_changing_sources(runtime):
    app = _generate(runtime)
    captured = copy.deepcopy(app.session_state.result["source_snapshot"])
    first_key = _editor(app).key
    manual = "人工补充：完成重试策略复核，检查 8 条用例。"
    _editor(app).set_value(manual).run()
    app.button(key="revise_btn").click().run()
    app.text_input(key="feedback_input").set_value("保留人工补充，突出复核结果。")
    app.button(key="confirm_revise_btn").click().run()
    assert not app.exception
    assert app.session_state.app_state == "reviewing"
    assert app.session_state.result["revision_count"] == 1
    assert _editor(app).key != first_key
    assert _editor(app).value == REVISED
    assert manual in runtime.polish_inputs[-1]
    assert "保留人工补充，突出复核结果。" in runtime.polish_inputs[-1]
    assert app.session_state.result["source_snapshot"] == captured
    assert len(runtime.git_reads) == 1
    assert sqlite_mod.count_reports() == 0  # Revision is never an approval.


def test_new_session_recovers_review_and_frozen_comparison_from_sqlite(runtime):
    app = _generate(runtime)
    thread_id = app.session_state.thread_id
    captured = copy.deepcopy(app.session_state.result["source_snapshot"])
    calls_before = len(runtime.model_calls)
    import streamlit as st

    st.cache_resource.clear()  # Rebuild the graph from the persisted checkpoint.
    recovered = _app()
    recovered.text_area(key="raw_input_field").set_value("未提交的新会话输入")
    recovered.button(key=f"recover_{thread_id}").click().run()
    assert not recovered.exception
    assert recovered.session_state.app_state == "reviewing"
    assert recovered.session_state.thread_id == thread_id
    assert recovered.session_state.result["source_snapshot"] == captured
    assert RAW in _text(_sources_column(recovered))
    assert DATA in _text(_sources_column(recovered))
    assert GIT in _text(_sources_column(recovered))
    assert _editor(recovered).value == BODY
    assert len(runtime.model_calls) == calls_before
    assert len(runtime.git_reads) == 1


def test_legacy_checkpoint_shows_missing_snapshot_without_fabricating_evidence(runtime):
    graph = graph_mod.build_graph(use_sqlite=True)
    config = {"configurable": {"thread_id": "legacy-review"}}
    graph.update_state(
        config,
        {
            "report_id": "legacy-review-report", "date": "2026-10-14",
            "raw_input": RAW, "data_input": DATA, "git_log": GIT,
            "polished": BODY, "template_type": "技术型", "revision_count": 0,
            "data_summary": "旧模型摘要，不是当时的来源快照。",
        },
        as_node="polish",
    )
    graph.invoke(None, config)  # Persist the same review interrupt as a pre-W02 run.
    app = _app()
    app.text_area(key="raw_input_field").set_value("当前表单的无关材料")
    app.button(key="recover_legacy-review").click().run()
    assert not app.exception
    assert "旧任务未保存来源快照" in _text(app)
    assert "完整性无法确认" in _text(app)
    assert not app.session_state.result.get("source_snapshot")
    assert _editor(app).value == BODY
    assert not runtime.git_reads
    assert not runtime.model_calls
    assert "当前表单的无关材料" not in _text(app)
    app.button(key="accept_btn").click().run()
    assert not app.exception
    saved = sqlite_mod.get_report("legacy-review-report")
    assert saved["polished"] == BODY
    assert saved["source_snapshot"] is None
    assert saved["source_snapshot_status"] == "missing"


def test_history_comparison_reads_saved_snapshot_after_current_inputs_are_edited(runtime):
    app = _generate(runtime)
    report_id = app.session_state.result["report_id"]
    app.button(key="accept_btn").click().run()
    assert not app.exception
    record = sqlite_mod.get_report(report_id)
    update_saved_report(
        record["id"], date=record["date"], template_type=record["template_type"],
        raw_input="后来修改的历史输入", polished="人工编辑后的日报，已复核 8 条用例。",
    )
    calls_before = len(runtime.model_calls)
    history = _app()
    history.sidebar.radio[0].set_value("历史记录").run()
    assert not history.exception
    source_column = _sources_column(history)
    assert GIT in _text(source_column)
    assert "后来修改的历史输入" not in _text(source_column)
    assert "人工编辑后的日报，已复核 8 条用例。" in _text(history)
    assert "后来修改的历史输入" in _text(history)
    assert len(runtime.model_calls) == calls_before
    assert len(runtime.git_reads) == 1
