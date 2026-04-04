"""
Claim Gate Evaluator — E1 / U1 / V1 / C1 / H1 / QB / QM / REP gate calculations.

Source of truth: SCIENTIFIC_UI_COCKPIT_BLUEPRINT.md §5.1 + §5.2
                 Core/contracts/jsonschema/claim-lifecycle.schema.json

Gate semantics:
  Gate-E1:  Claim has at least 1 traceable evidence path (min_traceable_evidence_paths ≥ 1)
  Gate-U1:  Uncertainty must be present for Under Review → Provisionally Supported
  Gate-V1:  Validity scope must be declared for Provisionally Supported → Endorsable
  Gate-C1:  No unresolved critical contradictions for Endorsable → Endorsed (max=0)
  Gate-H1:  Signed endorsement record required for Endorsed status
  Gate-QB:  Quantum claims must have a classical baseline reference (M3)
  Gate-QM:  Quantum claims must include quantum_metadata for provenance
  Gate-REP: Quantum_hw/hybrid claims require confirmed institutional replication (M3-G §9A.5)

Constitutional rule: Scientific authority resides with the human researcher.
  Gate-H1 is therefore the only gate that CANNOT be computed automatically —
  it requires a human-signed endorsement record.

All gate functions are pure: no I/O, no side effects, no external dependencies.
Input: claim as plain dict (from database, daemon, or test).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GateResult:
    """Aggregate result of all gate checks for a claim.

    passed: True iff all applicable gates pass.
    gate_e1: evidence gate result
    gate_u1: uncertainty gate result
    gate_v1: validity scope gate result
    gate_c1: contradiction gate result
    gate_h1: human endorsement gate result
    gate_qb: quantum baseline gate (True if non-quantum or baseline present)
    gate_qm: quantum metadata gate (True if non-quantum or metadata present)
    gate_rep: replication gate (True if non-quantum_hw/hybrid or confirmed replication present)
    failures: list of gate names that failed (e.g. ["E1", "H1", "QB", "REP"])
    """

    passed: bool
    gate_e1: bool
    gate_u1: bool
    gate_v1: bool
    gate_c1: bool
    gate_h1: bool
    gate_qb: bool = True
    gate_qm: bool = True
    gate_rep: bool = True
    failures: list[str] = field(default_factory=list)


def gate_e1(claim: dict) -> bool:
    """Gate-E1: claim must have at least 1 traceable evidence path.

    Evidence may be provided as:
      - claim["evidence_paths"]: list of evidence references (W2 schema)
      - claim["evidence"]: legacy list field
      - claim["ssv_id"]: a direct SSV link counts as 1 evidence path

    Blueprint parameter: min_traceable_evidence_paths = 1 (M1 default)
    """
    paths = claim.get("evidence_paths") or claim.get("evidence") or []
    if isinstance(paths, list) and len(paths) >= 1:
        return True
    # A bare SSV reference counts as a single evidence path
    if claim.get("ssv_id"):
        return True
    return False


def gate_u1(claim: dict) -> bool:
    """Gate-U1: uncertainty must be present for Under Review → Provisionally Supported.

    Checks that the claim references an SSV whose uncertainty component (U) is
    non-trivial. In the gate model, this means the claim dict carries an
    "uncertainty_present" flag (set by the daemon after SSV validation) OR
    references an ssv with a populated uncertainty model.

    Blueprint parameter: require_uncertainty_for_under_review_plus = true
    """
    # Explicit flag from daemon / SSV resolution layer
    if claim.get("uncertainty_present") is True:
        return True
    # Inline uncertainty data (partial SSV embedded in claim)
    u = claim.get("uncertainty") or claim.get("u")
    if isinstance(u, dict):
        return bool(
            u.get("measurement_error")
            or u.get("measurement_uncertainty")
            or u.get("propagated_uncertainty")
            or u.get("confidence_intervals")
            or u.get("reason_if_unquantifiable")
        )
    return False


def gate_v1(claim: dict) -> bool:
    """Gate-V1: validity scope must be declared for Provisionally Supported → Endorsable.

    Checks that the claim carries a validity domain declaration — either inline
    or via the daemon's "validity_scope_present" flag.

    Blueprint parameter: require_validity_scope_for_provisional_plus = true
    """
    if claim.get("validity_scope_present") is True:
        return True
    v = claim.get("validity_domain") or claim.get("v")
    if isinstance(v, dict):
        return bool(
            v.get("conditions")
            or v.get("model_breakdown_conditions")
            or v.get("status")
        )
    return False


def gate_c1(claim: dict) -> bool:
    """Gate-C1: no unresolved critical contradictions for Endorsable → Endorsed.

    Counts the number of contradictions with severity == "critical" and
    resolution_status != "resolved".

    Blueprint parameter: max_unresolved_critical_contradictions_for_endorsement = 0
    """
    contradictions = claim.get("contradictions") or []
    if not isinstance(contradictions, list):
        return True  # No contradiction data → assume no unresolved criticals
    unresolved_critical = sum(
        1
        for c in contradictions
        if isinstance(c, dict)
        and c.get("severity") == "critical"
        and c.get("resolution_status") != "resolved"
    )
    return unresolved_critical == 0


def gate_h1(claim: dict) -> bool:
    """Gate-H1: signed endorsement record required for Endorsed status.

    Constitutional rule: this gate CANNOT be satisfied by computation alone.
    A human researcher must provide a signed endorsement. The daemon verifies
    the signature and sets "endorsement_record" on the claim.

    Exploratory hard block (Main_Source §9A.3):
    Claims marked exploratory=True unconditionally fail H1.
    Quantum simulation results cannot enter the endorsable path
    without a classical baseline reference.

    Blueprint parameter: require_signed_endorsement_for_endorsed = true
    """
    # Exploratory claims are hard-blocked from endorsement
    if claim.get("exploratory") is True:
        return False

    record = claim.get("endorsement_record")
    if not isinstance(record, dict):
        return False
    # Record must have a non-empty endorser_id and signature
    return bool(record.get("endorser_id")) and bool(record.get("signature"))


# ── Quantum-specific gate rules (Main_Source §9A.3, §M3) ─────────────────────

_QUANTUM_COMPUTE_CLASSES = {"quantum_sim", "quantum_hw", "hybrid"}


def is_quantum_claim(claim: dict) -> bool:
    """Check if a claim originates from a quantum or hybrid computation."""
    cc = claim.get("compute_class", "")
    if cc in _QUANTUM_COMPUTE_CLASSES:
        return True
    # Check nested provenance
    p = claim.get("p") or claim.get("provenance") or {}
    ew = p.get("execution_witness") or {}
    return ew.get("compute_class", "") in _QUANTUM_COMPUTE_CLASSES


def gate_quantum_baseline(claim: dict) -> bool:
    """Quantum claims MUST have a classical baseline reference (M3 hard rule).

    Without a classical baseline, quantum results cannot be compared or
    validated. This gate returns True for non-quantum claims (not applicable).

    The classical_baseline_ref field must contain a reference to a classical
    SSV that covers the same method and dataset.
    """
    if not is_quantum_claim(claim):
        return True  # Not applicable to non-quantum claims
    ref = claim.get("classical_baseline_ref") or claim.get("classical_baseline_ssv_id")
    return bool(ref)


def gate_quantum_metadata(claim: dict) -> bool:
    """Quantum claims MUST include quantum_metadata for provenance.

    Required fields: at least shots and one of backend_name/simulator/provider.
    Returns True for non-quantum claims (not applicable).
    """
    if not is_quantum_claim(claim):
        return True  # Not applicable to non-quantum claims
    qm = claim.get("quantum_metadata")
    if not qm:
        # Check nested in provenance
        p = claim.get("p") or claim.get("provenance") or {}
        qm = p.get("quantum_metadata")
    if not isinstance(qm, dict):
        return False
    has_shots = "shots" in qm
    has_backend = bool(
        qm.get("backend_name") or qm.get("simulator") or qm.get("provider")
    )
    return has_shots and has_backend


def gate_replication(claim: dict) -> bool:
    """Gate-REP: Quantum/hybrid claims require confirmed institutional replication.

    Main_Source §9A.5 M3-G: quantum_hw and hybrid claims must have at least
    one confirmed independent replication before endorsement.
    Classical and quantum_sim claims pass automatically.
    """
    compute_class = claim.get("compute_class", "classical")
    if compute_class not in ("quantum_hw", "hybrid"):
        return True
    replications = claim.get("replications", [])
    confirmed = [r for r in replications if r.get("status") == "confirmed"]
    return len(confirmed) >= 1


def evaluate_all(claim: dict) -> GateResult:
    """Evaluate all gates for a claim and return an aggregate GateResult.

    Args:
        claim: plain dict representation of a claim (from DB, daemon, or test).

    Returns:
        GateResult with passed=True only when all gates pass.

    Note: In practice, not all gates are applicable to every state transition.
    The daemon applies gate checks selectively per transition. This function
    evaluates all gates and is used for full compliance audits and reporting.

    Quantum-specific gates (QB, QM) are evaluated for all claims but only
    fail for quantum/hybrid compute classes. Non-quantum claims pass these
    gates automatically.
    """
    e1 = gate_e1(claim)
    u1 = gate_u1(claim)
    v1 = gate_v1(claim)
    c1 = gate_c1(claim)
    h1 = gate_h1(claim)
    qb = gate_quantum_baseline(claim)
    qm = gate_quantum_metadata(claim)
    rep = gate_replication(claim)

    failures = [
        name
        for name, result in (
            ("E1", e1), ("U1", u1), ("V1", v1), ("C1", c1), ("H1", h1),
            ("QB", qb), ("QM", qm), ("REP", rep),
        )
        if not result
    ]

    return GateResult(
        passed=len(failures) == 0,
        gate_e1=e1,
        gate_u1=u1,
        gate_v1=v1,
        gate_c1=c1,
        gate_h1=h1,
        gate_qb=qb,
        gate_qm=qm,
        gate_rep=rep,
        failures=failures,
    )


# ── Classical baseline validation helpers (Phase 7 — M2 additive) ──────────


def validate_classical_baseline_exists(
    classical_baseline_ref: str | None,
    ssv_store: dict | None = None,
) -> tuple[bool, str]:
    """Validate that a classical baseline SSV exists and is classical compute.

    Args:
        classical_baseline_ref: SSV id of the classical baseline run.
        ssv_store: optional dict mapping ssv_id -> ssv dict for lookup.

    Returns:
        (is_valid, reason) tuple. is_valid is True when the ref is present and
        (if ssv_store is provided) points to a classical compute SSV.
    """
    if not classical_baseline_ref:
        return False, "No classical_baseline_ref provided"

    if ssv_store is None:
        # Without a store we can only confirm the ref is non-empty
        return True, "classical_baseline_ref present (store not available for verification)"

    ssv = ssv_store.get(classical_baseline_ref)
    if ssv is None:
        return False, f"Classical baseline SSV not found: {classical_baseline_ref}"

    # Check compute_class is classical
    p = ssv.get("p") or ssv.get("provenance") or {}
    ew = p.get("execution_witness") or {}
    cc = ew.get("compute_class", ssv.get("compute_class", "classical"))
    if cc != "classical":
        return False, f"Baseline SSV compute_class is '{cc}', expected 'classical'"

    return True, "Classical baseline SSV verified"


def enrich_quantum_claim_provenance(
    claim: dict,
    quantum_result: dict,
    classical_baseline_ref: str | None,
) -> dict:
    """Enrich a claim dict with quantum execution witness provenance.

    Creates a new dict (does not mutate the input). Adds execution_witness
    and quantum_metadata from the quantum backend result into the claim's
    provenance structure.

    Args:
        claim: original claim dict.
        quantum_result: result dict from QuantumSimBackend.execute().
        classical_baseline_ref: SSV id of the classical baseline, if any.

    Returns:
        New claim dict with enriched provenance.
    """
    enriched = {**claim}

    # Extract execution_witness from quantum_result
    ew = quantum_result.get("execution_witness") or {}
    qm = ew.get("quantum_metadata") or quantum_result.get("quantum_metadata") or {}

    enriched["compute_class"] = quantum_result.get("compute_class", "quantum_sim")
    enriched["exploratory"] = quantum_result.get("exploratory", True)

    # Set quantum_metadata at claim level for gate_quantum_metadata check
    enriched["quantum_metadata"] = qm

    # Set classical baseline ref for gate_quantum_baseline check
    if classical_baseline_ref:
        enriched["classical_baseline_ref"] = classical_baseline_ref

    # Set provenance with execution_witness
    provenance = dict(enriched.get("p") or enriched.get("provenance") or {})
    provenance["execution_witness"] = ew
    enriched["p"] = provenance

    return enriched
