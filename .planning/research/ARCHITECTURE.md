# Architecture Patterns: LangGraph Multi-Node Agent with Human-in-the-Loop

**Domain:** LangGraph-based AI Agent (智能日报 Agent)
**Researched:** 2026-04-22
**Confidence:** HIGH (LangGraph 0.2.x, verified against training data through Aug 2025; WebFetch unavailable)

---

## Recommended Architecture

```
Streamlit UI
     │
     │  graph.stream() / graph.invoke()
     ▼
┌─────────────────────────────────────────────┐
│  StateGraph (AgentState: TypedDict)          │
│                                             │
│  extract → enrich → route_template          │
│               │           │ (sub-graph call)│
│               │     TemplateRouterAgent      │
│               │           │                 │
│               └──► draft → polish           │
│                              │              │
│                           review  ◄──────── │
│                         (interrupt)         │
│                              │              │
│                    ┌─── approve             │
│                    │         │              │
│                 revise    save              │
│              (loop ≤3)       │              │
└─────────────────────────────────────────────┘
                               │
                    SQLite (history)
                    Markdown file (export)
```

---

## 1. State Schema: TypedDict vs Pydantic

### Recommendation: TypedDict with Annotated reducers

**Why TypedDict over Pydantic for this project:**

LangGraph's `StateGraph` natively accepts `TypedDict` subclasses and uses `Annotated` type hints to declare reducers. This is the canonical pattern in all official LangGraph examples and docs.

Pydantic `BaseModel` is also supported as of LangGraph 0.2.x, but adds overhead and validator complexity that is unnecessary for a single-developer, week-scoped project.

**Concrete State schema for this project:**

```python
from typing import TypedDict, Annotated, Optional, Literal
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Input
    raw_input: str                          # User's spoken work description
    git_log: Optional[str]                  # Output of git log tool (nullable)
    repo_path: Optional[str]               # Path to git repo (nullable)

    # Extracted structure
    structured_info: Optional[dict]        # tasks, output, problems, progress

    # Routing decision
    template_type: Optional[Literal["tech", "business", "mixed"]]
    selected_template: Optional[str]       # Template string with placeholders

    # Draft pipeline
    draft: Optional[str]                   # Raw draft from draft node
    polished: Optional[str]                # Boss-perspective polished version

    # Human-in-the-loop
    human_feedback: Optional[str]          # Human's review comment
    human_decision: Optional[Literal["approve", "revise", "reject"]]
    revision_count: int                    # Loop guard counter

    # Output
    final_report: Optional[str]            # Approved final text
    export_path: Optional[str]             # Written markdown path
    history_id: Optional[int]             # SQLite row ID
```

**Key rules:**
- Fields that accumulate (e.g., message lists) use `Annotated[list, add_messages]` reducer.
- Fields that replace use plain types (default reducer is overwrite).
- `revision_count: int` must default to `0` — set this in the graph initializer via `graph.compile()` state defaults or ensure nodes always carry it forward.

**Confidence: HIGH** — TypedDict + Annotated is the documented canonical pattern.

---

## 2. Human-in-the-Loop: interrupt_before

### How it works

LangGraph's human-in-the-loop relies on two mechanisms working together:

1. **A checkpointer** that persists graph state between invocations.
2. **`interrupt_before` or `interrupt_after`** on `graph.compile()` that tells the graph to pause before/after a specified node.

```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("state.db")

graph = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["review"]   # pause BEFORE the review node executes
)
```

### Execution flow

```
First invocation:
  graph.invoke(initial_state, config={"configurable": {"thread_id": "session-1"}})
  → runs: extract → enrich → route_template → draft → polish
  → PAUSES before "review" node
  → returns current state snapshot to caller

UI presents polished draft to user.
User clicks "Approve" or types feedback.

Second invocation (resume):
  graph.invoke(
      {"human_feedback": "...", "human_decision": "revise"},
      config={"configurable": {"thread_id": "session-1"}}
  )
  → resumes from "review" node with updated state
  → runs: review → (conditional) → revise or save
```

### Why `interrupt_before` not `interrupt_after` here

Use `interrupt_before=["review"]` so the review node can read `human_feedback` and `human_decision` that were injected by the second invocation. If you used `interrupt_after=["polish"]`, the review node would need to be its own separate pause point anyway — same result, cleaner with `interrupt_before=["review"]`.

### The `review` node itself

The review node should be a pure router — it reads `human_decision` from state and sets up the outgoing edge signal. The actual human input is injected via state update before resuming.

```python
def review_node(state: AgentState) -> dict:
    # human_decision was set by the UI before graph.invoke() was called again
    decision = state.get("human_decision", "revise")
    # No LLM call here — this is a pure routing checkpoint
    return {"human_decision": decision}
```

### Conditional edge after review

```python
def route_after_review(state: AgentState) -> str:
    if state["human_decision"] == "approve":
        return "save"
    elif state["revision_count"] >= 3:
        return "save"   # Force exit after 3 revisions — avoid infinite loop
    else:
        return "revise"

workflow.add_conditional_edges(
    "review",
    route_after_review,
    {"save": "save", "revise": "revise"}
)
```

### `thread_id` is mandatory for interrupt to work

Every `graph.invoke()` call that participates in a conversation must pass the same `thread_id` in `config`. The checkpointer uses this to store/restore state.

```python
config = {"configurable": {"thread_id": "daily-report-2026-04-22"}}
```

Use date + session ID as thread_id. For single-user Streamlit, store in `st.session_state`.

**Confidence: HIGH** — This is the canonical interrupt/resume pattern from LangGraph docs.

---

## 3. TemplateRouterAgent as Sub-Agent

### Pattern: Sub-graph (recommended over nested agent)

For this project, "TemplateRouterAgent" should be implemented as a **compiled sub-graph** that is called from the `route_template` node. This is simpler than a full multi-agent handoff and is the right tool for a classification+selection task.

```python
# template_router.py

class RouterState(TypedDict):
    structured_info: dict
    template_type: Optional[Literal["tech", "business", "mixed"]]
    selected_template: Optional[str]

def classify_node(state: RouterState) -> dict:
    # LLM call to classify content type
    result = llm.invoke(classify_prompt.format(info=state["structured_info"]))
    return {"template_type": result.template_type}

def select_template_node(state: RouterState) -> dict:
    # Deterministic lookup based on template_type
    templates = {
        "tech": TECH_TEMPLATE,
        "business": BUSINESS_TEMPLATE,
        "mixed": MIXED_TEMPLATE,
    }
    return {"selected_template": templates[state["template_type"]]}

router_workflow = StateGraph(RouterState)
router_workflow.add_node("classify", classify_node)
router_workflow.add_node("select_template", select_template_node)
router_workflow.set_entry_point("classify")
router_workflow.add_edge("classify", "select_template")
router_workflow.set_finish_point("select_template")

template_router_graph = router_workflow.compile()
```

Then call it from the parent graph's `route_template` node:

```python
def route_template_node(state: AgentState) -> dict:
    result = template_router_graph.invoke({
        "structured_info": state["structured_info"]
    })
    return {
        "template_type": result["template_type"],
        "selected_template": result["selected_template"]
    }
```

### Why sub-graph over LangGraph's multi-agent handoff

Full multi-agent handoff (supervisor/swarm patterns) is designed for agents that take many sequential steps with tool calls. TemplateRouterAgent is a 2-step classify+select workflow. A sub-graph is the right level of abstraction — it shows multi-agent awareness in the architecture without over-engineering.

**Confidence: HIGH** — Sub-graph as callable node is documented and idiomatic.

---

## 4. Checkpointer Patterns

### For this project: SqliteSaver

LangGraph ships two built-in checkpointers:
- `MemorySaver` — in-memory, lost on restart. Use only for testing.
- `SqliteSaver` — persists to a SQLite file. Correct for this project.

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Single connection for single-user Streamlit app
checkpointer = SqliteSaver.from_conn_string(".state/graph_state.db")
```

**Important:** The graph state DB (`graph_state.db`) is separate from the history DB (`history.db`). Keep them separate:
- `graph_state.db` — LangGraph checkpointer (conversation flow state)
- `history.db` — Application data (completed reports, user history)

### Thread lifecycle

Each daily report generation session should use a unique `thread_id`. When the user starts a new report, generate a new thread_id. This prevents stale state from a previous session bleeding into a new one.

```python
import uuid
thread_id = f"report-{date.today().isoformat()}-{uuid.uuid4().hex[:8]}"
```

**Confidence: HIGH** — SqliteSaver is the documented single-user persistence checkpointer.

---

## 5. Connecting Streamlit to LangGraph

### Recommended pattern: `graph.stream()` with SSE-style yielding

Streamlit does not have native async support in the main thread (as of Streamlit 1.x). Use synchronous `graph.stream()` with Streamlit's `st.write_stream()` or manual streaming loop.

```python
# In Streamlit — two-phase interaction

# Phase 1: Initial generation (runs until interrupt)
def run_generation(raw_input: str, repo_path: str, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "raw_input": raw_input,
        "repo_path": repo_path,
        "revision_count": 0,
    }
    # Stream events until interrupt
    for event in graph.stream(initial_state, config=config, stream_mode="updates"):
        node_name = list(event.keys())[0]
        st.session_state["last_node"] = node_name
        # Update progress in UI
        st.session_state["current_state"] = event[node_name]

    # After stream exhausts (interrupted before "review"), get snapshot
    snapshot = graph.get_state(config)
    return snapshot.values

# Phase 2: Resume after human decision
def resume_with_feedback(feedback: str, decision: str, thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    # Inject human input via state update
    graph.update_state(
        config,
        {"human_feedback": feedback, "human_decision": decision}
    )
    # Resume
    for event in graph.stream(None, config=config, stream_mode="updates"):
        pass  # or update progress UI

    snapshot = graph.get_state(config)
    return snapshot.values
```

### Key API calls

| Action | LangGraph API |
|--------|--------------|
| Start graph | `graph.stream(state, config)` or `graph.invoke(state, config)` |
| Check if interrupted | `graph.get_state(config).next` — non-empty means paused |
| Inject human input | `graph.update_state(config, {"field": value})` |
| Resume from interrupt | `graph.stream(None, config)` — pass `None` as input |
| Get current state | `graph.get_state(config).values` |

### Streamlit session state management

Store `thread_id` in `st.session_state` so it persists across button clicks in the same session:

```python
if "thread_id" not in st.session_state:
    st.session_state.thread_id = generate_thread_id()
if "phase" not in st.session_state:
    st.session_state.phase = "input"  # "input" | "review" | "done"
```

Use `st.session_state.phase` to control which UI panel is shown (input form vs review panel vs export panel).

### Avoid async pitfalls

Do NOT use `graph.ainvoke()` / `graph.astream()` directly in Streamlit's main thread — Streamlit's event loop handling in 1.x can cause issues with nested event loops. If you need async, wrap with `asyncio.run()` in a separate thread or use `nest_asyncio`. For a week-scoped project, stick to sync `graph.invoke()`.

**Confidence: MEDIUM** — Streamlit + LangGraph sync streaming is the standard pattern; specific `st.write_stream` integration details depend on Streamlit version.

---

## 6. Data Flow Between Nodes

### Node responsibility matrix

| Node | Reads from State | Writes to State | LLM Call? |
|------|-----------------|-----------------|-----------|
| `extract` | `raw_input` | `structured_info` | YES — extract tasks/output/problems/progress |
| `enrich` | `structured_info`, `repo_path` | `git_log`, `structured_info` (merged) | NO — tool call only (subprocess git log) |
| `route_template` | `structured_info` | `template_type`, `selected_template` | YES (via sub-graph) |
| `draft` | `structured_info`, `selected_template`, `git_log` | `draft` | YES — fill template |
| `polish` | `draft` | `polished` | YES — boss-perspective rewrite |
| `review` | `human_decision` | `human_decision` | NO — pure router |
| `revise` | `polished`, `human_feedback` | `polished`, `revision_count` | YES — targeted revision |
| `save` | `polished` | `final_report`, `export_path`, `history_id` | NO — IO only |

### Critical data flow rules

1. `enrich` is optional: if `repo_path` is None, skip git log and pass state through unchanged.
2. `revise` must increment `revision_count` — this is the loop guard.
3. `save` writes to two sinks: markdown file (file system) and SQLite (history DB). Keep these as separate functions called within `save` node.
4. `polished` is the field that persists across revise loops — `draft` is only used once.

### Conditional edge map

```
enrich → route_template          (always)
route_template → draft           (always)
draft → polish                   (always)
polish → review                  (always, but interrupted before review)
review → save | revise           (conditional: human_decision + revision_count)
revise → review                  (loop back, interrupted again before review)
save → END                       (always)
```

---

## 7. Suggested Build Order

Build in dependency order. Each layer is testable before the next.

### Layer 0: Skeleton (Day 1)
1. Define `AgentState` TypedDict
2. Create all node functions as stubs (return empty dict)
3. Wire the `StateGraph` — add_node, add_edge, add_conditional_edges
4. Compile with `MemorySaver` (no SQLite yet)
5. Run with `graph.invoke()` end-to-end — verify routing works

**Why first:** Graph topology bugs (wrong edge, wrong condition) are easiest to catch when nodes are stubs.

### Layer 1: Core LLM nodes (Day 1-2)
1. `extract` node — implement prompt + parse structured output
2. `draft` node — implement template filling
3. `polish` node — implement boss-perspective rewrite

**Why before routing/tools:** These are the value-generating nodes. Test them in isolation with unit tests before connecting.

### Layer 2: TemplateRouterAgent (Day 2)
1. Build `RouterState` and sub-graph
2. Implement `classify` node (LLM)
3. Implement `select_template` node (deterministic)
4. Integrate into parent graph's `route_template` node

**Why after core nodes:** Sub-graph only adds routing. Core nodes must exist first.

### Layer 3: Git tool (Day 2-3)
1. Implement `enrich` node with subprocess git log call
2. Add None-guard: skip if `repo_path` is None
3. Merge git log into `structured_info`

**Why after core:** Git enrichment is additive. Core flow must work without it.

### Layer 4: Human-in-the-loop (Day 3)
1. Switch checkpointer from `MemorySaver` to `SqliteSaver`
2. Add `interrupt_before=["review"]` to `graph.compile()`
3. Implement `review` node (pure router)
4. Implement `revise` node
5. Test interrupt/resume cycle via Python REPL (no UI yet)

**Why before UI:** HIL logic must be proven correct before layering on Streamlit complexity.

### Layer 5: Storage (Day 3-4)
1. Implement SQLite schema for history
2. Implement `save` node: write markdown + insert SQLite row

### Layer 6: Streamlit UI (Day 4-5)
1. Input form → calls Phase 1 (initial generation)
2. Review panel (shows polished draft, feedback input, approve/revise buttons)
3. Export panel (download markdown, view history)
4. Wire `st.session_state` for phase management

**Why last:** UI is the thinnest layer. All logic must be working before adding UI.

---

## Component Boundaries

| Component | Location | Responsibility |
|-----------|----------|---------------|
| `agent/graph.py` | Core | StateGraph definition, node wiring |
| `agent/state.py` | Core | AgentState TypedDict |
| `agent/nodes/` | Core | One file per node (extract, enrich, etc.) |
| `agent/router/` | Core | TemplateRouterAgent sub-graph |
| `agent/prompts/` | Core | Prompt templates |
| `agent/tools/git_tool.py` | Tool | Git log subprocess wrapper |
| `storage/sqlite.py` | Storage | History DB schema + CRUD |
| `storage/markdown.py` | Storage | Markdown export |
| `ui/app.py` | UI | Streamlit app |
| `ui/components/` | UI | Review panel, history viewer |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Putting interrupt logic inside the review node
**What goes wrong:** Calling `raise NodeInterrupt()` explicitly inside the node instead of using `interrupt_before` on `compile()`.
**Why bad:** `NodeInterrupt` (manual interrupt API) and `interrupt_before` (compile-time) serve different purposes. For a fixed "always pause at review" pattern, compile-time `interrupt_before` is cleaner and guaranteed.
**Instead:** Set `interrupt_before=["review"]` at compile time.

### Anti-Pattern 2: No loop guard on revise
**What goes wrong:** User keeps requesting revisions, graph runs forever (or until API rate limit).
**Why bad:** Infinite loop, runaway API costs, user confusion.
**Instead:** Check `revision_count >= MAX_REVISIONS` in the conditional edge after review. Force save after limit.

### Anti-Pattern 3: Sharing the checkpointer DB with the history DB
**What goes wrong:** LangGraph writes internal serialized state blobs into its tables. Mixing with application data creates schema conflicts and makes history queries fragile.
**Instead:** Two separate SQLite files: `graph_state.db` (LangGraph-managed) and `history.db` (app-managed).

### Anti-Pattern 4: Using `graph.ainvoke()` in Streamlit main thread without nest_asyncio
**What goes wrong:** `RuntimeError: This event loop is already running` in Streamlit.
**Instead:** Use sync `graph.invoke()` / `graph.stream()` for week-scoped project.

### Anti-Pattern 5: Storing the entire polished draft in `human_feedback`
**What goes wrong:** User edits are mixed with AI output. On next revision, LLM doesn't know what changed.
**Instead:** Keep `polished` as the current AI output. Keep `human_feedback` as the user's directive ("make it shorter", "emphasize the metric"). The `revise` node reads both.

---

## Scalability Considerations (Not Needed Now, Good to Know)

| Concern | At Single User | At 10+ Users |
|---------|---------------|-------------|
| Checkpointer | SqliteSaver (file lock OK) | PostgresSaver (concurrent writes) |
| LLM concurrency | Sequential (Streamlit) | Async graph with astream |
| State persistence | Single SQLite file | Separate DB per user |

For a portfolio/single-user project, none of these apply. Build for single user.

---

## Sources

- LangGraph official documentation (training data, LangGraph 0.1.x–0.2.x, HIGH confidence)
- LangGraph How-Tos: human-in-the-loop (interrupt_before/after, update_state) — HIGH confidence
- LangGraph Concepts: StateGraph, reducers, TypedDict schema — HIGH confidence
- LangGraph How-Tos: sub-graphs — HIGH confidence
- SqliteSaver, MemorySaver checkpointer docs — HIGH confidence
- Streamlit sync/async integration: MEDIUM confidence (version-dependent behavior)

**Note:** WebFetch was unavailable during this research session. All findings are based on training data (LangGraph through Aug 2025). The core patterns (interrupt_before, TypedDict state, SqliteSaver, sub-graph as node) are stable documented APIs unlikely to have changed.
