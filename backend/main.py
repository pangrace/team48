from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agent.feedback_agent import AgentConfigError, AgentRuntimeError, generate_initial_feedback, generate_practice_feedback
from agent.pdf_extract_agent import PdfExtractionError, extract_text_from_pdf_bytes

load_dotenv()

MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024

app = FastAPI(title="Team48 PDF Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_pdf_filename(filename: str) -> None:
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are accepted.")


async def _read_pdf(upload: UploadFile) -> bytes:
    filename = (upload.filename or "").strip()
    _validate_pdf_filename(filename)
    file_bytes = await upload.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail=f"Uploaded file '{filename}' is empty.")
    if len(file_bytes) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"Uploaded file '{filename}' exceeds 10MB max size.")
    return file_bytes


def _normalize_feedback(raw: dict[str, Any]) -> dict[str, Any]:
    steps = raw.get("steps", [])
    score = int(raw.get("score", 0))
    total_points = int(raw.get("totalPoints", 10))
    normalized_steps = []
    for idx, step in enumerate(steps):
        status = str(step.get("status", "incorrect")).lower()
        normalized_steps.append(
            {
                "id": f"step-{idx + 1}",
                "studentStep": str(step.get("studentStep", "")).strip(),
                "status": "correct" if status == "correct" else "incorrect",
                "whatWentWrong": str(step.get("whatWentWrong", "")).strip(),
                "howToFix": str(step.get("howToFix", "")).strip(),
            }
        )

    summary = str(raw.get("personalizedSummary", "Feedback generated from uploaded work.")).strip()
    if not normalized_steps:
        inferred_status = "correct" if total_points > 0 and score / total_points >= 0.7 else "incorrect"
        normalized_steps = [
            {
                "id": "step-1",
                "studentStep": "Overall solution comparison",
                "status": inferred_status,
                "whatWentWrong": summary or "The submission differs from the reference approach or result.",
                "howToFix": "Show key algebra transitions or explain your reasoning to improve targeted feedback.",
            }
        ]

    return {
        "problemTitle": str(raw.get("problemTitle", "Math Homework Feedback")).strip(),
        "problemPrompt": str(raw.get("problemPrompt", "Problem text not clearly detected.")).strip(),
        "personalizedSummary": summary,
        "score": score,
        "totalPoints": total_points,
        "steps": normalized_steps,
    }


def _normalize_next_problem(raw: dict[str, Any]) -> dict[str, str]:
    return {
        "question": str(raw.get("question", "")).strip(),
        "solution": str(raw.get("solution", "")).strip(),
        "common_pitfall": str(raw.get("common_pitfall", "")).strip(),
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/initial-feedback")
async def initial_feedback(
    student_pdf: UploadFile = File(...),
    instructor_pdf: UploadFile = File(...),
) -> dict[str, Any]:
    student_bytes = await _read_pdf(student_pdf)
    instructor_bytes = await _read_pdf(instructor_pdf)

    try:
        student_text = extract_text_from_pdf_bytes(student_bytes)
        instructor_text = extract_text_from_pdf_bytes(instructor_bytes)
    except PdfExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        agent_response = generate_initial_feedback(
            student_text=student_text,
            instructor_text=instructor_text,
        )
    except AgentConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    comparison = agent_response.get("comparison_feedback", {})
    next_problem = agent_response.get("next_problem", {})

    return {
        "feedback": _normalize_feedback(comparison if isinstance(comparison, dict) else {}),
        "nextProblem": _normalize_next_problem(next_problem if isinstance(next_problem, dict) else {}),
    }


@app.post("/api/practice-feedback")
async def practice_feedback(
    student_pdf: UploadFile = File(...),
    question: str = Form(...),
    solution: str = Form(...),
    common_pitfall: str = Form(""),
) -> dict[str, Any]:
    student_bytes = await _read_pdf(student_pdf)
    try:
        student_text = extract_text_from_pdf_bytes(student_bytes)
    except PdfExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        agent_response = generate_practice_feedback(
            student_attempt_text=student_text,
            question=question,
            solution=solution,
            common_pitfall=common_pitfall,
        )
    except AgentConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    feedback = agent_response.get("feedback", {})
    next_problem = agent_response.get("next_problem", {})
    return {
        "feedback": _normalize_feedback(feedback if isinstance(feedback, dict) else {}),
        "nextProblem": _normalize_next_problem(next_problem if isinstance(next_problem, dict) else {}),
    }
