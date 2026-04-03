import React from "react";
import { useNavigate } from "@tanstack/react-router";

interface ModuleSummary {
  domain_id: string;
  name: string;
  version: string;
  author?: string;
  status: "active" | "deprecated" | "revoked";
  download_count?: number;
  description?: string;
}

interface Props {
  module: ModuleSummary;
}

export function ModuleCard({ module: m }: Props) {
  const navigate = useNavigate();

  const statusColor = m.status === "active"
    ? "var(--ss-success)"
    : m.status === "deprecated"
    ? "var(--ss-warning)"
    : "var(--ss-error)";

  return (
    <div
      className="mc-card"
      onClick={() => navigate({ to: "/modules/$domainId", params: { domainId: m.domain_id } })}
    >
      <style>{styles}</style>

      <div className="mc-top">
        <span className="mc-name">{m.name || m.domain_id}</span>
        <span className="mc-badge" style={{ background: statusColor }}>{m.status}</span>
      </div>

      <span className="mc-version">v{m.version}</span>
      {m.author && <span className="mc-author">{m.author}</span>}
      {m.description && <p className="mc-desc">{m.description}</p>}

      {m.download_count !== undefined && (
        <span className="mc-downloads">{m.download_count} downloads</span>
      )}
    </div>
  );
}

const styles = `
  .mc-card {
    background: var(--ss-surface);
    border: 1px solid var(--ss-border);
    border-radius: 8px;
    padding: 16px;
    cursor: pointer;
    transition: border-color 0.15s;
  }
  .mc-card:hover {
    border-color: var(--ss-accent);
  }
  .mc-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }
  .mc-name {
    font-size: 15px;
    font-weight: 600;
  }
  .mc-badge {
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
    color: #fff;
    text-transform: uppercase;
  }
  .mc-version {
    font-size: 12px;
    color: var(--ss-text-muted);
    font-family: monospace;
    display: block;
    margin-bottom: 4px;
  }
  .mc-author {
    font-size: 12px;
    color: var(--ss-text-muted);
    display: block;
    margin-bottom: 8px;
  }
  .mc-desc {
    font-size: 13px;
    color: var(--ss-text);
    margin: 0 0 8px;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .mc-downloads {
    font-size: 11px;
    color: var(--ss-text-muted);
  }
`;
