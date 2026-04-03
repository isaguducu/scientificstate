"""
Scientific State Vector (SSV) — SSV = (D, I, A, T, R, U, V, P)

An SSV is an immutable, atomic representation of a complete scientific state.
Any modification to any component produces a new SSV; the original is unchanged.

Phase 0 plan skeleton (Execution_Plan_Phase0.md §2.3):
    @dataclass
    class SSV:
        id: str
        version: int
        d, i, a, t, r, u, v, p: ...
        parent_ssv_id: str | None = None

Constitutional rule: No component may assert scientific validity on its own.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class RawData:
    """
    D — Raw observational data.

    The unmodified primary instrumental record.
    Must be preserved as-is; never transformed or deleted.
    """
    ref: str = ""          # Stable reference/URI to raw data in custody layer
    domain: str = ""       # e.g. "polymer", "genomics", "climate"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InstrumentConfig:
    """
    I — Instrument and measurement configuration.

    Captures the instrumental context required for uncertainty quantification.
    """
    instrument_id: str = ""
    resolution: str = ""
    mode: str = ""
    dynamic_range: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Assumptions:
    """
    A — Explicit scientific assumptions.

    P3 constitutional rule: assumptions must not be empty for a complete SSV.
    Every inference depends on assumptions. If undocumented, validity is unassessable.
    """
    background_model: str = ""
    signal_model: str = ""
    domain_constraints: list[str] = field(default_factory=list)
    confounds: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TransformStep:
    """Single step in transformation chain T."""
    name: str = ""
    algorithm: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    software_version: str = ""


@dataclass(frozen=True)
class InferenceResult:
    """
    R — Inference results.

    Derived scientific quantities. Non-authoritative; human researcher governs claims.
    """
    quantities: dict[str, Any] = field(default_factory=dict)
    method: str = ""
    notes: str = ""


@dataclass(frozen=True)
class UncertaintyModel:
    """
    U — Uncertainty model (P4 — constitutionally required).

    Measurement error, propagated uncertainties, confidence intervals.
    """
    measurement_error: dict[str, Any] = field(default_factory=dict)
    confidence_intervals: dict[str, Any] = field(default_factory=dict)
    propagation_method: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ValidityDomain:
    """
    V — Validity domain (P5 — constitutionally required).

    Conditions under which R remains scientifically defensible.
    Without this, no claim boundary can be established.
    """
    conditions: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class Provenance:
    """
    P — Provenance + execution_witness.

    Timestamp, researcher identity, software versions.
    Immutable audit trail — cannot be altered after creation.

    Note: parent_ssv_id is a top-level SSV field (per plan §2.3), not nested here.
    """
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    researcher_id: str = ""
    software_versions: dict[str, str] = field(default_factory=dict)
    notes: str = ""


@dataclass(frozen=True)
class SSV:
    """
    Scientific State Vector — SSV = (D, I, A, T, R, U, V, P)

    Immutable. Atomic. Complete only when all 8 components are formally present.
    Any modification produces a new SSV; the original is unchanged.

    Plan skeleton (Execution_Plan_Phase0.md §2.3):
        id: str
        version: int          ← SSV lineage version counter
        d, i, a, t, r, u, v, p: component fields
        parent_ssv_id: str | None  ← direct parent link

    Constitutional constraint: scientific authority resides with the human researcher.
    This object is evidence — not a claim, not a verdict.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    parent_ssv_id: str | None = None
    d: RawData = field(default_factory=RawData)
    i: InstrumentConfig = field(default_factory=InstrumentConfig)
    a: Assumptions = field(default_factory=Assumptions)
    t: list[TransformStep] = field(default_factory=list)
    r: InferenceResult = field(default_factory=InferenceResult)
    u: UncertaintyModel = field(default_factory=UncertaintyModel)
    v: ValidityDomain = field(default_factory=ValidityDomain)
    p: Provenance = field(default_factory=Provenance)

    @property
    def is_complete(self) -> bool:
        """
        An SSV is complete iff all constitutionally required components are non-empty:
          - D: raw data ref present
          - I: instrument id present
          - A: at least one assumption documented (P3)
          - R: results present
          - U: uncertainty present (P4)
          - V: validity conditions present (P5)
        """
        return (
            bool(self.d.ref)
            and bool(self.i.instrument_id)
            and bool(
                self.a.background_model
                or self.a.signal_model
                or self.a.domain_constraints
            )
            and bool(self.r.quantities)
            and bool(
                self.u.measurement_error
                or self.u.confidence_intervals
            )
            and bool(self.v.conditions)
        )

    def derive(self, **overrides: Any) -> "SSV":
        """
        Produce a new SSV derived from this one.

        The new SSV:
          - gets a fresh id
          - version = self.version + 1
          - parent_ssv_id = self.id

        The original SSV is not modified.
        """
        return SSV(
            version=self.version + 1,
            parent_ssv_id=self.id,
            d=overrides.get("d", self.d),
            i=overrides.get("i", self.i),
            a=overrides.get("a", self.a),
            t=overrides.get("t", self.t),
            r=overrides.get("r", self.r),
            u=overrides.get("u", self.u),
            v=overrides.get("v", self.v),
            p=overrides.get("p", Provenance(
                researcher_id=self.p.researcher_id,
                software_versions=self.p.software_versions,
            )),
        )
