"""Biology domain integration tests -- domain-agnostic pipeline test."""

import json
from pathlib import Path

import pytest

from biology import BiologyDomain


@pytest.fixture
def domain():
    return BiologyDomain()


# -- Properties ---------------------------------------------------------------


def test_domain_id():
    domain = BiologyDomain()
    assert domain.domain_id == "biology"


def test_domain_name():
    domain = BiologyDomain()
    assert "Biology" in domain.domain_name


def test_supported_data_types():
    domain = BiologyDomain()
    types = domain.supported_data_types
    assert "pcr_csv" in types
    assert "gel_csv" in types
    assert "viability_csv" in types


def test_version():
    domain = BiologyDomain()
    assert domain.version == "0.1.0"


def test_taxonomy():
    domain = BiologyDomain()
    tax = domain.taxonomy
    assert tax is not None
    assert "field" in tax


def test_describe():
    domain = BiologyDomain()
    desc = domain.describe()
    assert desc["domain_id"] == "biology"
    assert desc["method_count"] == 3


# -- list_methods -------------------------------------------------------------


def test_list_methods_count(domain):
    methods = domain.list_methods()
    assert len(methods) == 3


def test_list_methods_ids(domain):
    methods = domain.list_methods()
    ids = [m["method_id"] for m in methods]
    assert "pcr_amplification" in ids
    assert "gel_electrophoresis" in ids
    assert "cell_viability" in ids


def test_list_methods_required_fields(domain):
    methods = domain.list_methods()
    for m in methods:
        assert "method_id" in m
        assert "domain_id" in m
        assert m["domain_id"] == "biology"
        assert m["produces_uncertainty"] is True
        assert m["produces_validity_scope"] is True
        assert m["compute_class"] == "classical"


# -- execute_method errors ----------------------------------------------------


def test_unknown_method(domain):
    result = domain.execute_method("nonexistent", "", [], {})
    assert result["status"] == "error"
    assert result["error_code"].value == "UNKNOWN_METHOD"


def test_missing_pcr_params(domain):
    result = domain.execute_method("pcr_amplification", "", [], {})
    assert result["status"] == "error"
    assert "cycles" in result["error"]


def test_missing_gel_params(domain):
    result = domain.execute_method("gel_electrophoresis", "", [], {})
    assert result["status"] == "error"
    assert "distances" in result["error"]


def test_missing_viability_params(domain):
    result = domain.execute_method("cell_viability", "", [], {})
    assert result["status"] == "error"
    assert "concentrations" in result["error"]


# -- scientificstate-domain.json -----------------------------------------------


def test_domain_json_exists():
    json_path = Path(__file__).parents[1] / "scientificstate-domain.json"
    assert json_path.exists()


def test_domain_json_valid():
    json_path = Path(__file__).parents[1] / "scientificstate-domain.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["domain_id"] == "biology"
    assert len(data["methods"]) == 3
    assert data["version"] == "0.1.0"
