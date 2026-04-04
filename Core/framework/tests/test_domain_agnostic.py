"""Domain-agnostic framework tests — proves Core/framework has no domain binding.

These tests verify that:
  1. DomainRegistry accepts any domain_id
  2. DomainModule interface is domain-neutral
  3. Pipeline infrastructure works without domain-specific code
  4. Two different domains can coexist in the same registry
  5. Result adapters produce the same SSV shape regardless of domain
"""
from __future__ import annotations

from scientificstate.domain_registry import DomainModule, DomainRegistry


# ── Minimal stub domains (no real domain code) ──────────────────────────────


class _StubDomainA(DomainModule):
    """Minimal domain stub for testing framework agnosticism."""

    @property
    def domain_id(self) -> str:
        return "stub_domain_a"

    @property
    def domain_name(self) -> str:
        return "Stub Domain A"

    @property
    def supported_data_types(self) -> list[str]:
        return ["csv"]

    @property
    def version(self) -> str:
        return "0.1.0"

    def list_methods(self) -> list[dict]:
        return [
            {
                "method_id": "method_a",
                "domain_id": self.domain_id,
                "name": "Method A",
                "required_data_types": ["csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
        ]

    def execute_method(self, method_id, data_ref, assumptions, params):
        if method_id != "method_a":
            return {"method_id": method_id, "domain_id": self.domain_id, "status": "error",
                    "error": "unknown method", "diagnostics": {}}
        return {"method_id": method_id, "domain_id": self.domain_id, "status": "ok",
                "result": {"value": 42}, "diagnostics": {}}


class _StubDomainB(DomainModule):
    """Second stub domain — proves multi-domain coexistence."""

    @property
    def domain_id(self) -> str:
        return "stub_domain_b"

    @property
    def domain_name(self) -> str:
        return "Stub Domain B"

    @property
    def supported_data_types(self) -> list[str]:
        return ["json"]

    @property
    def version(self) -> str:
        return "0.2.0"

    def list_methods(self) -> list[dict]:
        return [
            {
                "method_id": "method_b",
                "domain_id": self.domain_id,
                "name": "Method B",
                "required_data_types": ["json"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
        ]

    def execute_method(self, method_id, data_ref, assumptions, params):
        if method_id != "method_b":
            return {"method_id": method_id, "domain_id": self.domain_id, "status": "error",
                    "error": "unknown method", "diagnostics": {}}
        return {"method_id": method_id, "domain_id": self.domain_id, "status": "ok",
                "result": {"answer": "hello"}, "diagnostics": {}}


# ── Tests ────────────────────────────────────────────────────────────────────


def test_registry_accepts_any_domain():
    """DomainRegistry.register() works with any domain_id."""
    registry = DomainRegistry()
    domain = _StubDomainA()
    registry.register(domain)
    assert "stub_domain_a" in registry


def test_registry_get_returns_registered_domain():
    """DomainRegistry.get() retrieves a registered domain."""
    registry = DomainRegistry()
    domain = _StubDomainA()
    registry.register(domain)
    retrieved = registry.get("stub_domain_a")
    assert retrieved is domain


def test_registry_list_domains():
    """DomainRegistry.list_domains() returns all registered domain_ids."""
    registry = DomainRegistry()
    registry.register(_StubDomainA())
    registry.register(_StubDomainB())
    domains = registry.list_domains()
    assert "stub_domain_a" in domains
    assert "stub_domain_b" in domains


def test_two_domains_coexist():
    """Two different domains can be registered and executed independently."""
    registry = DomainRegistry()
    domain_a = _StubDomainA()
    domain_b = _StubDomainB()
    registry.register(domain_a)
    registry.register(domain_b)

    result_a = registry.get("stub_domain_a").execute_method(
        "method_a", "", [], {}
    )
    result_b = registry.get("stub_domain_b").execute_method(
        "method_b", "", [], {}
    )

    assert result_a["status"] == "ok"
    assert result_b["status"] == "ok"
    assert result_a["domain_id"] == "stub_domain_a"
    assert result_b["domain_id"] == "stub_domain_b"


def test_pipeline_runs_without_domain_binding():
    """Pipeline infrastructure (registry + execute) works without domain-specific code."""
    registry = DomainRegistry()
    registry.register(_StubDomainA())

    # Simulate pipeline: lookup → execute → result
    domain = registry.get("stub_domain_a")
    assert domain is not None
    methods = domain.list_methods()
    assert len(methods) >= 1

    result = domain.execute_method(methods[0]["method_id"], "", [], {})
    assert result["status"] == "ok"
    assert "result" in result


def test_describe_is_domain_neutral():
    """DomainModule.describe() returns the same shape regardless of domain."""
    desc_a = _StubDomainA().describe()
    desc_b = _StubDomainB().describe()

    # Same keys
    assert set(desc_a.keys()) == set(desc_b.keys())
    # Required keys present
    for key in ("domain_id", "domain_name", "version", "supported_data_types", "method_count"):
        assert key in desc_a
        assert key in desc_b


def test_result_shape_consistent_across_domains():
    """execute_method() returns same top-level keys regardless of domain."""
    result_a = _StubDomainA().execute_method("method_a", "", [], {})
    result_b = _StubDomainB().execute_method("method_b", "", [], {})

    expected_keys = {"method_id", "domain_id", "status", "result", "diagnostics"}
    assert expected_keys <= set(result_a.keys())
    assert expected_keys <= set(result_b.keys())
