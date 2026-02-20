from __future__ import annotations

import io

from pypdf import PdfReader


class PdfExtractionError(Exception):
    pass


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise PdfExtractionError("Failed to parse PDF content.") from exc

    text = "\n\n".join(part for part in pages if part).strip()
    if not text:
        raise PdfExtractionError("No readable text found in PDF.")
    return text
