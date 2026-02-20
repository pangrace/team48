from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    def load_dotenv() -> None:
        return None
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agent.feedback_agent import (
    AgentConfigError,
    AgentRuntimeError,
    generate_initial_feedback,
    generate_next_problem,
    generate_practice_feedback,
)
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


def _pick_feedback_payload(raw: dict[str, Any]) -> dict[str, Any]:
    # Preferred schema
    for key in ("comparison_feedback", "comparisonFeedback", "feedback"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value

    # Alternate schema: feedback fields returned at top-level.
    if any(field in raw for field in ("problemTitle", "problemPrompt", "personalizedSummary", "steps")):
        return raw

    # Recursive search for any nested dict with feedback-like fields.
    for value in raw.values():
        if isinstance(value, dict):
            nested = _pick_feedback_payload(value)
            if nested:
                return nested
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested = _pick_feedback_payload(item)
                    if nested:
                        return nested

    return {}


def _pick_next_problem_payload(raw: dict[str, Any]) -> dict[str, Any]:
    # Preferred schema
    for key in ("next_problem", "nextProblem"):
        value = raw.get(key)
        if isinstance(value, dict):
            return value

    # Alternate schema: generated question fields at top-level.
    if any(field in raw for field in ("question", "solution", "common_pitfall", "commonPitfall")):
        return {
            "question": raw.get("question", ""),
            "solution": raw.get("solution", ""),
            "common_pitfall": raw.get("common_pitfall", raw.get("commonPitfall", "")),
        }

    # Alternate schema: a single question string.
    question_value = raw.get("next_question") or raw.get("generated_question")
    if isinstance(question_value, str):
        return {"question": question_value, "solution": "", "common_pitfall": ""}

    # Recursive search for any nested dict with question-like fields.
    for value in raw.values():
        if isinstance(value, dict):
            nested = _pick_next_problem_payload(value)
            if nested:
                return nested
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested = _pick_next_problem_payload(item)
                    if nested:
                        return nested

    return {}


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

    comparison = _pick_feedback_payload(agent_response)

    return {
        "feedback": _normalize_feedback(comparison if isinstance(comparison, dict) else {}),
    }


@app.post("/api/initial-next-problem")
async def initial_next_problem(
    student_pdf: UploadFile = File(...),
    instructor_pdf: UploadFile = File(...),
    comparison_summary: str = Form(""),
) -> dict[str, Any]:
    student_bytes = await _read_pdf(student_pdf)
    instructor_bytes = await _read_pdf(instructor_pdf)

    try:
        student_text = extract_text_from_pdf_bytes(student_bytes)
        instructor_text = extract_text_from_pdf_bytes(instructor_bytes)
    except PdfExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        agent_response = generate_next_problem(
            student_text=student_text,
            instructor_text=instructor_text,
            comparison_summary=comparison_summary,
        )
    except AgentConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    next_problem = _pick_next_problem_payload(agent_response)
    return {
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

    feedback = _pick_feedback_payload(agent_response)
    next_problem = _pick_next_problem_payload(agent_response)
    return {
        "feedback": _normalize_feedback(feedback if isinstance(feedback, dict) else {}),
        "nextProblem": _normalize_next_problem(next_problem if isinstance(next_problem, dict) else {}),
    }
