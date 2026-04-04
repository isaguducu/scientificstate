import { useState, useEffect } from "react";

interface CredentialStatus {
  ibm: "connected" | "untested" | "none";
  ionq: "connected" | "untested" | "none";
}

export function CredentialManager() {
  const [ibmToken, setIbmToken] = useState("");
  const [ionqToken, setIonqToken] = useState("");
  const [status, setStatus] = useState<CredentialStatus>({ ibm: "none", ionq: "none" });
  const [testing, setTesting] = useState<string | null>(null);

  useEffect(() => {
    // Fetch current credential status from daemon
    fetch("http://localhost:9473/qpu/credential-status")
      .then((r) => r.json())
      .then((data) => setStatus(data))
      .catch(() => {});
  }, []);

  const saveCredential = async (provider: "ibm_quantum" | "ionq", token: string) => {
    // Save to daemon — daemon stores in encrypted config file
    // ~/.scientificstate/qpu-credentials.json (permissions 600, AES-256 encrypted)
    // Plain text token NEVER written to disk, NEVER logged
    const res = await fetch("http://localhost:9473/qpu/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, token }),
    });
    if (res.ok) {
      setStatus((prev) => ({
        ...prev,
        [provider === "ibm_quantum" ? "ibm" : "ionq"]: "untested",
      }));
    }
  };

  const testConnection = async (provider: "ibm_quantum" | "ionq") => {
    setTesting(provider);
    try {
      const res = await fetch(
        `http://localhost:9473/qpu/credentials/test?provider=${provider}`
      );
      const data = await res.json();
      setStatus((prev) => ({
        ...prev,
        [provider === "ibm_quantum" ? "ibm" : "ionq"]: data.ok ? "connected" : "none",
      }));
    } finally {
      setTesting(null);
    }
  };

  const statusColor = (s: string) =>
    s === "connected" ? "text-green-500" : s === "untested" ? "text-yellow-500" : "text-red-500";
  const statusLabel = (s: string) =>
    s === "connected" ? "Connected" : s === "untested" ? "Token set (untested)" : "Not configured";

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold">QPU Credentials</h3>
      <p className="text-sm text-gray-500">
        Tokens are stored in an encrypted local config file. They are never sent to any
        server other than the QPU provider.
      </p>

      {/* IBM Quantum */}
      <div className="border rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-medium">IBM Quantum</span>
          <span className={statusColor(status.ibm)}>{statusLabel(status.ibm)}</span>
        </div>
        <input
          type="password"
          placeholder="IBMQ_TOKEN"
          value={ibmToken}
          onChange={(e) => setIbmToken(e.target.value)}
          className="w-full border rounded px-3 py-2 font-mono text-sm"
        />
        <div className="flex gap-2">
          <button
            onClick={() => saveCredential("ibm_quantum", ibmToken)}
            disabled={!ibmToken}
            className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
          >
            Save
          </button>
          <button
            onClick={() => testConnection("ibm_quantum")}
            disabled={testing === "ibm_quantum" || status.ibm === "none"}
            className="px-4 py-2 border rounded disabled:opacity-50"
          >
            {testing === "ibm_quantum" ? "Testing..." : "Test Connection"}
          </button>
        </div>
      </div>

      {/* IonQ */}
      <div className="border rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-medium">IonQ</span>
          <span className={statusColor(status.ionq)}>{statusLabel(status.ionq)}</span>
        </div>
        <input
          type="password"
          placeholder="IONQ_TOKEN"
          value={ionqToken}
          onChange={(e) => setIonqToken(e.target.value)}
          className="w-full border rounded px-3 py-2 font-mono text-sm"
        />
        <div className="flex gap-2">
          <button
            onClick={() => saveCredential("ionq", ionqToken)}
            disabled={!ionqToken}
            className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
          >
            Save
          </button>
          <button
            onClick={() => testConnection("ionq")}
            disabled={testing === "ionq" || status.ionq === "none"}
            className="px-4 py-2 border rounded disabled:opacity-50"
          >
            {testing === "ionq" ? "Testing..." : "Test Connection"}
          </button>
        </div>
      </div>

      <p className="text-xs text-gray-400">
        Env vars (IBMQ_TOKEN, IONQ_TOKEN) override stored credentials — for CI/test only.
      </p>
    </div>
  );
}
