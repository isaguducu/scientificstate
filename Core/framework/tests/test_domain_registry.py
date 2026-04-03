"""DomainRegistry + DomainModule tests — including version and taxonomy fields."""
import inspect
import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_domain(domain_id="test", version="0.1.0", taxonomy=None):
    from scientificstate.domain_registry.registry import DomainModule

    class _D(DomainModule):
        @property
        def domain_id(self) -> str: return domain_id
        @property
        def domain_name(self) -> str: return domain_id.capitalize()
        @property
        def version(self) -> str: return version
        @property
        def supported_data_types(self) -> list: return ["csv"]
        @property
        def taxonomy(self) -> dict | None: return taxonomy
        def list_methods(self) -> list: return [{"method_id": "m1"}]
        def execute_method(self, method_id, data_ref, assumptions, params): return {}

    return _D()


# ── DomainModule interface ─────────────────────────────────────────────────────

def test_domain_module_version_is_abstract():
    from scientificstate.domain_registry.registry import DomainModule
    abstract = {
        name for name, m in inspect.getmembers(DomainModule)
        if getattr(m, "__isabstractmethod__", False)
    }
    assert "version" in abstract, "version must be an abstract property"


def test_domain_module_taxonomy_has_default_none():
    """taxonomy is non-abstract — default implementation returns None."""
    d = _make_domain()
    assert d.taxonomy is None


def test_domain_module_taxonomy_can_be_overridden():
    tax = {"class": "spectroscopy", "subclass": "mass_spectrometry"}
    d = _make_domain(taxonomy=tax)
    assert d.taxonomy == tax


def test_domain_module_version_semver():
    d = _make_domain(version="1.2.3")
    assert d.version == "1.2.3"


def test_domain_module_describe_includes_version():
    d = _make_domain(version="2.0.0")
    desc = d.describe()
    assert "version" in desc
    assert desc["version"] == "2.0.0"


def test_domain_module_describe_shape():
    d = _make_domain(domain_id="chem", version="0.3.1")
    desc = d.describe()
    assert desc["domain_id"] == "chem"
    assert desc["domain_name"] == "Chem"
    assert desc["version"] == "0.3.1"
    assert desc["supported_data_types"] == ["csv"]
    assert desc["method_count"] == 1


# ── DomainRegistry ─────────────────────────────────────────────────────────────

def test_registry_register_and_version_accessible():
    from scientificstate.domain_registry.registry import DomainRegistry
    reg = DomainRegistry()
    d = _make_domain(domain_id="x", version="0.5.0")
    reg.register(d)
    module = reg.get("x")
    assert module is not None
    assert module.version == "0.5.0"


def test_registry_register_overwrites_on_conflict():
    from scientificstate.domain_registry.registry import DomainRegistry
    reg = DomainRegistry()
    reg.register(_make_domain(domain_id="dup", version="0.1.0"))
    reg.register(_make_domain(domain_id="dup", version="0.2.0"))
    assert reg.get("dup").version == "0.2.0"


def test_registry_version_in_describe_via_registry():
    from scientificstate.domain_registry.registry import DomainRegistry
    reg = DomainRegistry()
    reg.register(_make_domain(domain_id="bio", version="3.1.4"))
    desc = reg.get("bio").describe()
    assert desc["version"] == "3.1.4"


def test_registry_cannot_instantiate_without_version():
    """Concrete subclass missing version must raise TypeError (ABC enforcement)."""
    from scientificstate.domain_registry.registry import DomainModule

    class Incomplete(DomainModule):
        @property
        def domain_id(self) -> str: return "bad"
        @property
        def domain_name(self) -> str: return "Bad"
        # version NOT implemented — abstract
        @property
        def supported_data_types(self) -> list: return []
        def list_methods(self) -> list: return []
        def execute_method(self, method_id, data_ref, assumptions, params): return {}

    with pytest.raises(TypeError):
        Incomplete()
