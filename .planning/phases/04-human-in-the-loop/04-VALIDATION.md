---
phase: 4
slug: human-in-the-loop
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-24
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing — all prior phases use it) |
| **Config file** | none (run with conda run) |
| **Quick run command** | `conda run -n llm-data-pipeline pytest tests/test_phase04_hitl.py -v` |
| **Full suite command** | `conda run -n llm-data-pipeline pytest tests/ -v` |
| **Estimated runtime** | ~10s (mocked LLMs) |

---

## Sampling Rate

- **After every task commit:** Run `conda run -n llm-data-pipeline pytest tests/test_phase04_hitl.py -v`
- **After every plan wave:** Run `conda run -n llm-data-pipeline pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-T1 | 01 | 1 | HITL-01, HITL-03, HITL-04 | unit (TDD RED) | `pytest tests/test_phase04_hitl.py -v` | ❌ W0 | ⬜ pending |
| 04-02-T1 | 02 | 2 | HITL-01, HITL-03, HITL-04 | unit | `pytest tests/test_phase04_hitl.py -k "route" -v` | ❌ W0 | ⬜ pending |
| 04-03-T1 | 03 | 2 | HITL-01, HITL-03 | unit | `python -c "from workdiary_agent.nodes.review import review_node; print('OK')"` | ❌ W0 | ⬜ pending |
| 04-03-T2 | 03 | 2 | HITL-03, HITL-04 | unit | `python -c "from workdiary_agent.nodes.save import save_node; print('OK')"` | ❌ W0 | ⬜ pending |
| 04-04-T1 | 04 | 3 | HITL-01, HITL-03, HITL-04 | unit (GREEN) | `pytest tests/test_phase04_hitl.py -v` | ❌ W0 | ⬜ pending |
| 04-04-T2 | 04 | 3 | SC-5 | smoke | `conda run -n llm-data-pipeline python scripts/test_hitl_cycle.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase04_hitl.py` — covers HITL-01, HITL-03, HITL-04 (created in plan 04-01)
- [ ] `scripts/test_hitl_cycle.py` — covers SC-5 standalone verification, all 3 paths (created in plan 04-04)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full interrupt/resume cycle output quality | SC-5 | Requires human judgment on report quality | Run scripts/test_hitl_cycle.py and confirm all 3 paths produce sensible output |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test_phase04_hitl.py + test_hitl_cycle.py)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
