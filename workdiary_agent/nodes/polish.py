# workdiary_agent/nodes/polish.py
"""
Polish node: refine the draft from boss-perspective without regenerating from scratch.

Strategy (D-09):
- INPUT: state["draft"] — the template-structured initial draft
- OUTPUT: polished version that leads with outcomes, uses goal-completion verbs
- Does NOT regenerate — improves tone/emphasis/verb choice of existing draft

AGENT-07 requirements:
- Lead with outcomes (business value first)
- Use goal-completion verbs: 完成、推进、对齐、输出、跟进
- Include quantified statements OR insert "（未提供量化指标）" placeholder (D-10)

D-10: If no numbers or metrics are found in the draft, insert "（未提供量化指标）" in the
     appropriate section rather than fabricating data.
"""
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import AgentState


# ---------------------------------------------------------------------------
# Helper: build ChatAnthropic with ANTHROPIC_CUSTOM_HEADERS if set
# ---------------------------------------------------------------------------

def _make_llm() -> ChatAnthropic:
    """Return ChatAnthropic with custom headers parsed from ANTHROPIC_CUSTOM_HEADERS env var.

    The environment variable is a newline-separated list of 'Key: Value' pairs.
    Required by the Meituan internal proxy (mcli.sankuai.com) to identify the caller.
    """
    custom_headers_str = os.environ.get("ANTHROPIC_CUSTOM_HEADERS", "")
    headers: dict[str, str] = {}
    if custom_headers_str:
        for line in custom_headers_str.split("\n"):
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
    return ChatAnthropic(model="claude-sonnet-4-5", default_headers=headers)


_POLISH_SYSTEM = """你是一位资深职场写作顾问，专门从老板视角优化工作日报。

请对以下日报初稿进行润色改写，要求：
1. **保留模板结构**：保持章节框架不变，只优化语言表达
2. **成果优先**：每个章节开头先说结果，再说过程
3. **使用目标完成动词**：多用"完成"、"推进"、"对齐"、"输出"、"跟进"等动词
4. **量化表达**：
   - 如果原文有数字/指标，请在润色版中保留或突出展示
   - 如果原文没有数字/指标，在应有数据的位置插入"（未提供量化指标）"标注，不得捏造数据
5. **简洁专业**：语气正式但不啰嗦，老板一眼能看到重点

注意：不要添加原文中没有的事实信息。只改语气和表达方式。"""


def polish_node(state: AgentState) -> dict:
    """Refine draft with boss-perspective polish (AGENT-07).

    Reads state["draft"] and returns {"polished": improved_text}.
    Uses goal-completion verbs and inserts quantification placeholder if needed (D-09, D-10).
    """
    draft = state.get("draft", "")
    if not draft or draft == "[stub draft]":
        return {"polished": draft or ""}

    llm = _make_llm()
    response = llm.invoke([
        SystemMessage(content=_POLISH_SYSTEM),
        HumanMessage(content=f"请润色以下日报初稿：\n\n{draft}"),
    ])
    return {"polished": response.content}
