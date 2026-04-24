"""
app.py — 智能日报 Agent Streamlit application.

Plan 06-01: Scaffold with session_state init, sidebar navigation, input form, and cached graph.
Plan 06-02: Full generation flow — graph invoke with st.status node labels, interrupt detection,
            HITL review UI with editable text_area, accept/revise/export buttons.
Subsequent plans (06-03) extend this file with history page logic.
"""
import uuid
from datetime import date
import streamlit as st
from langgraph.types import Command
from workdiary_agent.graph import build_graph
from workdiary_agent.storage.sqlite import get_all_reports


# ---------------------------------------------------------------------------
# Cached graph factory — prevents reopening sqlite3 connection on every rerun (SC-5)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_graph():
    """Cache the compiled graph across reruns — prevents thread_id regeneration (SC-5)."""
    return build_graph(use_sqlite=True)


# ---------------------------------------------------------------------------
# Page renderers (defined before routing so names are available at call time)
# ---------------------------------------------------------------------------

def _render_generate_page():
    """Render the 生成日报 page: input form and status/review area."""
    st.title("智能日报 Agent")
    st.markdown("将今天的工作描述转化为老板爱看的专业日报。")

    with st.form("input_form"):
        raw_input = st.text_area(
            "工作描述 *",
            placeholder="今天完成了登录模块开发，解决了token过期的bug...",
            height=150,
            key="raw_input_field",
        )
        repo_path = st.text_input(
            "Git 仓库路径（可选）",
            placeholder="/path/to/your/repo",
            key="repo_path_field",
        )
        data_input = st.text_area(
            "数据/指标（可选粘贴）",
            placeholder="DAU: 12000, 转化率: 3.2%, ...",
            height=80,
            key="data_input_field",
        )
        submitted = st.form_submit_button("生成日报", type="primary", use_container_width=True)

    if submitted:
        if not raw_input.strip():
            st.error("请填写工作描述（必填）")
            return
        # Store inputs for use by generation logic (Plan 06-02 will invoke graph here)
        st.session_state._pending_raw_input = raw_input.strip()
        st.session_state._pending_repo_path = repo_path.strip() or None
        st.session_state._pending_data_input = data_input.strip() or None
        st.session_state.app_state = "generating"
        st.rerun()

    # Generation / reviewing / done states rendered below form
    # (Plan 06-02 will fill in _render_status_and_review())
    if st.session_state.app_state != "idle":
        _render_status_and_review()


def _render_status_and_review():
    """Renders generation progress or review UI depending on app_state."""

    if st.session_state.app_state == "generating":
        _run_generation()

    if st.session_state.app_state == "reviewing":
        _render_review_ui()

    if st.session_state.app_state == "done":
        st.success("日报已完成并保存。")
        if st.button("重新生成", key="restart_btn"):
            # Reset for a new report — generate a fresh thread_id (new session)
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.app_state = "idle"
            st.session_state.result = None
            st.session_state._show_feedback = False
            st.rerun()


def _run_generation():
    """Invokes the graph and shows st.status node progress labels (D-11, D-12, D-13)."""
    # Node label mapping per D-12
    NODE_LABELS = {
        "extract":        "正在提取信息...",
        "enrich":         "正在丰富上下文...",
        "route_template": "正在判断日报类型...",
        "draft":          "正在生成初稿...",
        "polish":         "正在润色...",
        "review":         "等待审阅...",
    }

    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    raw_input  = st.session_state._pending_raw_input
    repo_path  = st.session_state._pending_repo_path
    data_input = st.session_state._pending_data_input

    with st.status("正在生成日报...", expanded=True) as status_ui:
        # Write sequential node labels — st.status keeps them visible.
        # Labels appear before the blocking invoke() call so the user sees progress context.
        for label in NODE_LABELS.values():
            st.write(label)

        try:
            result = get_graph().invoke(
                {
                    "raw_input": raw_input,
                    "repo_path": repo_path,
                    "data_input": data_input,
                },
                config,
            )
        except Exception as e:
            status_ui.update(label=f"生成失败: {e}", state="error")
            st.session_state.app_state = "idle"
            st.error(f"图执行出错: {e}")
            return

        # Check interrupt: graph paused at review node
        graph_state = get_graph().get_state(config)
        if "review" in (graph_state.next or []):
            # Extract polished content from interrupt payload
            interrupt_payload = {}
            if "__interrupt__" in result and result["__interrupt__"]:
                interrupt_payload = result["__interrupt__"][0].value

            polished = interrupt_payload.get("polished") or result.get("polished", "")
            template_type = result.get("template_type", "混合型")

            st.session_state.result = {
                "polished": polished,
                "template_type": template_type,
                "interrupt_payload": interrupt_payload,
            }
            st.session_state.app_state = "reviewing"
            status_ui.update(label="生成完成，请审阅", state="complete", expanded=False)
            st.rerun()
        else:
            # Graph completed without interrupt (edge case — no review pause)
            st.session_state.result = result
            st.session_state.app_state = "done"
            status_ui.update(label="生成完成", state="complete", expanded=False)
            st.rerun()


def _render_review_ui():
    """Review view: editable text_area + accept/revise/export buttons (D-14 through D-19)."""
    result = st.session_state.result or {}
    polished = result.get("polished", "")
    template_type = result.get("template_type", "未知模板")

    # D-13 equivalent: show selected template (TMPL-02 visibility)
    st.caption(f"已选用 {template_type} 模板")

    # D-14: editable text_area pre-filled with polished content (HITL-02 inline editing)
    edited_text = st.text_area(
        "日报内容（可直接编辑）",
        value=polished,
        height=300,
        key="edit_area",   # key ensures st.session_state["edit_area"] holds current value
    )

    # Three-button row (D-15)
    col1, col2, col3 = st.columns(3)

    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    # D-15 + D-16 + D-18: Accept button — uses edited text if different from polished
    with col1:
        if st.button("✓ 接受", type="primary", use_container_width=True, key="accept_btn"):
            # D-18: if user edited inline, read current value from session_state
            current_text = st.session_state.get("edit_area", polished)
            try:
                r = get_graph().invoke(
                    Command(resume={"decision": "approve", "feedback": ""}),
                    config,
                )
                # If user edited inline, preserve the edited version in result for export
                if current_text != polished:
                    st.session_state.result = dict(r)
                    st.session_state.result["polished"] = current_text
                else:
                    st.session_state.result = dict(r)
                st.session_state.app_state = "done"
                st.rerun()
            except Exception as e:
                st.error(f"接受失败: {e}")

    # D-15 + D-17: Revise button — shows feedback input, then resumes with revise decision
    with col2:
        if st.button("↻ 重新生成", use_container_width=True, key="revise_btn"):
            st.session_state._show_feedback = True

    if st.session_state.get("_show_feedback"):
        feedback = st.text_input("修改意见", key="feedback_input", placeholder="请说明修改方向...")
        if st.button("确认修改", key="confirm_revise_btn"):
            if not feedback.strip():
                st.warning("请填写修改意见")
            else:
                try:
                    result2 = get_graph().invoke(
                        Command(resume={"decision": "revise", "feedback": feedback.strip()}),
                        config,
                    )
                    # After revise, graph pauses at review again — update result
                    graph_state = get_graph().get_state(config)
                    if "review" in (graph_state.next or []):
                        interrupt_payload = {}
                        if "__interrupt__" in result2 and result2["__interrupt__"]:
                            interrupt_payload = result2["__interrupt__"][0].value
                        new_polished = interrupt_payload.get("polished") or result2.get("polished", polished)
                        new_template = result2.get("template_type", template_type)
                        st.session_state.result = {
                            "polished": new_polished,
                            "template_type": new_template,
                            "interrupt_payload": interrupt_payload,
                        }
                        st.session_state._show_feedback = False
                        st.session_state.app_state = "reviewing"
                    else:
                        # Force-exit after 3 revisions — graph reached save
                        st.session_state.result = dict(result2)
                        st.session_state.app_state = "done"
                    st.rerun()
                except Exception as e:
                    st.error(f"重新生成失败: {e}")

    # D-15 + D-19: Export download button — passes polished text directly (no file read, no reload)
    with col3:
        export_text = st.session_state.get("edit_area", polished) or polished
        st.download_button(
            label="⬇ 导出",
            data=export_text,
            file_name=f"daily_report_{date.today()}.md",
            mime="text/markdown",
            use_container_width=True,
            key="export_btn",
        )


def _render_history_page():
    """Placeholder — implemented in Plan 06-03."""
    st.title("历史记录")
    st.info("加载中...")


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="智能日报 Agent", page_icon="📝", layout="wide")

# ---------------------------------------------------------------------------
# session_state initialization — guarded with 'not in' so reruns don't reset them (SC-5)
# All three keys must be initialized at module level (not inside any conditional branch)
# ---------------------------------------------------------------------------

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "app_state" not in st.session_state:
    st.session_state.app_state = "idle"   # idle | generating | reviewing | done
if "result" not in st.session_state:
    st.session_state.result = None
if "_show_feedback" not in st.session_state:
    st.session_state._show_feedback = False

# ---------------------------------------------------------------------------
# Sidebar navigation (D-01, D-02)
# ---------------------------------------------------------------------------

page = st.sidebar.radio("导航", ["生成日报", "历史记录"])

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------

if page == "生成日报":
    _render_generate_page()
else:
    _render_history_page()
