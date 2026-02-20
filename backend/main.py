import io
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from team48.agent.pdf_extract_agent import AgentConfigError, AgentRuntimeError, analyze_math_pdf_text_with_agent

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


def _extract_pdf_text(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages).strip()


def _normalize_feedback(raw: dict[str, Any]) -> dict[str, Any]:
    steps = raw.get("steps", [])
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

    if not normalized_steps:
        normalized_steps = [
            {
                "id": "step-1",
                "studentStep": "Could not confidently parse detailed steps from the PDF text.",
                "status": "incorrect",
                "whatWentWrong": "The extracted text did not clearly preserve each algebra step.",
                "howToFix": "Upload a cleaner PDF with readable steps or higher scan quality.",
            }
        ]

    return {
        "problemTitle": str(raw.get("problemTitle", "Math Homework Feedback")).strip(),
        "problemPrompt": str(raw.get("problemPrompt", "Problem text not clearly detected.")).strip(),
        "personalizedSummary": str(
            raw.get(
                "personalizedSummary",
                "Work reviewed with limited extracted detail. Focus on clear step formatting.",
            )
        ).strip(),
        "score": int(raw.get("score", 0)),
        "totalPoints": int(raw.get("totalPoints", 10)),
        "steps": normalized_steps,
    }


def _analyze_pdf_text(pdf_text: str, filename: str) -> dict[str, Any]:
    try:
        raw_feedback = analyze_math_pdf_text_with_agent(pdf_text=pdf_text, filename=filename)
    except AgentConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent request failed: {exc}") from exc

    return _normalize_feedback(raw_feedback)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze-pdf")
async def analyze_pdf(pdf: UploadFile = File(...)) -> dict[str, Any]:
    filename = (pdf.filename or "").strip()
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads are accepted.")

    file_bytes = await pdf.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="PDF exceeds 10MB max size.")

    try:
        pdf_text = _extract_pdf_text(file_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Failed to parse PDF. Ensure file is a valid PDF.") from exc

    if not pdf_text:
        raise HTTPException(status_code=400, detail="No readable text found in PDF.")

    feedback = _analyze_pdf_text(pdf_text=pdf_text, filename=filename)
    return {"feedback": feedback}
