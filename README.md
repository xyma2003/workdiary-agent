# WorkDiary Agent

A LangGraph-based multi-node agent that turns a rough, spoken-style work description into a polished, manager-friendly daily report — in under 5 minutes.

The agent structures your input, pulls in today's git commits as context, selects the right report template, drafts and refines the content from a manager's perspective, then pauses for your review. You can accept, edit, or request revisions (up to 3 rounds) before the report is saved and exported as a markdown file.

Built as a portfolio project demonstrating: LangGraph state machine design, Human-in-the-Loop interrupt/resume with SQLite persistence, multi-node Pydantic structured outputs, and Streamlit UI integration.

---

## Demo

```
User input: "今天修了个 bug，跑了个数据，开了两个会"

→ extract:  { tasks: ["修复登录bug"], outputs: ["数据报告"], blockers: [] }
→ enrich:   git log pulled: "fix(auth): resolve token expiry edge case"
→ template: 技术型
→ draft:    structured first draft
→ polish:   "修复登录模块 Token 过期边界问题，影响约 3% DAU 的登录成功率..."

[HITL pause — user reviews in Streamlit]

User: "加上数据影响的百分比"
→ revise → polish (round 2)

User: approve

→ saved to history.db
→ exported to exports/daily_report_2026-05-06.md
```

---

## Prerequisites

- **Python 3.10+**
- **Anthropic API access** — either a direct API key or a corporate proxy (see below)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/workdiary-agent.git
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

**Option A — Direct Anthropic API key (standard):**

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

Or create a `.env` file and load it:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

**Option B — Corporate/internal proxy:**

```bash
# .env
ANTHROPIC_BASE_URL=https://your-proxy-base-url
ANTHROPIC_AUTH_TOKEN=your-auth-token
# Optional: extra headers required by your proxy, newline-separated "Key: Value" pairs
ANTHROPIC_CUSTOM_HEADERS=X-Custom-Header: value
```

> `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` are picked up automatically by the Anthropic SDK. `ANTHROPIC_CUSTOM_HEADERS` is parsed by `make_llm()` in `utils.py` and passed as `default_headers` to `ChatAnthropic`. No `ANTHROPIC_API_KEY` is needed for Option B.

Load the `.env` file before running:

```bash
export $(grep -v '^#' .env | xargs)
```

### 5. Run

```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## Usage

1. Enter a rough description of your day (口语化输入, any style)
2. Optionally paste a git repo path to pull in today's commits as context
3. Optionally paste raw data/metrics for the agent to extract and include
4. Click **生成日报** — the agent runs through all nodes and pauses for your review
5. Read the draft, edit inline if needed, then **接受** or **修改**（up to 3 revision rounds）
6. The final report is saved to history and exported as a markdown file in `exports/`
7. Past reports appear in the **历史记录** sidebar tab

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
| TemplateRouterAgent as a subgraph | Two-step chain-of-thought (analyse → decide) improves classification accuracy; fully isolated from main graph |
| interrupt() inside review node | Gives fine-grained control (pause mid-node with context payload); more flexible than compile-level `interrupt_before` |
| Two SQLite files | `graph_state.db` is owned exclusively by LangGraph's SqliteSaver; mixing app data into it breaks serialisation |
| Revision limit (3×) | Prevents infinite HITL loop; enforced by three independent guards (safe field access, conditional edge, approve shortcut) |

---

## Project Structure

```
workdiary_agent/
├── app.py                  # Streamlit UI — generation page + history page
├── graph.py                # StateGraph assembly, conditional edges, checkpointer init
├── state.py                # AgentState TypedDict + StructuredInfo Pydantic model
├── utils.py                # make_llm() factory + validate_repo_path()
├── requirements.txt
├── nodes/
│   ├── extract.py          # Structured extraction via with_structured_output
│   ├── enrich.py           # Git log reader + LLM metric extraction
│   ├── route_template.py   # Calls TemplateRouterAgent subgraph
│   ├── draft.py            # Template-specific first draft (3 templates)
│   ├── polish.py           # Manager-perspective rewrite (accepts revision feedback)
│   ├── review.py           # HITL interrupt node
│   ├── revise.py           # Increments revision_count
│   └── save.py             # Persist to history.db + export markdown
├── router/
│   └── agent.py            # TemplateRouterAgent subgraph (analyse → decide)
├── storage/
│   ├── sqlite.py           # history.db read/write API
│   └── export.py           # Markdown file export to exports/
├── exports/                # Auto-created; exported markdown reports
└── tests/
    ├── test_graph_skeleton.py
    ├── test_phase02_llm_nodes.py
    ├── test_phase03_enrichment.py
    ├── test_phase04_hitl.py
    └── test_phase05_storage.py
```

---

## Running Tests

```bash
# Fast unit tests only (mocked LLM calls, ~10 seconds)
python -m pytest tests/ -m "not integration" -v

# Full suite including live LLM calls (~3–5 minutes)
python -m pytest tests/ -v
```

---

## Tech Stack

| Component | Library | Version |
|-----------|---------|---------|
| Agent orchestration | LangGraph | 1.1.9 |
| LLM | Claude via langchain-anthropic | 1.4.1 |
| Structured outputs | Pydantic | 2.x |
| HITL persistence | SQLite (langgraph-checkpoint-sqlite) | 3.0.3 |
| UI | Streamlit | 1.56.0 |
| Git context | GitPython | 3.1.47 |

---

## Resume Bullet

> *Built a LangGraph agent that converts unstructured daily work notes into polished manager-facing reports, featuring a Human-in-the-Loop review loop with full state persistence across Streamlit reruns, a two-step template classification subgraph, and git commit enrichment. (LangGraph · Claude API · Pydantic · Streamlit · SQLite)*
