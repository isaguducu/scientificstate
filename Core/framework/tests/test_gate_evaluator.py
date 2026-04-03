"""Gate evaluator tests — E1 / U1 / V1 / C1 / H1 gate logic."""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _base_claim() -> dict:
    """Claim dict passing all 5 gates."""
    return {
        "evidence_paths": [{"ssv_id": "ssv-1", "type": "direct"}],
        "uncertainty_present": True,
        "validity_scope_present": True,
        "contradictions": [],
        "endorsement_record": {
            "endorser_id": "researcher-1",
            "signature": "sha256:abc123",
        },
    }


# ── Import ─────────────────────────────────────────────────────────────────────

def test_gate_evaluator_import():
    from scientificstate.claims.gate_evaluator import (
        gate_e1, evaluate_all, GateResult,
    )
    assert gate_e1 is not None
    assert evaluate_all is not None
    assert GateResult is not None


# ── GateResult ─────────────────────────────────────────────────────────────────

def test_gate_result_passed_true_when_all_pass():
    from scientificstate.claims.gate_evaluator import evaluate_all
    result = evaluate_all(_base_claim())
    assert result.passed is True
    assert result.failures == []


def test_gate_result_failures_list_on_all_fail():
    from scientificstate.claims.gate_evaluator import evaluate_all
    result = evaluate_all({})
    assert result.passed is False
    assert set(result.failures) == {"E1", "U1", "V1", "H1"}
    # C1 passes by default (no contradictions data → assume 0 criticals)


# ── Gate E1 ────────────────────────────────────────────────────────────────────

def test_e1_passes_with_evidence_paths():
    from scientificstate.claims.gate_evaluator import gate_e1
    assert gate_e1({"evidence_paths": [{"ssv_id": "ssv-1"}]}) is True


def test_e1_passes_with_ssv_id():
    from scientificstate.claims.gate_evaluator import gate_e1
    assert gate_e1({"ssv_id": "ssv-1"}) is True


def test_e1_fails_with_no_evidence():
    from scientificstate.claims.gate_evaluator import gate_e1
    assert gate_e1({}) is False


def test_e1_fails_with_empty_evidence_list():
    from scientificstate.claims.gate_evaluator import gate_e1
    assert gate_e1({"evidence_paths": []}) is False


# ── Gate U1 ────────────────────────────────────────────────────────────────────

def test_u1_passes_with_flag():
    from scientificstate.claims.gate_evaluator import gate_u1
    assert gate_u1({"uncertainty_present": True}) is True


def test_u1_passes_with_inline_uncertainty():
    from scientificstate.claims.gate_evaluator import gate_u1
    assert gate_u1({"u": {"measurement_error": {"mw": 500.0}}}) is True


def test_u1_fails_with_no_uncertainty():
    from scientificstate.claims.gate_evaluator import gate_u1
    assert gate_u1({}) is False


def test_u1_passes_with_reason_if_unquantifiable():
    from scientificstate.claims.gate_evaluator import gate_u1
    assert gate_u1({"u": {"reason_if_unquantifiable": "insufficient replicates"}}) is True


# ── Gate V1 ────────────────────────────────────────────────────────────────────

def test_v1_passes_with_flag():
    from scientificstate.claims.gate_evaluator import gate_v1
    assert gate_v1({"validity_scope_present": True}) is True


def test_v1_passes_with_inline_validity():
    from scientificstate.claims.gate_evaluator import gate_v1
    assert gate_v1({"v": {"conditions": ["T < 200C"]}}) is True


def test_v1_fails_with_no_validity():
    from scientificstate.claims.gate_evaluator import gate_v1
    assert gate_v1({}) is False


def test_v1_passes_with_status():
    from scientificstate.claims.gate_evaluator import gate_v1
    assert gate_v1({"validity_domain": {"status": "valid"}}) is True


# ── Gate C1 ────────────────────────────────────────────────────────────────────

def test_c1_passes_with_no_contradictions():
    from scientificstate.claims.gate_evaluator import gate_c1
    assert gate_c1({"contradictions": []}) is True


def test_c1_passes_when_no_contradictions_key():
    from scientificstate.claims.gate_evaluator import gate_c1
    assert gate_c1({}) is True


def test_c1_fails_with_unresolved_critical():
    from scientificstate.claims.gate_evaluator import gate_c1
    claim = {
        "contradictions": [
            {"severity": "critical", "resolution_status": "open"},
        ]
    }
    assert gate_c1(claim) is False


def test_c1_passes_when_critical_is_resolved():
    from scientificstate.claims.gate_evaluator import gate_c1
    claim = {
        "contradictions": [
            {"severity": "critical", "resolution_status": "resolved"},
        ]
    }
    assert gate_c1(claim) is True


def test_c1_passes_with_non_critical_contradiction():
    from scientificstate.claims.gate_evaluator import gate_c1
    claim = {
        "contradictions": [
            {"severity": "minor", "resolution_status": "open"},
        ]
    }
    assert gate_c1(claim) is True


# ── Gate H1 ────────────────────────────────────────────────────────────────────

def test_h1_passes_with_valid_endorsement():
    from scientificstate.claims.gate_evaluator import gate_h1
    claim = {"endorsement_record": {"endorser_id": "r-1", "signature": "sig-abc"}}
    assert gate_h1(claim) is True


def test_h1_fails_with_no_endorsement():
    from scientificstate.claims.gate_evaluator import gate_h1
    assert gate_h1({}) is False


def test_h1_fails_with_missing_signature():
    from scientificstate.claims.gate_evaluator import gate_h1
    claim = {"endorsement_record": {"endorser_id": "r-1"}}
    assert gate_h1(claim) is False


def test_h1_fails_with_missing_endorser_id():
    from scientificstate.claims.gate_evaluator import gate_h1
    claim = {"endorsement_record": {"signature": "sig-abc"}}
    assert gate_h1(claim) is False


# ── evaluate_all ───────────────────────────────────────────────────────────────

def test_evaluate_all_returns_gate_result():
    from scientificstate.claims.gate_evaluator import evaluate_all, GateResult
    result = evaluate_all(_base_claim())
    assert isinstance(result, GateResult)


def test_evaluate_all_individual_gate_access():
    from scientificstate.claims.gate_evaluator import evaluate_all
    result = evaluate_all(_base_claim())
    assert result.gate_e1 is True
    assert result.gate_u1 is True
    assert result.gate_v1 is True
    assert result.gate_c1 is True
    assert result.gate_h1 is True


def test_evaluate_all_partial_failure_tracked():
    from scientificstate.claims.gate_evaluator import evaluate_all
    # Only E1 satisfied, rest fail
    claim = {"ssv_id": "ssv-1"}
    result = evaluate_all(claim)
    assert result.passed is False
    assert result.gate_e1 is True
    assert "U1" in result.failures
    assert "V1" in result.failures
    assert "H1" in result.failures
