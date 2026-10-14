"""Validation logic: totals math, dates, required fields."""

from app.extraction.base import ExtractionResult, FieldResult, LineItem
from app.validation import validate


def _result(**field_values) -> ExtractionResult:
    r = ExtractionResult(extractor_name="test")
    for name, value in field_values.items():
        r.fields[name] = FieldResult(value=value, confidence=0.9, source="test")
    return r


def _clean():
    return _result(
        invoice_number="RE-1",
        issue_date="2026-10-01",
        due_date="2026-10-15",
        subtotal=100.0,
        vat_rate=19.0,
        vat_amount=19.0,
        total=119.0,
    )


class TestTotals:
    def test_clean_passes(self):
        assert validate(_clean()) == []

    def test_totals_mismatch_caught(self):
        r = _clean()
        r.fields["total"] = FieldResult(value=120.0, confidence=0.9, source="test")
        codes = [i.code for i in validate(r)]
        assert "totals_mismatch" in codes

    def test_vat_rate_mismatch_caught(self):
        r = _clean()
        r.fields["vat_amount"] = FieldResult(value=10.0, confidence=0.9, source="test")
        codes = [i.code for i in validate(r)]
        assert "vat_rate_mismatch" in codes

    def test_line_items_sum_mismatch_caught(self):
        r = _clean()
        r.line_items = [LineItem("a", 2, 30.0, 60.0), LineItem("b", 1, 30.0, 30.0)]
        codes = [i.code for i in validate(r)]
        assert "line_items_subtotal_mismatch" in codes

    def test_line_item_row_math_caught(self):
        r = _clean()
        r.line_items = [LineItem("a", 2, 30.0, 61.0)]  # 2x30 != 61
        codes = [i.code for i in validate(r)]
        assert "line_item_math" in codes

    def test_cent_rounding_tolerated(self):
        r = _clean()
        r.fields["total"] = FieldResult(value=119.004, confidence=0.9, source="test")
        assert "totals_mismatch" not in [i.code for i in validate(r)]


class TestRequiredAndDates:
    def test_missing_required_field_is_error(self):
        r = _clean()
        r.fields["invoice_number"] = FieldResult(value=None, confidence=0.0, source="none")
        issues = validate(r)
        err = [i for i in issues if i.code == "missing_invoice_number"]
        assert err and err[0].severity == "error"

    def test_future_issue_date_warns(self):
        r = _clean()
        r.fields["issue_date"] = FieldResult(value="2999-01-01", confidence=0.9, source="test")
        assert "issue_date_future" in [i.code for i in validate(r)]

    def test_due_before_issue_warns(self):
        r = _clean()
        r.fields["due_date"] = FieldResult(value="2026-09-01", confidence=0.9, source="test")
        assert "due_before_issue" in [i.code for i in validate(r)]
