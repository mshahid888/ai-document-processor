"""
In-memory document store for the local demo.

Keeps uploaded file bytes + pipeline results in memory. Uploads are also
mirrored to backend/data/uploads/ so you can inspect them on disk.
Nothing leaves the machine; no database, no cloud.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from .extraction.base import ExtractionResult
from .validation import ValidationIssue

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")


@dataclass
class Document:
    id: str
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: str
    file_bytes: bytes = field(repr=False)
    extraction: ExtractionResult | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    pipeline_warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "uploaded_at": self.uploaded_at,
            "extracted": self.extraction is not None,
            "issue_count": len(self.issues),
        }

    def detail(self) -> dict:
        return {
            **self.summary(),
            "extraction": self.extraction.to_dict() if self.extraction else None,
            "validation": [i.to_dict() for i in self.issues],
            "pipeline_warnings": self.pipeline_warnings,
        }


class DocumentStore:
    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    def add(self, filename: str, content_type: str, file_bytes: bytes) -> Document:
        doc_id = uuid.uuid4().hex[:12]
        safe_name = f"{doc_id}_{os.path.basename(filename)}"
        with open(os.path.join(UPLOAD_DIR, safe_name), "wb") as f:
            f.write(file_bytes)
        doc = Document(
            id=doc_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(file_bytes),
            uploaded_at=datetime.now().isoformat(timespec="seconds"),
            file_bytes=file_bytes,
        )
        self._docs[doc_id] = doc
        return doc

    def get(self, doc_id: str) -> Document | None:
        return self._docs.get(doc_id)

    def all(self) -> list[Document]:
        return sorted(self._docs.values(),
                      key=lambda d: d.uploaded_at, reverse=True)

    def to_export_dicts(self, docs: list[Document]) -> list[dict]:
        return [{
            "filename": d.filename,
            "uploaded_at": d.uploaded_at,
            "extraction": d.extraction,
            "issues": d.issues,
        } for d in docs]


store = DocumentStore()
