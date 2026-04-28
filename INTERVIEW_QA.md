# 智能日报 Agent — 面试题库

> 格式参考 Peppr Ava 题库：每题包含考查点、代码实际方案、理想方案/进步空间、如何表述、亮点/瓶颈、突出能力，以及层层追问。
> 核心原则：**主动暴露复杂度，主动说出进步空间，而不是等面试官追问。**

---

## 项目一句话定位

> "基于 LangGraph 的 Multi-Agent 系统，将口语化工作描述自动转化为老板视角的日报，核心亮点是完整实现了带状态持久化的 Human-in-the-Loop interrupt/resume 循环。"

---

## Q1：你的 HITL interrupt/resume 是怎么实现的？用户审阅期间图的状态存在哪里？

*（也可能被问成：LangGraph 的 interrupt 机制是怎么工作的？Streamlit rerun 之后图的状态会丢失吗？）*

### 面试官想听到的
考查点：**LangGraph HITL 机制的深度理解 + 状态持久化设计**。想知道你不只是"用了 interrupt"，而是清楚整个链路的时序和存储方式。

### 代码中的实际方案

**interrupt() 怎么工作的**

`workdiary_agent/nodes/review.py`：
```python
response = interrupt({
    "polished": state.get("polished"),
    "revision_count": state.get("revision_count", 0),
})
decision = response.get("decision", "approve")
feedback = response.get("feedback", "")
return {"human_decision": decision, "human_feedback": feedback}
```

`interrupt(payload)` 在节点内部调用时，抛出 `GraphInterrupt` 异常。LangGraph runtime 捕获这个异常，把完整的 `AgentState` 序列化到 `SqliteSaver`（`graph_state.db`），然后让 `graph.invoke()` 返回。此时 `graph.get_state(config).next == ("review",)`，图处于暂停状态。

恢复时：`graph.invoke(Command(resume={"decision": "approve", "feedback": "..."}), config)`，LangGraph 从 `graph_state.db` 加载状态，`interrupt()` 这次返回 `Command.resume` 的值，节点继续执行。

**Streamlit 层的状态管理**

`app.py`：
```python
@st.cache_resource
def get_graph():
    return build_graph(use_sqlite=True)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
```

`@st.cache_resource` 保证 graph 对象跨 rerun 保持同一个实例；`thread_id` 存在 `session_state` 里，用 `not in` guard 保证只初始化一次。

**两层持久化的分工**：
- `graph_state.db`：LangGraph 独占，存储 interrupt 时的完整 AgentState
- `st.session_state`：存储 UI 层状态（app_state、result、thread_id）
- 两者通过 `thread_id` 关联，Streamlit rerun 后两层都能恢复

### 踩过的三个坑

1. **`GraphInterrupt` 是 `Exception` 的子类**（继承链：`GraphInterrupt → GraphBubbleUp → Exception`）。如果 `interrupt()` 外面有 `except Exception:`，会把它静默吞掉，图不会暂停，直接跑穿。**解决：interrupt() 周围绝不加 try/except。**

2. **`SqliteSaver.from_conn_string()` 是 `@contextmanager`**，不能直接赋值。不加 `with` 语句返回的是 `_GeneratorContextManager`，`compile()` 时报 `TypeError`。**解决：`workdiary_agent/graph.py` 中用 `sqlite3.connect()` 直接传连接对象。**

3. **`graph.get_state(config).next` 返回的是 tuple**，不是 list。用 `== ["review"]` 判断会永远为 False。**解决：用 `"review" in state.next`。**

### 如何对面试官表述
> "interrupt() 在 review 节点内部调用，抛出 GraphInterrupt 异常，LangGraph 把完整 AgentState 序列化到 SQLite，图暂停。用户审阅期间状态安全地存在磁盘上，不会因为 Streamlit rerun 丢失。恢复时用同一个 thread_id 调用 Command(resume=...)，LangGraph 从 SQLite 加载状态继续执行。
>
> 踩过三个坑：GraphInterrupt 是 Exception 子类不能被 catch；SqliteSaver.from_conn_string() 是 context manager 不能直接用；get_state().next 是 tuple 不是 list。"

### 亮点
- 说清楚了两层持久化的分工（graph_state.db vs session_state），不只是说"存了状态"
- 主动说出三个坑，证明是真实踩过的

### 瓶颈
- `graph_state.db` 用相对路径，多用户场景会冲突（单用户工具可以接受）
- SqliteSaver 不支持并发写，高并发场景需要换 PostgreSQL checkpointer

### 突出的能力
**LangGraph HITL 机制的深度理解** + **状态持久化的分层设计**

---

**追问：用户在审阅期间关掉了浏览器，下次打开还能继续吗？**

**不能，因为 `thread_id` 存在 `session_state` 里，浏览器关掉后 session_state 清空，thread_id 丢失。**

虽然 `graph_state.db` 里的状态还在，但没有 thread_id 就找不回来。

**理想方案**：把 thread_id 持久化到 `history.db` 的 sessions 表，或者让用户登录后绑定到账号。但这个项目是单用户工具，当前设计合理——不需要跨浏览器恢复。

**对面试官表述：**
> "不能，thread_id 存在 session_state 里，浏览器关掉就丢了。graph_state.db 里的状态还在，但找不回来。如果要支持跨会话恢复，需要把 thread_id 持久化到数据库并和用户身份绑定。这个项目是单用户工具，当前设计是合理的权衡。"

---

## Q2：revision 循环最多 3 次，这个限制是怎么实现的？有几个守卫？

*（也可能被问成：如果用户一直拒绝，图会无限循环吗？怎么防止？）*

### 面试官想听到的
考查点：**状态机的边界条件设计**，能否说清楚防止无限循环的完整机制。

### 代码中的实际方案

**三个守卫协同工作**

**守卫一：安全的字段访问**（`workdiary_agent/nodes/revise.py`）
```python
count = state.get("revision_count", 0)  # 不用 state["revision_count"]
return {"revision_count": count + 1}
```
`AgentState` 是 `total=False` 的 TypedDict，`state["revision_count"]` 在字段未初始化时会 `KeyError`。用 `state.get()` + 默认值保证安全。

**守卫二：条件边路由**（`workdiary_agent/graph.py`）
```python
def route_after_revise(state: AgentState) -> Literal["polish", "save"]:
    count = state.get("revision_count", 0)
    return "save" if count >= 3 else "polish"

builder.add_conditional_edges(
    "revise",
    route_after_revise,
    {"polish": "polish", "save": "save"},
)
```
`revision_count >= 3` 时路由到 `save`，强制退出循环。

**守卫三：review 节点的路由**（`workdiary_agent/graph.py`）
```python
def route_after_review(state: AgentState) -> Literal["save", "revise"]:
    decision = state.get("human_decision", "approve")
    return "save" if decision == "approve" else "revise"
```
`approve` 直接到 `save`，跳过 revise 节点，不触发计数。

**完整循环路径**：
```
polish → review(interrupt) → [approve→save] 或 [revise→revise_node→route_after_revise→polish(count<3) 或 save(count>=3)]
```

### 如何对面试官表述
> "三个守卫协同工作：第一个是字段访问安全，用 state.get() 而不是 state[]，因为 total=False TypedDict 未初始化的键会 KeyError；第二个是 revise 节点的条件边，revision_count >= 3 时路由到 save 强制退出；第三个是 review 节点的条件边，approve 直接到 save 跳过计数。三个守卫缺一不可——少了任何一个都会有 bug。"

### 亮点
- 三个守卫有层次，不是单点保护
- 主动说出 total=False 的坑，证明理解 LangGraph 的状态设计

### 瓶颈
- 3 次上限是硬编码，不同场景最优值可能不同，可以做成配置项
- 第三次强制退出时用户没有明确确认，可能体验不够友好（可以在 save_node 里加提示）

### 突出的能力
**状态机边界条件设计** + **LangGraph TypedDict 的深度理解**

---

## Q3：TemplateRouterAgent 为什么做成子图而不是单个 LLM 调用？

*（也可能被问成：你的 Multi-Agent 架构是怎么设计的？为什么不用 supervisor 模式？）*

### 面试官想听到的
考查点：**Multi-Agent 架构的设计决策**，能否说清楚子图 vs 单节点的 trade-off，以及和 supervisor 模式的区别。

### 代码中的实际方案

`workdiary_agent/router/agent.py` 中独立编译的子图：
```python
_builder = StateGraph(RouterState)
_builder.add_node("analyze_content", analyze_content_node)
_builder.add_node("decide_template", decide_template_node)
_builder.add_edge(START, "analyze_content")
_builder.add_edge("analyze_content", "decide_template")
_builder.add_edge("decide_template", END)
_router_graph = _builder.compile()

class TemplateRouterAgent:
    def classify(self, raw_input: str, structured_info_text: str = "") -> str:
        result = _router_graph.invoke({...})
        return result.get("template_type", "混合型")
```

独立的 `RouterState(TypedDict, total=False)` 与主图的 `AgentState` 完全解耦。主图通过 `route_template_node` 调用，只关心输入输出接口。

**为什么两步走**：
- `analyze_content_node`：提取内容特征（有多少技术内容/业务内容）
- `decide_template_node`：根据特征决策模板类型

类似 chain-of-thought 的效果——先显式提取特征，再基于特征决策，比直接问"这是哪种模板"更准确，也更容易 debug（可以单独看 analyze 步骤的输出）。

**和 supervisor 模式的区别**：
- Supervisor 模式：一个 Agent 动态分派给多个 Worker，Worker 可以并行，适合任务分解
- 子图模式：静态组合，主图总是调用这个子图，适合封装复杂的子流程

这个项目用子图而不是 supervisor，因为路由逻辑是静态的——每次都需要分类，不需要动态决定是否调用。

### 如何对面试官表述
> "分两步是因为直接问'这是哪种模板'准确率不够高。先让一个节点提取内容特征，再让另一个节点基于特征决策，类似 chain-of-thought，效果更好也更容易 debug。
>
> 做成独立子图是为了解耦——有自己的 RouterState，主图只关心 classify() 接口，内部实现可以随时替换。这不是 supervisor 模式，而是静态的子图组合，因为路由逻辑每次都要执行，不需要动态分派。"

### 亮点
- 能区分子图和 supervisor 模式，说明对 Multi-Agent 架构有系统理解
- 两步走的设计有明确的准确率驱动

### 瓶颈
- 两步 LLM 调用比一步慢，增加了延迟和成本
- 分类准确率没有做系统评测，依赖 prompt 质量

**进步空间**：可以收集线上分类结果，用 LLM 做二次评判，统计各类型的准确率，形成自动化评测闭环（类似 Peppr 的菜单评估系统）。

### 突出的能力
**Multi-Agent 架构设计** + **分步推理的准确率意识**

---

**追问：如果分类出错了，用户选了错误的模板，怎么处理？**

**代码中已有完整的用户覆盖机制**（TMPL-03）：

`workdiary_agent/nodes/route_template.py`：
```python
if state.get("template_type") in {"技术型", "业务型", "混合型"}:
    return {"template_type": state["template_type"]}  # 尊重用户设置，跳过分类
```

`app.py` 中审阅 UI 提供模板显示（`st.caption(f"已选用{template_type}模板")`），用户看到后如果觉得不对，可以在「重新生成」时的反馈里说明，或者 v2 可以加模板切换按钮。

**对面试官表述：**
> "用户可以在审阅时看到'已选用XX模板'，如果觉得不对，在重新生成时的反馈里说明即可。代码里 route_template_node 会检查 state 里是否已有 template_type，有的话直接用，跳过自动分类——这样用户的选择永远优先于 AI 的判断。"

---

## Q4：history.db 和 graph_state.db 为什么要分开？混用会怎样？

*（也可能被问成：你的持久化架构是怎么设计的？为什么用两个 SQLite 文件？）*

### 面试官想听到的
考查点：**持久化架构的边界设计**，能否说清楚框架层和应用层的职责分离。

### 代码中的实际方案

**`graph_state.db`**（LangGraph 独占）：
- 由 `SqliteSaver` 管理，有自己的 schema（checkpoints 表、checkpoint_writes 表、checkpoint_blobs 表）
- 存储图的完整状态快照，用于 interrupt/resume
- 应用代码从不直接操作这个文件

**`history.db`**（应用层独占）：
- 由 `workdiary_agent/storage/sqlite.py` 管理
- 存储业务数据：日期、模板类型、原始输入、polished 内容
- `workdiary_agent/nodes/save.py` 是唯一写入点

`workdiary_agent/storage/sqlite.py` 里明确注释：
```python
DB_PATH = "history.db"
# history.db 是应用层数据库，与 LangGraph 的 graph_state.db 完全独立
```

**为什么必须分开**：
- Schema 冲突：LangGraph 的 checkpointer 有固定的表结构，应用代码往里写会破坏序列化格式，导致 interrupt/resume 失败
- 职责分离：将来备份历史日报、迁移数据库、清理 LangGraph 状态，需要能独立操作两个文件
- 这个决策在 Phase 1 设计时就确定，写在 `STATE.md` 的 Decisions 里，后面没有返工

### 如何对面试官表述
> "graph_state.db 是 LangGraph 的 SqliteSaver 独占管理的，有自己的 schema，存储图的状态快照用于 interrupt/resume。如果应用代码往里写东西，会破坏 LangGraph 的序列化格式，下次 resume 时会报错。
>
> history.db 是应用层的业务数据，schema 由我们控制。两个文件完全独立，将来备份日报、清理 LangGraph 状态都可以单独操作。这个决策在 Phase 1 就定下来了，是架构层面的约束，不是实现细节。"

### 亮点
- 说清楚了混用的具体后果（序列化格式被破坏），而不只是说"会出问题"
- 强调这是 Phase 1 的架构决策，体现了前期设计的意识

### 瓶颈
- 两个 SQLite 文件都用相对路径，生产环境应该用绝对路径或配置项
- 没有数据库迁移机制，表结构变更需要手动处理

### 突出的能力
**框架层与应用层的边界意识** + **前期架构决策的系统性**

---

## Q5：Streamlit 每次 rerun 都会重新执行整个 Python 文件，你怎么保证图不会重启？

*（也可能被问成：session_state 的管理策略是什么？SC-5 是怎么保证的？）*

### 面试官想听到的
考查点：**Streamlit + LangGraph 集成的核心难点**，能否说清楚 rerun 机制和状态保护策略。

### 代码中的实际方案

`app.py` 中两层保护：

**第一层：`@st.cache_resource` 缓存 graph 对象**
```python
@st.cache_resource
def get_graph():
    return build_graph(use_sqlite=True)
```
`@st.cache_resource` 是 Streamlit 的全局资源缓存，跨 rerun、跨用户共享同一个实例。`build_graph()` 只在第一次调用时执行，后续 rerun 直接返回缓存的对象。

**第二层：`not in` guard 保护 session_state**
```python
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "app_state" not in st.session_state:
    st.session_state.app_state = "idle"
if "result" not in st.session_state:
    st.session_state.result = None
```
每个状态字段都用 `not in` 判断，只在第一次访问时初始化，rerun 时直接跳过。

**容易犯的错误**：
```python
# 错误写法1：每次 rerun 都重新创建 graph
graph = build_graph(use_sqlite=True)  # 没有 @st.cache_resource

# 错误写法2：每次 rerun 都生成新 thread_id
st.session_state.thread_id = str(uuid.uuid4())  # 没有 not in 判断
```
这两种错误都会导致每次 rerun 都开始一个全新的图执行，interrupt 状态丢失。

### 如何对面试官表述
> "Streamlit 每次 rerun 都重新执行整个 Python 文件，所以必须两层保护：graph 对象用 @st.cache_resource 缓存，只创建一次，跨 rerun 保持同一个实例；thread_id 用 not in guard 保证只初始化一次，rerun 时直接跳过。两个错误最容易犯：一是 build_graph() 没有缓存，每次 rerun 都重建；二是 thread_id 每次都重新生成，interrupt 状态就找不回来了。"

### 亮点
- 不只说"用了 session_state"，而是说清楚了两层保护的具体机制
- 主动说出容易犯的错误，证明是真实踩过的

### 瓶颈
- `@st.cache_resource` 是全局共享的，多用户场景下所有用户共享同一个 graph 实例，需要靠 thread_id 区分（当前单用户工具可以接受）
- Streamlit 没有官方的 LangGraph 集成文档，这些模式都是实验出来的

### 突出的能力
**Streamlit rerun 机制的深度理解** + **状态保护的分层设计**

---

## Q6：enrich 节点的 git log 读取有什么安全问题？你怎么处理的？

*（也可能被问成：用户输入的 git 路径你们有做校验吗？有没有路径遍历风险？）*

### 面试官想听到的
考查点：**安全意识**，能否主动识别用户输入带来的安全风险并说出处理方案。

### 代码中的实际方案

**修复前的代码**（`workdiary_agent/nodes/enrich.py` 原始版本）：
```python
def _read_git_log(repo_path: str) -> str | None:
    if not repo_path:
        return None
    try:
        repo = git.Repo(repo_path)  # 直接用用户输入，有路径遍历风险
```

**修复后**（`workdiary_agent/utils.py`）：
```python
def validate_repo_path(repo_path: str) -> str | None:
    if not repo_path or not repo_path.strip():
        return None
    try:
        resolved = Path(repo_path).expanduser().resolve()
        if not resolved.exists():
            return None
        if not resolved.is_dir():
            return None
        return str(resolved)
    except (OSError, ValueError):
        return None
```

`enrich_node` 中先调用 `validate_repo_path()`，返回 None 则跳过 git 读取：
```python
safe_path = validate_repo_path(repo_path)
if not safe_path:
    return None
repo = git.Repo(safe_path)
```

**`pathlib.Path.resolve()` 的作用**：
- 展开 `~`（`expanduser`）
- 解析 `..`（防止 `../../etc/passwd` 类型的路径遍历）
- 转为绝对路径
- 验证路径实际存在且是目录

### 如何对面试官表述
> "用户输入的路径如果不校验，有路径遍历风险——比如输入 '../../sensitive_dir' 可能访问到不该访问的目录。我用 pathlib.Path.resolve() 规范化路径，它会展开 ~ 和解析 ..，转成绝对路径后再验证是否存在且是目录。这个修复是在代码审查时发现的，原始代码直接把用户输入传给 git.Repo()。"

### 亮点
- 主动识别安全问题，而不是等面试官问
- 说清楚了 resolve() 的具体作用，不只是说"做了校验"

### 瓶颈
- 只校验了路径的合法性，没有限制路径的范围（比如只允许访问用户主目录下的路径）
- GitPython 本身的安全性依赖版本，没有做版本锁定的安全审查

### 突出的能力
**安全意识** + **用户输入的防御性处理**

---

## Q7：你的测试策略是什么？LLM 调用怎么测？HITL 循环怎么测？

*（也可能被问成：怎么保证 AI 系统的代码质量？测试覆盖了哪些场景？）*

### 面试官想听到的
考查点：**AI 系统的测试策略**，能否说清楚 LLM mock 的方法和集成测试的设计。

### 代码中的实际方案

**TDD 驱动**：每个 Phase 先写 RED 测试，再写实现，再看 GREEN。33 个测试，覆盖全部 Phase 的验收标准。

**LLM 调用的 mock 策略**

所有 LLM 调用通过 `make_llm()` 工厂函数（`workdiary_agent/utils.py`）创建，测试中在使用处 patch：
```python
# tests/test_phase04_hitl.py
def _mock_all_llm_nodes():
    return [
        patch("workdiary_agent.nodes.extract.make_llm", return_value=_make_llm_mock()),
        patch("workdiary_agent.nodes.draft.make_llm", return_value=_make_llm_mock("【已选用混合型模板】\n...")),
        patch("workdiary_agent.nodes.polish.make_llm", return_value=_make_llm_mock("polished content")),
        patch("workdiary_agent.nodes.enrich.make_llm", return_value=_make_llm_mock()),
        patch("workdiary_agent.nodes.route_template.TemplateRouterAgent.classify", return_value="混合型"),
    ]
```

mock 的 `_make_llm_mock()` 返回真实的 `StructuredInfo` Pydantic 对象（不是 MagicMock），因为 LangGraph 的 msgpack checkpointer 无法序列化 MagicMock，会导致 interrupt/resume 测试失败。

**HITL 循环的测试**

`tests/test_phase04_hitl.py` 中测试 3 条路径：
```python
def test_approve_path():
    with mocks:
        result = graph.invoke({"raw_input": "..."}, config)
        assert "review" in graph.get_state(config).next  # SC-1: 暂停在 review

        result2 = graph.invoke(Command(resume={"decision": "approve", "feedback": ""}), config)
        assert not graph.get_state(config).next  # SC-2: 到达 END

def test_force_exit_after_3_revisions():
    # 连续 revise 3 次，第 4 次不再 interrupt
```

**独立验证脚本**（ROADMAP SC-5 要求）：
`scripts/test_hitl_cycle.py` 用 `InMemorySaver`（不写磁盘），跑 3 条路径的真实调用，最终输出 `ALL 3 PATHS PASSED`。

**为什么 mock 而不是真实调用**：
- 速度：每次测试省几十秒
- 成本：省 token
- 可重复性：LLM 输出不稳定，不能作为断言基准

### 如何对面试官表述
> "TDD 驱动，33 个测试覆盖全部 Phase。LLM 调用全部 mock，在使用处 patch make_llm()——这里有个细节：mock 返回的必须是真实的 Pydantic 对象，不能是 MagicMock，因为 LangGraph 的 checkpointer 序列化时会失败。
>
> HITL 循环专门有 3 条路径的集成测试：直接 approve、revise 一次后 approve、连续 3 次 revise 强制退出。还有独立的验证脚本调用真实 LLM，但只在手动验收时跑，不进 CI。"

### 亮点
- mock 策略有工程细节（Pydantic 对象 vs MagicMock），证明是真实踩过的
- HITL 循环的 3 条路径都有覆盖，不只测 happy path

### 瓶颈
- 没有 prompt 质量的自动化评测（输出是否"老板爱看"），这是 AI 系统测试的难点
- 测试只覆盖了功能正确性，没有性能测试（LLM 延迟、并发等）

**进步空间**：可以参考 Peppr 的评测系统，构建一套日报质量评测：用 LLM 判断生成的日报是否符合"老板视角"的标准，统计不同类型输入的质量分布。

### 突出的能力
**AI 系统测试策略** + **LangGraph 序列化机制的深度理解**

---

## Q8：`_make_llm()` 在 5 个文件里重复定义，你是怎么发现并重构的？

*（也可能被问成：代码里有什么你觉得不够好的地方？复盘时发现了什么问题？）*

### 面试官想听到的
考查点：**代码质量意识和重构能力**，能否主动识别问题并说清楚重构的影响范围。

### 代码中的实际方案

**重构前**：`_make_llm()` 在 5 个文件里各有一份完全相同的实现：
- `workdiary_agent/nodes/extract.py`
- `workdiary_agent/nodes/enrich.py`
- `workdiary_agent/nodes/draft.py`
- `workdiary_agent/nodes/polish.py`
- `workdiary_agent/router/agent.py`

**重构后**：提取到 `workdiary_agent/utils.py`，公开名为 `make_llm()`（去掉下划线，变成公共 API）：
```python
def make_llm() -> ChatAnthropic:
    """Return ChatAnthropic with custom headers from ANTHROPIC_CUSTOM_HEADERS env var."""
    ...
```

各节点改为 `from ..utils import make_llm`，调用处改为 `llm = make_llm()`。

**重构的连锁影响**：测试文件里的 mock 路径也需要更新，从 `workdiary_agent.nodes.extract._make_llm` 改为 `workdiary_agent.nodes.extract.make_llm`（在使用处 patch，不是在定义处 patch）。

**净效果**：删除 131 行重复代码，新增 69 行，净减 62 行。

### 如何对面试官表述
> "项目完成后做了一次代码审查，发现 _make_llm() 在 5 个文件里各有一份完全相同的实现。这是项目快速迭代的副产品——每个 Phase 的 executor agent 独立实现节点，各自复制了这个 helper。
>
> 重构时有两个注意点：一是函数名从 _make_llm 改成 make_llm，因为它现在是公共 API；二是测试文件里的 mock 路径要同步更新，因为 Python 的 patch 是在使用处拦截，不是在定义处。最终净减 62 行代码，测试全部通过。"

### 亮点
- 说清楚了重构的连锁影响（mock 路径），证明理解 Python 的 patch 机制
- 说出了重复出现的原因（多个 executor agent 独立实现），有自我反思

### 瓶颈
- 重构只解决了代码重复，没有解决 LLM 调用没有重试的问题
- `make_llm()` 每次调用都创建新实例，没有连接池或缓存，高频调用有开销

**进步空间**：可以在 `utils.py` 里加 LLM 调用的重试包装：
```python
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10),
       retry=lambda e: isinstance(e, anthropic.APIError))
def invoke_with_retry(llm, messages):
    return llm.invoke(messages)
```

### 突出的能力
**代码质量意识** + **重构的影响范围分析**

---

## Q9：TemplateRouterAgent 的分类准确率是多少？你怎么评估的？

*（也可能被问成：你怎么知道模板分类是准确的？有没有做过评测？）*

### 面试官想听到的
考查点：**AI 系统评测意识**，能否主动说出评测的缺失并提出改进方案。

### 代码中的实际方案

**实际情况：没有系统评测。**

分类准确率完全依赖 prompt 质量（`workdiary_agent/router/agent.py` 中的 `_ANALYZE_SYSTEM` 和 `_DECIDE_SYSTEM`），没有测试集，没有量化指标。

Phase 4 的集成测试中用了 mock（`TemplateRouterAgent.classify` 返回固定值 "混合型"），所以测试覆盖不了真实的分类质量。

**唯一的验证**是 Phase 2 的端到端 smoke test：
```python
tech_result = router.classify("今天实现了Redis缓存层，优化了SQL查询，修复了内存泄漏，写了单元测试")
assert tech_result == "技术型"
```
3 个样本，不具有统计意义。

### 理想方案（如果要做评测）

**第一步：构建测试集**

收集或构造 30-50 条有标注的工作描述样本，覆盖 3 种类型和边界情况：
```python
test_cases = [
    {"input": "今天优化了 SQL 查询，响应时间从 200ms 降到 45ms", "expected": "技术型"},
    {"input": "今天和客户对齐了 Q2 目标，GMV 增长 15%", "expected": "业务型"},
    {"input": "完成了支付接口优化，降低超时率，同时跟进了商务合同", "expected": "混合型"},
    # 边界：技术工作有业务影响
    {"input": "今天修复了登录 bug，影响了 3000 个用户", "expected": "?"},
]
```

**第二步：自动化评测**

```python
results = []
for case in test_cases:
    predicted = router.classify(case["input"])
    results.append({"expected": case["expected"], "predicted": predicted, "correct": predicted == case["expected"]})

accuracy = sum(r["correct"] for r in results) / len(results)
print(f"准确率: {accuracy:.1%}")
# 按类型分析
for template_type in ["技术型", "业务型", "混合型"]:
    subset = [r for r in results if r["expected"] == template_type]
    type_acc = sum(r["correct"] for r in subset) / len(subset)
    print(f"{template_type}: {type_acc:.1%}")
```

**第三步：bad case 分析**

对分类错误的样本，用 LLM 分析根因：是 prompt 对某类型的描述不够清晰，还是样本本身就是边界情况？

### 如何对面试官表述
> "坦白说，分类准确率没有做系统评测，是这个项目的明显缺口。目前只有 3 个样本的 smoke test，不具有统计意义。如果要完善，应该构建 30-50 条有标注的样本，按 3 种类型分别统计准确率，对 bad case 做根因分析，看是 prompt 的问题还是边界情况。这是 v2 要补的工作。"

### 亮点
- 主动承认缺口，而不是回避
- 提出了具体的改进方案，而不是说"以后再做"

### 瓶颈
- 混合型和技术型/业务型的边界本身就模糊，即使有评测，人工标注也会有分歧
- 评测结果是离线的，不能反映真实用户输入的分布

### 突出的能力
**AI 系统评测意识** + **主动识别技术债的诚实度**

---

## Q10：这个项目有什么你觉得还不够好的地方？如果再做一次你会怎么改？

*（也可能被问成：项目最大的技术债是什么？生产就绪度如何？）*

### 面试官想听到的
考查点：**自我认知和技术判断力**，面试官不想听"没有问题"，主动暴露问题比被追问出来要好。

### 代码中的实际情况

**P0（应该修但没修的）：**

**1. LLM 调用没有重试**
`make_llm().invoke()` 直接调用，API 限流或超时时直接报错，没有任何保护。生产环境不可接受。

**2. TemplateRouterAgent 没有评测**（见 Q9）

**P1（有进步空间的）：**

**3. Streamlit 是同步阻塞的**
用户点「生成日报」后，整个 UI 冻结直到图执行完（通常 10-30 秒）。体验不好。v2 可以用异步 + streaming 改善。

**4. 错误信息对用户不友好**（已修复）
原始代码 `st.error(f"图执行出错: {e}")` 直接暴露系统内部信息。已改为通用提示 + `logging.exception()` 记录详情。

**如果再做一次会怎么改**

**架构层面**：
- Phase 1 就把 `make_llm()` 放在 `utils.py`，不让每个 executor agent 各自复制
- 更早引入 prompt 版本管理（每个 prompt 有 ID，方便追踪哪个版本的问题）

**功能层面**：
- 在 Streamlit 里加 streaming 输出，让用户看到日报逐步生成
- 加 LLM 调用的重试和超时控制

### 如何对面试官表述
> "有三个明显的技术债：第一，LLM 调用没有重试，API 限流时直接崩，生产环境不行；第二，模板分类没有评测，准确率未知；第三，Streamlit 同步阻塞，生成期间 UI 冻结，体验差。
>
> 如果再做一次，我会在 Phase 1 就把 make_llm() 放在 utils.py，因为我知道每个节点都会用到它。这次是因为 executor agent 独立实现各节点，最后才发现重复——这是多 agent 并行开发的副产品，下次会在 Phase 1 的架构设计里预先规划共享工具层。"

### 亮点
- 说出了具体的技术债，而不是泛泛而谈
- 对"如果再做一次"有具体的改进点，而不是"会更认真"

### 瓶颈（坦诚的）
- 这是一个求职项目，时间约束下做了合理的权衡，生产就绪度不是首要目标

### 突出的能力
**技术判断力** + **自我认知的诚实度**

---

## 快问快答

| 问题 | 关键词 |
|------|--------|
| 用的什么模型？ | `claude-sonnet-4-5`，通过 `langchain-anthropic` 的 `ChatAnthropic` 调用，支持 `with_structured_output` |
| 结构化提取怎么做的？ | `llm.with_structured_output(StructuredInfo)`，直接返回 Pydantic 对象，不用手动解析 JSON |
| 为什么用 TypedDict 而不是 Pydantic 作为 State？ | LangGraph 推荐 TypedDict，`total=False` 让所有字段可选，`state.get()` 安全访问；Pydantic State 也支持但增加复杂度 |
| 怎么防止模板类型被用户覆盖后被重置？ | `route_template_node` 里检查 `state.get("template_type") in {"技术型","业务型","混合型"}`，已设置则直接返回，跳过子图分类 |
| 为什么 revise_node 只递增计数，不直接调用 polish LLM？ | 职责单一原则。revise 只负责"记录用户要修改"，polish 负责"重新生成"，两者解耦，polish 节点可以独立测试和替换 |
| `graph.get_state().next` 是什么类型？ | tuple，不是 list。用 `"review" in state.next` 判断，不要用 `== ["review"]` |
| SqliteSaver 怎么初始化？ | `conn = sqlite3.connect("graph_state.db", check_same_thread=False); checkpointer = SqliteSaver(conn)`，不能用 `from_conn_string()` 不加 `with` |
| 项目用了几天？ | 约 2 天完成全部 6 个 Phase，包括设计、实现、测试、UI |

---

*最后更新：2026-04-28*
