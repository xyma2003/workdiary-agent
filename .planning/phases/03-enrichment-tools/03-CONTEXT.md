# Phase 3: Enrichment Tools - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

为主流程添加两个可选的上下文来源：
1. **Git log**：读取用户指定本地 repo 的今日 commits，拼接为文本写入 `git_log`
2. **数字/数据输入**：接收用户粘贴的文本（含数字/表格/指标），用 LLM 提取关键指标写入 `data_summary`

两者均为可选——缺失时主流程不受影响，graph 正常完成并返回结果。

**不包含**：CSV 文件上传（Phase 6 UI 层处理）、HITL interrupt（Phase 4）、Streamlit UI（Phase 6）。

</domain>

<decisions>
## Implementation Decisions

### Git Log 读取范围
- **D-01:** 读取今日所有 commits（从当天 00:00:00 至当前时刻）
- **D-02:** 使用 GitPython：`Repo(repo_path).iter_commits(since="today midnight")`
- **D-03:** commit messages 拼接为多行文本字符串写入 `AgentState.git_log`，格式：每行一条 `{hash[:7]} {message}`
- **D-04:** `repo_path` 为空或无效时，`git_log` 设为 `None`，不抛异常，主流程继续

### 数据输入方式
- **D-05:** `AgentState` 新增字段 `data_input: Optional[str]`——用户粘贴的原始文本（数字、指标、表格等）
- **D-06:** `AgentState` 新增字段 `data_summary: Optional[str]`——enrich 节点用 LLM 从 `data_input` 提取的关键指标摘要
- **D-07:** `data_input` 为空或 None 时，`data_summary` 设为 `None`，跳过 LLM 调用

### enrich 节点职责
- **D-08:** 单个 `enrich_node` 同时处理 git log 读取和 data_input 提取，主图拓扑不变（graph.py 无需修改）
- **D-09:** 节点内部顺序：先读 git（同步 IO）→ 再处理 data_input（LLM 调用，仅当 data_input 非空）
- **D-10:** 节点返回 `{"git_log": ..., "data_summary": ...}`，两个字段都可以是 None

### enrichment 融入 draft
- **D-11:** 修改 `draft_node` 的 context 拼接逻辑：
  - 若 `git_log` 不为空，在 context 末尾追加：`\n今日 Git commits：\n{git_log}`
  - 若 `data_summary` 不为空，在 context 末尾追加：`\n数据指标：\n{data_summary}`
- **D-12:** 不新增节点，不修改主图拓扑，仅扩展 `draft_node` 内的 context 构建逻辑

### Claude's Discretion
- GitPython 的具体 API 调用方式（`iter_commits` 参数细节）由 Claude 决定
- data_input 提取的 LLM system prompt 措辞由 Claude 决定
- git_log 的具体格式（是否含 author、time 等）由 Claude 决定，保持简洁即可

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §AGENT-03 — Git repo 路径可选，读取今日 commits 作为辅助上下文
- `.planning/REQUIREMENTS.md` §AGENT-04 — 可解析粘贴的数字/指标/表格文本，提取数据特征融入日报

### Roadmap Success Criteria
- `.planning/ROADMAP.md` §Phase 3 — 3 条验收标准（有效 repo → commits 出现在报告；无效 repo → git_log=None 无异常；有数据 → 指标出现；无数据 → 正常生成）

### Tech Stack
- `.planning/research/STACK.md` — gitpython 3.1.47 版本锁定；ChatAnthropic(model="claude-sonnet-4-5")

### Phase 1 Decisions (延续)
- `.planning/phases/01-graph-skeleton/01-CONTEXT.md` §D-02 — 包结构：nodes/ 下每节点一个文件
- `.planning/phases/01-graph-skeleton/01-CONTEXT.md` §D-06 — `state.get("key", default)` 模式

### Existing Code
- `workdiary_agent/state.py` — AgentState 定义（Phase 3 需新增 data_input, data_summary 字段）
- `workdiary_agent/nodes/enrich.py` — 当前 stub，Phase 3 替换实现
- `workdiary_agent/nodes/draft.py` — Phase 3 修改 context 拼接逻辑（非替换，是扩展）
- `workdiary_agent/graph.py` — 主图拓扑（Phase 3 不修改）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `workdiary_agent/nodes/extract.py` — `_make_llm()` 工厂函数模式（含美团代理 headers），enrich 节点 LLM 调用需复用此模式
- `workdiary_agent/nodes/draft.py` — context 拼接逻辑已有框架（structured_info → 多行文本），Phase 3 在此基础上追加 git_log 和 data_summary

### Established Patterns
- 节点函数签名：`def xxx_node(state: AgentState) -> dict`，返回部分 state 更新
- `state.get("key", default)` — total=False TypedDict 的安全访问方式
- `_make_llm()` 工厂函数：读取 `ANTHROPIC_CUSTOM_HEADERS` 环境变量，传入 `default_headers`

### Integration Points
- `enrich_node` 在主图中位于 `extract` 之后、`route_template` 之前（已在 graph.py 中连接）
- `draft_node` 读取 `state.get("git_log")` 和 `state.get("data_summary")` 来扩展 context

</code_context>

<specifics>
## Specific Ideas

- git_log 格式建议：`{commit.hexsha[:7]} {commit.message.strip()}`，每行一条，简洁易读
- data_summary 的 LLM 提取目标：识别数字、百分比、时间指标、对比数据（如"从200ms降到45ms"）
- 错误处理：`InvalidGitRepositoryError`、`NoSuchPathError`、`GitCommandError` 均 catch 并返回 `git_log=None`

</specifics>

<deferred>
## Deferred Ideas

- CSV 文件路径读取 — 留到 Phase 6 UI 层处理（文件上传需要 Streamlit 支持）
- 可配置时间范围（N 天/N 条）— 当前 Phase 3 固定今日，未来可扩展

</deferred>

---

*Phase: 03-enrichment-tools*
*Context gathered: 2026-04-23*
