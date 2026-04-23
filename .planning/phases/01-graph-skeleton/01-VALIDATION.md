---
phase: 1
slug: graph-skeleton
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5 (in llm-data-pipeline conda env) |
| **Config file** | None — Wave 0 creates `tests/test_graph_skeleton.py` |
| **Quick run command** | `conda run -n llm-data-pipeline python scripts/test_skeleton.py` |
| **Full suite command** | `conda run -n llm-data-pipeline pytest tests/test_graph_skeleton.py -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `conda run -n llm-data-pipeline python scripts/test_skeleton.py`
- **After every plan wave:** Run `conda run -n llm-data-pipeline pytest tests/test_graph_skeleton.py -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | AGENT-01 | infra | `pip install langgraph==1.1.9 ...` exits 0 | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | SC-4 | unit | `pytest tests/test_graph_skeleton.py::test_agent_state_fields -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | SC-4 | unit | `pytest tests/test_graph_skeleton.py::test_agent_state_fields -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | SC-2 | unit | `pytest tests/test_graph_skeleton.py::test_all_nodes_present -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 1 | SC-3 | unit | `pytest tests/test_graph_skeleton.py::test_conditional_edge_logic -x` | ❌ W0 | ⬜ pending |
| 1-01-06 | 01 | 2 | SC-1 | smoke | `pytest tests/test_graph_skeleton.py::test_invoke_no_error -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_graph_skeleton.py` — test stubs for SC-1 through SC-4 and AGENT-01
- [ ] `scripts/test_skeleton.py` — standalone quick-check script (no pytest required)
- [ ] `tests/__init__.py` — empty init for test discovery
- [ ] Install: `pip install "langgraph==1.1.9" "langchain-anthropic==1.4.1" "langgraph-checkpoint-sqlite==3.0.3" "streamlit==1.56.0" "gitpython==3.1.47"` into llm-data-pipeline env

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
