# Phase 6: Streamlit UI - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

构建 Streamlit 应用，将完整工作流可视化：
- 输入区（工作描述 + 可选 Git 路径 + 可选数据粘贴）
- 生成过程节点状态展示
- 日报审阅区（接受 / 反馈重新生成 / inline 编辑）
- 导出按钮
- 历史记录查看

**不包含**：流式输出（v2）、自定义模板编辑器（v2）、多用户系统。

</domain>

<decisions>
## Implementation Decisions

### 应用结构
- **D-01:** 单文件 `app.py`（项目根目录），侧边栏切换「生成日报」/「历史记录」两个视图
- **D-02:** 侧边栏用 `st.sidebar.radio("导航", ["生成日报", "历史记录"])` 切换

### Session 管理（SC-5 防止重启）
- **D-03:** `build_graph(use_sqlite=True)` 用 `@st.cache_resource` 装饰，graph 对象跨 rerun 缓存
- **D-04:** `thread_id` 存 `st.session_state["thread_id"]`，首次访问时用 `uuid.uuid4()` 初始化
- **D-05:** `app_state`（当前阶段：idle/generating/reviewing/done）存 `st.session_state["app_state"]`
- **D-06:** 图的当前结果 `result` 存 `st.session_state["result"]`

### 输入区（UI-01）
- **D-07:** `st.text_area("工作描述 *")` 必填
- **D-08:** `st.text_input("Git 仓库路径（可选）")` 可选
- **D-09:** `st.text_area("数据/指标（可选粘贴）")` 可选
- **D-10:** 「生成日报」按钮触发 `graph.invoke()`

### 节点状态展示（SC-1，UI-02）
- **D-11:** 用 `st.status("正在生成日报...")` 容器，内部逐步展示各节点完成状态
- **D-12:** 节点标签映射：extract→"正在提取信息..."，enrich→"正在丰富上下文..."，route_template→"正在判断日报类型..."，draft→"正在生成初稿..."，polish→"正在润色..."，review→"等待审阅..."
- **D-13:** 生成完成后 status 变为 complete 状态

### 日报审阅区（SC-2，UI-03，UI-04，HITL-02）
- **D-14:** 用 `st.text_area("日报内容（可直接编辑）", value=polished, key="edit_area")` 展示，支持 inline 编辑（HITL-02）
- **D-15:** 三个按钮：`st.button("✓ 接受")`、`st.button("↻ 重新生成")`（弹出反馈输入框）、`st.download_button("⬇ 导出")`
- **D-16:** 「接受」：调用 `graph.invoke(Command(resume={"decision": "approve", "feedback": ""}), config)` 完成流程
- **D-17:** 「重新生成」：展示 `st.text_input("修改意见")` + 确认按钮，调用 `graph.invoke(Command(resume={"decision": "revise", "feedback": feedback}), config)`
- **D-18:** inline 编辑后「接受」：用 `st.session_state["edit_area"]` 的当前值覆盖 polished，再 approve
- **D-19:** `st.download_button` 直接传入 polished 文本内容（不读文件），文件名 `daily_report_{date}.md`

### 历史记录（SC-4，UI-05）
- **D-20:** 调用 `get_all_reports()` 获取列表（已按 date DESC 排序）
- **D-21:** 用 `st.expander(f"{r['date']} — {r['template_type']}")` 展示每条记录

### Claude's Discretion
- 具体 CSS/样式细节
- 错误提示文案
- 「已选用XX模板」的展示位置（caption 或 info box）

</decisions>

<canonical_refs>
## Canonical References

### Requirements
- `.planning/REQUIREMENTS.md` §UI-01 through UI-05 — 5条UI需求
- `.planning/REQUIREMENTS.md` §HITL-02 — inline 编辑（本 Phase 实现）

### Roadmap Success Criteria
- `.planning/ROADMAP.md` §Phase 6 — 5条验收标准

### Tech Stack
- `CLAUDE.md` §Tech Stack — streamlit 1.56.0；`st.session_state` 是关键桥接

### Phase 4 Decisions (延续)
- `.planning/phases/04-human-in-the-loop/04-CONTEXT.md` §D-01/D-03 — Command(resume={"decision":...,"feedback":...}) dict 结构
- `workdiary_agent/graph.py` — `build_graph(use_sqlite=True)`，`route_after_review` 条件边

### Existing Code
- `workdiary_agent/graph.py` — `build_graph(use_sqlite=True)` 生产用
- `workdiary_agent/storage/sqlite.py` — `get_all_reports()` 接口
- `workdiary_agent/state.py` — AgentState 字段（polished, template_type, export_path 等）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_graph(use_sqlite=True)` — 直接用 SqliteSaver，Phase 6 生产环境
- `get_all_reports()` — 已实现，返回 date DESC 列表
- `Command` from `langgraph.types` — HITL resume 已在 Phase 4 验证

### Established Patterns
- `@st.cache_resource` 缓存 graph（CLAUDE.md 关键坑已记录）
- `st.session_state` 持久化 thread_id 和 app_state

### Integration Points
- `graph.invoke(state_dict, config)` — 初始调用
- `graph.invoke(Command(resume=...), config)` — HITL resume
- `graph.get_state(config).next` — 判断是否暂停在 review
- `result["__interrupt__"]` — 获取 interrupt payload（含 polished）

</code_context>

<specifics>
## Specific Ideas

- `app_state` 状态机：`idle` → `generating`（invoke 中）→ `reviewing`（interrupt 暂停）→ `done`（approve 后）
- 「已选用XX模板」用 `st.caption()` 显示在日报文本区上方
- 历史记录页面加「刷新」按钮（调用 `st.rerun()`）

</specifics>

<deferred>
## Deferred Ideas

- 流式输出（streaming）— v2
- 自定义模板编辑器 — v2
- 飞书/钉钉 Webhook — v2
- 历史日报全文搜索 — v2

</deferred>

---

*Phase: 06-streamlit-ui*
*Context gathered: 2026-04-24*
