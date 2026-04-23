<!-- GSD:project-start source:PROJECT.md -->
## Project

**智能日报 Agent (WorkDiary Agent)**

一个基于 LangGraph 的智能日报生成 Agent，帮助用户将每天碎片化、口语化的工作描述，转化为结构清晰、突出业务价值的"老板爱看"日报。系统通过多节点状态机处理输入、自动识别日报类型、润色改写，并支持人工确认循环，最终导出为 markdown 文件并存储历史记录。

**Core Value:** 用户输入一段口语化的工作描述，Agent 能自动生成一份老板视角的专业日报，让用户5分钟内完成每日汇报。

### Constraints

- **Tech Stack**: Python + LangGraph + Claude API (claude-sonnet-4-5) + Streamlit + SQLite — 已确定，不考虑替代方案
- **Timeline**: 一周内完成 — 功能范围需严格控制，不做镀金
- **LLM**: Anthropic Claude API — 用户本地已有环境配置
- **UI**: Streamlit — 快速原型，无需复杂前端
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| langgraph | 1.1.9 | State machine, graph execution | Latest stable; 1.x is a major rewrite from 0.x with cleaner interrupt/Command API |
| langgraph-checkpoint | 4.0.2 | Checkpoint base classes (InMemorySaver) | Auto-installed by langgraph |
| langgraph-prebuilt | 1.0.10 | ToolNode, create_react_agent | Auto-installed by langgraph |
| langchain-core | 1.3.0 | Message types, Runnable protocol | Required by langgraph; provides HumanMessage, AIMessage, BaseMessage |
### LLM Integration
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| langchain-anthropic | 1.4.1 | ChatAnthropic wrapper for LangGraph nodes | Required by langchain-anthropic 1.4.1: `anthropic>=0.96.0`. Bridges Anthropic SDK to LangChain Runnable protocol. Supports `with_structured_output`, `bind_tools`, tool_choice. |
| anthropic | 0.96.0 | Direct Claude API access (fallback / raw calls) | You have existing env config. langchain-anthropic 1.4.1 requires exactly `anthropic>=0.96.0`. |
### Checkpointing & Persistence
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| langgraph-checkpoint-sqlite | 3.0.3 | SqliteSaver for graph state persistence | Uses stdlib sqlite3 + aiosqlite. Required deps: `aiosqlite>=0.20`, `sqlite-vec>=0.1.6`. Provides both sync `SqliteSaver` and async `AsyncSqliteSaver`. |
| aiosqlite | >=0.20 | Async SQLite driver for AsyncSqliteSaver | Pulled in by langgraph-checkpoint-sqlite. |
### UI
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| streamlit | 1.56.0 | Web UI for input / display / confirm flow | Latest stable. `st.chat_message` and `st.chat_input` available since 1.23.0 — both present in 1.56.0. `st.session_state` for persisting graph state across rerenders. |
### Structured Output
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| pydantic | 2.12.4 | Structured output from LLM nodes | langchain-anthropic 1.4.1 requires `pydantic>=2.7.4`. Use `BaseModel` + `Field` to define schemas, pass to `llm.with_structured_output(MyModel)`. LangGraph 1.1.9 requires `pydantic>=2.7.4`. |
### Git Log Tool
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| gitpython | 3.1.47 | Read git commits for the optional context tool | Clean Python API. `Repo(path).iter_commits(since='1 day ago')` gives today's commits. Latest version 3.1.47 on PyPI. |
## Key API Patterns
### StateGraph (LangGraph 1.x)
# ... conditional edges ...
### Human-in-the-Loop (interrupt + Command)
# Compile requires a checkpointer for interrupt to work
# Resume after human input
### Structured Output from LLM Nodes
### Streamlit Human-in-the-Loop Pattern
# Store graph instance and thread_id in session_state (persists across reruns)
# Initial invocation
# Render interrupt UI
### Git Log Tool
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
## What NOT to Use and Why
### Do NOT install `langchain` (the full package)
- `langchain-core` — message types and Runnable protocol
- `langchain-anthropic` — Claude wrapper
### Do NOT use the old interrupt pattern
### Do NOT use `MemorySaver` as the canonical name
### Do NOT call `graph.invoke()` directly in Streamlit without session_state management
## Installation
# Core LangGraph stack
# langgraph 1.1.9 auto-installs: langgraph-checkpoint>=2.1.0, langgraph-prebuilt>=1.0.9, langchain-core>=1.3.0
# Claude integration
# langchain-anthropic 1.4.1 auto-installs: anthropic>=0.96.0
# SQLite checkpointing (for graph interrupt/resume persistence)
# auto-installs: aiosqlite>=0.20, sqlite-vec>=0.1.6
# UI
# Structured output
# pydantic 2.12.4 already satisfied by langgraph requirements
# Git tool
## Sources
- PyPI index (live query via `pip3 index versions`): langgraph 1.1.9, anthropic 0.96.0, streamlit 1.56.0, langchain-anthropic 1.4.1, langgraph-checkpoint-sqlite 3.0.3, gitpython 3.1.47 — HIGH confidence
- `langgraph-1.1.9-py3-none-any.whl` extracted and inspected: `langgraph/types.py` (interrupt, Command), `langgraph/graph/__init__.py` (StateGraph, END, START), `langgraph/graph/state.py` (compile signature), `langgraph/graph/message.py` (MessagesState, add_messages) — HIGH confidence
- `langgraph-checkpoint-4.0.2-py3-none-any.whl` extracted: `langgraph/checkpoint/memory/__init__.py` (InMemorySaver) — HIGH confidence
- `langgraph-checkpoint-sqlite-3.0.3-py3-none-any.whl` extracted: `langgraph/checkpoint/sqlite/__init__.py` (SqliteSaver, from_conn_string) — HIGH confidence
- `langchain_anthropic-1.4.1-py3-none-any.whl` extracted: `chat_models.py` (ChatAnthropic, with_structured_output), `data/_profiles.py` (claude-sonnet-4-5 model ID, capabilities) — HIGH confidence
- METADATA files for all packages: confirmed dependency version constraints — HIGH confidence
- Existing `桌面动物园/agent/` code: confirmed working patterns for TypedDict state, ChatAnthropic usage, graph.compile() — MEDIUM confidence (working code but may be 0.x patterns)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
