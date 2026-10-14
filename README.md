# WorkDiary Agent

A LangGraph-based workflow that turns rough work notes into a polished, manager-friendly daily report with evidence-aware Git enrichment and explicit human approval.

The agent freezes your input and the report day's selected Git commits, structures the material, selects (or lets you choose) a report template, drafts and refines the content from a manager's perspective, then pauses for your review. You can accept, edit, or request revisions (up to 3 rounds) before the report and its source snapshot are saved; the report is also exported as a markdown file. Interrupted runs remain recoverable from their LangGraph checkpoints.

Built as a portfolio project demonstrating: LangGraph state machine design, Human-in-the-Loop interrupt/resume with SQLite persistence, multi-node Pydantic structured outputs, and Streamlit UI integration.

---

## Demo

```
User input: "今天修了个 bug，跑了个数据，开了两个会"

→ capture:  work notes, pasted metrics, and selected Git commits frozen locally
→ extract:  { tasks: ["修复登录bug"], outputs: ["数据报告"], blockers: [] }
→ enrich:   reuse frozen Git; extract a metric summary from the pasted data
→ template: 技术型
→ draft:    structured first draft
→ polish:   "完成登录模块 Token 过期边界问题修复..."

[HITL pause — user reviews in Streamlit]

User: "突出这是登录稳定性修复，不要添加未提供的数据"
→ revise → polish (round 2)

User: approve

→ saved to history.db
→ exported to exports/daily_report_2026-05-06_<report-id>.md
```

---

## Prerequisites

- **Python 3.10+**
- **An LLM API key** — pick one backend:
  - SiliconFlow (domestic, free credits, recommended for China) — https://cloud.siliconflow.cn/
  - Official OpenAI or another OpenAI-compatible provider
  - Anthropic (direct API key or corporate proxy)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/xyma2003/workdiary-agent.git
cd workdiary-agent
```

### 2. Create a virtual environment

```bash
# Option A: venv
python3 -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

# Option B: conda
conda create -n workdiary python=3.10
conda activate workdiary
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API credentials

The app supports **SiliconFlow**, **official OpenAI**, other **OpenAI-compatible** providers, and **Anthropic**. Provider-specific keys are intentionally separated so an official OpenAI key is never sent to a third-party endpoint by default.

**Option A — SiliconFlow / OpenAI-compatible (default, recommended for domestic use):**

```bash
# .env
LLM_PROVIDER=siliconflow
SILICONFLOW_API_KEY=sk-...
SILICONFLOW_MODEL=Qwen/Qwen3-32B
WORKDIARY_TIMEZONE=Asia/Shanghai
# Optional for deployments or when launching outside the repository directory
# WORKDIARY_DATA_DIR=/absolute/path/to/workdiary-data
```

Get a SiliconFlow key at https://cloud.siliconflow.cn/. See `.env.example` for all provider configurations.

**Option B — Official OpenAI:**

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

**Option C — Direct Anthropic API key:**

```bash
# .env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
```

**Option D — Corporate/internal proxy:**

```bash
# .env
LLM_PROVIDER=anthropic
ANTHROPIC_BASE_URL=https://your-proxy-base-url
ANTHROPIC_AUTH_TOKEN=your-auth-token
# Optional: extra headers required by your proxy, newline-separated "Key: Value" pairs
ANTHROPIC_CUSTOM_HEADERS=X-Custom-Header: value
```

> The app auto-loads `.env` via `python-dotenv`. Existing deployment or shell variables take precedence over the local file.

### 5. Run

```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## Usage

1. Enter a rough description of your day (口语化输入, any style) and optionally choose a template instead of automatic routing
2. Optionally paste a git repo path and author/email to pull in only your exact-identity commits from the report date in the configured timezone
3. Optionally paste raw data/metrics for the agent to extract and include
4. Click **生成日报** — the agent runs through all nodes and pauses for your review
5. Read the draft and its deterministic fact warnings, edit inline if needed, then **接受** or **修改**（number warnings require acknowledgement; potential credentials must be removed; final save always requires approval）
6. The final report is saved to history and exported as a markdown file in `exports/`
7. Past reports appear in the **历史记录** sidebar tab, with content search, template/date filters, pagination, editing, and confirmed deletion
8. If generation is interrupted or the browser closes during review, reopen it from **恢复未完成日报**

Deleting a saved report removes its history row first and attempts to clean up its
managed Markdown export. If cleanup fails, the page shows a partial-success
warning and a **待清理导出 → 重试清理** action. Pending tasks are stored in
`history.db`, so they remain available after a refresh or restart, even when no
reports remain. Missing files count as already cleaned up. Files outside the export
directory, paths containing symlinks, and exports still used by another report are
preserved with an explicit notice.

### Privacy and trust boundaries

- Work notes, pasted metrics, and selected Git commit subjects are sent to the configured LLM provider. Common credential formats are redacted in new source snapshots and before model calls, but this is best-effort; do not submit data your provider is not allowed to process. History and unfinished checkpoints are local files and may contain sensitive work material, including earlier inputs or subsequent edits.
- Git enrichment skips commit collection when it cannot resolve an explicit author/email or the repository's local `user.email` / `user.name`; it never attributes every contributor's commits to you.
- User text and repository-derived text are delimited as untrusted source data in prompts. This reduces prompt-injection risk but is not a complete security boundary.
- Repository paths are read from the machine running Streamlit. Keep the app local or add deployment-level access controls before exposing it to other users.

### Review against the original material

Before accepting a report, **原始材料** and **待审日报** appear side by side.
The source panel shows the frozen work description, pasted metric text and Git
commit subjects; long sources scroll independently. You can edit the report,
request a revision or download the current text while checking those sources.
The new-report form is collapsed during review so the active report stays in view.

**模型提炼的指标摘要（非原始证据）** is a separate, labeled section. Fact warnings
use the same frozen original sources shown in the panel, not the model's summary
or changes to the new-report form. These checks flag possible issues; they do not
prove factual correctness. A new report edit resets any warning acknowledgement.
When resuming an older task without a source snapshot, the app labels its remaining
checkpoint material as incomplete instead of reading today's repository.

### Inspect a saved report's sources

In **历史记录**, expand **生成时的来源快照** to compare the original material with
the currently saved report. You can inspect the work description and raw pasted
metrics used for generation, the selected Git commit subjects, and the resolved
author/date/timezone filters. The snapshot is checkpointed before
the first model stage: later Git changes or a retry after a model failure do not
silently replace those sources. A missing/unavailable Git result is recorded as
such; the snapshot is not a backup of repository files or the entire commit history.

The same view shows provider/model configuration for clients created in each
successfully completed generation stage, including both router calls and later
revision passes. It does not claim the provider actually served a particular
model revision, or record every failed request/retry. API keys and request headers
are excluded; endpoint identifiers retain only the origin, without user info,
paths, queries or fragments. Model-derived metric summaries are not presented as
raw evidence.

The snapshot is stored once alongside the approved report in `history.db`.
Editing the report, its date or its editable input preserves that original
snapshot. Markdown exports continue to contain only the report. Older reports
and tasks without capture data show **来源未保存**; the app never reconstructs
their historical evidence from the current environment or repository. Unreadable
or unsupported snapshots show a notice while the report remains usable.

---

## How It Works

```
User input
    │
    ▼
capture_sources ── freeze input + selected Git context in a checkpoint
    │
    ▼
extract ── structured extraction (tasks / outputs / blockers / progress)
    │
    ▼
enrich ── reuse frozen Git + LLM extraction of data metrics
    │
    ▼
route_template ── TemplateRouterAgent subgraph (技术型 / 业务型 / 混合型)
    │
    ▼
draft ── template-specific first draft
    │
    ▼
polish ── rewrite from manager's perspective, emphasise outcomes
    │
    ▼
review ── interrupt() → Streamlit HITL pause
    │
  ┌─┴──────────────┐
approve           revise (up to 3×)
  │                 │
save            revise_node → polish (loop)
  │
exports/ + history.db
```

**Key design decisions:**

| Decision | Rationale |
|----------|-----------|
| "Manager's perspective" as a separate polish node | Decouples tone/framing from content generation; polish can be reused across templates |
| TemplateRouterAgent as a subgraph | Keeps classification state isolated from the main graph; accuracy still requires evaluation |
| interrupt() inside review node | Gives fine-grained control (pause mid-node with context payload); more flexible than compile-level `interrupt_before` |
| Two SQLite files | `graph_state.db` is owned exclusively by LangGraph's SqliteSaver; mixing app data into it breaks serialisation |
| Revision limit (3×) | Applies all three revisions, then disables further model revisions while preserving manual edit and explicit approval |
| Checkpoint recovery | Incomplete graph threads are discovered directly from the LangGraph checkpointer; retry and review use the same persisted state |
| Checkpoint lifecycle | Completed UI runs remove their graph checkpoints after the approved report is persisted; unfinished runs remain recoverable |
| Stable data directory | `WORKDIARY_DATA_DIR` can place both databases and exports on a durable volume independent of the launch directory |
| Pre-save fact warnings | Checks compare the report and model-derived metric summary against original input/Git/data, require acknowledgement, and block likely credentials |
| Synchronized CRUD | Saved-report edits update SQLite and the Markdown export together; deletion is confirmed and restricted to managed export paths |
| Immutable source snapshot | Freeze sources before model work and retain them after editing; older records remain explicitly unknown |

---

## Project Structure

```
workdiary-agent/
├── app.py                  # Streamlit UI — generation page + history page
├── pyproject.toml          # Package metadata, dependencies, pytest markers
├── .github/workflows/      # Offline test CI
├── evals/                  # Labeled AI-quality evaluation cases
├── requirements.txt
├── workdiary_agent/
│   ├── graph.py            # StateGraph assembly, conditional edges, checkpointer init
│   ├── state.py            # AgentState TypedDict + StructuredInfo Pydantic model
│   ├── source_snapshot.py  # Frozen source evidence and credential-free metadata
│   ├── recovery.py         # Discover incomplete checkpoint threads
│   ├── time_utils.py       # Shared work-day timezone calculation
│   ├── paths.py            # Stable runtime database/export paths
│   ├── redaction.py        # Best-effort secret redaction before LLM calls
│   ├── quality.py          # Deterministic pre-save factual-risk checks
│   ├── report_service.py   # Coordinated history update/delete + export sync
│   ├── utils.py            # make_llm() factory + validate_repo_path()
│   ├── nodes/
│   │   ├── extract.py      # Structured extraction via with_structured_output
│   │   ├── enrich.py       # Git log reader + LLM metric extraction
│   │   ├── route_template.py  # Calls TemplateRouterAgent subgraph
│   │   ├── draft.py        # Template-specific first draft (3 templates)
│   │   ├── polish.py       # Manager-perspective rewrite (accepts revision feedback)
│   │   ├── review.py       # HITL interrupt node
│   │   ├── revise.py       # Increments revision_count
│   │   └── save.py         # Persist to history.db + export markdown
│   ├── router/
│   │   └── agent.py        # TemplateRouterAgent subgraph (analyse → decide)
│   └── storage/
│       ├── sqlite.py       # history.db read/write API
│       └── export.py       # Markdown file export to exports/
├── scripts/                # Manual integration test scripts
│   ├── test_hitl_cycle.py
│   ├── test_skeleton.py
│   └── evaluate_router.py  # Live routing accuracy/latency benchmark
├── tests/                  # pytest unit tests (5 phases)
│   ├── test_graph_skeleton.py
│   ├── test_phase02_llm_nodes.py
│   ├── test_phase03_enrichment.py
│   ├── test_phase04_hitl.py
│   └── test_phase05_storage.py
└── exports/                # Auto-created; exported markdown reports
```

---

## Running Tests

```bash
# Offline unit/integration tests (no API key or model cost)
python -m pytest tests/ -m "not integration" -v

# Live provider checks (requires a configured .env and incurs model calls)
python -m pytest tests/ -m integration -v

# Labeled router benchmark; the router makes two model calls per case
python scripts/evaluate_router.py --limit 3
python scripts/evaluate_router.py --output eval-results/router.json
```

The routing dataset contains 30 balanced cases across the three templates.
Do not claim an accuracy number until the benchmark has been run against the
specific provider/model being discussed and the boundary labels have been reviewed.

---

## Tech Stack

| Component | Library | Version |
|-----------|---------|---------|
| Agent orchestration | LangGraph | 1.1.9 |
| LLM (default) | SiliconFlow / OpenAI-compatible via langchain-openai | — |
| LLM (alt) | Claude via langchain-anthropic | 1.4.1 |
| Structured outputs | Pydantic | 2.x |
| HITL persistence | SQLite (langgraph-checkpoint-sqlite) | 3.0.3 |
| UI | Streamlit | 1.x |
| Git context | GitPython | 3.1.47 |

---

## Resume Bullet

> *Built a LangGraph agent that converts unstructured daily work notes into polished manager-facing reports, featuring a Human-in-the-Loop review loop with full state persistence across Streamlit reruns, a two-step template classification subgraph, and git commit enrichment. (LangGraph · Claude API · Pydantic · Streamlit · SQLite)*
