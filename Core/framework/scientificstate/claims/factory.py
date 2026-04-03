"""
Claim factory — creates a draft claim from an SSV.

Constitutional rule: the framework creates claims in DRAFT state only.
Scientific validity authority resides with the human researcher.
No gate may be pre-set to True by the framework — all gates start False.

Pure function: no I/O, no database, no network.
"""
from __future__ import annotations

import uuid

from scientificstate.claims.lifecycle import ClaimStatus


def create_claim_from_ssv(ssv: dict, question_ref: str) -> dict:
    """Create an initial DRAFT claim linked to an SSV.

    Args:
        ssv: SSV dict (from ssv/factory.py or ssv/model.py)
        question_ref: the scientific question or hypothesis this claim addresses

    Returns:
        Claim dict in DRAFT state with all gate fields set to False.
        Compatible with claims/lifecycle.py and claims/gate_evaluator.py.
    """
    return {
        "claim_id": str(uuid.uuid4()),
        "status": ClaimStatus.DRAFT.value,
        "ssv_id": ssv.get("id"),
        "question_ref": question_ref,
        # Gate fields — all False at creation (human researcher advances gates)
        "gate_e1": False,
        "gate_u1": False,
        "gate_v1": False,
        "gate_c1": False,
        "gate_h1": False,
        # Lifecycle metadata
        "evidence_paths": [],        # Gate-E1: no evidence yet
        "contradictions": [],        # Gate-C1: no contradictions yet
        "endorsement_record": None,  # Gate-H1: no endorsement yet
        "uncertainty_present": False,
        "validity_scope_present": False,
        "previous_status": None,
        "transitioned_at": None,
        "transition_reason": None,
    }
