"""Pipeline coordinator tests — E2E mock domain execution."""
from scientificstate.domain_registry.registry import DomainModule


# ── Mock domain ────────────────────────────────────────────────────────────────

class MockPolymerDomain(DomainModule):
    """Minimal mock domain — no polymer dependency, used for pipeline testing."""

    @property
    def domain_id(self) -> str:
        return "mock_polymer"

    @property
    def domain_name(self) -> str:
        return "Mock Polymer Domain"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def supported_data_types(self) -> list:
        return ["csv"]

    def list_methods(self) -> list:
        return [
            {
                "method_id": "mw_distribution",
                "domain_id": "mock_polymer",
                "name": "MW Distribution",
                "required_data_types": ["csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "parameters": {"peaks": 3},
            }
        ]

    def execute_method(self, method_id, data_ref, assumptions, params) -> dict:
        return {
            "method_id": method_id,
            "domain_id": self.domain_id,
            "status": "ok",
            "result": {"mw": 50000.0, "pdi": 1.2},
            "diagnostics": {
                "uncertainty": {"mw": 500.0, "pdi": 0.05},
                "validity_scope": ["temperature < 200C"],
            },
        }


class MockDomainWithMissingDiagnostics(DomainModule):
    """Mock domain that omits uncertainty/validity_scope in diagnostics."""

    @property
    def domain_id(self) -> str:
        return "mock_sparse"

    @property
    def domain_name(self) -> str:
        return "Sparse Domain"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def supported_data_types(self) -> list:
        return ["csv"]

    def list_methods(self) -> list:
        return [{"method_id": "compute", "domain_id": "mock_sparse", "name": "Compute",
                 "required_data_types": ["csv"], "produces_uncertainty": False,
                 "produces_validity_scope": False}]

    def execute_method(self, method_id, data_ref, assumptions, params) -> dict:
        return {
            "method_id": method_id,
            "domain_id": self.domain_id,
            "status": "ok",
            "result": {"value": 42.0},
            "diagnostics": {},
        }


# ── Import ─────────────────────────────────────────────────────────────────────

def test_pipeline_import():
    from scientificstate.pipeline import execute_pipeline, PipelineResult
    assert execute_pipeline is not None
    assert PipelineResult is not None


# ── Full pipeline ──────────────────────────────────────────────────────────────

def test_pipeline_returns_pipeline_result():
    from scientificstate.pipeline import execute_pipeline, PipelineResult
    domain = MockPolymerDomain()
    result = execute_pipeline(
        domain=domain,
        method_id="mw_distribution",
        assumptions=[{"assumption_id": "a1", "description": "linear baseline", "type": "background_model"}],
        dataset_ref="file://sample.csv",
        workspace_id="ws-001",
    )
    assert isinstance(result, PipelineResult)


def test_pipeline_run_is_populated():
    from scientificstate.pipeline import execute_pipeline
    from scientificstate.runs.model import ComputeRun
    result = execute_pipeline(
        domain=MockPolymerDomain(),
        method_id="mw_distribution",
        assumptions=[{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        dataset_ref=None,
        workspace_id="ws-1",
    )
    assert isinstance(result.run, ComputeRun)
    assert result.run.run_id


def test_pipeline_ssv_is_dict_with_keys():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockPolymerDomain(),
        method_id="mw_distribution",
        assumptions=[{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        dataset_ref=None,
        workspace_id="ws-1",
    )
    for key in ("id", "version", "r", "u", "v", "a"):
        assert key in result.ssv, f"SSV missing key: {key}"


def test_pipeline_claim_is_draft():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockPolymerDomain(),
        method_id="mw_distribution",
        assumptions=[{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        dataset_ref=None,
        workspace_id="ws-1",
    )
    assert result.claim["status"] == "draft"


def test_pipeline_gate_result_is_populated():
    from scientificstate.pipeline import execute_pipeline
    from scientificstate.claims.gate_evaluator import GateResult
    result = execute_pipeline(
        domain=MockPolymerDomain(),
        method_id="mw_distribution",
        assumptions=[{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        dataset_ref=None,
        workspace_id="ws-1",
    )
    assert isinstance(result.gate_result, GateResult)


def test_pipeline_complete_result_has_no_incomplete_flags():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockPolymerDomain(),
        method_id="mw_distribution",
        assumptions=[{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        dataset_ref=None,
        workspace_id="ws-1",
    )
    assert result.incomplete_flags == []


def test_pipeline_sparse_domain_has_incomplete_flags():
    from scientificstate.pipeline import execute_pipeline
    result = execute_pipeline(
        domain=MockDomainWithMissingDiagnostics(),
        method_id="compute",
        assumptions=[{"assumption_id": "a1", "description": "d", "type": "background_model"}],
        dataset_ref=None,
        workspace_id="ws-1",
    )
    assert "missing_uncertainty" in result.incomplete_flags
    assert "missing_validity_scope" in result.incomplete_flags


def test_pipeline_domain_agnostic():
    """Pipeline must not import domain-specific code."""
    import sys
    import importlib
    importlib.import_module("scientificstate.pipeline")
    domain_keys = [k for k in sys.modules if "polymer" in k and "mock" not in k]
    assert domain_keys == []
