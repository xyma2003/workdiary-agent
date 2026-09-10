"""Timezone consistency and checkpoint recovery tests."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from workdiary_agent.recovery import list_recoverable_runs
from workdiary_agent.paths import data_path
from workdiary_agent.time_utils import work_date


def test_work_date_uses_requested_timezone():
    instant = datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc)

    assert work_date("Asia/Shanghai", now=instant) == "2026-01-02"
    assert work_date("America/Los_Angeles", now=instant) == "2026-01-01"


def test_runtime_data_path_does_not_depend_on_cwd(tmp_path, monkeypatch):
    configured = tmp_path / "persistent-data"
    monkeypatch.setenv("WORKDIARY_DATA_DIR", str(configured))
    monkeypatch.chdir(tmp_path)

    assert data_path("history.db") == configured / "history.db"


def test_list_recoverable_runs_deduplicates_and_excludes_completed():
    graph = MagicMock()
    graph.checkpointer.list.return_value = [
        SimpleNamespace(
            config={"configurable": {"thread_id": "review-thread"}},
            checkpoint={"ts": "2026-01-02T09:00:00+08:00"},
        ),
        SimpleNamespace(
            config={"configurable": {"thread_id": "review-thread"}},
            checkpoint={"ts": "2026-01-02T08:00:00+08:00"},
        ),
        SimpleNamespace(
            config={"configurable": {"thread_id": "retry-thread"}},
            checkpoint={"ts": "2026-01-02T07:00:00+08:00"},
        ),
        SimpleNamespace(
            config={"configurable": {"thread_id": "done-thread"}},
            checkpoint={"ts": "2026-01-02T06:00:00+08:00"},
        ),
    ]
    snapshots = {
        "review-thread": SimpleNamespace(
            next=("review",),
            values={"raw_input": "review me", "revision_count": 1},
        ),
        "retry-thread": SimpleNamespace(
            next=("polish",),
            values={"raw_input": "retry me", "report_id": "report-2"},
        ),
        "done-thread": SimpleNamespace(
            next=(),
            values={"raw_input": "done", "final_report": "finished"},
        ),
    }
    graph.get_state.side_effect = lambda config: snapshots[
        config["configurable"]["thread_id"]
    ]

    runs = list_recoverable_runs(graph)

    assert [run["thread_id"] for run in runs] == [
        "review-thread",
        "retry-thread",
    ]
    assert runs[0]["status"] == "reviewing"
    assert runs[1]["status"] == "retryable"
