import React, { useEffect, useState } from "react";
import { useParams } from "@tanstack/react-router";
import { ModuleInstallButton } from "../../features/modules/ModuleInstallButton";

const DAEMON = "http://127.0.0.1:9473";

interface MethodInfo {
  method_id: string;
  name?: string;
  required_data_types?: string[];
}

interface ModuleInfo {
  domain_id: string;
  domain_name: string;
  version: string;
  author?: string;
  author_orcid?: string;
  description?: string;
  status: "active" | "deprecated" | "revoked";
  methods?: MethodInfo[];
  supported_data_types?: string[];
  installed?: boolean;
}

export function ModuleDetail() {
  const { domainId } = useParams({ strict: false });
  const [mod, setMod] = useState<ModuleInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchModule = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${DAEMON}/modules/${domainId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setMod(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load module");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchModule(); }, [domainId]);

  if (loading) return <p style={{ color: "var(--ss-text-muted)" }}>Loading...</p>;
  if (error) return <p style={{ color: "var(--ss-error)" }}>Error: {error}</p>;
  if (!mod) return <p style={{ color: "var(--ss-text-muted)" }}>Module not found.</p>;

  const statusColor = mod.status === "active"
    ? "var(--ss-success)"
    : mod.status === "deprecated"
    ? "var(--ss-warning)"
    : "var(--ss-error)";

  return (
    <div>
      <style>{styles}</style>

      <div className="md-header">
        <div>
          <h1 className="md-title">{mod.domain_name || mod.domain_id}</h1>
          <span className="md-domain-id">{mod.domain_id}</span>
        </div>
        <span className="md-badge" style={{ background: statusColor }}>
          {mod.status}
        </span>
      </div>

      <div className="md-meta">
        <div className="md-meta-item">
          <span className="md-label">Version</span>
          <span>{mod.version}</span>
        </div>
        {mod.author && (
          <div className="md-meta-item">
            <span className="md-label">Author</span>
            <span>{mod.author}</span>
          </div>
        )}
        {mod.author_orcid && (
          <div className="md-meta-item">
            <span className="md-label">ORCID</span>
            <span>{mod.author_orcid}</span>
          </div>
        )}
      </div>

      {mod.description && (
        <p className="md-description">{mod.description}</p>
      )}

      <div className="md-actions">
        <ModuleInstallButton
          domainId={mod.domain_id}
          installed={!!mod.installed}
          version={mod.version}
          onComplete={fetchModule}
        />
      </div>

      {mod.methods && mod.methods.length > 0 && (
        <div className="md-section">
          <h2 className="md-section-title">Methods ({mod.methods.length})</h2>
          <ul className="md-method-list">
            {mod.methods.map((m) => (
              <li key={m.method_id} className="md-method">
                <span className="md-method-id">{m.method_id}</span>
                {m.name && <span className="md-method-name">{m.name}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const styles = `
  .md-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 20px;
  }
  .md-title {
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 4px;
  }
  .md-domain-id {
    font-size: 13px;
    color: var(--ss-text-muted);
    font-family: monospace;
  }
  .md-badge {
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    color: #fff;
    text-transform: uppercase;
  }
  .md-meta {
    display: flex;
    gap: 24px;
    margin-bottom: 16px;
  }
  .md-meta-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 14px;
  }
  .md-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--ss-text-muted);
  }
  .md-description {
    color: var(--ss-text);
    font-size: 14px;
    line-height: 1.6;
    margin-bottom: 20px;
  }
  .md-actions {
    margin-bottom: 24px;
  }
  .md-section {
    border-top: 1px solid var(--ss-border);
    padding-top: 16px;
  }
  .md-section-title {
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 12px;
  }
  .md-method-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  .md-method {
    padding: 8px 12px;
    background: var(--ss-surface);
    border: 1px solid var(--ss-border);
    border-radius: 6px;
    margin-bottom: 8px;
    display: flex;
    gap: 12px;
    align-items: center;
  }
  .md-method-id {
    font-family: monospace;
    font-size: 13px;
    color: var(--ss-accent);
  }
  .md-method-name {
    font-size: 13px;
    color: var(--ss-text-muted);
  }
`;
