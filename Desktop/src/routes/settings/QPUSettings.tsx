import { CredentialManager } from "../../components/CredentialManager";
import { useState, useEffect } from "react";

type Tab = "credentials" | "broker" | "usage" | "prices";

export function QPUSettings() {
  const [activeTab, setActiveTab] = useState<Tab>("credentials");
  const [usage, setUsage] = useState<any[]>([]);
  const [prices, setPrices] = useState<any[]>([]);

  useEffect(() => {
    if (activeTab === "usage") {
      fetch("http://localhost:9473/qpu/usage/summary")
        .then((r) => r.json())
        .then((data) => setUsage(data.summary || []))
        .catch(() => {});
    }
    if (activeTab === "prices") {
      fetch("http://localhost:9473/qpu/price-snapshots/active")
        .then((r) => r.json())
        .then((data) => setPrices(data.prices || []))
        .catch(() => {});
    }
  }, [activeTab]);

  const tabs: { id: Tab; label: string }[] = [
    { id: "credentials", label: "Credentials (BYOT)" },
    { id: "broker", label: "Institutional Broker" },
    { id: "usage", label: "Usage & Quotas" },
    { id: "prices", label: "Price Table" },
  ];

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <h2 className="text-2xl font-bold">QPU Settings</h2>

      <div className="flex border-b">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              activeTab === tab.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "credentials" && <CredentialManager />}

      {activeTab === "broker" && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Institutional Broker (Tier 2)</h3>
          <p className="text-sm text-gray-500">
            Institutional tokens are managed by your institution admin. You cannot
            see or modify the institution token directly.
          </p>
          <div className="border rounded-lg p-4">
            <div className="flex items-center justify-between">
              <span>Signed Grant Status</span>
              <span className="text-yellow-500">No active grant</span>
            </div>
            <button className="mt-3 px-4 py-2 border rounded text-sm hover:bg-gray-50">
              Request Grant from Admin
            </button>
          </div>
          <p className="text-xs text-gray-400">
            Tier 2 broker is available for IBM Quantum only in Phase 8.
          </p>
        </div>
      )}

      {activeTab === "usage" && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Usage & Quotas</h3>
          {usage.length === 0 ? (
            <p className="text-sm text-gray-500">No usage data in the last 30 days.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Provider</th>
                  <th className="text-left py-2">Runs</th>
                  <th className="text-left py-2">Total Shots</th>
                  <th className="text-left py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {usage.map((row: any, i: number) => (
                  <tr key={i} className="border-b">
                    <td className="py-2">{row.provider}</td>
                    <td className="py-2">{row.run_count}</td>
                    <td className="py-2">{row.total_shots?.toLocaleString()}</td>
                    <td className="py-2">{row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === "prices" && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Active Price Snapshots</h3>
          {prices.length === 0 ? (
            <p className="text-sm text-gray-500">No active price snapshots.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Provider</th>
                  <th className="text-left py-2">Backend</th>
                  <th className="text-left py-2">$/shot</th>
                  <th className="text-left py-2">$/task</th>
                  <th className="text-left py-2">Effective</th>
                </tr>
              </thead>
              <tbody>
                {prices.map((row: any, i: number) => (
                  <tr key={i} className="border-b">
                    <td className="py-2">{row.provider}</td>
                    <td className="py-2">{row.backend_name}</td>
                    <td className="py-2">{row.price_per_shot ?? "free"}</td>
                    <td className="py-2">{row.price_per_task ?? "—"}</td>
                    <td className="py-2">{row.effective_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
