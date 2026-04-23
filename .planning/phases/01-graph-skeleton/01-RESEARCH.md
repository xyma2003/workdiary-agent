# Phase 1: Graph Skeleton - Research

**Researched:** 2026-04-23
**Domain:** LangGraph 1.1.9 StateGraph API — TypedDict state, node wiring, conditional edges, InMemorySaver checkpointing
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** New `workdiary_agent/` package at project root, alongside `桌面动物园/`
- **D-02:** Layered split: `workdiary_agent/graph.py` (StateGraph assembly), `workdiary_agent/state.py` (AgentState TypedDict + Pydantic models), `workdiary_agent/nodes/` (one stub file per node)
- **D-03:** Phase 2–6 extend sub-directories; graph.py assembly logic stays stable
- **D-04:** `structured_info` is `Optional[StructuredInfo]` where `StructuredInfo` is a Pydantic BaseModel in state.py
- **D-05:** `human_decision` type is `Literal["approve", "revise", "edit"] | None`
- **D-06:** All fields have defaults (Optional→None, revision_count→0) so `graph.invoke({"raw_input": "test"}, config)` works with partial input
- **D-07:** Phase 1 `route_template` node is a plain stub function — no sub-graph nesting in Phase 1
- **D-08:** Compile with `MemorySaver` (alias for `InMemorySaver`): `builder.compile(checkpointer=MemorySaver())`
- **D-09:** Invoke with `config={"configurable": {"thread_id": "test-1"}}` from Phase 1 onwards

### Claude's Discretion

- Specific content returned by each stub node (type-correct stubs only)
- File naming inside `nodes/` subdirectory
- `__init__.py` export style

### Deferred Ideas (OUT OF SCOPE)

None — all discussion stayed within Phase 1 scope.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AGENT-01 | User can describe today's work in natural language (口语化) in an input field | Skeleton-level: `raw_input: str` field present in AgentState; `graph.invoke({"raw_input": "test"}, config)` succeeds without error |

</phase_requirements>

---

## Summary

Phase 1 builds a runnable LangGraph StateGraph skeleton for WorkDiary Agent. All nodes (extract, enrich, route_template, draft, polish, review, revise, save) are implemented as stub functions. The conditional edge logic — revise routes to review unless `revision_count >= 3`, in which case it routes to save — is the only non-trivial wiring in this phase. AgentState is a TypedDict with all downstream fields defined and defaulted, enabling partial invocation with only `raw_input`.

The primary source of confusion in this domain is naming: `InMemorySaver` is the canonical class in langgraph-checkpoint 4.x; `MemorySaver` is a backwards-compat alias at line 530 of the source. The project uses `MemorySaver` per decision D-08, which works because the alias is preserved. However, import must come from `langgraph.checkpoint.memory`, not from `langgraph` directly.

LangGraph 1.1.9 fully supports cyclic graphs (the revise→review→revise loop). There is no built-in cycle detection in `StateGraph.validate()` — cycles are intentional and handled by the conditional edge guard. The graph will loop indefinitely without a termination condition, making the `revision_count >= 3` guard in the conditional edge function non-negotiable.

**Primary recommendation:** Build state.py first (AgentState + StructuredInfo), then nodes/ stubs, then assemble graph.py last. Each layer is independently importable and testable in isolation.

---

## Standard Stack

### Core (Phase 1 relevant subset)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| langgraph | 1.1.9 | StateGraph, conditional edges, compile | Locked by STACK.md |
| langgraph-checkpoint | 4.0.2 | InMemorySaver / MemorySaver alias | Auto-installed by langgraph 1.1.9 |
| pydantic | 2.12.4 | StructuredInfo BaseModel in state.py | Locked by STACK.md; required by langgraph |
| langchain-core | 1.3.0 | RunnableConfig type hint (optional in stubs) | Auto-installed by langgraph |

**All versions locked in `.planning/research/STACK.md`. Do not re-research.**

**Installation (for the project's conda env or fresh venv):**

```bash
pip install "langgraph==1.1.9" "langchain-anthropic==1.4.1" \
    "langgraph-checkpoint-sqlite==3.0.3" "streamlit==1.56.0" \
    "gitpython==3.1.47"
```

Note: langgraph is NOT currently installed in the `llm-data-pipeline` conda environment. Wave 0 must include a `pip install` step or environment setup task.

---

## Architecture Patterns

### Recommended Project Structure

```
workdiary_agent/
├── __init__.py          # exports: build_graph (or graph)
├── graph.py             # StateGraph assembly only — add_node, add_edge, compile
├── state.py             # AgentState TypedDict + StructuredInfo Pydantic model
└── nodes/
    ├── __init__.py      # re-exports all node functions
    ├── extract.py
    ├── enrich.py
    ├── route_template.py
    ├── draft.py
    ├── polish.py
    ├── review.py
    ├── revise.py
    └── save.py
```

### Pattern 1: AgentState TypedDict with Defaults

TypedDict does not natively support default values. The LangGraph pattern for defaults is to use `total=False` for optional fields or provide defaults via `NotRequired`. For Phase 1, the simplest correct approach is to use `total=False` for fields that are not required at invocation time, or use a wrapper that populates defaults before passing to `invoke`.

The cleanest approach verified from LangGraph source and STACK.md patterns:

```python
# Source: langgraph/graph/state.py — TypedDict state with Annotated reducers
# Source: STACK.md §Key API Patterns §StateGraph
from __future__ import annotations
from typing import Optional, Annotated
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


class StructuredInfo(BaseModel):
    """Filled by extract node in Phase 2 via llm.with_structured_output()."""
    tasks: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    progress: str = ""


class AgentState(TypedDict, total=False):
    # Required field — caller must supply this
    raw_input: str

    # All remaining fields are optional (total=False covers them)
    structured_info: Optional[StructuredInfo]
    template_type: Optional[str]         # "技术型" | "业务型" | "混合型"
    draft: Optional[str]
    polished: Optional[str]
    human_decision: Optional[str]        # Literal["approve","revise","edit"]
    human_feedback: Optional[str]
    revision_count: int                  # default 0 via graph initialization
    git_log: Optional[str]
    repo_path: Optional[str]
    final_report: Optional[str]
    export_path: Optional[str]
```

**Important caveat on `total=False` and `revision_count`:** With `total=False`, accessing `state["revision_count"]` will raise `KeyError` if the key was never set. The stub revise node and the conditional edge function must use `state.get("revision_count", 0)` instead of `state["revision_count"]`. This is the correct defensive pattern.

**Alternative approach — explicit defaults via `__init__` wrapper:** Wrap the invoke call so defaults are injected before the TypedDict reaches the graph. This avoids `total=False` but adds a layer. For Phase 1, `total=False` + `.get(key, default)` is simpler.

### Pattern 2: add_node with Explicit Name String

```python
# Source: langgraph/graph/state.py lines 430-495 (overload 3)
# builder.add_node("name", callable) — preferred when node function name != desired node name
builder.add_node("extract", extract_node)
builder.add_node("enrich", enrich_node)
builder.add_node("route_template", route_template_node)
builder.add_node("draft", draft_node)
builder.add_node("polish", polish_node)
builder.add_node("review", review_node)
builder.add_node("revise", revise_node)
builder.add_node("save", save_node)
```

The string-name overload signature is: `add_node(self, node: str, action: StateNode, *, ...)`. Using explicit string names decouples the node name (used in edges) from the Python function name, which matters because the graph's node names are part of the success criteria.

### Pattern 3: Conditional Edge for revise→review Loop

```python
# Source: langgraph/graph/state.py lines 842-890
# Source: STACK.md §Key API Patterns §StateGraph

from langgraph.graph import END

def route_after_revise(state: AgentState) -> str:
    """Routes to 'review' if under revision limit, 'save' if limit reached."""
    count = state.get("revision_count", 0)
    if count >= 3:
        return "save"
    return "review"

# In graph.py assembly:
builder.add_conditional_edges(
    "revise",
    route_after_revise,
    {
        "review": "review",
        "save": "save",
    }
)
```

The `path_map` dict (third argument) maps return values of the routing function to node names. When `path_map` is provided, the routing function returns a key from the dict, not a node name directly. When `path_map` is omitted, the routing function must return actual node names or `END`.

**Type hint on routing function return value** is recommended by the LangGraph source docstring (line 868): adding `-> Literal["review", "save"]` helps graph visualization and static analysis, but is not required for execution.

### Pattern 4: Complete Graph Assembly in graph.py

```python
# Source: STACK.md §Key API Patterns §StateGraph + source-verified signatures
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from typing import Literal

from .state import AgentState
from .nodes import (
    extract_node, enrich_node, route_template_node,
    draft_node, polish_node, review_node, revise_node, save_node
)


def route_after_revise(state: AgentState) -> Literal["review", "save"]:
    count = state.get("revision_count", 0)
    return "save" if count >= 3 else "review"


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("extract", extract_node)
    builder.add_node("enrich", enrich_node)
    builder.add_node("route_template", route_template_node)
    builder.add_node("draft", draft_node)
    builder.add_node("polish", polish_node)
    builder.add_node("review", review_node)
    builder.add_node("revise", revise_node)
    builder.add_node("save", save_node)

    builder.add_edge(START, "extract")
    builder.add_edge("extract", "enrich")
    builder.add_edge("enrich", "route_template")
    builder.add_edge("route_template", "draft")
    builder.add_edge("draft", "polish")
    builder.add_edge("polish", "review")
    builder.add_edge("review", "revise")    # Phase 4 replaces with interrupt()
    builder.add_conditional_edges("revise", route_after_revise, {"review": "review", "save": "save"})
    builder.add_edge("save", END)

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


# Module-level graph for convenience
graph = build_graph()
```

### Pattern 5: Stub Node Signature

Each stub must accept `state: AgentState` and return a dict with only the fields it sets. LangGraph merges the returned dict into the current state — nodes do NOT return a full state copy.

```python
# Source: langgraph/graph/state.py — "signature of each node is State -> Partial<State>"

def extract_node(state: AgentState) -> dict:
    """Stub: Phase 2 will call LLM to extract structured info."""
    return {"structured_info": None}


def revise_node(state: AgentState) -> dict:
    """Stub: Phase 4 will apply human feedback. Increments revision_count."""
    count = state.get("revision_count", 0)
    return {"revision_count": count + 1}


def route_template_node(state: AgentState) -> dict:
    """Stub: Phase 2 replaces with TemplateRouterAgent sub-graph."""
    return {"template_type": "技术型"}
```

### Anti-Patterns to Avoid

- **Returning full state from a node:** `return state` or `return dict(state)` — LangGraph merges partial updates; returning the full state dict sets every field, which is wasteful and can mask bugs.
- **Using `MemorySaver` from `langgraph` top-level:** The canonical import is `from langgraph.checkpoint.memory import InMemorySaver`. The alias `MemorySaver` lives at the same path: `from langgraph.checkpoint.memory import MemorySaver` also works (confirmed line 530 of source), but the top-level `langgraph` namespace does not re-export it.
- **Calling `graph.invoke()` without `config`:** When a checkpointer is attached, omitting the `config` with `thread_id` causes a runtime error. Always pass `config={"configurable": {"thread_id": "..."}}`.
- **Using `state["revision_count"]` without a default:** With `total=False` TypedDict, unset keys raise `KeyError`. Use `state.get("revision_count", 0)` in the revise stub and the routing function.
- **`set_entry_point()` instead of `add_edge(START, ...)`:** `set_entry_point` is a deprecated wrapper in 1.x. Use `add_edge(START, "node_name")` directly.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State merging | Custom dict merge logic in nodes | LangGraph's native partial-update protocol | Nodes return `dict` of changed keys only; LangGraph handles the merge. Custom merge adds bugs. |
| Thread/session memory | Custom in-memory dict for graph state | `InMemorySaver` checkpointer | InMemorySaver handles checkpoint storage, versioning, and thread isolation. Hand-rolling duplicates all of this. |
| Cycle termination | Custom recursion counter outside state | `revision_count` field in AgentState + conditional edge guard | The count lives in graph state so it's checkpointed; placing it outside state loses persistence in Phase 4. |
| Pydantic-in-TypedDict compatibility | Custom serialization of StructuredInfo | Store as `Optional[StructuredInfo]` directly in TypedDict | LangGraph 1.1.9 uses `pydantic>=2.7.4` and handles Pydantic objects in TypedDict state transparently. |

**Key insight:** LangGraph's state merge and checkpoint protocol handles the complexity that would otherwise require custom infrastructure. Keep nodes as pure functions returning partial dicts.

---

## Common Pitfalls

### Pitfall 1: Missing `config` in invoke() with Checkpointer

**What goes wrong:** `graph.invoke({"raw_input": "test"})` raises a runtime error — something like `ValueError: No thread_id provided` or similar when checkpointer is attached.

**Why it happens:** `InMemorySaver` requires a `thread_id` to store checkpoints. Without `config`, the checkpointer cannot determine which thread's state to read/write.

**How to avoid:** Always call `graph.invoke({"raw_input": "test"}, config={"configurable": {"thread_id": "test-1"}})`.

**Warning signs:** Any `AttributeError` or `KeyError` related to `thread_id` or `configurable` during `invoke`.

### Pitfall 2: `MemorySaver` Import Path

**What goes wrong:** `from langgraph import MemorySaver` raises `ImportError`. `from langgraph.checkpoint import MemorySaver` also fails.

**Why it happens:** `MemorySaver` (and `InMemorySaver`) live in the `langgraph-checkpoint` package, not the `langgraph` package. The `langgraph` wheel does not include a `checkpoint/` directory.

**How to avoid:** Use `from langgraph.checkpoint.memory import InMemorySaver` (canonical) or `from langgraph.checkpoint.memory import MemorySaver` (alias). Both are verified present at `/tmp/lgcp_src/langgraph/checkpoint/memory/__init__.py` lines 31 and 530.

**Warning signs:** `ModuleNotFoundError: No module named 'langgraph.checkpoint'` — means `langgraph-checkpoint` package is not installed.

### Pitfall 3: Accessing Missing State Keys with `total=False` TypedDict

**What goes wrong:** `state["revision_count"]` raises `KeyError` on the first invocation because the key was never explicitly set in the initial `{"raw_input": "test"}` call.

**Why it happens:** `total=False` TypedDict means all keys are optional. If a node or routing function uses bracket access on an unset key, it crashes.

**How to avoid:** Use `state.get("revision_count", 0)` in any node or routing function that accesses a key that might not be set. Alternatively, handle defaults in a dedicated "initialize" node that runs first.

**Warning signs:** `KeyError` in a node function pointing to a state field.

### Pitfall 4: Infinite Loop Without Routing Guard

**What goes wrong:** Graph loops forever between `revise` and `review` nodes, never reaching `save`.

**Why it happens:** LangGraph does not detect infinite cycles — they are a feature. If `route_after_revise` always returns `"review"`, execution never terminates.

**How to avoid:** Ensure `route_after_revise` checks `revision_count >= 3` and returns `"save"`. The `revise_node` stub must increment `revision_count`.

**Warning signs:** `graph.invoke()` hangs indefinitely. In Phase 1 with stubs, this is the most likely reason for a hanging test.

### Pitfall 5: `review` Node Behavior in Phase 1

**What goes wrong:** In Phase 1, `review` is a stub that returns immediately. In Phase 4, it will contain `interrupt()`. If Phase 1 wires `review` → `revise` as a normal edge, and `revise` always increments `revision_count`, the graph will loop 3 times through revise (count: 0→1, 1→2, 2→3) and then exit to `save`. This is correct behavior for Phase 1 stubs.

**Why it matters:** Make sure the stub `revise_node` increments `revision_count` correctly so the Phase 1 loop terminates. Do not let `revise_node` return an empty dict — it must return `{"revision_count": count + 1}`.

**Warning signs:** Infinite loop if `revise_node` doesn't increment, or `revision_count` is always 0 because `state.get("revision_count", 0)` was not used.

---

## Code Examples

### Complete state.py

```python
# Source: STACK.md §Key API Patterns + verified against langgraph/graph/state.py
from __future__ import annotations
from typing import Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


class StructuredInfo(BaseModel):
    """Structured extraction of user's work description. Filled in Phase 2."""
    tasks: list[str] = Field(default_factory=list, description="Tasks worked on")
    outputs: list[str] = Field(default_factory=list, description="Outputs produced")
    blockers: list[str] = Field(default_factory=list, description="Blockers encountered")
    progress: str = Field(default="", description="Overall progress summary")


class AgentState(TypedDict, total=False):
    # The only field the caller is required to supply
    raw_input: str

    # Filled by extract node (Phase 2)
    structured_info: Optional[StructuredInfo]

    # Filled by route_template node (Phase 2)
    template_type: Optional[str]

    # Filled by draft node (Phase 2)
    draft: Optional[str]

    # Filled by polish node (Phase 2)
    polished: Optional[str]

    # Filled by review node after HITL interrupt (Phase 4)
    human_decision: Optional[str]   # Literal["approve", "revise", "edit"]
    human_feedback: Optional[str]

    # Incremented by revise node; guards the revise→review loop
    revision_count: int

    # Filled by enrich node (Phase 3)
    git_log: Optional[str]
    repo_path: Optional[str]

    # Filled by save node (Phase 5)
    final_report: Optional[str]
    export_path: Optional[str]
```

### Minimal smoke test script

```python
# scripts/test_skeleton.py — verifies all 4 success criteria
from workdiary_agent.graph import build_graph
from workdiary_agent.state import AgentState

def test_invoke_no_error():
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-1"}}
    result = graph.invoke({"raw_input": "test"}, config)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    print("PASS: invoke returns dict")

def test_all_nodes_present():
    graph = build_graph()
    node_names = set(graph.nodes.keys())
    required = {"extract", "enrich", "route_template", "draft",
                "polish", "review", "revise", "save"}
    missing = required - node_names
    assert not missing, f"Missing nodes: {missing}"
    print(f"PASS: all 8 nodes present: {sorted(node_names & required)}")

def test_conditional_edge_logic():
    # Directly test the routing function — no graph invocation needed
    from workdiary_agent.graph import route_after_revise
    assert route_after_revise({"revision_count": 0}) == "review"
    assert route_after_revise({"revision_count": 2}) == "review"
    assert route_after_revise({"revision_count": 3}) == "save"
    assert route_after_revise({"revision_count": 4}) == "save"
    assert route_after_revise({}) == "review"   # unset key → default 0
    print("PASS: conditional edge logic correct")

def test_agent_state_fields():
    from workdiary_agent.state import AgentState
    import typing
    hints = typing.get_type_hints(AgentState)
    required_fields = {
        "raw_input", "structured_info", "template_type", "draft",
        "polished", "human_decision", "human_feedback", "revision_count",
        "git_log", "repo_path", "final_report", "export_path"
    }
    missing = required_fields - set(hints.keys())
    assert not missing, f"AgentState missing fields: {missing}"
    print(f"PASS: AgentState has all {len(required_fields)} required fields")

if __name__ == "__main__":
    test_invoke_no_error()
    test_all_nodes_present()
    test_conditional_edge_logic()
    test_agent_state_fields()
    print("\nAll checks passed.")
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| langgraph 1.1.9 | Graph skeleton | No | — | None — must install |
| langgraph-checkpoint 4.0.2 | InMemorySaver | No | — | Auto-installed with langgraph |
| pydantic | StructuredInfo model | Yes (via conda base?) | TBD | None — required |
| Python 3.12 | All code | Yes | 3.12.13 | — |
| pytest | Test runner | Yes (in llm-data-pipeline) | — | Run scripts directly |

**Missing dependencies with no fallback:**
- `langgraph==1.1.9` — must be installed before any graph code can run. Wave 0 must include: `pip install "langgraph==1.1.9" "langchain-anthropic==1.4.1" "langgraph-checkpoint-sqlite==3.0.3" "streamlit==1.56.0" "gitpython==3.1.47"`

**Note on environment:** The project currently has only one conda environment (`llm-data-pipeline`, Python 3.12.13) and no `requirements.txt` for the WorkDiary Agent. Wave 0 should create one at `workdiary_agent/requirements.txt` or the project root.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5 (already in llm-data-pipeline conda env) |
| Config file | None — see Wave 0 |
| Quick run command | `conda run -n llm-data-pipeline python scripts/test_skeleton.py` |
| Full suite command | `conda run -n llm-data-pipeline pytest tests/test_graph_skeleton.py -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AGENT-01 | `raw_input` field exists in AgentState | unit | `pytest tests/test_graph_skeleton.py::test_agent_state_fields -x` | Wave 0 |
| SC-1 | `graph.invoke({"raw_input": "test"}, config)` returns dict | smoke | `pytest tests/test_graph_skeleton.py::test_invoke_no_error -x` | Wave 0 |
| SC-2 | All 8 node names present in graph | unit | `pytest tests/test_graph_skeleton.py::test_all_nodes_present -x` | Wave 0 |
| SC-3 | `revision_count >= 3` routes to save, else to review | unit | `pytest tests/test_graph_skeleton.py::test_conditional_edge_logic -x` | Wave 0 |
| SC-4 | AgentState defines all 12 required fields | unit | `pytest tests/test_graph_skeleton.py::test_agent_state_fields -x` | Wave 0 |

### How to Verify Each Success Criterion

**SC-1: invoke() runs without error and returns dict**
```python
graph = build_graph()
config = {"configurable": {"thread_id": "test-1"}}
result = graph.invoke({"raw_input": "test"}, config)
assert isinstance(result, dict)
```

**SC-2: All 8 node names present**
```python
node_names = set(build_graph().nodes.keys())
assert {"extract","enrich","route_template","draft","polish","review","revise","save"}.issubset(node_names)
```

**SC-3: Conditional edge logic — test the routing function directly**
```python
from workdiary_agent.graph import route_after_revise
assert route_after_revise({"revision_count": 2}) == "review"
assert route_after_revise({"revision_count": 3}) == "save"
assert route_after_revise({}) == "review"    # unset key defaults to 0
```

**SC-4: AgentState defines all required fields**
```python
import typing
hints = typing.get_type_hints(AgentState)
required = {"raw_input","structured_info","template_type","draft","polished",
            "human_decision","human_feedback","revision_count",
            "git_log","repo_path","final_report","export_path"}
assert not (required - set(hints.keys()))
```

### Sampling Rate

- **Per task commit:** `conda run -n llm-data-pipeline python scripts/test_skeleton.py`
- **Per wave merge:** `conda run -n llm-data-pipeline pytest tests/test_graph_skeleton.py -v`
- **Phase gate:** All 4 success criteria pass before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_graph_skeleton.py` — covers SC-1 through SC-4 and AGENT-01
- [ ] `scripts/test_skeleton.py` — standalone quick-check (no pytest dependency)
- [ ] `workdiary_agent/__init__.py` — package init
- [ ] `workdiary_agent/nodes/__init__.py` — re-exports all node functions
- [ ] Install: `pip install "langgraph==1.1.9" "langchain-anthropic==1.4.1" "langgraph-checkpoint-sqlite==3.0.3" "streamlit==1.56.0" "gitpython==3.1.47"`

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `MemorySaver` (canonical name) | `InMemorySaver` (canonical); `MemorySaver` is alias | langgraph-checkpoint 4.x | Use `from langgraph.checkpoint.memory import InMemorySaver`; `MemorySaver` still works but is an alias |
| `compile(interrupt_before=["node"])` | `interrupt()` inside node body | LangGraph 1.x | Compile-level interrupt still supported but in-node `interrupt()` gives more control; Phase 4 uses in-node |
| `set_entry_point("node")` | `add_edge(START, "node")` | LangGraph 1.x | `set_entry_point` is a thin wrapper, still works but `add_edge(START, ...)` is idiomatic 1.x |
| `workflow.compile()` (no checkpointer) | `builder.compile(checkpointer=InMemorySaver())` | Phase 1 design decision | Without checkpointer, `interrupt()` in Phase 4 will not work; add checkpointer from the start |

**Deprecated/outdated:**
- `interrupt_before=["review"]` compile parameter: still works in 1.1.9 (confirmed in `compile()` signature), but the project uses in-node `interrupt()` (D-08/STATE.md decision). Phase 1 does NOT use `interrupt_before`.
- `MemorySaver` as canonical name: replaced by `InMemorySaver` in langgraph-checkpoint 4.x. Alias preserved at source line 530.

---

## Open Questions

1. **`total=False` vs explicit `NotRequired` for AgentState defaults**
   - What we know: `total=False` makes all keys optional; `revision_count` defaults to 0 via `.get()` in routing function
   - What's unclear: Whether LangGraph's internal state merge expects any keys to be always-present vs. optional
   - Recommendation: Use `total=False` for all fields except `raw_input`. Validate by running the smoke test — if LangGraph raises on missing keys internally, switch to providing explicit defaults in a Wave 0 initialization helper.

2. **`interrupt_before` parameter in Phase 1**
   - What we know: STATE.md says final architecture uses `interrupt_before=["review"]` at compile time. CONTEXT.md D-07/D-08 says Phase 1 uses plain `MemorySaver` with no interrupt.
   - What's unclear: Whether to include `interrupt_before=["review"]` in Phase 1's compile call as a forward-compatibility stub.
   - Recommendation: Do NOT include `interrupt_before` in Phase 1. The Phase 1 success criteria only require `invoke()` to return a dict without error. Adding `interrupt_before` would cause Phase 1's test to see an interrupted graph (pausing before `review`), making SC-1 fail in its current form. Add it in Phase 4.

3. **`workdiary_agent` package Python environment**
   - What we know: Only `llm-data-pipeline` conda env exists; langgraph is not installed there.
   - What's unclear: Whether to install into `llm-data-pipeline` or create a new dedicated env.
   - Recommendation: Install into `llm-data-pipeline` for simplicity — it's Python 3.12.13 which is compatible with all required packages. Planner should include an explicit install task in Wave 0.

---

## Project Constraints (from CLAUDE.md)

| Constraint | Source | Applies to Phase 1? |
|------------|--------|---------------------|
| Use Python + LangGraph + Claude API (claude-sonnet-4-5) + Streamlit + SQLite | CLAUDE.md §Constraints | Yes — LangGraph stack |
| Timeline: one week, strict scope control, no gold-plating | CLAUDE.md §Constraints | Yes — stubs only, no LLM calls |
| LLM: Anthropic Claude API — local env already configured | CLAUDE.md §Constraints | No LLM calls in Phase 1 |
| GSD workflow: use `/gsd:execute-phase`, not direct file edits | CLAUDE.md §GSD Workflow | Yes — all edits via planned tasks |
| CLAUDE.md has complete stack version table — do NOT re-research | CLAUDE.md §Technology Stack | Honored — versions taken from STACK.md |
| Do not install `langchain` full package | CLAUDE.md §Technology Stack §What NOT to Use | Wave 0 install must use `langchain-anthropic`, not `langchain` |

---

## Sources

### Primary (HIGH confidence)

- `/tmp/lg_src/langgraph/graph/state.py` — Source-verified: `StateGraph.__init__`, `add_node` overloads (lines 293–495, 430–495), `add_edge` (lines 788–840), `add_conditional_edges` (lines 842–890), `compile` signature (lines 1038–1048), `validate` (lines 989–1028)
- `/tmp/lgcp_src/langgraph/checkpoint/memory/__init__.py` — Source-verified: `InMemorySaver` class (line 31), `MemorySaver` alias (line 530)
- `/tmp/lg_src/langgraph/graph/__init__.py` — Source-verified: `StateGraph`, `START`, `END`, `add_messages` exports
- `.planning/research/STACK.md` — Project-locked versions and API patterns
- `.planning/phases/01-graph-skeleton/01-CONTEXT.md` — All locked decisions (D-01 through D-09)

### Secondary (MEDIUM confidence)

- `/Users/maxinyue09/Downloads/projects/项目/桌面动物园/agent/graph.py` — Working LangGraph graph.py from existing project (confirms `add_node`, `add_conditional_edges`, `add_edge`, `set_entry_point` patterns, though may use 0.x style)
- `/Users/maxinyue09/Downloads/projects/项目/桌面动物园/agent/state.py` — Confirms `TypedDict` + `Annotated[Sequence[BaseMessage], operator.add]` pattern for reducers

### Tertiary (LOW confidence)

None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions from STACK.md, verified against extracted wheels
- Architecture patterns: HIGH — `add_node`, `add_edge`, `add_conditional_edges`, `compile` signatures source-verified from langgraph-1.1.9 wheel
- `InMemorySaver`/`MemorySaver` naming: HIGH — line 530 of langgraph-checkpoint source confirmed alias
- TypedDict `total=False` pitfall: HIGH — Python type system behavior, confirmed by state accessor patterns
- Pitfalls: HIGH for P1–P4 (verified from source), MEDIUM for P5 (behavior extrapolated from stub design)

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (langgraph 1.x stable; re-verify if langgraph version changes)
