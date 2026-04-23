# Technology Stack

**Project:** 智能日报 Agent (WorkDiary Agent)
**Researched:** 2026-04-22
**Verification method:** PyPI index queries, wheel extraction + source inspection, installed package introspection

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| langgraph | 1.1.9 | State machine, graph execution | Latest stable; 1.x is a major rewrite from 0.x with cleaner interrupt/Command API |
| langgraph-checkpoint | 4.0.2 | Checkpoint base classes (InMemorySaver) | Auto-installed by langgraph |
| langgraph-prebuilt | 1.0.10 | ToolNode, create_react_agent | Auto-installed by langgraph |
| langchain-core | 1.3.0 | Message types, Runnable protocol | Required by langgraph; provides HumanMessage, AIMessage, BaseMessage |

**Confidence: HIGH** — Versions verified directly from PyPI index; wheel contents inspected.

---

### LLM Integration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| langchain-anthropic | 1.4.1 | ChatAnthropic wrapper for LangGraph nodes | Required by langchain-anthropic 1.4.1: `anthropic>=0.96.0`. Bridges Anthropic SDK to LangChain Runnable protocol. Supports `with_structured_output`, `bind_tools`, tool_choice. |
| anthropic | 0.96.0 | Direct Claude API access (fallback / raw calls) | You have existing env config. langchain-anthropic 1.4.1 requires exactly `anthropic>=0.96.0`. |

**Model name to use:** `claude-sonnet-4-5` (alias that always resolves to latest claude-sonnet-4-5 snapshot) or `claude-sonnet-4-5-20250929` for pinned version. Both are valid in langchain-anthropic 1.4.1 `_profiles.py`. PROJECT.md says `claude-sonnet-4-5` — that's correct and verified.

**Confidence: HIGH** — Verified via `langchain_anthropic/data/_profiles.py` inspection. Both model IDs confirmed present with `tool_calling: True` and `structured_output: True`.

---

### Checkpointing & Persistence

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| langgraph-checkpoint-sqlite | 3.0.3 | SqliteSaver for graph state persistence | Uses stdlib sqlite3 + aiosqlite. Required deps: `aiosqlite>=0.20`, `sqlite-vec>=0.1.6`. Provides both sync `SqliteSaver` and async `AsyncSqliteSaver`. |
| aiosqlite | >=0.20 | Async SQLite driver for AsyncSqliteSaver | Pulled in by langgraph-checkpoint-sqlite. |

**Two distinct SQLite usages in this project:**

1. **LangGraph checkpoint SQLite** — managed by `SqliteSaver` from `langgraph.checkpoint.sqlite`. Stores graph execution state (for interrupt/resume). Use the context-manager pattern:
   ```python
   from langgraph.checkpoint.sqlite import SqliteSaver
   with SqliteSaver.from_conn_string("agent_checkpoints.sqlite") as checkpointer:
       graph = workflow.compile(checkpointer=checkpointer)
   ```

2. **Application history SQLite** — your own table for storing finished daily reports. Use stdlib `sqlite3` directly (no extra install). Keep it in a separate file from checkpoints.

**Confidence: HIGH** — SqliteSaver class verified from extracted wheel. `from_conn_string(path)` is the documented constructor.

---

### UI

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| streamlit | 1.56.0 | Web UI for input / display / confirm flow | Latest stable. `st.chat_message` and `st.chat_input` available since 1.23.0 — both present in 1.56.0. `st.session_state` for persisting graph state across rerenders. |

**Confidence: HIGH** — Version verified from PyPI index. Chat APIs stable since 1.23.0.

---

### Structured Output

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pydantic | 2.12.4 | Structured output from LLM nodes | langchain-anthropic 1.4.1 requires `pydantic>=2.7.4`. Use `BaseModel` + `Field` to define schemas, pass to `llm.with_structured_output(MyModel)`. LangGraph 1.1.9 requires `pydantic>=2.7.4`. |

**Confidence: HIGH** — Pydantic 2.12.4 installed and importable in active Python environment.

---

### Git Log Tool

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| gitpython | 3.1.47 | Read git commits for the optional context tool | Clean Python API. `Repo(path).iter_commits(since='1 day ago')` gives today's commits. Latest version 3.1.47 on PyPI. |

**Alternative:** `subprocess.run(["git", "log", "--oneline", "--since=1 day ago"], ...)` — zero dependency, simpler, but less structured. For a portfolio project showcasing tool use, GitPython's typed API reads better in code.

**Recommendation: Use GitPython.** The commit object gives you `.hexsha`, `.message`, `.author`, `.committed_date` as Python attributes — cleaner for wrapping as a LangGraph tool.

**Confidence: MEDIUM** — GitPython 3.1.47 confirmed on PyPI. API pattern based on training knowledge, not direct source inspection.

---

## Key API Patterns

### StateGraph (LangGraph 1.x)

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class DiaryState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    raw_input: str
    extracted_info: dict
    diary_type: str       # "tech" | "business" | "mixed"
    draft: str
    polished_draft: str
    user_feedback: str
    iteration_count: int
    final_output: str

builder = StateGraph(DiaryState)
builder.add_node("extract", extract_node)
builder.add_node("route_template", template_router_node)
builder.add_node("generate_draft", generate_draft_node)
builder.add_node("polish", polish_node)
builder.add_node("human_review", human_review_node)  # uses interrupt()
builder.add_node("revise", revise_node)

builder.add_edge(START, "extract")
# ... conditional edges ...
builder.add_edge("polish", "human_review")
```

**Note:** `set_entry_point("node")` still works in 1.1.9 (it's a wrapper for `add_edge(START, "node")`), but `add_edge(START, "node")` is the idiomatic 1.x style.

---

### Human-in-the-Loop (interrupt + Command)

The 1.x `interrupt()` pattern replaces the old `interrupt_before`/`interrupt_after` compile flags for mid-node interruption:

```python
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver  # renamed from MemorySaver

def human_review_node(state: DiaryState):
    # Execution pauses here; value sent to Streamlit UI
    user_response = interrupt({
        "draft": state["polished_draft"],
        "prompt": "Approve, revise, or reject?"
    })
    return {"user_feedback": user_response}

# Compile requires a checkpointer for interrupt to work
checkpointer = InMemorySaver()  # or SqliteSaver for persistence
graph = builder.compile(checkpointer=checkpointer)

# Resume after human input
config = {"configurable": {"thread_id": "diary-session-1"}}
graph.invoke(initial_state, config)                    # runs until interrupt
graph.invoke(Command(resume="approve"), config)        # resumes
```

**Critical:** `InMemorySaver` is the current name in langgraph-checkpoint 4.x. `MemorySaver` still works (kept as alias at line 530 of source) but `InMemorySaver` is the canonical name.

**Confidence: HIGH** — Source-verified from extracted wheel. `interrupt()` function at line 705 of `langgraph/types.py`. `Command(resume=...)` at line 653.

---

### Structured Output from LLM Nodes

```python
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic

class DiaryType(BaseModel):
    type: str = Field(description="'tech', 'business', or 'mixed'")
    reasoning: str = Field(description="Why this type was chosen")

llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0)
structured_llm = llm.with_structured_output(DiaryType)

def template_router_node(state: DiaryState) -> dict:
    result: DiaryType = structured_llm.invoke([
        SystemMessage(content="Classify the work diary type..."),
        HumanMessage(content=state["raw_input"])
    ])
    return {"diary_type": result.type}
```

**Confidence: HIGH** — `with_structured_output` confirmed present in `langchain_anthropic/chat_models.py` line 1736. `structured_output: True` in claude-sonnet-4-5 profile.

---

### Streamlit Human-in-the-Loop Pattern

The core challenge: Streamlit reruns top-to-bottom on every interaction. LangGraph's blocked graph state must survive reruns.

```python
import streamlit as st
from langgraph.types import Command

# Store graph instance and thread_id in session_state (persists across reruns)
if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.pending_interrupt = None

config = {"configurable": {"thread_id": st.session_state.thread_id}}

# Initial invocation
if st.button("Generate Diary"):
    result = st.session_state.graph.invoke({"raw_input": user_text}, config)
    if "__interrupt__" in result:
        st.session_state.pending_interrupt = result["__interrupt__"]

# Render interrupt UI
if st.session_state.pending_interrupt:
    draft = st.session_state.pending_interrupt[0].value["draft"]
    st.markdown(draft)
    decision = st.radio("Action", ["approve", "revise"])
    if st.button("Submit"):
        st.session_state.graph.invoke(Command(resume=decision), config)
        st.session_state.pending_interrupt = None
```

**Key pattern:** store graph, thread_id, and pending interrupt in `st.session_state`. Use `st.chat_message` for message display in a chat-like layout.

**Confidence: MEDIUM** — Pattern based on training knowledge of Streamlit + LangGraph integration. The `__interrupt__` key in graph output is verified from source (line 775 in types.py docstring).

---

### Git Log Tool

```python
from langchain_core.tools import tool
import git

@tool
def read_git_log(repo_path: str, since_hours: int = 24) -> str:
    """Read today's git commits from a local repository.
    
    Args:
        repo_path: Absolute path to the git repository
        since_hours: How many hours back to look (default 24)
    
    Returns:
        Formatted string of commits with hash, message, and author
    """
    try:
        repo = git.Repo(repo_path)
        commits = list(repo.iter_commits(
            'HEAD',
            since=f'{since_hours} hours ago'
        ))
        if not commits:
            return "No commits found in the specified time range."
        lines = [
            f"- {c.hexsha[:7]} {c.message.strip()} ({c.author.name})"
            for c in commits
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Error reading git log: {e}"
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| LLM wrapper | langchain-anthropic + ChatAnthropic | anthropic SDK directly | Direct SDK bypasses LangChain Runnable protocol; LangGraph nodes expect Runnable-compatible LLMs for `bind_tools`, `with_structured_output`. Would require custom adapter. |
| State type | TypedDict | Pydantic BaseModel for state | TypedDict is simpler, has less overhead, and works perfectly with LangGraph's type reducers (Annotated). Pydantic state is supported but adds complexity without benefit for this project scope. |
| Checkpointer (HITL) | InMemorySaver (dev) / SqliteSaver (prod) | PostgreSQL via langgraph-checkpoint-postgres | SQLite is zero-infrastructure and sufficient for single-user desktop tool. Postgres adds ops complexity. |
| Git reading | GitPython | subprocess.run(["git", "log"]) | GitPython provides typed commit objects; subprocess is simpler but returns raw strings requiring manual parsing. Both valid — GitPython preferred for clean demo code. |
| Interrupt pattern | `interrupt()` function (1.x style) | `interrupt_before=["node"]` on compile | Compile-level interrupts pause before the node runs; `interrupt()` inside a node gives you more control (pause mid-node, send context to UI). Better for this project's confirm flow. |
| UI | Streamlit | Gradio | Streamlit has better session_state management for stateful graph interactions. Both viable; Streamlit more widely understood in interviews. |
| LangChain full package | Not needed | langchain (the full package) | You only need langchain-core (message types, Runnable) and langchain-anthropic (Claude wrapper). The `langchain` meta-package pulls in ~40 extras you won't use. Install only what you need. |

---

## What NOT to Use and Why

### Do NOT install `langchain` (the full package)

`langchain==1.2.15` is a meta-package with heavy optional dependencies (SQL agents, document loaders, vector stores, etc.). This project needs only:
- `langchain-core` — message types and Runnable protocol
- `langchain-anthropic` — Claude wrapper

Installing the full `langchain` bloats the environment and creates version conflict surface area. The desktop pet's `requirements.txt` lists `langchain>=0.3.0` but that was for a different project with different needs.

### Do NOT use the old interrupt pattern

LangGraph 0.x used `compile(interrupt_before=["node_name"])` to pause execution. This still works in 1.x but is limited: you can't pause mid-node or send custom data to the UI. Use `interrupt(value)` inside the node instead.

### Do NOT use `MemorySaver` as the canonical name

`MemorySaver` is kept as a backwards-compatibility alias in langgraph-checkpoint 4.x (confirmed in source), but the class is now named `InMemorySaver`. Use `InMemorySaver` to avoid deprecation warnings in future versions.

### Do NOT call `graph.invoke()` directly in Streamlit without session_state management

Streamlit reruns the entire script on every widget interaction. If graph state isn't stored in `st.session_state`, you'll create a new graph instance on every rerun and lose the interrupted state. This is the #1 pitfall for LangGraph + Streamlit integrations.

---

## Installation

```bash
# Core LangGraph stack
pip install "langgraph==1.1.9"
# langgraph 1.1.9 auto-installs: langgraph-checkpoint>=2.1.0, langgraph-prebuilt>=1.0.9, langchain-core>=1.3.0

# Claude integration
pip install "langchain-anthropic==1.4.1"
# langchain-anthropic 1.4.1 auto-installs: anthropic>=0.96.0

# SQLite checkpointing (for graph interrupt/resume persistence)
pip install "langgraph-checkpoint-sqlite==3.0.3"
# auto-installs: aiosqlite>=0.20, sqlite-vec>=0.1.6

# UI
pip install "streamlit==1.56.0"

# Structured output
# pydantic 2.12.4 already satisfied by langgraph requirements

# Git tool
pip install "gitpython==3.1.47"
```

**Minimal requirements.txt:**
```
langgraph==1.1.9
langchain-anthropic==1.4.1
langgraph-checkpoint-sqlite==3.0.3
streamlit==1.56.0
gitpython==3.1.47
```

---

## Sources

- PyPI index (live query via `pip3 index versions`): langgraph 1.1.9, anthropic 0.96.0, streamlit 1.56.0, langchain-anthropic 1.4.1, langgraph-checkpoint-sqlite 3.0.3, gitpython 3.1.47 — HIGH confidence
- `langgraph-1.1.9-py3-none-any.whl` extracted and inspected: `langgraph/types.py` (interrupt, Command), `langgraph/graph/__init__.py` (StateGraph, END, START), `langgraph/graph/state.py` (compile signature), `langgraph/graph/message.py` (MessagesState, add_messages) — HIGH confidence
- `langgraph-checkpoint-4.0.2-py3-none-any.whl` extracted: `langgraph/checkpoint/memory/__init__.py` (InMemorySaver) — HIGH confidence
- `langgraph-checkpoint-sqlite-3.0.3-py3-none-any.whl` extracted: `langgraph/checkpoint/sqlite/__init__.py` (SqliteSaver, from_conn_string) — HIGH confidence
- `langchain_anthropic-1.4.1-py3-none-any.whl` extracted: `chat_models.py` (ChatAnthropic, with_structured_output), `data/_profiles.py` (claude-sonnet-4-5 model ID, capabilities) — HIGH confidence
- METADATA files for all packages: confirmed dependency version constraints — HIGH confidence
- Existing `桌面动物园/agent/` code: confirmed working patterns for TypedDict state, ChatAnthropic usage, graph.compile() — MEDIUM confidence (working code but may be 0.x patterns)
