# workdiary_agent/nodes/draft.py
"""
Draft node: generate a structured daily report draft based on StructuredInfo and template_type.

Three templates hardcoded in system prompts (D-05, D-06, D-07, D-08):
- 技术型: 任务 → 方案 → 进度 → 下一步
- 业务型: 结论 → 数据 → 进展 → 下一步
- 混合型: 业务影响 → 技术工作 → 量化指标 → 下一步

TMPL-02: Every draft begins with "【已选用XX模板】" for user visibility.
TMPL-03: template_type is always read from state — never hardcoded.
"""
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import AgentState
from ..utils import make_llm


# ---------------------------------------------------------------------------
# Template-specific system prompts (D-05, D-06, D-07, D-08)
# ---------------------------------------------------------------------------

_TECH_SYSTEM = """你是一个技术日报撰写助手，采用「技术型」模板。
请按以下结构生成日报初稿：
1. 任务：今天进行了哪些技术工作
2. 方案：采用了什么技术方案或解决思路
3. 进度：当前进展状态
4. 下一步：明天计划的技术工作

要求：
- 第一行必须是：【已选用技术型模板】
- 每个章节用「**章节名**」加粗标注
- 语言简洁、专业
- 保持原始信息，不捏造细节"""

_BIZ_SYSTEM = """你是一个业务日报撰写助手，采用「业务型」模板。
请按以下结构生成日报初稿：
1. 结论：今天最重要的业务结果
2. 数据：支撑结论的关键数据或指标（若无数据请注明"（未提供量化指标）"）
3. 进展：各项业务事项的推进情况
4. 下一步：后续业务跟进计划

要求：
- 第一行必须是：【已选用业务型模板】
- 每个章节用「**章节名**」加粗标注
- 语言简洁、聚焦结果
- 保持原始信息，不捏造细节"""

_MIXED_SYSTEM = """你是一个混合型日报撰写助手，采用「混合型」模板。
请按以下结构生成日报初稿：
1. 业务影响：技术工作带来的业务价值
2. 技术工作：今天进行的技术实现细节
3. 量化指标：关键数据或度量（若无数据请注明"（未提供量化指标）"）
4. 下一步：业务与技术双线的后续计划

要求：
- 第一行必须是：【已选用混合型模板】
- 每个章节用「**章节名**」加粗标注
- 语言兼顾业务和技术受众
- 保持原始信息，不捏造细节"""

_TEMPLATE_PROMPTS = {
    "技术型": _TECH_SYSTEM,
    "业务型": _BIZ_SYSTEM,
    "混合型": _MIXED_SYSTEM,
}


def draft_node(state: AgentState) -> dict:
    """Generate report draft using the template selected by TemplateRouterAgent.

    Reads template_type from state (TMPL-03: respects user override).
    Returns draft string with '【已选用XX模板】' header (TMPL-02).
    """
    template_type = state.get("template_type", "混合型")
    structured_info = state.get("structured_info")
    raw_input = state.get("raw_input", "")

    # Build context for LLM
    if structured_info is not None:
        tasks_str = "\n".join(f"- {t}" for t in structured_info.tasks) or "（无）"
        outputs_str = "\n".join(f"- {o}" for o in structured_info.outputs) or "（无）"
        blockers_str = "\n".join(f"- {b}" for b in structured_info.blockers) or "（无）"
        progress_str = structured_info.progress or "（未提供）"
        context = (
            f"原始描述：{raw_input}\n\n"
            f"结构化信息：\n"
            f"任务：\n{tasks_str}\n"
            f"产出：\n{outputs_str}\n"
            f"问题/阻碍：\n{blockers_str}\n"
            f"整体进度：{progress_str}"
        )
    else:
        context = f"原始描述：{raw_input}"

    # Phase 3 (D-11): append enrichment context when available
    git_log = state.get("git_log")
    if git_log:
        context += f"\n今日 Git commits：\n{git_log}"

    data_summary = state.get("data_summary")
    if data_summary:
        context += f"\n数据指标：\n{data_summary}"

    system_prompt = _TEMPLATE_PROMPTS.get(template_type, _MIXED_SYSTEM)

    llm = make_llm()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"请根据以下信息生成日报初稿：\n\n{context}"),
    ])
    return {"draft": response.content}
