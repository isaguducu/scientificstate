"""
Hybrid orchestrator — parallel classical + quantum branch execution.

Main_Source §9A.3: Any run containing a quantum branch is automatically
exploratory. The hybrid orchestrator runs both branches and aggregates
their execution witnesses separately.

Constitutional constraint (P7): The orchestrator performs computation only.
It does not assert scientific claims or validity.
"""
from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

logger = logging.getLogger("scientificstate.daemon.hybrid.orchestrator")


def execute_hybrid(
    classical_fn: Any,
    quantum_fn: Any,
    method_id: str,
    dataset_ref: str,
    assumptions: list,
    params: dict,
) -> dict:
    """
    Execute classical and quantum branches in parallel and aggregate results.

    Args:
        classical_fn: Callable that executes the classical branch.
                      Signature: (method_id, dataset_ref, assumptions, params) -> dict
        quantum_fn: Callable that executes the quantum branch.
                    Signature: (method_id, dataset_ref, assumptions, params) -> dict
        method_id: Domain method identifier.
        dataset_ref: Dataset reference.
        assumptions: Scientific assumptions (P3).
        params: Method-specific parameters.

    Returns:
        Aggregated result dict with both branch witnesses.
        Always sets exploratory=True (quantum content present).
    """
    hybrid_id = str(uuid.uuid4())[:8]
    branches: dict[str, dict] = {}
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(
                classical_fn, method_id, dataset_ref, assumptions, params
            ): "classical",
            executor.submit(
                quantum_fn, method_id, dataset_ref, assumptions, params
            ): "quantum",
        }

        for future in as_completed(futures):
            branch_name = futures[future]
            try:
                result = future.result()
                branches[branch_name] = result
                logger.info(
                    "Hybrid %s: branch '%s' completed (status=%s)",
                    hybrid_id, branch_name, result.get("status", "unknown"),
                )
            except Exception as exc:
                errors[branch_name] = str(exc)
                logger.error(
                    "Hybrid %s: branch '%s' failed: %s",
                    hybrid_id, branch_name, exc,
                )

    # Determine overall status
    if not branches:
        return {
            "status": "error",
            "error_code": "HYBRID_ALL_BRANCHES_FAILED",
            "error": f"All branches failed: {errors}",
            "compute_class": "hybrid",
            "exploratory": True,
        }

    overall_status = "ok"
    if errors:
        overall_status = "partial"

    # Build aggregated result
    classical_result = branches.get("classical", {})
    quantum_result = branches.get("quantum", {})

    # Merge counts from quantum branch (primary quantum output)
    counts = quantum_result.get("counts", {})

    # Build per-branch execution witnesses
    execution_witnesses = {}
    if "classical" in branches:
        execution_witnesses["classical"] = {
            "compute_class": "classical",
            "backend_id": classical_result.get("domain_id", "classical"),
            "status": classical_result.get("status", "unknown"),
            "result_summary": _summarize_result(classical_result),
        }
    if "quantum" in branches:
        execution_witnesses["quantum"] = {
            "compute_class": quantum_result.get("compute_class", "quantum_sim"),
            "backend_id": quantum_result.get("quantum_metadata", {}).get(
                "backend_name", "unknown"
            ),
            "status": quantum_result.get("status", "unknown"),
            "quantum_metadata": quantum_result.get("quantum_metadata", {}),
        }

    if errors:
        for branch_name, err in errors.items():
            execution_witnesses[branch_name] = {
                "status": "error",
                "error": err,
            }

    # --- Phase 8 W2: timing + risk assessment ---
    # NOTE: ThreadPoolExecutor above does not capture per-branch timing.
    # We approximate parallel_execution_time_ms from wall-clock span.
    classical_time_ms = classical_result.get("execution_time_ms", 0)
    quantum_time_ms = quantum_result.get("execution_time_ms", 0)

    result = {
        "status": overall_status,
        "compute_class": "hybrid",
        "counts": counts,
        "classical_result": classical_result.get("result", {}),
        "quantum_result": quantum_result.get("result", quantum_result.get("counts", {})),
        "quantum_metadata": quantum_result.get("quantum_metadata", {}),
        "execution_witnesses": execution_witnesses,
        "exploratory": True,  # M3 hard rule: quantum content → exploratory
        "branch_errors": errors if errors else None,
        "compute_artifact_risk": _assess_compute_artifact_risk(quantum_result),
        "semantic_loss_risk": _assess_semantic_loss_risk(classical_result, quantum_result),
        "parallel_execution_time_ms": max(classical_time_ms, quantum_time_ms),
        "branch_count": 2,
    }

    return result


def _assess_compute_artifact_risk(quantum_result: dict) -> str:
    """Assess risk of hardware/transpiler artifacts in quantum result."""
    if quantum_result.get("fallback"):
        return "low"
    qm = quantum_result.get("quantum_metadata", {})
    if not qm:
        qm = quantum_result.get("execution_witness", {}).get("quantum_metadata", {})
    depth = qm.get("circuit_depth", 0)
    qubits = qm.get("qubit_count", 0)
    if depth > 100 or qubits > 20:
        return "high"
    if depth > 50 or qubits > 10:
        return "medium"
    return "low"


def _assess_semantic_loss_risk(classical_result: dict, quantum_result: dict) -> str:
    """Assess risk of meaning loss during classical->quantum translation."""
    if quantum_result.get("status") in ("failed", "error"):
        return "high"
    if quantum_result.get("fallback"):
        return "low"
    return "medium"


def _summarize_result(result: dict) -> dict:
    """Extract a brief summary from a branch result for the witness."""
    r = result.get("result", {})
    if isinstance(r, dict):
        return {k: v for k, v in r.items() if not isinstance(v, (list, dict))}
    return {}
