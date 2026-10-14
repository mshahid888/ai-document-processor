"""
AI Document Processor — backend (FastAPI).

Local demo server. Run:  .venv/bin/uvicorn app.main:app --reload --port 8000
API docs (after login token not needed for docs UI): http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .auth import DEMO_PASSWORD, DEMO_USERNAME, create_token, get_current_user
from .export import build_workbook
from .pipeline import DEFAULT_EXTRACTOR, EXTRACTORS, run_pipeline
from .store import store

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

app = FastAPI(
    title="AI Document Processor (demo)",
    description="Upload invoice PDFs -> deterministic extraction -> validation -> xlsx export. "
                "Demo auth only; all data is fake and stays on this machine.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# auth
# --------------------------------------------------------------------------

class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginBody):
    """Demo login. Credentials: demo / demo1234 (see app/auth.py)."""
    if body.username == DEMO_USERNAME and body.password == DEMO_PASSWORD:
        return {"access_token": create_token(body.username), "token_type": "bearer",
                "demo": True}
    raise HTTPException(status_code=401, detail="Invalid demo credentials.")


@app.get("/api/auth/me")
def me(user: str = Depends(get_current_user)):
    return {"username": user, "demo": True}


# --------------------------------------------------------------------------
# documents
# --------------------------------------------------------------------------

@app.post("/api/upload")
async def upload(file: UploadFile = File(...),
                 user: str = Depends(get_current_user)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    doc = store.add(file.filename or "upload", file.content_type or "", data)
    return doc.summary()


@app.get("/api/documents")
def list_documents(user: str = Depends(get_current_user)):
    return {"documents": [d.summary() for d in store.all()]}


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: str, user: str = Depends(get_current_user)):
    doc = store.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc.detail()


class ExtractBody(BaseModel):
    extractor: str = DEFAULT_EXTRACTOR


@app.post("/api/documents/{doc_id}/extract")
def extract_document(doc_id: str, body: ExtractBody | None = None,
                     user: str = Depends(get_current_user)):
    doc = store.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    extractor_name = (body.extractor if body else DEFAULT_EXTRACTOR)
    if extractor_name not in EXTRACTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown extractor '{extractor_name}'. "
                   f"Available: {sorted(EXTRACTORS)}",
        )
    result, issues, warnings = run_pipeline(doc.file_bytes, doc.filename,
                                            extractor_name)
    doc.extraction = result
    doc.issues = issues
    doc.pipeline_warnings = warnings
    return doc.detail()


@app.get("/api/documents/{doc_id}/export.xlsx")
def export_document(doc_id: str, user: str = Depends(get_current_user)):
    doc = store.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if doc.extraction is None:
        raise HTTPException(
            status_code=409,
            detail="Document not extracted yet. POST /api/documents/{id}/extract first.",
        )
    xlsx = build_workbook(store.to_export_dicts([doc]))
    name = doc.filename.rsplit(".", 1)[0]
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}-extracted.xlsx"'},
    )


@app.get("/api/export.xlsx")
def export_all(user: str = Depends(get_current_user)):
    docs = [d for d in store.all() if d.extraction is not None]
    if not docs:
        raise HTTPException(status_code=409, detail="No extracted documents yet.")
    xlsx = build_workbook(store.to_export_dicts(docs))
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="documents-export.xlsx"'},
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "extractors": sorted(EXTRACTORS), "demo": True}
