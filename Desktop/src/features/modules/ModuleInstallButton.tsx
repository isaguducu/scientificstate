import React, { useState } from "react";

const DAEMON = "http://127.0.0.1:9473";

interface Props {
  domainId: string;
  installed: boolean;
  version: string;
  onComplete?: () => void;
}

export function ModuleInstallButton({ domainId, installed, version, onComplete }: Props) {
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null);

  const handleInstall = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${DAEMON}/modules/install`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ module_id: domainId, version }),
      });
      if (res.ok) {
        setFeedback({ ok: true, msg: "Installed successfully" });
        onComplete?.();
      } else {
        const data = await res.json().catch(() => ({}));
        setFeedback({ ok: false, msg: data.detail || `HTTP ${res.status}` });
      }
    } catch {
      setFeedback({ ok: false, msg: "Connection failed" });
    } finally {
      setLoading(false);
    }
  };

  const handleUninstall = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${DAEMON}/modules/${domainId}`, { method: "DELETE" });
      if (res.ok) {
        setFeedback({ ok: true, msg: "Uninstalled (data preserved)" });
        onComplete?.();
      } else {
        const data = await res.json().catch(() => ({}));
        setFeedback({ ok: false, msg: data.detail || `HTTP ${res.status}` });
      }
    } catch {
      setFeedback({ ok: false, msg: "Connection failed" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <style>{styles}</style>

      {installed ? (
        <button
          className="mib-btn mib-uninstall"
          disabled={loading}
          onClick={handleUninstall}
        >
          {loading ? "Removing..." : "Uninstall"}
        </button>
      ) : (
        <button
          className="mib-btn mib-install"
          disabled={loading}
          onClick={handleInstall}
        >
          {loading ? "Installing..." : "Install"}
        </button>
      )}

      {feedback && (
        <span
          className="mib-feedback"
          style={{ color: feedback.ok ? "var(--ss-success)" : "var(--ss-error)" }}
        >
          {feedback.msg}
        </span>
      )}
    </div>
  );
}

const styles = `
  .mib-btn {
    padding: 8px 20px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: opacity 0.15s;
  }
  .mib-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .mib-install {
    background: var(--ss-accent);
    color: #fff;
  }
  .mib-uninstall {
    background: transparent;
    border: 1px solid var(--ss-error);
    color: var(--ss-error);
  }
  .mib-feedback {
    margin-left: 12px;
    font-size: 13px;
  }
`;
