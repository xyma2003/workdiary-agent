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
    If template_type is already set in state (user override, TMPL-03), skip classification.
    Returns {"template_type": "技术型" | "业务型" | "混合型"}.
    """
    # TMPL-03: respect user override — if already set, skip auto-classification
    if state.get("template_type") in {"技术型", "业务型", "混合型"}:
        return {"template_type": state["template_type"]}

    raw_input = state.get("raw_input", "")
    structured_info = state.get("structured_info")

    # Build optional structured_info summary for richer router context
    si_text = ""
    if structured_info is not None:
        if isinstance(structured_info, dict):
            tasks = structured_info.get("tasks", [])
            outputs = structured_info.get("outputs", [])
            progress = structured_info.get("progress", "")
        else:  # Backward-compatible direct node calls.
            tasks = structured_info.tasks
            outputs = structured_info.outputs
            progress = structured_info.progress
        tasks_str = "、".join(tasks) if tasks else ""
        outputs_str = "、".join(outputs) if outputs else ""
        si_text = f"任务：{tasks_str}；产出：{outputs_str}；进度：{progress}"

    router = TemplateRouterAgent()
    template_type = router.classify(raw_input, structured_info_text=si_text)
    return {"template_type": template_type}
