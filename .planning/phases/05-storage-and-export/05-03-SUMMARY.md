---
phase: "05"
plan: "03"
subsystem: storage-integration
tags: [save-node, sqlite, markdown-export, hitl-integration]
dependency_graph:
  requires: ["05-01", "05-02"]
  provides: ["wired-save-node", "history-db-writes", "markdown-exports"]
  affects: ["workdiary_agent/nodes/save.py", "AgentState.export_path"]
tech_stack:
  added: []
  patterns: ["storage-layer-wiring", "node-calls-storage-api"]
key_files:
  created: [".gitignore"]
  modified: ["workdiary_agent/nodes/save.py"]
decisions:
  - "save_node is the single write point for history.db — no other node touches it"
  - "polished or '' guards against None state fields at the boundary"
  - "Phase 4 HITL tests tolerate real history.db/exports/ writes during test_approve_path and test_force_exit (no mock needed — acceptable side effect for integration coverage)"
metrics:
  duration: "~5min"
  completed_date: "2026-04-24"
  tasks_completed: 2
  tasks_total: 3
  files_modified: 2
---

# Phase 5 Plan 03: Wire save_node to Storage Layer Summary

**One-liner:** Upgraded save_node to call save_report(state) + save_markdown(polished, date), wiring history.db writes and markdown exports into the live graph; all 33 tests GREEN.

## What Was Built

`workdiary_agent/nodes/save.py` was upgraded from a Phase 4 stub that returned `export_path: None` to a fully wired node that:

1. Calls `save_report(state)` to persist the completed report row to `history.db` (D-04)
2. Calls `save_markdown(polished, today)` to write `exports/daily_report_{YYYY-MM-DD}.md` (D-05, D-06)
3. Returns `export_path` in the state dict for Phase 6 Streamlit UI (D-07)

The `polished or ""` guard handles `None` in Optional state fields without masking real errors (no bare except — storage errors propagate).

## Tasks Completed

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1 | Upgrade save_node to call save_report and save_markdown | DONE | f435597 |
| 2 | Run full test suite — all tests GREEN | DONE | 4d65679 |
| 3 | Human verification — HITL cycle with history.db and markdown export | PENDING HUMAN |  |

## Test Results

```
33 passed in 97.20s
  tests/test_phase05_storage.py:  7 passed (all Phase 5 criteria)
  tests/test_phase04_hitl.py:    10 passed (no regression from save_node change)
  tests/test_phase03_enrichment.py: 7 passed
  tests/test_phase02_llm_nodes.py:  5 passed
  tests/test_graph_skeleton.py:     4 passed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Added .gitignore to suppress generated runtime files**
- **Found during:** Task 2 (post-test `git status`)
- **Issue:** No `.gitignore` existed; test run produced `history.db`, `exports/`, and `__pycache__/` as untracked files
- **Fix:** Created `.gitignore` excluding `*.db`, `exports/`, `__pycache__/`, `.pytest_cache/`, etc.
- **Files modified:** `.gitignore` (new)
- **Commit:** 4d65679

## Known Stubs

None — `save_node` is fully wired. `export_path` is returned with a real file path, not `None`.

## Awaiting Human Verification (Task 3)

Task 3 is a `checkpoint:human-verify`. The human must:

1. Run the HITL verification script:
   ```bash
   conda run -n llm-data-pipeline python scripts/test_hitl_cycle.py
   ```
   Approve the report when prompted.

2. Verify `history.db` was created with a data row:
   ```bash
   conda run -n llm-data-pipeline python -c "
   import sqlite3
   conn = sqlite3.connect('history.db')
   rows = conn.execute('SELECT date, template_type, raw_input, polished FROM reports ORDER BY date DESC').fetchall()
   conn.close()
   print(f'{len(rows)} row(s) in history.db')
   for r in rows:
       print(f'  date={r[0]}, template={r[1]}, raw_input preview: {r[2][:30]}...')
   "
   ```

3. Verify the markdown export exists:
   ```bash
   ls -la exports/daily_report_*.md
   cat exports/daily_report_$(date +%Y-%m-%d).md | head -10
   ```

4. Verify `graph_state.db` and `history.db` are separate:
   ```bash
   ls -la graph_state.db history.db
   ```

**Resume signal:** Type "approved" if all 4 checks pass.

## Self-Check: PASSED

- workdiary_agent/nodes/save.py: FOUND
- .gitignore: FOUND
- Commit f435597: FOUND (feat(05-03): upgrade save_node...)
- Commit 4d65679: FOUND (chore(05-03): all 33 tests GREEN...)
