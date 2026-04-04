"""Domain manifest tests — MaterialsScienceDomain interface compliance."""

import json
from pathlib import Path

import pytest

from materials_science import MaterialsScienceDomain


@pytest.fixture
def domain():
    return MaterialsScienceDomain()


# ── Properties ───────────────────────────────────────────────────────────────


def test_domain_id():
    domain = MaterialsScienceDomain()
    assert domain.domain_id == "materials_science"


def test_domain_name():
    domain = MaterialsScienceDomain()
    assert "Materials Science" in domain.domain_name


def test_supported_data_types():
    domain = MaterialsScienceDomain()
    types = domain.supported_data_types
    assert "xrd_csv" in types
    assert "tensile_csv" in types
    assert "dsc_csv" in types


def test_version():
    domain = MaterialsScienceDomain()
    assert domain.version == "0.1.0"


def test_taxonomy():
    domain = MaterialsScienceDomain()
    tax = domain.taxonomy
    assert tax is not None
    assert "field" in tax


def test_describe():
    domain = MaterialsScienceDomain()
    desc = domain.describe()
    assert desc["domain_id"] == "materials_science"
    assert desc["method_count"] == 3


# ── list_methods ─────────────────────────────────────────────────────────────


def test_list_methods_count(domain):
    methods = domain.list_methods()
    assert len(methods) == 3


def test_list_methods_ids(domain):
    methods = domain.list_methods()
    ids = [m["method_id"] for m in methods]
    assert "xrd_analysis" in ids
    assert "tensile_test" in ids
    assert "dsc_thermal" in ids


def test_list_methods_required_fields(domain):
    methods = domain.list_methods()
    for m in methods:
        assert "method_id" in m
        assert "domain_id" in m
        assert m["domain_id"] == "materials_science"
        assert m["produces_uncertainty"] is True
        assert m["produces_validity_scope"] is True
        assert m["compute_class"] == "classical"


# ── execute_method errors ────────────────────────────────────────────────────


def test_unknown_method(domain):
    result = domain.execute_method("nonexistent", "", [], {})
    assert result["status"] == "error"
    assert result["error_code"].value == "UNKNOWN_METHOD"


def test_missing_xrd_params(domain):
    result = domain.execute_method("xrd_analysis", "", [], {})
    assert result["status"] == "error"
    assert "two_theta" in result["error"]


def test_missing_tensile_params(domain):
    result = domain.execute_method("tensile_test", "", [], {})
    assert result["status"] == "error"
    assert "strain" in result["error"]


def test_missing_dsc_params(domain):
    result = domain.execute_method("dsc_thermal", "", [], {})
    assert result["status"] == "error"
    assert "temperature" in result["error"]


# ── scientificstate-domain.json ──────────────────────────────────────────────


def test_domain_json_exists():
    json_path = Path(__file__).parents[1] / "scientificstate-domain.json"
    assert json_path.exists()


def test_domain_json_valid():
    json_path = Path(__file__).parents[1] / "scientificstate-domain.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["domain_id"] == "materials_science"
    assert len(data["methods"]) == 3
    assert data["version"] == "0.1.0"
