"""Gate-REP tests — classical PASS, quantum_hw no replication FAIL, quantum_hw confirmed PASS."""


# ── Helpers ───────────────────────────────────────────────────────────────────


def _quantum_hw_claim(**overrides) -> dict:
    """Quantum hardware claim for gate testing."""
    claim = {
        "evidence_paths": [{"ssv_id": "ssv-1", "type": "direct"}],
        "uncertainty_present": True,
        "validity_scope_present": True,
        "contradictions": [],
        "endorsement_record": {
            "endorser_id": "researcher-1",
            "signature": "sha256:abc123",
        },
        "compute_class": "quantum_hw",
        "exploratory": True,
        "classical_baseline_ref": "ssv-classical-001",
        "quantum_metadata": {
            "shots": 1024,
            "backend_name": "ibm_brisbane",
            "provider": "ibm_quantum",
        },
    }
    claim.update(overrides)
    return claim


def _hybrid_claim(**overrides) -> dict:
    """Hybrid claim for gate testing."""
    claim = _quantum_hw_claim(compute_class="hybrid")
    claim.update(overrides)
    return claim


def _classical_claim() -> dict:
    """Classical claim passing all gates."""
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


# ── gate_replication — classical always passes ──────────────────────────────


def test_classical_passes_rep_gate():
    from scientificstate.claims.gate_evaluator import gate_replication
    assert gate_replication(_classical_claim()) is True


def test_classical_no_replications_passes():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _classical_claim()
    claim["replications"] = []
    assert gate_replication(claim) is True


def test_quantum_sim_passes_rep_gate():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = {"compute_class": "quantum_sim"}
    assert gate_replication(claim) is True


def test_empty_claim_passes_rep_gate():
    from scientificstate.claims.gate_evaluator import gate_replication
    assert gate_replication({}) is True


# ── gate_replication — quantum_hw requires confirmed replication ─────────────


def test_quantum_hw_no_replications_fails():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _quantum_hw_claim()
    assert gate_replication(claim) is False


def test_quantum_hw_empty_replications_fails():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _quantum_hw_claim(replications=[])
    assert gate_replication(claim) is False


def test_quantum_hw_pending_replication_fails():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _quantum_hw_claim(replications=[{"status": "pending"}])
    assert gate_replication(claim) is False


def test_quantum_hw_not_confirmed_replication_fails():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _quantum_hw_claim(replications=[{"status": "not_confirmed"}])
    assert gate_replication(claim) is False


def test_quantum_hw_confirmed_replication_passes():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _quantum_hw_claim(replications=[{"status": "confirmed"}])
    assert gate_replication(claim) is True


def test_quantum_hw_multiple_replications_one_confirmed():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _quantum_hw_claim(replications=[
        {"status": "not_confirmed"},
        {"status": "confirmed"},
        {"status": "pending"},
    ])
    assert gate_replication(claim) is True


# ── gate_replication — hybrid requires confirmed replication ─────────────────


def test_hybrid_no_replications_fails():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _hybrid_claim()
    assert gate_replication(claim) is False


def test_hybrid_confirmed_replication_passes():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _hybrid_claim(replications=[{"status": "confirmed"}])
    assert gate_replication(claim) is True


def test_hybrid_partially_confirmed_fails():
    from scientificstate.claims.gate_evaluator import gate_replication
    claim = _hybrid_claim(replications=[{"status": "partially_confirmed"}])
    assert gate_replication(claim) is False


# ── evaluate_all includes REP gate ──────────────────────────────────────────


def test_evaluate_all_quantum_hw_fails_rep():
    from scientificstate.claims.gate_evaluator import evaluate_all
    claim = _quantum_hw_claim()
    result = evaluate_all(claim)
    assert result.gate_rep is False
    assert "REP" in result.failures


def test_evaluate_all_quantum_hw_with_replication_passes_rep():
    from scientificstate.claims.gate_evaluator import evaluate_all
    claim = _quantum_hw_claim(replications=[{"status": "confirmed"}])
    result = evaluate_all(claim)
    assert result.gate_rep is True
    assert "REP" not in result.failures


def test_evaluate_all_classical_passes_rep():
    from scientificstate.claims.gate_evaluator import evaluate_all
    result = evaluate_all(_classical_claim())
    assert result.gate_rep is True
    assert "REP" not in result.failures


def test_evaluate_all_hybrid_no_rep_fails():
    from scientificstate.claims.gate_evaluator import evaluate_all
    claim = _hybrid_claim()
    result = evaluate_all(claim)
    assert result.gate_rep is False
    assert "REP" in result.failures


def test_evaluate_all_hybrid_with_rep_passes():
    from scientificstate.claims.gate_evaluator import evaluate_all
    claim = _hybrid_claim(replications=[{"status": "confirmed"}])
    result = evaluate_all(claim)
    assert result.gate_rep is True


# ── GateResult has gate_rep field ────────────────────────────────────────────


def test_gate_result_has_rep_field():
    from scientificstate.claims.gate_evaluator import evaluate_all
    result = evaluate_all({})
    assert hasattr(result, "gate_rep")


def test_gate_result_frozen_rep():
    from scientificstate.claims.gate_evaluator import evaluate_all
    result = evaluate_all(_classical_claim())
    try:
        result.gate_rep = False
        assert False, "Should be frozen"
    except AttributeError:
        pass
