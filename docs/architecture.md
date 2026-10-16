# Workflow and architecture

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
| Two SQLite files | `graph_state.db` belongs to LangGraph's SqliteSaver; `history.db` keeps report data in a separately managed schema |
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
├── tests/                  # offline regression and live integration tests
│   ├── test_graph_skeleton.py
│   ├── test_phase02_llm_nodes.py
│   ├── test_phase03_enrichment.py
│   ├── test_phase04_hitl.py
│   └── test_phase05_storage.py
└── exports/                # Auto-created; exported markdown reports
```

---


[Back to the project](../README.md)
