/**
 * HybridResultView — dual-branch result display for hybrid compute runs.
 *
 * Phase 8 W2: Shows classical and quantum branches side-by-side with
 * per-branch execution witnesses, risk indicators, and result data.
 */

interface HybridResultViewProps {
  classicalResult: Record<string, any>;
  quantumResult: Record<string, any>;
  executionWitnesses: {
    classical: Record<string, any>;
    quantum: Record<string, any>;
  };
  status: string;
  computeArtifactRisk?: string;
  semanticLossRisk?: string;
}

export function HybridResultView({
  classicalResult,
  quantumResult,
  executionWitnesses,
  status,
  computeArtifactRisk,
  semanticLossRisk,
}: HybridResultViewProps) {
  const statusColor = (s: string) =>
    s === "ok" || s === "succeeded" ? "text-green-500" :
    s === "partial" ? "text-yellow-500" : "text-red-500";

  const riskColor = (r?: string) =>
    r === "low" ? "text-green-500" : r === "medium" ? "text-yellow-500" : "text-red-500";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h3 className="text-lg font-semibold">Hybrid Compute Result</h3>
        <span className={`px-2 py-1 rounded text-sm font-medium ${statusColor(status)} bg-gray-100`}>
          {status}
        </span>
      </div>

      {/* Risk indicators */}
      <div className="flex gap-4 text-sm">
        <span>Compute Artifact Risk: <span className={riskColor(computeArtifactRisk)}>{computeArtifactRisk ?? "unknown"}</span></span>
        <span>Semantic Loss Risk: <span className={riskColor(semanticLossRisk)}>{semanticLossRisk ?? "unknown"}</span></span>
      </div>

      {/* Dual branch view */}
      <div className="grid grid-cols-2 gap-4">
        {/* Classical Branch */}
        <div className="border rounded-lg p-4 space-y-2">
          <h4 className="font-medium">Classical Branch</h4>
          <div className="text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-500">Status</span>
              <span className={statusColor(executionWitnesses?.classical?.status || "unknown")}>
                {executionWitnesses?.classical?.status || "unknown"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Backend</span>
              <span>{executionWitnesses?.classical?.backend_id || "\u2014"}</span>
            </div>
            {classicalResult && (
              <pre className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                {JSON.stringify(classicalResult, null, 2)}
              </pre>
            )}
          </div>
        </div>

        {/* Quantum Branch */}
        <div className="border rounded-lg p-4 space-y-2">
          <h4 className="font-medium">Quantum Branch</h4>
          <div className="text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-500">Status</span>
              <span className={statusColor(executionWitnesses?.quantum?.status || "unknown")}>
                {executionWitnesses?.quantum?.status || "unknown"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Backend</span>
              <span>{executionWitnesses?.quantum?.backend_id || "\u2014"}</span>
            </div>
            {executionWitnesses?.quantum?.quantum_metadata && (
              <div className="mt-1 text-xs text-gray-500">
                <div>Provider: {executionWitnesses.quantum.quantum_metadata.provider}</div>
                <div>Shots: {executionWitnesses.quantum.quantum_metadata.shots}</div>
              </div>
            )}
            {quantumResult && (
              <pre className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                {JSON.stringify(quantumResult, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
