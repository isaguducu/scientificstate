"""
Claim Lifecycle — 7-state enum with gate-based transition table.

Constitutional rule: scientific authority resides with the human researcher.
  - No component may transition a claim to Endorsed without an explicit
    human endorsement record.
  - Retracted is a terminal state — no further transitions allowed.
  - Retracted is only reachable from CONTESTED (per plan §2.3).

State machine (Execution_Plan_Phase0.md §2.3 + SCIENTIFIC_UI_COCKPIT_BLUEPRINT §5.1):
  Draft → Under Review
  Under Review → Provisionally Supported
  Provisionally Supported → Endorsable
  Endorsable → Endorsed
  Any non-terminal → Contested
  Contested → Endorsable (contradiction resolved + gate re-check)
  Contested → Retracted (terminal)
"""
from __future__ import annotations

from enum import Enum


class ClaimStatus(str, Enum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    PROVISIONALLY_SUPPORTED = "provisionally_supported"
    ENDORSABLE = "endorsable"
    ENDORSED = "endorsed"
    CONTESTED = "contested"
    RETRACTED = "retracted"


class ClaimTransitionError(Exception):
    """Raised when a claim transition violates the gate rules."""


# Plan-canonical transition table (Execution_Plan_Phase0.md §2.3)
VALID_TRANSITIONS: dict[ClaimStatus, list[ClaimStatus]] = {
    ClaimStatus.DRAFT: [
        ClaimStatus.UNDER_REVIEW,
        ClaimStatus.CONTESTED,
    ],
    ClaimStatus.UNDER_REVIEW: [
        ClaimStatus.PROVISIONALLY_SUPPORTED,
        ClaimStatus.CONTESTED,
    ],
    ClaimStatus.PROVISIONALLY_SUPPORTED: [
        ClaimStatus.ENDORSABLE,
        ClaimStatus.CONTESTED,
    ],
    ClaimStatus.ENDORSABLE: [
        ClaimStatus.ENDORSED,
        ClaimStatus.CONTESTED,
    ],
    ClaimStatus.ENDORSED: [
        ClaimStatus.CONTESTED,
    ],
    ClaimStatus.CONTESTED: [
        ClaimStatus.ENDORSABLE,
        ClaimStatus.RETRACTED,
    ],
    ClaimStatus.RETRACTED: [],  # Terminal
}

# Keep legacy alias for backwards compatibility with existing code
ALLOWED_TRANSITIONS: dict[ClaimStatus, frozenset[ClaimStatus]] = {
    k: frozenset(v) for k, v in VALID_TRANSITIONS.items()
}


def transition(current: ClaimStatus, target: ClaimStatus) -> ClaimStatus:
    """
    Validate and apply a claim status transition.

    Raises ClaimTransitionError if the transition violates gate rules.
    Returns the new status on success.
    """
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ClaimTransitionError(
            f"Invalid transition: {current.value!r} → {target.value!r}. "
            f"Allowed: {[s.value for s in allowed]}"
        )
    return target
