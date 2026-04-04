"""Chemistry domain integration tests -- domain-agnostic pipeline test."""

import json
from pathlib import Path

import pytest

from chemistry import ChemistryDomain


@pytest.fixture
def domain():
    return ChemistryDomain()


# -- Properties ---------------------------------------------------------------


def test_domain_id():
    domain = ChemistryDomain()
    assert domain.domain_id == "chemistry"


def test_domain_name():
    domain = ChemistryDomain()
    assert "Chemistry" in domain.domain_name


def test_supported_data_types():
    domain = ChemistryDomain()
    types = domain.supported_data_types
    assert "uv_vis_csv" in types
    assert "titration_csv" in types
    assert "hplc_csv" in types


def test_version():
    domain = ChemistryDomain()
    assert domain.version == "0.1.0"


def test_taxonomy():
    domain = ChemistryDomain()
    tax = domain.taxonomy
    assert tax is not None
    assert "field" in tax


def test_describe():
    domain = ChemistryDomain()
    desc = domain.describe()
    assert desc["domain_id"] == "chemistry"
    assert desc["method_count"] == 3


# -- list_methods -------------------------------------------------------------


def test_list_methods_count(domain):
    methods = domain.list_methods()
    assert len(methods) == 3


def test_list_methods_ids(domain):
    methods = domain.list_methods()
    ids = [m["method_id"] for m in methods]
    assert "uv_vis_spectroscopy" in ids
    assert "titration" in ids
    assert "hplc" in ids


def test_list_methods_required_fields(domain):
    methods = domain.list_methods()
    for m in methods:
        assert "method_id" in m
        assert "domain_id" in m
        assert m["domain_id"] == "chemistry"
        assert m["produces_uncertainty"] is True
        assert m["produces_validity_scope"] is True
        assert m["compute_class"] == "classical"


# -- execute_method errors ----------------------------------------------------


def test_unknown_method(domain):
    result = domain.execute_method("nonexistent", "", [], {})
    assert result["status"] == "error"
    assert result["error_code"].value == "UNKNOWN_METHOD"


def test_missing_uv_vis_params(domain):
    result = domain.execute_method("uv_vis_spectroscopy", "", [], {})
    assert result["status"] == "error"
    assert "wavelength" in result["error"]


def test_missing_titration_params(domain):
    result = domain.execute_method("titration", "", [], {})
    assert result["status"] == "error"
    assert "volume" in result["error"]


def test_missing_hplc_params(domain):
    result = domain.execute_method("hplc", "", [], {})
    assert result["status"] == "error"
    assert "time" in result["error"]


# -- scientificstate-domain.json -----------------------------------------------


def test_domain_json_exists():
    json_path = Path(__file__).parents[1] / "scientificstate-domain.json"
    assert json_path.exists()


def test_domain_json_valid():
    json_path = Path(__file__).parents[1] / "scientificstate-domain.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["domain_id"] == "chemistry"
    assert len(data["methods"]) == 3
    assert data["version"] == "0.1.0"
