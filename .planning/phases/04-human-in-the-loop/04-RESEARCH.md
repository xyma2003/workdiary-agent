# Phase 4: Human-in-the-Loop - Research

**Researched:** 2026-04-23
**Domain:** LangGraph 1.1.9 interrupt/Command API, SqliteSaver, HITL graph topology
**Confidence:** HIGH (all findings verified by live code execution in the project's conda env)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**interrupt() 设计**
- D-01: `Command(resume={"decision": "approve"|"revise", "feedback": "..."})` dict 结构
- D-02: review_node 内：`response = interrupt({"polished": state.get("polished"), "revision_count": state.get("revision_count", 0)})`，从 response 中提取 `decision` 和 `feedback`，写入 state
- D-03: 只支持 approve 和 revise 两种 decision（edit/inline 路径留到 Phase 6）

**拓扑修改（graph.py）**
- D-04: 删除 Phase 1 的 `review → revise` 直接边
- D-05: 新增 review 节点的条件边：`approve → save`，`revise → revise`（节点名）
- D-06: revise_node 返回后加边 `revise → polish`，循环变为 `polish → review → revise → polish`
- D-07: 原有 `route_after_revise` 条件边（`revise → review/save`）**保留不变**，作为 revision_count >= 3 的强制退出守卫

**revise_node 升级**
- D-08: revise_node 只做两件事：`revision_count += 1`，`human_feedback = feedback from state`
- D-09: revise_node 返回 `{"revision_count": count + 1}`（human_feedback 已在 review_node 写入 state，revise 不需要重写）

**polish_node 小改**
- D-10: 若 `state.get("human_feedback")` 非空，在 HumanMessage 内容末尾追加 `\n\n请根据以下意见修改：{human_feedback}`
- D-11: human_feedback 为空时 polish 行为不变（向后兼容 Phase 2/3 的调用）

**SqliteSaver 替换**
- D-12: `build_graph(use_sqlite: bool = False)` 新增参数
- D-13: `use_sqlite=True` 时：`from langgraph.checkpoint.sqlite import SqliteSaver; checkpointer = SqliteSaver.from_conn_string("graph_state.db")`
- D-14: 默认 `use_sqlite=False` 保持 InMemorySaver，单元测试不写磁盘

**save_node 轻量升级**
- D-15: save_node 返回 `{"final_report": state.get("polished", "")}`（Phase 5 再加 SQLite 写入）
- D-16: 验证 SC-2 用 `graph.get_state(config).next == []`（到达 END）+ `result["final_report"]` 非空

**验收策略**
- D-17: 用独立 Python 脚本（`scripts/test_hitl_cycle.py`）验证完整 interrupt/resume 循环
- D-18: 同时用 pytest + mock LLM 做单元测试，覆盖 interrupt 暂停、approve 路径、revise 循环、第三次强制退出

### Claude's Discretion
- interrupt() 传给用户的 payload 具体内容（除 polished 和 revision_count 外的字段）
- review_node 对 decision 值的容错处理（非 approve/revise 时的 fallback）
- 独立验证脚本的具体输出格式

### Deferred Ideas (OUT OF SCOPE)
- inline-edit 路径（human_decision = "edit"）— Phase 6 UI 层实现
- 异步 AsyncSqliteSaver — Streamlit 是同步的，不需要
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HITL-01 | 生成初稿后系统暂停，用户可查看完整日报内容 | interrupt() in review_node pauses graph at "review"; result dict contains `__interrupt__` key with payload |
| HITL-02 | 用户可直接在文本框中编辑（PHASE 6, not implemented here) | Deferred — out of scope for Phase 4 |
| HITL-03 | 用户可输入修改意见，Agent 根据反馈重新润色（最多循环 3 次） | route_after_revise guard: count >= 3 → save; revise→polish edge enables feedback loop |
| HITL-04 | 用户可一键接受当前版本，结束生成流程 | route_after_review: decision == "approve" → save → END |
</phase_requirements>

---

## Summary

Phase 4 adds real Human-in-the-Loop pause/resume to the WorkDiary Agent graph. The mechanism is LangGraph 1.1.9's `interrupt()` function, which raises an internal `GraphInterrupt` exception on first call in a node, persists state to the checkpointer, and returns the resume payload on re-execution. The caller resumes with `graph.invoke(Command(resume=payload), config)` using the SAME `thread_id`.

Three concrete technical discoveries from live testing require specific planner attention. First, `SqliteSaver.from_conn_string()` is a `@contextmanager` that yields a `SqliteSaver` — using it without `with` returns a `_GeneratorContextManager` object that crashes `compile()` with a `TypeError`. The correct pattern for `build_graph(use_sqlite=True)` is to construct the connection directly via `sqlite3.connect(db_path, check_same_thread=False)` and pass it to `SqliteSaver(conn)`, avoiding the `with`-block lifetime problem. Second, the CONTEXT.md D-07 decision to "keep route_after_revise unchanged" has a hidden subtlety: the function's RETURN VALUES must change from `"review"|"save"` to `"polish"|"save"` because the new D-06 edge makes `revise → polish` the normal path. The guard LOGIC (`count >= 3 → save`) stays identical; only the destination names change. Third, `graph.get_state(config).next` returns a `tuple`, not a list — both `not state.next` and `state.next == ()` and `list(state.next) == []` all work for the D-16 completion check.

**Primary recommendation:** Implement the graph topology change first (graph.py), verify all 3 paths with a standalone script, then implement the node changes. Never wrap review_node's interrupt() in a bare `except Exception` block.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | 1.1.9 | Graph execution, interrupt/Command | Already installed; 1.x interrupt API is stable |
| langgraph-checkpoint-sqlite | 3.0.3 | SqliteSaver for persistent checkpointing | Already in requirements.txt; needed for interrupt to survive process restarts |
| langgraph-checkpoint | 4.0.2 | InMemorySaver (test) | Auto-installed; used for unit tests |
| langchain-core | 1.3.0 | HumanMessage, SystemMessage | Already used in polish.py |

**Import paths (verified against installed whl):**
```python
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
```

**Installation:** All packages already in `requirements.txt`. No new installs needed for Phase 4.

---

## Architecture Patterns

### Recommended Project Structure
No new directories needed. Phase 4 modifies existing files only:
```
workdiary_agent/
├── graph.py          # Topology change + SqliteSaver
├── nodes/
│   ├── review.py     # Replace stub with interrupt()
│   ├── revise.py     # Upgrade: increment count only
│   ├── polish.py     # Small change: read human_feedback
│   └── save.py       # Lightweight upgrade: return final_report
scripts/
└── test_hitl_cycle.py  # NEW: standalone verification script
tests/
└── test_phase04_hitl.py  # NEW: pytest unit tests
```

### Pattern 1: interrupt() Inside Node Body

**What:** Call `interrupt(payload)` inside a node function. On first execution it raises `GraphInterrupt` (a subclass of `Exception`), halting the graph. The return value of `interrupt()` is the dict passed via `Command(resume=...)` on the second execution.

**When to use:** Any HITL pause point where you want to both send context to the user AND receive input.

```python
# Source: verified by live execution in llm-data-pipeline conda env
from langgraph.types import interrupt, Command

def review_node(state: AgentState) -> dict:
    response = interrupt({
        "polished": state.get("polished"),
        "revision_count": state.get("revision_count", 0),
    })
    # response is the dict from Command(resume={...})
    decision = response.get("decision", "approve")
    feedback = response.get("feedback", "")
    return {"human_decision": decision, "human_feedback": feedback}
```

**Critical:** `interrupt()` MUST NOT be inside a `try/except Exception` block. `GraphInterrupt` IS-A `Exception` (verified: `GraphInterrupt.__bases__ == (GraphBubbleUp,)`, `issubclass(GraphInterrupt, Exception) == True`). A bare `except Exception` will swallow the interrupt and the node will complete without pausing.

### Pattern 2: Resuming with Command

**What:** Pass `Command(resume=payload)` as the first argument to `graph.invoke()` with the SAME config (same thread_id).

```python
# Source: verified by live execution
# Initial invocation (pauses at interrupt)
result = graph.invoke({"raw_input": "..."}, config)
# result contains: {"polished": "...", "__interrupt__": [Interrupt(value={...}, id="...")]}

# Resume after user input
result2 = graph.invoke(
    Command(resume={"decision": "approve", "feedback": ""}),
    config,   # SAME config with SAME thread_id
)
```

**Command dataclass fields (verified):**
- `resume: dict[str, Any] | Any | None` — the value returned by `interrupt()`
- `update: Any | None` — optional state update
- `goto: Send | Sequence[...] | N` — optional routing
- `graph: str | None` — optional graph name

### Pattern 3: graph topology for HITL loop

**The correct Phase 4 topology (verified with all 3 paths):**

```python
# graph.py - Phase 4 changes
def route_after_review(state: AgentState) -> Literal["save", "revise"]:
    decision = state.get("human_decision", "approve")
    return "save" if decision == "approve" else "revise"

def route_after_revise(state: AgentState) -> Literal["polish", "save"]:
    # CHANGED from Phase 1: returns "polish"|"save" not "review"|"save"
    # Guard logic UNCHANGED: count >= 3 → force to save
    count = state.get("revision_count", 0)
    return "save" if count >= 3 else "polish"

# In build_graph():
# Delete: builder.add_edge("review", "revise")        # D-04: remove direct edge
# Add: review conditional edge                         # D-05
builder.add_conditional_edges(
    "review",
    route_after_review,
    {"save": "save", "revise": "revise"},
)
# Replace: revise conditional edge (D-06 + D-07 combined)
# OLD: {"review": "review", "save": "save"}
# NEW: {"polish": "polish", "save": "save"}
builder.add_conditional_edges(
    "revise",
    route_after_revise,
    {"polish": "polish", "save": "save"},
)
# Note: NO separate add_edge("revise", "polish") — the conditional edge IS the revise→polish path
```

**CRITICAL TOPOLOGY NOTE (discovered during verification):** D-06 says "add edge revise → polish" and D-07 says "keep route_after_revise unchanged." These decisions CANNOT both be satisfied literally. If you add `builder.add_edge("revise", "polish")` AND keep `builder.add_conditional_edges("revise", route_after_revise, {"review": ..., "save": ...})`, you get dual outgoing edges from `revise` that conflict in practice (tested: force-exit after 3 revisions breaks). The correct interpretation of D-06/D-07 is:
- D-07 means "keep the guard LOGIC" (count >= 3 → save), not "keep the literal return values"
- Implement as a SINGLE `add_conditional_edges("revise", route_after_revise, {"polish": "polish", "save": "save"})`
- This replaces the Phase 1 conditional edge entirely
- No separate `add_edge("revise", "polish")` is needed

### Pattern 4: SqliteSaver without context manager lifetime problem

**The problem:** `SqliteSaver.from_conn_string()` is a `@contextmanager` that yields a `SqliteSaver`. Calling it without `with` returns a `_GeneratorContextManager`, which causes `TypeError: Invalid checkpointer provided` at compile time.

**The solution:** Construct the SQLite connection directly.

```python
# Source: verified by live execution
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import InMemorySaver

def build_graph(use_sqlite: bool = False):
    builder = StateGraph(AgentState)
    # ... add nodes and edges ...

    if use_sqlite:
        # Direct connection — no context manager needed, no lifetime issue
        conn = sqlite3.connect("graph_state.db", check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    else:
        checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
```

**Alternative (also valid):** Use `with SqliteSaver.from_conn_string(...) as saver` at the call site and pass `saver` into `build_graph()`. But the direct-connection pattern is simpler for this project.

### Pattern 5: Checking graph completion

```python
# Source: verified by live execution
state = graph.get_state(config)

# state.next is a TUPLE, not a list
# All of these work:
is_done = not state.next          # simplest
is_done = state.next == ()        # explicit tuple comparison
is_done = list(state.next) == []  # D-16 pattern from CONTEXT.md

# When paused at interrupt:
state.next == ("review",)         # contains the node name
"review" in state.next            # True when paused at review
```

### Anti-Patterns to Avoid

- **Swallowing GraphInterrupt:** `try: response = interrupt(...)  except Exception: ...` — `GraphInterrupt` IS-A `Exception` and will be caught, causing silent pass-through without pausing.
- **Using from_conn_string without `with`:** `checkpointer = SqliteSaver.from_conn_string("db")` returns a context manager object, not a `SqliteSaver` — causes `TypeError` at `compile()`.
- **New thread_id on resume:** Always use the same config/thread_id for resume. A new thread_id creates a fresh graph execution that pauses immediately again.
- **D-07 literal interpretation:** Do NOT add both `builder.add_edge("revise", "polish")` AND keep `add_conditional_edges("revise", ..., {"review":..., "save":...})` — this creates conflicting paths.
- **Bracket access on unset state keys:** `state["revision_count"]` raises `KeyError` when unset in `total=False` TypedDict. Always use `state.get("revision_count", 0)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pausing execution for human input | Custom flag + polling loop | `interrupt()` from `langgraph.types` | interrupt() integrates with checkpointer for state persistence; polling has race conditions |
| Resuming paused graph | Custom state machine re-entry | `Command(resume=...)` passed to `graph.invoke()` | Command is the only documented resume mechanism; alternatives break state replay |
| Persistent checkpointing | Custom SQLite write/read in nodes | `SqliteSaver` from `langgraph-checkpoint-sqlite` | SqliteSaver implements the full `BaseCheckpointSaver` protocol including serialization, blob storage, and channel versioning |
| Counting interrupts | Custom interrupt counter | LangGraph's built-in scratchpad counter | `interrupt()` uses `CONFIG_KEY_SCRATCHPAD.interrupt_counter()` internally; multiple interrupt() calls in one node are correctly sequenced |

---

## Common Pitfalls

### Pitfall 1: GraphInterrupt Swallowed in try/except
**What goes wrong:** Node completes without pausing; graph runs straight through to save.
**Why it happens:** `GraphInterrupt` subclasses `Exception` (chain: `GraphInterrupt → GraphBubbleUp → Exception`). Any `except Exception:` block catches it.
**How to avoid:** Never wrap `interrupt()` in a bare `except Exception`. Only catch specific exceptions if needed:
```python
# WRONG:
try:
    response = interrupt(payload)
except Exception:  # catches GraphInterrupt!
    ...

# RIGHT:
response = interrupt(payload)  # no try/except wrapping interrupt()
```
**Warning signs:** Graph returns `final_report` on first invoke without any `Command(resume=...)` call.

### Pitfall 2: thread_id Regenerated on Resume
**What goes wrong:** `Command(resume=...)` starts a NEW graph execution that pauses immediately, rather than resuming the existing one.
**Why it happens:** The checkpointer uses `thread_id` as the primary key for state lookup. A different `thread_id` creates a new checkpoint namespace.
**How to avoid:** Store and reuse the exact same config dict for both initial invoke and all resumes. In `scripts/test_hitl_cycle.py`, define `config` once at the top of each test case.
**Warning signs:** `graph.get_state(config).next` shows `("review",)` after a `Command(resume=...)` call that should have completed.

### Pitfall 3: from_conn_string Used Without Context Manager
**What goes wrong:** `TypeError: Invalid checkpointer provided... Received _GeneratorContextManager` at compile time.
**Why it happens:** `from_conn_string` is decorated with `@contextmanager`, so calling it returns a generator object.
**How to avoid:** Use direct `sqlite3.connect()` + `SqliteSaver(conn)` pattern (see Pattern 4 above).
**Warning signs:** `build_graph(use_sqlite=True)` raises `TypeError` at the `builder.compile()` call.

### Pitfall 4: route_after_revise Returning "review" After Topology Change
**What goes wrong:** Force-exit after 3 revisions never triggers because `revise → review → revise` is now an invalid cycle (review no longer has a direct edge to revise; the conditional edge sends approve→save, revise→revise).
**Why it happens:** D-07 says "保留不变" but the topology changed. The return value `"review"` no longer matches any edge destination after D-04/D-05/D-06.
**How to avoid:** Update `route_after_revise` to return `Literal["polish", "save"]` and update `add_conditional_edges` accordingly.
**Warning signs:** `revise → review` path causes re-interrupt at review without incrementing count; the 3-revision limit never triggers.

### Pitfall 5: No Loop Guard on Revision Count
**What goes wrong:** Infinite loop between polish → review → revise → polish.
**Why it happens:** If `route_after_revise` always returns `"polish"` (missing the `>= 3 → save` guard), the graph never terminates.
**How to avoid:** The guard `return "save" if count >= 3 else "polish"` must use `state.get("revision_count", 0)` (not `state["revision_count"]`) and compare against `3`.
**Warning signs:** Third `Command(resume={"decision": "revise", ...})` causes another interrupt instead of going to save.

---

## Code Examples

### review_node — Full Implementation
```python
# Source: verified pattern from live testing (llm-data-pipeline env)
from langgraph.types import interrupt
from ..state import AgentState

def review_node(state: AgentState) -> dict:
    """HITL pause: sends polished content to user, receives decision/feedback.

    interrupt() raises GraphInterrupt on first execution, resuming with the
    dict passed via Command(resume={...}) on subsequent execution.
    NEVER wrap interrupt() in bare except Exception — GraphInterrupt IS-A Exception.
    """
    response = interrupt({
        "polished": state.get("polished"),
        "revision_count": state.get("revision_count", 0),
    })
    decision = response.get("decision", "approve")
    feedback = response.get("feedback", "")
    # Fallback for unrecognized decision values (Claude's discretion)
    if decision not in ("approve", "revise"):
        decision = "approve"
    return {"human_decision": decision, "human_feedback": feedback}
```

### revise_node — Upgraded Implementation
```python
# Source: D-08/D-09 from CONTEXT.md + verified by live testing
from ..state import AgentState

def revise_node(state: AgentState) -> dict:
    """Increment revision count only. human_feedback already written by review_node."""
    count = state.get("revision_count", 0)
    return {"revision_count": count + 1}
```

### polish_node — human_feedback Integration
```python
# Source: D-10/D-11 from CONTEXT.md
def polish_node(state: AgentState) -> dict:
    draft = state.get("draft", "")
    human_feedback = state.get("human_feedback")

    if not draft or draft == "[stub draft]":
        return {"polished": draft or ""}

    llm = _make_llm()
    content = f"请润色以下日报初稿：\n\n{draft}"
    if human_feedback:  # D-10: append feedback when present
        content += f"\n\n请根据以下意见修改：{human_feedback}"

    response = llm.invoke([
        SystemMessage(content=_POLISH_SYSTEM),
        HumanMessage(content=content),
    ])
    return {"polished": response.content}
```

### graph.py — Phase 4 Topology Changes
```python
# Source: verified correct topology from live testing all 3 paths
from typing import Literal
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import InMemorySaver

def route_after_review(state: AgentState) -> Literal["save", "revise"]:
    """New conditional edge from review node."""
    decision = state.get("human_decision", "approve")
    return "save" if decision == "approve" else "revise"

def route_after_revise(state: AgentState) -> Literal["polish", "save"]:
    """UPDATED: was Literal["review", "save"]. Guard logic unchanged; destination renamed."""
    count = state.get("revision_count", 0)
    return "save" if count >= 3 else "polish"

def build_graph(use_sqlite: bool = False):
    builder = StateGraph(AgentState)
    # ... add_node() calls unchanged ...

    builder.add_edge(START, "extract")
    builder.add_edge("extract", "enrich")
    builder.add_edge("enrich", "route_template")
    builder.add_edge("route_template", "draft")
    builder.add_edge("draft", "polish")
    builder.add_edge("polish", "review")
    # D-04: deleted builder.add_edge("review", "revise")
    # D-05: new conditional edge from review
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {"save": "save", "revise": "revise"},
    )
    # D-06+D-07 combined: single conditional edge replaces Phase 1 conditional edge
    builder.add_conditional_edges(
        "revise",
        route_after_revise,
        {"polish": "polish", "save": "save"},
    )
    builder.add_edge("save", END)

    if use_sqlite:
        conn = sqlite3.connect("graph_state.db", check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    else:
        checkpointer = InMemorySaver()

    return builder.compile(checkpointer=checkpointer)
```

### scripts/test_hitl_cycle.py — Verification Script Template
```python
# Source: pattern from existing scripts/test_skeleton.py + verified test patterns
import sys, os
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from langgraph.types import Command
from workdiary_agent.graph import build_graph

def test_path1_approve():
    """SC-2: approve → final_report non-empty, next == ()"""
    g = build_graph()
    cfg = {"configurable": {"thread_id": "hitl-path1"}}
    r1 = g.invoke({"raw_input": "test"}, cfg)
    assert "__interrupt__" in r1
    r2 = g.invoke(Command(resume={"decision": "approve", "feedback": ""}), cfg)
    assert r2.get("final_report"), "final_report should be non-empty"
    assert not g.get_state(cfg).next, "graph should be at END"
    print("PASS: Path 1 (approve)")

def test_path2_revise_then_approve():
    """SC-3: revise → loop (pauses again with count=1)"""
    g = build_graph()
    cfg = {"configurable": {"thread_id": "hitl-path2"}}
    g.invoke({"raw_input": "test"}, cfg)
    g.invoke(Command(resume={"decision": "revise", "feedback": "add more context"}), cfg)
    state = g.get_state(cfg)
    assert "review" in state.next
    assert state.values.get("revision_count", 0) == 1
    r = g.invoke(Command(resume={"decision": "approve", "feedback": ""}), cfg)
    assert r.get("final_report")
    print("PASS: Path 2 (revise once then approve)")

def test_path3_force_exit():
    """SC-4: 3 revisions → force save, next == ()"""
    g = build_graph()
    cfg = {"configurable": {"thread_id": "hitl-path3"}}
    g.invoke({"raw_input": "test"}, cfg)
    for i in range(3):
        g.invoke(Command(resume={"decision": "revise", "feedback": f"fix {i+1}"}), cfg)
    state = g.get_state(cfg)
    assert not state.next, f"Expected END, got {state.next}"
    assert state.values.get("final_report") is not None
    assert state.values.get("revision_count", 0) == 3
    print("PASS: Path 3 (force exit after 3 revisions)")
```

### pytest unit test patterns (tests/test_phase04_hitl.py)
```python
# Source: pattern from tests/test_phase03_enrichment.py + verified test patterns
import pytest
from unittest.mock import patch, MagicMock
from langgraph.types import Command
from workdiary_agent.graph import build_graph, route_after_revise, route_after_review

# SC-1 test
def test_graph_pauses_at_review_after_invoke():
    g = build_graph()
    cfg = {"configurable": {"thread_id": "sc1"}}
    # Mock LLM calls to avoid real API calls
    with patch("workdiary_agent.nodes.extract.ChatAnthropic"), \
         patch("workdiary_agent.nodes.polish.ChatAnthropic"), \
         # ... other LLM mocks ...
    :
        result = g.invoke({"raw_input": "test"}, cfg)
    assert "review" in g.get_state(cfg).next

# Route function unit tests (no LLM needed)
def test_route_after_review_approve():
    assert route_after_review({"human_decision": "approve"}) == "save"

def test_route_after_review_revise():
    assert route_after_review({"human_decision": "revise"}) == "revise"

def test_route_after_revise_under_limit():
    assert route_after_revise({"revision_count": 0}) == "polish"
    assert route_after_revise({"revision_count": 2}) == "polish"

def test_route_after_revise_at_limit():
    assert route_after_revise({"revision_count": 3}) == "save"
    assert route_after_revise({"revision_count": 4}) == "save"
    assert route_after_revise({}) == "polish"  # unset defaults to 0
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `interrupt_before=["node"]` at compile | `interrupt()` inside node body | LangGraph 1.x | Compile-level pauses before node runs; body-level pauses mid-node with context |
| `MemorySaver` | `InMemorySaver` | LangGraph 1.x | `MemorySaver` is a backwards-compat alias at line 530 of checkpoint/memory/__init__.py |
| Direct `interrupt_before` | `interrupt()` function | LangGraph 1.x | `interrupt()` sends payload to caller; `interrupt_before` does not |

**Deprecated/outdated:**
- `interrupt_before=["review"]` at compile: valid but gives no context to UI; body-level `interrupt()` is the correct pattern for this project
- `MemorySaver`: alias works but `InMemorySaver` is canonical

---

## Open Questions

1. **build_graph() module-level graph instance**
   - What we know: `graph.py` exports `graph = build_graph()` at module level (line 106). Phase 4 makes `build_graph()` parameterized.
   - What's unclear: Should the module-level `graph` use `use_sqlite=True` or `False`? If `True`, it writes `graph_state.db` on import, which may be unexpected.
   - Recommendation: Keep `graph = build_graph()` (use_sqlite=False). Scripts and production code that need SQLite should call `build_graph(use_sqlite=True)` explicitly. Unit tests import `build_graph` directly.

2. **test_phase04_hitl.py: LLM mocking scope**
   - What we know: End-to-end graph tests must mock `extract_node`, `enrich_node`, `draft_node`, `polish_node` to avoid real Claude API calls.
   - What's unclear: Whether to test the full graph (more realistic) or individual node functions (faster). The existing phase tests use both approaches.
   - Recommendation: Test routing functions (`route_after_review`, `route_after_revise`) without mocking; test full graph flow for SC-1 through SC-4 with LLM mocks.

---

## Environment Availability

All dependencies are already installed. No new packages required.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| langgraph | interrupt/Command API | ✓ | 1.1.9 | — |
| langgraph-checkpoint-sqlite | SqliteSaver | ✓ | 3.0.3 | — |
| sqlite3 | Direct connection pattern | ✓ | stdlib | — |
| pytest | Unit tests | ✓ | (installed) | — |
| conda env: llm-data-pipeline | All runtime | ✓ | active | — |

**Run command:** `conda run -n llm-data-pipeline pytest tests/test_phase04_hitl.py -v`

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, all prior phases use it) |
| Config file | none (no pytest.ini; run with conda run) |
| Quick run command | `conda run -n llm-data-pipeline pytest tests/test_phase04_hitl.py -v` |
| Full suite command | `conda run -n llm-data-pipeline pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HITL-01 | Graph pauses at review after invoke | unit | `pytest tests/test_phase04_hitl.py::test_graph_pauses_at_review -x` | ❌ Wave 0 |
| HITL-03 | Revise loops, count increments | unit | `pytest tests/test_phase04_hitl.py::test_revise_loop -x` | ❌ Wave 0 |
| HITL-03 | 3rd revise → force save | unit | `pytest tests/test_phase04_hitl.py::test_force_exit -x` | ❌ Wave 0 |
| HITL-04 | Approve → final_report non-empty | unit | `pytest tests/test_phase04_hitl.py::test_approve_path -x` | ❌ Wave 0 |
| SC-5 | Full 3-path verification | smoke | `conda run -n llm-data-pipeline python scripts/test_hitl_cycle.py` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `conda run -n llm-data-pipeline pytest tests/test_phase04_hitl.py -v`
- **Per wave merge:** `conda run -n llm-data-pipeline pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase04_hitl.py` — covers HITL-01, HITL-03, HITL-04
- [ ] `scripts/test_hitl_cycle.py` — covers SC-5 (standalone verification, all 3 paths)

*(Existing test infrastructure is sufficient — only new test files need to be created)*

---

## Sources

### Primary (HIGH confidence)
- Live code execution in `llm-data-pipeline` conda env with langgraph 1.1.9 — all patterns verified by running tests
- `langgraph/types.py` (installed whl, extracted): `interrupt` function source, `GraphInterrupt` exception chain, `Interrupt` dataclass, `Command` dataclass fields
- `langgraph/checkpoint/sqlite/__init__.py` (installed whl): `SqliteSaver.__init__`, `from_conn_string` as `@contextmanager`
- `langgraph/errors.py` (installed): `GraphInterrupt → GraphBubbleUp → Exception` MRO confirmed

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions D-01 through D-18 — user/Claude-agreed design choices, confirmed compatible with live API behavior
- Existing `workdiary_agent/graph.py` — Phase 1 topology confirmed; phase 4 topology conflict identified by testing

---

## Metadata

**Confidence breakdown:**
- interrupt/Command API: HIGH — verified by running 4 distinct test scenarios in project env
- SqliteSaver lifetime: HIGH — verified that `from_conn_string()` without `with` fails; direct `sqlite3.connect()` pattern works
- Topology D-06/D-07 conflict: HIGH — live tests prove dual-edge approach breaks force-exit; single conditional edge is correct
- Unit test patterns: HIGH — all 4 success criteria tested and passing in prototype

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (stable LangGraph 1.x API; SqliteSaver interface unlikely to change)
