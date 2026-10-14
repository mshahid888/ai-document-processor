"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, downloadXlsx, getToken, setToken } from "../lib/api";

type DocSummary = {
  id: string;
  filename: string;
  size_bytes: number;
  uploaded_at: string;
  extracted: boolean;
  issue_count: number;
};

export default function HomePage() {
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  const refresh = useCallback(async () => {
    try {
      const data = await api("/api/documents");
      setDocs(data.documents);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) router.push("/login");
    else refresh();
  }, [refresh, router]);

  async function uploadFile(file: File) {
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      await api("/api/upload", { method: "POST", body: form });
      await refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function extract(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/api/documents/${id}/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      await refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    setToken(null);
    router.push("/login");
  }

  return (
    <div className="wrap">
      <div className="topbar">
        <div>
          <h1>AI Document Processor</h1>
          <div className="sub">invoice PDFs → extraction → validation → spreadsheet</div>
        </div>
        <button className="btn" onClick={logout}>Sign out</button>
      </div>

      <div className="demo-banner">
        <b>Demo environment.</b> Auth is demo-grade (demo/demo1234), all
        invoices are fictional, and nothing leaves this machine.
      </div>

      <div className="card">
        <h2>1 · Upload a document</h2>
        <div
          className={"dropzone" + (dragOver ? " over" : "")}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) uploadFile(f);
          }}
        >
          {busy ? "Working…" : "Drop a PDF here or click to choose (text-based PDF, max 10 MB)"}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) uploadFile(f);
            e.target.value = "";
          }}
        />
        <p className="hint">
          Tip: the repo ships 3 fake sample invoices in{" "}
          <span className="mono">backend/samples/</span> — upload one to try the full flow.
        </p>
        {error && <div className="error-text">{error}</div>}
      </div>

      <div className="card">
        <h2>2 · Documents</h2>
        {docs.length === 0 ? (
          <p className="hint">No documents yet — upload one above.</p>
        ) : (
          <table className="grid">
            <thead>
              <tr>
                <th>File</th>
                <th>Uploaded</th>
                <th>Status</th>
                <th>Issues</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td className="mono">{d.filename}</td>
                  <td>{d.uploaded_at.replace("T", " ")}</td>
                  <td>
                    {d.extracted ? (
                      <span className="badge ok">extracted</span>
                    ) : (
                      <span className="badge idle">uploaded</span>
                    )}
                  </td>
                  <td>
                    {d.extracted && d.issue_count > 0 ? (
                      <span className="badge warn">{d.issue_count} ⚠</span>
                    ) : (
                      <span className="hint">—</span>
                    )}
                  </td>
                  <td>
                    <div className="row-actions">
                      {!d.extracted && (
                        <button className="btn" disabled={busy} onClick={() => extract(d.id)}>
                          Extract
                        </button>
                      )}
                      <Link className="btn" href={`/documents/${d.id}`}>View</Link>
                      {d.extracted && (
                        <button
                          className="btn"
                          onClick={() => downloadXlsx(`/api/documents/${d.id}/export.xlsx`, `${d.filename}-extracted.xlsx`)}
                        >
                          ⬇ xlsx
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {docs.some((d) => d.extracted) && (
          <div style={{ marginTop: 12 }}>
            <button
              className="btn primary"
              onClick={() => downloadXlsx("/api/export.xlsx", "documents-export.xlsx")}
            >
              ⬇ Export all extracted (.xlsx)
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
