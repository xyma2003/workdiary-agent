"""Streamlit UI for generation, checkpoint recovery, review, and history."""
import os
import uuid
import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

load_dotenv(override=False)  # load runtime paths/config before project modules

from workdiary_agent.graph import build_graph
from workdiary_agent.graph_constants import MAX_REVISIONS
from workdiary_agent.quality import analyze_report_quality
from workdiary_agent.recovery import list_recoverable_runs
from workdiary_agent.storage.export import delete_markdown
from workdiary_agent.storage.sqlite import count_reports, get_all_reports, get_report
from workdiary_agent.time_utils import work_date
from workdiary_agent.utils import LLMConfigurationError, validate_llm_configuration


# ---------------------------------------------------------------------------
# Cached graph factory — prevents reopening sqlite3 connection on every rerun (SC-5)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_graph():
    """Cache the compiled graph across reruns — prevents thread_id regeneration (SC-5)."""
    return build_graph(use_sqlite=True)


NODE_LABELS = {
    "extract": "已提取工作信息",
    "enrich": "已读取可信上下文",
    "route_template": "已选择日报模板",
    "draft": "已生成初稿",
    "polish": "已完成表达优化",
    "review": "等待人工审阅",
    "save": "已保存日报",
}


def _stream_graph(graph_input, config, status_ui=None):
    """Run/resume the graph and report node progress when updates arrive."""
    interrupt_payload = {}
    graph = get_graph()
    for update in graph.stream(graph_input, config, stream_mode="updates"):
        if not isinstance(update, dict):
            continue
        interrupts = update.get("__interrupt__") or []
        if interrupts:
            value = getattr(interrupts[0], "value", None)
            if isinstance(value, dict):
                interrupt_payload = value
        if status_ui is not None:
            for node_name in update:
                label = NODE_LABELS.get(node_name)
                if label:
                    status_ui.write(label)

    graph_state = graph.get_state(config)
    return dict(graph_state.values), interrupt_payload, "review" in (graph_state.next or [])


def _activate_checkpoint(thread_id: str) -> None:
    """Attach this browser session to an incomplete persisted graph thread."""
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = get_graph().get_state(config)
    if not snapshot.next:
        st.warning("该任务已经完成或不存在。")
        return

    st.session_state.thread_id = thread_id
    st.session_state.result = dict(snapshot.values or {})
    st.session_state._show_feedback = False
    if "review" in snapshot.next:
        st.session_state.app_state = "reviewing"
        st.session_state._resume_existing = False
    else:
        st.session_state.app_state = "generating"
        st.session_state._resume_existing = True
    st.rerun()


def _render_recoverable_runs() -> None:
    """Show unfinished checkpoint threads that can be reopened or retried."""
    try:
        runs = list_recoverable_runs(get_graph())
    except Exception:
        import logging
        logging.exception("Failed to list recoverable runs")
        return
    if not runs:
        return

    with st.expander(f"恢复未完成日报（{len(runs)}）", expanded=False):
        for run in runs:
            status = "待审阅" if run["status"] == "reviewing" else "待重试"
            preview = run["raw_input"].replace("\n", " ")[:60]
            label = f"{run.get('date') or '未定日期'} · {status} · {preview}"
            col_text, col_action = st.columns([5, 1])
            col_text.caption(label)
            if col_action.button(
                "恢复",
                key=f"recover_{run['thread_id']}",
                use_container_width=True,
            ):
                _activate_checkpoint(run["thread_id"])


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
        template_choice = st.selectbox(
            "日报模板",
            ["自动判断", "技术型", "业务型", "混合型"],
            key="template_choice_field",
        )
        repo_path = st.text_input(
            "Git 仓库路径（可选）",
            placeholder="/path/to/your/repo",
            key="repo_path_field",
        )
        with st.expander("Git 提交归属设置"):
            git_author = st.text_input(
                "Git 作者或邮箱（推荐）",
                placeholder="name@example.com；留空时读取仓库 git user.email",
                key="git_author_field",
            )
            timezone = st.text_input(
                "工作日时区",
                value=os.environ.get("WORKDIARY_TIMEZONE", ""),
                placeholder="例如 Asia/Shanghai；留空使用系统时区",
                key="timezone_field",
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
        try:
            validate_llm_configuration()
        except LLMConfigurationError as exc:
            st.error(f"模型配置不完整：{exc}")
            return
        # Every submission gets a fresh checkpoint thread. Failed or unfinished
        # threads remain separately recoverable instead of leaking state here.
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state._pending_raw_input = raw_input.strip()
        st.session_state._pending_repo_path = repo_path.strip() or None
        st.session_state._pending_git_author = git_author.strip() or None
        st.session_state._pending_timezone = timezone.strip() or None
        st.session_state._pending_template_type = (
            None if template_choice == "自动判断" else template_choice
        )
        st.session_state._pending_report_date = work_date(timezone.strip() or None)
        st.session_state._pending_data_input = data_input.strip() or None
        st.session_state._pending_report_id = uuid.uuid4().hex
        st.session_state._resume_existing = False
        st.session_state.app_state = "generating"
        st.rerun()

    # Generation / reviewing / done states rendered below form
    # (Plan 06-02 will fill in _render_status_and_review())
    if st.session_state.app_state != "idle":
        _render_status_and_review()
    else:
        _render_recoverable_runs()


def _render_status_and_review():
    """Renders generation progress or review UI depending on app_state."""

    if st.session_state.app_state == "generating":
        _run_generation()

    if st.session_state.app_state == "reviewing":
        _render_review_ui()

    if st.session_state.app_state == "failed":
        _render_failure_ui()

    if st.session_state.app_state == "done":
        st.success("日报已完成并保存。")
        if st.button("重新生成", key="restart_btn"):
            # Reset for a new report — generate a fresh thread_id (new session)
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.app_state = "idle"
            st.session_state.result = None
            st.session_state._show_feedback = False
            st.session_state._resume_existing = False
            st.rerun()


def _run_generation():
    """Invokes the graph and shows st.status node progress labels (D-11, D-12, D-13)."""
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    resume_existing = st.session_state.get("_resume_existing", False)
    if resume_existing:
        graph_input = None
        report_id = (st.session_state.result or {}).get("report_id")
    else:
        raw_input = st.session_state._pending_raw_input
        repo_path = st.session_state._pending_repo_path
        git_author = st.session_state._pending_git_author
        timezone = st.session_state._pending_timezone
        data_input = st.session_state._pending_data_input
        report_id = st.session_state._pending_report_id
        graph_input = {
            "raw_input": raw_input,
            "repo_path": repo_path,
            "git_author": git_author,
            "timezone": timezone,
            "template_type": st.session_state._pending_template_type,
            "data_input": data_input,
            "date": st.session_state._pending_report_date,
            "report_id": report_id,
            "feedback_history": [],
            "revision_count": 0,
        }

    with st.status("正在生成日报...", expanded=True) as status_ui:
        try:
            result, interrupt_payload, is_reviewing = _stream_graph(
                graph_input,
                config,
                status_ui,
            )
        except Exception:
            import logging
            logging.exception("Graph invoke failed")
            status_ui.update(label="生成失败，请重试", state="error")
            snapshot = get_graph().get_state(config)
            st.session_state.result = dict(snapshot.values or {})
            st.session_state._resume_existing = True
            st.session_state.app_state = "failed"
            return

        if is_reviewing:
            polished = interrupt_payload.get("polished") or result.get("polished", "")
            template_type = result.get("template_type", "混合型")
            revision_count = interrupt_payload.get(
                "revision_count", result.get("revision_count", 0)
            )

            st.session_state.result = {
                **result,
                "polished": polished,
                "template_type": template_type,
                "revision_count": revision_count,
                "report_id": result.get("report_id", report_id),
                "interrupt_payload": interrupt_payload,
            }
            st.session_state._resume_existing = False
            st.session_state.app_state = "reviewing"
            status_ui.update(label="生成完成，请审阅", state="complete", expanded=False)
            st.rerun()
        else:
            # Graph completed without interrupt (edge case — no review pause)
            st.session_state.result = result
            st.session_state._resume_existing = False
            st.session_state.app_state = "done"
            status_ui.update(label="生成完成", state="complete", expanded=False)
            st.rerun()


def _render_failure_ui():
    """Offer checkpoint-safe retry or explicit discard after a node failure."""
    st.error("日报生成中断。可以从最近的节点重试，不会创建重复日报。")
    col_retry, col_discard = st.columns(2)
    if col_retry.button("重试当前日报", type="primary", use_container_width=True):
        st.session_state._resume_existing = True
        st.session_state.app_state = "generating"
        st.rerun()
    if col_discard.button("放弃当前日报", use_container_width=True):
        abandoned = dict(st.session_state.result or {})
        try:
            get_graph().checkpointer.delete_thread(st.session_state.thread_id)
        except Exception:
            import logging
            logging.exception("Failed to discard checkpoint thread")
            st.error("删除未完成任务失败，请重试。")
            return
        # A crash between file export and the history DB write can leave an
        # orphan. Only remove it after confirming there is no persisted row.
        try:
            report_id = abandoned.get("report_id")
            report_date = abandoned.get("date")
            if report_id and report_date and get_report(report_id) is None:
                delete_markdown(report_date, report_id)
        except Exception:
            import logging
            logging.exception("Failed to clean abandoned report export")
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.result = None
        st.session_state._show_feedback = False
        st.session_state._resume_existing = False
        st.session_state.app_state = "idle"
        st.rerun()


def _render_review_ui():
    """Review view: editable text_area + accept/revise/export buttons (D-14 through D-19)."""
    result = st.session_state.result or {}
    polished = result.get("polished", "")
    template_type = result.get("template_type", "未知模板")
    revision_count = result.get("revision_count", 0)

    # D-13 equivalent: show selected template (TMPL-02 visibility)
    st.caption(f"已选用 {template_type} 模板")

    # D-14: editable text_area pre-filled with polished content (HITL-02 inline editing)
    edit_key = f"edit_area_{st.session_state.thread_id}_{revision_count}"
    edited_text = st.text_area(
        "日报内容（可直接编辑）",
        value=polished,
        height=300,
        key=edit_key,
    )

    # Three-button row (D-15)
    col1, col2, col3 = st.columns(3)

    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    # D-15 + D-16 + D-18: Accept button — passes edited text back to graph so save_node persists it
    with col1:
        if st.button("✓ 接受", type="primary", use_container_width=True, key="accept_btn"):
            # D-18: read current value from session_state (includes user's inline edits)
            current_text = st.session_state.get(edit_key, polished)
            if not current_text.strip():
                st.warning("日报内容不能为空")
                return
            try:
                r = get_graph().invoke(
                    Command(resume={
                        "decision": "approve",
                        "feedback": "",
                        "edited_text": current_text,
                    }),
                    config,
                )
                # save_node already persisted current_text via edited_text in state
                st.session_state.result = dict(r)
                st.session_state.result["polished"] = current_text
                st.session_state.app_state = "done"
                st.rerun()
            except Exception:
                import logging
                logging.exception("Accept failed")
                st.session_state._resume_existing = True
                st.session_state.app_state = "failed"
                return

    # D-15 + D-17: Revise button — shows feedback input, then resumes with revise decision
    with col2:
        if st.button(
            "↻ 重新生成",
            use_container_width=True,
            key="revise_btn",
            disabled=revision_count >= MAX_REVISIONS,
        ):
            st.session_state._show_feedback = True

    if revision_count >= MAX_REVISIONS:
        st.info("已达到修改上限，请直接编辑后接受；系统不会自动保存未经确认的版本。")

    if result.get("git_log") or result.get("data_summary"):
        with st.expander("本次生成依据", expanded=False):
            if result.get("git_log"):
                st.markdown("**Git commits**")
                st.code(result["git_log"], language="text")
            if result.get("data_summary"):
                st.markdown("**数据指标**")
                st.text(result["data_summary"])

    quality = analyze_report_quality({**result, "edited_text": edited_text})
    if quality["warnings"]:
        with st.expander("保存前事实检查", expanded=True):
            for warning in quality["warnings"]:
                st.warning(warning)

    if st.session_state.get("_show_feedback"):
        feedback = st.text_input("修改意见", key="feedback_input", placeholder="请说明修改方向...")
        if st.button("确认修改", key="confirm_revise_btn"):
            if not feedback.strip():
                st.warning("请填写修改意见")
            else:
                try:
                    current_text = st.session_state.get(edit_key, polished)
                    if not current_text.strip():
                        st.warning("日报内容不能为空")
                        return
                    result2, interrupt_payload, is_reviewing = _stream_graph(
                        Command(resume={
                            "decision": "revise",
                            "feedback": feedback.strip(),
                            "edited_text": current_text,
                        }),
                        config,
                    )
                    if is_reviewing:
                        new_polished = interrupt_payload.get("polished") or result2.get("polished", polished)
                        new_template = result2.get("template_type", template_type)
                        st.session_state.result = {
                            **result2,
                            "polished": new_polished,
                            "template_type": new_template,
                            "revision_count": interrupt_payload.get(
                                "revision_count", result2.get("revision_count", revision_count + 1)
                            ),
                            "report_id": result2.get("report_id", result.get("report_id")),
                            "interrupt_payload": interrupt_payload,
                        }
                        st.session_state._show_feedback = False
                        st.session_state.app_state = "reviewing"
                    else:
                        st.session_state.result = dict(result2)
                        st.session_state.app_state = "done"
                    st.rerun()
                except Exception:
                    import logging
                    logging.exception("Revise failed")
                    st.session_state._resume_existing = True
                    st.session_state.app_state = "failed"
                    return

    # D-15 + D-19: Export download button — passes polished text directly (no file read, no reload)
    with col3:
        export_text = st.session_state.get(edit_key, polished) or polished
        export_id = (result.get("report_id") or st.session_state.thread_id)[:8]
        report_date = result.get("date") or work_date(result.get("timezone"))
        st.download_button(
            label="⬇ 导出",
            data=export_text,
            file_name=f"daily_report_{report_date}_{export_id}.md",
            mime="text/markdown",
            use_container_width=True,
            key="export_btn",
        )


def _render_history_page():
    """History view with search, filters, pagination, and export."""
    st.title("历史记录")

    col_query, col_template = st.columns([3, 1])
    with col_query:
        query = st.text_input(
            "搜索内容",
            placeholder="搜索原始输入或日报内容",
            key="history_query",
        ).strip()
    with col_template:
        template_choice = st.selectbox(
            "模板类型",
            ["全部", "技术型", "业务型", "混合型"],
            key="history_template_filter",
        )
    date_range = st.date_input(
        "日期范围",
        value=(),
        format="YYYY-MM-DD",
        key="history_date_range",
    )
    date_from = date_to = None
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        date_from = date_range[0].isoformat()
        date_to = date_range[1].isoformat()
    elif isinstance(date_range, (tuple, list)) and len(date_range) == 1:
        st.caption("请继续选择结束日期；选定前暂不应用日期筛选。")

    template_type = None if template_choice == "全部" else template_choice
    filter_signature = (query, template_type, date_from, date_to)
    if st.session_state.get("_history_filter_signature") != filter_signature:
        st.session_state._history_filter_signature = filter_signature
        st.session_state.history_page = 0

    col_refresh, _ = st.columns([1, 5])
    with col_refresh:
        if st.button("刷新", key="history_refresh_btn"):
            st.rerun()

    page_size = 10
    filters = {
        "query": query or None,
        "template_type": template_type,
        "date_from": date_from,
        "date_to": date_to,
    }
    try:
        total = count_reports(**filters)
        max_page = max((total - 1) // page_size, 0)
        current_page = min(st.session_state.get("history_page", 0), max_page)
        st.session_state.history_page = current_page
        reports = get_all_reports(
            **filters,
            limit=page_size,
            offset=current_page * page_size,
        )
    except Exception:
        import logging
        logging.exception("Failed to load history")
        st.error("无法加载历史记录，请刷新重试。")
        return

    if not reports:
        if any(filters.values()):
            st.info("没有符合当前筛选条件的记录。")
        else:
            st.info("暂无历史记录。生成并接受一篇日报后，记录将出现在这里。")
        return

    st.markdown(f"共 **{total}** 条记录")

    for r in reports:
        # D-21: st.expander labeled with date and template_type
        label = f"{r['date']} — {r.get('template_type') or '未知模板'}"
        with st.expander(label, expanded=False):
            st.caption(f"创建时间: {r.get('created_at', '')}")
            st.markdown("**原始输入:**")
            st.text(r.get("raw_input", ""))
            st.markdown("**日报内容:**")
            st.markdown(r.get("polished", ""))
            # Inline export from history
            st.download_button(
                label="⬇ 导出此记录",
                data=r.get("polished", ""),
                file_name=(
                    f"daily_report_{r['date']}_"
                    f"{(r.get('report_id') or str(r['id']))[:8]}.md"
                ),
                mime="text/markdown",
                key=f"hist_export_{r['id']}",
            )

    if total > page_size:
        previous, page_label, following = st.columns([1, 2, 1])
        if previous.button(
            "上一页",
            disabled=current_page == 0,
            key="history_previous_page",
            use_container_width=True,
        ):
            st.session_state.history_page = current_page - 1
            st.rerun()
        page_label.markdown(
            f"<p style='text-align:center'>第 {current_page + 1} / {max_page + 1} 页</p>",
            unsafe_allow_html=True,
        )
        if following.button(
            "下一页",
            disabled=current_page >= max_page,
            key="history_next_page",
            use_container_width=True,
        ):
            st.session_state.history_page = current_page + 1
            st.rerun()


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="智能日报 Agent", page_icon="📝", layout="wide")

# ---------------------------------------------------------------------------
# session_state initialization — guarded with 'not in' so reruns don't reset them (SC-5)
# Keys are initialized once per browser session and retained across reruns.
# ---------------------------------------------------------------------------

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "app_state" not in st.session_state:
    st.session_state.app_state = "idle"   # idle | generating | reviewing | done
if "result" not in st.session_state:
    st.session_state.result = None
if "_show_feedback" not in st.session_state:
    st.session_state._show_feedback = False
if "_resume_existing" not in st.session_state:
    st.session_state._resume_existing = False
if "history_page" not in st.session_state:
    st.session_state.history_page = 0

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
