"""
Phase 2 — Core LLM Nodes and Template Routing test suite.
Tests cover all 5 success criteria from ROADMAP.md §Phase 2.
Run: conda run -n llm-data-pipeline pytest tests/test_phase02_llm_nodes.py -v
All tests FAIL in RED state (stubs return placeholders, not real values).
"""
import pytest
from unittest.mock import patch, MagicMock
from workdiary_agent.state import AgentState, StructuredInfo
from workdiary_agent.nodes.extract import extract_node
from workdiary_agent.nodes.route_template import route_template_node
from workdiary_agent.nodes.draft import draft_node
from workdiary_agent.nodes.polish import polish_node


# ---------------------------------------------------------------------------
# SC-1 (AGENT-02): extract node returns populated StructuredInfo
# ---------------------------------------------------------------------------

def test_extract_node_returns_structured_info():
    """SC-1: extract_node must return structured_info with non-empty tasks, outputs, blockers, progress."""
    state: AgentState = {
        "raw_input": "今天完成了用户登录模块的单元测试，修了3个bug，还和产品对齐了需求，明天要做数据库迁移"
    }
    result = extract_node(state)
    assert "structured_info" in result
    info = result["structured_info"]
    assert info is not None, "structured_info must not be None"
    assert isinstance(info, StructuredInfo), f"Expected StructuredInfo, got {type(info)}"
    assert len(info.tasks) > 0, "tasks must be non-empty"
    assert len(info.outputs) > 0, "outputs must be non-empty"
    assert isinstance(info.blockers, list), "blockers must be a list"
    assert isinstance(info.progress, str) and len(info.progress) > 0, "progress must be non-empty string"


# ---------------------------------------------------------------------------
# SC-2 (AGENT-05, TMPL-01): TemplateRouterAgent classifies 3 types correctly
# ---------------------------------------------------------------------------

def test_router_classifies_templates():
    """SC-2: TemplateRouterAgent must classify tech/business/mixed inputs correctly."""
    try:
        from workdiary_agent.router.agent import TemplateRouterAgent
    except ImportError:
        pytest.fail("workdiary_agent.router.agent module not found — implement TemplateRouterAgent first")

    router = TemplateRouterAgent()

    tech_result = router.classify("今天实现了Redis缓存层，优化了SQL查询，修复了内存泄漏，写了单元测试")
    assert tech_result == "技术型", f"Expected '技术型', got '{tech_result}'"

    biz_result = router.classify("今天和客户对齐了Q2目标，确认了GMV增长15%的方案，推进了合同签署")
    assert biz_result == "业务型", f"Expected '业务型', got '{biz_result}'"

    mixed_result = router.classify("今天完成了支付接口优化，降低了超时率从5%到0.3%，同时跟进了商务合同和数据报表")
    assert mixed_result == "混合型", f"Expected '混合型', got '{mixed_result}'"


# ---------------------------------------------------------------------------
# SC-2 (TMPL-02): route_template_node writes template_type to state
# ---------------------------------------------------------------------------

def test_route_template_node_sets_template_type():
    """SC-2 + TMPL-02: route_template_node must classify content and set template_type correctly.
    A business-type input must yield '业务型', not the stub's hardcoded '技术型'.
    """
    # Tech input — should classify as 技术型
    tech_state: AgentState = {
        "raw_input": "今天实现了Redis缓存层，优化了SQL查询，修复了内存泄漏，写了单元测试",
        "structured_info": StructuredInfo(
            tasks=["实现Redis缓存", "优化SQL"],
            outputs=["缓存模块", "测试报告"],
            blockers=[],
            progress="完成"
        )
    }
    tech_result = route_template_node(tech_state)
    assert "template_type" in tech_result
    assert tech_result["template_type"] in {"技术型", "业务型", "混合型"}, \
        f"template_type must be one of the 3 types, got '{tech_result['template_type']}'"

    # Business input — must yield '业务型' (not stub's hardcoded '技术型')
    biz_state: AgentState = {
        "raw_input": "今天和客户对齐了Q2目标，确认了GMV增长15%的方案，推进了合同签署",
        "structured_info": StructuredInfo(
            tasks=["客户对齐Q2目标", "推进合同签署"],
            outputs=["GMV增长方案确认", "合同进展"],
            blockers=[],
            progress="完成"
        )
    }
    biz_result = route_template_node(biz_state)
    assert "template_type" in biz_result
    assert biz_result["template_type"] == "业务型", \
        f"Business-type input must yield '业务型', got '{biz_result['template_type']}'"


# ---------------------------------------------------------------------------
# SC-4 + SC-5 (TMPL-02, TMPL-03): draft node uses template_type from state
# ---------------------------------------------------------------------------

def test_draft_node_uses_template_type_from_state():
    """SC-4 + TMPL-03: draft_node must read template_type from state and produce template-specific draft.
    Also verifies '已选用XX模板' is visible in the draft (TMPL-02).
    """
    si = StructuredInfo(
        tasks=["实现Redis缓存"],
        outputs=["缓存模块上线"],
        blockers=["内存泄漏已修复"],
        progress="完成"
    )
    # Test that overriding template_type changes draft behaviour (TMPL-03)
    for ttype in ["技术型", "业务型", "混合型"]:
        state: AgentState = {
            "raw_input": "test input",
            "structured_info": si,
            "template_type": ttype,
        }
        result = draft_node(state)
        assert "draft" in result
        draft = result["draft"]
        assert draft is not None and len(draft) > 20, f"draft must be non-empty for template '{ttype}'"
        assert draft != "[stub draft]", "draft must not be the stub placeholder"
        # TMPL-02: "已选用XX模板" must be visible in draft
        assert "已选用" in draft and "模板" in draft, \
            f"TMPL-02: draft must contain '已选用XX模板', got: {draft[:100]}"


# ---------------------------------------------------------------------------
# SC-3 (AGENT-07): polish node produces boss-friendly output
# ---------------------------------------------------------------------------

def test_polish_node_produces_boss_friendly_output():
    """SC-3: polish_node must produce output with quantified statement or placeholder,
    and use goal-completion verbs (完成/推进/对齐/输出/跟进).
    """
    state: AgentState = {
        "raw_input": "今天完成了缓存优化",
        "structured_info": StructuredInfo(
            tasks=["缓存优化"],
            outputs=["优化完成"],
            blockers=[],
            progress="完成"
        ),
        "template_type": "技术型",
        "draft": "【已选用技术型模板】\n任务：缓存优化\n进度：完成\n下一步：上线"
    }
    result = polish_node(state)
    assert "polished" in result
    polished = result["polished"]
    assert polished is not None and len(polished) > 20, "polished output must be non-empty"
    assert polished != "[stub polished]", "polished must not be stub placeholder"

    # SC-3a: must contain quantified statement OR the placeholder
    has_quantified = any(c.isdigit() for c in polished)
    has_placeholder = "未提供量化指标" in polished
    assert has_quantified or has_placeholder, \
        "polished must contain a number (quantified) or '未提供量化指标' placeholder"

    # SC-3b: must use at least one goal-completion verb
    goal_verbs = ["完成", "推进", "对齐", "输出", "跟进"]
    assert any(v in polished for v in goal_verbs), \
        f"polished must use at least one of {goal_verbs}"
