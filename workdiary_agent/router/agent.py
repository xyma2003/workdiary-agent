# workdiary_agent/router/agent.py
"""
TemplateRouterAgent: compiled sub-graph that classifies a work description into one of
three template types: 技术型 (technical), 业务型 (business), 混合型 (mixed).

Sub-graph topology: START → analyze_content → decide_template → END
Uses independent RouterState (does not share AgentState).
"""
from __future__ import annotations

from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from ..utils import make_llm


class RouterState(TypedDict, total=False):
    """Independent state for the TemplateRouterAgent sub-graph."""
    raw_input: str
    structured_info_text: str   # textual summary of structured_info for classification
    content_features: str       # intermediate: key content features extracted in analyze step
    template_type: str          # output: "技术型" | "业务型" | "混合型"


_ANALYZE_SYSTEM = """你是一个内容分析助手。请分析工作描述，提取以下特征：
1. 是否包含技术细节（代码、架构、数据库、API、算法、测试等）
2. 是否包含业务内容（客户、GMV、合同、需求对齐、数据报表、商务等）
3. 主要工作类型比例

请用简洁的1-2句话描述内容特征，供后续分类使用。"""

_DECIDE_SYSTEM = """你是一个日报类型分类助手。根据内容特征，从以下三种类型中选择最合适的一种：
- 技术型：工作内容以技术实现为主（编码、架构设计、测试、Bug修复等），业务内容较少
- 业务型：工作内容以业务推进为主（客户对齐、数据分析、需求确认、商务谈判等），技术内容较少
- 混合型：技术工作和业务工作均有实质性内容，缺一不可

请只输出以下三者之一（不含其他文字）：技术型、业务型、混合型"""


def analyze_content_node(state: RouterState) -> dict:
    """Analyze work content and extract classification features."""
    raw = state.get("raw_input", "")
    si_text = state.get("structured_info_text", "")
    combined = f"{raw}\n\n结构化摘要：{si_text}" if si_text else raw

    llm = make_llm()
    response = llm.invoke([
        SystemMessage(content=_ANALYZE_SYSTEM),
        HumanMessage(content=f"请分析以下工作内容的特征：\n\n{combined}"),
    ])
    return {"content_features": response.content}


def decide_template_node(state: RouterState) -> dict:
    """Classify template type based on extracted content features."""
    features = state.get("content_features", "")
    raw = state.get("raw_input", "")

    llm = make_llm()
    response = llm.invoke([
        SystemMessage(content=_DECIDE_SYSTEM),
        HumanMessage(content=f"内容特征：{features}\n\n原始描述：{raw}"),
    ])
    # Normalize — strip whitespace, fall back to 混合型 if unexpected value
    raw_type = response.content.strip()
    valid_types = {"技术型", "业务型", "混合型"}
    template_type = raw_type if raw_type in valid_types else "混合型"
    return {"template_type": template_type}


# ---------------------------------------------------------------------------
# Compile the sub-graph once at module level
# ---------------------------------------------------------------------------
_builder = StateGraph(RouterState)
_builder.add_node("analyze_content", analyze_content_node)
_builder.add_node("decide_template", decide_template_node)
_builder.add_edge(START, "analyze_content")
_builder.add_edge("analyze_content", "decide_template")
_builder.add_edge("decide_template", END)

_router_graph = _builder.compile()


class TemplateRouterAgent:
    """Wrapper around the compiled router sub-graph.

    Usage:
        router = TemplateRouterAgent()
        template_type = router.classify("today's work description...")
        # Returns: "技术型" | "业务型" | "混合型"
    """

    def classify(self, raw_input: str, structured_info_text: str = "") -> str:
        """Classify raw_input into a template type.

        Args:
            raw_input: User's work description (口语化 Chinese text)
            structured_info_text: Optional textual summary of StructuredInfo for richer context

        Returns:
            One of "技术型", "业务型", "混合型"
        """
        result = _router_graph.invoke({
            "raw_input": raw_input,
            "structured_info_text": structured_info_text,
        })
        return result.get("template_type", "混合型")
