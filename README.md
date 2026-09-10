# WorkDiary Agent

A LangGraph-based workflow that turns rough work notes into a polished, manager-friendly daily report with evidence-aware Git enrichment and explicit human approval.

The agent structures your input, pulls in today's git commits as context, selects (or lets you choose) a report template, drafts and refines the content from a manager's perspective, then pauses for your review. You can accept, edit, or request revisions (up to 3 rounds) before the report is saved and exported as a markdown file. Interrupted runs remain recoverable from their LangGraph checkpoints.

Built as a portfolio project demonstrating: LangGraph state machine design, Human-in-the-Loop interrupt/resume with SQLite persistence, multi-node Pydantic structured outputs, and Streamlit UI integration.

---

## Demo

```
User input: "今天修了个 bug，跑了个数据，开了两个会"

→ extract:  { tasks: ["修复登录bug"], outputs: ["数据报告"], blockers: [] }
→ enrich:   git log pulled: "fix(auth): resolve token expiry edge case"
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
2. Optionally paste a git repo path and author/email to pull in only your commits from the configured work-day timezone
3. Optionally paste raw data/metrics for the agent to extract and include
4. Click **生成日报** — the agent runs through all nodes and pauses for your review
5. Read the draft, edit inline if needed, then **接受** or **修改**（up to 3 applied revision rounds; final save always requires approval）
6. The final report is saved to history and exported as a markdown file in `exports/`
7. Past reports appear in the **历史记录** sidebar tab
8. If generation is interrupted or the browser closes during review, reopen it from **恢复未完成日报**

### Privacy and trust boundaries

- Work notes, pasted metrics, and selected Git commit subjects are sent to the configured LLM provider. Common credential formats are redacted before model calls, but this is best-effort; do not submit data your provider is not allowed to process. The original input remains stored locally in history after approval.
- Git enrichment skips commit collection when it cannot resolve an explicit author/email or the repository's local `user.email` / `user.name`; it never attributes every contributor's commits to you.
- User text and repository-derived text are delimited as untrusted source data in prompts. This reduces prompt-injection risk but is not a complete security boundary.
- Repository paths are read from the machine running Streamlit. Keep the app local or add deployment-level access controls before exposing it to other users.

---

## How It Works

```
User input
    │
    ▼
extract ── structured extraction (tasks / outputs / blockers / progress)
    │
    ▼
enrich ── git log (today's commits) + LLM extraction of data metrics
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
| Stable data directory | `WORKDIARY_DATA_DIR` can place both databases and exports on a durable volume independent of the launch directory |

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
│   ├── recovery.py         # Discover incomplete checkpoint threads
│   ├── time_utils.py       # Shared work-day timezone calculation
│   ├── paths.py            # Stable runtime database/export paths
│   ├── redaction.py        # Best-effort secret redaction before LLM calls
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
