# workdiary_agent/nodes/enrich.py
"""Enrich node: read today's git commits and extract metrics from pasted data.

Phase 3 implementation (replaces stub from Phase 1).

Decision references:
  D-01 to D-04: Git reading scope, GitPython, format, error handling
  D-05 to D-07: data_input field, data_summary field, skip LLM when empty
  D-08 to D-10: Single node, git-first then LLM, return both fields

Node signature follows project convention: def xxx_node(state: AgentState) -> dict
"""
import os
from datetime import datetime, date

import git
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from ..state import AgentState


# ---------------------------------------------------------------------------
# Helper: build ChatAnthropic with ANTHROPIC_CUSTOM_HEADERS if set
# (Copied verbatim from extract.py — Meituan proxy requirement)
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


# ---------------------------------------------------------------------------
# System prompt for data_input metric extraction
# ---------------------------------------------------------------------------

_DATA_EXTRACT_SYSTEM = """你是一个数据指标提取助手。请从用户粘贴的文本中，识别并提取所有关键数字指标，
包括：百分比、绝对数值、时间指标、对比数据（如"从200ms降到45ms"）等。

输出格式：每行一条关键指标，简洁描述，例如：
- 转化率：15%（环比+3pp）
- GMV：环比增长20%
- 响应时间：从200ms降到45ms

只提取文本中明确出现的数据，不推断或捏造。若无有效指标，输出"无有效数字指标"。"""


# ---------------------------------------------------------------------------
# Git log reading
# ---------------------------------------------------------------------------

def _read_git_log(repo_path: str) -> str | None:
    """Read today's commits from repo_path using GitPython.

    Returns formatted multi-line string or None on any error/empty.
    Format per commit: "{hash[:7]} {message}"

    Catches all git errors (D-04):
      git.InvalidGitRepositoryError, git.NoSuchPathError, git.GitCommandError, Exception
    """
    if not repo_path:
        return None
    try:
        repo = git.Repo(repo_path)
        today = datetime.combine(date.today(), datetime.min.time())
        commits = list(repo.iter_commits(since=today.isoformat()))
        if not commits:
            return None
        return "\n".join(f"{c.hexsha[:7]} {c.message.strip()}" for c in commits)
    except git.InvalidGitRepositoryError:
        return None
    except git.NoSuchPathError:
        return None
    except git.GitCommandError:
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Data input metric extraction
# ---------------------------------------------------------------------------

def _extract_data_summary(data_input: str) -> str | None:
    """Use LLM to extract key metrics from pasted numeric/tabular text.

    Returns extracted metrics summary or None on empty input.
    """
    if not data_input or not data_input.strip():
        return None
    llm = _make_llm()
    response = llm.invoke([
        SystemMessage(content=_DATA_EXTRACT_SYSTEM),
        HumanMessage(content=f"请提取以下文本中的关键数字指标：\n\n{data_input}"),
    ])
    content = response.content
    if not content or content.strip() == "无有效数字指标":
        return None
    return content.strip()


# ---------------------------------------------------------------------------
# Node entrypoint
# ---------------------------------------------------------------------------

def enrich_node(state: AgentState) -> dict:
    """Enrich state with git commit log and extracted data metrics.

    Step 1 (D-09): Read git log (sync IO) — always runs.
    Step 2 (D-09): Extract data metrics via LLM — only when data_input is non-empty.

    Returns partial state update with git_log and data_summary (both may be None).
    """
    # Step 1: Git log (D-01 to D-04)
    repo_path = state.get("repo_path", "") or ""
    git_log = _read_git_log(repo_path)

    # Step 2: Data input extraction (D-05 to D-07)
    data_input = state.get("data_input", "") or ""
    data_summary = _extract_data_summary(data_input)

    # D-10: return both fields, both can be None
    return {"git_log": git_log, "data_summary": data_summary}
