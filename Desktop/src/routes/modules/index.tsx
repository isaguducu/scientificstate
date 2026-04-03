import React, { useEffect, useState } from "react";
import { ModuleCard } from "../../features/modules/ModuleCard";

const DAEMON = "http://127.0.0.1:9473";

interface ModuleSummary {
  domain_id: string;
  name: string;
  version: string;
  author?: string;
  status: "active" | "deprecated" | "revoked";
  download_count?: number;
  description?: string;
}

type Tab = "installed" | "available";
type Filter = "all" | "active" | "deprecated";

export function ModuleStore() {
  const [tab, setTab] = useState<Tab>("installed");
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [installed, setInstalled] = useState<ModuleSummary[]>([]);
  const [available, setAvailable] = useState<ModuleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const fetchData = async () => {
      try {
        const [instRes, availRes] = await Promise.all([
          fetch(`${DAEMON}/modules`),
          fetch(`${DAEMON}/modules/available`),
        ]);

        if (!cancelled) {
          setInstalled(instRes.ok ? await instRes.json() : []);
          setAvailable(availRes.ok ? await availRes.json() : []);
        }
      } catch (err) {
        if (!cancelled) setError("Failed to connect to daemon");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchData();
    return () => { cancelled = true; };
  }, []);

  const handleSearch = async (q: string) => {
    setQuery(q);
    if (!q.trim()) return;
    try {
      const res = await fetch(`${DAEMON}/modules/search?q=${encodeURIComponent(q)}`);
      if (res.ok) {
        const results: ModuleSummary[] = await res.json();
        setAvailable(results);
        setTab("available");
      }
    } catch { /* ignore */ }
  };

  const modules = tab === "installed" ? installed : available;
  const filtered = modules.filter((m) => {
    if (filter === "all") return true;
    return m.status === filter;
  });

  return (
    <div>
      <style>{styles}</style>

      <div className="ms-header">
        <h1 className="ms-title">Module Store</h1>
        <input
          className="ms-search"
          type="text"
          placeholder="Search modules..."
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
        />
      </div>

      <div className="ms-tabs">
        <button
          className={`ms-tab ${tab === "installed" ? "ms-tab-active" : ""}`}
          onClick={() => setTab("installed")}
        >
          Installed ({installed.length})
        </button>
        <button
          className={`ms-tab ${tab === "available" ? "ms-tab-active" : ""}`}
          onClick={() => setTab("available")}
        >
          Available ({available.length})
        </button>

        <div className="ms-filter">
          {(["all", "active", "deprecated"] as Filter[]).map((f) => (
            <button
              key={f}
              className={`ms-filter-btn ${filter === f ? "ms-filter-active" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="ms-status">Loading modules...</p>}
      {error && <p className="ms-status ms-error">{error}</p>}

      {!loading && filtered.length === 0 && (
        <p className="ms-status">No modules found.</p>
      )}

      <div className="ms-grid">
        {filtered.map((m) => (
          <ModuleCard key={m.domain_id} module={m} />
        ))}
      </div>
    </div>
  );
}

const styles = `
  .ms-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
  }
  .ms-title {
    font-size: 22px;
    font-weight: 600;
    margin: 0;
  }
  .ms-search {
    flex: 1;
    max-width: 360px;
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid var(--ss-border);
    background: var(--ss-surface);
    color: var(--ss-text);
    font-size: 14px;
    outline: none;
  }
  .ms-search:focus {
    border-color: var(--ss-accent);
  }
  .ms-tabs {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 20px;
    border-bottom: 1px solid var(--ss-border);
    padding-bottom: 8px;
  }
  .ms-tab {
    padding: 6px 16px;
    border: none;
    background: transparent;
    color: var(--ss-text-muted);
    cursor: pointer;
    font-size: 14px;
    border-bottom: 2px solid transparent;
  }
  .ms-tab-active {
    color: var(--ss-accent);
    border-bottom-color: var(--ss-accent);
  }
  .ms-filter {
    margin-left: auto;
    display: flex;
    gap: 4px;
  }
  .ms-filter-btn {
    padding: 4px 10px;
    border: 1px solid var(--ss-border);
    border-radius: 4px;
    background: transparent;
    color: var(--ss-text-muted);
    font-size: 12px;
    cursor: pointer;
    text-transform: capitalize;
  }
  .ms-filter-active {
    background: var(--ss-accent);
    color: #fff;
    border-color: var(--ss-accent);
  }
  .ms-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }
  .ms-status {
    color: var(--ss-text-muted);
    font-size: 14px;
    padding: 24px 0;
    text-align: center;
  }
  .ms-error {
    color: var(--ss-error);
  }
`;
