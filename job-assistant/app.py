import streamlit as st
from crew import run_job_assistant

st.set_page_config(page_title="求职助手", page_icon="💼", layout="wide")
st.title("💼 AI 求职助手")
st.caption("粘贴你的简历和目标 JD，4 个 AI Agent 协作生成定制简历 + Cover Letter + 评分")

# --- 输入区 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("你的简历")
    resume = st.text_area(
        "粘贴简历（纯文本或 Markdown）",
        height=400,
        placeholder="粘贴你的简历内容...",
        label_visibility="collapsed",
    )

with col2:
    st.subheader("目标职位 JD")
    job_description = st.text_area(
        "粘贴职位描述",
        height=400,
        placeholder="粘贴招聘 JD 全文...",
        label_visibility="collapsed",
    )

# --- 运行按钮 ---
if st.button("🚀 开始分析", type="primary", use_container_width=True):
    if not resume.strip():
        st.error("请先粘贴你的简历")
    elif not job_description.strip():
        st.error("请先粘贴职位 JD")
    else:
        with st.spinner("4 个 Agent 正在协作分析中，预计需要 1–2 分钟..."):
            try:
                results = run_job_assistant(resume, job_description)
                st.session_state["results"] = results
                st.success("分析完成！")
            except Exception as e:
                st.error(f"运行出错：{e}")

# --- 结果展示 ---
if "results" in st.session_state:
    results = st.session_state["results"]

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 JD 分析", "📄 定制简历", "✉️ Cover Letter", "⭐ 评分报告"
    ])

    with tab1:
        st.markdown(results.get("jd_analysis", ""))
        st.download_button(
            "下载 JD 分析", results.get("jd_analysis", ""),
            file_name="jd_analysis.md", mime="text/markdown"
        )

    with tab2:
        st.markdown(results.get("tailored_resume", ""))
        st.download_button(
            "下载定制简历", results.get("tailored_resume", ""),
            file_name="tailored_resume.md", mime="text/markdown"
        )

    with tab3:
        st.markdown(results.get("cover_letter", ""))
        st.download_button(
            "下载 Cover Letter", results.get("cover_letter", ""),
            file_name="cover_letter.md", mime="text/markdown"
        )

    with tab4:
        st.markdown(results.get("review", ""))
        st.download_button(
            "下载评分报告", results.get("review", ""),
            file_name="review.md", mime="text/markdown"
        )
