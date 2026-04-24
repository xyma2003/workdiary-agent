"""
app.py — 智能日报 Agent Streamlit application.

Plan 06-01: Scaffold with session_state init, sidebar navigation, input form, and cached graph.
Subsequent plans (06-02, 06-03) extend this file with graph invocation and history page logic.
"""
import uuid
import streamlit as st
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
    """Placeholder — implemented in Plan 06-02."""
    if st.session_state.app_state == "generating":
        st.info("正在生成日报，请稍候...")


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
