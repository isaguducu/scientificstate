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
    replications: list[dict],
) -> dict:
    """Validate whether a claim has sufficient replication for endorsement.

    Args:
        claim: Claim dict with compute_class.
        replications: List of replication result dicts.

    Returns:
        Dict with "endorsable" (bool) and "reason" (str).
    """
    if not is_replication_required(claim):
        return {
            "endorsable": True,
            "reason": "Replication not required for this compute class.",
        }

    confirmed = [
        r for r in replications
        if r.get("status") == "confirmed"
    ]

    if len(confirmed) >= 1:
        return {
            "endorsable": True,
            "reason": f"Replication confirmed by {len(confirmed)} institution(s).",
        }

    partially = [
        r for r in replications
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
