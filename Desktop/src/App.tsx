import React from "react";
import { DaemonStatus } from "./components/DaemonStatus";

// Tauri IPC — gracefully falls back when running in browser (e.g. vite dev without tauri)
async function tauriInvoke<T>(cmd: string): Promise<T> {
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return invoke<T>(cmd);
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

function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <span className="app-logo">⚗️ ScientificState</span>
          <span className="app-tagline">authoritative scientific work surface</span>
        </div>
      </header>

      <main className="app-main">
        <DaemonStatus />
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
  .app-main {
    flex: 1;
    padding: 24px;
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
  }
`;
document.head.appendChild(style);
