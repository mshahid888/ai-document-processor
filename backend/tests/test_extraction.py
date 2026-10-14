"""Field-level extraction accuracy on the fake sample invoices.

The extractor must find what's there and return None (never a guess)
for what's missing.
"""

import os

import pytest

from app.pipeline import run_pipeline

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def load(name: str) -> bytes:
    with open(os.path.join(SAMPLES, name), "rb") as f:
        return f.read()


def fields_of(name: str):
    result, issues, warnings = run_pipeline(load(name), name)
    return {k: v for k, v in result.fields.items()}, result, issues


class TestSample1GermanClean:
    def test_core_fields(self):
        fields, _, _ = fields_of("sample-1-rechnung-korrekt.pdf")
        assert fields["invoice_number"].value == "RE-2026-001"
        assert fields["issue_date"].value == "2026-10-14"
        assert fields["due_date"].value == "2026-10-28"
        assert fields["subtotal"].value == pytest.approx(2050.0)
        assert fields["vat_amount"].value == pytest.approx(389.5)
        assert fields["total"].value == pytest.approx(2439.5)
        assert fields["vat_rate"].value == pytest.approx(19.0)
        assert fields["currency"].value == "EUR"
        assert fields["seller_name"].value == "Musterfirma GmbH"

    def test_confidences_high(self):
        fields, _, _ = fields_of("sample-1-rechnung-korrekt.pdf")
        for name in ("invoice_number", "issue_date", "total"):
            assert fields[name].confidence >= 0.9, name

    def test_line_items(self):
        _, result, _ = fields_of("sample-1-rechnung-korrekt.pdf")
        assert len(result.line_items) == 2
        first = result.line_items[0]
        assert first.quantity == pytest.approx(10.0)
        assert first.unit_price == pytest.approx(120.0)
        assert first.line_total == pytest.approx(1200.0)

    def test_no_validation_issues(self):
        _, _, issues = fields_of("sample-1-rechnung-korrekt.pdf")
        assert issues == []


class TestSample2English:
    def test_core_fields(self):
        fields, _, _ = fields_of("sample-2-invoice-english.pdf")
        assert fields["invoice_number"].value == "INV-2026-0142"
        assert fields["issue_date"].value == "2026-09-03"
        assert fields["due_date"].value == "2026-09-17"
        assert fields["subtotal"].value == pytest.approx(879.0)
        assert fields["vat_amount"].value == pytest.approx(175.8)
        assert fields["total"].value == pytest.approx(1054.8)
        assert fields["vat_rate"].value == pytest.approx(20.0)

    def test_total_not_confused_with_subtotal(self):
        # regression: "Total" must not match inside "Subtotal"
        fields, _, _ = fields_of("sample-2-invoice-english.pdf")
        assert fields["total"].value != fields["subtotal"].value

    def test_no_validation_issues(self):
        _, _, issues = fields_of("sample-2-invoice-english.pdf")
        assert issues == []


class TestSample3DeliberateErrors:
    def test_missing_due_date_is_null_not_guessed(self):
        fields, result, _ = fields_of("sample-3-rechnung-fehlerhaft.pdf")
        due = fields["due_date"]
        assert due.value is None
        assert due.confidence == 0.0
        assert due.warning is not None and "not found" in due.warning
        assert any("due_date" in w for w in result.warnings)

    def test_totals_mismatch_detected(self):
        _, _, issues = fields_of("sample-3-rechnung-fehlerhaft.pdf")
        codes = [i.code for i in issues]
        assert "line_items_subtotal_mismatch" in codes

    def test_still_extracts_what_is_there(self):
        fields, _, _ = fields_of("sample-3-rechnung-fehlerhaft.pdf")
        assert fields["invoice_number"].value == "RE-2026-002"
        assert fields["total"].value == pytest.approx(3451.0)


class TestNeverInvents:
    def test_garbage_text_yields_nulls(self):
        # run through the extractor directly with nonsense text
        from app.extraction.invoice_extractor import InvoiceExtractor
        result = InvoiceExtractor().extract(
            "hello world\nthis is not an invoice\nlorem ipsum 123", filename="x.pdf")
        for name in ("invoice_number", "issue_date", "total"):
            assert result.field(name).value is None
            assert result.field(name).confidence == 0.0

    def test_empty_pdf_text(self):
        result, issues, warnings = run_pipeline(b"not a pdf at all", "broken.pdf")
        assert result is not None
        # no crash, honest empty result
        assert all(f.value is None for f in result.fields.values())
