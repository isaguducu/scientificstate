"""
SSV Completeness Validator — P3 / P4 / P5 gate checks.

Constitutional principles enforced here:
  P3: Assumptions (A) must not be empty — every inference depends on assumptions.
  P4: Uncertainty model (U) is mandatory — without it, validity is unassessable.
  P5: Validity domain (V) is mandatory — without it, no claim boundary exists.

This module contains only pure functions with no side effects.
Input: SSV as a plain dict (as produced by SSV.dict() or received from daemon).
Output: ValidationResult dataclass.

The validator is intentionally domain-agnostic — it checks structural completeness
only. Domain-specific semantic validation belongs in the domain module itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ValidationResult:
    """Result of an SSV completeness check.

    passed: True iff all P3/P4/P5 requirements are satisfied.
    missing_fields: list of human-readable field paths that failed the check.
                    Empty when passed=True.
    """

    passed: bool
    missing_fields: list[str] = field(default_factory=list)


def validate_ssv(ssv: dict) -> ValidationResult:
    """Check P3/P4/P5 completeness of an SSV dict.

    Args:
        ssv: plain dict representation of an SSV (from SSV.dict() or JSON).

    Returns:
        ValidationResult with passed=True only when all checks pass.
    """
    missing: list[str] = []

    # ── Top-level required fields ─────────────────────────────────────────
    for top_field in ("id", "version", "d", "i", "a", "t", "r", "u", "v", "p"):
        if top_field not in ssv:
            missing.append(top_field)

    # ── D: raw data reference ─────────────────────────────────────────────
    d = ssv.get("d") or {}
    if not d.get("ref") and not d.get("raw_data_id"):
        missing.append("d.ref")

    # ── I: instrument config ──────────────────────────────────────────────
    i = ssv.get("i") or {}
    if not i.get("instrument_id"):
        missing.append("i.instrument_id")

    # ── A: assumptions (P3) — must be non-empty ──────────────────────────
    a = ssv.get("a")
    if a is None:
        missing.append("a")
    elif isinstance(a, list):
        if len(a) == 0:
            missing.append("a (P3: assumptions list must not be empty)")
    elif isinstance(a, dict):
        # Legacy dict-style assumption — check at least one substantive field
        if not any(a.get(k) for k in ("background_model", "signal_model", "domain_constraints")):
            missing.append("a (P3: no substantive assumption documented)")

    # ── R: inference results ──────────────────────────────────────────────
    r = ssv.get("r") or {}
    if isinstance(r, dict):
        quantities = r.get("quantities")
        if not quantities:
            missing.append("r.quantities")
    else:
        missing.append("r.quantities")

    # ── U: uncertainty model (P4) — mandatory ────────────────────────────
    u = ssv.get("u")
    if u is None:
        missing.append("u (P4: uncertainty model is mandatory)")
    elif isinstance(u, dict):
        # P4 requires either quantified uncertainty OR an explicit reason
        has_quantified = any(
            u.get(k)
            for k in ("measurement_error", "confidence_intervals", "measurement_uncertainty", "propagated_uncertainty")
        )
        has_reason = u.get("reason_if_unquantifiable") or u.get("status") == "unquantifiable_with_reason"
        if not has_quantified and not has_reason:
            missing.append("u (P4: neither quantified uncertainty nor reason_if_unquantifiable present)")

    # ── V: validity domain (P5) — mandatory ──────────────────────────────
    v = ssv.get("v")
    if v is None:
        missing.append("v (P5: validity domain is mandatory)")
    elif isinstance(v, dict):
        # P5 requires either explicit conditions or a declared status
        has_conditions = bool(v.get("conditions") or v.get("model_breakdown_conditions"))
        has_status = bool(v.get("status"))
        if not has_conditions and not has_status:
            missing.append("v (P5: validity domain has no conditions or status declared)")

    return ValidationResult(passed=len(missing) == 0, missing_fields=missing)
