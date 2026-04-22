# 智能日报 Agent (WorkDiary Agent)

## What This Is

一个基于 LangGraph 的智能日报生成 Agent，帮助用户将每天碎片化、口语化的工作描述，转化为结构清晰、突出业务价值的"老板爱看"日报。系统通过多节点状态机处理输入、自动识别日报类型、润色改写，并支持人工确认循环，最终导出为 markdown 文件并存储历史记录。

## Core Value

用户输入一段口语化的工作描述，Agent 能自动生成一份老板视角的专业日报，让用户5分钟内完成每日汇报。

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] 用户可以用自然语言（口语化）输入今天的工作内容
- [ ] Agent 自动提取结构化信息：任务、产出、问题、进度
- [ ] TemplateRouterAgent 根据内容自动判断日报类型（技术型/业务型/混合型）
- [ ] 按选定模板生成日报初稿
- [ ] 老板视角润色改写：突出业务价值、量化指标、推进进度
- [ ] 人工确认环节（human-in-the-loop）：用户可查看、修改或要求重新生成
- [ ] 按用户反馈定向修改，支持循环（带最大重试次数限制）
- [ ] 可选输入 Git repo 路径，Agent 自动读取今日 commits 作为辅助上下文
- [ ] 导出日报为 markdown 文件
- [ ] 历史日报存储到 SQLite，支持查看历史记录
- [ ] Streamlit UI 界面，支持输入、展示、确认、导出全流程

### Out of Scope

- 自动发送到飞书/钉钉 — 增加外部 API 依赖，复杂度高，用户可手动复制粘贴
- 用户自定义模板编辑器 — 一周内开发时间有限，预设3种模板已足够展示
- 多用户/账号系统 — 个人工具，单用户场景
- 移动端适配 — Streamlit 桌面端已够用

## Context

- **项目定位**：求职项目，用于展示 AI Agent 开发能力，面向 AI Agent 开发岗位应聘
- **目标受众**：开发者自用，同时作为面试作品集展示
- **核心亮点**：LangGraph 状态机、TemplateRouterAgent（Multi-Agent 路由）、human-in-the-loop、tool use（Git log 读取）
- **技术背景**：用户熟悉 Python，有 Anthropic SDK 使用经验（本地有 Claude API 环境）
- **时间约束**：一周内完成开发

## Constraints

- **Tech Stack**: Python + LangGraph + Claude API (claude-sonnet-4-5) + Streamlit + SQLite — 已确定，不考虑替代方案
- **Timeline**: 一周内完成 — 功能范围需严格控制，不做镀金
- **LLM**: Anthropic Claude API — 用户本地已有环境配置
- **UI**: Streamlit — 快速原型，无需复杂前端

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 使用 LangGraph 而非直接链式调用 | 展示 Agent 状态机概念，面试价值更高 | — Pending |
| TemplateRouterAgent 作为独立子 Agent | 路由决策是独立判断任务，合理拆分，展示 Multi-Agent 意识 | — Pending |
| Human-in-the-loop 节点 | 体现 Agent 落地的核心挑战（幻觉、不可控），面试可深入讲解 | — Pending |
| Git log 作为可选工具调用 | 让项目从"prompt wrapper"升级为真正的 Agent（有工具、有决策） | — Pending |
| 导出 markdown 而非对接飞书/钉钉 | 降低复杂度，一周时间内可完成，用户手动复制即可 | — Pending |
| Streamlit UI | 一天搞定，够用，不分散精力在前端 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-22 after initialization*
