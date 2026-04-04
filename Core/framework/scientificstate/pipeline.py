"""
Pipeline coordinator — E2E scientific state pipeline.

Orchestrates: domain execution → SSV creation → claim creation → gate evaluation.

Constitutional rules enforced here:
  - No component may assert scientific validity on its own.
  - Gates start at False; human researcher advances them.
  - Pipeline is pure: no I/O, no database writes, no network calls.

Dependency graph (read-only imports from P0 + Phase A siblings):
  DomainModule.execute_method()  →  ssv/factory.py
  ssv/factory.py                 →  claims/factory.py
  claims/factory.py              →  claims/gate_evaluator.py
"""
from __future__ import annotations

from dataclasses import dataclass, field

from scientificstate.claims.factory import create_claim_from_ssv
from scientificstate.claims.gate_evaluator import GateResult, evaluate_all
from scientificstate.runs.model import ComputeRun
from scientificstate.ssv.factory import create_ssv_from_run_result


@dataclass
class PipelineResult:
    """Complete result of a single pipeline execution.

    run: ComputeRun record (Pydantic model, serializable)
    ssv: SSV as plain dict (from ssv/factory.py)
    claim: Claim dict in DRAFT state (from claims/factory.py)
    gate_result: GateResult dataclass (from gate_evaluator.py)
    incomplete_flags: P4/P5 gaps flagged by ssv/factory.py (empty = fully complete)
    """

    run: ComputeRun
    ssv: dict
    claim: dict
    gate_result: GateResult
    incomplete_flags: list[str] = field(default_factory=list)


def execute_pipeline(
    domain,
    method_id: str,
    assumptions: list,
    dataset_ref: str | None,
    workspace_id: str,
    parameters: dict | None = None,
) -> PipelineResult:
    """Execute the full scientific state pipeline.

    Pure coordination function — no I/O, no DB, no file system access.

    Args:
        domain: DomainModule instance (must implement execute_method + list_methods)
        method_id: identifier of the method to invoke on the domain
        assumptions: list of assumption dicts (P3 — caller must provide non-empty list)
        dataset_ref: optional file path or URI to input dataset
        workspace_id: owning workspace identifier
        parameters: user-provided method parameters (merged with manifest defaults)

    Returns:
        PipelineResult containing run, ssv, claim, gate_result, incomplete_flags.

    Raises:
        ValueError: if domain.execute_method() returns a non-dict or error status.
    """
    # ── Step 1: resolve method manifest ───────────────────────────────────
    manifests = {m["method_id"]: m for m in domain.list_methods()}
    method_manifest = manifests.get(method_id, {"method_id": method_id, "parameters": {}})

    # ── Step 2: execute domain method ─────────────────────────────────────
    # Merge manifest defaults with user-provided parameters (user wins)
    merged_params = {**method_manifest.get("parameters", {}), **(parameters or {})}

    # If a backend already executed (quantum/hybrid), use its result directly
    # instead of re-running through the domain. The daemon injects
    # _backend_result when compute_class != "classical".
    backend_result = merged_params.pop("_backend_result", None)
    compute_class = merged_params.pop("_compute_class", "classical")

    if backend_result is not None and isinstance(backend_result, dict):
        raw_result = backend_result
    else:
        raw_result = domain.execute_method(
            method_id=method_id,
            data_ref=dataset_ref or "",
            assumptions=assumptions,
            params=merged_params,
        )

    # ── Step 3: build a ComputeRun record ─────────────────────────────────
    run = ComputeRun(
        workspace_id=workspace_id,
        domain_id=domain.domain_id,
        method_id=method_id,
    )
    if isinstance(raw_result, dict) and raw_result.get("status") not in ("error",):
        run = run.mark_running().mark_succeeded(result_ref="pipeline-inline")
    else:
        run = run.mark_running().mark_failed()

    # ── Step 4: create SSV from run result ────────────────────────────────
    ssv = create_ssv_from_run_result(
        run_result=raw_result if isinstance(raw_result, dict) else {},
        method_manifest=method_manifest,
        assumptions=assumptions,
    )
    incomplete_flags: list[str] = ssv.pop("incomplete_flags", [])

    # ── Step 5: create draft claim ────────────────────────────────────────
    claim = create_claim_from_ssv(ssv=ssv, question_ref=method_id)

    # ── Step 5b: quantum provenance + exploratory hard block (Main_Source §9A.3) ─
    # Propagate compute_class and quantum_metadata to the claim so that
    # gate_quantum_baseline (QB) and gate_quantum_metadata (QM) can fire.
    if compute_class != "classical":
        claim["compute_class"] = compute_class
    if isinstance(raw_result, dict):
        qm = raw_result.get("quantum_metadata")
        if qm:
            claim["quantum_metadata"] = qm
        cbr = raw_result.get("classical_baseline_ref") or raw_result.get("classical_baseline_ssv_id")
        if cbr:
            claim["classical_baseline_ref"] = cbr

    # Quantum simulation runs are automatically exploratory.
    # Exploratory claims CANNOT enter the endorsable path:
    #   - H1 gate is unconditionally blocked
    #   - Claim status stays at DRAFT (cannot reach endorsable)
    #   - Classical baseline ref required for endorsement
    is_exploratory = raw_result.get("exploratory", False) if isinstance(raw_result, dict) else False
    if is_exploratory:
        claim["exploratory"] = True
        claim["exploratory_reason"] = (
            "Quantum simulation — requires classical baseline for endorsement"
        )

    # ── Step 6: evaluate gates ────────────────────────────────────────────
    gate_result = evaluate_all(claim)

    return PipelineResult(
        run=run,
        ssv=ssv,
        claim=claim,
        gate_result=gate_result,
        incomplete_flags=incomplete_flags,
    )
