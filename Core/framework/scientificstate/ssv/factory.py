"""
SSV factory — creates an SSV dict from a domain execute_method() result.

Maps domain output to SSV components:
  run_result["result"]                         → R (inference results)
  run_result["diagnostics"]["uncertainty"]      → U (P4)
  run_result["diagnostics"]["validity_scope"]   → V (P5)
  assumptions (caller-supplied)                 → A (P3)
  method_manifest (method_id + parameters)      → T (transformation chain)
  Provenance: execution_witness + timestamp

If U or V are absent, the SSV is still created but
"incomplete_flags" is populated to signal P4/P5 gaps.

Pure function: no I/O, no database, no network.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def create_ssv_from_run_result(
    run_result: dict,
    method_manifest: dict,
    assumptions: list,
) -> dict:
    """Build an SSV dict from a domain execute_method() result.

    Args:
        run_result: dict returned by DomainModule.execute_method()
                    Expected keys: "result", "diagnostics", "method_id", "domain_id"
        method_manifest: method descriptor from DomainModule.list_methods()
                         Expected keys: "method_id", "parameters" (optional)
        assumptions: list of assumption dicts (caller-supplied, satisfies P3)

    Returns:
        SSV dict compatible with scientificstate/ssv/model.py structure.
        Extra key "incomplete_flags" (list[str]) is added when P4/P5 are missing.
    """
    incomplete_flags: list[str] = []

    # ── R: inference results ──────────────────────────────────────────────
    r = {
        "quantities": run_result.get("result") or {},
        "method": method_manifest.get("method_id", ""),
        "notes": "",
    }

    # ── U: uncertainty model (P4) ─────────────────────────────────────────
    diagnostics = run_result.get("diagnostics") or {}
    raw_uncertainty = diagnostics.get("uncertainty")
    if raw_uncertainty:
        u = {
            "measurement_error": raw_uncertainty if isinstance(raw_uncertainty, dict) else {},
            "confidence_intervals": {},
            "propagation_method": "",
            "notes": str(raw_uncertainty) if not isinstance(raw_uncertainty, dict) else "",
        }
    else:
        u = {
            "measurement_error": {},
            "confidence_intervals": {},
            "propagation_method": "",
            "notes": "",
        }
        incomplete_flags.append("missing_uncertainty")

    # ── V: validity domain (P5) ───────────────────────────────────────────
    raw_validity = diagnostics.get("validity_scope")
    if raw_validity:
        conditions = (
            raw_validity if isinstance(raw_validity, list)
            else [str(raw_validity)]
        )
        v = {"conditions": conditions, "exclusions": [], "notes": ""}
    else:
        v = {"conditions": [], "exclusions": [], "notes": ""}
        incomplete_flags.append("missing_validity_scope")

    # ── A: assumptions (P3) ───────────────────────────────────────────────
    # Pass through as-is — caller is responsible for non-empty list (P3)
    a = assumptions

    # ── T: transformation chain ───────────────────────────────────────────
    t = [
        {
            "name": method_manifest.get("method_id", ""),
            "algorithm": method_manifest.get("method_id", ""),
            "parameters": method_manifest.get("parameters", {}),
            "software_version": "",
        }
    ]

    # ── P: provenance ─────────────────────────────────────────────────────
    quantum_metadata = run_result.get("quantum_metadata")
    compute_class = "quantum_sim" if quantum_metadata else "classical"

    p: dict = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "researcher_id": "",
        "software_versions": {},
        "notes": "",
        "execution_witness": {
            "compute_class": compute_class,
            "backend_id": run_result.get("domain_id", "unknown"),
        },
    }

    # Quantum metadata → embedded in provenance (Main_Source §9A.3)
    if quantum_metadata:
        p["quantum_metadata"] = quantum_metadata

    # Exploratory flag — quantum runs are automatically exploratory
    if run_result.get("exploratory"):
        p["exploratory"] = True

    # ── D + I: minimal stubs (domain fills these via data_ref) ───────────
    d = {"ref": "", "domain": run_result.get("domain_id", ""), "metadata": {}}
    i = {"instrument_id": "", "resolution": "", "mode": "", "dynamic_range": "", "extra": {}}

    ssv: dict = {
        "id": str(uuid.uuid4()),
        "version": 1,
        "parent_ssv_id": None,
        "d": d,
        "i": i,
        "a": a,
        "t": t,
        "r": r,
        "u": u,
        "v": v,
        "p": p,
    }

    if incomplete_flags:
        ssv["incomplete_flags"] = incomplete_flags

    return ssv
