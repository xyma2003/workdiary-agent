# workdiary_agent/nodes/extract.py
"""Extract node: parse raw Chinese work description into StructuredInfo via LLM."""
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import AgentState, StructuredInfo
from ..utils import make_llm


_SYSTEM_PROMPT = """你是一个工作日报信息提取助手。请从用户的口语化工作描述中，提取以下结构化信息：

- tasks: 今天实际进行的工作任务列表（每项是简短的动宾短语，如"完成用户登录模块单元测试"）
- outputs: 产出的具体成果或交付物列表（如"通过3个bug修复"、"需求对齐确认"）
- blockers: 遇到的阻碍或未解决问题列表（若无则为空列表）
- progress: 一句话总结今天整体工作进展（如"主要功能开发推进顺利，无重大阻碍"）

请只提取用户描述中明确提及的信息，不要臆测或补充未提及的内容。"""


def extract_node(state: AgentState) -> dict:
    """Call ChatAnthropic with_structured_output to parse raw_input into StructuredInfo."""
    raw_input = state.get("raw_input", "")
    if not raw_input:
        return {"structured_info": StructuredInfo()}

    llm = make_llm()
    structured_llm = llm.with_structured_output(StructuredInfo)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"请提取以下工作描述的结构化信息：\n\n{raw_input}"),
    ]
    result: StructuredInfo = structured_llm.invoke(messages)
    return {"structured_info": result}
