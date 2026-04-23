# workdiary_agent/nodes/route_template.py
"""
Route template node: calls TemplateRouterAgent compiled sub-graph to classify
the work description and writes template_type into AgentState.
"""
from ..state import AgentState
from ..router.agent import TemplateRouterAgent


def route_template_node(state: AgentState) -> dict:
    """Invoke TemplateRouterAgent sub-graph to determine template_type.

    Reads raw_input and optional structured_info from state.
    Returns {"template_type": "技术型" | "业务型" | "混合型"}.
    """
    raw_input = state.get("raw_input", "")
    structured_info = state.get("structured_info")

    # Build optional structured_info summary for richer router context
    si_text = ""
    if structured_info is not None:
        tasks_str = "、".join(structured_info.tasks) if structured_info.tasks else ""
        outputs_str = "、".join(structured_info.outputs) if structured_info.outputs else ""
        si_text = f"任务：{tasks_str}；产出：{outputs_str}；进度：{structured_info.progress}"

    router = TemplateRouterAgent()
    template_type = router.classify(raw_input, structured_info_text=si_text)
    return {"template_type": template_type}
