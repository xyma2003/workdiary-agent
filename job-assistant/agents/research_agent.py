from crewai import Agent, LLM
from config import HAIKU, ANTHROPIC_API_KEY


def make_research_agent() -> Agent:
    llm = LLM(
        model=HAIKU,
        api_key=ANTHROPIC_API_KEY,
        max_tokens=2048,
    )
    return Agent(
        role="Job Description Analyst",
        goal=(
            "Extract and structure all key information from a job description: "
            "required skills, responsibilities, company culture, and keywords "
            "that should appear in a strong application."
        ),
        backstory=(
            "You are a senior recruiter with 10 years of experience screening "
            "resumes. You know exactly what hiring managers look for and can "
            "identify the 20% of requirements that matter most."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
