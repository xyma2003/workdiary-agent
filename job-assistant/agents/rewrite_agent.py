from crewai import Agent, LLM
from config import SONNET, ANTHROPIC_API_KEY


def make_rewrite_agent() -> Agent:
    llm = LLM(
        model=SONNET,
        api_key=ANTHROPIC_API_KEY,
        max_tokens=4096,
    )
    return Agent(
        role="Resume Tailoring Specialist",
        goal=(
            "Rewrite the candidate's resume to maximally match the target job "
            "description. Preserve all factual content — only reframe, "
            "reorder, and emphasize. Never fabricate experience."
        ),
        backstory=(
            "You are an expert resume writer who has helped 500+ candidates "
            "land interviews at top tech companies. You know how to mirror "
            "job description language while keeping the resume authentic."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
