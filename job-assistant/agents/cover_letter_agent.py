from crewai import Agent, LLM
from config import SONNET, ANTHROPIC_API_KEY


def make_cover_letter_agent() -> Agent:
    llm = LLM(
        model=SONNET,
        api_key=ANTHROPIC_API_KEY,
        max_tokens=2048,
    )
    return Agent(
        role="Cover Letter Writer",
        goal=(
            "Write a compelling, personalized cover letter that connects the "
            "candidate's experience to the specific role and company. "
            "Should be concise (3–4 paragraphs), confident, and human."
        ),
        backstory=(
            "You are a professional writer who specializes in job application "
            "materials. You write cover letters that get read — not the "
            "generic templates that go straight to the trash."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
