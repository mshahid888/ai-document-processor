"""
Deterministic rule/template-based invoice extractor.

Approach: regexes over labeled lines + layout heuristics for the line-item
table. Handles German and English invoice labels. Reports per-field
confidence and NEVER invents values — missing fields come back as
value=None with a warning.

Confidence policy (documented, fixed):
- 0.95  labeled line matched by an exact label regex (invoice no, dates)
- 0.90  labeled amount line (subtotal / VAT / total)
- 0.85  parsed line-item table row
- 0.75  VAT rate parsed next to a VAT label
- 0.60  company name guessed from legal-form suffix (GmbH, AG, UG, Ltd, ...)
- 0.00  field not found -> value None + warning (never guessed)
"""

from __future__ import annotations

import re
from datetime import datetime

from .base import ExtractionResult, Extractor, FieldResult, LineItem


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

# Thousands-aware: tries "1,054.80" / "1.200,00" before plain "120,00".
# Trailing lookahead keeps "1,05" from matching inside "1,054.80".
AMOUNT_RE = (
    r"(\d{1,3}(?:[.,]\d{3})+[.,]\d{2}(?![\d.,])"
    r"|\d+[.,]\d{2}(?![\d.,])"
    r"|\d+(?![\d.,]))"
)


def parse_amount(raw: str) -> float | None:
    """Parse German ('1.234,56') and English ('1,234.56') amounts."""
    s = raw.strip().replace("\u00a0", " ").replace(" ", "")
    s = re.sub(r"[€$£]", "", s)
    try:
        if "," in s and "." in s:
            # the LAST separator is the decimal one
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")  # 1.234,56 -> 1234.56
            else:
                s = s.replace(",", "")  # 1,234.56 -> 1234.56
        elif "," in s:
            s = s.replace(",", ".")  # 234,56 -> 234.56
        return float(s)
    except ValueError:
        return None


def parse_date(raw: str):
    """Parse DD.MM.YYYY / DD/MM/YYYY / YYYY-MM-DD. Returns ISO string or None."""
    raw = raw.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


DATE_RE = r"(\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}-\d{2}-\d{2})"

LABEL_PATTERNS: dict[str, list[str]] = {
    "invoice_number": [
        r"(?:Rechnungsnummer|Rechnungs-Nr\.?|Rg\.?-Nr\.?|Invoice\s*(?:No|Number|#))\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-\/]{2,30})",
    ],
    "issue_date": [
        r"(?:Rechnungsdatum|Ausstellungsdatum|Invoice\s*date|Date)\s*:?\s*" + DATE_RE,
    ],
    "due_date": [
        r"(?:F[äa]lligkeitsdatum|Zahlbar\s*bis|F[äa]llig\s*am|Due\s*date)\s*:?\s*" + DATE_RE,
    ],
    "subtotal": [
        r"(?:Nettobetrag|Zwischensumme|Nettosumme|Subtotal|Net\s*total)\s*:?\s*" + AMOUNT_RE,
    ],
    "vat_amount": [
        # optional "(19 %)" rate in parentheses must be skipped, not read as the amount
        r"\b(?:MwSt|Mehrwertsteuer|USt|Umsatzsteuer|VAT(?:\s*amount)?)\.?\s*"
        r"(?:\(\s*\d{1,2}(?:[.,]\d+)?\s*%\s*\))?\s*:?\s*" + AMOUNT_RE,
    ],
    "total": [
        # \b guards: "Total" must not match inside "Subtotal"
        r"\b(?:Rechnungsbetrag|Gesamtbetrag|Bruttobetrag|Endbetrag|Total(?:\s*due)?|Grand\s*total|Amount\s*due)\b\s*:?\s*" + AMOUNT_RE,
    ],
    "vat_rate": [
        r"(?:MwSt\.?|Mehrwertsteuer|USt\.?|VAT)\D{0,20}(\d{1,2}(?:[.,]\d+)?)\s*%",
    ],
    "currency": [
        r"([€$£]|EUR|USD|GBP)",
    ],
}

REQUIRED_FIELDS = ["invoice_number", "issue_date", "total"]

TABLE_HEADER_RE = re.compile(
    r"(Pos|Nr\.?|#)\s+.*(Beschreibung|Description|Artikel|Item).*"
    r"(Menge|Qty|Quantity|Anzahl).*"
    r"(Einzelpreis|Unit\s*price|Preis).*"
    r"(Gesamt|Amount|Summe|Betrag)",
    re.IGNORECASE,
)

CUR_WORD = r"(?:[€$£]|EUR|USD|GBP)?"

LINE_ROW_RE = re.compile(
    r"^\s*(\d{1,3})\s+(.+?)\s+(\d+(?:[.,]\d+)?)\s+"
    + AMOUNT_RE
    + r"\s*" + CUR_WORD + r"\s+"
    + AMOUNT_RE
    + r"\s*" + CUR_WORD + r"\s*$"
)

COMPANY_SUFFIX_RE = re.compile(
    r"\b(GmbH|AG|UG|GbR|e\.K\.|Ltd\.?|Inc\.?|LLC|S\.?A\.?R\.?L\.?)\b"
)

BUYER_LABEL_RE = re.compile(
    r"(Rechnungsempf[äa]nger|Rechnungsadresse|Bill\s*to|Billed\s*to|Kunde)\s*:?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# extractor
# ---------------------------------------------------------------------------

class InvoiceExtractor(Extractor):
    name = "invoice-rule-extractor-v1"

    def extract(self, text: str, *, filename: str = "") -> ExtractionResult:
        result = ExtractionResult(extractor_name=self.name)
        lines = [ln.strip() for ln in text.splitlines()]
        non_empty = [ln for ln in lines if ln]

        result.raw_text_preview = "\n".join(non_empty[:8])

        # ---- labeled fields -------------------------------------------------
        confidences = {
            "invoice_number": 0.95,
            "issue_date": 0.95,
            "due_date": 0.95,
            "subtotal": 0.90,
            "vat_amount": 0.90,
            "total": 0.90,
            "vat_rate": 0.75,
        }
        for fname, patterns in LABEL_PATTERNS.items():
            found: FieldResult | None = None
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE)
                if not m:
                    continue
                raw = m.group(1)
                if fname in ("issue_date", "due_date"):
                    value = parse_date(raw)
                    if value is None:
                        continue
                elif fname in ("subtotal", "vat_amount", "total"):
                    value = parse_amount(raw)
                    if value is None:
                        continue
                elif fname == "vat_rate":
                    value = float(raw.replace(",", "."))
                elif fname == "currency":
                    value = {"€": "EUR", "$": "USD", "£": "GBP"}.get(raw, raw)
                else:
                    value = raw.strip()
                found = FieldResult(
                    value=value,
                    confidence=confidences.get(fname, 0.9),
                    source=f"regex:{fname}",
                )
                break
            if found is None:
                found = FieldResult(
                    value=None,
                    confidence=0.0,
                    source="none",
                    warning=f"Field '{fname}' not found in document (not guessed).",
                )
                result.warnings.append(found.warning)
            result.fields[fname] = found

        # ---- seller: first line with a legal-form suffix near the top -------
        seller = FieldResult(value=None, confidence=0.0, source="none",
                             warning="Field 'seller_name' not found in document (not guessed).")
        for ln in non_empty[:6]:
            if COMPANY_SUFFIX_RE.search(ln):
                seller = FieldResult(value=ln, confidence=0.60,
                                     source="layout:header_company_suffix")
                break
        if seller.value is None:
            result.warnings.append(seller.warning)
        result.fields["seller_name"] = seller

        # ---- buyer: lines after a buyer label --------------------------------
        buyer = FieldResult(value=None, confidence=0.0, source="none",
                            warning="Field 'buyer_name' not found in document (not guessed).")
        for i, ln in enumerate(non_empty):
            if BUYER_LABEL_RE.search(ln):
                following = [x for x in non_empty[i + 1:i + 4]
                             if not TABLE_HEADER_RE.search(x)]
                if following:
                    buyer = FieldResult(value="; ".join(following[:2]),
                                        confidence=0.60,
                                        source="layout:buyer_block")
                break
        if buyer.value is None:
            result.warnings.append(buyer.warning)
        result.fields["buyer_name"] = buyer

        # ---- line items ------------------------------------------------------
        result.line_items = self._extract_line_items(non_empty, result)

        # ---- required-field check --------------------------------------------
        for fname in REQUIRED_FIELDS:
            if result.fields[fname].value is None:
                result.warnings.append(
                    f"Required field '{fname}' is missing — document may be incomplete."
                )

        return result

    def _extract_line_items(self, lines: list[str], result: ExtractionResult) -> list[LineItem]:
        items: list[LineItem] = []
        header_idx = next(
            (i for i, ln in enumerate(lines) if TABLE_HEADER_RE.search(ln)), None
        )
        if header_idx is None:
            result.warnings.append(
                "No line-item table detected (header row not found)."
            )
            return items
        for ln in lines[header_idx + 1:]:
            # stop at the totals block
            if re.search(
                r"(Nettobetrag|Zwischensumme|Subtotal|MwSt|VAT|Rechnungsbetrag|Gesamtbetrag|Total)",
                ln, re.IGNORECASE,
            ):
                break
            m = LINE_ROW_RE.match(ln)
            if not m:
                continue
            qty = float(m.group(3).replace(",", "."))
            unit = parse_amount(m.group(4))
            total_ = parse_amount(m.group(5))
            if unit is None or total_ is None:
                continue
            items.append(LineItem(
                description=m.group(2).strip(),
                quantity=qty,
                unit_price=unit,
                line_total=total_,
            ))
        if not items:
            result.warnings.append("Line-item table header found but no rows parsed.")
        return items
