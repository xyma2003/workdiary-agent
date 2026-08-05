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

## Q11：用户第二次点「重新生成」时，第一次的 human_feedback 还在 state 里吗？会影响第二次的 polish 吗？

*（也可能被问成：多轮 revise 循环中，feedback 是累积的还是覆盖的？）*

### 面试官想听到的
考查点：**多轮状态管理的细节**，能否追踪 human_feedback 在循环中的生命周期，以及 LangGraph 的状态更新语义。

### 代码中的实际方案

**状态更新是 merge，不是替换**

LangGraph 节点返回的 dict 是**部分更新**，只更新返回的字段，不清空其他字段。

`review_node`（`workdiary_agent/nodes/review.py:42`）：
```python
return {"human_decision": decision, "human_feedback": feedback}
```

第一次 revise：`human_feedback = "请加强量化指标"`，写入 state。

Polish 节点读取并用掉这个 feedback，生成新的 `polished`。

第二次 review 暂停，用户输入新 feedback `"语气太正式，改得自然一点"`，调用：
```python
Command(resume={"decision": "revise", "feedback": "语气太正式，改得自然一点"})
```

review_node 返回 `{"human_decision": "revise", "human_feedback": "语气太正式，改得自然一点"}`，**覆盖**了第一次的 feedback。

**所以：feedback 是覆盖，不是累积。**

`polish_node`（`workdiary_agent/nodes/polish.py:54-56`）每次只读当前 state 中的 `human_feedback`，不会看到历史的 feedback。

### 这个设计的隐患

**场景**：用户第一次说"加量化指标"，第二次说"语气自然一点"。第二次 polish 时，第一次的"加量化指标"这个需求就被覆盖了，LLM 可能不再关注量化指标。

**代码中没有处理这个问题**。

### 理想方案

两个选项：

**选项一：累积 feedback（追加而非覆盖）**
```python
# review_node 中
existing_feedback = state.get("human_feedback", "")
new_feedback = response.get("feedback", "")
combined = f"{existing_feedback}\n{new_feedback}".strip() if existing_feedback else new_feedback
return {"human_decision": decision, "human_feedback": combined}
```

**选项二：在 polish 的 HumanMessage 里注入 feedback 历史**
```python
# polish_node 中
feedback_history = state.get("feedback_history", [])  # 新增字段
if human_feedback:
    context = f"历史修改意见：\n" + "\n".join(f"- {f}" for f in feedback_history)
    context += f"\n本次修改意见：{human_feedback}"
```

当前实现选了最简单的方案（覆盖），对大多数场景够用，但面试时要主动说出这个 trade-off。

### 如何对面试官表述
> "LangGraph 的状态更新是 merge 语义，节点返回的 dict 只更新对应字段，不清空其他字段。但 review_node 每次都写 human_feedback 字段，所以是覆盖而不是累积。第二次 revise 时，第一次的 feedback 就丢了。
>
> 这个设计对大多数场景够用——用户通常每次只关注一个问题。但如果用户的两次 feedback 是正交的需求，第二次 polish 可能忽略第一次的要求。改进方案是把 feedback 改成列表字段累积，或者在 polish 的 prompt 里注入所有历史 feedback。"

### 亮点
- 说清楚了 LangGraph 状态更新的 merge 语义，不只是说"会覆盖"
- 主动识别多轮场景下的信息丢失问题

### 瓶颈
- 累积 feedback 会让 prompt 越来越长，多轮后可能超过 token 限制
- 用户可能不希望历史 feedback 影响当前这次——覆盖有时反而是正确的

### 突出的能力
**LangGraph 状态语义的深度理解** + **多轮对话中的信息保持设计**

---

**追问：用户 inline 编辑了日报内容后点「重新生成」，编辑会丢失吗？**

**会丢失，这是一个设计缺陷。**

`app.py:207-208`：
```python
if st.button("↻ 重新生成", use_container_width=True, key="revise_btn"):
    st.session_state._show_feedback = True
    # 注意：没有保存 session_state["edit_area"] 的内容
```

用户在 `edit_area` 里做的修改存在 `session_state["edit_area"]`，但点「重新生成」时没有把它存起来。`Command(resume={"decision": "revise", ...})` 之后图重新跑 polish，返回全新的 `polished`，覆盖掉 `session_state.result["polished"]`，用户的编辑就丢失了。

**修复方案**：在点「重新生成」时，把 `edit_area` 的内容作为额外的 feedback 传进去：
```python
if st.button("↻ 重新生成"):
    edited = st.session_state.get("edit_area", "")
    original = result.get("polished", "")
    if edited != original:
        # 用户有编辑，把编辑内容作为 feedback 的一部分
        st.session_state._pending_edit = edited
    st.session_state._show_feedback = True
```

---

## Q12：`st.status` 里的节点标签是在图执行前就全部写出来的，这意味着什么？

*（也可能被问成：用户看到的进度标签是实时的吗？如果某个节点失败了，标签会显示错误吗？）*

### 面试官想听到的
考查点：**Streamlit 执行模型的理解**，以及流式 UI vs 批量 UI 的设计权衡。

### 代码中的实际方案

`app.py:110-114`：
```python
with st.status("正在生成日报...", expanded=True) as status_ui:
    for label in NODE_LABELS.values():
        st.write(label)           # ← 在 invoke() 之前把所有标签全写出来

    try:
        result = get_graph().invoke(...)   # ← 阻塞调用，图在这里执行
```

**这意味着**：所有节点标签（"正在提取信息..."、"正在润色..."等）在图开始执行之前就已经渲染完了。用户看到的是一个静态的标签列表，不是节点逐一完成时的实时更新。

**视觉效果**：用户点击「生成日报」后，立刻看到所有标签同时出现，然后等待图执行完成。这不是真正的进度条，而是"预告"。

**为什么这样设计**：`graph.invoke()` 是同步阻塞调用，执行期间 Streamlit 无法更新 UI（Python 单线程）。要做真正的实时进度更新，需要用 `graph.stream()` + `st.empty()` 的异步模式。

### 理想方案（真正的实时进度）

```python
with st.status("正在生成日报...", expanded=True) as status_ui:
    progress_placeholder = st.empty()

    for chunk in get_graph().stream({"raw_input": raw_input, ...}, config):
        # chunk 是 {节点名: 节点输出} 的字典
        node_name = list(chunk.keys())[0]
        label = NODE_LABELS.get(node_name, f"正在执行 {node_name}...")
        progress_placeholder.write(f"✓ {label}")

    status_ui.update(label="生成完成", state="complete")
```

`graph.stream()` 每个节点完成时 yield 一个 chunk，可以实现真正的逐节点进度更新。

**但 stream() 和 interrupt() 的配合有坑**：stream() 在遇到 interrupt 时会 yield 一个包含 `__interrupt__` 键的 chunk，然后停止。需要特殊处理这个 chunk 来检测暂停状态。

### 如何对面试官表述
> "当前的进度标签是在 invoke() 之前一次性全写出来的，不是实时更新的。因为 invoke() 是阻塞调用，执行期间 Streamlit 无法更新 UI。用户看到的是'预告'，不是真正的进度条。
>
> 要做真正的实时进度，需要换成 graph.stream()，每个节点完成时 yield 一个 chunk，再用 st.empty() 逐步更新。但 stream() 和 interrupt() 配合有额外的处理逻辑，复杂度更高，当前 scope 内没做。"

### 亮点
- 说清楚了"假进度条"的本质，而不是假装它是实时的
- 知道 stream() 的存在和使用场景

### 瓶颈
- 图执行期间（10-30秒）UI 完全冻结，用户体验差
- 没有超时机制，如果 LLM API 不响应，用户会一直等待

### 突出的能力
**Streamlit 执行模型的深度理解** + **流式 UI 的设计意识**

---

## Q13：git log 读取的时间范围是"今天"，但代码里 `datetime.min.time()` 是什么？有时区问题吗？

*（也可能被问成：如果服务器在 UTC，用户在中国，git log 会读到哪一天的 commits？）*

### 面试官想听到的
考查点：**时区处理的细节意识**，这是分布式系统和 AI 应用中的经典坑。

### 代码中的实际方案

`workdiary_agent/nodes/enrich.py:55-56`：
```python
today = datetime.combine(date.today(), datetime.min.time())
commits = list(repo.iter_commits(since=today.isoformat()))
```

**`datetime.min.time()` 是 `time(0, 0, 0)`**，即当天的 00:00:00。

**`today.isoformat()` 生成的字符串**：`"2026-04-28T00:00:00"`，**不含时区信息**。

**问题**：
- `date.today()` 返回的是**运行进程的本地时区**的日期
- `isoformat()` 生成的字符串不含时区，git 会用**系统时区**解释它
- 如果服务器在 UTC（0时区），用户在中国（UTC+8），`date.today()` 是 UTC 的今天
- 中国用户在 UTC+8 的 09:00 产生的 commit，对应 UTC 的 01:00，在 UTC 的"今天"里
- 但中国用户在 UTC+8 的 00:30（即 UTC 的前一天 16:30）产生的 commit，会被错误地排除

**实际影响**：在本地开发（服务器和用户同时区）时不会有问题。在云部署（服务器 UTC，用户 UTC+8）时，每天最早的 8 小时内的 commits 可能被错误读取或遗漏。

### 理想方案

```python
from datetime import datetime, date, timezone, timedelta

# 方案1：使用 UTC，让 git 统一用 UTC 解释
today_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
commits = list(repo.iter_commits(since=today_utc.isoformat()))

# 方案2：让用户指定时区（更精确）
user_tz = timezone(timedelta(hours=8))  # 从配置读取
today_local = datetime.now(user_tz).replace(hour=0, minute=0, second=0, microsecond=0)
commits = list(repo.iter_commits(since=today_local.isoformat()))
```

### 如何对面试官表述
> "datetime.min.time() 是 time(0,0,0)，就是当天的零点。isoformat() 生成不含时区的字符串，git 用系统时区解释。
>
> 问题在于：如果服务器在 UTC，用户在中国 UTC+8，中国用户在凌晨 00:30 产生的 commit 对应 UTC 前一天 16:30，会被排除在'今天'之外。这是个真实的 bug，在本地开发时不会暴露，部署到云端才会出现。修复方案是用 timezone-aware 的 datetime，或者从配置读取用户时区。"

### 亮点
- 说清楚了 `datetime.min.time()` 的含义，不是模糊带过
- 给出了具体的 bug 复现场景（服务器 UTC + 用户 UTC+8 的边界情况）

### 瓶颈
- 即使修复了时区问题，"今天"的定义仍然取决于用户的时区设置，需要用户配置
- git 的 `--since` 参数的行为在不同版本可能有细微差异

### 突出的能力
**时区处理的细节意识** + **本地开发 vs 云部署的差异认知**

---

## Q14：`final_report` 和 `polished` 两个字段都存在，有什么区别？为什么不直接用一个？

*（也可能被问成：save_node 为什么要把 polished 复制到 final_report？）*

### 面试官想听到的
考查点：**状态字段设计的意图**，以及对 inline edit 场景下数据一致性的理解。

### 代码中的实际方案

`workdiary_agent/nodes/save.py:22, 32-34`：
```python
polished = state.get("polished", "") or ""
# ...
return {
    "final_report": polished,   # ← 复制
    "export_path": export_path,
}
```

`app.py:193-197`（inline edit 场景）：
```python
current_text = st.session_state.get("edit_area", polished)
if current_text != polished:
    st.session_state.result = dict(r)
    st.session_state.result["polished"] = current_text  # ← 覆盖 polished
else:
    st.session_state.result = dict(r)
```

**关键问题**：用户 inline 编辑后点「接受」时，代码修改的是 `session_state.result["polished"]`，但 `graph.invoke(Command(resume={"decision": "approve"}))` 触发的 `save_node` 用的是图内部 state 的 `polished`，不是 session_state 里的修改版本。

**所以**：`history.db` 里存的是**原始 polish 节点的输出**，不是用户编辑后的版本。`st.download_button` 导出的是编辑后的版本（`app.py:248`），但数据库里的是原版。

这是一个**数据不一致 bug**：用户编辑了内容并接受，但数据库里存的不是他们接受的版本。

### 理想方案

在 Streamlit 层，`approve` 时把编辑后的内容传回图：
```python
# 方案：通过 feedback 传递编辑内容
current_text = st.session_state.get("edit_area", polished)
if current_text != polished:
    # 把编辑后的内容通过 feedback 传回，让 save_node 用编辑版本
    r = get_graph().invoke(
        Command(resume={"decision": "approve", "feedback": "", "edited_content": current_text}),
        config,
    )
```
或者在 `save_node` 里优先读 `edited_content` 字段。

### 如何对面试官表述
> "final_report 是 save_node 的输出，polished 是 polish 节点的输出，save_node 把 polished 复制到 final_report 作为最终锁定版本。
>
> 但这里有个 bug：用户 inline 编辑后点接受，编辑内容只存在 session_state 里，没有传回图。save_node 用的还是图内部的 polished，所以 history.db 里存的是原始版本，不是用户编辑后的版本。导出的文件是编辑版，数据库里是原版，两个不一致。"

### 亮点
- 发现了 inline edit 场景下的数据不一致 bug
- 能追踪数据从 session_state 到 graph state 再到 history.db 的完整路径

### 瓶颈
- 修复这个 bug 需要改变 Command(resume=...) 的接口，或者在 save_node 里增加对 edited_content 的支持

### 突出的能力
**跨层数据一致性的追踪能力** + **HITL 流程中 UI 与图状态同步的深度理解**

---

## Q15：`add_conditional_edges` 的第三个参数是什么？如果路由函数返回了映射里不存在的值会怎样？

*（也可能被问成：conditional edge 的 mapping 参数有什么用？能不能省略？）*

### 面试官想听到的
考查点：**LangGraph API 的细节理解**，以及图拓扑设计的防御性思维。

### 代码中的实际方案

`workdiary_agent/graph.py:104-108`：
```python
builder.add_conditional_edges(
    "review",
    route_after_review,
    {"save": "save", "revise": "revise"},   # ← 第三个参数
)
```

**第三个参数是路由函数返回值到节点名的映射字典**。

`route_after_review` 返回字符串 `"save"` 或 `"revise"`，映射字典把这些字符串对应到图中的节点名称。

**为什么需要这个映射**：路由函数的"语言"（返回值）可以和图的节点名称解耦。比如路由函数可以返回 `"approve"` 和 `"reject"`，而图里的节点叫 `"save"` 和 `"revise"`，通过映射连接。

**如果路由函数返回了映射里不存在的值**：LangGraph 会抛出 `InvalidUpdateError` 或类似的运行时错误，图执行中断。

**代码中的防御**（`workdiary_agent/router/agent.py:66-68`）：
```python
valid_types = {"技术型", "业务型", "混合型"}
template_type = raw_type if raw_type in valid_types else "混合型"  # 归一化
```
TemplateRouterAgent 的 `decide_template_node` 在写入状态前做了归一化，防止无效值进入路由。

**但 `route_after_review` 没有这样的防御**：
```python
def route_after_review(state: AgentState) -> Literal["save", "revise"]:
    decision = state.get("human_decision", "approve")
    return "save" if decision == "approve" else "revise"
```
任何非 `"approve"` 的 decision 都会路由到 `"revise"`，包括 None、空字符串、非法值。这实际上是一种隐式的 fallback，但不够明确。

### 如何对面试官表述
> "第三个参数是映射字典，把路由函数的返回值映射到图中的节点名称。这允许路由逻辑和图拓扑解耦——路由函数说'approve'，图里的节点叫'save'，通过映射连接。
>
> 如果路由函数返回了映射里不存在的值，LangGraph 会在运行时报错。代码里 route_after_review 用了 else 兜底——任何非 approve 的值都路由到 revise，这是一个隐式的 fallback，能防止崩溃，但不够明确。更好的做法是显式处理所有可能的值，对非法输入记录日志或抛出明确的错误。"

### 亮点
- 说清楚了映射参数的解耦作用，不只是说"把返回值映射到节点"
- 发现了 `else` 兜底的隐式 fallback，并评价了它的优劣

### 瓶颈
- 第三个参数省略时，LangGraph 会尝试直接用路由函数的返回值作为节点名，更容易出错

### 突出的能力
**LangGraph API 细节理解** + **防御性编程意识**

---

## Q16：如果要加第 4 种模板（比如"总结型"），代码需要改哪些地方？哪些不需要改？

*（也可能被问成：你的模板系统扩展性如何？）*

### 面试官想听到的
考查点：**代码的松耦合设计**，能否快速定位扩展点，区分需要改和不需要改的部分。

### 代码中的实际方案

**需要改的（4处）**：

1. **`workdiary_agent/nodes/draft.py`**：添加新的 system prompt 字符串，加入 `_TEMPLATE_PROMPTS` 字典
```python
_SUMMARY_SYSTEM = """你是一个总结型日报撰写助手..."""
_TEMPLATE_PROMPTS = {
    "技术型": _TECH_SYSTEM,
    "业务型": _BIZ_SYSTEM,
    "混合型": _MIXED_SYSTEM,
    "总结型": _SUMMARY_SYSTEM,   # ← 新增
}
```

2. **`workdiary_agent/router/agent.py`**：更新 `decide_template_node` 的 system prompt，告诉 LLM 新增了"总结型"，以及它的判断标准；更新归一化集合 `valid_types`
```python
valid_types = {"技术型", "业务型", "混合型", "总结型"}
```

3. **`workdiary_agent/nodes/route_template.py`**：更新用户覆盖的校验集合
```python
if state.get("template_type") in {"技术型", "业务型", "混合型", "总结型"}:
```

4. **测试文件**：添加新模板的测试用例

**不需要改的（大多数代码）**：

- `workdiary_agent/graph.py`：图拓扑完全不变
- `workdiary_agent/nodes/polish.py`：polish 不关心模板类型
- `workdiary_agent/nodes/extract.py`：提取逻辑不变
- `workdiary_agent/state.py`：`template_type: Optional[str]` 已是字符串，无需改
- `app.py`：UI 层通过 `result.get("template_type")` 显示，自动适配新值
- `workdiary_agent/storage/`：存储层不关心模板类型的具体值

**这说明**：模板系统的扩展点集中在 draft 节点和 router，其他层都对模板类型透明，是松耦合的设计。

### 如何对面试官表述
> "加第 4 种模板只需要改 4 处：draft.py 里加 system prompt 和字典条目，router/agent.py 里更新分类 prompt 和归一化集合，route_template.py 里更新覆盖校验集合，再加测试用例。
>
> 不需要改的地方很多：graph.py 的拓扑、polish 节点、extract 节点、存储层、UI 层——它们都对模板类型的具体值透明，只传递字符串。这说明模板系统的扩展点设计是收敛的，改动范围可控。"

### 亮点
- 能精确定位需要改和不需要改的地方，说明对代码依赖关系有清晰认知
- "扩展点收敛"这个表述展示了对系统设计的理解

### 瓶颈
- 归一化集合 `valid_types` 在三个地方都有，加新模板时需要同步修改三处，容易漏
- 理想做法是把合法模板类型定义为一个常量，集中管理

**进步空间**：
```python
# workdiary_agent/constants.py
VALID_TEMPLATE_TYPES = {"技术型", "业务型", "混合型"}  # 单一来源
```
所有用到这个集合的地方都从这里导入，加新模板只改一处。

### 突出的能力
**代码依赖关系的清晰认知** + **扩展性设计的评估能力**

---

## Q17：`draft_node` 里 `_TEMPLATE_PROMPTS.get(template_type, _MIXED_SYSTEM)` 为什么用 `_MIXED_SYSTEM` 作为默认值？

*（也可能被问成：如果 template_type 是 None 或者未知值，draft 会用哪个模板？）*

### 面试官想听到的
考查点：**防御性编程和默认值选择的设计意图**，以及对 LLM 输出不确定性的处理。

### 代码中的实际方案

`workdiary_agent/nodes/draft.py:75, 105`：
```python
template_type = state.get("template_type", "混合型")   # 第一层默认
# ...
system_prompt = _TEMPLATE_PROMPTS.get(template_type, _MIXED_SYSTEM)  # 第二层默认
```

**两层防御**：
- 第一层：`state.get("template_type", "混合型")`，如果 state 里没有 template_type，默认"混合型"
- 第二层：`_TEMPLATE_PROMPTS.get(template_type, _MIXED_SYSTEM)`，如果 template_type 不在字典里（比如 TemplateRouterAgent 返回了意外值），也用混合型

**为什么选"混合型"作为默认**：混合型模板同时包含"业务影响"和"技术工作"两个维度，是最通用的格式，适合大多数工作描述。退化到混合型比退化到技术型或业务型更安全——不会因为选错了单一维度的模板而丢失信息。

**实际上 `route_template_node` 已经有归一化**（`workdiary_agent/router/agent.py:66-68`），所以第二层防御理论上不会触发。但作为防御性编程，保留它是合理的。

### 如何对面试官表述
> "混合型模板是最通用的，包含业务影响和技术工作两个维度，退化到混合型比退化到单一维度的模板损失更小。这里有两层防御：state 里没有 template_type 时默认混合型，template_type 不在字典里时也用混合型。虽然 route_template_node 已经做了归一化，理论上第二层不会触发，但作为防御性编程保留它是值得的——LLM 的输出永远有不确定性。"

### 亮点
- 能解释"为什么选混合型"而不是随便选一个，说明有设计意图
- 识别出两层防御，并说明它们的关系

### 瓶颈
- 如果未来添加新模板，这里的默认值可能需要重新评估
- 两层防御的存在可能掩盖 TemplateRouterAgent 的 bug（返回了非法值但被静默处理）

### 突出的能力
**防御性编程的设计意图理解** + **LLM 不确定性的处理意识**

---

## Q18：`@st.cache_resource` 缓存了 graph 对象，这意味着 SqliteSaver 的数据库连接也被缓存了。多用户场景下有什么问题？

*（也可能被问成：如果两个用户同时生成日报，会互相干扰吗？）*

### 面试官想听到的
考查点：**并发安全性分析**，能否识别共享资源的竞态风险。

### 代码中的实际方案

`app.py:21-24`：
```python
@st.cache_resource
def get_graph():
    return build_graph(use_sqlite=True)
```

`workdiary_agent/graph.py:125-126`：
```python
conn = sqlite3.connect("graph_state.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)
```

**`check_same_thread=False` 的含义**：允许同一个 SQLite 连接被多个线程使用（SQLite 默认只允许创建连接的线程使用它）。

**多用户场景下的情况**：
- 所有用户共享同一个 `graph` 对象和同一个 `conn`（SQLite 连接）
- 每个用户有独立的 `thread_id`，所以逻辑上的状态是隔离的
- 但底层的 SQLite 连接是共享的，并发写入时由 SQLite 的文件级锁保护

**SQLite 的并发限制**：
- SQLite 支持多读单写（WAL 模式下可以并发读）
- 写操作需要获取文件锁，并发写入时会串行化
- 高并发下会出现 `database is locked` 错误

**实际风险**：对于单用户工具（这个项目的定位），没有问题。如果有多个并发用户同时调用 `graph.invoke()`，可能出现写入冲突。

### 理想方案

**方案一（小规模多用户）**：为每个用户会话创建独立的 SqliteSaver 连接
```python
# 在 session_state 里存连接，而不是 cache_resource
if "graph" not in st.session_state:
    conn = sqlite3.connect(f"graph_state_{st.session_state.thread_id}.db")
    st.session_state.graph = build_graph_with_conn(conn)
```

**方案二（大规模）**：换用 PostgreSQL checkpointer，天然支持并发
```python
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
```

### 如何对面试官表述
> "cache_resource 缓存了 graph 实例，连带着 SqliteSaver 的数据库连接也被共享了。check_same_thread=False 允许多线程使用同一个连接，但 SQLite 本身是文件级锁，并发写入时会串行化，高并发下可能出现 'database is locked' 错误。
>
> 对于单用户工具这不是问题。如果要支持多用户，方案一是把 graph 实例从 cache_resource 移到 session_state，每个用户独立连接；方案二是换 PostgreSQL checkpointer，天然支持并发。"

### 亮点
- 说清楚了 `check_same_thread=False` 的含义，而不是模糊带过
- 给出了两个层次的解决方案

### 瓶颈
- 每个用户独立数据库文件（方案一）会导致文件数量爆炸，需要清理机制
- PostgreSQL 方案引入了额外的基础设施依赖

### 突出的能力
**并发安全性分析** + **SQLite 并发限制的深度理解**

---

## Q19：polish 节点的 system prompt 里说"不要添加原文中没有的事实信息，只改语气和表达方式"，这个约束 LLM 能保证遵守吗？

*（也可能被问成：你怎么防止 LLM 在润色时捏造数据？有验证机制吗？）*

### 面试官想听到的
考查点：**LLM 可靠性和 AI 安全设计**，能否识别 prompt 约束的局限性，以及如何用工程手段补充。

### 代码中的实际方案

`workdiary_agent/nodes/polish.py:24-35`（system prompt 关键部分）：
```
注意：不要添加原文中没有的事实信息。只改语气和表达方式。
```

以及 draft 节点的三个模板都有：
```
保持原始信息，不捏造细节
```

**LLM 能保证遵守吗？不能完全保证。**

这是一个 prompt 层面的约束，LLM 会尽力遵守，但没有任何机制验证它是否真的遵守了。常见的违反场景：
1. 用户输入"今天响应时间提升了"，LLM 可能自动补充"提升了约 30%"
2. LLM 在"下一步"章节里发明了用户没提到的计划
3. 量化指标占位符被替换成了捏造的数字

**代码中没有任何验证机制**：没有对比 `raw_input` 和 `polished` 的内容，没有检测是否有新的数字出现，没有事实核查步骤。

### 理想方案（按成本从低到高）

**方案一：在 prompt 里加强约束**（成本最低，效果有限）
```
如果原文没有数字，绝对不能在润色版中出现任何数字（0-9）。
```

**方案二：事后验证节点**（增加一个 LLM 调用）
```python
def verify_node(state: AgentState) -> dict:
    """Verify polished content doesn't hallucinate facts not in raw_input."""
    prompt = f"""
    原始描述：{state.get('raw_input')}
    润色版本：{state.get('polished')}
    
    请检查润色版本是否添加了原始描述中没有的事实信息（特别是数字、日期、具体成果）。
    如果有，列出哪些内容是捏造的。如果没有，回答"验证通过"。
    """
```

**方案三：规则验证**（成本最低，只能检测数字）
```python
import re
raw_numbers = set(re.findall(r'\d+', state.get('raw_input', '')))
polished_numbers = set(re.findall(r'\d+', state.get('polished', '')))
new_numbers = polished_numbers - raw_numbers
if new_numbers:
    log.warning(f"Potential hallucination: new numbers {new_numbers} in polished")
```

### 如何对面试官表述
> "Prompt 约束是软约束，LLM 会尽力遵守，但没有任何保证。常见违反场景是 LLM 自动补充了用户没提到的数字或计划。代码里没有验证机制，这是明显的缺口。
>
> 修复方案有三个层次：加强 prompt 约束（成本低，效果有限）；加一个验证节点，用 LLM 检查润色版是否有幻觉内容（成本高但最准确）；或者用正则检测新增的数字（成本最低，只能覆盖数字幻觉）。当前项目没有做，是因为这是求职 demo，完整的事实核查超出了 scope。"

### 亮点
- 主动说出 prompt 约束的局限性，而不是假装它能保证正确
- 提出了三个层次的方案，说明有系统性思考

### 瓶颈
- 验证节点会增加一次 LLM 调用，成本和延迟都增加
- 规则验证（正则）只能检测数字，无法检测其他类型的幻觉

### 突出的能力
**LLM 可靠性的现实认知** + **AI 安全的工程化思维**

---

## Q20：`enrich_node` 里 git log 读取（同步 I/O）和 data_input 提取（LLM 调用）是串行的，能并行吗？

*（也可能被问成：enrich 节点的性能可以优化吗？两个操作有依赖关系吗？）*

### 面试官想听到的
考查点：**并发优化意识**，能否识别可以并行的独立操作，以及 LangGraph 同步节点的限制。

### 代码中的实际方案

`workdiary_agent/nodes/enrich.py:104-113`：
```python
def enrich_node(state: AgentState) -> dict:
    # Step 1: Git log (sync IO) — always runs
    repo_path = state.get("repo_path", "") or ""
    git_log = _read_git_log(repo_path)          # ← 可能耗时 0.5-2s

    # Step 2: Data input extraction via LLM
    data_input = state.get("data_input", "") or ""
    data_summary = _extract_data_summary(data_input)  # ← 可能耗时 2-5s

    return {"git_log": git_log, "data_summary": data_summary}
```

**两个操作完全独立，没有依赖关系**。git log 读取不需要 data_summary，data_input 提取不需要 git_log。

**当前串行总耗时**：最坏情况 `0.5 + 5 = 5.5` 秒。

**如果并行**：最坏情况 `max(0.5, 5) = 5` 秒，节省约 10% 时间。

**为什么没有并行**：LangGraph 的节点函数是同步的（`def enrich_node`，不是 `async def`）。在同步函数里用 `asyncio.gather` 需要额外处理事件循环，比较麻烦。

### 理想方案

**方案一：用 `concurrent.futures.ThreadPoolExecutor`（同步节点里的并行）**
```python
from concurrent.futures import ThreadPoolExecutor

def enrich_node(state: AgentState) -> dict:
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_git = executor.submit(_read_git_log, repo_path)
        future_data = executor.submit(_extract_data_summary, data_input)
        git_log = future_git.result()
        data_summary = future_data.result()
    return {"git_log": git_log, "data_summary": data_summary}
```

**方案二：改为异步节点**
```python
import asyncio

async def enrich_node(state: AgentState) -> dict:
    git_log, data_summary = await asyncio.gather(
        asyncio.to_thread(_read_git_log, repo_path),
        _extract_data_summary_async(data_input),  # 需要 async 版本
    )
    return {"git_log": git_log, "data_summary": data_summary}
```

LangGraph 1.x 支持异步节点，但需要 `graph.ainvoke()` 调用，Streamlit 的支持也需要额外处理。

### 如何对面试官表述
> "两个操作完全独立，没有依赖关系，理论上可以并行。当前是串行，最坏情况 5.5 秒。并行化的障碍是节点函数是同步的，在同步函数里做异步并行需要用 ThreadPoolExecutor。
>
> 实际收益有限——LLM 调用是 5 秒，git log 是 0.5 秒，并行只节省 0.5 秒，约 10%。如果整个图的总耗时是 30 秒，这个优化不是瓶颈。真正的优化方向是让 LLM 调用支持流式输出，让用户更早看到内容，而不是减少总耗时。"

### 亮点
- 不只说"可以并行"，还量化了收益（节省 0.5 秒，约 10%）
- 指出了"真正的优化方向"（流式输出 vs 减少总耗时），说明有系统性思维

### 瓶颈
- ThreadPoolExecutor 引入了线程，GitPython 的线程安全性需要验证
- 异步节点需要整个调用链都支持 async，改动范围更大

### 突出的能力
**性能优化的量化分析** + **识别真正瓶颈而不是优化非关键路径**

---

## Q21：`save_node` 里 `save_report(state)` 和 `save_markdown(polished, today)` 如果一个成功一个失败，会怎样？

*（也可能被问成：save_node 的两个操作有原子性保证吗？如果 markdown 写入失败但数据库写入成功，怎么办？）*

### 面试官想听到的
考查点：**事务和原子性意识**，能否识别多步操作的一致性问题。

### 代码中的实际方案

`workdiary_agent/nodes/save.py:25-29`：
```python
save_report(state)           # ← 写 history.db
export_path = save_markdown(polished, today)   # ← 写 exports/ 目录
```

**没有任何事务保护**：两个操作是独立的，没有原子性保证。

**场景一：`save_report` 成功，`save_markdown` 失败**
- `history.db` 里有记录，但 `exports/` 目录里没有文件
- `export_path` 不会被写入 state（因为函数抛异常了）
- 用户看到"生成失败"，但数据库里已经有了这条记录
- 下次生成会再写一条新记录，数据库里出现重复

**场景二：`save_report` 失败**
- `save_markdown` 不会执行（Python 顺序执行，前面抛异常后面不跑）
- `history.db` 里没有记录，`exports/` 也没有文件
- 用户看到"生成失败"，数据丢失

**代码中没有错误处理**：两个函数的异常都会向上传播，被 `app.py:125-131` 的通用 `except Exception` 捕获，显示"生成日报时出现错误"。

### 理想方案

**方案一：独立错误处理，最大化成功率**
```python
def save_node(state: AgentState) -> dict:
    polished = state.get("polished", "") or ""
    today = datetime.date.today().isoformat()
    export_path = None

    try:
        save_report(state)
    except Exception:
        log.exception("Failed to save report to history.db")
        # 不中断，继续尝试导出

    try:
        export_path = save_markdown(polished, today)
    except Exception:
        log.exception("Failed to export markdown")

    return {"final_report": polished, "export_path": export_path}
```

**方案二：幂等写入，防止重复记录**
在 `save_report` 里加 `INSERT OR IGNORE`（基于日期+raw_input 的唯一约束），防止重复写入。

### 如何对面试官表述
> "两个操作没有原子性保证。最危险的场景是 save_report 成功但 save_markdown 失败——数据库里有记录，但文件没写出来，用户看到错误，下次重试会写入重复记录。
>
> 修复方案有两个方向：独立错误处理，让两个操作互不影响，最大化成功率；或者加幂等约束，防止重复写入。对于这个项目，独立错误处理更合适——日志写入失败不应该影响文件导出，反之亦然。"

### 亮点
- 识别了两种失败场景，而不是只说"可能出错"
- 提出了"幂等写入"这个具体的技术方案

### 瓶颈
- 独立错误处理后，用户可能看到"生成成功"但实际上数据库写入失败了，需要在 UI 上有更细粒度的提示

### 突出的能力
**事务和原子性意识** + **多步操作的一致性设计**

---

## Q22：你的 `with_structured_output(StructuredInfo)` 直接返回 Pydantic 对象，但 LangGraph 的 checkpointer 序列化时会怎样处理这个对象？

*（也可能被问成：为什么测试里 mock 的 StructuredInfo 必须是真实的 Pydantic 对象，不能是 MagicMock？）*

### 面试官想听到的
考查点：**LangGraph 序列化机制的深度理解**，以及 Pydantic 对象在 checkpointer 中的处理方式。

### 代码中的实际方案

`workdiary_agent/nodes/extract.py:48-55`：
```python
structured_llm = llm.with_structured_output(StructuredInfo)
result: StructuredInfo = structured_llm.invoke(messages)
return {"structured_info": result}   # ← Pydantic 对象写入 state
```

**LangGraph 的 checkpointer 序列化**：

SqliteSaver（和 InMemorySaver）使用 `msgpack` 序列化 AgentState，然后存储到数据库。

**问题**：`StructuredInfo` 是 Pydantic `BaseModel` 的子类，不是原生 Python 类型。msgpack 不知道如何序列化它。

**LangGraph 的处理方式**：LangGraph 1.x 有一个注册机制，允许自定义类型的序列化/反序列化。但 `StructuredInfo` 没有显式注册，会触发：
```
Deserializing unregistered type workdiary_agent.state.StructuredInfo from checkpoint.
This will be blocked in a future version.
```

**这就是为什么测试里必须用真实 Pydantic 对象**（`tests/test_phase04_hitl.py:28-35`）：
```python
mock_structured.invoke.return_value = StructuredInfo(
    tasks=["完成登录模块开发"],
    outputs=["登录模块代码"],
    blockers=[],
    progress="登录模块开发完成",
)
```
如果返回 `MagicMock()`，msgpack 无法序列化它，checkpointer 在 interrupt 时会失败。

### 理想方案

显式注册 StructuredInfo 到 LangGraph 的 msgpack 允许列表：
```python
# 在 graph.py 或 state.py 里
import os
allowed = os.environ.get("LANGGRAPH_ALLOWED_MSGPACK_MODULES", "")
os.environ["LANGGRAPH_ALLOWED_MSGPACK_MODULES"] = (
    allowed + ",workdiary_agent.state" if allowed else "workdiary_agent.state"
)
```
或者等待 LangGraph 提供更好的 Pydantic 集成 API。

### 如何对面试官表述
> "LangGraph 的 checkpointer 用 msgpack 序列化状态，但 Pydantic BaseModel 不是原生类型，没有显式注册就会触发'Deserializing unregistered type'的警告。这就是为什么测试里 mock 必须返回真实的 StructuredInfo 对象——如果返回 MagicMock，interrupt 时 checkpointer 序列化会失败。
>
> 这个 warning 说明 LangGraph 目前是用 pickle-like 的方式处理未注册类型，在未来版本可能被 block。修复方案是显式注册 StructuredInfo 到 LANGGRAPH_ALLOWED_MSGPACK_MODULES 环境变量。"

### 亮点
- 能解释 warning 的根本原因（msgpack 序列化 + 未注册类型）
- 连接了 warning 和测试设计的关系，说明是真实踩过的

### 瓶颈
- 环境变量方案是临时的，LangGraph 未来版本可能改变 API
- 如果 StructuredInfo 的字段有嵌套的复杂类型，序列化问题会更复杂

### 突出的能力
**LangGraph 序列化机制的深度理解** + **测试设计与运行时行为的关联分析**

---

## Q23：用户提交了空的工作描述，你的系统会怎样？从 UI 到图执行，每一层的防御是什么？

*（也可能被问成：空输入的防御是几层的？哪一层是最关键的？）*

### 面试官想听到的
考查点：**分层防御设计**，能否追踪一个边界输入从 UI 到底层的完整处理路径。

### 代码中的实际方案

**第一层：UI 层（app.py:57-59）**
```python
if not raw_input.strip():
    st.error("请填写工作描述（必填）")
    return
```
用户点击「生成日报」时，Streamlit 检查输入是否为空，如果是则显示错误并提前返回，不触发 `graph.invoke()`。

**第二层：extract_node（workdiary_agent/nodes/extract.py:22-23）**
```python
if not raw_input:
    return {"structured_info": StructuredInfo()}   # 返回空的 StructuredInfo
```
如果 `raw_input` 为空（不应该到达这里，但作为防御），返回空的 StructuredInfo，不调用 LLM。

**第三层：draft_node（workdiary_agent/nodes/draft.py:93-94）**
```python
else:
    context = f"原始描述：{raw_input}"
```
如果 `structured_info` 为 None（StructuredInfo 提取失败），只用 `raw_input` 构建 context。

**第四层：polish_node（workdiary_agent/nodes/polish.py:48-50）**
```python
draft = state.get("draft", "")
if not draft or draft == "[stub draft]":
    return {"polished": draft or ""}
```
如果 draft 为空，直接返回空字符串，不调用 LLM。

**总结**：4 层防御，第一层是最关键的（UI 层拦截，不浪费 API 调用），后面三层是纵深防御。

### 如何对面试官表述
> "空输入有 4 层防御：第一层在 UI，点击生成时检查 raw_input 是否为空，是则显示错误并提前返回，不调用图——这是最关键的一层，不浪费 API 调用；第二层在 extract_node，raw_input 为空时返回空 StructuredInfo，不调用 LLM；第三层在 draft_node，structured_info 为 None 时只用 raw_input 构建 context；第四层在 polish_node，draft 为空时直接返回，不调用 LLM。
>
> 纵深防御的价值在于：即使某一层被绕过（比如直接调用 graph.invoke() 而不走 UI），后面的层仍然能保护系统不崩溃。"

### 亮点
- 能追踪完整的 4 层防御路径，说明对代码流程有清晰认知
- 说出了"纵深防御"的价值，不只是说"有防御"

### 瓶颈
- 第二层到第四层的防御会让系统"静默成功"——空输入最终可能生成一个空的日报，而不是明确的错误提示
- 没有对输入长度的上限检查（超长输入可能导致 token 超限）

### 突出的能力
**分层防御的系统性设计** + **边界输入的完整路径追踪**

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
