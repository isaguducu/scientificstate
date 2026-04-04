"""
Tests for quantum–classical baseline gate interaction — Phase 7 M2.

Covers: quantum claim with baseline passes, without baseline fails,
classical auto-passes, hybrid needs baseline, validate_classical_baseline_exists,
enrich_quantum_claim_provenance, and quantum eligibility module.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FRAMEWORK = str(Path(__file__).resolve().parents[1])
if _FRAMEWORK not in sys.path:
    sys.path.insert(0, _FRAMEWORK)

from scientificstate.claims.gate_evaluator import (  # noqa: E402
    evaluate_all,
    gate_quantum_baseline,
    gate_quantum_metadata,
    is_quantum_claim,
    validate_classical_baseline_exists,
    enrich_quantum_claim_provenance,
)
from scientificstate.modules.quantum_eligibility import (  # noqa: E402
    assess_quantum_eligibility,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _base_claim(**overrides) -> dict:
    """Minimal valid claim for gate evaluation."""
    claim = {
        "evidence_paths": ["ev-1"],
        "uncertainty_present": True,
        "validity_scope_present": True,
        "contradictions": [],
    }
    claim.update(overrides)
    return claim


def _quantum_claim(**overrides) -> dict:
    """Quantum-sim claim with metadata but no baseline or endorsement."""
    claim = _base_claim(
        compute_class="quantum_sim",
        quantum_metadata={
            "shots": 1024,
            "simulator": "mock_fallback",
        },
        exploratory=True,
    )
    claim.update(overrides)
    return claim


def _quantum_result() -> dict:
    """Mock QuantumSimBackend result dict."""
    return {
        "run_id": "r-001",
        "status": "succeeded",
        "compute_class": "quantum_sim",
        "counts": {"00": 512, "11": 512},
        "statevector": None,
        "execution_witness": {
            "compute_class": "quantum_sim",
            "backend_id": "mock_fallback",
            "quantum_metadata": {
                "shots": 1024,
                "noise_model": None,
                "simulator": "mock_fallback",
                "circuit_depth": 0,
                "qubit_count": 2,
            },
        },
        "exploratory": True,
    }


# ---------------------------------------------------------------------------
# Gate-QB: quantum baseline tests
# ---------------------------------------------------------------------------


class TestQuantumBaselineGate:
    def test_quantum_with_baseline_passes(self):
        claim = _quantum_claim(classical_baseline_ref="ssv-classical-001")
        assert gate_quantum_baseline(claim) is True

    def test_quantum_without_baseline_fails(self):
        claim = _quantum_claim()
        assert gate_quantum_baseline(claim) is False

    def test_classical_auto_passes(self):
        claim = _base_claim(compute_class="classical")
        assert gate_quantum_baseline(claim) is True

    def test_hybrid_needs_baseline(self):
        claim = _base_claim(
            compute_class="hybrid",
            quantum_metadata={"shots": 100, "simulator": "mock"},
        )
        assert gate_quantum_baseline(claim) is False

    def test_hybrid_with_baseline_passes(self):
        claim = _base_claim(
            compute_class="hybrid",
            classical_baseline_ref="ssv-cl-002",
            quantum_metadata={"shots": 100, "simulator": "mock"},
        )
        assert gate_quantum_baseline(claim) is True


class TestIsQuantumClaim:
    def test_classical_is_not_quantum(self):
        assert is_quantum_claim({"compute_class": "classical"}) is False

    def test_quantum_sim_is_quantum(self):
        assert is_quantum_claim({"compute_class": "quantum_sim"}) is True

    def test_nested_provenance_detected(self):
        claim = {"p": {"execution_witness": {"compute_class": "quantum_hw"}}}
        assert is_quantum_claim(claim) is True


# ---------------------------------------------------------------------------
# Gate-QM: quantum metadata tests
# ---------------------------------------------------------------------------


class TestQuantumMetadataGate:
    def test_quantum_with_metadata_passes(self):
        claim = _quantum_claim()
        assert gate_quantum_metadata(claim) is True

    def test_quantum_without_metadata_fails(self):
        claim = _quantum_claim()
        del claim["quantum_metadata"]
        assert gate_quantum_metadata(claim) is False


# ---------------------------------------------------------------------------
# validate_classical_baseline_exists helper
# ---------------------------------------------------------------------------


class TestValidateClassicalBaseline:
    def test_none_ref_invalid(self):
        valid, reason = validate_classical_baseline_exists(None)
        assert valid is False
        assert "No classical_baseline_ref" in reason

    def test_empty_string_invalid(self):
        valid, reason = validate_classical_baseline_exists("")
        assert valid is False

    def test_ref_without_store_valid(self):
        valid, reason = validate_classical_baseline_exists("ssv-001")
        assert valid is True
        assert "store not available" in reason

    def test_ref_in_store_classical(self):
        store = {"ssv-001": {"compute_class": "classical"}}
        valid, reason = validate_classical_baseline_exists("ssv-001", store)
        assert valid is True

    def test_ref_not_in_store(self):
        store = {}
        valid, reason = validate_classical_baseline_exists("ssv-missing", store)
        assert valid is False
        assert "not found" in reason

    def test_ref_in_store_quantum_rejected(self):
        store = {"ssv-q": {"p": {"execution_witness": {"compute_class": "quantum_sim"}}}}
        valid, reason = validate_classical_baseline_exists("ssv-q", store)
        assert valid is False
        assert "quantum_sim" in reason


# ---------------------------------------------------------------------------
# enrich_quantum_claim_provenance helper
# ---------------------------------------------------------------------------


class TestEnrichQuantumClaimProvenance:
    def test_enriched_has_compute_class(self):
        claim = _base_claim()
        enriched = enrich_quantum_claim_provenance(claim, _quantum_result(), "ssv-001")
        assert enriched["compute_class"] == "quantum_sim"

    def test_enriched_has_exploratory(self):
        claim = _base_claim()
        enriched = enrich_quantum_claim_provenance(claim, _quantum_result(), None)
        assert enriched["exploratory"] is True

    def test_enriched_has_quantum_metadata(self):
        claim = _base_claim()
        enriched = enrich_quantum_claim_provenance(claim, _quantum_result(), None)
        assert "quantum_metadata" in enriched
        assert enriched["quantum_metadata"]["shots"] == 1024

    def test_enriched_has_baseline_ref(self):
        claim = _base_claim()
        enriched = enrich_quantum_claim_provenance(claim, _quantum_result(), "ssv-cl-1")
        assert enriched["classical_baseline_ref"] == "ssv-cl-1"

    def test_enriched_does_not_mutate_original(self):
        claim = _base_claim()
        enriched = enrich_quantum_claim_provenance(claim, _quantum_result(), "ssv-cl-1")
        assert "compute_class" not in claim
        assert "compute_class" in enriched

    def test_enriched_preserves_existing_fields(self):
        claim = _base_claim(custom_field="hello")
        enriched = enrich_quantum_claim_provenance(claim, _quantum_result(), None)
        assert enriched["custom_field"] == "hello"


# ---------------------------------------------------------------------------
# Quantum eligibility
# ---------------------------------------------------------------------------


class TestQuantumEligibility:
    def test_method_not_in_contract(self):
        manifest = {"quantum_contract": {"supported_methods": ["other"]}}
        result = assess_quantum_eligibility(manifest, "my_method")
        assert result.eligible is False
        assert result.branching_suggestion == "classical_only"

    def test_method_in_contract_eligible(self):
        manifest = {
            "quantum_contract": {
                "supported_methods": ["my_method"],
                "translation_fidelity": {"my_method": 0.85},
            }
        }
        result = assess_quantum_eligibility(manifest, "my_method")
        assert result.eligible is True
        assert result.classical_baseline_required is True
        assert result.translation_fidelity_estimate == pytest.approx(0.85)

    def test_high_fidelity_suggests_quantum_sim(self):
        manifest = {
            "quantum_contract": {
                "supported_methods": ["m1"],
                "translation_fidelity": {"m1": 0.95},
            }
        }
        result = assess_quantum_eligibility(manifest, "m1")
        assert result.branching_suggestion == "quantum_sim"

    def test_low_fidelity_suggests_classical_only(self):
        manifest = {
            "quantum_contract": {
                "supported_methods": ["m1"],
                "translation_fidelity": {"m1": 0.2},
            }
        }
        result = assess_quantum_eligibility(manifest, "m1")
        assert result.branching_suggestion == "classical_only"

    def test_no_quantum_contract(self):
        manifest = {}
        result = assess_quantum_eligibility(manifest, "any_method")
        assert result.eligible is False

    def test_dataclass_frozen(self):
        result = assess_quantum_eligibility({}, "m")
        with pytest.raises(AttributeError):
            result.eligible = True  # type: ignore


# ---------------------------------------------------------------------------
# Full evaluate_all with quantum claims
# ---------------------------------------------------------------------------


class TestEvaluateAllQuantum:
    def test_quantum_claim_exploratory_fails_h1(self):
        """Exploratory quantum claims always fail H1."""
        claim = _quantum_claim(
            classical_baseline_ref="ssv-001",
            endorsement_record={"endorser_id": "u1", "signature": "sig1"},
        )
        result = evaluate_all(claim)
        assert result.gate_h1 is False
        assert "H1" in result.failures

    def test_quantum_claim_without_baseline_fails_qb(self):
        claim = _quantum_claim()
        result = evaluate_all(claim)
        assert result.gate_qb is False
        assert "QB" in result.failures
