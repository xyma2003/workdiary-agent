import os
from crewai import Crew, Task, Process
from agents import (
    make_research_agent,
    make_rewrite_agent,
    make_cover_letter_agent,
    make_review_agent,
)
from config import OUTPUT_DIR


def run_job_assistant(resume: str, job_description: str) -> dict:
    """
    Run the full 4-agent job application pipeline.

    Args:
        resume: Full resume text (plain text or markdown)
        job_description: Full JD text pasted from the job posting

    Returns:
        dict with keys: jd_analysis, tailored_resume, cover_letter, review
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # --- Agents ---
    research_agent = make_research_agent()
    rewrite_agent = make_rewrite_agent()
    cover_letter_agent = make_cover_letter_agent()
    review_agent = make_review_agent()

    # --- Tasks ---
    jd_task = Task(
        description=(
            "Analyze the following job description thoroughly.\n\n"
            "Job Description:\n{job_description}\n\n"
            "Extract:\n"
            "1. Must-have skills and experience\n"
            "2. Nice-to-have skills\n"
            "3. Key responsibilities\n"
            "4. Company culture signals\n"
            "5. Keywords the resume MUST contain to pass ATS screening\n"
            "6. Red flags or unusual requirements"
        ),
        expected_output=(
            "A structured analysis with sections: Required Skills, "
            "Nice-to-Have, Responsibilities, Culture, ATS Keywords, Red Flags."
        ),
        agent=research_agent,
        output_file=f"{OUTPUT_DIR}/jd_analysis.md",
    )

    rewrite_task = Task(
        description=(
            "Rewrite the resume below to best match the job description analysis "
            "from the previous task. Mirror keywords, reorder bullet points by "
            "relevance, and strengthen impact statements.\n\n"
            "Original Resume:\n{resume}\n\n"
            "Rules:\n"
            "- Do NOT invent experience or skills\n"
            "- Keep all dates, company names, and titles accurate\n"
            "- Output clean markdown formatted for readability"
        ),
        expected_output=(
            "A complete tailored resume in markdown, with experience bullet "
            "points rewritten to match the JD keywords and requirements."
        ),
        agent=rewrite_agent,
        output_file=f"{OUTPUT_DIR}/tailored_resume.md",
    )

    cover_letter_task = Task(
        description=(
            "Write a cover letter for this application.\n\n"
            "Use the JD analysis and tailored resume from previous tasks.\n\n"
            "Structure:\n"
            "1. Opening: Hook that shows genuine interest in this specific role\n"
            "2. Body (2 paragraphs): Connect 2–3 specific experiences to JD requirements\n"
            "3. Closing: Clear call to action\n\n"
            "Tone: Professional but human. No clichés like 'I am writing to apply'."
        ),
        expected_output=(
            "A 3–4 paragraph cover letter in markdown, personalized to the "
            "specific role and company."
        ),
        agent=cover_letter_agent,
        output_file=f"{OUTPUT_DIR}/cover_letter.md",
    )

    review_task = Task(
        description=(
            "Review the complete application package and provide honest feedback.\n\n"
            "Evaluate:\n"
            "1. Resume-JD keyword match (did we hit the ATS keywords?)\n"
            "2. Experience relevance (does the experience actually match?)\n"
            "3. Cover letter strength (compelling? specific? human?)\n"
            "4. Overall gaps (what's missing or weak?)\n"
            "5. Top 3 improvements to make before submitting\n\n"
            "End with an overall match score from 0–100."
        ),
        expected_output=(
            "A structured review with sections for each evaluation area, "
            "top 3 improvements, and a final match score (0–100)."
        ),
        agent=review_agent,
        context=[jd_task, rewrite_task, cover_letter_task],
        output_file=f"{OUTPUT_DIR}/review.md",
    )

    # --- Crew ---
    crew = Crew(
        agents=[research_agent, rewrite_agent, cover_letter_agent, review_agent],
        tasks=[jd_task, rewrite_task, cover_letter_task, review_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff(inputs={
        "resume": resume,
        "job_description": job_description,
    })

    return {
        "jd_analysis": jd_task.output.raw if jd_task.output else "",
        "tailored_resume": rewrite_task.output.raw if rewrite_task.output else "",
        "cover_letter": cover_letter_task.output.raw if cover_letter_task.output else "",
        "review": review_task.output.raw if review_task.output else "",
        "raw": result.raw,
    }
