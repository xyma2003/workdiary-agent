# Phase 1: Graph Skeleton - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

构建一个可运行的 LangGraph StateGraph 骨架：所有节点（extract, enrich, route_template, draft, polish, review, revise, save）以 stub 函数实现，条件边逻辑正确（revise→review 的 revision_count 守卫），AgentState TypedDict 定义完整，graph.invoke() 可无错运行并返回 dict。

**不包含**：任何真实 LLM 调用、TemplateRouterAgent 子图、HITL interrupt、数据库写入。

</domain>

<decisions>
## Implementation Decisions

### 目录结构
- **D-01:** 在项目根下新建 `workdiary_agent/` 包目录，与 `桌面动物园/` 并列
- **D-02:** 采用层次化拆分：`workdiary_agent/graph.py`（StateGraph 组装）、`workdiary_agent/state.py`（AgentState TypedDict + Pydantic models）、`workdiary_agent/nodes/`（各节点 stub 函数，每个节点一个文件）
- **D-03:** Phase 2-6 添加新功能时直接扩展对应子目录，不动 graph.py 的组装逻辑

### AgentState 字段设计
- **D-04:** `structured_info` 字段类型为 `Optional[StructuredInfo]`，其中 `StructuredInfo` 是 Pydantic BaseModel（定义在 state.py），Phase 2 用 `llm.with_structured_output(StructuredInfo)` 直接填充
- **D-05:** `human_decision` 字段类型为 `Literal["approve", "revise", "edit"] | None`，利用类型检查器在编译期捕获错误输入
- **D-06:** 所有字段提供合理默认值（Optional 字段默认 None，revision_count 默认 0），确保 `graph.invoke({"raw_input": "test"}, config)` 无需传入完整 state

### TemplateRouterAgent 接入方式
- **D-07:** Phase 1 的 `route_template` 节点是一个普通 stub 函数（返回 state 副本，设置 template_type="技术型"）。Phase 2 再将其替换为编译好的子图并挂载到主图。Phase 1 不引入 StateGraph 嵌套。

### Checkpointer
- **D-08:** Phase 1 就使用 `MemorySaver` 编译 graph：`builder.compile(checkpointer=MemorySaver())`
- **D-09:** invoke 时传入 `config={"configurable": {"thread_id": "test-1"}}`，从 Phase 1 起验证 config 格式正确。Phase 4 只需将 MemorySaver 换成 SqliteSaver，其余调用处不需改动。

### Claude's Discretion
- 各 stub 节点的具体返回内容（只要类型正确）由 Claude 决定
- nodes/ 子目录内的文件命名规范由 Claude 决定
- `__init__.py` 的导出方式由 Claude 决定

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tech Stack & Versions
- `.planning/research/STACK.md` — 锁定的依赖版本（langgraph 1.1.9, langchain-anthropic 1.4.1, pydantic 2.12.4 等）；所有 import 和 API 调用必须与此版本一致

### Requirements
- `.planning/REQUIREMENTS.md` §AGENT-01 — Phase 1 唯一覆盖的需求：用户可用自然语言输入工作内容（骨架层面：raw_input 字段存在即满足）

### Roadmap Success Criteria
- `.planning/ROADMAP.md` §Phase 1 — 4条验收标准（invoke 无错、8个节点名存在、revise→review 条件边、AgentState 字段完整）

### Project Decisions (STATE.md)
- `.planning/STATE.md` §Decisions — interrupt_before=["review"] 编译方式；两个独立 SQLite 文件（Phase 1 不涉及但骨架设计需知晓）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- 无可直接复用的资产（workdiary_agent 是全新包，与 桌面动物园 无代码共享）

### Established Patterns
- 项目根已有 `桌面动物园/` 包结构（带 `__init__.py`、子目录分层）— workdiary_agent 沿用相同包组织方式
- CLAUDE.md 中已有完整 stack 版本表 — 直接参考，不重新 research

### Integration Points
- Phase 1 产物是独立可运行模块；Phase 2 直接编辑 nodes/ 下的文件填充 LLM 逻辑
- Phase 4 在 graph.py 的 compile 调用处将 MemorySaver 替换为 SqliteSaver

</code_context>

<specifics>
## Specific Ideas

- 节点列表（8个，顺序为边的连接顺序）：extract → enrich → route_template → draft → polish → review → revise → save
- revise→review 条件边逻辑：`revision_count >= 3` 时路由到 save，否则路由到 review（interrupt 点）
- AgentState 必须包含的字段（来自 ROADMAP.md）：raw_input, structured_info, template_type, draft, polished, human_decision, human_feedback, revision_count, git_log, repo_path, final_report, export_path

</specifics>

<deferred>
## Deferred Ideas

None — 讨论全程在 Phase 1 骨架范围内，无超范围提议。

</deferred>

---

*Phase: 01-graph-skeleton*
*Context gathered: 2026-04-23*
