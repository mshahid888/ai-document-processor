"""
Validation layer: cross-checks extracted invoice data for internal
consistency. Never "fixes" values — it only surfaces warnings with
severity levels for the UI and API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .extraction.base import ExtractionResult

TOLERANCE = 0.01  # euro-cent rounding tolerance


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"severity": self.severity, "code": self.code, "message": self.message}


def _num(result: ExtractionResult, name: str) -> float | None:
    v = result.field(name).value
    return float(v) if isinstance(v, (int, float)) else None


def validate(result: ExtractionResult) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # ---- required fields ----------------------------------------------------
    for fname in ("invoice_number", "issue_date", "total"):
        if result.field(fname).value is None:
            issues.append(ValidationIssue(
                "error", f"missing_{fname}",
                f"Required field '{fname}' was not extracted. "
                "The document may be incomplete or use an unsupported layout.",
            ))

    # ---- line items sum vs subtotal ------------------------------------------
    subtotal = _num(result, "subtotal")
    if result.line_items and subtotal is not None:
        items_sum = round(sum(li.line_total for li in result.line_items), 2)
        if abs(items_sum - subtotal) > TOLERANCE:
            issues.append(ValidationIssue(
                "warning", "line_items_subtotal_mismatch",
                f"Line items sum to {items_sum:.2f} but subtotal is {subtotal:.2f} "
                f"(diff {items_sum - subtotal:+.2f}).",
            ))

    # ---- subtotal + VAT == total ----------------------------------------------
    vat = _num(result, "vat_amount")
    total = _num(result, "total")
    if subtotal is not None and vat is not None and total is not None:
        if abs((subtotal + vat) - total) > TOLERANCE:
            issues.append(ValidationIssue(
                "warning", "totals_mismatch",
                f"Subtotal ({subtotal:.2f}) + VAT ({vat:.2f}) = {subtotal + vat:.2f}, "
                f"but stated total is {total:.2f} (diff {(subtotal + vat) - total:+.2f}).",
            ))

    # ---- VAT rate plausibility --------------------------------------------------
    vat_rate = _num(result, "vat_rate")
    if vat_rate is not None and subtotal is not None and vat is not None and subtotal > 0:
        expected = round(subtotal * vat_rate / 100, 2)
        if abs(expected - vat) > TOLERANCE:
            issues.append(ValidationIssue(
                "warning", "vat_rate_mismatch",
                f"VAT rate {vat_rate}% of {subtotal:.2f} = {expected:.2f}, "
                f"but stated VAT is {vat:.2f}.",
            ))

    # ---- date sanity ------------------------------------------------------------
    issue_raw = result.field("issue_date").value
    due_raw = result.field("due_date").value
    today = date.today()
    if issue_raw:
        try:
            issue_d = date.fromisoformat(issue_raw)
            if issue_d > today:
                issues.append(ValidationIssue(
                    "warning", "issue_date_future",
                    f"Issue date {issue_raw} is in the future.",
                ))
            if (today - issue_d).days > 730:
                issues.append(ValidationIssue(
                    "info", "issue_date_old",
                    f"Issue date {issue_raw} is more than 2 years ago.",
                ))
            if due_raw:
                due_d = date.fromisoformat(due_raw)
                if due_d < issue_d:
                    issues.append(ValidationIssue(
                        "warning", "due_before_issue",
                        f"Due date {due_raw} is before issue date {issue_raw}.",
                    ))
        except ValueError:
            issues.append(ValidationIssue(
                "error", "issue_date_unparseable",
                f"Issue date '{issue_raw}' could not be parsed as a date.",
            ))

    # ---- line-item row math -------------------------------------------------------
    for i, li in enumerate(result.line_items, start=1):
        expected = round(li.quantity * li.unit_price, 2)
        if abs(expected - li.line_total) > TOLERANCE:
            issues.append(ValidationIssue(
                "warning", "line_item_math",
                f"Row {i} ('{li.description}'): {li.quantity} x {li.unit_price:.2f} "
                f"= {expected:.2f}, but row total is {li.line_total:.2f}.",
            ))

    return issues
