"""RO-Crate v2 mapper tests — SSV → valid JSON-LD, quantum provenance."""

from scientificstate.standards.rocrate import ssv_to_rocrate


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_ssv(**overrides) -> dict:
    """Minimal SSV for testing."""
    ssv = {
        "id": "test-ssv-001",
        "version": 1,
        "parent_ssv_id": None,
        "d": {"ref": "raw-data-ref", "domain": "test_domain", "metadata": {"sample": "A1"}},
        "i": {"instrument_id": "inst-001", "resolution": "0.1nm", "mode": "XRD", "dynamic_range": "", "extra": {}},
        "a": [
            {"assumption_id": "a1", "description": "Temperature stable", "type": "background_model"},
            {"assumption_id": "a2", "description": "Pure sample", "type": "simplification"},
        ],
        "t": [
            {
                "name": "kmd_analysis",
                "algorithm": "kmd_analysis",
                "parameters": {"resolution": 0.001, "range": "100-500"},
                "software_version": "1.0.0",
            }
        ],
        "r": {"quantities": {"mw": 50000.0, "pdi": 1.5}, "method": "kmd_analysis", "notes": ""},
        "u": {
            "measurement_error": {"mw": 500.0},
            "confidence_intervals": {},
            "propagation_method": "GUM",
            "notes": "",
        },
        "v": {"conditions": ["T < 200C", "ambient pressure"], "exclusions": ["T > 500C"], "notes": ""},
        "p": {
            "created_at": "2026-04-04T12:00:00+00:00",
            "researcher_id": "researcher-1",
            "software_versions": {},
            "notes": "",
            "execution_witness": {"compute_class": "classical", "backend_id": "test_domain"},
        },
    }
    ssv.update(overrides)
    return ssv


def _make_quantum_ssv() -> dict:
    """SSV with quantum provenance metadata."""
    ssv = _make_ssv()
    ssv["p"]["execution_witness"] = {
        "compute_class": "quantum_sim",
        "backend_id": "qiskit_aer",
        "shots": 1024,
        "circuit_depth": 3,
        "qubit_count": 2,
    }
    ssv["p"]["quantum_metadata"] = {
        "shots": 1024,
        "noise_model": None,
        "simulator": "mock_fallback",
        "circuit_depth": 3,
        "qubit_count": 2,
        "backend_name": "qiskit_aer",
    }
    ssv["p"]["exploratory"] = True
    return ssv


def _make_run() -> dict:
    return {
        "run_id": "run-001",
        "workspace_id": "ws-1",
        "domain_id": "test_domain",
        "method_id": "kmd_analysis",
        "status": "succeeded",
        "started_at": "2026-04-04T12:00:00+00:00",
        "finished_at": "2026-04-04T12:00:05+00:00",
    }


# ── Structure tests ─────────────────────────────────────────────────────────

def test_rocrate_has_context_and_graph():
    doc = ssv_to_rocrate(_make_ssv())
    assert "@context" in doc
    assert "@graph" in doc
    assert isinstance(doc["@graph"], list)


def test_rocrate_context_is_correct():
    doc = ssv_to_rocrate(_make_ssv())
    assert doc["@context"] == "https://w3id.org/ro/crate/1.2-DRAFT/context"


def test_rocrate_conformsto():
    doc = ssv_to_rocrate(_make_ssv())
    root = doc["@graph"][0]
    assert root["@id"] == "./"
    assert root["@type"] == "Dataset"
    assert root["conformsTo"]["@id"] == "https://w3id.org/ro/crate/1.2-DRAFT"


def test_rocrate_has_metadata_descriptor():
    doc = ssv_to_rocrate(_make_ssv())
    descriptors = [e for e in doc["@graph"] if e.get("@id") == "ro-crate-metadata.json"]
    assert len(descriptors) == 1
    assert descriptors[0]["@type"] == "CreativeWork"


# ── D: Dataset entity ────────────────────────────────────────────────────────

def test_rocrate_dataset_entity():
    doc = ssv_to_rocrate(_make_ssv())
    datasets = [e for e in doc["@graph"] if e.get("@id") == "#dataset-test-ssv-001"]
    assert len(datasets) == 1
    ds = datasets[0]
    assert ds["@type"] == "Dataset"
    assert ds["identifier"] == "raw-data-ref"


# ── T: SoftwareApplication + CreateAction ─────────────────────────────────

def test_rocrate_software_application():
    doc = ssv_to_rocrate(_make_ssv())
    sw = [e for e in doc["@graph"] if e.get("@type") == "SoftwareApplication"]
    assert len(sw) >= 1
    assert sw[0]["name"] == "kmd_analysis"


def test_rocrate_create_action():
    doc = ssv_to_rocrate(_make_ssv(), run=_make_run())
    actions = [e for e in doc["@graph"] if e.get("@type") == "CreateAction"]
    assert len(actions) >= 1
    assert actions[0]["startTime"] == "2026-04-04T12:00:00+00:00"


# ── R: Results ────────────────────────────────────────────────────────────────

def test_rocrate_result_entity():
    doc = ssv_to_rocrate(_make_ssv())
    results = [e for e in doc["@graph"] if e.get("@id") == "#result-test-ssv-001"]
    assert len(results) == 1
    props = results[0]["additionalProperty"]
    prop_names = [p["name"] for p in props]
    assert "mw" in prop_names
    assert "pdi" in prop_names


# ── A: Assumptions ────────────────────────────────────────────────────────────

def test_rocrate_assumptions():
    doc = ssv_to_rocrate(_make_ssv())
    assumptions = [e for e in doc["@graph"] if "Assumption" in str(e.get("propertyID", ""))]
    assert len(assumptions) == 2
    assert assumptions[0]["name"] == "Temperature stable"


# ── U: Uncertainty ────────────────────────────────────────────────────────────

def test_rocrate_uncertainty():
    doc = ssv_to_rocrate(_make_ssv())
    unc = [e for e in doc["@graph"] if "Uncertainty" in str(e.get("propertyID", ""))]
    assert len(unc) == 1
    prop_names = [p["name"] for p in unc[0]["additionalProperty"]]
    assert "measurement_error.mw" in prop_names


# ── V: Validity ───────────────────────────────────────────────────────────────

def test_rocrate_validity_domain():
    doc = ssv_to_rocrate(_make_ssv())
    val = [e for e in doc["@graph"] if "ValidityDomain" in str(e.get("propertyID", ""))]
    assert len(val) == 1
    assert "T < 200C" in val[0]["value"]


# ── P: Provenance ─────────────────────────────────────────────────────────────

def test_rocrate_provenance():
    doc = ssv_to_rocrate(_make_ssv())
    prov = [e for e in doc["@graph"] if "Provenance" in str(e.get("propertyID", ""))]
    assert len(prov) == 1
    prop_names = [p["name"] for p in prov[0]["additionalProperty"]]
    assert "compute_class" in prop_names
    assert "backend_id" in prop_names


# ── Quantum provenance (W1 output) ───────────────────────────────────────────

def test_rocrate_quantum_provenance_included():
    ssv = _make_quantum_ssv()
    doc = ssv_to_rocrate(ssv)
    prov = [e for e in doc["@graph"] if "Provenance" in str(e.get("propertyID", ""))]
    assert len(prov) == 1
    prop_names = [p["name"] for p in prov[0]["additionalProperty"]]
    assert "quantum.shots" in prop_names
    assert "quantum.circuit_depth" in prop_names
    assert "quantum.qubit_count" in prop_names
    assert "quantum.simulator" in prop_names
    assert "exploratory" in prop_names


def test_rocrate_quantum_compute_class():
    ssv = _make_quantum_ssv()
    doc = ssv_to_rocrate(ssv)
    prov = [e for e in doc["@graph"] if "Provenance" in str(e.get("propertyID", ""))]
    props = {p["name"]: p["value"] for p in prov[0]["additionalProperty"]}
    assert props["compute_class"] == "quantum_sim"


# ── hasPart references ───────────────────────────────────────────────────────

def test_rocrate_root_has_part_references():
    doc = ssv_to_rocrate(_make_ssv())
    root = doc["@graph"][0]
    part_ids = [p["@id"] for p in root["hasPart"]]
    assert "#dataset-test-ssv-001" in part_ids
    assert "#result-test-ssv-001" in part_ids


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_rocrate_empty_ssv():
    doc = ssv_to_rocrate({"id": "empty"})
    assert "@graph" in doc
    assert len(doc["@graph"]) >= 2  # root + metadata descriptor


def test_rocrate_no_run():
    doc = ssv_to_rocrate(_make_ssv(), run=None)
    actions = [e for e in doc["@graph"] if e.get("@type") == "CreateAction"]
    assert len(actions) >= 1
    assert actions[0].get("startTime") is None
