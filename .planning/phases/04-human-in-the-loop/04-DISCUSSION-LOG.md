# Phase 4: Human-in-the-Loop - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-23
**Phase:** 04-human-in-the-loop
**Areas discussed:** interrupt() 返回内容设计, revise_node 实现方式, SqliteSaver 替换方式, Phase 4 验收策略

---

## interrupt() 返回内容设计

| Option | Description | Selected |
|--------|-------------|----------|
| dict 包含 decision + feedback | Command(resume={"decision": ..., "feedback": ...}) | ✓ |
| 简单字符串（仅 decision） | Command(resume="approve") | |

**User's choice:** dict 结构，approve + revise 两种 decision

---

## 拓扑修改

| Option | Description | Selected |
|--------|-------------|----------|
| 修改拓扑（推荐） | 删除 review→revise 直接边，review 根据 decision 路由；revise→polish 新边 | ✓ |
| 保持现状 | revise 内部调用 polish LLM，职责混乱 | |

**User's choice:** 修改拓扑（用户主动要求：架构更清晰就修改）

---

## revise_node 实现方式

| Option | Description | Selected |
|--------|-------------|----------|
| revise 只递增计数 + 写入 feedback，主图重跳 polish | 职责分离，拓扑清晰 | ✓ |
| revise 自己调用 LLM 重新生成 | 职责混乱，polish 逻辑重复 | |

**User's choice:** revise 只递增计数，主图重跳 polish

### polish 融入 feedback

| Option | Description | Selected |
|--------|-------------|----------|
| 在 HumanMessage 里附加 feedback（推荐） | polish 读取 human_feedback，附加到 HumanMessage 末尾 | ✓ |
| 修改 system prompt | 类似但位置不同 | |

---

## SqliteSaver 替换方式

| Option | Description | Selected |
|--------|-------------|----------|
| 同步 SqliteSaver.from_conn_string()（推荐） | 简单直接，无需 async | ✓ |
| 异步 AsyncSqliteSaver | Streamlit 是同步的，不需要 | |

| Option | Description | Selected |
|--------|-------------|----------|
| build_graph(use_sqlite: bool = False)（推荐） | 测试用内存，生产用 SQLite，不改调用处 | ✓ |
| 直接替换 | 测试也写磁盘，隔离性差 | |

---

## Phase 4 验收策略

| Option | Description | Selected |
|--------|-------------|----------|
| graph.get_state(config).next == [] 验证到达 END | 不需改 save_node | ✓ |
| save_node 返回 final_report | 需改 save_node | |

| Option | Description | Selected |
|--------|-------------|----------|
| 独立 Python 脚本 + pytest（推荐） | ROADMAP SC-5 要求独立脚本；pytest 做单元测试 | ✓ |
| 仅 pytest | 真实循环测试成本高 | |

---

## Claude's Discretion

- interrupt() payload 除 polished/revision_count 外的字段
- review_node 对非法 decision 值的 fallback
- 独立验证脚本的输出格式

## Deferred Ideas

- inline-edit 路径（Phase 6）
- AsyncSqliteSaver（不需要）
