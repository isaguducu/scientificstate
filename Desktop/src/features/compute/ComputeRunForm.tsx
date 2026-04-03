import React, { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";

const DAEMON = "http://127.0.0.1:9473";

interface DomainSummary {
  domain_id: string;
  domain_name: string;
  supported_data_types: string[];
  method_count: number;
  version: string;
}

interface MethodManifest {
  method_id: string;
  name: string;
}

interface Props {
  workspaceId: string;
}

export function ComputeRunForm({ workspaceId }: Props) {
  const [domains, setDomains] = useState<DomainSummary[]>([]);
  const [methods, setMethods] = useState<MethodManifest[]>([]);
  const [domainId, setDomainId] = useState("");
  const [methodId, setMethodId] = useState("");
  const [params, setParams] = useState("{}");
  const [datasetRef, setDatasetRef] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetch(`${DAEMON}/domains`)
      .then((r) => r.json())
      .then(setDomains)
      .catch(() => setError("Cannot reach daemon"));
  }, []);

  useEffect(() => {
    if (!domainId) { setMethods([]); return; }
    fetch(`${DAEMON}/domains/${domainId}`)
      .then((r) => r.json())
      .then((d) => setMethods(d.methods ?? []))
      .catch(() => setMethods([]));
  }, [domainId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      let parsedParams: Record<string, unknown> = {};
      try { parsedParams = JSON.parse(params); } catch { /* ignore */ }

      const resp = await fetch(`${DAEMON}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: workspaceId,
          domain_id: domainId,
          method_id: methodId,
          dataset_ref: datasetRef || undefined,
          assumptions: [],
          parameters: parsedParams,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const { run_id } = await resp.json();
      navigate({ to: "/compute/$runId", params: { runId: run_id } });
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div>
        <label style={{ display: "block", marginBottom: 4, fontSize: 13, color: "#aaa" }}>Domain</label>
        <select
          value={domainId}
          onChange={(e) => { setDomainId(e.target.value); setMethodId(""); }}
          required
          style={{ width: "100%", padding: "6px 10px", borderRadius: 6, border: "1px solid #444", background: "#1c1c1e", color: "#fff" }}
        >
          <option value="">— select domain —</option>
          {domains.map((d) => (
            <option key={d.domain_id} value={d.domain_id}>{d.domain_name}</option>
          ))}
        </select>
      </div>

      <div>
        <label style={{ display: "block", marginBottom: 4, fontSize: 13, color: "#aaa" }}>Method</label>
        <select
          value={methodId}
          onChange={(e) => setMethodId(e.target.value)}
          required
          disabled={!domainId}
          style={{ width: "100%", padding: "6px 10px", borderRadius: 6, border: "1px solid #444", background: "#1c1c1e", color: "#fff" }}
        >
          <option value="">— select method —</option>
          {methods.map((m) => (
            <option key={m.method_id} value={m.method_id}>{m.name ?? m.method_id}</option>
          ))}
        </select>
      </div>

      <div>
        <label style={{ display: "block", marginBottom: 4, fontSize: 13, color: "#aaa" }}>Dataset ref (optional)</label>
        <input
          value={datasetRef}
          onChange={(e) => setDatasetRef(e.target.value)}
          placeholder="raw_data_id from /datasets/ingest"
          style={{ width: "100%", padding: "6px 10px", borderRadius: 6, border: "1px solid #444", background: "#1c1c1e", color: "#fff", boxSizing: "border-box" }}
        />
      </div>

      <div>
        <label style={{ display: "block", marginBottom: 4, fontSize: 13, color: "#aaa" }}>Parameters (JSON)</label>
        <textarea
          value={params}
          onChange={(e) => setParams(e.target.value)}
          rows={4}
          style={{ width: "100%", padding: "6px 10px", borderRadius: 6, border: "1px solid #444", background: "#1c1c1e", color: "#fff", fontFamily: "monospace", boxSizing: "border-box" }}
        />
      </div>

      {error && <p style={{ color: "#ff453a", margin: 0 }}>{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        style={{ padding: "8px 20px", borderRadius: 6, background: "#00B7C7", border: "none", color: "#fff", cursor: submitting ? "not-allowed" : "pointer", opacity: submitting ? 0.7 : 1 }}
      >
        {submitting ? "Submitting…" : "Run Compute"}
      </button>
    </form>
  );
}
