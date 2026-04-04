"""
Replication Protocol — rules for when replication is required.

Main_Source §9A.5 M3-G: Quantum/hybrid claims require at least one
confirmed independent institutional replication before endorsement.

Classical claims do not require institutional replication for endorsement,
though it is encouraged.
"""
from __future__ import annotations


_REPLICATION_REQUIRED_COMPUTE_CLASSES = {"quantum_hw", "hybrid"}


def is_replication_required(claim: dict, run: dict | None = None) -> bool:
    """Check if a claim requires independent institutional replication.

    Quantum hardware and hybrid claims require replication.
    Classical and quantum_sim claims do not (though sim is exploratory anyway).

    Args:
        claim: Claim dict (may contain compute_class).
        run: Optional run result dict (may contain compute_class).

    Returns:
        True if replication is required for endorsement.
    """
    cc = claim.get("compute_class", "")
    if cc in _REPLICATION_REQUIRED_COMPUTE_CLASSES:
        return True
    if run:
        cc = run.get("compute_class", "")
        if cc in _REPLICATION_REQUIRED_COMPUTE_CLASSES:
            return True
    return False


def validate_replication_for_endorsement(
    claim: dict,
    replications: list[dict] | None = None,
    replication_history: list[dict] | None = None,
) -> dict:
    """Validate whether a claim has sufficient replication for endorsement.

    SYNC interface — no aiosqlite.

    Args:
        claim: Claim dict with compute_class.
        replications: List of replication result dicts (legacy in-memory path).
        replication_history: list[dict] with {request_id, status,
            source_institution_id, target_institution_id}.
            Daemon queries DB and passes results here.

    Returns:
        Dict with "endorsable" (bool) and "reason" (str).
    """
    if not is_replication_required(claim):
        return {
            "endorsable": True,
            "reason": "Replication not required for this compute class.",
        }

    # Prefer replication_history (DB-backed institutional path)
    if replication_history:
        valid_confirmed = [
            r for r in replication_history
            if r.get("status") == "confirmed"
            and r.get("source_institution_id") != r.get("target_institution_id")
        ]
        if len(valid_confirmed) >= 1:
            return {
                "endorsable": True,
                "reason": f"{len(valid_confirmed)} confirmed institutional replication(s).",
            }
        return {
            "endorsable": False,
            "reason": "quantum/hybrid claim requires \u22651 confirmed cross-institutional replication",
        }

    # Fallback to existing in-memory check behavior
    reps = replications or []

    confirmed = [
        r for r in reps
        if r.get("status") == "confirmed"
    ]

    if len(confirmed) >= 1:
        return {
            "endorsable": True,
            "reason": f"Replication confirmed by {len(confirmed)} institution(s).",
        }

    partially = [
        r for r in reps
        if r.get("status") == "partially_confirmed"
    ]

    if partially and not confirmed:
        return {
            "endorsable": False,
            "reason": (
                f"{len(partially)} partial replication(s) found, "
                "but at least 1 confirmed replication is required."
            ),
        }

    return {
        "endorsable": False,
        "reason": "No confirmed institutional replication. At least 1 required for quantum_hw/hybrid claims.",
    }
