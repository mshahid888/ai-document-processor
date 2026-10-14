"""
Generates 3 FAKE invoice PDFs for the local demo (reportlab, free).

Everything is fictional: fake companies, fake addresses, fake amounts.
Each PDF carries a visible "DEMO - KEIN ECHTES DOKUMENT" banner.

- sample-1: clean German invoice, consistent totals.
- sample-2: English-label invoice, consistent totals (shows the extractor
             handles both label languages).
- sample-3: German invoice with a DELIBERATE error (line items sum to
             3.000,00 EUR but the printed subtotal is 2.900,00 EUR) and a
             missing due date -> exercises validation warnings + null fields.

Run:  .venv/bin/python backend/generate_samples.py
Output: backend/samples/*.pdf
"""

from __future__ import annotations

import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT_DIR = os.path.join(os.path.dirname(__file__), "samples")

SELLER = [
    "Musterfirma GmbH",
    "Musterstraße 12, 12345 Berlin",
    "Tel: 030-000000  |  info@musterfirma.example",
]


def draw_invoice(path: str, *, title: str, meta: list[tuple[str, str]],
                 buyer: list[str], items: list[tuple[str, str, str, str]],
                 totals: list[tuple[str, str]], footer: str) -> None:
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "DEMO-RECHNUNG - KEIN ECHTES DOKUMENT (alle Angaben frei erfunden)")
    y -= 30
    c.setFont("Helvetica", 10)
    for line in SELLER:
        c.drawString(50, y, line)
        y -= 14
    y -= 10
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, title)
    y -= 26
    c.setFont("Helvetica", 10)
    for label, value in meta:
        c.drawString(50, y, f"{label}: {value}")
        y -= 15
    y -= 8
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, buyer[0])
    c.setFont("Helvetica", 10)
    y -= 15
    for line in buyer[1:]:
        c.drawString(50, y, line)
        y -= 14
    y -= 12
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Pos  Beschreibung                      Menge  Einzelpreis   Gesamt")
    c.setFont("Helvetica", 10)
    y -= 15
    for desc, qty, unit, total in items:
        c.drawString(50, y, f"{items.index((desc, qty, unit, total)) + 1}  {desc}  {qty}  {unit}  {total}")
        y -= 15
    y -= 8
    for label, value in totals:
        c.drawString(50, y, f"{label}: {value}")
        y -= 15
    y -= 14
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, y, footer)
    c.showPage()
    c.save()
    print("wrote", path)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---- sample 1: clean German invoice -------------------------------------
    draw_invoice(
        os.path.join(OUT_DIR, "sample-1-rechnung-korrekt.pdf"),
        title="RECHNUNG",
        meta=[
            ("Rechnungsnummer", "RE-2026-001"),
            ("Rechnungsdatum", "14.10.2026"),
            ("Fälligkeitsdatum", "28.10.2026"),
        ],
        buyer=["Rechnungsempfänger:", "Demokunde AG", "Beispielweg 3, 10115 Berlin"],
        items=[
            ("KI-Beratung Tagessatz", "10", "120,00 EUR", "1.200,00 EUR"),
            ("Chatbot-Integration", "1", "850,00 EUR", "850,00 EUR"),
        ],
        totals=[
            ("Nettobetrag", "2.050,00 EUR"),
            ("MwSt. (19 %)", "389,50 EUR"),
            ("Rechnungsbetrag", "2.439,50 EUR"),
        ],
        footer="Alle Firmen-, Personen- und Betragsangaben sind frei erfunden (Demo).",
    )

    # ---- sample 2: English labels --------------------------------------------
    draw_invoice(
        os.path.join(OUT_DIR, "sample-2-invoice-english.pdf"),
        title="INVOICE",
        meta=[
            ("Invoice No", "INV-2026-0142"),
            ("Invoice date", "03/09/2026"),
            ("Due date", "17/09/2026"),
        ],
        buyer=["Bill to:", "Demo Customer Ltd", "42 Example Road, London EC1A 1AA"],
        items=[
            ("Automation workflow setup", "1", "499.00 EUR", "499.00 EUR"),
            ("Monthly support hours", "4", "95.00 EUR", "380.00 EUR"),
        ],
        totals=[
            ("Subtotal", "879.00 EUR"),
            ("VAT (20 %)", "175.80 EUR"),
            ("Total", "1,054.80 EUR"),
        ],
        footer="All companies, persons and amounts are fictional (demo data).",
    )

    # ---- sample 3: deliberate totals error + missing due date ------------------
    draw_invoice(
        os.path.join(OUT_DIR, "sample-3-rechnung-fehlerhaft.pdf"),
        title="RECHNUNG",
        meta=[
            ("Rechnungsnummer", "RE-2026-002"),
            ("Rechnungsdatum", "14.10.2026"),
            # NOTE: no due date on purpose -> extractor must return null + warning
        ],
        buyer=["Rechnungsempfänger:", "Testkunde UG", "Demostraße 7, 20095 Hamburg"],
        items=[
            ("Webseiten-Relaunch", "1", "2.400,00 EUR", "2.400,00 EUR"),
            ("SEO-Basispaket", "1", "600,00 EUR", "600,00 EUR"),
        ],
        totals=[
            # DELIBERATE ERROR: items sum to 3.000,00 but subtotal says 2.900,00
            ("Nettobetrag", "2.900,00 EUR"),
            ("MwSt. (19 %)", "551,00 EUR"),
            ("Rechnungsbetrag", "3.451,00 EUR"),
        ],
        footer="Demo mit bewusstem Rechenfehler + fehlendem Fälligkeitsdatum.",
    )


if __name__ == "__main__":
    main()
