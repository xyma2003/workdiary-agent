# Roadmap: 智能日报 Agent (WorkDiary Agent)

## Overview

Six phases following the research-validated build order: graph skeleton first, then core LLM
nodes with template routing, then optional enrichment tools, then the high-risk HITL loop,
then storage, and finally the Streamlit UI last. Each layer is independently testable before
the next is added. The order prevents the most expensive debugging scenarios — topology bugs
are free to fix on stubs, HITL correctness is proven in a REPL before Streamlit rerun
semantics are introduced, and the UI is the thinnest layer added on top of working logic.

## Phases

- [x] **Phase 1: Graph Skeleton** - Runnable StateGraph with all nodes as stubs and correct edge wiring (completed 2026-04-23)
- [x] **Phase 2: Core LLM Nodes and Template Routing** - Extract, draft, polish nodes producing boss-friendly output; TemplateRouterAgent sub-graph (completed 2026-04-23)
- [x] **Phase 3: Enrichment Tools** - Optional git log and data input context enrichment (completed 2026-04-23)
- [ ] **Phase 4: Human-in-the-Loop** - Interrupt/resume cycle with SqliteSaver, revision loop capped at 3
- [ ] **Phase 5: Storage and Export** - SQLite history writes and markdown file export
- [ ] **Phase 6: Streamlit UI** - Full input-to-export UI wired to the working graph

## Phase Details

### Phase 1: Graph Skeleton
**Goal**: A runnable StateGraph exists with all nodes stubbed, correct conditional edges, and end-to-end invocability
**Depends on**: Nothing (first phase)
**Requirements**: AGENT-01
**Success Criteria** (what must be TRUE):
  1. `graph.invoke({"raw_input": "test"}, config)` runs without error and returns a dict
  2. All node names are present in the graph (extract, enrich, route_template, draft, polish, review, revise, save)
  3. The revise→review conditional edge respects `revision_count` — a state with `revision_count >= 3` routes to save, not revise
  4. AgentState TypedDict defines every field used downstream (raw_input, structured_info, template_type, draft, polished, human_decision, human_feedback, revision_count, git_log, repo_path, final_report, export_path)
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Install deps (langgraph 1.1.9 + 4 others) and write test suite in RED state
- [x] 01-02-PLAN.md — Create state.py (AgentState + StructuredInfo) and all 8 node stubs
- [x] 01-03-PLAN.md — Assemble graph.py, wire edges, compile with InMemorySaver, turn all 4 tests GREEN

### Phase 2: Core LLM Nodes and Template Routing
**Goal**: Real Claude API calls produce structured extraction, template-routed drafts, and boss-friendly polished output from raw Chinese work descriptions
**Depends on**: Phase 1
**Requirements**: AGENT-02, AGENT-05, AGENT-06, AGENT-07, TMPL-01, TMPL-02, TMPL-03
**Success Criteria** (what must be TRUE):
  1. Given a casual Chinese work description, the extract node returns a populated structured_info dict with at least task, output, blockers, and progress fields
  2. TemplateRouterAgent correctly classifies a technical input as "技术型", a business input as "业务型", and a mixed input as "混合型"
  3. The polished output leads with outcomes, contains at least one quantified statement (or explicit "未提供量化指标" marker), and uses goal-completion verbs (完成/推进/对齐/输出/跟进)
  4. User can see which template was selected ("已选用XX模板" visible in graph state)
  5. User can override the auto-selected template type and the draft re-generates using the chosen template
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — Write failing test suite (RED) for all 5 Phase 2 success criteria
- [x] 02-02-PLAN.md — Implement extract_node (LLM structured output) + TemplateRouterAgent sub-graph + route_template_node
- [x] 02-03-PLAN.md — Implement draft_node (3-template system) + polish_node (boss-perspective refinement)
- [x] 02-04-PLAN.md — Integration: turn all tests GREEN + human checkpoint for polished output quality

### Phase 3: Enrichment Tools
**Goal**: Optional git commit context and optional numeric/tabular data are safely ingested and available to downstream nodes without breaking the main flow when absent
**Depends on**: Phase 2
**Requirements**: AGENT-03, AGENT-04
**Success Criteria** (what must be TRUE):
  1. When a valid local git repo path is provided, today's commits appear in the polished report content
  2. When an invalid or empty repo path is provided, the graph completes normally with git_log set to None — no exception propagates
  3. When pasted numeric data or a CSV is provided, extracted metrics appear in the polished report; when absent, the report still generates without error
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Write failing test suite (RED) for all 3 Phase 3 success criteria
- [x] 03-02-PLAN.md — Add state.py fields (data_input, data_summary) + implement enrich_node (GitPython + LLM extraction)
- [x] 03-03-PLAN.md — Extend draft_node enrichment context + turn all 7 tests GREEN + human checkpoint

### Phase 4: Human-in-the-Loop
**Goal**: The graph reliably pauses for user review after polish, resumes correctly after a decision, loops on revision feedback up to 3 times, and force-exits to save on the third rejection
**Depends on**: Phase 3
**Requirements**: HITL-01, HITL-03, HITL-04
**Success Criteria** (what must be TRUE):
  1. After `graph.invoke()`, `graph.get_state(config).next` equals `["review"]` — the graph is paused, not completed
  2. After `Command(resume={"decision": "approve"})`, the graph reaches save and returns a final_report
  3. After `Command(resume={"decision": "revise", "feedback": "..."})`, the graph loops: polish → review pause → revision_count increments
  4. On the third rejection, the graph force-exits the loop and proceeds to save without a fourth interrupt
  5. Full interrupt/resume cycle verified in a standalone Python script (not Streamlit) before this phase is declared done
**Plans**: 4 plans

Plans:
- [x] 04-01-PLAN.md — Write RED test suite (9 tests covering all 5 HITL success criteria)
- [ ] 04-02-PLAN.md — graph.py topology update: route_after_review, updated route_after_revise, SqliteSaver parameterization
- [ ] 04-03-PLAN.md — Node implementations: review_node (interrupt), revise_node, polish_node (human_feedback), save_node (final_report)
- [ ] 04-04-PLAN.md — Turn all tests GREEN + scripts/test_hitl_cycle.py + human verification checkpoint

### Phase 5: Storage and Export
**Goal**: Every completed report is persisted to SQLite history and exportable as a dated markdown file, using a dedicated database separate from LangGraph checkpoints
**Depends on**: Phase 4
**Requirements**: STORE-01, STORE-02, STORE-03
**Success Criteria** (what must be TRUE):
  1. After a completed HITL cycle, a row appears in history.db with date, template_type, raw_input, and polished content fields populated
  2. `storage/sqlite.py` queries return reports ordered by date descending — most recent report is first
  3. Calling the markdown export function produces a `.md` file named with the current date (e.g., `daily_report_2026-04-22.md`) containing the polished report
  4. history.db and graph_state.db are separate files — app code never writes to graph_state.db
**Plans**: TBD

### Phase 6: Streamlit UI
**Goal**: A Streamlit app covers the full workflow — input, agent processing status, review with inline editing, accept/revise/export actions, and history browsing — wired to the working graph via session_state
**Depends on**: Phase 5
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, HITL-02
**Success Criteria** (what must be TRUE):
  1. User submits a work description and optional git path in the input form, clicks Generate, and sees processing status labels update as each node runs ("正在提取信息..." / "正在润色...")
  2. After generation, the polished report renders in an editable text area and "已选用XX模板" is displayed — user can accept, request revision with feedback, or edit inline
  3. Clicking "导出" downloads a dated markdown file without page reload errors
  4. Navigating to the history view shows past reports in date-descending order
  5. Clicking a new widget after generation does not regenerate a new thread_id or restart the graph — the existing session is preserved in st.session_state
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Graph Skeleton | 3/3 | Complete   | 2026-04-23 |
| 2. Core LLM Nodes and Template Routing | 4/4 | Complete    | 2026-04-23 |
| 3. Enrichment Tools | 3/3 | Complete   | 2026-04-23 |
| 4. Human-in-the-Loop | 1/4 | In Progress|  |
| 5. Storage and Export | 0/TBD | Not started | - |
| 6. Streamlit UI | 0/TBD | Not started | - |
