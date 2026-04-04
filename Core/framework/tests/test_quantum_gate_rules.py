"""Quantum gate rule tests — exploratory label, H1 gate, classical baseline, metadata."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _quantum_claim(**overrides) -> dict:
    """Quantum claim that passes all gates including quantum-specific ones."""
    claim = {
        "evidence_paths": [{"ssv_id": "ssv-1", "type": "direct"}],
        "uncertainty_present": True,
        "validity_scope_present": True,
        "contradictions": [],
        "endorsement_record": {
            "endorser_id": "researcher-1",
            "signature": "sha256:abc123",
        },
        "compute_class": "quantum_sim",
        "exploratory": True,
        "classical_baseline_ref": "ssv-classical-001",
        "quantum_metadata": {
            "shots": 1024,
            "simulator": "qiskit_aer",
            "circuit_depth": 2,
            "qubit_count": 2,
        },
    }
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


# ── is_quantum_claim detection ────────────────────────────────────────────────

def test_is_quantum_claim_with_compute_class():
    from scientificstate.claims.gate_evaluator import is_quantum_claim
    assert is_quantum_claim({"compute_class": "quantum_sim"}) is True
    assert is_quantum_claim({"compute_class": "quantum_hw"}) is True
    assert is_quantum_claim({"compute_class": "hybrid"}) is True


def test_is_quantum_claim_classical():
    from scientificstate.claims.gate_evaluator import is_quantum_claim
    assert is_quantum_claim({"compute_class": "classical"}) is False
    assert is_quantum_claim({}) is False


def test_is_quantum_claim_from_provenance():
    from scientificstate.claims.gate_evaluator import is_quantum_claim
    claim = {
        "p": {
            "execution_witness": {
                "compute_class": "quantum_hw",
            }
        }
    }
    assert is_quantum_claim(claim) is True


def test_is_quantum_claim_from_provenance_classical():
    from scientificstate.claims.gate_evaluator import is_quantum_claim
    claim = {
        "p": {
            "execution_witness": {
                "compute_class": "classical",
            }
        }
    }
    assert is_quantum_claim(claim) is False


# ── gate_quantum_baseline ─────────────────────────────────────────────────────

def test_quantum_baseline_passes_with_ref():
    from scientificstate.claims.gate_evaluator import gate_quantum_baseline
    claim = _quantum_claim(classical_baseline_ref="ssv-classical-001")
    assert gate_quantum_baseline(claim) is True


def test_quantum_baseline_passes_with_ssv_id():
    from scientificstate.claims.gate_evaluator import gate_quantum_baseline
    claim = _quantum_claim(
        classical_baseline_ref=None,
        classical_baseline_ssv_id="ssv-classical-002",
    )
    assert gate_quantum_baseline(claim) is True


def test_quantum_baseline_fails_without_ref():
    from scientificstate.claims.gate_evaluator import gate_quantum_baseline
    claim = _quantum_claim(classical_baseline_ref=None)
    del claim["classical_baseline_ref"]
    assert gate_quantum_baseline(claim) is False


def test_quantum_baseline_not_applicable_to_classical():
    """Classical claims always pass quantum baseline gate."""
    from scientificstate.claims.gate_evaluator import gate_quantum_baseline
    assert gate_quantum_baseline(_classical_claim()) is True


def test_quantum_baseline_fails_for_hybrid():
    from scientificstate.claims.gate_evaluator import gate_quantum_baseline
    claim = _quantum_claim(compute_class="hybrid")
    del claim["classical_baseline_ref"]
    assert gate_quantum_baseline(claim) is False


def test_quantum_baseline_fails_for_quantum_hw():
    from scientificstate.claims.gate_evaluator import gate_quantum_baseline
    claim = _quantum_claim(compute_class="quantum_hw")
    del claim["classical_baseline_ref"]
    assert gate_quantum_baseline(claim) is False


# ── gate_quantum_metadata ─────────────────────────────────────────────────────

def test_quantum_metadata_passes_with_data():
    from scientificstate.claims.gate_evaluator import gate_quantum_metadata
    claim = _quantum_claim()
    assert gate_quantum_metadata(claim) is True


def test_quantum_metadata_fails_without_data():
    from scientificstate.claims.gate_evaluator import gate_quantum_metadata
    claim = _quantum_claim()
    del claim["quantum_metadata"]
    assert gate_quantum_metadata(claim) is False


def test_quantum_metadata_fails_without_shots():
    from scientificstate.claims.gate_evaluator import gate_quantum_metadata
    claim = _quantum_claim(quantum_metadata={"simulator": "aer"})
    assert gate_quantum_metadata(claim) is False


def test_quantum_metadata_fails_without_backend_info():
    from scientificstate.claims.gate_evaluator import gate_quantum_metadata
    claim = _quantum_claim(quantum_metadata={"shots": 1024})
    assert gate_quantum_metadata(claim) is False


def test_quantum_metadata_passes_with_provider():
    from scientificstate.claims.gate_evaluator import gate_quantum_metadata
    claim = _quantum_claim(quantum_metadata={"shots": 1024, "provider": "ibm_quantum"})
    assert gate_quantum_metadata(claim) is True


def test_quantum_metadata_passes_with_backend_name():
    from scientificstate.claims.gate_evaluator import gate_quantum_metadata
    claim = _quantum_claim(quantum_metadata={"shots": 512, "backend_name": "ibm_brisbane"})
    assert gate_quantum_metadata(claim) is True


def test_quantum_metadata_not_applicable_to_classical():
    """Classical claims always pass quantum metadata gate."""
    from scientificstate.claims.gate_evaluator import gate_quantum_metadata
    assert gate_quantum_metadata(_classical_claim()) is True


def test_quantum_metadata_from_provenance():
    from scientificstate.claims.gate_evaluator import gate_quantum_metadata
    claim = {
        "compute_class": "quantum_sim",
        "p": {
            "quantum_metadata": {
                "shots": 1024,
                "simulator": "aer",
            }
        },
    }
    assert gate_quantum_metadata(claim) is True


# ── H1 gate — exploratory hard block ─────────────────────────────────────────

def test_h1_hard_blocks_exploratory():
    """Exploratory claims cannot pass H1 (Main_Source §9A.3)."""
    from scientificstate.claims.gate_evaluator import gate_h1
    claim = _quantum_claim()
    assert claim["exploratory"] is True
    assert gate_h1(claim) is False


def test_h1_passes_non_exploratory_with_endorsement():
    """Non-exploratory claims with valid endorsement pass H1."""
    from scientificstate.claims.gate_evaluator import gate_h1
    claim = _classical_claim()
    assert gate_h1(claim) is True


# ── evaluate_all with quantum claims ──────────────────────────────────────────

def test_evaluate_all_quantum_claim_fails_h1():
    """Quantum claim always fails H1 due to exploratory=True."""
    from scientificstate.claims.gate_evaluator import evaluate_all
    claim = _quantum_claim()
    result = evaluate_all(claim)
    assert result.passed is False
    assert "H1" in result.failures
    assert result.gate_h1 is False


def test_evaluate_all_quantum_claim_passes_qb_qm():
    """Quantum claim with baseline and metadata passes QB/QM gates."""
    from scientificstate.claims.gate_evaluator import evaluate_all
    claim = _quantum_claim()
    result = evaluate_all(claim)
    assert result.gate_qb is True
    assert result.gate_qm is True
    assert "QB" not in result.failures
    assert "QM" not in result.failures


def test_evaluate_all_quantum_no_baseline_fails_qb():
    """Quantum claim without classical baseline fails QB gate."""
    from scientificstate.claims.gate_evaluator import evaluate_all
    claim = _quantum_claim()
    del claim["classical_baseline_ref"]
    result = evaluate_all(claim)
    assert result.gate_qb is False
    assert "QB" in result.failures


def test_evaluate_all_quantum_no_metadata_fails_qm():
    """Quantum claim without metadata fails QM gate."""
    from scientificstate.claims.gate_evaluator import evaluate_all
    claim = _quantum_claim()
    del claim["quantum_metadata"]
    result = evaluate_all(claim)
    assert result.gate_qm is False
    assert "QM" in result.failures


def test_evaluate_all_classical_passes_all():
    """Classical claim with full data passes all gates including QB/QM."""
    from scientificstate.claims.gate_evaluator import evaluate_all
    result = evaluate_all(_classical_claim())
    assert result.passed is True
    assert result.gate_qb is True
    assert result.gate_qm is True
    assert result.failures == []


def test_evaluate_all_classical_no_quantum_fields_still_passes():
    """Classical claims don't need quantum fields."""
    from scientificstate.claims.gate_evaluator import evaluate_all
    claim = _classical_claim()
    # Explicitly verify no quantum fields
    assert "compute_class" not in claim
    assert "quantum_metadata" not in claim
    assert "classical_baseline_ref" not in claim
    result = evaluate_all(claim)
    assert result.gate_qb is True
    assert result.gate_qm is True


# ── GateResult struct validation ──────────────────────────────────────────────

def test_gate_result_has_qb_qm_fields():
    from scientificstate.claims.gate_evaluator import evaluate_all
    result = evaluate_all({})
    assert hasattr(result, "gate_qb")
    assert hasattr(result, "gate_qm")


def test_gate_result_frozen():
    from scientificstate.claims.gate_evaluator import evaluate_all
    result = evaluate_all(_classical_claim())
    try:
        result.gate_qb = False
        assert False, "Should be frozen"
    except AttributeError:
        pass


# ── Hybrid claim tests ───────────────────────────────────────────────────────

def test_hybrid_claim_is_quantum():
    from scientificstate.claims.gate_evaluator import is_quantum_claim
    assert is_quantum_claim({"compute_class": "hybrid"}) is True


def test_hybrid_claim_needs_baseline():
    from scientificstate.claims.gate_evaluator import gate_quantum_baseline
    claim = {"compute_class": "hybrid"}
    assert gate_quantum_baseline(claim) is False


def test_hybrid_claim_needs_metadata():
    from scientificstate.claims.gate_evaluator import gate_quantum_metadata
    claim = {"compute_class": "hybrid"}
    assert gate_quantum_metadata(claim) is False


def test_hybrid_claim_exploratory_blocks_h1():
    from scientificstate.claims.gate_evaluator import gate_h1
    claim = _quantum_claim(compute_class="hybrid")
    assert gate_h1(claim) is False
