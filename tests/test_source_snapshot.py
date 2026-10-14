"""Offline provenance regressions: frozen inputs, actual factory metadata, history.

Every database, export, and Git repository used here is temporary. SDK client
construction is replaced before any model is requested; no live credentials or
application history are needed.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from collections import Counter
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langgraph.types import Command

import workdiary_agent.storage.export as export_mod
import workdiary_agent.storage.sqlite as sqlite_mod
from workdiary_agent.graph import build_graph
from workdiary_agent.nodes.save import save_node
from workdiary_agent.report_service import update_saved_report
from workdiary_agent.source_snapshot import capture_sources_node, snapshot_for_storage
from workdiary_agent.state import StructuredInfo


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("WORKDIARY_DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))
    for key in (
        "LLM_PROVIDER", "LLM_TIMEOUT_SECONDS", "LLM_MAX_RETRIES",
        "OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_BASE_URL", "OPENAI_MODEL",
        "SILICONFLOW_API_KEY", "SILICONFLOW_BASE_URL", "SILICONFLOW_MODEL",
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL", "ANTHROPIC_CUSTOM_HEADERS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-1234567890123456")
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.invalid/v1")
    monkeypatch.setenv("OPENAI_MODEL", "offline-model-one")


def _mock_client():
    client = MagicMock()
    client.invoke.return_value = SimpleNamespace(content="混合型")
    client.with_structured_output.return_value.invoke.return_value = StructuredInfo(
        tasks=["修复离线示例"], outputs=["完成验证"], progress="已完成",
    )
    return client


def _input_state(**changes):
    return {
        "report_id": "snapshot-report", "date": "2026-01-02",
        "timezone": "Asia/Shanghai", "raw_input": "完成离线示例修复",
        "data_input": "验证通过率 100%", "polished": "完成离线示例修复并验证。",
        **changes,
    }


def _captured_state(**changes):
    state = _input_state(**changes)
    return {**state, **capture_sources_node(state)}


def _git_repo(tmp_path):
    git = pytest.importorskip("git")
    repo = git.Repo.init(tmp_path / "source-repo")
    identity = git.Actor("Snapshot User", "snapshot@example.invalid")

    def commit(subject, hour):
        path = tmp_path / "source-repo" / "work.txt"
        path.write_text(subject, encoding="utf-8")
        repo.index.add([str(path)])
        instant = datetime.fromisoformat(f"2026-01-02T{hour}:00:00+08:00")
        return repo.index.commit(
            subject, author=identity, committer=identity,
            author_date=instant, commit_date=instant,
        )

    return repo, commit


def test_failed_enrichment_recovers_original_git_from_sqlite_checkpoint(tmp_path):
    repo, commit = _git_repo(tmp_path)
    initial = commit("fix: original source", "09")
    config = {"configurable": {"thread_id": "frozen-checkpoint"}}
    graph = build_graph(use_sqlite=True)
    state = _input_state(
        repo_path=repo.working_tree_dir, git_author="snapshot@example.invalid",
        template_type="技术型",
    )
    with patch("langchain_openai.ChatOpenAI", return_value=_mock_client()), patch(
        "workdiary_agent.nodes.enrich._extract_data_summary",
        side_effect=RuntimeError("temporary offline failure"),
    ):
        with pytest.raises(RuntimeError, match="temporary offline failure"):
            graph.invoke(state, config)
    checkpoint = graph.get_state(config)
    assert checkpoint.next == ("enrich",)
    frozen = copy.deepcopy(checkpoint.values["source_snapshot"])
    assert initial.hexsha[:7] in frozen["git"]["log"]
    assert frozen["git"]["resolved_author"] == "snapshot@example.invalid"
    assert frozen["git"]["since"] == "2026-01-02T00:00:00+08:00"
    assert frozen["git"]["until"] == "2026-01-03T00:00:00+08:00"
    graph.checkpointer.conn.close()

    later = commit("feat: added after failed generation", "10")
    recovered = build_graph(use_sqlite=True)
    try:
        with patch("langchain_openai.ChatOpenAI", return_value=_mock_client()), patch(
            "workdiary_agent.nodes.enrich._read_git_log",
            side_effect=AssertionError("Recovery must not reread the Git repository"),
        ):
            result = recovered.invoke(None, config)
            assert recovered.get_state(config).next == ("review",)
            assert result["source_snapshot"] == frozen
            assert initial.hexsha[:7] in result["git_log"]
            assert later.hexsha[:7] not in result["git_log"]
            recovered.invoke(Command(resume={"decision": "approve"}), config)
        saved = sqlite_mod.get_report(state["report_id"])
        assert saved["source_snapshot_status"] == "saved"
        assert saved["source_snapshot"]["git"] == frozen["git"]
        assert saved["source_snapshot"]["captured_at"] == frozen["captured_at"]
        fresh = _captured_state(
            report_id="new-generation", repo_path=repo.working_tree_dir,
            git_author="snapshot@example.invalid",
        )
        assert later.hexsha[:7] in fresh["source_snapshot"]["git"]["log"]
        assert saved["source_snapshot"]["git"] == frozen["git"]
    finally:
        recovered.checkpointer.conn.close()


def test_factory_metadata_tracks_router_calls_and_changed_revision_model(monkeypatch):
    monkeypatch.setenv(
        "OPENAI_API_BASE",
        "https://demo-user:demo-password@example.invalid:8443/v1/private-token"
        "?api_key=demo-query-token#fragment",
    )
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "37")
    monkeypatch.setenv("LLM_MAX_RETRIES", "1")
    monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "X-Internal: secret-header-value")
    graph = build_graph()
    config = {"configurable": {"thread_id": "actual-factory"}}
    with patch("langchain_openai.ChatOpenAI", return_value=_mock_client()) as sdk:
        graph.invoke(_input_state(), config)
        initial = graph.get_state(config).values["model_usage"]
        assert Counter(item["stage"] for item in initial) == {
            "extract": 1, "enrich": 1, "route_template": 2, "draft": 1, "polish": 1,
        }
        assert sdk.call_count == len(initial) == 6
        monkeypatch.setenv("OPENAI_MODEL", "offline-model-two")
        graph.invoke(Command(resume={"decision": "revise", "feedback": "补充结果"}), config)
        graph.invoke(Command(resume={"decision": "approve"}), config)
    snapshot = sqlite_mod.get_report("snapshot-report")["source_snapshot"]
    usage = snapshot["model_usage"]
    assert len(usage) == 7
    assert [item["model"] for item in usage] == ["offline-model-one"] * 6 + ["offline-model-two"]
    assert usage[-1]["stage"] == "polish"
    for item in usage:
        assert set(item) == {
            "stage", "provider", "model", "endpoint", "temperature",
            "timeout_seconds", "max_retries",
        }
        assert item["provider"] == "openai-compatible"
        assert item["endpoint"] == "https://example.invalid:8443"
        assert item["temperature"] == 0
        assert item["timeout_seconds"] == 37
        assert item["max_retries"] == 1
    encoded = json.dumps(snapshot)
    for forbidden in (
        "sk-test-secret", "demo-user", "demo-password", "private-token",
        "demo-query-token", "secret-header-value", "default_headers", "api_key",
    ):
        assert forbidden not in encoded


def test_capture_redacts_inputs_and_commit_subject_without_reading_commit_body(tmp_path):
    repo, commit = _git_repo(tmp_path)
    secret = "sk-fictional-snapshot-secret-1234567890"
    commit(f"fix: {secret}\n\nPrivate commit body must stay out", "09")
    state = _captured_state(
        repo_path=repo.working_tree_dir, git_author="snapshot@example.invalid",
        raw_input=f"完成修复 api_key={secret}", data_input=f"通过率 100% {secret}",
    )
    snapshot = snapshot_for_storage(state)
    encoded = json.dumps(snapshot, ensure_ascii=False)
    assert secret not in encoded
    assert "[REDACTED_SECRET]" in snapshot["raw_input"]
    assert "[REDACTED_SECRET]" in snapshot["data_input"]
    assert "[REDACTED_SECRET]" in snapshot["git"]["log"]
    assert "Private commit body" not in encoded
    assert secret not in state["raw_input"]
    assert secret not in state["data_input"]
    assert secret not in state["git_log"]


def test_pre_capture_checkpoint_resumes_without_inventing_sources():
    graph = build_graph()
    config = {"configurable": {"thread_id": "legacy-checkpoint"}}
    graph.update_state(
        config,
        _input_state(
            repo_path="/unavailable/old/repository", git_log="old1234 known earlier material",
            template_type="技术型", structured_info=StructuredInfo().model_dump(),
        ),
        as_node="extract",
    )
    with patch("langchain_openai.ChatOpenAI", return_value=_mock_client()), patch(
        "workdiary_agent.nodes.enrich._read_git_log",
        side_effect=AssertionError("An old checkpoint must not gain present-day Git evidence"),
    ):
        result = graph.invoke(None, config)
        assert result["git_log"] == "old1234 known earlier material"
        assert not result.get("source_snapshot")
        graph.invoke(Command(resume={"decision": "approve"}), config)
    saved = sqlite_mod.get_report("snapshot-report")
    assert saved["source_snapshot"] is None
    assert saved["source_snapshot_status"] == "missing"


@pytest.mark.parametrize("with_snapshot", [False, True], ids=["legacy-null", "captured"])
def test_upsert_and_history_edit_preserve_original_snapshot(with_snapshot):
    state = _captured_state(template_type="技术型") if with_snapshot else _input_state(template_type="技术型")
    sqlite_mod.save_report(state)
    original = sqlite_mod.get_report("snapshot-report")
    expected = original["source_snapshot"]
    assert original["source_snapshot_status"] == ("saved" if with_snapshot else "missing")
    replacement = _captured_state(raw_input="另一份输入", polished="重复保存时更新正文。")
    sqlite_mod.save_report(replacement)
    assert sqlite_mod.get_report("snapshot-report")["source_snapshot"] == expected
    edited = update_saved_report(
        original["id"], date="2026-01-03", template_type="技术型",
        raw_input="编辑后的原始输入", polished="编辑后的日报正文。",
    )
    assert edited["polished"] == "编辑后的日报正文。"
    assert edited["source_snapshot"] == expected
    assert sqlite_mod.get_all_reports()[0]["source_snapshot"] == expected
    assert sqlite_mod.delete_report_by_id(original["id"])
    assert sqlite_mod.get_report("snapshot-report") is None


def test_old_database_migrates_without_inventing_a_source_snapshot():
    with sqlite3.connect(sqlite_mod.DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE reports (id INTEGER PRIMARY KEY, date TEXT NOT NULL, "
            "template_type TEXT, raw_input TEXT, polished TEXT, created_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO reports VALUES (1, '2026-01-02', '技术型', '旧输入', '旧正文', '2026-01-02T12:00:00')"
        )
    migrated = sqlite_mod.get_all_reports()[0]
    assert migrated["polished"] == "旧正文"
    assert migrated["source_snapshot"] is None
    assert migrated["source_snapshot_status"] == "missing"
    with sqlite3.connect(sqlite_mod.DB_PATH) as conn:
        assert conn.execute("SELECT source_snapshot_json FROM reports").fetchone() == (None,)
    edited = update_saved_report(
        migrated["id"], date="2026-01-03", template_type="技术型",
        raw_input="修改旧输入", polished="修改旧正文。",
    )
    assert edited["source_snapshot"] is None
    assert edited["source_snapshot_status"] == "missing"


@pytest.mark.parametrize(
    ("raw_snapshot", "status"),
    [("{bad-json", "invalid"), ("[]", "invalid"), ('{"schema_version": 999}', "unsupported")],
)
def test_unreadable_snapshot_does_not_hide_report_text(raw_snapshot, status):
    sqlite_mod.save_report(_input_state())
    with sqlite3.connect(sqlite_mod.DB_PATH) as conn:
        conn.execute("UPDATE reports SET source_snapshot_json = ?", (raw_snapshot,))
    for row in [sqlite_mod.get_report("snapshot-report"), sqlite_mod.get_all_reports()[0]]:
        assert row["polished"] == "完成离线示例修复并验证。"
        assert row["source_snapshot"] is None
        assert row["source_snapshot_status"] == status


def test_snapshot_serialization_failure_keeps_existing_report_unchanged():
    state = _captured_state()
    sqlite_mod.save_report(state)
    original = sqlite_mod.get_report("snapshot-report")
    # A future collector regression must fail before an existing row is changed.
    with patch.object(sqlite_mod, "snapshot_for_storage", return_value={"bad": object()}):
        with pytest.raises(TypeError):
            sqlite_mod.save_report({**state, "polished": "must not replace the original"})
    assert sqlite_mod.get_report("snapshot-report") == original
    assert sqlite_mod.count_reports() == 1


def test_capture_freezes_report_date_before_a_next_day_save(tmp_path):
    repo, commit = _git_repo(tmp_path)
    source_commit = commit("fix: work completed before midnight", "23")
    initial = _input_state(
        repo_path=repo.working_tree_dir, git_author="snapshot@example.invalid",
    )
    initial.pop("date")
    with patch("workdiary_agent.source_snapshot.work_date", return_value="2026-01-02"):
        frozen = {**initial, **capture_sources_node(initial)}
    assert frozen["date"] == "2026-01-02"
    assert frozen["source_snapshot"]["git"]["report_date"] == "2026-01-02"
    assert source_commit.hexsha[:7] in frozen["git_log"]

    with patch("workdiary_agent.nodes.save.work_date", return_value="2026-01-03"), patch(
        "workdiary_agent.storage.sqlite.work_date", return_value="2026-01-03",
    ):
        result = save_node(frozen)
    saved = sqlite_mod.get_report("snapshot-report")
    assert saved["date"] == "2026-01-02"
    assert saved["source_snapshot"]["git"]["report_date"] == saved["date"]
    assert "daily_report_2026-01-02_" in result["export_path"]
