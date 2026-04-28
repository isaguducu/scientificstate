import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "@tanstack/react-router";

const DAEMON = "http://127.0.0.1:9473";

const S = {
  page: { padding: "24px", maxWidth: 1100, margin: "0 auto" } as React.CSSProperties,
  h2: { marginBottom: 20, fontSize: 20, fontWeight: 600 } as React.CSSProperties,
  layout: { display: "flex", gap: 20, minHeight: 600 } as React.CSSProperties,
  leftPanel: {
    width: "30%", minWidth: 220,
    background: "#1c1c1e", border: "1px solid #2c2c2e",
    borderRadius: 10, padding: 16,
    display: "flex", flexDirection: "column" as const, gap: 8,
  } as React.CSSProperties,
  rightPanel: {
    flex: 1, display: "flex", flexDirection: "column" as const, gap: 16,
  } as React.CSSProperties,
  card: {
    background: "#1c1c1e", border: "1px solid #2c2c2e",
    borderRadius: 10, padding: 18,
  } as React.CSSProperties,
  cardTitle: { fontSize: 14, fontWeight: 600, marginBottom: 14, color: "#00B7C7" } as React.CSSProperties,
  label: { display: "block", fontSize: 12, color: "#888", marginBottom: 4 } as React.CSSProperties,
  field: { marginBottom: 12 } as React.CSSProperties,
  input: {
    width: "100%", boxSizing: "border-box" as const,
    padding: "6px 10px", borderRadius: 6,
    border: "1px solid #2c2c2e", background: "#0d0d0f",
    color: "#fff", fontSize: 13,
  } as React.CSSProperties,
  textarea: {
    width: "100%", boxSizing: "border-box" as const,
    padding: "8px 10px", borderRadius: 6,
    border: "1px solid #2c2c2e", background: "#0d0d0f",
    color: "#fff", fontSize: 13, minHeight: 72, resize: "vertical" as const,
  } as React.CSSProperties,
  select: {
    width: "100%", boxSizing: "border-box" as const,
    padding: "6px 10px", borderRadius: 6,
    border: "1px solid #2c2c2e", background: "#0d0d0f",
    color: "#fff", fontSize: 13,
  } as React.CSSProperties,
  btn: {
    padding: "7px 18px", borderRadius: 6, border: "none",
    background: "#00B7C7", color: "#fff", fontSize: 13,
    cursor: "pointer", fontWeight: 600,
  } as React.CSSProperties,
  btnSmall: {
    padding: "5px 12px", borderRadius: 5, border: "none",
    background: "#0a84ff", color: "#fff", fontSize: 12,
    cursor: "pointer",
  } as React.CSSProperties,
  btnOutline: {
    padding: "5px 12px", borderRadius: 5,
    border: "1px solid #2c2c2e", background: "transparent",
    color: "#888", fontSize: 12, cursor: "pointer",
  } as React.CSSProperties,
  questionItem: (selected: boolean): React.CSSProperties => ({
    padding: "10px 12px", borderRadius: 7,
    background: selected ? "#002b30" : "transparent",
    border: selected ? "1px solid #00B7C7" : "1px solid transparent",
    cursor: "pointer", marginBottom: 4,
  }),
  statusBadge: (status: string): React.CSSProperties => ({
    display: "inline-block", fontSize: 10, fontWeight: 600,
    padding: "2px 6px", borderRadius: 4,
    background: status === "answered" ? "#0d2b1a" : "#1c1c1e",
    color: status === "answered" ? "#30d158" : "#0a84ff",
    border: `1px solid ${status === "answered" ? "#30d158" : "#0a84ff"}`,
    marginLeft: 6,
  }),
  error: { color: "#ff453a", fontSize: 12, marginTop: 6 } as React.CSSProperties,
  success: { color: "#30d158", fontSize: 12, marginTop: 6 } as React.CSSProperties,
  kvRow: { display: "flex", gap: 6, marginBottom: 6 } as React.CSSProperties,
  kvInput: {
    flex: 1, padding: "5px 8px", borderRadius: 5,
    border: "1px solid #2c2c2e", background: "#0d0d0f",
    color: "#fff", fontSize: 12,
  } as React.CSSProperties,
};

interface QuestionItem {
  question_id: string;
  text: string;
  status: string;
}

interface DomainSummary {
  domain_id: string;
  name: string;
}

interface DomainDetail {
  domain_id: string;
  name: string;
  methods: MethodSummary[];
}

interface MethodSummary {
  method_id: string;
  name: string;
}

interface KVPair {
  key: string;
  value: string;
}

export function QuestionWorkspace() {
  const { workspaceId } = useParams({ from: "/workspace/$workspaceId" });
  const navigate = useNavigate();

  const [questions, setQuestions] = useState<QuestionItem[]>([]);
  const [selectedQ, setSelectedQ] = useState<QuestionItem | null>(null);
  const [domains, setDomains] = useState<DomainSummary[]>([]);

  // Create question form
  const [newQuestionText, setNewQuestionText] = useState("");
  const [newDomainId, setNewDomainId] = useState("");
  const [qError, setQError] = useState<string | null>(null);
  const [qSuccess, setQSuccess] = useState<string | null>(null);
  const [qSubmitting, setQSubmitting] = useState(false);

  // Run form
  const [runDomainId, setRunDomainId] = useState("");
  const [domainDetail, setDomainDetail] = useState<DomainDetail | null>(null);
  const [methodId, setMethodId] = useState("");
  const [datasetRef, setDatasetRef] = useState("");
  const [assumptions, setAssumptions] = useState<KVPair[]>([{ key: "", value: "" }]);
  const [runError, setRunError] = useState<string | null>(null);
  const [runSubmitting, setRunSubmitting] = useState(false);

  useEffect(() => {
    loadQuestions();
    fetch(`${DAEMON}/domains`)
      .then((r) => r.json())
      .then(setDomains)
      .catch(() => {});
  }, [workspaceId]);

  useEffect(() => {
    if (!runDomainId) { setDomainDetail(null); return; }
    fetch(`${DAEMON}/domains/${runDomainId}`)
      .then((r) => r.json())
      .then(setDomainDetail)
      .catch(() => {});
  }, [runDomainId]);

  async function loadQuestions() {
    try {
      const r = await fetch(`${DAEMON}/workspaces/${workspaceId}/questions`);
      if (r.ok) setQuestions(await r.json());
    } catch { /* ignore */ }
  }

  async function handleCreateQuestion(e: React.FormEvent) {
    e.preventDefault();
    setQError(null);
    setQSuccess(null);
    if (newQuestionText.trim().length < 5) {
      setQError("Question must be at least 5 characters.");
      return;
    }
    setQSubmitting(true);
    try {
      const resp = await fetch(`${DAEMON}/workspaces/${workspaceId}/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: newQuestionText.trim(), domain_id: newDomainId }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const q = await resp.json();
      setQSuccess(`Question created. ID: ${q.question_id}`);
      setNewQuestionText("");
      await loadQuestions();
      setSelectedQ(q);
    } catch (err) {
      setQError(String(err));
    } finally {
      setQSubmitting(false);
    }
  }

  function addAssumption() {
    setAssumptions((prev) => [...prev, { key: "", value: "" }]);
  }
  function removeAssumption(idx: number) {
    setAssumptions((prev) => prev.filter((_, i) => i !== idx));
  }
  function updateAssumption(idx: number, field: "key" | "value", val: string) {
    setAssumptions((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, [field]: val } : p))
    );
  }

  async function handleStartRun(e: React.FormEvent) {
    e.preventDefault();
    setRunError(null);
    setRunSubmitting(true);
    try {
      const assumptionsObj: Record<string, string> = {};
      for (const kv of assumptions) {
        if (kv.key.trim()) assumptionsObj[kv.key.trim()] = kv.value.trim();
      }
      const body = {
        workspace_id: workspaceId,
        domain_id: runDomainId,
        method_id: methodId,
        dataset_ref: datasetRef,
        assumptions: assumptionsObj,
        compute_class: "classical",
      };
      const resp = await fetch(`${DAEMON}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const run = await resp.json();
      navigate({ to: "/compute/$runId", params: { runId: run.run_id } });
    } catch (err) {
      setRunError(String(err));
    } finally {
      setRunSubmitting(false);
    }
  }

  return (
    <div style={S.page}>
      <h2 style={S.h2}>
        Question Workspace
        <span style={{ fontSize: 13, fontWeight: 400, color: "#888", marginLeft: 10 }}>
          {workspaceId}
        </span>
      </h2>

      <div style={S.layout}>
        {/* Left panel — questions list */}
        <div style={S.leftPanel}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Questions</div>
          {questions.length === 0 && (
            <div style={{ fontSize: 12, color: "#888" }}>No questions yet.</div>
          )}
          {questions.map((q) => (
            <div
              key={q.question_id}
              style={S.questionItem(selectedQ?.question_id === q.question_id)}
              onClick={() => setSelectedQ(q)}
            >
              <div style={{ fontSize: 12, lineHeight: 1.4 }}>{q.text}</div>
              <span style={S.statusBadge(q.status)}>{q.status}</span>
            </div>
          ))}
        </div>

        {/* Right panel */}
        <div style={S.rightPanel}>
          {/* Create question */}
          <div style={S.card}>
            <div style={S.cardTitle}>Bilimsel Sorunuzu Tanimlayın</div>
            <form onSubmit={handleCreateQuestion}>
              <div style={S.field}>
                <label style={S.label}>Soru (min 5 karakter)</label>
                <textarea
                  value={newQuestionText}
                  onChange={(e) => setNewQuestionText(e.target.value)}
                  placeholder="Araştırmak istediğiniz bilimsel soruyu yazın…"
                  style={S.textarea}
                />
              </div>
              <div style={S.field}>
                <label style={S.label}>Domain</label>
                <select
                  value={newDomainId}
                  onChange={(e) => setNewDomainId(e.target.value)}
                  style={S.select}
                >
                  <option value="">-- domain seç --</option>
                  {domains.map((d) => (
                    <option key={d.domain_id} value={d.domain_id}>
                      {d.name || d.domain_id}
                    </option>
                  ))}
                </select>
              </div>
              <button type="submit" style={S.btn} disabled={qSubmitting}>
                {qSubmitting ? "Kaydediliyor…" : "Başlat"}
              </button>
              {qError && <div style={S.error}>{qError}</div>}
              {qSuccess && <div style={S.success}>{qSuccess}</div>}
            </form>
          </div>

          {/* Start run */}
          <div style={S.card}>
            <div style={S.cardTitle}>
              Run Başlat
              {selectedQ && (
                <span style={{ fontSize: 11, fontWeight: 400, color: "#888", marginLeft: 8 }}>
                  → {selectedQ.text.slice(0, 60)}{selectedQ.text.length > 60 ? "…" : ""}
                </span>
              )}
            </div>
            <form onSubmit={handleStartRun}>
              <div style={S.field}>
                <label style={S.label}>Domain</label>
                <select
                  value={runDomainId}
                  onChange={(e) => setRunDomainId(e.target.value)}
                  required
                  style={S.select}
                >
                  <option value="">-- domain seç --</option>
                  {domains.map((d) => (
                    <option key={d.domain_id} value={d.domain_id}>
                      {d.name || d.domain_id}
                    </option>
                  ))}
                </select>
              </div>

              <div style={S.field}>
                <label style={S.label}>Method</label>
                <select
                  value={methodId}
                  onChange={(e) => setMethodId(e.target.value)}
                  required
                  style={S.select}
                >
                  <option value="">-- method seç --</option>
                  {(domainDetail?.methods ?? []).map((m) => (
                    <option key={m.method_id} value={m.method_id}>
                      {m.name || m.method_id}
                    </option>
                  ))}
                </select>
              </div>

              <div style={S.field}>
                <label style={S.label}>Dataset Ref (raw_data_id)</label>
                <input
                  value={datasetRef}
                  onChange={(e) => setDatasetRef(e.target.value)}
                  placeholder="Ingest'ten alınan raw_data_id"
                  style={S.input}
                />
              </div>

              <div style={S.field}>
                <label style={S.label}>Assumptions</label>
                {assumptions.map((kv, idx) => (
                  <div key={idx} style={S.kvRow}>
                    <input
                      value={kv.key}
                      onChange={(e) => updateAssumption(idx, "key", e.target.value)}
                      placeholder="key"
                      style={S.kvInput}
                    />
                    <input
                      value={kv.value}
                      onChange={(e) => updateAssumption(idx, "value", e.target.value)}
                      placeholder="value"
                      style={S.kvInput}
                    />
                    <button
                      type="button"
                      onClick={() => removeAssumption(idx)}
                      style={{ ...S.btnOutline, padding: "4px 8px" }}
                    >
                      ×
                    </button>
                  </div>
                ))}
                <button type="button" onClick={addAssumption} style={S.btnOutline}>
                  + Ekle
                </button>
              </div>

              <button type="submit" style={S.btn} disabled={runSubmitting}>
                {runSubmitting ? "Başlatılıyor…" : "Run Başlat"}
              </button>
              {runError && <div style={S.error}>{runError}</div>}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
