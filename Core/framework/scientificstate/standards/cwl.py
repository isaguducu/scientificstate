"""
CWL workflow portability — pipeline → CWL v1.2 Workflow YAML.

Converts ScientificState pipeline definitions and run sequences
into CWL (Common Workflow Language) v1.2 compatible YAML documents.

CWL spec: https://www.commonwl.org/v1.2/

Pure function: no I/O, no database, no network.
Dependencies: pyyaml (for YAML serialization)
"""
from __future__ import annotations

import json


_CWL_VERSION = "v1.2"


def pipeline_to_cwl(
    domain_id: str,
    method_id: str,
    method_manifest: dict | None = None,
    ssv: dict | None = None,
) -> dict:
    """Convert a pipeline definition to a CWL Workflow document.

    Args:
        domain_id: domain module identifier
        method_id: method identifier within the domain
        method_manifest: optional method descriptor (parameters, data_types)
        ssv: optional SSV dict for enrichment (transforms, assumptions)

    Returns:
        CWL Workflow document as a dict (serialize with yaml.dump).
    """
    manifest = method_manifest or {}

    # Build inputs from method parameters
    inputs: dict = {
        "dataset_ref": {
            "type": "File",
            "doc": "Input dataset reference",
        },
        "assumptions": {
            "type": "string",
            "doc": "JSON-encoded assumptions list (P3)",
        },
    }

    # Add method-specific parameters
    params = manifest.get("parameters", {})
    if isinstance(params, dict):
        for param_name, default_val in params.items():
            cwl_type = _infer_cwl_type(default_val)
            inputs[param_name] = {
                "type": cwl_type,
                "doc": f"Method parameter: {param_name}",
            }
            if default_val is not None:
                inputs[param_name]["default"] = default_val

    # Build outputs
    outputs: dict = {
        "ssv_output": {
            "type": "File",
            "doc": "Scientific State Vector (JSON)",
            "outputSource": "execute/ssv_json",
        },
        "claim_output": {
            "type": "File",
            "doc": "Draft claim (JSON)",
            "outputSource": "execute/claim_json",
        },
    }

    # Build steps
    steps: dict = {
        "execute": {
            "run": _build_command_line_tool(domain_id, method_id, manifest),
            "in": {
                "dataset_ref": "dataset_ref",
                "assumptions": "assumptions",
            },
            "out": ["ssv_json", "claim_json"],
        },
    }

    # Add parameter bindings to step inputs
    for param_name in params:
        steps["execute"]["in"][param_name] = param_name

    doc: dict = {
        "cwlVersion": _CWL_VERSION,
        "class": "Workflow",
        "label": f"ScientificState: {domain_id}/{method_id}",
        "doc": f"CWL workflow for {domain_id} domain, method {method_id}",
        "requirements": {
            "InlineJavascriptRequirement": {},
        },
        "inputs": inputs,
        "outputs": outputs,
        "steps": steps,
    }

    # Enrich with SSV transform chain if available
    if ssv:
        transforms = ssv.get("t", [])
        if transforms:
            doc["doc"] += f"\nTransform chain: {len(transforms)} step(s)"

    return doc


def pipeline_to_cwl_yaml(
    domain_id: str,
    method_id: str,
    method_manifest: dict | None = None,
    ssv: dict | None = None,
) -> str:
    """Convert a pipeline definition to CWL YAML string.

    Args:
        domain_id: domain module identifier
        method_id: method identifier
        method_manifest: optional method descriptor
        ssv: optional SSV for enrichment

    Returns:
        CWL YAML string (valid YAML).
    """
    try:
        import yaml
        doc = pipeline_to_cwl(domain_id, method_id, method_manifest, ssv)
        return yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)
    except ImportError:
        # Fallback: JSON output if pyyaml not available
        doc = pipeline_to_cwl(domain_id, method_id, method_manifest, ssv)
        return json.dumps(doc, indent=2)


def _build_command_line_tool(domain_id: str, method_id: str, manifest: dict) -> dict:
    """Build an inline CWL CommandLineTool for the domain method."""
    tool_inputs: dict = {
        "dataset_ref": {
            "type": "File",
            "inputBinding": {"position": 1},
        },
        "assumptions": {
            "type": "string",
            "inputBinding": {"position": 2},
        },
    }

    params = manifest.get("parameters", {})
    if isinstance(params, dict):
        for idx, param_name in enumerate(params, start=3):
            tool_inputs[param_name] = {
                "type": _infer_cwl_type(params[param_name]),
                "inputBinding": {"position": idx},
            }

    return {
        "class": "CommandLineTool",
        "label": f"{domain_id}:{method_id}",
        "baseCommand": ["scientificstate-run"],
        "arguments": [
            f"--domain={domain_id}",
            f"--method={method_id}",
        ],
        "inputs": tool_inputs,
        "outputs": {
            "ssv_json": {
                "type": "File",
                "outputBinding": {"glob": "ssv_*.json"},
            },
            "claim_json": {
                "type": "File",
                "outputBinding": {"glob": "claim_*.json"},
            },
        },
    }


def _infer_cwl_type(value: object) -> str:
    """Infer CWL type from a Python value."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return "string"
