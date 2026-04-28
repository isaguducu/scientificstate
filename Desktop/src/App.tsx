import React from "react";
import { Link } from "@tanstack/react-router";
import { DaemonStatus } from "./components/DaemonStatus";

// Tauri IPC — gracefully falls back when running in browser (e.g. vite dev without tauri)
async function tauriInvoke<T>(cmd: string): Promise<T> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke<T>(cmd);
  } catch {
    // Tauri not available (browser dev mode) — call daemon directly
    const urlMap: Record<string, string> = {
      get_daemon_health: "http://127.0.0.1:9473/health",
      get_domains: "http://127.0.0.1:9473/domains",
    };
    const url = urlMap[cmd];
    if (!url) throw new Error(`No browser fallback for command: ${cmd}`);
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as T;
  }
}

export { tauriInvoke };

interface Props {
  children?: React.ReactNode;
}

function App({ children }: Props) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <Link to="/" className="app-logo" style={{ textDecoration: "none", color: "inherit" }}>
            ⚗️ ScientificState
          </Link>
          <span className="app-tagline">authoritative scientific work surface</span>
          <nav className="app-nav">
            <Link to="/" className="app-nav-link">Dashboard</Link>
            <Link to="/ingest" className="app-nav-link">Ingest</Link>
            <Link to="/modules" className="app-nav-link">Modules</Link>
            <Link to="/settings/qpu" className="app-nav-link">Settings</Link>
          </nav>
          <div style={{ marginLeft: "auto" }}>
            <DaemonStatus />
          </div>
        </div>
      </header>

      <main className="app-main">
        {children}
      </main>
    </div>
  );
}

export default App;

// Inline styles — no build toolchain dependency for Phase 0
const style = document.createElement("style");
style.textContent = `
  .app-shell {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    background: var(--ss-bg);
  }
  .app-header {
    background: var(--ss-surface);
    border-bottom: 1px solid var(--ss-border);
    padding: 12px 24px;
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .app-header-inner {
    display: flex;
    align-items: center;
    gap: 16px;
    max-width: 1200px;
    margin: 0 auto;
  }
  .app-logo {
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.3px;
  }
  .app-tagline {
    font-size: 12px;
    color: var(--ss-text-muted);
    font-style: italic;
  }
  .app-nav {
    display: flex;
    gap: 8px;
    margin-left: 16px;
  }
  .app-nav-link {
    font-size: 13px;
    color: var(--ss-text-muted);
    text-decoration: none;
    padding: 4px 10px;
    border-radius: 4px;
    transition: color 0.15s, background 0.15s;
  }
  .app-nav-link:hover {
    color: var(--ss-text);
    background: var(--ss-surface-2);
  }
  .app-main {
    flex: 1;
    padding: 24px;
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
  }
`;
document.head.appendChild(style);
