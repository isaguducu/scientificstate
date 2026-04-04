import { useState } from "react";

interface PreRunCostEstimateProps {
  provider: string;
  backendName: string;
  shots: number;
  onConfirm: () => void;
  onCancel: () => void;
}

interface CostEstimate {
  currency: string;
  min: number;
  max: number;
  unit_price: number;
  shots: number;
}

interface QuotaStatus {
  shot_used: number;
  shot_limit: number;
  budget_used: number;
  budget_limit: number | null;
}

export function PreRunCostEstimate({
  provider,
  backendName,
  shots,
  onConfirm,
  onCancel,
}: PreRunCostEstimateProps) {
  const [estimate, setEstimate] = useState<CostEstimate | null>(null);
  const [quota, setQuota] = useState<QuotaStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useState(() => {
    // Fetch estimate from daemon
    fetch("http://localhost:9473/qpu/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, backend_name: backendName, shots }),
    })
      .then((r) => {
        if (!r.ok) return r.json().then((d) => Promise.reject(d));
        return r.json();
      })
      .then((data) => {
        setEstimate(data.estimate);
        setQuota(data.quota);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.detail || "Failed to estimate cost");
        setLoading(false);
      });
  });

  const isBlocked = error !== null;
  const isOverCap = estimate ? estimate.max > 50.0 : false;
  const isOverQuota = quota ? quota.shot_used + shots > quota.shot_limit : false;
  const canRun = !isBlocked && !isOverCap && !isOverQuota;

  const quotaPercent = quota ? Math.round((quota.shot_used / quota.shot_limit) * 100) : 0;

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 max-w-md w-full">
          <p className="text-center">Estimating cost...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full space-y-4">
        <h3 className="text-lg font-semibold">QPU Cost Estimate</h3>

        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">Provider</span>
            <span>{provider} ({backendName})</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Shots</span>
            <span>{shots.toLocaleString()}</span>
          </div>
          {estimate && (
            <>
              <div className="flex justify-between">
                <span className="text-gray-500">Unit price</span>
                <span>${estimate.unit_price}/shot</span>
              </div>
              <div className="flex justify-between font-medium">
                <span>Estimated cost</span>
                <span>
                  ${estimate.min.toFixed(2)} - ${estimate.max.toFixed(2)}
                </span>
              </div>
            </>
          )}
        </div>

        {quota && (
          <div className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Quota status</span>
              <span>
                {quota.shot_used.toLocaleString()} / {quota.shot_limit.toLocaleString()} shots ({quotaPercent}%)
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full ${quotaPercent > 90 ? "bg-red-500" : quotaPercent > 70 ? "bg-yellow-500" : "bg-green-500"}`}
                style={{ width: `${Math.min(quotaPercent, 100)}%` }}
              />
            </div>
          </div>
        )}

        {error && (
          <div className="text-red-600 text-sm bg-red-50 p-3 rounded">
            {error}
          </div>
        )}
        {isOverCap && (
          <div className="text-red-600 text-sm bg-red-50 p-3 rounded">
            Exceeds per-run cap ($50)
          </div>
        )}
        {isOverQuota && (
          <div className="text-red-600 text-sm bg-red-50 p-3 rounded">
            Shot quota exceeded
          </div>
        )}

        <p className="text-xs text-gray-400">
          This run will charge your {provider} account
        </p>

        <div className="flex justify-end gap-3 pt-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 border rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={!canRun}
            className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {canRun && estimate
              ? `Run (~$${((estimate.min + estimate.max) / 2).toFixed(2)})`
              : error
                ? "Price unknown"
                : "Blocked"}
          </button>
        </div>
      </div>
    </div>
  );
}
