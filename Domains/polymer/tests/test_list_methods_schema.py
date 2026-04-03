"""
test_list_methods_schema.py — Validates list_methods() output against
domain-module.schema.json §$defs/MethodManifest required fields (Phase 1-A, W4).

Required fields per schema:
  method_id, domain_id, name, required_data_types,
  produces_uncertainty (const: true), produces_validity_scope (const: true)
"""
import re

import pytest


REQUIRED_FIELDS = {
    "method_id",
    "domain_id",
    "name",
    "required_data_types",
    "produces_uncertainty",
    "produces_validity_scope",
}

METHOD_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
EXPECTED_METHOD_IDS = {"pca", "hca", "kmd_analysis", "deisotoping", "fragment_matching"}


@pytest.fixture
def domain():
    from polymer_science import PolymerScienceDomain
    return PolymerScienceDomain()


@pytest.fixture
def methods(domain):
    return domain.list_methods()


def test_list_methods_returns_list(methods):
    assert isinstance(methods, list)
    assert len(methods) >= 1


def test_all_expected_method_ids_present(methods):
    ids = {m["method_id"] for m in methods}
    assert EXPECTED_METHOD_IDS == ids, (
        f"Missing: {EXPECTED_METHOD_IDS - ids}  Extra: {ids - EXPECTED_METHOD_IDS}"
    )


@pytest.mark.parametrize("method_id", sorted(EXPECTED_METHOD_IDS))
def test_required_fields_present(method_id, methods):
    """Every MethodManifest has all schema-required fields."""
    m = next((m for m in methods if m["method_id"] == method_id), None)
    assert m is not None, f"Method {method_id!r} not found in list_methods()"
    missing = REQUIRED_FIELDS - m.keys()
    assert not missing, f"{method_id}: missing required fields: {missing}"


@pytest.mark.parametrize("method_id", sorted(EXPECTED_METHOD_IDS))
def test_produces_uncertainty_is_true(method_id, methods):
    """produces_uncertainty must be boolean True (schema: const: true)."""
    m = next(m for m in methods if m["method_id"] == method_id)
    assert m["produces_uncertainty"] is True, (
        f"{method_id}: produces_uncertainty must be True, got {m['produces_uncertainty']!r}"
    )


@pytest.mark.parametrize("method_id", sorted(EXPECTED_METHOD_IDS))
def test_produces_validity_scope_is_true(method_id, methods):
    """produces_validity_scope must be boolean True (schema: const: true)."""
    m = next(m for m in methods if m["method_id"] == method_id)
    assert m["produces_validity_scope"] is True, (
        f"{method_id}: produces_validity_scope must be True, got {m['produces_validity_scope']!r}"
    )


@pytest.mark.parametrize("method_id", sorted(EXPECTED_METHOD_IDS))
def test_method_id_snake_case(method_id, methods):
    """method_id must match ^[a-z][a-z0-9_]*$ (schema pattern)."""
    m = next(m for m in methods if m["method_id"] == method_id)
    assert METHOD_ID_PATTERN.match(m["method_id"]), (
        f"{method_id}: method_id does not match snake_case pattern"
    )


@pytest.mark.parametrize("method_id", sorted(EXPECTED_METHOD_IDS))
def test_domain_id_matches_parent(method_id, methods, domain):
    """method[domain_id] must match PolymerScienceDomain.domain_id."""
    m = next(m for m in methods if m["method_id"] == method_id)
    assert m["domain_id"] == domain.domain_id, (
        f"{method_id}: domain_id mismatch: {m['domain_id']!r} != {domain.domain_id!r}"
    )


@pytest.mark.parametrize("method_id", sorted(EXPECTED_METHOD_IDS))
def test_required_data_types_non_empty(method_id, methods):
    """required_data_types must be a non-empty list of strings."""
    m = next(m for m in methods if m["method_id"] == method_id)
    assert isinstance(m["required_data_types"], list), (
        f"{method_id}: required_data_types must be a list"
    )
    assert len(m["required_data_types"]) >= 1, (
        f"{method_id}: required_data_types must have at least one item"
    )
    for dt in m["required_data_types"]:
        assert isinstance(dt, str), f"{method_id}: data type {dt!r} is not a string"


@pytest.mark.parametrize("method_id", sorted(EXPECTED_METHOD_IDS))
def test_name_is_non_empty_string(method_id, methods):
    """name must be a non-empty human-readable string."""
    m = next(m for m in methods if m["method_id"] == method_id)
    assert isinstance(m["name"], str) and m["name"].strip(), (
        f"{method_id}: name must be a non-empty string"
    )


@pytest.mark.parametrize("method_id", sorted(EXPECTED_METHOD_IDS))
def test_compute_class_classical(method_id, methods):
    """compute_class must be 'classical' (M1 milestone — no quantum)."""
    m = next(m for m in methods if m["method_id"] == method_id)
    assert m.get("compute_class") == "classical", (
        f"{method_id}: compute_class must be 'classical', got {m.get('compute_class')!r}"
    )


@pytest.mark.parametrize("method_id", sorted(EXPECTED_METHOD_IDS))
def test_quantum_contract_is_none(method_id, methods):
    """quantum_contract must be None for classical methods."""
    m = next(m for m in methods if m["method_id"] == method_id)
    assert m.get("quantum_contract") is None, (
        f"{method_id}: quantum_contract must be None for classical methods"
    )
