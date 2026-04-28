# 智能日报 Agent — 面试问答指南

> 针对 AI Agent 开发岗位面试，整理高频考点、答题方向和示例答案。
> 核心原则：**主动暴露复杂度，而不是回避它**。

---

## 项目一句话定位

> "基于 LangGraph 的 Multi-Agent 系统，将口语化工作描述自动转化为老板视角的日报，核心亮点是完整实现了带状态持久化的 Human-in-the-Loop interrupt/resume 循环。"

---

## 一、LangGraph 与图设计

### Q1：为什么用 LangGraph，而不是直接写 Python 或用 LangChain chain？

**考查点：** 候选人是否理解 LangGraph 的核心价值，而不只是"用了新框架"。

**面试官更想听：** 从具体需求出发推导出技术选型，而不是"LangGraph 比较流行"。

**答：**
核心需求是 Human-in-the-Loop：需要图的执行能在中间暂停、把状态序列化到磁盘、等用户输入后从断点恢复。纯 Python 函数做不到"暂停一个调用栈、存储所有中间状态、若干分钟后继续"。LangGraph 的 checkpointer 机制天然解决了这个问题。

LangChain chain 是线性的，没有条件边和循环。这个项目有 `revise → polish → review` 的循环，最多 3 次后强制退出，这种有状态的循环需要 StateGraph 的图结构来表达。

---

### Q2：讲一下你的图拓扑设计，为什么这样设计？

**考查点：** 是否能清晰描述节点职责和边的逻辑，是否有意识地做了关注点分离。

**答：**
```
START → extract → enrich → route_template → draft → polish → review ⇄ revise → save → END
```

关键设计决策：

1. **enrich 节点可选**：git log 和数据指标都是可选输入，enrich 节点处理缺失情况（返回 None），下游节点不感知，主流程不受影响。

2. **route_template 是子图**：TemplateRouterAgent 独立编译，两步走——先提取内容特征，再决策模板类型。比单步分类准确，也可以独立测试和替换。

3. **review ↔ revise 循环**：review 节点用 `interrupt()` 暂停，用户 approve 走条件边到 save，用户 revise 走条件边到 revise 节点，revise 递增计数后路由回 polish。`route_after_revise` 守卫 `revision_count >= 3` 时强制到 save，防止无限循环。

---

### Q3：`interrupt()` 怎么工作的？有什么坑？

**考查点：** 这是 LangGraph 1.x 最核心的 HITL 机制，面试官很可能深挖。

**答：**

`interrupt(payload)` 在节点内部调用时，会抛出 `GraphInterrupt` 异常。LangGraph runtime 捕获这个异常，把当前完整状态序列化到 checkpointer（SQLite），然后让 `graph.invoke()` 返回。此时图处于暂停状态：`graph.get_state(config).next == ("review",)`。

恢复时调用 `graph.invoke(Command(resume={"decision": "approve"}), config)`，LangGraph 从 checkpointer 加载状态，`interrupt()` 这次返回 `Command.resume` 的值，节点继续执行。

**三个真实踩过的坑：**

1. `GraphInterrupt` 是 `Exception` 的子类（继承链：`GraphInterrupt → GraphBubbleUp → Exception`）。如果 `interrupt()` 外面有 `except Exception:`，会把它静默吞掉，图不会暂停，直接跑穿。**解决：interrupt() 周围绝不加 try/except。**

2. `SqliteSaver.from_conn_string("graph_state.db")` 是 `@contextmanager`，不能直接赋值。不加 `with` 语句返回的是 `_GeneratorContextManager`，`compile()` 时报 `TypeError`。**解决：用 `sqlite3.connect()` 直接传连接对象。**

3. `graph.get_state(config).next` 返回的是 tuple，不是 list。用 `== ["review"]` 判断会永远为 False。**解决：用 `"review" in state.next`。**

---

### Q4：revision 循环的三个守卫是什么？

**考查点：** 防止无限循环是 agent 设计的基础，考查候选人是否认真处理边界情况。

**答：**

1. **初始化守卫**：`AgentState` 中 `revision_count` 字段默认 0，`state.get("revision_count", 0)` 而不是 `state["revision_count"]`（`total=False` TypedDict，未设置的键会 KeyError）。

2. **递增守卫**：`revise_node` 只做一件事——返回 `{"revision_count": count + 1}`，不做其他逻辑。职责单一，容易测试。

3. **条件边守卫**：`route_after_revise` 函数：`count >= 3` 路由到 `save`，否则路由到 `polish`。这是唯一的退出条件，保证第三次 revise 后一定到达 END。

---

## 二、Multi-Agent 架构

### Q5：TemplateRouterAgent 为什么做成子图而不是单个节点？

**考查点：** 是否理解 LangGraph sub-graph 的使用场景，以及分步推理 vs 单步推理的权衡。

**答：**

两个理由：

**准确性**：分类任务分两步——`analyze_content` 先提取内容特征（有多少技术内容/业务内容），`decide_template` 再根据特征决策——比直接问"这是哪种模板"更准确。这类似 chain-of-thought 的效果。

**可维护性**：子图独立编译，有自己的 `RouterState`，与主图的 `AgentState` 完全解耦。主图只关心输入（`raw_input` + `structured_info`）和输出（`template_type`），内部实现可以随时替换——比如换成向量相似度分类——而不影响主图。

---

### Q6：这个项目算 Multi-Agent 吗？和 supervisor 模式有什么区别？

**考查点：** 候选人对 Multi-Agent 概念的理解深度，避免用词不当。

**答：**

严格来说，这是一个**主图 + 子图**的组合，不是完整的 Multi-Agent supervisor 模式。TemplateRouterAgent 是主图内部的一个节点，不是独立的 Agent。

Supervisor 模式通常是：一个 Supervisor Agent 根据任务动态分派给多个 Worker Agent，Worker 之间可以并行，Supervisor 聚合结果。这个项目的路由是静态的——在主图里总是调用 TemplateRouterAgent，不会动态选择是否调用。

说它是 Multi-Agent 的依据是：有两个独立编译的 StateGraph，有明确的状态边界，信息通过接口传递而不是共享内存。但如果面试官追问，我会直接说"更准确的描述是主图 + sub-graph 组合，而不是完整的 supervisor multi-agent 架构"。

---

## 三、Human-in-the-Loop 设计

### Q7：HITL 的 state 是怎么在 Streamlit 和 LangGraph 之间传递的？

**考查点：** Streamlit 每次 rerun 会重建 Python 状态，这是 LangGraph + Streamlit 集成的核心难点。

**答：**

两层持久化：

1. **LangGraph 层**：graph 的完整状态（包括 interrupt 时的 `AgentState`）存在 `graph_state.db`（SqliteSaver）。只要 `thread_id` 不变，随时可以恢复。

2. **Streamlit 层**：`graph` 对象用 `@st.cache_resource` 缓存（跨 rerun 保持同一个实例），`thread_id` 存在 `st.session_state`（用 `not in` guard 保证只初始化一次）。

这样，Streamlit rerun 时：UI 状态从 `session_state` 恢复，graph 状态从 `graph_state.db` 恢复，两者通过 `thread_id` 关联。用户点任何按钮都不会重新开始一个新的图执行。

**容易犯的错误**：每次 rerun 都调用 `build_graph()` 创建新实例，或者每次都生成新的 `thread_id`——这两种情况都会让 interrupt 状态丢失，图从头开始跑。

---

### Q8：用户可以 inline 编辑日报后再接受，这个路径怎么实现的？

**考查点：** HITL-02（inline edit）是这个项目在 Phase 4 之外额外实现的功能，考查候选人对状态流的理解。

**答：**

`st.text_area(key="edit_area", value=polished)` 是可编辑的。用户修改文本后，Streamlit 自动把最新内容存在 `session_state["edit_area"]`。

用户点「接受」时：
```python
current_text = st.session_state.get("edit_area", polished)
if current_text != polished:
    # 用编辑后的内容覆盖 session_state 里的 result
    st.session_state.result["polished"] = current_text
```
然后再调用 `graph.invoke(Command(resume={"decision": "approve"}), config)`。

这样 graph 的 `save_node` 拿到的 `polished` 是用户编辑后的版本，写入 `history.db` 的也是编辑版。LangGraph 不需要知道用户做了 inline edit，完全在 Streamlit 层处理。

---

## 四、工程质量

### Q9：测试策略是怎么做的？LLM 调用怎么测？

**考查点：** AI 应用的测试是常见考点，面试官想知道候选人有没有工程意识。

**答：**

**TDD 驱动**：每个 Phase 先写 RED 测试，再写实现，再看 GREEN。33 个测试，覆盖全部 Phase 的验收标准。

**LLM 调用的处理**：全部 mock。测试不调用真实 API，原因有三：速度（每次测试省几十秒）、成本（省 token）、可重复性（LLM 输出不稳定，不能作为断言基准）。

mock 策略：`patch("workdiary_agent.nodes.extract.make_llm", return_value=mock_llm)`，在使用处拦截而不是在定义处拦截。`make_llm` 统一定义在 `utils.py`，各节点从那里导入，所以 mock 路径是节点模块的本地名。

**集成测试**：HITL 循环有独立的验证脚本 `scripts/test_hitl_cycle.py`，用 InMemorySaver（不写磁盘），跑三条真实路径：直接 approve、revise 一次后 approve、连续 3 次 revise 强制退出。这部分调用真实 LLM，但只在 CI 之外手动运行。

---

### Q10：`history.db` 和 `graph_state.db` 为什么要分开？

**考查点：** 持久化架构设计，考查候选人是否理解框架边界。

**答：**

`graph_state.db` 是 LangGraph 的 SqliteSaver 独占管理的，它有自己的 schema（checkpoint 表、channel_values 表等）。如果应用代码往里写东西，会破坏 LangGraph 的序列化格式，导致 interrupt/resume 失败。

`history.db` 是应用层的业务数据——日报内容、模板类型、原始输入——schema 由我们自己设计，查询逻辑也由我们控制。

两者混用会产生 schema 冲突，而且职责不清楚——将来要备份历史日报、迁移数据库、或者清理 LangGraph 状态，都需要能独立操作两个文件。这是在 Phase 1 设计阶段就定下来的，后面没有返工。

---

### Q11：代码里有什么觉得还不够好的地方？

**考查点：** 自我认知，面试官不想听"没有问题"。主动暴露问题比被追问出来要好。

**答：**

有三个地方：

1. **LLM 调用没有重试**：API 限流或超时时直接报错。应该加 `anthropic.APIError` 的捕获和指数退避重试。这在个人项目里可以接受，生产环境不行。

2. **TemplateRouterAgent 没有评测**：分类准确率完全依赖 prompt，没有用真实样本做过系统评测。如果要上线，应该有测试集验证 3 类分类的 precision/recall。

3. **Streamlit 是同步阻塞的**：用户点「生成日报」后，整个 UI 会冻结直到图执行完。体验不好。v2 可以用 `asyncio` + `st.empty()` 实现流式更新，但会增加 LangGraph + Streamlit 的集成复杂度，当前 scope 内没做。

---

## 五、快问快答

| 问题 | 关键词 |
|------|--------|
| 用的什么模型？ | `claude-sonnet-4-5`，通过 `langchain-anthropic` 的 `ChatAnthropic` 调用，支持 `with_structured_output` |
| 结构化提取怎么做的？ | `llm.with_structured_output(StructuredInfo)`，直接返回 Pydantic 对象，不用手动解析 JSON |
| 为什么用 TypedDict 而不是 Pydantic 作为 State？ | LangGraph 官方推荐 TypedDict，`total=False` 让所有字段可选，`state.get()` 安全访问；Pydantic State 也支持但增加复杂度 |
| 怎么防止模板类型被用户覆盖后被重置？ | `route_template_node` 里检查 `state.get("template_type") in {"技术型","业务型","混合型"}`，已设置则直接返回，跳过子图分类 |
| 项目用了几天？ | 约 2 天完成全部 6 个 Phase，包括设计、实现、测试、UI |

---

*最后更新：2026-04-28*
