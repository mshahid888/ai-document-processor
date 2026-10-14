"""
Extraction pipeline: orchestrates text extraction -> Extractor -> validation.

Swap path for a real document-AI model (documented, one place):
    1. Implement the `Extractor` interface from
       `app.extraction.base` (see base.py docstring for the contract).
    2. Register it in EXTRACTORS below, e.g.:
           EXTRACTORS["layoutlm"] = LayoutLMExtractor(model_path="...")
    3. Select it per request via POST /api/documents/{id}/extract
       {"extractor": "layoutlm"} or set DEFAULT_EXTRACTOR.
Everything downstream (validation, export, UI) is extractor-agnostic.
"""

from __future__ import annotations

import io

import pdfplumber

from .extraction.base import ExtractionResult, Extractor
from .extraction.invoice_extractor import InvoiceExtractor
from .validation import ValidationIssue, validate

EXTRACTORS: dict[str, Extractor] = {
    "invoice": InvoiceExtractor(),
}

DEFAULT_EXTRACTOR = "invoice"


def extract_text(file_bytes: bytes, filename: str) -> tuple[str, list[str]]:
    """Return (full_text, warnings). Text-based PDFs only in the local demo.

    Image-only uploads are stored but cannot be text-extracted without an
    OCR engine; instead of failing silently we return an explicit warning.
    """
    warnings: list[str] = []
    if not filename.lower().endswith(".pdf"):
        return "", [
            "OCR is not enabled in the local demo — text extraction needs "
            "a text-based PDF. The file was stored but not extracted."
        ]
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
    except Exception as exc:  # corrupted / encrypted / image-only PDF
        return "", [f"Could not read PDF text ({exc}). "
                    "Image-only PDFs need OCR, which is not enabled locally."]
    text = "\n".join(pages)
    if not text.strip():
        warnings.append(
            "No text layer found in this PDF (probably a scan). "
            "OCR is not enabled in the local demo."
        )
    return text, warnings


def run_pipeline(file_bytes: bytes, filename: str,
                 extractor_name: str = DEFAULT_EXTRACTOR
                 ) -> tuple[ExtractionResult, list[ValidationIssue], list[str]]:
    """Run the full pipeline. Returns (extraction, validation_issues, warnings)."""
    extractor = EXTRACTORS.get(extractor_name)
    if extractor is None:
        raise ValueError(f"Unknown extractor '{extractor_name}'. "
                         f"Available: {sorted(EXTRACTORS)}")

    text, warnings = extract_text(file_bytes, filename)
    if text.strip():
        result = extractor.extract(text, filename=filename)
    else:
        # Honest empty result: every field None, never invented.
        result = ExtractionResult(extractor_name=extractor.name)
        result.warnings.append("No text extracted — all fields are null (not guessed).")

    issues = validate(result) if text.strip() else []
    return result, issues, warnings
