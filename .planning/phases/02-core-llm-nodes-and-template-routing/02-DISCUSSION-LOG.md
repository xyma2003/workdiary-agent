# Phase 2: Core LLM Nodes and Template Routing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 02-core-llm-nodes-and-template-routing
**Areas discussed:** TemplateRouterAgent 实现方式, 3 种模板内容设计, polish 润色策略, extract 结构化提取

---

## TemplateRouterAgent 实现方式

| Option | Description | Selected |
|--------|-------------|----------|
| 独立编译的子图 | 新建 router/ 子目录，独立 StateGraph，在 route_template_node 内调用。展示 Multi-Agent 意识，面试价值高。 | ✓ |
| 单个 LLM 调用内联 | 直接在 route_template_node 里调用 ChatAnthropic，返回 template_type。实现简单，但展示不出子图架构。 | |

**User's choice:** 独立编译的子图

---

## TemplateRouterAgent 子图内部结构

| Option | Description | Selected |
|--------|-------------|----------|
| 单节点：直接返回分类结果 | START → classify → END。简洁，展示子图概念已足够。 | |
| 双节点：analyze → decide | START → analyze_content → decide_template → END。先提取内容特征，再做分类决策。更接近真实 Multi-Agent 模式，面试可讲性更强。 | ✓ |

**User's choice:** 双节点：analyze → decide

---

## TemplateRouterAgent 子图 State 设计

| Option | Description | Selected |
|--------|-------------|----------|
| 独立 TypedDict，不共享主图 State | 定义 RouterState(TypedDict)，只包含 router 需要的字段。主图调用时传入 raw_input/structured_info，取回 template_type。架构更清晰。 | ✓ |
| 复用 AgentState | 子图直接使用主图的 AgentState。少写一个类，但子图和主图耦合较紧。 | |

**User's choice:** 独立 TypedDict，不共享主图 State

---

## 技术型模板结构

| Option | Description | Selected |
|--------|-------------|----------|
| 任务/方案/进度/下一步 | 「完成了什么」→「怎么做的」→「进到哪了」→「接下来」。适合纯技术工作（开发、架构、调研）。 | ✓ |
| 背景/工作/结果/问题 | 主要展示技术背景和工作内容，适合面向技术老板的展示。 | |

**User's choice:** 任务/方案/进度/下一步

---

## 业务型模板结构

| Option | Description | Selected |
|--------|-------------|----------|
| 结论/数据/进展/下一步 | 先说结论，再用数据支撑，适合业务老板。重点突出业务价值和量化指标。 | ✓ |
| 目标/进展/阻碍/资源需求 | 面向项目管理风格，适合有明确 OKR 目标的工作。 | |

**User's choice:** 结论/数据/进展/下一步

---

## 混合型模板结构

| Option | Description | Selected |
|--------|-------------|----------|
| 业务影响/技术工作/量化指标/下一步 | 先说技术工作带来了什么业务价值，再展开。最适合展示给技商兼备的老板。 | ✓ |
| 技术工作/业务关联/数据支撑/下一步 | 先展示技术工作，再关联业务意义。适合技术老板为主的场景。 | |

**User's choice:** 业务影响/技术工作/量化指标/下一步

---

## draft 节点 prompt 传入方式

| Option | Description | Selected |
|--------|-------------|----------|
| 模板结构硬编码在 prompt 里 | 每种模板对应一个独立 system prompt，根据 template_type 动态选择。简单可控。 | ✓ |
| 模板内容存入文件，运行时加载 | 将模板 prompt 存为 .txt/.md 文件，运行时读取。不改代码可更新模板，但增加文件依赖。 | |

**User's choice:** 模板结构硬编码在 prompt 里

---

## polish 节点输入

| Option | Description | Selected |
|--------|-------------|----------|
| 基于 draft 润色改写 | 读取 draft 内容，按老板视角改写表达方式。保留结构，优化语气和用词。 | ✓ |
| 基于 structured_info 重新生成 | 跳过 draft，直接用结构化信息生成老板视角日报。更强的老板视角转换，但可能丢失模板结构。 | |

**User's choice:** 基于 draft 润色改写

---

## 量化指标缺失处理

| Option | Description | Selected |
|--------|-------------|----------|
| 显示「未提供量化指标」占位符 | 在应有数据的位置写「（未提供量化指标）」。不捏造数据，老板看到后知道需要追问。 | ✓ |
| 不补充数据占位符，直接略过量化要求 | 如果没有数据就不强调量化，润色其他部分。少一个占位符，但隐藏了信息缺失。 | |

**User's choice:** 显示「未提供量化指标」占位符

---

## StructuredInfo 字段

| Option | Description | Selected |
|--------|-------------|----------|
| 够用，保持现有字段 | 4 个字段（tasks, outputs, blockers, progress）已覆盖 AGENT-02 要求。不加字段。 | ✓ |
| 增加 template_hint 字段 | extract 节点同时输出内容分类提示，供 TemplateRouterAgent 参考。 | |

**User's choice:** 够用，保持现有字段

---

## extract 节点 LLM 调用方式

| Option | Description | Selected |
|--------|-------------|----------|
| with_structured_output(StructuredInfo) | ChatAnthropic.with_structured_output(StructuredInfo) 直接返回 Pydantic 对象。Phase 1 已锁定（D-04）。 | ✓ |
| 普通 LLM 调用 + JSON 解析 | 返回文本后手动解析 JSON。更容易出错，不推荐。 | |

**User's choice:** with_structured_output(StructuredInfo)

---

## Claude's Discretion

- 各节点的具体 prompt 措辞
- TemplateRouterAgent analyze_content 节点的提取维度
- RouterState 的具体字段设计
- polish 节点的老板视角 prompt 具体写法

## Deferred Ideas

None
