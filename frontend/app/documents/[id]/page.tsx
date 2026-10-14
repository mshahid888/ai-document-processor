"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, downloadXlsx, getToken } from "../../../lib/api";

type Field = { value: any; confidence: number; source: string; warning: string | null };
type Issue = { severity: string; code: string; message: string };

function confClass(c: number) {
  if (c >= 0.85) return "conf-hi";
  if (c >= 0.6) return "conf-mid";
  return "conf-lo";
}

function fmtValue(v: any) {
  if (v === null || v === undefined) return <span className="field-null">null — not found, not guessed</span>;
  if (typeof v === "number") return v.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return String(v);
}

export default function DocumentPage() {
  const { id } = useParams();
  const [doc, setDoc] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const refresh = useCallback(async () => {
    try {
      setDoc(await api(`/api/documents/${id}`));
    } catch (e: any) {
      setError(e.message);
    }
  }, [id]);

  useEffect(() => {
    if (!getToken()) router.push("/login");
    else refresh();
  }, [refresh, router]);

  async function reextract() {
    setBusy(true);
    setError("");
    try {
      setDoc(await api(`/api/documents/${id}/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (error) return <div className="wrap"><div className="error-text">{error}</div><Link href="/">← back</Link></div>;
  if (!doc) return <div className="wrap"><p className="hint">Loading…</p></div>;

  const ext = doc.extraction;
  const issues: Issue[] = doc.validation || [];

  return (
    <div className="wrap">
      <div className="topbar">
        <div>
          <h1 className="mono">{doc.filename}</h1>
          <div className="sub">
            extractor: <span className="mono">{ext?.extractor || "—"}</span> · uploaded {doc.uploaded_at?.replace("T", " ")}
          </div>
        </div>
        <Link className="btn" href="/">← Documents</Link>
      </div>

      {!ext ? (
        <div className="card">
          <p className="hint">Not extracted yet.</p>
          <button className="btn primary" disabled={busy} onClick={reextract}>
            {busy ? "Extracting…" : "Run extraction"}
          </button>
        </div>
      ) : (
        <>
          <div className="card">
            <h2>Extracted fields <span className="hint">(per-field confidence — null means not found, never guessed)</span></h2>
            <table className="grid">
              <thead><tr><th>Field</th><th>Value</th><th>Confidence</th><th>Source</th></tr></thead>
              <tbody>
                {Object.entries(ext.fields as Record<string, Field>).map(([name, f]) => (
                  <tr key={name}>
                    <td className="mono">{name}</td>
                    <td>
                      {fmtValue(f.value)}
                      {f.warning && <div className="hint">⚠ {f.warning}</div>}
                    </td>
                    <td>
                      <div className="confbar" title={`${Math.round(f.confidence * 100)}%`}>
                        <div className={confClass(f.confidence)} style={{ width: `${Math.round(f.confidence * 100)}%` }} />
                      </div>
                      <span className="hint">{Math.round(f.confidence * 100)}%</span>
                    </td>
                    <td className="mono hint">{f.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>Line items ({ext.line_items.length})</h2>
            {ext.line_items.length === 0 ? (
              <p className="hint">No line items parsed.</p>
            ) : (
              <table className="grid">
                <thead><tr><th>Description</th><th>Qty</th><th>Unit price</th><th>Line total</th><th>Conf.</th></tr></thead>
                <tbody>
                  {ext.line_items.map((li: any, i: number) => (
                    <tr key={i}>
                      <td>{li.description}</td>
                      <td>{li.quantity}</td>
                      <td>{fmtValue(li.unit_price)}</td>
                      <td>{fmtValue(li.line_total)}</td>
                      <td><span className="hint">{Math.round(li.confidence * 100)}%</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card">
            <h2>
              Validation{" "}
              {issues.length === 0
                ? <span className="badge ok">all checks passed</span>
                : <span className="badge warn">{issues.length} issue{issues.length > 1 ? "s" : ""}</span>}
            </h2>
            {issues.length === 0 ? (
              <p className="hint">Totals add up, dates sane, required fields present.</p>
            ) : (
              issues.map((iss, i) => (
                <div key={i} className={`issue ${iss.severity}`}>
                  <b>{iss.severity.toUpperCase()}</b> · <code>{iss.code}</code>
                  <div>{iss.message}</div>
                </div>
              ))
            )}
            {(doc.pipeline_warnings || []).map((w: string, i: number) => (
              <div key={"p" + i} className="issue info"><div>{w}</div></div>
            ))}
          </div>

          <div className="card">
            <h2>Export</h2>
            <div className="row-actions">
              <button
                className="btn primary"
                onClick={() => downloadXlsx(`/api/documents/${id}/export.xlsx`, `${doc.filename}-extracted.xlsx`)}
              >
                ⬇ Download .xlsx
              </button>
              <button className="btn" disabled={busy} onClick={reextract}>
                {busy ? "Extracting…" : "↻ Re-run extraction"}
              </button>
            </div>
            <p className="hint">Workbook contains field, line-item and validation sheets.</p>
          </div>
        </>
      )}
    </div>
  );
}
