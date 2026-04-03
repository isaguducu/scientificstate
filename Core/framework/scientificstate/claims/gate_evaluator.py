"""
Claim Gate Evaluator — E1 / U1 / V1 / C1 / H1 gate calculations.

Source of truth: SCIENTIFIC_UI_COCKPIT_BLUEPRINT.md §5.1 + §5.2
                 Core/contracts/jsonschema/claim-lifecycle.schema.json

Gate semantics:
  Gate-E1: Claim has at least 1 traceable evidence path (min_traceable_evidence_paths ≥ 1)
  Gate-U1: Uncertainty must be present for Under Review → Provisionally Supported
  Gate-V1: Validity scope must be declared for Provisionally Supported → Endorsable
  Gate-C1: No unresolved critical contradictions for Endorsable → Endorsed (max=0)
  Gate-H1: Signed endorsement record required for Endorsed status

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
    failures: list of gate names that failed (e.g. ["E1", "H1"])
    """

    passed: bool
    gate_e1: bool
    gate_u1: bool
    gate_v1: bool
    gate_c1: bool
    gate_h1: bool
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


def evaluate_all(claim: dict) -> GateResult:
    """Evaluate all gates for a claim and return an aggregate GateResult.

    Args:
        claim: plain dict representation of a claim (from DB, daemon, or test).

    Returns:
        GateResult with passed=True only when all 5 gates pass.

    Note: In practice, not all gates are applicable to every state transition.
    The daemon applies gate checks selectively per transition. This function
    evaluates all gates and is used for full compliance audits and reporting.
    """
    e1 = gate_e1(claim)
    u1 = gate_u1(claim)
    v1 = gate_v1(claim)
    c1 = gate_c1(claim)
    h1 = gate_h1(claim)

    failures = [
        name
        for name, result in (("E1", e1), ("U1", u1), ("V1", v1), ("C1", c1), ("H1", h1))
        if not result
    ]

    return GateResult(
        passed=len(failures) == 0,
        gate_e1=e1,
        gate_u1=u1,
        gate_v1=v1,
        gate_c1=c1,
        gate_h1=h1,
        failures=failures,
    )
