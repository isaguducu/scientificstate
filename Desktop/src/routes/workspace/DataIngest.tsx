import React, { useEffect, useState } from "react";

const DAEMON = "http://127.0.0.1:9473";

const S = {
  page: { padding: "24px", maxWidth: 640, margin: "0 auto" } as React.CSSProperties,
  h2: { marginBottom: 24, fontSize: 20, fontWeight: 600 } as React.CSSProperties,
  label: { display: "block", fontSize: 12, color: "#888", marginBottom: 4 } as React.CSSProperties,
  field: { marginBottom: 16 } as React.CSSProperties,
  input: {
    width: "100%", boxSizing: "border-box" as const,
    padding: "7px 10px", borderRadius: 6,
    border: "1px solid #2c2c2e", background: "#1c1c1e",
    color: "#fff", fontSize: 13,
  } as React.CSSProperties,
  select: {
    width: "100%", boxSizing: "border-box" as const,
    padding: "7px 10px", borderRadius: 6,
    border: "1px solid #2c2c2e", background: "#1c1c1e",
    color: "#fff", fontSize: 13,
  } as React.CSSProperties,
  btn: {
    padding: "8px 20px", borderRadius: 6, border: "none",
    background: "#00B7C7", color: "#fff", fontSize: 13,
    cursor: "pointer", fontWeight: 600,
  } as React.CSSProperties,
  btnSecondary: {
    padding: "6px 14px", borderRadius: 6, border: "1px solid #2c2c2e",
    background: "#1c1c1e", color: "#fff", fontSize: 12, cursor: "pointer",
  } as React.CSSProperties,
  success: {
    background: "#0d2b1a", border: "1px solid #30d158", borderRadius: 8,
    padding: "14px 16px", marginTop: 20, color: "#30d158", fontSize: 13,
  } as React.CSSProperties,
  error: {
    background: "#2b0d0d", border: "1px solid #ff453a", borderRadius: 8,
    padding: "14px 16px", marginTop: 20, color: "#ff453a", fontSize: 13,
  } as React.CSSProperties,
};

interface DomainSummary {
  domain_id: string;
  name: string;
}

export function DataIngest() {
  const [domains, setDomains] = useState<DomainSummary[]>([]);
  const [domainId, setDomainId] = useState("");
  const [dataPath, setDataPath] = useState("");
  const [datasetName, setDatasetName] = useState("");
  const [instrumentId, setInstrumentId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ raw_data_id: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetch(`${DAEMON}/domains`)
      .then((r) => r.json())
      .then(setDomains)
      .catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setSubmitting(true);
    try {
      const body = {
        data_path: dataPath,
        domain_id: domainId,
        dataset_name: datasetName,
        acquisition_timestamp: new Date().toISOString(),
        instrument_id: instrumentId || "unknown",
        signal_metadata: {},
      };
      const resp = await fetch(`${DAEMON}/datasets/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${txt}`);
      }
      const data = await resp.json();
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  function handleCopy() {
    if (!result) return;
    navigator.clipboard.writeText(result.raw_data_id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div style={S.page}>
      <h2 style={S.h2}>Dataset Ingest</h2>

      <form onSubmit={handleSubmit}>
        <div style={S.field}>
          <label style={S.label}>Domain</label>
          <select
            value={domainId}
            onChange={(e) => setDomainId(e.target.value)}
            required
            style={S.select}
          >
            <option value="">-- select domain --</option>
            {domains.map((d) => (
              <option key={d.domain_id} value={d.domain_id}>
                {d.name || d.domain_id}
              </option>
            ))}
          </select>
        </div>

        <div style={S.field}>
          <label style={S.label}>File Path (macOS)</label>
          <input
            value={dataPath}
            onChange={(e) => setDataPath(e.target.value)}
            placeholder="/Users/you/data/sample.csv"
            required
            style={S.input}
          />
        </div>

        <div style={S.field}>
          <label style={S.label}>Dataset Name</label>
          <input
            value={datasetName}
            onChange={(e) => setDatasetName(e.target.value)}
            placeholder="PS sample 01"
            required
            style={S.input}
          />
        </div>

        <div style={S.field}>
          <label style={S.label}>Instrument ID (optional)</label>
          <input
            value={instrumentId}
            onChange={(e) => setInstrumentId(e.target.value)}
            placeholder="gc-ms-001"
            style={S.input}
          />
        </div>

        <button type="submit" style={S.btn} disabled={submitting}>
          {submitting ? "Ingesting…" : "Ingest Dataset"}
        </button>
      </form>

      {result && (
        <div style={S.success}>
          <div style={{ marginBottom: 8, fontWeight: 600 }}>Dataset ingested.</div>
          <div style={{ fontSize: 12, marginBottom: 8 }}>
            ID: <span style={{ fontFamily: "monospace" }}>{result.raw_data_id}</span>
          </div>
          <button onClick={handleCopy} style={S.btnSecondary}>
            {copied ? "Copied!" : "Copy ID"}
          </button>
        </div>
      )}

      {error && (
        <div style={S.error}>
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  );
}
