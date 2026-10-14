"""
Spreadsheet export: real .xlsx workbooks via openpyxl (free, local).

One workbook per document with three sheets:
  - "Document"  : one row per extracted field (name, value, confidence, source)
  - "Line Items": the parsed line-item table
  - "Validation": validation issues (severity, code, message)

`export_all` adds a "Summary" sheet with one row per document.
"""

from __future__ import annotations

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font

from .extraction.base import ExtractionResult
from .validation import ValidationIssue

HEADER_FONT = Font(bold=True)


def _add_sheet(wb: Workbook, title: str, headers: list[str], rows: list[list]) -> None:
    ws = wb.create_sheet(title=title)
    ws.append(headers)
    for cell in ws[1]:
        cell.font = HEADER_FONT
    for row in rows:
        ws.append(["" if v is None else v for v in row])
    # readable column widths
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(width + 2, 48)


def build_workbook(documents: list[dict]) -> bytes:
    """documents: list of {"filename","uploaded_at","extraction": ExtractionResult|None,
    "issues": [ValidationIssue]}. Returns xlsx bytes."""
    wb = Workbook()
    wb.remove(wb.active)  # drop the default empty sheet

    # ---- summary ----
    summary_rows = []
    for d in documents:
        ext: ExtractionResult | None = d.get("extraction")
        fields = ext.fields if ext else {}
        summary_rows.append([
            d["filename"],
            d.get("uploaded_at", ""),
            (fields.get("invoice_number").value if "invoice_number" in fields else None),
            (fields.get("issue_date").value if "issue_date" in fields else None),
            (fields.get("seller_name").value if "seller_name" in fields else None),
            (fields.get("total").value if "total" in fields else None),
            (fields.get("currency").value if "currency" in fields else None),
            len(d.get("issues", [])),
        ])
    _add_sheet(wb, "Summary",
               ["File", "Uploaded", "Invoice No", "Issue Date", "Seller", "Total", "Currency", "Issues"],
               summary_rows)

    # ---- per-document detail ----
    for d in documents:
        ext: ExtractionResult | None = d.get("extraction")
        issues: list[ValidationIssue] = d.get("issues", [])
        if ext is None:
            continue
        # Excel sheet titles are limited to 31 chars
        tag = d["filename"].rsplit(".", 1)[0][:20]
        field_rows = [[name, f.value, f.confidence, f.source, f.warning or ""]
                      for name, f in ext.fields.items()]
        _add_sheet(wb, f"{tag} - fields",
                   ["Field", "Value", "Confidence", "Source", "Warning"], field_rows)
        item_rows = [[li.description, li.quantity, li.unit_price, li.line_total, li.confidence]
                     for li in ext.line_items]
        _add_sheet(wb, f"{tag} - items",
                   ["Description", "Qty", "Unit Price", "Line Total", "Confidence"], item_rows)
        issue_rows = [[i.severity, i.code, i.message] for i in issues]
        _add_sheet(wb, f"{tag} - validation",
                   ["Severity", "Code", "Message"], issue_rows)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_generated_note() -> str:
    return (f"Exported by ai-document-processor demo on "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')} — demo data, not real invoices.")
