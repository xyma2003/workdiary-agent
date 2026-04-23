# Phase 2: Core LLM Nodes and Template Routing - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

用真实的 Claude API 调用替换 4 个 stub 节点（extract、route_template、draft、polish），让整条链路产出真正的日报。核心产物：
- extract 节点：从口语化中文输入提取结构化信息（StructuredInfo）
- route_template 节点：替换为 TemplateRouterAgent 独立子图，自动分类日报类型
- draft 节点：按模板结构生成初稿
- polish 节点：以老板视角润色改写

**不包含**：HITL interrupt（Phase 4）、SQLite 持久化（Phase 5）、Streamlit UI（Phase 6）、Git log 工具（Phase 3）。

</domain>

<decisions>
## Implementation Decisions

### TemplateRouterAgent 架构
- **D-01:** TemplateRouterAgent 实现为独立编译的子图（非单节点 LLM 调用），存放在 `workdiary_agent/router/` 子目录
- **D-02:** 子图内部采用双节点结构：`START → analyze_content → decide_template → END`。analyze_content 提取内容特征，decide_template 做分类决策
- **D-03:** 子图使用独立的 `RouterState(TypedDict)`，不复用主图的 AgentState。主图调用时传入 raw_input/structured_info，取回 template_type
- **D-04:** route_template_node 函数内部调用编译好的 router 子图，将结果写入 `{"template_type": ...}`，对主图透明

### 3 种模板结构（硬编码在 draft 节点的 prompt 里）
- **D-05:** 技术型模板结构：任务 → 方案 → 进度 → 下一步
- **D-06:** 业务型模板结构：结论 → 数据 → 进展 → 下一步
- **D-07:** 混合型模板结构：业务影响 → 技术工作 → 量化指标 → 下一步
- **D-08:** 模板结构直接硬编码在 draft 节点的 system prompt 中（不存文件），根据 template_type 动态选择对应 prompt

### polish 节点润色策略
- **D-09:** polish 节点基于 draft 内容进行润色改写（不重新生成），保留模板结构，优化语气和用词
- **D-10:** 量化指标缺失时，在应有数据的位置显示占位符「（未提供量化指标）」，不捏造数据

### extract 节点
- **D-11:** StructuredInfo 字段保持现有 4 个字段：tasks, outputs, blockers, progress（已满足 AGENT-02 要求）
- **D-12:** 使用 `ChatAnthropic.with_structured_output(StructuredInfo)` 直接返回 Pydantic 对象（Phase 1 已锁定，D-04 延续）

### Claude's Discretion
- 各节点的具体 prompt 措辞由 Claude 决定
- TemplateRouterAgent analyze_content 节点的具体提取维度由 Claude 决定
- RouterState 的具体字段设计由 Claude 决定
- polish 节点的老板视角 prompt 具体写法由 Claude 决定（需包含"完成/推进/对齐/输出/跟进"等动词要求）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §AGENT-02 — 结构化提取：任务、产出、问题、进度
- `.planning/REQUIREMENTS.md` §AGENT-05 — TemplateRouterAgent 自动判断日报类型（技术型/业务型/混合型）
- `.planning/REQUIREMENTS.md` §AGENT-06 — 按选定模板生成日报初稿
- `.planning/REQUIREMENTS.md` §AGENT-07 — 老板视角润色：业务价值、量化指标、目标完成动词
- `.planning/REQUIREMENTS.md` §TMPL-01 — 3 种内置模板定义
- `.planning/REQUIREMENTS.md` §TMPL-02 — 路由决策对用户可见（「已选用XX模板」）
- `.planning/REQUIREMENTS.md` §TMPL-03 — 用户可手动覆盖模板类型

### Roadmap Success Criteria
- `.planning/ROADMAP.md` §Phase 2 — 5 条验收标准（结构化提取、3类分类正确率、polish 输出格式、模板可见性、用户覆盖）

### Tech Stack & Versions
- `.planning/research/STACK.md` — 锁定版本（langgraph 1.1.9, langchain-anthropic 1.4.1 等）；with_structured_output 用法在此

### Phase 1 Decisions (延续)
- `.planning/phases/01-graph-skeleton/01-CONTEXT.md` §D-02 — 包结构：nodes/ 下每节点一个文件
- `.planning/phases/01-graph-skeleton/01-CONTEXT.md` §D-04 — with_structured_output(StructuredInfo) 已锁定

### Existing Code
- `workdiary_agent/state.py` — AgentState 和 StructuredInfo 定义（Phase 2 直接使用）
- `workdiary_agent/nodes/` — 4 个 stub 节点待替换：extract.py, route_template.py, draft.py, polish.py
- `workdiary_agent/graph.py` — 主图组装（Phase 2 不修改拓扑，只替换节点实现）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `workdiary_agent/state.py`：StructuredInfo Pydantic BaseModel 已定义（tasks/outputs/blockers/progress），Phase 2 直接用 with_structured_output 填充
- `workdiary_agent/graph.py`：主图拓扑已固定，Phase 2 只需替换 nodes/ 下的实现，不动 graph.py
- `workdiary_agent/nodes/__init__.py`：re-export 机制已就位，新实现自动被主图引用

### Established Patterns
- 节点函数签名：`def xxx_node(state: AgentState) -> dict`，返回部分 state 更新
- 使用 `state.get("key", default)` 而非 `state["key"]`（total=False TypedDict）
- ChatAnthropic 模型：`claude-sonnet-4-5`（CLAUDE.md 锁定）

### Integration Points
- route_template_node 替换后：从返回 `{"template_type": "技术型"}` 改为调用 TemplateRouterAgent 子图
- extract_node 替换后：从返回 `{"structured_info": None}` 改为 LLM with_structured_output 调用
- draft_node/polish_node：从返回 stub 字符串改为真实 LLM 调用

</code_context>

<specifics>
## Specific Ideas

- TMPL-02 要求「已选用XX模板」对用户可见：可在 template_type 字段值中直接体现，或在 draft/polished 内容头部加一行说明
- ROADMAP.md SC-5 要求用户可覆盖模板类型后 draft 重新生成：Phase 2 在 draft 节点读取 template_type，用户覆盖后重新 invoke 即可触发（Phase 4 HITL 完成后才有完整流程）
- polish 节点的目标动词清单（来自 AGENT-07）：完成/推进/对齐/输出/跟进

</specifics>

<deferred>
## Deferred Ideas

None — 讨论全程在 Phase 2 范围内，无超范围提议。

</deferred>

---

*Phase: 02-core-llm-nodes-and-template-routing*
*Context gathered: 2026-04-23*
