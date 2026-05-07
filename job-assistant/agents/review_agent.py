from crewai import Agent, LLM
from config import HAIKU, ANTHROPIC_API_KEY


def make_review_agent() -> Agent:
    llm = LLM(
        model=HAIKU,
        api_key=ANTHROPIC_API_KEY,
        max_tokens=1024,
    )
    return Agent(
        role="Application Quality Reviewer",
        goal=(
            "Score the tailored resume and cover letter against the job "
            "description. Identify gaps, suggest improvements, and give an "
            "overall match score from 0 to 100."
        ),
        backstory=(
            "You are a hiring manager who reviews hundreds of applications. "
            "You give honest, blunt feedback — no sugarcoating. Your goal is "
            "to help the candidate improve before they submit."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
