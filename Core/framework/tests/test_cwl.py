"""CWL workflow portability tests — valid YAML, v1.2 compliance."""

import json

from scientificstate.standards.cwl import pipeline_to_cwl, pipeline_to_cwl_yaml


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_manifest(**overrides) -> dict:
    manifest = {
        "method_id": "kmd_analysis",
        "name": "KMD Analysis",
        "parameters": {"resolution": 0.001, "range": "100-500"},
        "required_data_types": ["mass_spec_gcms"],
    }
    manifest.update(overrides)
    return manifest


def _make_ssv() -> dict:
    return {
        "id": "ssv-cwl-001",
        "t": [
            {"name": "kmd_analysis", "algorithm": "kmd", "parameters": {"resolution": 0.001}, "software_version": "1.0"},
            {"name": "pdi_calc", "algorithm": "pdi", "parameters": {}, "software_version": "1.0"},
        ],
    }


# ── CWL dict structure ──────────────────────────────────────────────────────

def test_cwl_has_class_workflow():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis")
    assert doc["class"] == "Workflow"


def test_cwl_version():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis")
    assert doc["cwlVersion"] == "v1.2"


def test_cwl_has_label():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis")
    assert "polymer_science" in doc["label"]
    assert "kmd_analysis" in doc["label"]


def test_cwl_has_inputs():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis", method_manifest=_make_manifest())
    inputs = doc["inputs"]
    assert "dataset_ref" in inputs
    assert "assumptions" in inputs
    assert inputs["dataset_ref"]["type"] == "File"
    assert inputs["assumptions"]["type"] == "string"


def test_cwl_method_parameters_as_inputs():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis", method_manifest=_make_manifest())
    inputs = doc["inputs"]
    assert "resolution" in inputs
    assert inputs["resolution"]["type"] == "float"
    assert inputs["resolution"]["default"] == 0.001
    assert "range" in inputs
    assert inputs["range"]["type"] == "string"


def test_cwl_has_outputs():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis")
    outputs = doc["outputs"]
    assert "ssv_output" in outputs
    assert "claim_output" in outputs
    assert outputs["ssv_output"]["type"] == "File"


def test_cwl_has_steps():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis", method_manifest=_make_manifest())
    steps = doc["steps"]
    assert "execute" in steps
    step = steps["execute"]
    assert step["run"]["class"] == "CommandLineTool"
    assert step["run"]["baseCommand"] == ["scientificstate-run"]


def test_cwl_step_arguments():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis")
    step = doc["steps"]["execute"]
    args = step["run"]["arguments"]
    assert "--domain=polymer_science" in args
    assert "--method=kmd_analysis" in args


def test_cwl_requirements():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis")
    assert "InlineJavascriptRequirement" in doc["requirements"]


def test_cwl_enriched_with_ssv():
    doc = pipeline_to_cwl("polymer_science", "kmd_analysis", ssv=_make_ssv())
    assert "2 step(s)" in doc["doc"]


# ── CWL YAML string ─────────────────────────────────────────────────────────

def test_cwl_yaml_is_string():
    result = pipeline_to_cwl_yaml("polymer_science", "kmd_analysis")
    assert isinstance(result, str)


def test_cwl_yaml_contains_cwl_version():
    result = pipeline_to_cwl_yaml("polymer_science", "kmd_analysis")
    assert "v1.2" in result


def test_cwl_yaml_contains_workflow():
    result = pipeline_to_cwl_yaml("polymer_science", "kmd_analysis")
    assert "Workflow" in result


def test_cwl_yaml_valid_parse():
    """YAML output can be parsed back to a dict."""
    yaml_str = pipeline_to_cwl_yaml("polymer_science", "kmd_analysis")
    try:
        import yaml
        parsed = yaml.safe_load(yaml_str)
        assert parsed["cwlVersion"] == "v1.2"
        assert parsed["class"] == "Workflow"
    except ImportError:
        # If pyyaml not installed, output is JSON
        parsed = json.loads(yaml_str)
        assert parsed["cwlVersion"] == "v1.2"


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_cwl_no_manifest():
    doc = pipeline_to_cwl("test_domain", "test_method")
    assert doc["class"] == "Workflow"
    assert "dataset_ref" in doc["inputs"]


def test_cwl_boolean_parameter():
    manifest = _make_manifest(parameters={"verbose": True})
    doc = pipeline_to_cwl("test", "test", method_manifest=manifest)
    assert doc["inputs"]["verbose"]["type"] == "boolean"


def test_cwl_int_parameter():
    manifest = _make_manifest(parameters={"max_iter": 100})
    doc = pipeline_to_cwl("test", "test", method_manifest=manifest)
    assert doc["inputs"]["max_iter"]["type"] == "int"
