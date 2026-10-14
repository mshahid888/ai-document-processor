"""
Extraction pipeline interfaces.

Design contract (portfolio-grade, honest AI):
- An Extractor NEVER invents values. A field it cannot find is returned as
  value=None with confidence 0.0 and a human-readable warning.
- Every extracted field carries: value, confidence (0..1), source (which
  rule found it), and an optional warning.
- Swapping in a real document-AI model later means implementing the
  `Extractor` interface below and registering it in `pipeline.py`.
  No other code changes.

See README.md ("Swap path for a real document-AI model").
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FieldResult:
    """A single extracted field.

    value:      the extracted value, or None when not found (never guessed).
    confidence: 0.0 - 1.0, how sure the extractor is. 0.0 when value is None.
    source:     short tag naming the rule, e.g. "regex:invoice_number".
    warning:    human-readable note when something is off / missing.
    """

    value: Any = None
    confidence: float = 0.0
    source: str = "none"
    warning: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "confidence": round(self.confidence, 2),
            "source": self.source,
            "warning": self.warning,
        }


@dataclass
class LineItem:
    description: str
    quantity: float
    unit_price: float
    line_total: float
    confidence: float = 0.85
    source: str = "layout:line_items_table"

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "line_total": self.line_total,
            "confidence": round(self.confidence, 2),
            "source": self.source,
        }


@dataclass
class ExtractionResult:
    """Full result of running an Extractor over one document."""

    extractor_name: str
    fields: dict[str, FieldResult] = field(default_factory=dict)
    line_items: list[LineItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_text_preview: str = ""

    def field(self, name: str) -> FieldResult:
        return self.fields.get(name, FieldResult())

    def to_dict(self) -> dict:
        return {
            "extractor": self.extractor_name,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "line_items": [li.to_dict() for li in self.line_items],
            "warnings": self.warnings,
            "raw_text_preview": self.raw_text_preview,
        }


class Extractor(ABC):
    """Interface every document extractor must implement."""

    name: str = "base"

    @abstractmethod
    def extract(self, text: str, *, filename: str = "") -> ExtractionResult:
        """Extract structured data from plain document text.

        Must never invent values: unknown fields -> FieldResult(value=None).
        """
        raise NotImplementedError
