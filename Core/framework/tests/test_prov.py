"""W3C PROV mapping tests — PROV-JSON structure, PROV-N string, quantum run type."""

from scientificstate.standards.prov import ssv_to_prov_json, ssv_to_prov_n


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_ssv(**overrides) -> dict:
    ssv = {
        "id": "ssv-prov-001",
        "version": 1,
        "d": {"ref": "data-ref-1", "domain": "polymer_science", "metadata": {}},
        "i": {"instrument_id": "inst-1"},
        "a": [{"assumption_id": "a1", "description": "test", "type": "bg"}],
        "t": [{"name": "kmd", "algorithm": "kmd", "parameters": {}, "software_version": "1.0"}],
        "r": {"quantities": {"mw": 50000.0}, "method": "kmd", "notes": ""},
        "u": {"measurement_error": {"mw": 500.0}},
        "v": {"conditions": ["T < 200C"]},
        "p": {
            "created_at": "2026-04-04T12:00:00+00:00",
            "researcher_id": "researcher-1",
            "execution_witness": {"compute_class": "classical", "backend_id": "polymer_science"},
        },
    }
    ssv.update(overrides)
    return ssv


def _make_quantum_ssv() -> dict:
    ssv = _make_ssv()
    ssv["p"]["execution_witness"] = {
        "compute_class": "quantum_sim",
        "backend_id": "qiskit_aer",
    }
    ssv["p"]["quantum_metadata"] = {
        "shots": 1024,
        "simulator": "mock_fallback",
        "circuit_depth": 3,
        "qubit_count": 2,
    }
    return ssv


def _make_run(**overrides) -> dict:
    run = {
        "run_id": "run-prov-001",
        "domain_id": "polymer_science",
        "method_id": "kmd",
        "status": "succeeded",
        "started_at": "2026-04-04T12:00:00+00:00",
        "finished_at": "2026-04-04T12:00:05+00:00",
    }
    run.update(overrides)
    return run


# ── PROV-JSON structure ──────────────────────────────────────────────────────

def test_prov_json_has_required_sections():
    doc = ssv_to_prov_json(_make_ssv())
    for section in ("prefix", "entity", "activity", "agent", "wasGeneratedBy", "used"):
        assert section in doc


def test_prov_json_prefixes():
    doc = ssv_to_prov_json(_make_ssv())
    assert doc["prefix"]["prov"] == "http://www.w3.org/ns/prov#"
    assert doc["prefix"]["ss"] == "https://scientificstate.org/ontology/"


def test_prov_json_entities():
    doc = ssv_to_prov_json(_make_ssv())
    entities = doc["entity"]
    assert "ss:data-ssv-prov-001" in entities
    assert "ss:result-ssv-prov-001" in entities
    assert "ss:ssv-ssv-prov-001" in entities


def test_prov_json_entity_types():
    doc = ssv_to_prov_json(_make_ssv())
    assert doc["entity"]["ss:data-ssv-prov-001"]["prov:type"] == "ss:RawData"
    assert doc["entity"]["ss:result-ssv-prov-001"]["prov:type"] == "ss:InferenceResult"
    assert doc["entity"]["ss:ssv-ssv-prov-001"]["prov:type"] == "ss:ScientificStateVector"


def test_prov_json_activity_classical():
    doc = ssv_to_prov_json(_make_ssv(), run=_make_run())
    activity = doc["activity"]["ss:run-run-prov-001"]
    assert activity["prov:type"] == "ss:ComputeRun"
    assert activity["ss:compute_class"] == "classical"
    assert activity["prov:startTime"] == "2026-04-04T12:00:00+00:00"


def test_prov_json_activity_quantum():
    doc = ssv_to_prov_json(_make_quantum_ssv(), run=_make_run())
    activity = doc["activity"]["ss:run-run-prov-001"]
    assert activity["prov:type"] == "ss:QuantumComputeRun"
    assert activity["ss:compute_class"] == "quantum_sim"


def test_prov_json_quantum_metadata_on_activity():
    doc = ssv_to_prov_json(_make_quantum_ssv(), run=_make_run())
    activity = doc["activity"]["ss:run-run-prov-001"]
    assert activity["ss:quantum_shots"] == 1024
    assert activity["ss:quantum_circuit_depth"] == 3
    assert activity["ss:quantum_qubit_count"] == 2


def test_prov_json_agents():
    doc = ssv_to_prov_json(_make_ssv())
    assert "ss:researcher-researcher-1" in doc["agent"]
    assert "ss:module-polymer_science" in doc["agent"]


def test_prov_json_was_generated_by():
    doc = ssv_to_prov_json(_make_ssv())
    wgb = doc["wasGeneratedBy"]
    assert len(wgb) == 2  # result + ssv


def test_prov_json_used():
    doc = ssv_to_prov_json(_make_ssv())
    used = doc["used"]
    assert len(used) == 1
    key = list(used.keys())[0]
    assert used[key]["prov:entity"] == "ss:data-ssv-prov-001"


def test_prov_json_was_attributed_to():
    doc = ssv_to_prov_json(_make_ssv())
    wat = doc["wasAttributedTo"]
    assert len(wat) == 1
    key = list(wat.keys())[0]
    assert wat[key]["prov:agent"] == "ss:researcher-researcher-1"


def test_prov_json_no_run():
    doc = ssv_to_prov_json(_make_ssv())
    # Activity uses ssv_id when no run
    assert "ss:run-ssv-prov-001" in doc["activity"]


# ── PROV-N string ────────────────────────────────────────────────────────────

def test_prov_n_is_string():
    result = ssv_to_prov_n(_make_ssv())
    assert isinstance(result, str)


def test_prov_n_starts_with_document():
    result = ssv_to_prov_n(_make_ssv())
    assert result.startswith("document")


def test_prov_n_ends_with_end_document():
    result = ssv_to_prov_n(_make_ssv())
    assert result.strip().endswith("endDocument")


def test_prov_n_has_prefixes():
    result = ssv_to_prov_n(_make_ssv())
    assert "prefix ss" in result
    assert "prefix prov" in result


def test_prov_n_has_entities():
    result = ssv_to_prov_n(_make_ssv())
    assert "entity(ss:data-ssv-prov-001" in result
    assert "entity(ss:result-ssv-prov-001" in result
    assert "entity(ss:ssv-ssv-prov-001" in result


def test_prov_n_has_activity():
    result = ssv_to_prov_n(_make_ssv(), run=_make_run())
    assert "activity(ss:run-run-prov-001" in result


def test_prov_n_quantum_type():
    result = ssv_to_prov_n(_make_quantum_ssv(), run=_make_run())
    assert "ss:QuantumComputeRun" in result


def test_prov_n_classical_type():
    result = ssv_to_prov_n(_make_ssv(), run=_make_run())
    assert "ss:ComputeRun" in result
    assert "ss:QuantumComputeRun" not in result


def test_prov_n_has_relations():
    result = ssv_to_prov_n(_make_ssv())
    assert "wasGeneratedBy" in result
    assert "used" in result
    assert "wasAttributedTo" in result


def test_prov_n_has_agents():
    result = ssv_to_prov_n(_make_ssv())
    assert "agent(ss:researcher-researcher-1" in result
    assert "agent(ss:module-polymer_science" in result
