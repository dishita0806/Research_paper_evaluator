from fastapi import FastAPI, UploadFile, File
from fastapi.responses import RedirectResponse
import pdfplumber
import io
import os
import requests
import json

app = FastAPI()

# -------------------------------------------------
# Redirect root URL to Swagger UI
# -------------------------------------------------
@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")

# -------------------------------------------------
# Section splitter
# -------------------------------------------------
def split_into_sections(text: str):
    sections = {
        "abstract": "",
        "introduction": "",
        "methodology": "",
        "results": "",
        "conclusion": "",
        "references": ""
    }

    text_lower = text.lower()

    headings = {
        "abstract": ["abstract", "summary"],
        "introduction": ["introduction", "background", "motivation"],
        "methodology": [
            "methodology", "methods", "materials and methods",
            "proposed method", "approach", "model", "algorithm",
            "framework", "implementation", "experimental setup"
        ],
        "results": [
            "results", "experiments", "evaluation",
            "performance evaluation", "analysis",
            "results and discussion"
        ],
        "conclusion": [
            "conclusion", "conclusions",
            "concluding remarks", "final remarks"
        ],
        "references": ["references", "bibliography", "works cited"]
    }

    positions = {}

    for section, keys in headings.items():
        for key in keys:
            idx = text_lower.find("\n" + key)
            if idx != -1:
                positions[section] = idx
                break

    sorted_sections = sorted(positions.items(), key=lambda x: x[1])

    for i, (section, start) in enumerate(sorted_sections):
        end = (
            sorted_sections[i + 1][1]
            if i + 1 < len(sorted_sections)
            else len(text)
        )
        sections[section] = text[start:end].strip()

    return sections

# -------------------------------------------------
# LLM call helper
# -------------------------------------------------
def call_groq(system_prompt: str, user_prompt: str):
    api_key = os.getenv("GROQ_API_KEY")

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }
    )

    return response.json()["choices"][0]["message"]["content"]

# -------------------------------------------------
# Observation generation
# -------------------------------------------------
def get_section_observations(section_name: str, section_text: str):
    system_prompt = """
You are an expert academic peer reviewer with experience reviewing papers for
IEEE, ACM, Springer, and Elsevier venues.

Your task is to FIRST understand and summarize the content of the provided
paper section, and THEN extract objective reviewer observations.

You must strictly follow the two-phase process below.

================================================
PHASE 1 — SECTION SUMMARY (UNDERSTANDING PHASE)
================================================
Briefly summarize what this section is about.

The summary should:
• Capture the purpose of the section
• Identify what the authors are trying to do or claim
• Be purely descriptive and neutral
• Be at most 3–4 sentences

Do NOT evaluate or judge in the summary.
Do NOT add opinions or criticism.

This phase answers:
“What is the author saying in this section?”

================================================
PHASE 2 — REVIEWER OBSERVATIONS (EVALUATION PHASE)
================================================
After summarizing, extract factual reviewer observations.

Your observations must:
• Be grounded strictly in the provided text
• Identify what is clearly present
• Identify what is missing, unclear, or under-specified
• Identify weaknesses only when supported by text
• Identify strengths only when explicitly justified

You are NOT scoring.
You are NOT giving suggestions.
You are NOT rewriting the paper.

================================================
STRICT RULES
================================================
• Do NOT hallucinate experiments, datasets, metrics, or comparisons
• Do NOT assume standard practices unless stated
• Do NOT invent citations or baselines
• Do NOT provide advice or fixes
• If information is missing, explicitly state that it is missing

================================================
OUTPUT FORMAT (STRICT)
================================================
Return your response in the following format:

SUMMARY:
<3–4 sentence neutral summary>

OBSERVATIONS:
- Bullet point observation 1
- Bullet point observation 2
- Bullet point observation 3
(3–6 observations total)

================================================
STYLE & TONE
================================================
• Professional, neutral, analytical
• Sound like a real academic reviewer
• Avoid emotional or judgmental language
• Avoid speculation

You are acting as a reviewer, not an editor, mentor, or co-author.

"""

    user_prompt = f"""
Section: {section_name}

Text:
{section_text[:3000]}
"""

    return call_groq(system_prompt, user_prompt)

# -------------------------------------------------
# Scoring using observations
# -------------------------------------------------
def score_paper(observations: dict):
    scoring_system_prompt = """
You are an academic peer reviewer assigning scores based strictly on
previously identified reviewer observations.

You must follow the scoring rubric exactly.
You must justify every score using the observations.

--------------------------------
SCORING CRITERIA (0–10)
--------------------------------
Novelty:
- 0–3: No clear novelty
- 4–6: Incremental or weak novelty
- 7–8: Clear and meaningful novelty
- 9–10: Strong, well-justified novelty

Technical Quality:
- Correctness, rigor, and soundness of approach

Methodology:
- Completeness, clarity, and reproducibility

Experimental Validation:
- Quality of experiments, datasets, baselines, metrics

Clarity:
- Organization, readability, and presentation

--------------------------------
RULES
--------------------------------
• Scores must be integers
• Scores must be conservative
• Missing information must reduce scores
• Do NOT infer or assume missing details
• Do NOT change or reinterpret observations

--------------------------------
OUTPUT FORMAT (STRICT JSON)
--------------------------------
{
  "novelty": <int>,
  "technical_quality": <int>,
  "methodology": <int>,
  "experimental_validation": <int>,
  "clarity": <int>,
  "justification": {
    "novelty": "...",
    "technical_quality": "...",
    "methodology": "...",
    "experimental_validation": "...",
    "clarity": "..."
  }
}
"""

    user_prompt = f"""
Reviewer observations:
{json.dumps(observations, indent=2)}
"""

    raw = call_groq(scoring_system_prompt, user_prompt)
    return json.loads(raw)

def generate_suggestions(observations: dict, scores: dict, decision: str, avg_score: float):
    system_prompt = """
You are an academic peer reviewer providing constructive feedback to authors
after completing a formal review and scoring of a research paper.

Your task is to generate clear, actionable suggestions for improving the paper,
based strictly on reviewer observations and assigned scores.

================================================
INPUT CONTEXT
================================================
You are given:
• Section-wise reviewer observations
• Numeric rubric scores with justifications
• Overall average score
• Final reviewer decision

================================================
WHAT YOU SHOULD DO
================================================
• Identify weaknesses implied by low or moderate scores
• Suggest improvements that directly address those weaknesses
• Suggest missing experiments, evaluations, or comparisons if relevant
• Suggest clarity or structural improvements where appropriate
• Align all suggestions with the review outcome

================================================
WHAT YOU MUST NOT DO
================================================
• Do NOT invent new weaknesses not supported by observations
• Do NOT contradict the given scores or decision
• Do NOT restate observations verbatim
• Do NOT rewrite the paper
• Do NOT suggest future research directions unrelated to the review
• Do NOT be vague or generic

================================================
STYLE & TONE
================================================
• Professional and constructive
• Reviewer-to-author tone
• Specific and actionable
• Neutral and respectful

================================================
OUTPUT FORMAT (STRICT)
================================================
Return 4–8 bullet-point suggestions.

Each suggestion must:
• Be directly actionable
• Be 1–2 sentences long
• Clearly correspond to an identified weakness

================================================
FINAL INSTRUCTION
================================================
The goal is to help the authors improve the quality, clarity,
and rigor of the paper without altering its core idea.
"""

    user_prompt = f"""
Final decision: {decision}
Average score: {avg_score}

Scores:
{json.dumps(scores, indent=2)}

Reviewer observations:
{json.dumps(observations, indent=2)}
"""

    return call_groq(system_prompt, user_prompt)


# -------------------------------------------------
# Main endpoint
# -------------------------------------------------
@app.post("/review-paper")
async def review_paper(file: UploadFile = File(...)):
    pdf_bytes = await file.read()

    extracted_text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            extracted_text += page.extract_text() or ""

    sections = split_into_sections(extracted_text)

    observations = {}
    for section, content in sections.items():
        if content.strip():
            observations[section] = get_section_observations(section, content)

    scores = score_paper(observations)

    avg_score = sum([
        scores["novelty"],
        scores["technical_quality"],
        scores["methodology"],
        scores["experimental_validation"],
        scores["clarity"]
    ]) / 5

    if avg_score >= 8:
        decision = "Accept"
    elif avg_score >= 7:
        decision = "Weak Accept"
    elif avg_score >= 6:
        decision = "Weak Reject"
    else:
        decision = "Reject"
    
    suggestions = generate_suggestions(observations, scores, decision, avg_score)

    return {
        "filename": file.filename,
        "scores": scores,
        "average_score": round(avg_score, 2),
        "decision": decision,
        "suggestions": suggestions
    }
