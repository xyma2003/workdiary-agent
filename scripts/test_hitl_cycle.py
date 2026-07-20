#!/usr/bin/env python3
"""
Standalone HITL verification script — Phase 4 Success Criteria 5.
ROADMAP §Phase 4 SC-5: "Full interrupt/resume cycle verified in a standalone
Python script (not Streamlit) before this phase is declared done."

Demonstrates all 3 paths:
  Path 1 — Approve directly: invoke → approve → final_report + END
  Path 2 — Revise once then approve: invoke → revise(×1) → loop pause → approve → END
  Path 3 — Force-exit after 3 revisions: invoke → revise(×3) → END (no 4th interrupt)

Uses InMemorySaver (build_graph() default) with LLM nodes mocked to avoid API calls.
Run: conda run -n llm-data-pipeline python scripts/test_hitl_cycle.py
"""
import sys
import os
from unittest.mock import patch, MagicMock

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from langgraph.types import Command
from workdiary_agent.graph import build_graph
from workdiary_agent.state import StructuredInfo


# ---------------------------------------------------------------------------
# LLM mock helpers (avoids real API calls while exercising real interrupt logic)
# ---------------------------------------------------------------------------

def _make_llm_mock(return_text: str = "polished draft content") -> MagicMock:
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = return_text
    mock_llm.invoke.return_value = mock_response
    # with_structured_output must return mock whose invoke() gives a real StructuredInfo
    # so LangGraph's msgpack checkpointer can serialize the state.
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = StructuredInfo(
        tasks=["完成登录模块开发"],
        outputs=["登录模块代码"],
        blockers=[],
        progress="100%",
    )
    mock_llm.with_structured_output.return_value = mock_structured
    return mock_llm


def _all_llm_patches():
    """Return list of context managers that mock all LLM-calling nodes."""
    return [
        patch("workdiary_agent.nodes.extract._make_llm", return_value=_make_llm_mock()),
        patch("workdiary_agent.nodes.draft._make_llm",
              return_value=_make_llm_mock("【已选用混合型模板】\n日报初稿")),
        patch("workdiary_agent.nodes.polish._make_llm",
              return_value=_make_llm_mock("polished: 完成登录模块，覆盖核心业务流程")),
        patch("workdiary_agent.nodes.enrich._make_llm", return_value=_make_llm_mock()),
        patch("workdiary_agent.nodes.route_template.TemplateRouterAgent.classify",
              return_value="混合型"),
    ]


def _enter_patches(patches):
    for p in patches:
        p.__enter__()
    return patches


def _exit_patches(patches):
    for p in reversed(patches):
        p.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Path 1: Approve directly
# ---------------------------------------------------------------------------

def test_path1_approve():
    """SC-1 + SC-2: invoke → pauses at review → approve → final_report + END."""
    g = build_graph()  # InMemorySaver, no disk writes
    cfg = {"configurable": {"thread_id": "hitl-path1"}}

    patches = _all_llm_patches()
    _enter_patches(patches)
    try:
        r1 = g.invoke({"raw_input": "今天完成了登录模块开发"}, cfg)
    finally:
        _exit_patches(patches)

    # SC-1: graph must be paused at review
    state = g.get_state(cfg)
    assert "review" in state.next, (
        f"FAIL Path1: expected paused at 'review', got state.next={state.next}"
    )
    assert "__interrupt__" in r1, (
        f"FAIL Path1: expected '__interrupt__' in result, got keys={list(r1.keys())}"
    )
    interrupt_payload = r1["__interrupt__"][0].value
    assert "polished" in interrupt_payload, (
        f"FAIL Path1: interrupt payload missing 'polished' key: {interrupt_payload}"
    )
    print(f"  SC-1 OK: graph paused at review (revision_count={interrupt_payload.get('revision_count', 0)})")

    # SC-2: approve → final_report + END
    r2 = g.invoke(Command(resume={"decision": "approve", "feedback": ""}), cfg)
    assert r2.get("final_report"), (
        f"FAIL Path1: final_report should be non-empty after approve, got: {r2.get('final_report')!r}"
    )
    state2 = g.get_state(cfg)
    assert not state2.next, (
        f"FAIL Path1: graph should be at END after approve, got state.next={state2.next}"
    )
    print(f"  SC-2 OK: final_report={r2['final_report'][:50]!r}... graph at END")
    print("PASS: Path 1 (approve directly)")


# ---------------------------------------------------------------------------
# Path 2: Revise once then approve
# ---------------------------------------------------------------------------

def test_path2_revise_then_approve():
    """SC-3: invoke → revise(×1) → pauses again at review → approve → END."""
    g = build_graph()
    cfg = {"configurable": {"thread_id": "hitl-path2"}}

    patches = _all_llm_patches()
    _enter_patches(patches)
    try:
        g.invoke({"raw_input": "今天完成了登录模块开发"}, cfg)
    finally:
        _exit_patches(patches)

    # First revise — polish is called again, so mock it
    polish_patch = patch(
        "workdiary_agent.nodes.polish._make_llm",
        return_value=_make_llm_mock("revised: 完成登录模块，优化了安全性"),
    )
    with polish_patch:
        g.invoke(Command(resume={"decision": "revise", "feedback": "请加上安全性说明"}), cfg)

    state = g.get_state(cfg)
    assert "review" in state.next, (
        f"FAIL Path2: expected paused at 'review' after revise, got {state.next}"
    )
    count = state.values.get("revision_count", 0)
    assert count == 1, f"FAIL Path2: revision_count should be 1, got {count}"
    feedback_in_state = state.values.get("human_feedback", "")
    assert "安全性" in feedback_in_state, (
        f"FAIL Path2: human_feedback should contain '安全性', got {feedback_in_state!r}"
    )
    print(f"  SC-3 OK: paused at review again, revision_count={count}, feedback stored")

    # Now approve
    r = g.invoke(Command(resume={"decision": "approve", "feedback": ""}), cfg)
    assert r.get("final_report"), "FAIL Path2: final_report empty after approve"
    assert not g.get_state(cfg).next, "FAIL Path2: graph not at END after approve"
    print("PASS: Path 2 (revise once then approve)")


# ---------------------------------------------------------------------------
# Path 3: Force-exit after 3 revisions
# ---------------------------------------------------------------------------

def test_path3_force_exit():
    """SC-4: invoke → revise(×3) → force-exits to save → END without 4th interrupt."""
    g = build_graph()
    cfg = {"configurable": {"thread_id": "hitl-path3"}}

    patches = _all_llm_patches()
    _enter_patches(patches)
    try:
        g.invoke({"raw_input": "今天完成了登录模块开发"}, cfg)
    finally:
        _exit_patches(patches)

    for i in range(3):
        polish_patch = patch(
            "workdiary_agent.nodes.polish._make_llm",
            return_value=_make_llm_mock(f"revision {i+1}: 完成登录模块"),
        )
        with polish_patch:
            g.invoke(
                Command(resume={"decision": "revise", "feedback": f"第{i+1}次修改意见"}),
                cfg,
            )
        state_mid = g.get_state(cfg)
        if i < 2:
            # After 1st and 2nd revise: still paused at review
            assert "review" in state_mid.next, (
                f"FAIL Path3: after revise {i+1} expected paused at review, "
                f"got {state_mid.next}"
            )
            print(f"  Revise {i+1}: still paused at review (revision_count={state_mid.values.get('revision_count', 0)})")
        else:
            # After 3rd revise: should be at END (force-exit)
            assert not state_mid.next, (
                f"FAIL Path3: after 3rd revise expected END, got {state_mid.next}. "
                "route_after_revise guard (count>=3->save) may not be working."
            )

    state = g.get_state(cfg)
    assert not state.next, (
        f"FAIL Path3: expected END after 3 revisions, got state.next={state.next}"
    )
    count = state.values.get("revision_count", 0)
    assert count == 3, f"FAIL Path3: revision_count should be 3, got {count}"
    assert state.values.get("final_report"), (
        "FAIL Path3: final_report must be non-empty after force-exit"
    )
    print(f"  SC-4 OK: force-exited to save at revision_count={count}, no 4th interrupt")
    print("PASS: Path 3 (force-exit after 3 revisions)")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("Phase 4 HITL Verification — all 3 paths")
    print("=" * 60)
    failures = []

    for name, fn in [
        ("Path 1 — approve directly", test_path1_approve),
        ("Path 2 — revise once then approve", test_path2_revise_then_approve),
        ("Path 3 — force-exit after 3 revisions", test_path3_force_exit),
    ]:
        print(f"\n--- {name} ---")
        try:
            fn()
        except AssertionError as e:
            print(f"FAIL: {e}")
            failures.append(name)
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            failures.append(name)

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED: {len(failures)}/3 paths failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("ALL 3 PATHS PASSED — Phase 4 HITL verified")
        print("SC-5: interrupt/resume cycle confirmed in standalone script")
    print("=" * 60)
