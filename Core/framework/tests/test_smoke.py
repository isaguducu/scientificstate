"""
Smoke tests — W3 done criteria (post-correction):

1. from scientificstate.ssv.model import SSV  → OK
2. SSV has version (int) and parent_ssv_id (str | None) fields
3. ClaimStatus has all 7 states
4. VALID_TRANSITIONS matches plan — RETRACTED only from CONTESTED
5. DomainModule has domain_id, domain_name, supported_data_types, list_methods(), execute_method()
6. DomainRegistry().discover_and_register() callable, returns list[str]
7. DomainRegistry.list_domains() returns list[str]
8. Framework has no domain-specific imports
"""
import pytest


# ── SSV smoke ──────────────────────────────────────────────────────────────

def test_ssv_import():
    from scientificstate.ssv.model import SSV
    assert SSV is not None


def test_ssv_instantiation():
    from scientificstate.ssv.model import SSV
    ssv = SSV()
    assert ssv.id


def test_ssv_has_version_field():
    from scientificstate.ssv.model import SSV
    ssv = SSV()
    assert isinstance(ssv.version, int)
    assert ssv.version == 1


def test_ssv_has_parent_ssv_id_field():
    from scientificstate.ssv.model import SSV
    ssv = SSV()
    assert ssv.parent_ssv_id is None


def test_ssv_completeness_false_on_empty():
    from scientificstate.ssv.model import SSV
    ssv = SSV()
    assert ssv.is_complete is False


def test_ssv_completeness_true():
    from scientificstate.ssv.model import (
        SSV, RawData, InstrumentConfig, Assumptions,
        InferenceResult, UncertaintyModel, ValidityDomain,
    )
    ssv = SSV(
        d=RawData(ref="file://sample.csv", domain="polymer"),
        i=InstrumentConfig(instrument_id="GC-MS-001"),
        a=Assumptions(background_model="linear baseline"),
        r=InferenceResult(quantities={"mw": 50000.0}),
        u=UncertaintyModel(measurement_error={"mw": 500.0}),
        v=ValidityDomain(conditions=["temperature < 200C"]),
    )
    assert ssv.is_complete is True


def test_ssv_immutable():
    from scientificstate.ssv.model import SSV
    ssv = SSV()
    with pytest.raises((AttributeError, TypeError)):
        ssv.id = "mutated"  # type: ignore[misc]


def test_ssv_derive_increments_version():
    from scientificstate.ssv.model import SSV, RawData
    original = SSV(d=RawData(ref="file://raw.csv", domain="polymer"))
    derived = original.derive(d=RawData(ref="file://raw2.csv", domain="polymer"))
    assert derived.id != original.id
    assert derived.version == original.version + 1
    assert derived.parent_ssv_id == original.id


# ── ClaimStatus smoke ──────────────────────────────────────────────────────

def test_claim_status_import():
    from scientificstate.claims.lifecycle import ClaimStatus
    assert ClaimStatus is not None


def test_claim_status_has_7_states():
    from scientificstate.claims.lifecycle import ClaimStatus
    states = {s.value for s in ClaimStatus}
    assert states == {
        "draft",
        "under_review",
        "provisionally_supported",
        "endorsable",
        "endorsed",
        "contested",
        "retracted",
    }


def test_valid_transitions_matches_plan():
    """
    Plan (Execution_Plan_Phase0.md §2.3): RETRACTED is only reachable from CONTESTED.
    No other state may transition directly to RETRACTED.
    """
    from scientificstate.claims.lifecycle import ClaimStatus, VALID_TRANSITIONS

    # Only CONTESTED should have RETRACTED as a target
    for state, targets in VALID_TRANSITIONS.items():
        if state == ClaimStatus.CONTESTED:
            assert ClaimStatus.RETRACTED in targets, "CONTESTED must allow → RETRACTED"
        else:
            assert ClaimStatus.RETRACTED not in targets, (
                f"{state.value} must NOT allow → RETRACTED (only CONTESTED can)"
            )


def test_claim_transition_valid():
    from scientificstate.claims.lifecycle import ClaimStatus, transition
    result = transition(ClaimStatus.DRAFT, ClaimStatus.UNDER_REVIEW)
    assert result == ClaimStatus.UNDER_REVIEW


def test_claim_transition_invalid_skip():
    from scientificstate.claims.lifecycle import ClaimStatus, transition, ClaimTransitionError
    with pytest.raises(ClaimTransitionError):
        transition(ClaimStatus.DRAFT, ClaimStatus.ENDORSED)


def test_claim_transition_retracted_is_terminal():
    from scientificstate.claims.lifecycle import ClaimStatus, transition, ClaimTransitionError
    with pytest.raises(ClaimTransitionError):
        transition(ClaimStatus.RETRACTED, ClaimStatus.DRAFT)


def test_claim_draft_cannot_retract_directly():
    """Plan: RETRACTED only from CONTESTED."""
    from scientificstate.claims.lifecycle import ClaimStatus, transition, ClaimTransitionError
    with pytest.raises(ClaimTransitionError):
        transition(ClaimStatus.DRAFT, ClaimStatus.RETRACTED)


def test_claim_contested_can_retract():
    from scientificstate.claims.lifecycle import ClaimStatus, transition
    result = transition(ClaimStatus.CONTESTED, ClaimStatus.RETRACTED)
    assert result == ClaimStatus.RETRACTED


# ── DomainRegistry / DomainModule smoke ───────────────────────────────────

def test_domain_registry_import():
    from scientificstate.domain_registry.registry import DomainRegistry
    assert DomainRegistry is not None


def test_domain_module_import():
    from scientificstate.domain_registry.registry import DomainModule
    assert DomainModule is not None


def test_domain_registry_instantiation():
    from scientificstate.domain_registry.registry import DomainRegistry
    reg = DomainRegistry()
    assert len(reg) == 0


def test_domain_registry_discover_and_register_callable_returns_list():
    from scientificstate.domain_registry.registry import DomainRegistry
    reg = DomainRegistry()
    result = reg.discover_and_register()
    assert isinstance(result, list)


def test_domain_registry_list_domains_returns_list_of_str():
    from scientificstate.domain_registry.registry import DomainRegistry
    reg = DomainRegistry()
    result = reg.list_domains()
    assert isinstance(result, list)
    assert all(isinstance(k, str) for k in result)


def test_domain_module_required_interface():
    """DomainModule must enforce domain_id, domain_name, supported_data_types,
    list_methods(), execute_method() — plan §2.3."""
    from scientificstate.domain_registry.registry import DomainModule
    import inspect

    abstract_methods = {
        name for name, m in inspect.getmembers(DomainModule)
        if getattr(m, "__isabstractmethod__", False)
    }
    assert "domain_id" in abstract_methods, "domain_id must be abstract"
    assert "domain_name" in abstract_methods, "domain_name must be abstract"
    assert "supported_data_types" in abstract_methods, "supported_data_types must be abstract"
    assert "list_methods" in abstract_methods, "list_methods must be abstract"
    assert "execute_method" in abstract_methods, "execute_method must be abstract"


def test_domain_registry_register_and_get():
    from scientificstate.domain_registry.registry import DomainRegistry, DomainModule

    class FakeDomain(DomainModule):
        @property
        def domain_id(self) -> str: return "fake_domain"
        @property
        def domain_name(self) -> str: return "Fake Domain"
        @property
        def supported_data_types(self) -> list: return ["fake_csv"]
        def list_methods(self) -> list: return []
        def execute_method(self, method_id, data_ref, assumptions, params): return {}

    reg = DomainRegistry()
    reg.register(FakeDomain())
    assert "fake_domain" in reg
    module = reg.get("fake_domain")
    assert module is not None
    assert module.domain_name == "Fake Domain"
    assert module.supported_data_types == ["fake_csv"]


def test_domain_registry_list_domains_contains_registered():
    from scientificstate.domain_registry.registry import DomainRegistry, DomainModule

    class D1(DomainModule):
        @property
        def domain_id(self) -> str: return "d1"
        @property
        def domain_name(self) -> str: return "D1"
        @property
        def supported_data_types(self) -> list: return []
        def list_methods(self) -> list: return []
        def execute_method(self, method_id, data_ref, assumptions, params): return {}

    reg = DomainRegistry()
    reg.register(D1())
    assert reg.list_domains() == ["d1"]


def test_domain_registry_get_returns_none_for_unknown():
    from scientificstate.domain_registry.registry import DomainRegistry
    reg = DomainRegistry()
    assert reg.get("does_not_exist") is None


def test_domain_module_describe():
    from scientificstate.domain_registry.registry import DomainModule

    class FakeDomain(DomainModule):
        @property
        def domain_id(self) -> str: return "fake"
        @property
        def domain_name(self) -> str: return "Fake"
        @property
        def supported_data_types(self) -> list: return ["x"]
        def list_methods(self) -> list: return [{"method_id": "m1"}]
        def execute_method(self, method_id, data_ref, assumptions, params): return {}

    d = FakeDomain()
    desc = d.describe()
    assert desc["domain_id"] == "fake"
    assert desc["method_count"] == 1


# ── No domain imports in framework ────────────────────────────────────────

def test_framework_has_no_polymer_import():
    """
    The framework must not import any domain-specific module.
    Structural enforcement of the domain-agnostic constraint.
    """
    import sys
    polymer_keys = [k for k in sys.modules if "polymer" in k]
    assert polymer_keys == [], f"Framework imported domain module: {polymer_keys}"
