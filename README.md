# AI Document Processor

**Upload an invoice PDF → deterministic extraction → validation → spreadsheet export.**
Full-stack portfolio project: **Next.js** frontend + **FastAPI** backend, 100% local,
zero API keys, zero cloud, zero cost.

> **Demo only.** Auth is demo-grade (`demo` / `demo1234`), every invoice is
> fictional, and nothing leaves your machine. See `backend/app/auth.py`.

---

## What it does

1. **Upload** a PDF invoice (drag & drop).
2. **Extract** structured fields — invoice number, dates, seller/buyer, line
   items, subtotal, VAT, total — each with a **per-field confidence score**.
   Missing fields come back as `null` with a warning. **The extractor never
   invents values.**
3. **Validate** — line items vs subtotal, subtotal + VAT vs total, VAT-rate
   plausibility, date sanity, required fields. Problems surface as
   severity-tagged warnings in the UI and API.
4. **Export** a real `.xlsx` workbook (Summary + per-document field/item/
   validation sheets).

## Architecture

```
┌─────────────────────────────┐
│  Next.js frontend (:3000)   │
│  /login  /  /documents/[id] │
│  upload · results · export  │
└──────────────┬──────────────┘
               │  /api/* (same-origin rewrite)
┌──────────────▼──────────────┐
│  FastAPI backend (:8000)    │
│  auth (demo JWT) · upload   │
│  extract · export.xlsx      │
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│  Extraction pipeline        │
│  pdfplumber text            │
│   → Extractor interface     │
│   → InvoiceExtractor        │──▶ swap path: implement Extractor,
│        (regex + layout       │    register in pipeline.py (1 place)
│         heuristics, DE+EN)   │
│   → validation layer        │
│   → openpyxl xlsx export    │
└─────────────────────────────┘
```

**Swap path for a real document-AI model:** implement the `Extractor`
interface (`backend/app/extraction/base.py` — contract documented there),
register it in `EXTRACTORS` in `backend/app/pipeline.py`, select it via
`POST /api/documents/{id}/extract {"extractor": "<name>"}`. Validation,
export and UI are extractor-agnostic.

## Setup

```bash
cd ai-document-processor

# backend
cd backend
python3 -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt
../.venv/bin/python generate_samples.py   # 3 fake invoices → backend/samples/
../.venv/bin/python -m pytest tests/ -q   # 29 tests

# frontend (separate terminal)
cd ../frontend
npm install
```

## 3-step demo

Terminal 1 — backend:
```bash
cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000
```

Terminal 2 — frontend:
```bash
cd frontend && npm run dev
```

Browser → **http://localhost:3000**

1. **Sign in** with `demo` / `demo1234`.
2. **Upload** `backend/samples/sample-1-rechnung-korrekt.pdf` → click
   **Extract** → open it: fields with confidence bars, line items,
   "all checks passed".
3. **Upload** `backend/samples/sample-3-rechnung-fehlerhaft.pdf` → Extract →
   see the `line_items_subtotal_mismatch` warning and the `null` due date
   (not guessed) → **⬇ Download .xlsx** and open it.

## Recording guide (portfolio video)

On http://localhost:3000, record in one continuous take:

1. **Upload** — drag `sample-1-rechnung-korrekt.pdf` into the dropzone.
   Narrate: "Invoice PDF in, no API keys, everything local."
2. **Extraction** — click Extract, open the document. Point at the
   per-field confidence bars: "every field carries a confidence score —
   and look, nothing is invented."
3. **Validation warning** — upload `sample-3-rechnung-fehlerhaft.pdf`
   (the one with the deliberate totals error). Extract → the warning
   appears: "line items sum to 3.000,00 but the subtotal says 2.900,00 —
   and the missing due date is null, not guessed."
4. **Export** — click "⬇ Download .xlsx", open the workbook on screen:
   Summary, fields, line items, validation sheets. "Real spreadsheet,
   ready for bookkeeping."

Total: ~90 seconds.

## Project layout

```
ai-document-processor/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI routes
│   │   ├── auth.py                 # demo JWT (NOT production auth)
│   │   ├── store.py                # in-memory doc store
│   │   ├── pipeline.py             # text → extractor → validation
│   │   ├── validation.py           # totals / date / required checks
│   │   ├── export.py               # openpyxl xlsx builder
│   │   └── extraction/
│   │       ├── base.py             # Extractor interface + contracts
│   │       └── invoice_extractor.py# deterministic DE+EN invoice rules
│   ├── tests/                      # 29 tests: extraction, validation, export, API
│   ├── generate_samples.py         # 3 fake invoices (reportlab)
│   └── samples/                    # generated fake PDFs (gitignored or committed)
├── frontend/
│   ├── app/
│   │   ├── login/page.tsx
│   │   ├── page.tsx                # upload + document list
│   │   └── documents/[id]/page.tsx # fields, confidences, warnings, export
│   ├── lib/api.ts
│   └── next.config.mjs             # /api rewrite → :8000
└── README.md
```

## API quick reference

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | – | `{username,password}` → JWT (demo/demo1234) |
| GET | `/api/auth/me` | ✓ | current demo user |
| POST | `/api/upload` | ✓ | multipart PDF/image (10 MB max) |
| GET | `/api/documents` | ✓ | list |
| GET | `/api/documents/{id}` | ✓ | detail + extraction + validation |
| POST | `/api/documents/{id}/extract` | ✓ | run pipeline (`{"extractor":"invoice"}`) |
| GET | `/api/documents/{id}/export.xlsx` | ✓ | workbook download |
| GET | `/api/export.xlsx` | ✓ | all extracted docs, one workbook |

Interactive docs: http://localhost:8000/docs

## Honest limitations

- Text-based PDFs only — scanned/image PDFs need OCR, which is not bundled
  (the API says so explicitly instead of failing silently).
- Rule-based extractor: great on standard invoice layouts, not a general
  document-AI model. The interface is built for swapping one in.
- Demo auth, in-memory store: restart the backend and documents are gone.
  By design for a portfolio demo.
