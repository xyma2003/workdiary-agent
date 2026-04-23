# Phase 3: Enrichment Tools - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 03-enrichment-tools
**Areas discussed:** Git log 内容范围, 数据输入方式, enrich 节点职责, enrichment 融入 draft

---

## Git Log 内容范围

### 读取范围

| Option | Description | Selected |
|--------|-------------|----------|
| 今日所有 commits | 读取今天 0:00 至现在的所有 commits，最匹配"今日工作"语义 | ✓ |
| 最近 N 条 commits | 读取最新 N 条，不管时间 | |
| 可配置（时间范围 or N 条） | 用户可传参，灵活但增加输入复杂度 | |

**User's choice:** 今日所有 commits（推荐）

### 传递格式

| Option | Description | Selected |
|--------|-------------|----------|
| 拼接成文本字符串写入 git_log | commit messages 拼接为多行文本，draft 节点直接读取字段 | ✓ |
| 结构化列表写入新字段 | List[str] 保持结构，但需改 AgentState 和 draft prompt | |

**User's choice:** 拼接成文本字符串写入 git_log（推荐）

---

## 数据输入方式

### 进入 graph 的方式

| Option | Description | Selected |
|--------|-------------|----------|
| 用户直接传入文本字符串 | AgentState 新增 data_input: Optional[str]，Phase 6 UI 再提供输入框 | ✓ |
| 仅支持粘贴文本（不支持 CSV 文件） | Phase 3 只处理文本，CSV 文件留到 Phase 6 | |
| 支持文本 + CSV 文件路径 | 自动判断并读取，灵活但复杂度稍高 | |

**User's choice:** 用户直接传入文本字符串（推荐）

### enrich 节点处理方式

| Option | Description | Selected |
|--------|-------------|----------|
| LLM 提取关键指标写入新字段 | 用 Claude 从 data_input 提取数字/指标，写入 data_summary | ✓ |
| 原文直接传递 | 不预处理，让 draft 节点自己处理 | |

**User's choice:** LLM 提取关键指标写入新字段（推荐）

---

## enrich 节点职责

| Option | Description | Selected |
|--------|-------------|----------|
| 一个 enrich 节点同时处理两者 | 单节点内部顺序处理 git + data，主图拓扑不变 | ✓ |
| 拆成两个节点（enrich_git + enrich_data） | 更清晰但需修改 graph.py 拓扑 | |

**User's choice:** 一个 enrich 节点同时处理两者（推荐）

---

## enrichment 融入 draft

| Option | Description | Selected |
|--------|-------------|----------|
| 修改 draft 节点的 prompt，动态拼入局部信息 | 在现有 context 字符串后追加 git_log 和 data_summary | ✓ |
| 新增一个 merge_context 节点做预处理 | 主图拓扑需修改，增加复杂度 | |

**User's choice:** 修改 draft 节点的 prompt，动态拼入局部信息（推荐）

---

## Claude's Discretion

- GitPython 的具体 API 调用方式（`iter_commits` 参数细节）
- data_input 提取的 LLM system prompt 措辞
- git_log 的具体格式（是否含 author、time 等）

## Deferred Ideas

- CSV 文件路径读取 — 留到 Phase 6 UI 层处理
- 可配置时间范围（N 天/N 条）— 当前 Phase 3 固定今日
