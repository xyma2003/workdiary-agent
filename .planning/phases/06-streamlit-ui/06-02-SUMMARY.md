---
phase: "06-streamlit-ui"
plan: "02"
subsystem: "ui"
tags: [streamlit, langgraph, hitl, interrupt, command-resume, st-status, download-button]
dependency_graph:
  requires: ["06-01", "workdiary_agent.graph.build_graph", "workdiary_agent.storage.sqlite.get_all_reports"]
  provides: ["app.py:_run_generation", "app.py:_render_review_ui", "full generate->pause->review->accept/revise flow"]
  affects: ["app.py"]
tech_stack:
  added: ["langgraph.types.Command", "datetime.date"]
  patterns:
    - "st.status with expanded=True for node progress labels before blocking invoke()"
    - "graph.get_state(config).next to detect interrupt pause after invoke()"
    - "result['__interrupt__'][0].value for interrupt payload (polished, template_type)"
    - "Command(resume={'decision':'approve'/'revise','feedback':...}) for HITL resume"
    - "key='edit_area' on text_area so st.session_state['edit_area'] holds live edited value"
    - "st.download_button(data=text_str) — no file read, no page reload (D-19)"
key_files:
  modified:
    - path: "app.py"
      role: "Streamlit app — full generation flow and HITL review UI"
      lines: 293
decisions:
  - "NODE_LABELS dict defined inside _run_generation() (not module-level) for locality; matches D-12 exactly"
  - "st.status labels written synchronously before blocking invoke() — intentional since LangGraph .invoke() is blocking; labels serve as context, not real-time progress"
  - "'review' in (graph_state.next or []) — tuple membership check, not equality, to handle tuple or list returns"
  - "_show_feedback initialized in session_state init block to prevent KeyError on first render"
  - "Inline-edit path (D-18): if edited_text != polished after approve, override polished in result dict for export consistency"
metrics:
  duration: "2m"
  completed_date: "2026-04-24"
  tasks_completed: 2
  files_modified: 1
---

# Phase 06 Plan 02: Generation Flow and HITL Review UI Summary

**One-liner:** Full generate→pause→review flow: st.status node labels, interrupt detection via graph.get_state().next, editable text_area with key, and Command(resume=...) wired to accept/revise/export buttons.

## What Was Built

Extended `app.py` with three new functions:

**`_render_status_and_review()`** (replacement of stub): State dispatcher — calls `_run_generation()` when `app_state=="generating"`, `_render_review_ui()` when `app_state=="reviewing"`, and shows success + restart button when `app_state=="done"`.

**`_run_generation()`** (new): Invokes the graph with `st.status` showing NODE_LABELS (D-11/D-12/D-13). After `invoke()` returns, checks `graph.get_state(config).next` for interrupt. If `"review"` is in `.next`, extracts `result["__interrupt__"][0].value` for polished content and transitions `app_state` to `"reviewing"`. Handles errors with `status="error"`.

**`_render_review_ui()`** (new): Shows `st.caption(f"已选用 {template_type} 模板")` (TMPL-02), editable `st.text_area` with `key="edit_area"` (HITL-02/D-14), and three-column button row (D-15):
- Accept: `Command(resume={"decision":"approve","feedback":""})` + inline-edit override (D-16/D-18)
- Revise: shows `st.text_input` for feedback + confirm button → `Command(resume={"decision":"revise","feedback":...})`, re-checks interrupt for re-review loop (D-17)
- Export: `st.download_button(data=export_text, ...)` passing text directly — no file read (D-19)

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Generation flow: graph invoke + st.status + interrupt detection | 89402e0 | app.py |
| 2 | Review UI: editable text_area, accept/revise/export buttons | 89402e0 | app.py |

*(Tasks 1 and 2 were committed together as a single atomic unit — both modify app.py and implement one cohesive feature.)*

## Deviations from Plan

None — plan executed exactly as written.

## Success Criteria Verification

- [x] `_render_status_and_review()` implements st.status with NODE_LABELS dict
- [x] `graph.invoke()` called with correct config (`{"configurable": {"thread_id": st.session_state.thread_id}}`)
- [x] Interrupt detection: `"review" in graph.get_state(config).next`
- [x] Editable `text_area` with `key="edit_area"`
- [x] Three buttons: accept (Command approve), revise (feedback + Command revise), export (st.download_button)
- [x] `Command(resume={"decision": "approve"/"revise", "feedback": ...})` pattern — 2 occurrences
- [x] `st.download_button` with `data=` parameter (text content, no file read)
- [x] `st.caption(f"已选用 {template_type} 模板")` displayed above text_area
- [x] Committed with --no-verify

## Known Stubs

None — all functionality is wired. `_render_history_page()` remains a stub but is out of scope for this plan (implemented in 06-03).

## Self-Check: PASSED
