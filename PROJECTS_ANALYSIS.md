# 三个项目亮点分析

> 本文档记录三个 portfolio 项目的技术亮点、架构设计、Idea 创新点，以及后续优化思考。
> 面试备用，持续更新。
>
> 最后更新：2026-04-29

---

## 目录

- [桌面动物园](#桌面动物园-desktop-pet-zoo)
- [Multi-Agent Debate System](#multi-agent-debate-system)
- [智能日报 Agent](#智能日报-agent-workdiary-agent)
- [三个项目横向对比](#三个项目横向对比)

---

## 桌面动物园 (Desktop Pet Zoo)

**路径：** `./桌面动物园/`

**一句话定位：** PyQt6 桌面宠物（边牧）+ LangGraph AI Agent，支持自然语言控制桌面功能。

### 是什么

用户桌面上常驻一只边牧宠物，可以拖动、点击交互，也可以用自然语言跟它说话。说"帮我看今天的新闻"，它会自动爬取热搜并展示；说"先看新闻，再定10分钟闹钟"，它会自动分解任务依次完成。

### 技术亮点

**LangGraph 5节点工作流（含自动反思）：**
```
understand → plan → execute ⇄ reflect → respond
```
- `reflect` 节点：执行失败时 Claude 自动分析原因，返回 replan/continue/abort，不需要人工干预
- `plan` 节点：根据可用工具列表让 Claude 制定分步计划，解决复杂多步任务

**工具自动绑定：**
- `@tool` 装饰器定义工具，动态工具列表传给 Agent
- 新增功能只需加一个工具函数，Agent 自动可用，无需改调用逻辑

**异步 UI 不卡顿：**
- `QThread + Signal/Slot`：Agent 在后台线程运行，UI 全程响应
- `finished` signal 回调更新聊天列表

**双模式降级：**
- `Config.ENABLE_AI_AGENT` 开关，无 API Key 时自动退回按钮模式
- 功能模块对两种模式透明，不需要分别适配

### 架构亮点

**插件化功能架构（BaseFeature 基类）：**
```python
class BaseFeature(ABC):
    def get_name(self) -> str: ...
    def get_button_text(self) -> str: ...
    def execute(self) -> dict: ...
    def on_result(self, result, pet_window=None): ...
```
- 功能模块同时支持 GUI 按钮调用 和 Agent 工具调用，一套代码两种触发方式
- 新增功能只需继承 BaseFeature，UI 和 Agent 自动感知

**用户状态持久化：**
```json
{ "last_seen": "2026-04-29T15:45:00" }
```
- 7天以上 → 久别重逢语；1天以上 → 欢迎回来；4小时以上 → 好久不见；否则 → 时间段问候
- 情感化设计，宠物有"记忆"

**单双击识别：**
- 300ms 定时器区分单击（交互动画）和双击（打开主面板）

### Idea 亮点

- **交互形态创新**：不是"打开 AI 工具"，而是"跟桌面宠物说话"，降低了 AI 工具的使用门槛和心理距离
- **功能与情绪融合**：闹钟触发时宠物放大 2 倍全屏乱跑，功能反馈通过 UI 情绪表达
- **可扩展的宠物工具箱**：任何桌面功能都可以包装成工具挂载，天气、番茄钟、待办等都是天然延伸

### AgentState 数据结构

```python
{
    "messages": [HumanMessage, AIMessage, ...],
    "current_task": str,        # 当前任务描述
    "plan": [str],              # 执行步骤列表
    "steps_completed": [str],   # 已完成步骤
    "tool_results": {str: dict},# 每步执行结果
    "reasoning": str,           # reflect 节点的决策
    "status": str,              # 状态标志
}
```

### 面试表述建议

> "这个项目的核心是把 LangGraph Agent 嵌入桌面宠物，让 AI 能力通过一个有情感的 UI 载体呈现。技术上最值得说的有三点：一是 5 节点工作流里的 reflect 节点，Agent 执行失败会自动分析原因并重新规划，不崩溃；二是插件化的 BaseFeature 架构，每个功能同时支持按钮触发和 Agent 调用；三是 QThread + Signal/Slot 保证 UI 不卡顿。"

---

## Multi-Agent Debate System

**路径：** `./debate-agent/`

**一句话定位：** 三个有认知偏见的 LLM Agent 多轮结构化辩论，用语义分歧检测驱动轮数，输出置信度评分 + 可审计共识报告。

### 是什么

给定任何话题（"远程工作对公司是净正收益吗？"），三个 Agent 分别扮演：
- 🟢 **Optimist** — 乐观情景分析
- 🔴 **Pessimist** — 悲观/bear-case 分析
- 😈 **Devil's Advocate** — 挑战双方假设

Round 1 三者并行独立分析，系统计算语义分歧分数，若分歧仍高则触发回合制辩论，直到收敛或达到最大轮数，最终生成置信度评分 + 共识/争议分析报告。

### 技术亮点

**PROHIBITION 块 — 工程化反 sycophancy：**
```
PROHIBITION: 禁止出现 "however"、"but"、"on the other hand"、"balanced view"
必须维持立场，除非遇到逻辑上更优的论据
```
- 不是建议，而是硬约束
- 核心洞察：单 LLM 的"多角度分析"是假多角度，表面平衡实为单调性；PROHIBITION 强制真正的认知对立

**Claim 级别 embedding — 解决 naive 相似度的陷阱：**
- 问题：三个 Agent 讨论同一 topic，完整文本在语义空间里本来就相似，直接比较会误判收敛
- 解决：只 embed `key_claims`（3-7 个短句核心论点），粒度更细，保留真正的分歧信号
- 细节：`normalize_embeddings=True` 保证 dot product == cosine similarity，数学正确性

**置信度公式写死在代码里（SYNTH-03）：**
```python
def _compute_confidence_score(round_history, round_num) -> float:
    max_divergence = max(r.divergence_score for r in round_history)
    round_adjustment = {1: 1.0, 2: 0.9, 3: 0.8}[round_num]
    return round((1.0 - max_divergence) * round_adjustment, 4)
```
- 拒绝让 LLM 自己给分——LLM 的自评往往编造数字来显得有信心
- 好处：可审计、可复现、无偏差

**Concession 溯源：**
```python
class Concession(BaseModel):
    triggered_by_agent: str    # 被谁说服
    triggered_by_claim: str    # 被哪个论点说服（原文复制）
    conceded_point: str        # 让步了什么
    rationale: str             # 一句话解释为什么
```
- 每个让步都有完整的推理链，能审计"为什么妥协"

**Sentinel 对象 — 优雅的失败降级：**
- LLM 结构化输出解析失败时注入 sentinel（带 `is_sentinel=True` 标志）
- 不崩溃，UI 能感知并提示
- 3 次重试 + sentinel 兜底，鲁棒性设计

### 架构亮点

**LangGraph Send/fan-out 并行：**
```
dispatch_round1 → Send(optimist_node)  ┐
                → Send(pessimist_node) ┼ 真正并行执行
                → Send(devil_node)     ┘
                         ↓
                    collect_round1 (add reducer fan-in)
```
- routing 函数返回 `list[Send]`，LangGraph 自动并行调度
- 坑：routing 函数不能注册为节点，只能传给 `add_conditional_edges`，否则报 InvalidUpdateError
- `current_round_arguments` 是唯一用 `add` reducer 的字段，其他字段都是 last-write-wins

**Compact summaries — 防止 token 随轮数爆炸：**
```python
# 回合制只取最新一轮的前 3 个 key_claims，约 80 tokens/Agent
summaries = [{"key_claims": arg.key_claims[:3], ...}]
```

**SYNTH-04 诚实不确定路径：**
- 未达成共识时 verdict 必须以 "Agents did not reach consensus on this topic." 开头
- 避免 LLM 在没有共识时编造虚假总结

**Single flat StateGraph：**
- 不用 subgraph 嵌套，每个字段的生命周期、修改点一目了然
- 更易 checkpoint 和审计

### 系统架构拓扑

```
START
  ↓
initialize_node
  ↓
dispatch_round1 → [optimist | pessimist | devil]（并行）
  ↓
collect_round1
  ↓
divergence_check_node
  ↓
route_divergence
  ├─ diverged + round < max → dispatch rebuttal（循环）
  └─ converged / max_rounds → synthesize_stub → save_node → END
```

### Idea 亮点

- **结构性质疑 > Prompt 技巧**：通过架构强制认知冲突，而不是靠 prompt 请求"批判性思考"
- **不信任 LLM 的自我评估**：置信度公式是对 LLM 局限性的清醒认知，体现在架构设计上而不是注释里
- **可追溯的让步链**：辩论的价值不只是结论，而是推理过程——concession 溯源让整个思维过程可审计

### 面试表述建议

> "这个系统的核心洞察是：单 LLM 的多角度分析存在 sycophancy 问题，表面上多视角但实际上是同一立场。我通过三个方向解决它：PROHIBITION 块硬约束 Agent 不得妥协、Round 1 完全隔离保证独立性、回合制辩论强制质疑对方。"
>
> "另一个值得说的点是置信度分数——我没有让 LLM 自己评分，因为 LLM 的自评不可靠。我用代码公式 (1 - max_divergence) * round_adjustment 计算，可审计、无偏差。"
>
> "LangGraph 里用了 Send API 做真正的并行 fan-out，这里有个坑：routing 函数不能注册为节点，只能传给 add_conditional_edges，踩过这个坑。"

---

## 智能日报 Agent (WorkDiary Agent)

**路径：** `./workdiary_agent/`

**一句话定位：** LangGraph 8节点状态机，将口语化工作描述转化为"老板爱看"的专业日报，完整实现带状态持久化的 Human-in-the-Loop 修改循环。

### 是什么

用户输入一段口语化描述（"今天修了个 bug，跑了个数据，开了两个会"），系统自动：
1. 结构化提取任务/产出/阻碍/进度
2. 读取今日 git commits 丰富上下文
3. 分类日报模板（技术型/业务型/混合型）
4. 生成初稿 → 从老板视角润色
5. **暂停，让用户审阅、编辑、反馈**（HITL interrupt）
6. 最多 3 次修改循环后保存，导出 markdown

### 技术亮点

**完整 HITL interrupt/resume（LangGraph 高级用法）：**
```python
# review 节点内
payload = interrupt({"draft": state["polished_draft"], "version": state["revision_count"]})
# → 抛出 GraphInterrupt，LangGraph runtime 序列化完整 state 到 SqliteSaver，图暂停

# 用户操作后恢复
graph.invoke(Command(resume={"action": "approve"}), config={"configurable": {"thread_id": tid}})
# → 从 SqliteSaver 加载状态，从 review 节点继续
```
- 踩坑 1：`GraphInterrupt` 是 Exception 子类，不能被 `except Exception:` 吞掉
- 踩坑 2：`SqliteSaver.from_conn_string()` 是 context manager，不加 `with` 返回生成器对象
- 踩坑 3：`graph.get_state().next` 是 tuple，用 `"review" in state.next` 判断

**两层 SQLite 严格分离：**
- `graph_state.db`：LangGraph SqliteSaver 独占，固定 schema，存状态快照，不能混用
- `history.db`：业务层，存最终日报记录，应用代码控制 schema
- 混用会破坏 LangGraph 序列化格式，导致 resume 失败

**Streamlit rerun 保护：**
```python
@st.cache_resource          # graph 对象跨 rerun 同一实例
def get_graph(): ...

if "thread_id" not in st.session_state:  # thread_id 只初始化一次
    st.session_state.thread_id = str(uuid.uuid4())
```

**三重循环守卫 — 防止无限修改：**
1. `state.get("revision_count", 0)` 安全访问，默认 0
2. 条件边：`count >= 3 → save`（跳过 review 直接保存）
3. approve 路径：直接跳到 save，不经过计数

### 架构亮点

**TemplateRouterAgent 子图 — 两步推理：**
```
analyze_content_node (提取技术/业务内容比例)
       ↓
decide_template_node (基于特征决策模板类型)
```
- 两步 chain-of-thought 比单次决策准确率更高
- 独立的 `RouterState`，与主图完全解耦，内部实现可随时替换
- 对比 Supervisor 模式：子图是静态组合，每次都执行，适合封装复杂子流程

**完整状态机流转：**
```
START
  → extract (with_structured_output 结构化提取)
  → enrich (git log + 数据指标提取)
  → route_template (调用子图分类)
  → draft (按模板生成初稿)
  → polish (老板视角润色，可接收人工反馈)
  → review (interrupt 暂停)
  ↙ approve        ↘ revise
save               revise_node (count+1) → polish (循环，最多3次)
  ↓
END
```

**模板扩展性：**
- 加第 4 种模板只需改 4 处：`draft.py`, `router/agent.py`, `route_template.py`, `tests`
- 其他层对模板类型透明，松耦合设计

**安全意识：**
- git 路径用 `pathlib.Path.resolve()` 规范化，防止路径遍历攻击

### 已知 Bug / 技术债

**P0（应该修的）：**
- LLM 调用没有重试——API 限流或超时时直接报错，无任何保护
- TemplateRouterAgent 没有系统评测——分类准确率没有量化指标

**P1（设计缺陷）：**
- **Inline edit 数据不一致**：用户在 UI 编辑的内容只存在 `session_state`，没有传回图，`history.db` 里存的是未编辑版本
- **Revision feedback 被覆盖**：多轮修改时新 feedback 覆盖旧 feedback，第一次修改意见可能被遗忘
- **进度条是假的**：`st.status` 里的节点标签在 `invoke()` 之前全部写出，不是实时更新
- **时区 bug（隐藏）**：`enrich.py` 里 `datetime.combine(date.today(), ...).isoformat()` 无时区信息，云部署 UTC 服务器 + UTC+8 用户时会漏掉当天早晨的 commits

### TDD 策略

- 33 个测试，5 个文件覆盖全部阶段
- LLM mock 必须返回真实 Pydantic 对象，不能用 MagicMock（checkpointer 无法序列化）
- HITL 循环测 3 条路径：直接 approve / revise 一次后 approve / 连续 3 次 revise 强制保存

### Idea 亮点

- **"老板视角"作为独立节点**：把视角转换从生成中解耦，polish 节点可以被任何 draft 复用
- **整合 git log**：工程师的工作描述本来就在 commit 里，用代码历史辅助日报是自然的
- **口语 → 专业**：target 用户是每天需要写日报但不知道怎么写得好看的工程师

### 面试表述建议

> "这个项目的核心技术挑战是 Human-in-the-Loop 的完整实现。LangGraph 的 interrupt() 会抛出 GraphInterrupt 异常，runtime 把完整的图状态序列化到 SqliteSaver，图暂停。用户在 Streamlit 审阅后，用 Command(resume=...) 加同一个 thread_id 恢复。有三个坑踩过：GraphInterrupt 不能被 except Exception 吞掉、SqliteSaver 要用 with 语法、get_state().next 是 tuple。"
>
> "两个 SQLite 文件的分离也是刻意设计的——graph_state.db 是 LangGraph 独占的，schema 固定，混入业务数据会破坏序列化。"

---

## 三个项目横向对比

| | 桌面动物园 | Debate Agent | WorkDiary Agent |
|---|---|---|---|
| **核心难点** | PyQt6 + LangGraph 融合 | 多 Agent 分歧检测设计 | HITL interrupt/resume |
| **最大亮点** | 自然语言控制桌面，体验新颖 | 置信度公式 + PROHIBITION 反 sycophancy | 完整 HITL 工程实现 |
| **工程成熟度** | 中 | 高 | 高 |
| **面试差异化** | 产品 idea | 系统设计思维 | LangGraph 深度 |
| **LangGraph 用法** | 基础（5节点线性+反思） | 进阶（Send 并行 + fan-in） | 高级（interrupt/resume + subgraph） |
| **共同技术** | LangGraph + Claude API + Pydantic | | |

### 三个项目共同的设计原则

1. **不信任 LLM 做关键决策**：桌面动物园用 reflect 节点兜底，debate-agent 用代码公式计算置信度，workdiary 用条件边强制循环上限
2. **状态机显式建模**：三个项目都选择 LangGraph 的显式状态机，而不是隐式对话链
3. **失败有降级路径**：宠物支持无 AI 模式，debate-agent 有 sentinel 对象，workdiary 有修改上限保护

---

*本文档由 Claude Code 整理，后续优化和新发现持续追加至各项目节的末尾。*
