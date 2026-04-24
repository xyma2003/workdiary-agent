# Phase 5: Storage and Export - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning
**Source:** Auto-generated (Phase 5 requirements are unambiguous, no discuss needed)

<domain>
## Phase Boundary

在 save_node 中添加两件事：
1. **SQLite 历史写入**：将日报写入 `history.db`（与 `graph_state.db` 完全独立）
2. **Markdown 导出**：将 polished 内容写入 `exports/daily_report_{date}.md`

同时创建 `storage/sqlite.py` 模块，提供历史查询接口（按日期降序）。

**不包含**：Streamlit UI（Phase 6）、history.db 的 UI 展示（Phase 6）。

</domain>

<decisions>
## Implementation Decisions

### 存储结构
- **D-01:** `storage/` 目录放在 `workdiary_agent/storage/`，包含 `__init__.py` 和 `sqlite.py`
- **D-02:** `history.db` 存放在项目根目录，与 `graph_state.db` 并列，两者永不混用
- **D-03:** history 表结构：`id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, template_type TEXT, raw_input TEXT, polished TEXT, created_at TEXT`

### save_node 升级
- **D-04:** save_node 调用 `storage.sqlite.save_report(state)` 写入 history.db
- **D-05:** save_node 调用 `storage.export.save_markdown(polished, date)` 写入 markdown 文件
- **D-06:** export 文件路径：`exports/daily_report_{YYYY-MM-DD}.md`，目录不存在时自动创建
- **D-07:** `export_path` 字段写入 state，供 Phase 6 UI 使用

### 查询接口
- **D-08:** `storage/sqlite.py` 提供 `get_all_reports()` 返回按 date DESC 排序的列表
- **D-09:** 使用 stdlib `sqlite3`，不引入新依赖

### Claude's Discretion
- history 表的具体 SQL 语句
- markdown 文件的格式（标题、元信息等）
- 连接管理方式（每次调用新建连接 or 模块级连接）

</decisions>

<canonical_refs>
## Canonical References

### Requirements
- `.planning/REQUIREMENTS.md` §STORE-01 — SQLite 历史库，含日期/模板类型/原始输入/最终输出
- `.planning/REQUIREMENTS.md` §STORE-02 — 历史列表按日期排序（Phase 6 UI 用，Phase 5 提供接口）
- `.planning/REQUIREMENTS.md` §STORE-03 — 导出为 markdown，文件名含日期

### Roadmap Success Criteria
- `.planning/ROADMAP.md` §Phase 5 — 4条验收标准

### Existing Code
- `workdiary_agent/nodes/save.py` — Phase 5 在此添加 storage 调用
- `workdiary_agent/state.py` — AgentState（export_path 字段已存在）
- `workdiary_agent/graph.py` — 主图（Phase 5 不修改）

</canonical_refs>

<code_context>
## Existing Code Insights

### Integration Points
- `save_node` 已有 `export_path: None` 占位，Phase 5 填充真实路径
- `AgentState` 已有 `export_path: Optional[str]` 字段
- `history.db` 和 `graph_state.db` 分离是 Phase 1 的架构决策（STATE.md 已记录）

</code_context>

<deferred>
## Deferred Ideas

- history.db UI 展示 → Phase 6
- 导出格式自定义 → 未来扩展

</deferred>

---

*Phase: 05-storage-and-export*
*Context gathered: 2026-04-24 (auto-generated)*
