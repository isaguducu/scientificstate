"""Quantum pipeline tests — SSV quantum_metadata, exploratory hard block."""

from scientificstate.domain_registry.registry import DomainModule


# ── Mock quantum domain ───────────────────────────────────────────────────────

class MockQuantumDomain(DomainModule):
    """Mock domain that returns quantum simulation results."""

    @property
    def domain_id(self) -> str:
        return "mock_quantum"

    @property
    def domain_name(self) -> str:
        return "Mock Quantum Domain"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def supported_data_types(self) -> list:
        return ["qasm"]

    def list_methods(self) -> list:
        return [
            {
                "method_id": "bell_state",
                "domain_id": "mock_quantum",
                "name": "Bell State Simulation",
                "required_data_types": ["qasm"],
                "produces_uncertainty": False,
                "produces_validity_scope": False,
            }
        ]

    def execute_method(self, method_id, data_ref, assumptions, params) -> dict:
        return {
            "method_id": method_id,
            "domain_id": self.domain_id,
            "status": "ok",
            "result": {"counts": {"00": 512, "11": 512}},
            "diagnostics": {},
            "quantum_metadata": {
                "shots": 1024,
                "noise_model": None,
                "simulator": "mock_fallback",
                "circuit_depth": 3,
                "qubit_count": 2,
            },
            "exploratory": True,
        }


class MockClassicalDomain(DomainModule):
    """Mock classical domain — NO quantum metadata."""

    @property
    def domain_id(self) -> str:
        return "mock_classical"

    @property
    def domain_name(self) -> str:
        return "Mock Classical Domain"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def supported_data_types(self) -> list:
        return ["csv"]

    def list_methods(self) -> list:
        return [{"method_id": "compute", "domain_id": "mock_classical", "name": "Compute",
                 "required_data_types": ["csv"], "produces_uncertainty": True,
                 "produces_validity_scope": True}]

    def execute_method(self, method_id, data_ref, assumptions, params) -> dict:
        return {
            "method_id": method_id,
            "domain_id": self.domain_id,
            "status": "ok",
            "result": {"mw": 50000.0},
            "diagnostics": {
                "uncertainty": {"mw": 500.0},
                "validity_scope": ["T < 200C"],
            },
        }


# ── Assumptions helper ─────────────────────────────────────────────────────────

_ASSUMPTIONS = [{"assumption_id": "a1", "description": "test", "type": "background_model"}]


# ── SSV quantum_metadata tests ─────────────────────────────────────────────────

def test_quantum_run_ssv_has_quantum_metadata():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockQuantumDomain(),
        method_id="bell_state",
        assumptions=_ASSUMPTIONS,
        dataset_ref=None,
        workspace_id="ws-q1",
    )
    assert "quantum_metadata" in result.ssv["p"]
    qm = result.ssv["p"]["quantum_metadata"]
    assert qm["shots"] == 1024
    assert qm["simulator"] == "mock_fallback"
    assert qm["circuit_depth"] == 3
    assert qm["qubit_count"] == 2


def test_quantum_run_ssv_has_exploratory_flag():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockQuantumDomain(),
        method_id="bell_state",
        assumptions=_ASSUMPTIONS,
        dataset_ref=None,
        workspace_id="ws-q2",
    )
    assert result.ssv["p"].get("exploratory") is True


def test_quantum_run_ssv_compute_class_is_quantum_sim():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockQuantumDomain(),
        method_id="bell_state",
        assumptions=_ASSUMPTIONS,
        dataset_ref=None,
        workspace_id="ws-q3",
    )
    assert result.ssv["p"]["execution_witness"]["compute_class"] == "quantum_sim"


# ── Exploratory hard block tests ───────────────────────────────────────────────

def test_exploratory_claim_has_exploratory_flag():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockQuantumDomain(),
        method_id="bell_state",
        assumptions=_ASSUMPTIONS,
        dataset_ref=None,
        workspace_id="ws-q4",
    )
    assert result.claim["exploratory"] is True


def test_exploratory_claim_has_exploratory_reason():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockQuantumDomain(),
        method_id="bell_state",
        assumptions=_ASSUMPTIONS,
        dataset_ref=None,
        workspace_id="ws-q5",
    )
    assert "exploratory_reason" in result.claim
    assert "classical baseline" in result.claim["exploratory_reason"].lower()


def test_exploratory_claim_h1_gate_blocked():
    """Exploratory claims CANNOT pass H1 — hard block (Main_Source §9A.3)."""
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockQuantumDomain(),
        method_id="bell_state",
        assumptions=_ASSUMPTIONS,
        dataset_ref=None,
        workspace_id="ws-q6",
    )
    assert result.gate_result.gate_h1 is False
    assert "H1" in result.gate_result.failures


def test_exploratory_claim_cannot_reach_endorsable():
    """Even with an endorsement record, exploratory claims are blocked at H1."""
    from scientificstate.claims.gate_evaluator import gate_h1
    # Claim with valid endorsement but exploratory=True → still False
    claim = {
        "exploratory": True,
        "endorsement_record": {
            "endorser_id": "researcher-1",
            "signature": "sha256:valid_signature",
        },
    }
    assert gate_h1(claim) is False


# ── Classical run has NO exploratory flag ──────────────────────────────────────

def test_classical_run_no_exploratory_flag():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockClassicalDomain(),
        method_id="compute",
        assumptions=_ASSUMPTIONS,
        dataset_ref=None,
        workspace_id="ws-c1",
    )
    assert result.claim.get("exploratory") is not True
    assert result.ssv["p"].get("exploratory") is not True


def test_classical_run_no_quantum_metadata():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockClassicalDomain(),
        method_id="compute",
        assumptions=_ASSUMPTIONS,
        dataset_ref=None,
        workspace_id="ws-c2",
    )
    assert "quantum_metadata" not in result.ssv["p"]


def test_classical_run_compute_class_is_classical():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockClassicalDomain(),
        method_id="compute",
        assumptions=_ASSUMPTIONS,
        dataset_ref=None,
        workspace_id="ws-c3",
    )
    assert result.ssv["p"]["execution_witness"]["compute_class"] == "classical"
