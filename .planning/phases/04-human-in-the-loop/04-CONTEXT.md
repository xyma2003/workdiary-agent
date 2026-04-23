# Phase 4: Human-in-the-Loop - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

在 polish 节点之后插入真实的 HITL 暂停：`review_node` 调用 `interrupt()`，用户通过 `Command(resume=...)` 传回决策。支持 approve（直接到 save）和 revise（重新 polish）两种路径，revision 最多 3 次后强制到 save。

**包含**：
- review_node 实现（interrupt + 提取 decision/feedback 写入 state）
- revise_node 升级（递增计数 + 写入 feedback，返回跳回 polish）
- polish_node 小改（读取 human_feedback 融入 HumanMessage）
- graph.py 拓扑调整（新增条件边，替换 checkpointer）
- save_node 轻量升级（返回 final_report = polished）
- SqliteSaver 替换 InMemorySaver

**不包含**：Streamlit UI（Phase 6）、SQLite history 写入（Phase 5）、inline-edit 路径（Phase 6）。

</domain>

<decisions>
## Implementation Decisions

### interrupt() 设计
- **D-01:** `Command(resume={"decision": "approve"|"revise", "feedback": "..."})` dict 结构
- **D-02:** review_node 内：`response = interrupt({"polished": state.get("polished"), "revision_count": state.get("revision_count", 0)})`，从 response 中提取 `decision` 和 `feedback`，写入 state
- **D-03:** 只支持 approve 和 revise 两种 decision（edit/inline 路径留到 Phase 6）

### 拓扑修改（graph.py）
- **D-04:** 删除 Phase 1 的 `review → revise` 直接边
- **D-05:** 新增 review 节点的条件边：`approve → save`，`revise → revise`（节点名）
- **D-06:** revise_node 返回后加边 `revise → polish`，循环变为 `polish → review → revise → polish`
- **D-07:** 原有 `route_after_revise` 条件边（`revise → review/save`）**保留不变**，作为 revision_count >= 3 的强制退出守卫

### revise_node 升级
- **D-08:** revise_node 只做两件事：`revision_count += 1`，`human_feedback = feedback from state`
- **D-09:** revise_node 返回 `{"revision_count": count + 1}`（human_feedback 已在 review_node 写入 state，revise 不需要重写）

### polish_node 小改
- **D-10:** 若 `state.get("human_feedback")` 非空，在 HumanMessage 内容末尾追加 `\n\n请根据以下意见修改：{human_feedback}`
- **D-11:** human_feedback 为空时 polish 行为不变（向后兼容 Phase 2/3 的调用）

### SqliteSaver 替换
- **D-12:** `build_graph(use_sqlite: bool = False)` 新增参数
- **D-13:** `use_sqlite=True` 时：`from langgraph.checkpoint.sqlite import SqliteSaver; checkpointer = SqliteSaver.from_conn_string("graph_state.db")`
- **D-14:** 默认 `use_sqlite=False` 保持 InMemorySaver，单元测试不写磁盘

### save_node 轻量升级
- **D-15:** save_node 返回 `{"final_report": state.get("polished", "")}`（Phase 5 再加 SQLite 写入）
- **D-16:** 验证 SC-2 用 `graph.get_state(config).next == []`（到达 END）+ `result["final_report"]` 非空

### 验收策略
- **D-17:** 用独立 Python 脚本（`scripts/test_hitl_cycle.py`）验证完整 interrupt/resume 循环（ROADMAP SC-5 要求）
- **D-18:** 同时用 pytest + mock LLM 做单元测试，覆盖 interrupt 暂停、approve 路径、revise 循环、第三次强制退出

### Claude's Discretion
- interrupt() 传给用户的 payload 具体内容（除 polished 和 revision_count 外的字段）
- review_node 对 decision 值的容错处理（非 approve/revise 时的 fallback）
- 独立验证脚本的具体输出格式

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §HITL-01 — 生成后暂停，用户可查看完整日报
- `.planning/REQUIREMENTS.md` §HITL-02 — 用户可直接编辑（Phase 6，此处不实现）
- `.planning/REQUIREMENTS.md` §HITL-03 — 用户可输入修改意见，最多循环 3 次
- `.planning/REQUIREMENTS.md` §HITL-04 — 用户可一键接受当前版本

### Roadmap Success Criteria
- `.planning/ROADMAP.md` §Phase 4 — 5 条验收标准（graph.get_state().next=["review"]、approve→final_report、revise→循环、第三次强退、独立脚本验证）

### Tech Stack
- `CLAUDE.md` §Tech Stack — langgraph 1.1.9 interrupt()/Command API；langgraph-checkpoint-sqlite 3.0.3 SqliteSaver.from_conn_string

### Phase 1 Decisions (延续)
- `.planning/phases/01-graph-skeleton/01-CONTEXT.md` §D-08/D-09 — interrupt() 在节点内部调用，不用 interrupt_before；Phase 4 只换 checkpointer
- `.planning/phases/01-graph-skeleton/01-CONTEXT.md` §D-06 — state.get() 模式

### Existing Code
- `workdiary_agent/graph.py` — 主图拓扑（Phase 4 修改此文件：删边、加条件边、换 checkpointer）
- `workdiary_agent/nodes/review.py` — stub，Phase 4 替换为 interrupt() 实现
- `workdiary_agent/nodes/revise.py` — stub，Phase 4 升级（递增计数）
- `workdiary_agent/nodes/polish.py` — Phase 4 小改（融入 human_feedback）
- `workdiary_agent/nodes/save.py` — Phase 4 轻量升级（返回 final_report）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `workdiary_agent/graph.py` 中的 `route_after_revise` 函数已就位（revision_count >= 3 → save），Phase 4 保留不变
- `_make_llm()` 工厂函数（extract.py/enrich.py）——polish_node 修改时继续使用

### Established Patterns
- 节点签名：`def xxx_node(state: AgentState) -> dict`
- `state.get("key", default)` — total=False TypedDict 安全访问
- `_make_llm()` 工厂函数处理 Meituan 代理 headers

### Integration Points
- graph.py `build_graph()` 是唯一需要修改拓扑的地方
- polish_node 读取 `state.get("human_feedback")` 即可融入反馈，无需新增节点
- SqliteSaver 的 `graph_state.db` 与 Phase 5 的 `history.db` 是完全独立的两个文件

</code_context>

<specifics>
## Specific Ideas

- 独立验证脚本路径：`scripts/test_hitl_cycle.py`
- 验证脚本需演示完整 3 种路径：1) approve 直接通过；2) revise 一次后 approve；3) 连续 revise 3 次强制退出
- interrupt() 的 payload 建议包含 polished 内容和 revision_count，让调用方知道当前状态

</specifics>

<deferred>
## Deferred Ideas

- inline-edit 路径（human_decision = "edit"）— Phase 6 UI 层实现
- 异步 AsyncSqliteSaver — Streamlit 是同步的，不需要

</deferred>

---

*Phase: 04-human-in-the-loop*
*Context gathered: 2026-04-23*
