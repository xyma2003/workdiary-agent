# Domain Pitfalls: LangGraph AI Agent (智能日报 Agent)

**Domain:** LangGraph-based multi-node AI Agent with human-in-the-loop, Streamlit UI, SQLite storage
**Researched:** 2026-04-22
**Sources:** LangGraph official error docs (docs.langchain.com/oss/python/langgraph), GitHub issues analysis, LangGraph interrupt/persistence/subgraph docs
**Confidence:** HIGH for LangGraph-specific items (official docs verified); MEDIUM for Streamlit integration patterns

---

## Critical Pitfalls

Mistakes that cause silent misbehavior, complete rewrites, or days of debugging.

---

### Pitfall C1: Wrapping `interrupt()` in a try/except Block

**What goes wrong:** The `interrupt()` function works by raising a special internal exception. If you wrap the node body in a bare `try/except Exception`, you catch and swallow that exception, and the graph never pauses — it either crashes with a confusing error or silently skips the human review step.

**Why it happens:** Defensive coding instinct. Developer adds a broad error handler to "make the node safe," not knowing `interrupt()` uses exceptions for control flow.

**Consequences:** The human-in-the-loop step disappears. The graph runs straight through "review" without pausing. User never gets to approve or revise. You spend time debugging why the interrupt "isn't working" when it was caught silently.

**Prevention:**
- Never put `interrupt()` inside a `try/except` block.
- If you need error handling in the same node, catch only specific exceptions, never bare `except` or `except Exception`.
- Place `interrupt()` at the top level of the node function body.

**Detection:** Symptom is that `graph.get_state(config).next` is empty right after `graph.invoke()` returns, when you expected it to be paused.

**Phase:** Human-in-the-loop implementation (Layer 4 in build order).

---

### Pitfall C2: Using a Different `thread_id` on Resume

**What goes wrong:** LangGraph's checkpointer uses `thread_id` as the primary key to locate the saved state snapshot. If the resume invocation uses a different `thread_id` (or omits it entirely), the graph starts fresh instead of resuming — and you get a new session, not a continuation.

**Why it happens:** Streamlit reruns the entire script top-to-bottom on every widget interaction. If `thread_id` is generated inside the script body (e.g., `thread_id = str(uuid.uuid4())`) without being stored in `st.session_state`, a new UUID is generated on every Streamlit rerun, breaking the resume chain.

**Consequences:** Every "Submit" click starts a brand-new graph execution. The saved checkpoint from the initial generation is abandoned. Appears as: user clicks Approve, nothing happens or a new draft is generated from scratch.

**Prevention:**
- Always store `thread_id` in `st.session_state` immediately on creation.
- Use exactly this pattern:
  ```python
  if "thread_id" not in st.session_state:
      st.session_state.thread_id = f"report-{date.today().isoformat()}-{uuid.uuid4().hex[:8]}"
  config = {"configurable": {"thread_id": st.session_state.thread_id}}
  ```
- Never regenerate `thread_id` outside of explicit "start new session" logic.

**Detection:** `graph.get_state(config).values` returns empty or default state when you expect a populated state from a previous run.

**Phase:** Streamlit UI wiring (Layer 6 in build order).

---

### Pitfall C3: Node Returns Non-Dict Value (INVALID_GRAPH_NODE_RETURN_VALUE)

**What goes wrong:** LangGraph raises `GraphBuildError` or a runtime error with code `INVALID_GRAPH_NODE_RETURN_VALUE` if a node returns anything other than a `dict`. This includes returning `None` (implicit return), returning a string, or returning a Pydantic model directly.

**Why it happens:** Forgetting that LangGraph expects a dict that maps to state fields. Returning the LLM output object directly instead of wrapping it. Forgetting a `return` statement on a code path (Python returns `None`).

**Consequences:** Graph crashes at runtime, often on a path not covered by basic testing. Easy to miss if you only test the happy path and one of the conditional branches has no return statement.

**Prevention:**
- Every node function must return a `dict` on every code path.
- Check all `if/else` branches — including the else clause you might not have written.
- Lint rule: type-annotate every node as `-> dict` and run mypy.
  ```python
  def extract_node(state: AgentState) -> dict:  # enforce the return type
      ...
      return {"structured_info": result}
  ```

**Detection:** `INVALID_GRAPH_NODE_RETURN_VALUE` error in stack trace. Or `TypeError: 'NoneType' is not subscriptable` when the next node tries to read state.

**Phase:** Initial graph skeleton (Layer 0 in build order). Catch this before adding LLM logic.

---

### Pitfall C4: State Mutation Instead of Return

**What goes wrong:** LangGraph state is passed to nodes as a read-only snapshot. Mutating `state["field"] = value` inside a node does NOT update the actual graph state — the mutation is silently discarded. Only values returned in the node's dict are merged into state.

**Why it happens:** The state dict looks like a regular Python dict, so mutation feels natural. Developers from imperative backgrounds instinctively mutate instead of returning.

**Consequences:** Node "runs" but state never changes. Next node sees the old value. LLM output is lost. Appears as: draft is generated but `draft` field is still `None` in subsequent nodes.

**Prevention:**
- Treat state as immutable inside nodes. Read from it freely, but only write via the return dict.
- Code review rule: no assignments to `state[...]` inside any node function.
  ```python
  # WRONG
  def draft_node(state: AgentState) -> dict:
      state["draft"] = llm.invoke(...)   # silently discarded
      return {}

  # CORRECT
  def draft_node(state: AgentState) -> dict:
      result = llm.invoke(...)
      return {"draft": result.content}
  ```

**Detection:** State field is still `None` after the node that should have set it. `graph.get_state(config).values["draft"]` shows no change after `draft` node ran.

**Phase:** Initial graph skeleton (Layer 0). This is a foundational pattern, establish it on day 1.

---

### Pitfall C5: Node Restart Side Effects with `interrupt()` (Non-Idempotent Operations Before Interrupt)

**What goes wrong:** When a graph resumes after an `interrupt()`, the runtime restarts the entire node from the beginning — not from the line where `interrupt()` was called. Any code before the `interrupt()` call re-executes. If that code makes an LLM call, writes to a file, or inserts a database row, it happens twice.

**Why it happens:** Developers think the resume picks up from after the `interrupt()` line, like a coroutine. It does not. The node always restarts from the top.

**Consequences:** Duplicate LLM API calls (wasted cost). Duplicate database rows. Duplicate file writes. Hard to debug because the second execution produces the same output, so it looks like one execution.

**Prevention:**
- Place `interrupt()` at the beginning of the review node, before any processing.
- Do not make LLM calls or IO writes in the same node that calls `interrupt()`.
- Keep the `review` node as a pure router: it only calls `interrupt()` to receive user input, then returns the decision. No LLM calls, no file writes.
  ```python
  def human_review_node(state: AgentState) -> dict:
      # Only reads state + pauses. No LLM call here.
      decision = interrupt({
          "polished": state["polished"],
          "prompt": "Approve, revise, or reject?"
      })
      return {"human_decision": decision}
  ```

**Detection:** Duplicate rows in history DB. Duplicate API billing entries. Double LLM latency on resume.

**Phase:** Human-in-the-loop implementation (Layer 4).

---

### Pitfall C6: No Loop Guard on the Revise Cycle (GRAPH_RECURSION_LIMIT)

**What goes wrong:** The revise → review → revise loop has no exit condition other than user approval. If the user never approves (or if the conditional edge routing logic has a bug), the graph loops until it hits LangGraph's recursion limit (default: 25 steps), then crashes with `GRAPH_RECURSION_LIMIT`.

**Why it happens:** Developer implements the happy path (approve → save) but forgets the force-exit path after N revisions.

**Consequences:** Runaway API costs. Graph crashes mid-run with an opaque recursion error. User experience breaks.

**Prevention:**
- Always implement a `revision_count` guard in the conditional edge after review:
  ```python
  def route_after_review(state: AgentState) -> str:
      MAX_REVISIONS = 3
      if state["human_decision"] == "approve":
          return "save"
      elif state.get("revision_count", 0) >= MAX_REVISIONS:
          return "save"   # Force exit — prevents infinite loop
      else:
          return "revise"
  ```
- The `revise` node must increment `revision_count` on every call.
- Ensure `revision_count` is initialized to `0` in the initial state passed to `graph.invoke()`. If it is missing, `state.get("revision_count", 0)` is the safe fallback.

**Detection:** `GraphRecursionError` with `GRAPH_RECURSION_LIMIT` in the error code. Or: graph runs longer than expected, API costs spike.

**Phase:** Human-in-the-loop + conditional edges (Layer 4).

---

### Pitfall C7: Mixing LangGraph Checkpoint DB with Application History DB

**What goes wrong:** Using the same SQLite file (or even the same connection) for both LangGraph's `SqliteSaver` checkpoint tables and the application's own history records. LangGraph writes serialized binary blobs into its tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_migrations`). These table names may collide, and the schema is LangGraph-internal, not designed for application queries.

**Why it happens:** "It's all SQLite, why use two files?" reasoning.

**Consequences:** Schema collision if you create tables with the same names as LangGraph's internal tables. History queries become fragile or impossible. Checkpoint data is mixed with human-readable report data. Migrations become entangled.

**Prevention:**
- Two separate SQLite files, always:
  - `graph_state.db` — owned by `SqliteSaver`, never touched directly by app code
  - `history.db` — owned by the app, contains `reports` table with `id`, `date`, `type`, `content`, `created_at`
- Never query `graph_state.db` from app code.

**Detection:** `OperationalError: table already exists` on first run. Or history queries return unexpected binary data.

**Phase:** Storage implementation (Layer 5).

---

## Moderate Pitfalls

Mistakes that cost 2–8 hours to debug but do not require architectural rewrites.

---

### Pitfall M1: Missing Checkpointer on `compile()` When Using `interrupt()`

**What goes wrong:** Calling `interrupt()` inside a node requires a checkpointer to be configured on `graph.compile(checkpointer=...)`. Without it, LangGraph raises `MissingCheckpointerError` (error code: `MISSING_CHECKPOINTER`) at runtime.

**Prevention:**
- During development: `from langgraph.checkpoint.memory import InMemorySaver; graph = builder.compile(checkpointer=InMemorySaver())`
- For persistence: `from langgraph.checkpoint.sqlite import SqliteSaver; graph = builder.compile(checkpointer=checkpointer)`
- Never call `graph.compile()` without `checkpointer=...` if any node uses `interrupt()`.

**Detection:** `MissingCheckpointerError` on first invocation. The error message is clear.

**Phase:** Layer 0 skeleton — add the checkpointer from day 1 so you never develop without it.

---

### Pitfall M2: Streamlit Re-Run Creates New Graph Instance

**What goes wrong:** In Streamlit, every widget interaction (button click, text input) reruns the entire script. If the graph is instantiated at the module level or inside the script body without `st.session_state` caching, a new graph object is created on every rerun. The new graph object has no memory of the previous checkpoint even if the checkpoint is in SQLite — because the `graph` object itself is recreated.

**Why it happens:** Developers test LangGraph in a Python script or notebook where graph creation happens once. In Streamlit, every rerun is a new execution context.

**Prevention:**
```python
@st.cache_resource
def build_graph():
    # Called once per Streamlit server start
    checkpointer = SqliteSaver.from_conn_string("graph_state.db")
    return workflow.compile(checkpointer=checkpointer)

graph = build_graph()  # cached, not recreated on rerun
```
Use `@st.cache_resource` for the graph object. Use `st.session_state` for per-session data (thread_id, current phase, pending interrupt).

**Detection:** Every button click starts a fresh generation instead of resuming. `st.session_state` shows correct data but graph behavior ignores it.

**Phase:** Streamlit UI wiring (Layer 6).

---

### Pitfall M3: TemplateRouterAgent Sub-Graph State Mismatch

**What goes wrong:** The sub-graph (`TemplateRouterAgent`) has its own `RouterState` TypedDict. When calling `template_router_graph.invoke(input_dict)`, the `input_dict` must contain only keys that exist in `RouterState`. Passing extra keys from `AgentState` causes a validation error. Not passing required keys causes a `KeyError` inside the sub-graph.

**Prevention:**
- The parent node that calls the sub-graph is responsible for extracting only the fields the sub-graph needs:
  ```python
  def route_template_node(state: AgentState) -> dict:
      result = template_router_graph.invoke({
          "structured_info": state["structured_info"]  # only what RouterState needs
      })
      return {
          "template_type": result["template_type"],
          "selected_template": result["selected_template"]
      }
  ```
- The sub-graph returns a full `RouterState` dict; extract only the fields you need back into `AgentState`.

**Detection:** `KeyError` in the sub-graph node. Or `ValidationError` on input to `template_router_graph.invoke()`.

**Phase:** TemplateRouterAgent sub-graph (Layer 2).

---

### Pitfall M4: Conditional Edge Routing Function Returns a Value Not in the Edge Map

**What goes wrong:** `add_conditional_edges` requires the routing function to return a string that matches a key in the path map dict. If the routing function returns an unexpected value (e.g., `"rejected"` when the map only has `"approve"`, `"revise"`, `"save"`), LangGraph raises a runtime error or silently routes to END.

**Prevention:**
- Define routing function output as a `Literal` type and match it to the edge map exactly:
  ```python
  from typing import Literal

  def route_after_review(state: AgentState) -> Literal["save", "revise"]:
      ...
  
  workflow.add_conditional_edges(
      "review",
      route_after_review,
      {"save": "save", "revise": "revise"}  # keys must match all possible return values
  )
  ```
- Test each conditional edge path explicitly before testing the full graph.

**Detection:** Graph terminates unexpectedly or `InvalidUpdateError`. The error message shows the unrecognized edge key.

**Phase:** Graph skeleton (Layer 0) — wire and test edges before adding LLM logic.

---

### Pitfall M5: `with_structured_output` Fails on Complex Pydantic Schemas

**What goes wrong:** `llm.with_structured_output(MyModel)` works reliably for schemas with flat fields and clear descriptions. It becomes unreliable with: deeply nested models, `Union` types, overly long `description` strings, or schemas with more than ~10 fields. Claude may return a partial JSON, add markdown code fences, or populate fields with incorrect types.

**Why it happens:** The LLM maps the schema to a tool call definition. Complex schemas produce large tool definitions that approach context limits or confuse the model.

**Prevention:**
- Keep extraction schemas flat. For `DiaryExtraction`, use at most 5–6 top-level string fields.
- Avoid `Optional[List[dict]]` — prefer `Optional[str]` where possible (the LLM can serialize lists as text if needed).
- Use short, action-oriented `Field(description=...)` strings. Under 20 words each.
- Test each structured output node in isolation with real sample inputs before wiring into the graph.
- Add a fallback: if the structured call raises `ValidationError`, retry once with a simplified prompt.

**Detection:** `ValidationError` from Pydantic during node execution. Or `AttributeError: 'NoneType' object has no attribute 'type'` if the model returns a partial object.

**Phase:** Core LLM nodes (Layer 1) — test extraction quality before building downstream nodes that depend on the extracted structure.

---

### Pitfall M6: `graph.update_state()` Requires `as_node` Parameter in Some LangGraph Versions

**What goes wrong:** When injecting human input via `graph.update_state(config, {"human_decision": "approve"})` before resuming, some LangGraph versions require the `as_node` parameter to specify which node is "responsible" for the update. Without it, the update may be applied but the graph may not route correctly on resume.

**Prevention:**
- Prefer using `Command(resume=...)` for resuming after `interrupt()`:
  ```python
  graph.invoke(Command(resume="approve"), config)
  ```
- If using `graph.update_state()` + `graph.invoke(None, config)` pattern, add `as_node`:
  ```python
  graph.update_state(config, {"human_decision": "approve"}, as_node="review")
  graph.invoke(None, config)
  ```
- The `Command(resume=...)` pattern is the LangGraph 1.x canonical approach and avoids this ambiguity entirely.

**Detection:** Graph resumes but routes to the wrong branch, or `get_state(config).next` still shows the paused node after `invoke(None, config)`.

**Phase:** Human-in-the-loop (Layer 4). Verify the resume pattern in isolation before adding Streamlit.

---

### Pitfall M7: Forgetting to Call `.setup()` on SqliteSaver Before First Use

**What goes wrong:** `SqliteSaver` requires calling `.setup()` once to create its internal checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_migrations`). If you skip this, the first `graph.invoke()` call fails with an `OperationalError: no such table: checkpoints`.

**Prevention:**
```python
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("graph_state.db") as checkpointer:
    checkpointer.setup()   # creates tables if they don't exist; idempotent
    graph = workflow.compile(checkpointer=checkpointer)
    graph.invoke(...)
```
The `from_conn_string()` context manager is the documented pattern. Call `setup()` before the first `compile()`.

**Detection:** `OperationalError: no such table: checkpoints` on the first invocation.

**Phase:** Storage layer setup (Layer 5), but test this during Layer 4 when you first switch from `InMemorySaver` to `SqliteSaver`.

---

### Pitfall M8: Streamlit `asyncio` Event Loop Conflict with `graph.ainvoke()`

**What goes wrong:** Streamlit runs its own event loop internally. Calling `asyncio.run(graph.ainvoke(...))` or `await graph.ainvoke(...)` directly in Streamlit's main thread raises `RuntimeError: This event loop is already running`.

**Prevention:**
- For a single-developer, one-week project: use synchronous `graph.invoke()` and `graph.stream()` exclusively. Avoid all async graph calls.
- If async is needed later: use `nest_asyncio.apply()` at startup, or run async calls in a separate thread via `concurrent.futures.ThreadPoolExecutor`.
- The ARCHITECTURE.md already recommends sync-only. Follow that recommendation.

**Detection:** `RuntimeError: This event loop is already running` when a Streamlit button triggers a graph call.

**Phase:** Streamlit UI (Layer 6). Non-issue if you follow the sync-only recommendation from the start.

---

## Minor Pitfalls

Mistakes that cause 30–90 minutes of confusion but are easy to fix once identified.

---

### Pitfall m1: `MemorySaver` vs `InMemorySaver` Name Confusion

LangGraph 1.x renamed `MemorySaver` to `InMemorySaver`. `MemorySaver` still works as an alias but will generate deprecation warnings in future versions. Use `from langgraph.checkpoint.memory import InMemorySaver` for new code.

---

### Pitfall m2: `set_entry_point()` vs `add_edge(START, ...)`

Both work in LangGraph 1.x but `add_edge(START, "node_name")` is the idiomatic 1.x style. `set_entry_point()` is a legacy wrapper. Use `START` and `END` sentinel values consistently.

---

### Pitfall m3: Forgetting `revision_count` in Initial State

If `revision_count` is not included in the initial state dict passed to `graph.invoke()`, it will be `None` in the first node that tries to read it. The loop guard `state.get("revision_count", 0) >= 3` protects against this, but `state["revision_count"] >= 3` (without `.get()`) will raise `TypeError: '>=' not supported between instances of 'NoneType' and 'int'`.

**Prevention:** Always initialize `revision_count: 0` in the initial state. Or use `.get()` everywhere with a default.

---

### Pitfall m4: GitPython `Repo()` Raises `InvalidGitRepositoryError` on Non-Git Paths

If the user provides a path that is not a git repository (or an invalid path), `git.Repo(path)` raises `git.exc.InvalidGitRepositoryError`. Since the git tool is optional, this exception must be caught and handled gracefully — return an informative string, do not crash the graph.

**Prevention:** The `enrich` node should always catch exceptions from the git tool and set `git_log` to `None` or an error string. Never let a tool exception propagate to the graph runner.

---

### Pitfall m5: SQLite `TEXT` Columns Silently Truncate Nothing — But Schema Choice Affects Queries

For the history DB, storing the full markdown report as a `TEXT` column is correct (SQLite `TEXT` is unlimited length). The pitfall is using `VARCHAR(255)` or similar, which some ORMs add automatically. Use plain `TEXT` for the `content` field.

---

### Pitfall m6: Streamlit Double-Execution on Button Click

Streamlit reruns the script when a button is clicked AND when the widget state changes. Using `st.button("Generate")` in combination with conditional logic that triggers graph execution can sometimes execute the graph twice in quick succession. 

**Prevention:** Use `st.session_state` flags to track whether execution has started:
```python
if st.button("Generate") and not st.session_state.get("generating"):
    st.session_state.generating = True
    # run graph
    st.session_state.generating = False
```

---

### Pitfall m7: `polished` vs `draft` Field Overwrite in Revise Loop

The `revise` node should update `polished` (the field that represents the current best version) and NOT touch `draft` (the first pass). If the revise node writes back to `draft`, the polish node comparison logic breaks and you lose the revision history context.

---

## Scope Creep Risks for a One-Week Timeline

The project's Out of Scope section is already well-defined. The following are the most likely places where scope creep will occur during development:

| Feature That Will Tempt You | Why It Looks Small | Why It Isn't | What to Do |
|-----------------------------|--------------------|--------------|------------|
| Streaming token output (word-by-word typing effect in UI) | `st.write_stream` looks easy | Requires generator plumbing through all LLM nodes, changes graph.stream() mode, adds ~1 day | Do not implement. Batch output is fine for a portfolio demo. |
| History search / filter by date or type | One SQL query, right? | Requires search UI component, pagination, query input parsing, test data | Display flat list only. No search. |
| User-editable prompt templates | "Just a text area" | Requires template validation, storage, versioning, and testing that templates don't break structured extraction | Use 3 hardcoded templates. |
| Custom retry logic per node | Feels like robustness | Adds state fields, complicates graph topology, hard to test | Use a single top-level try/except + `recursion_limit` guard only. |
| Streaming git log for large repos | "What if git log is slow?" | Not a real problem for daily commits. | Hard limit: only last 24h commits, no pagination. |
| Fancy Streamlit layout (columns, tabs, sidebar) | CSS feels fast | Streamlit layout bugs are a time sink. | Single-column, top-to-bottom layout. Add layout polish only if core features are done by day 5. |

**Hard stop rule for the one-week timeline:** If a feature is not in the Active requirements list in PROJECT.md, it is out of scope. Do not add it to Active without explicitly removing something else or confirming it fits in remaining time.

---

## Phase-Specific Warnings

| Phase / Layer | Topic | Likely Pitfall | Mitigation |
|---------------|-------|---------------|------------|
| Layer 0: Skeleton | Graph topology | Wrong edge target name (typo in node name) causes silent routing failures | Use constants for node names: `EXTRACT = "extract"` etc. |
| Layer 0: Skeleton | Node return | Node returns `None` instead of `{}` on stub implementation | Stub every node as `return {}` from day 1 |
| Layer 1: LLM nodes | Structured output | Pydantic schema too complex for reliable extraction | Start with the flattest possible schema; add fields only as needed |
| Layer 1: LLM nodes | Prompt iteration | "I'll fix the prompt later" → later never comes | Spend 2h on extraction prompt quality before moving on — it is the foundation of everything |
| Layer 2: Sub-graph | State handoff | Passing full AgentState into RouterState sub-graph | Write explicit field mapping in the wrapper node |
| Layer 3: Git tool | Tool errors | `InvalidGitRepositoryError` propagates and crashes the graph | Always catch exceptions in the `enrich` node; make git context truly optional |
| Layer 4: HITL | try/except | Interrupt exception caught by broad error handler | Remove all broad try/except from `human_review_node` |
| Layer 4: HITL | Resume pattern | `update_state` + `invoke(None)` vs `invoke(Command(resume=...))` — mixing the two styles | Pick one pattern, use it consistently. Prefer `Command(resume=...)`. |
| Layer 5: Storage | DB separation | Using same SQLite file for checkpoints and history | Create two files at the start; enforce in code comments |
| Layer 5: Storage | Schema migration | Adding columns to history table mid-development | Define final schema before writing the save node; don't iterate the schema |
| Layer 6: Streamlit | Session state | `thread_id` regenerated on rerun | Store in `st.session_state` on the very first line of the UI |
| Layer 6: Streamlit | Async conflict | `graph.ainvoke()` used by mistake | Only import `graph.invoke` and `graph.stream`; do not import async variants |
| All layers | Scope creep | Adding "small" features during implementation | Check PROJECT.md Active list before starting any unplanned work |

---

## Warning Signs: How to Detect Problems Early

| Warning Sign | What It Indicates | Action |
|--------------|------------------|--------|
| `graph.get_state(config).next` is empty right after initial invoke | Interrupt not firing — likely caught by try/except or checkpointer missing | Check: (1) checkpointer set? (2) no bare try/except around interrupt()? |
| Same draft generated twice on resume | Node restart side effects (LLM call before interrupt) | Move LLM call to a separate node before the review node |
| `revision_count` stays at 0 after multiple revisions | Revise node not returning `revision_count` in its dict | Ensure `return {"polished": ..., "revision_count": state["revision_count"] + 1}` |
| Streamlit generates a new report every button click | `thread_id` not persisted in session_state | Check `if "thread_id" not in st.session_state: ...` guard |
| `KeyError` inside sub-graph | State field expected by sub-graph not passed in | Check input dict to `template_router_graph.invoke()` |
| `ValidationError` from Pydantic on structured output | LLM returned unexpected JSON shape | Simplify schema; add retry with error message appended to prompt |
| `OperationalError: no such table: checkpoints` | `SqliteSaver.setup()` not called | Call `checkpointer.setup()` before compiling the graph |
| API cost higher than expected | Revise loop running more times than expected | Add logging of `revision_count` at the start of each revise node; verify loop guard fires |

---

## Sources

- LangGraph official error documentation: `docs.langchain.com/oss/python/langgraph/common-errors` — HIGH confidence (fetched 2026-04-22)
- LangGraph interrupt documentation: `docs.langchain.com/oss/python/langgraph/interrupts` — HIGH confidence (fetched 2026-04-22)
- LangGraph persistence documentation: `docs.langchain.com/oss/python/langgraph/add-memory` — HIGH confidence (fetched 2026-04-22)
- LangGraph subgraph documentation: `docs.langchain.com/oss/python/langgraph/use-subgraphs` — HIGH confidence (fetched 2026-04-22)
- LangGraph error codes (GRAPH_RECURSION_LIMIT, INVALID_GRAPH_NODE_RETURN_VALUE, MISSING_CHECKPOINTER, INVALID_CONCURRENT_GRAPH_UPDATE, MULTIPLE_SUBGRAPHS): official error pages — HIGH confidence (fetched 2026-04-22)
- GitHub issues: LangGraph + Streamlit incompatibility (#101, #118, #2063) — MEDIUM confidence (summary extracted from issue index)
- GitHub issues: interrupt double-call, subgraph state loss, checkpoint deserialization bugs — MEDIUM confidence (summary extracted from issue index)
- Anthropic SDK structured output issues (GitHub #1185, #1204, #1094) — MEDIUM confidence (issue index summary)
- STACK.md and ARCHITECTURE.md from this project's prior research — HIGH confidence (verified against official sources)
