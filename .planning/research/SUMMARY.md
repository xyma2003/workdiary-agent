# Project Research Summary

**Project:** 智能日报 Agent (WorkDiary Agent)
**Domain:** LangGraph multi-node AI agent with human-in-the-loop and Streamlit UI
**Researched:** 2026-04-22
**Confidence:** HIGH

## Executive Summary

智能日报 Agent is a single-user, AI-assisted daily work report generator targeted at Chinese workplace professionals. The core value proposition is transforming casual, unstructured input into boss-friendly, quantified, section-structured reports without manual formatting effort. Research confirms the domain is well-understood: the technology stack (LangGraph 1.x, langchain-anthropic, Streamlit, SQLite) is stable and thoroughly documented, the feature set maps cleanly to established Chinese workplace reporting conventions, and the LangGraph interrupt/resume pattern provides a reliable foundation for the human-in-the-loop approval flow that is essential for user trust in an AI writing tool.

The recommended build approach is a 7-node StateGraph with a compiled TemplateRouterAgent sub-graph for template classification, two separate SQLite databases (one for LangGraph checkpoints, one for report history), and a Streamlit UI wired to LangGraph's synchronous graph.invoke() / graph.stream() APIs. The key architectural insight is that Streamlit must cache the graph object via @st.cache_resource and persist thread_id in st.session_state — failure to do either causes silent restart bugs that are the single most common integration failure point. The build order must go skeleton first, then core LLM nodes, then routing, then HITL, then storage, then UI — each layer is independently testable and this order minimizes debugging complexity.

The principal risks are: (1) broad try/except blocks silently swallowing the interrupt() control-flow exception, destroying the HITL step without an obvious error; (2) Streamlit rerun semantics regenerating thread_id on every widget interaction, breaking graph resume; and (3) scope creep into streaming output, history search, or custom template editors, which individually look small but each adds at least a day of work to a one-week build. All three risks have clear, concrete prevention strategies documented in the research.

---

## Key Findings

### Recommended Stack

The stack is narrow and dependency-minimal by design. LangGraph 1.1.9 is a major rewrite from 0.x with a cleaner interrupt/Command API; versions are pinned and verified directly from PyPI wheel inspection. The full `langchain` meta-package must NOT be installed — only `langchain-core` and `langchain-anthropic` are needed. Two separate SQLite files serve different purposes and must not be merged.

**Core technologies:**

| Technology | Version | Purpose | Confidence |
|------------|---------|---------|------------|
| langgraph | 1.1.9 | StateGraph, interrupt/Command, graph execution | HIGH — wheel inspected |
| langchain-anthropic | 1.4.1 | ChatAnthropic wrapper, bind_tools, with_structured_output | HIGH — source verified |
| anthropic | >=0.96.0 | Required by langchain-anthropic; direct SDK fallback | HIGH |
| langgraph-checkpoint-sqlite | 3.0.3 | SqliteSaver for HITL state persistence | HIGH — wheel inspected |
| pydantic | 2.12.4 | Structured LLM output schemas | HIGH — installed |
| streamlit | 1.56.0 | UI, session_state, chat_message | HIGH — PyPI verified |
| gitpython | 3.1.47 | Read git commits for optional context tool | MEDIUM — API from training knowledge |

**Model:** `claude-sonnet-4-5` — verified in langchain_anthropic profiles as having `tool_calling: True` and `structured_output: True`.

**Interrupt pattern decision:** Use `interrupt_before=["review"]` at compile time for the "always pause" guarantee, combined with `Command(resume=...)` for the resume call. PITFALLS.md flags `Command(resume=...)` as safer than `graph.update_state()` + `graph.invoke(None)` across LangGraph versions.

**Minimal requirements.txt:**
```
langgraph==1.1.9
langchain-anthropic==1.4.1
langgraph-checkpoint-sqlite==3.0.3
streamlit==1.56.0
gitpython==3.1.47
```

---

### Expected Features

The feature research is grounded in Chinese workplace reporting conventions and LangGraph HITL design patterns. The hardest feature to deliver is "boss-friendly" output — leading with outcomes, quantifying everything quantifiable, surfacing blockers with ownership — which is 80% prompt engineering and is the core differentiator over a generic GPT wrapper.

**Must have (MVP — week one):**
- Natural-language input accepted without formatting requirements
- Three template types: technical (engineers), business (sales/ops/BD), hybrid (PMs, leads)
- Structured output sections: 今日完成, 进度, 量化指标, 风险/问题, 明日计划
- Boss-friendly rewriting: outcomes over activities, quantification, blocker surfacing with ownership, forward-looking close
- Human review interrupt: Accept / Reject-with-feedback / Direct inline edit
- Retry loop capped at 3 revisions, accumulating rejection context each pass
- Markdown export to file
- SQLite history (write + date-sorted read)
- Streamlit UI covering full input → review → export flow

**Should have (stretch goals, in priority order):**
- Git log optional context tool — grounding LLM output in actual commit evidence is the strongest "real agent" signal
- Diff view showing raw input vs polished output — low complexity, high demo value
- Section-targeted feedback ("fix just the blockers section") — shows HITL sophistication

**Defer to v2+:**
- Confidence scoring per section (self-evaluation adds latency)
- Writing style memory / personalization (requires embedding + retrieval)
- Voice input
- External integrations (Feishu, DingTalk, WeChat Work)
- Streaming token-by-token UI display

**Critical anti-features — do not implement even if they look small:**
- Streaming output display (+1 day of plumbing)
- History search/filter (+1 day of UI)
- User-editable prompt templates (+1 day of validation/storage)
- Multi-user / auth (wrong scope)

---

### Architecture Approach

The architecture is a linear StateGraph with a single cyclic sub-path (revise → review loop). The TemplateRouterAgent is implemented as a compiled sub-graph — a 2-step classify+select workflow, not a full multi-agent handoff. Streamlit connects to LangGraph via synchronous APIs only. The state schema uses TypedDict (not Pydantic BaseModel) for simplicity and compatibility with LangGraph's Annotated reducers.

**Node responsibility matrix:**

| Node | Reads | Writes | LLM? |
|------|-------|--------|------|
| extract | raw_input | structured_info | YES |
| enrich | structured_info, repo_path | git_log (optional) | NO — tool call |
| route_template | structured_info | template_type, selected_template | YES — via sub-graph |
| draft | structured_info, selected_template, git_log | draft | YES |
| polish | draft | polished | YES |
| review | human_decision | human_decision | NO — pure router |
| revise | polished, human_feedback | polished, revision_count | YES |
| save | polished | final_report, export_path, history_id | NO — IO only |

**Conditional edge flow:**
```
START → extract → enrich → route_template → draft → polish
polish → [interrupt_before review] → review
review → save  (if approve or revision_count >= 3)
review → revise  (else)
revise → review  (loop back, interrupted again)
save → END
```

**Component boundaries:**

| Component | Location |
|-----------|----------|
| Graph definition | agent/graph.py |
| State schema | agent/state.py |
| Node implementations | agent/nodes/ |
| TemplateRouterAgent sub-graph | agent/router/ |
| Prompt templates | agent/prompts/ |
| Git tool | agent/tools/git_tool.py |
| LangGraph checkpoint DB | graph_state.db (LangGraph-owned) |
| Application history DB | history.db (app-owned) |
| Storage layer | storage/sqlite.py, storage/markdown.py |
| Streamlit app | ui/app.py + ui/components/ |

---

### Critical Pitfalls

The top pitfalls most likely to cause wasted days on this specific project. Full details in PITFALLS.md.

1. **interrupt() swallowed by try/except (C1) — silent HITL killer.** The `interrupt()` function raises an internal exception for control flow. Any `try/except Exception` in the same node catches it silently. The graph runs through "review" without pausing. Detection: `graph.get_state(config).next` is empty right after invoke. Prevention: never put `interrupt()` inside a try/except; keep the review node as a pure router with no other logic.

2. **thread_id regenerated on Streamlit rerun (C2) — breaks graph resume.** Streamlit reruns the full script on every widget click. If `thread_id = uuid.uuid4()` is at the script body level, a new UUID is generated on every rerun and resume silently starts a new graph instead. Prevention: store thread_id in `st.session_state` at initialization; never regenerate outside of "start new session" logic.

3. **State mutation instead of return (C4) — changes silently discarded.** Assigning `state["draft"] = result` inside a node does nothing — state is read-only. Only values in the returned dict are merged into graph state. Prevention: annotate every node as `-> dict` and run mypy; code review rule: no assignments to `state[...]`.

4. **No loop guard on revise cycle (C6) — GRAPH_RECURSION_LIMIT crash.** Without a `revision_count >= MAX_REVISIONS` exit condition, the revise loop runs until LangGraph's recursion limit (default 25) and crashes with `GRAPH_RECURSION_LIMIT`. Prevention: implement the force-exit path in the conditional edge and ensure `revise` node increments `revision_count` on every call.

5. **Shared SQLite file for checkpoints and history (C7) — schema collision.** LangGraph's SqliteSaver writes internal binary blobs into its own tables. Mixing with application tables risks name collision. Prevention: two separate files — `graph_state.db` (LangGraph-owned, never touched by app code) and `history.db` (app-owned). Always call `checkpointer.setup()` before first compile.

6. **Graph recreated on every Streamlit rerun without @st.cache_resource (M2).** Without caching, a new graph object is created on every widget interaction. Even with SqliteSaver, the new object has no continuity. Prevention: wrap `build_graph()` with `@st.cache_resource`.

---

## Implications for Roadmap

The architecture file's 6-layer build order is the correct structure. Each layer is independently testable, and the ordering ensures HITL correctness is proven before Streamlit complexity is added. Suggested phases below map directly to those layers with pitfall awareness integrated.

### Phase 1: Graph Skeleton and State Schema

**Rationale:** Graph topology bugs are cheapest to catch when nodes are stubs. Establishing TypedDict schema and all edge wiring before any LLM code prevents architectural rework.

**Delivers:** Runnable StateGraph with all nodes as stubs, correct conditional edges, InMemorySaver checkpointer, verifiable end-to-end execution via `graph.invoke(minimal_state, config)`.

**Implements:** AgentState TypedDict, all node stubs (`return {}`), StateGraph wiring, node name constants, `revision_count` loop guard in conditional edge.

**Avoids:** C3 (None return), C6 (no loop guard), M4 (conditional edge returns unmapped value). Establish `-> dict` annotation rule on Day 1.

**Research flag:** Standard patterns. No additional research needed.

---

### Phase 2: Core LLM Nodes

**Rationale:** The extraction prompt is the foundation of everything downstream — bad structured_info poisons every subsequent node. Test in isolation with real sample inputs before connecting.

**Delivers:** Working `extract`, `draft`, and `polish` nodes producing boss-friendly output from unstructured Chinese input. Pydantic schemas for structured output validated against real inputs.

**Implements:** Boss-friendly writing principles (outcomes over activities, quantification, blocker surfacing, forward-looking close), three template prompt variants, flat Pydantic extraction schema (5-6 fields max).

**Avoids:** M5 (over-complex Pydantic schema — keep flat and short Field descriptions).

**Research flag:** Prompt engineering quality cannot be validated from research alone. Budget 2h for iterating extraction and polish prompts with real inputs. This is the highest-value work in the project.

---

### Phase 3: TemplateRouterAgent Sub-Graph

**Rationale:** Routing depends on structured_info from Phase 2. Sub-graph pattern demonstrates multi-agent architecture without over-engineering.

**Delivers:** Compiled RouterGraph that takes structured_info and returns template_type + selected_template string, integrated into parent graph.

**Implements:** RouterState TypedDict, classify_node (LLM with structured output), select_template_node (deterministic dict lookup), wrapper node in parent graph with explicit field projection.

**Avoids:** M3 (state mismatch — wrapper node must project only RouterState-required fields from AgentState).

**Research flag:** Standard patterns. Sub-graph as callable node is well-documented.

---

### Phase 4: Git Log Enrichment Tool

**Rationale:** Optional context enrichment — strongest portfolio demo signal but must not gate the main flow. Implement after core is stable so optional failures don't confuse core debugging.

**Delivers:** Exception-safe `enrich` node with None-guard. Main flow works with or without a valid repo_path.

**Implements:** git_tool.py with full exception handling, GitPython Repo.iter_commits(since='24 hours ago'), graceful degradation to git_log=None.

**Avoids:** m4 (InvalidGitRepositoryError propagates — every exception must be caught in enrich node, never re-raised to graph runner).

**Research flag:** Standard patterns. Quick validation: test git_tool.py standalone with a local repo before wiring into enrich node.

---

### Phase 5: Human-in-the-Loop

**Rationale:** Most failure-prone phase. Test interrupt/resume cycle in Python REPL before touching Streamlit. Switch from InMemorySaver to SqliteSaver here.

**Delivers:** Verified interrupt/resume cycle. Graph pauses at review, correctly resumes after Command(resume=...), revise node increments revision_count, force-exit fires at 3 revisions.

**Implements:** `interrupt_before=["review"]` at compile time, review node (pure router — calls interrupt(), no LLM), revise node with `revision_count + 1`, SqliteSaver replacing InMemorySaver, `checkpointer.setup()` call before compile.

**Avoids:** C1 (interrupt swallowed — review node must have no try/except), C5 (non-idempotent ops before interrupt — review node is pure), C6 (loop guard), M1 (missing checkpointer), M6 (use Command(resume=...) not update_state()+invoke(None)), M7 (SqliteSaver.setup() not called).

**Research flag:** HIGH RISK. Test the full 3-revision cycle (interrupt → resume → interrupt → resume → force-exit) in a Python script before proceeding to Phase 6.

---

### Phase 6: Storage Layer

**Rationale:** Pure IO with no graph dependencies beyond reading state.polished. Finalize schema before writing save node — no mid-development schema changes.

**Delivers:** Working save node writing markdown file and inserting a row into history.db. Two-DB separation enforced from first line of storage code.

**Implements:** history.db schema (id, date, type, content TEXT, created_at), storage/sqlite.py CRUD, storage/markdown.py export.

**Avoids:** C7 (shared SQLite file — two separate files, graph_state.db never touched by app code), m5 (use TEXT not VARCHAR for content column).

**Research flag:** Standard patterns.

---

### Phase 7: Streamlit UI

**Rationale:** UI is the thinnest layer and depends on all previous phases being correct. Building it last means UI bugs are UI bugs, not disguised graph bugs.

**Delivers:** Full Streamlit app: input form, review panel (approve/revise/edit-inline), export panel (download + date-sorted history). Phase state machine in st.session_state. Single-column layout.

**Implements:** @st.cache_resource for graph object, st.session_state for thread_id and phase management, two-invoke pattern (initial generation → resume after human decision), generating flag for double-click prevention.

**Avoids:** C2 (thread_id in session_state from first line), M2 (@st.cache_resource for graph), M8 (sync-only — never import ainvoke/astream), m6 (generating flag for double-execution).

**Research flag:** MEDIUM RISK. Streamlit + LangGraph integration has no official combined documentation. Test the full rerun cycle (button click → Streamlit rerun → st.session_state preserved → graph resumes correctly) explicitly before declaring Phase 7 done.

---

### Phase Ordering Rationale

- Skeleton before LLM: graph topology bugs are free to fix on stubs; expensive after logic is added.
- Core LLM before routing: TemplateRouterAgent depends on structured_info quality; extract must be validated first.
- Git tool before HITL: optional enrichment should be independently verified before interrupt complexity is introduced.
- HITL before Streamlit: interrupt/resume correctness must be proven in Python before Streamlit rerun semantics are layered on.
- Storage before UI: save node needs real polished output from a completed HITL cycle.
- UI last: all logic working before the thinnest layer is added.

---

### Research Flags

**Phases needing extra attention during implementation:**

- **Phase 2 (Core LLM nodes):** Prompt engineering quality is the highest-value and most uncertain deliverable. Treat extraction prompt quality as a first-class milestone. Budget 2h iteration time.
- **Phase 5 (HITL):** Highest failure density — three critical pitfalls (C1, C2/M2, C5) converge here. Do not proceed to Phase 7 until the full interrupt/resume cycle passes a standalone Python test.
- **Phase 7 (Streamlit):** No official combined Streamlit+LangGraph integration guide. Test session_state + graph rerun semantics explicitly.

**Phases with well-documented standard patterns:**

- **Phase 1 (Skeleton):** TypedDict state, StateGraph wiring, conditional edges — all canonical LangGraph patterns.
- **Phase 3 (Sub-graph):** Compiled sub-graph as callable node is well-documented in LangGraph How-Tos.
- **Phase 4 (Git tool):** GitPython API is stable; exception-safe wrapper is a standard pattern.
- **Phase 6 (Storage):** Plain SQLite with stdlib sqlite3; no novel patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core package versions verified from PyPI wheel contents and METADATA. GitPython API is MEDIUM — confirmed on PyPI, API patterns from training knowledge. |
| Features | HIGH | Template sections and boss-friendly writing principles are well-established Chinese workplace conventions, cross-validated against PROJECT.md. Timing threshold (< 10s) is subjective. |
| Architecture | HIGH | StateGraph, interrupt_before, sub-graph, SqliteSaver — canonical documented APIs. Streamlit integration is MEDIUM due to version-dependent sync/async behavior. |
| Pitfalls | HIGH | Critical pitfalls sourced from official LangGraph error documentation fetched during research. Streamlit pitfalls are MEDIUM confidence from GitHub issue summaries. |

**Overall confidence: HIGH**

Core stack is wheel-inspected. Architecture patterns are canonical documented APIs. Pitfalls are from official LangGraph error docs. The only MEDIUM areas have clear prevention strategies that do not require further research.

### Gaps to Address

- **Streamlit + LangGraph session_state integration:** No official combined documentation. The patterns are synthesized from multiple sources. Validate the full two-invoke cycle (generate → pause → Streamlit rerun → resume on button click) as the first task in Phase 7, not the last.
- **Interrupt pattern consistency:** STACK.md describes in-node `interrupt()` + `Command(resume=...)`; ARCHITECTURE.md describes compile-time `interrupt_before`. Decision: use `interrupt_before=["review"]` at compile time for the "always pause" guarantee, and `Command(resume=...)` for resume. Do not mix the two styles.
- **Boss-friendly prompt quality:** Cannot be assessed from research. Validate with 5-10 real Chinese daily report inputs at the start of Phase 2 before building downstream nodes.

---

## Sources

### Primary (HIGH confidence)

- LangGraph 1.1.9 wheel inspection: `langgraph/types.py` (interrupt, Command), `langgraph/graph/__init__.py` (StateGraph, START, END), `langgraph/graph/state.py`, `langgraph/graph/message.py` (add_messages)
- langgraph-checkpoint-4.0.2 wheel: `checkpoint/memory/__init__.py` (InMemorySaver)
- langgraph-checkpoint-sqlite-3.0.3 wheel: `checkpoint/sqlite/__init__.py` (SqliteSaver, from_conn_string, setup())
- langchain-anthropic-1.4.1 wheel: `chat_models.py` (ChatAnthropic, with_structured_output), `data/_profiles.py` (claude-sonnet-4-5 confirmed with tool_calling + structured_output)
- PyPI index queries: all pinned versions confirmed
- LangGraph official error documentation (fetched 2026-04-22): GRAPH_RECURSION_LIMIT, INVALID_GRAPH_NODE_RETURN_VALUE, MISSING_CHECKPOINTER error codes
- LangGraph official interrupt, persistence, and sub-graph how-to documentation (fetched 2026-04-22)

### Secondary (MEDIUM confidence)

- LangGraph + Streamlit integration: GitHub issues #101, #118, #2063 (issue index summaries)
- Streamlit sync/async behavior in 1.x: training knowledge, version-dependent
- GitPython 3.1.47 API patterns: training knowledge (API stable, not source-inspected)
- Chinese workplace reporting conventions: training knowledge through Aug 2025
- AI writing tool HITL UX patterns (Notion AI, GitHub Copilot, Jasper): training knowledge

### Tertiary (LOW confidence)

- Timing expectation (< 10 seconds for generation): subjective UX threshold, no empirical source

---

*Research completed: 2026-04-22*
*Ready for roadmap: yes*
