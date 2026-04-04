"""
RO-Crate v2 mapper — SSV → ro-crate-metadata.json (JSON-LD).

Mapping:
  SSV D → Dataset entity
  SSV I → instrument PropertyValue
  SSV A → assumptions as PropertyValue annotations
  SSV T → SoftwareApplication + actions
  SSV R → CreateAction outputs
  SSV U → uncertainty as custom properties
  SSV V → validity domains as spatial/temporal extents
  SSV P → PROV-O provenance statements (quantum metadata included)

conformsTo: https://w3id.org/ro/crate/1.2-DRAFT

Pure function: no I/O, no database, no network.
"""
from __future__ import annotations

from datetime import datetime, timezone


_ROCRATE_CONTEXT = "https://w3id.org/ro/crate/1.2-DRAFT/context"
_ROCRATE_CONFORMS_TO = "https://w3id.org/ro/crate/1.2-DRAFT"
_SS_NAMESPACE = "https://scientificstate.org/ontology/"


def ssv_to_rocrate(ssv: dict, run: dict | None = None) -> dict:
    """Convert an SSV dict to an RO-Crate v2 metadata document (JSON-LD).

    Args:
        ssv: SSV dict (keys: id, d, i, a, t, r, u, v, p)
        run: optional ComputeRun dict (adds timing/status metadata)

    Returns:
        RO-Crate metadata document as a dict (valid JSON-LD @graph structure).
    """
    ssv_id = ssv.get("id", "unknown")
    p = ssv.get("p", {})
    created_at = p.get("created_at", datetime.now(timezone.utc).isoformat())

    graph: list[dict] = []

    # ── Root dataset entity ──────────────────────────────────────────────
    root_dataset = {
        "@type": "Dataset",
        "@id": "./",
        "name": f"SSV {ssv_id}",
        "description": "Scientific State Vector exported as RO-Crate v2",
        "datePublished": created_at,
        "conformsTo": {"@id": _ROCRATE_CONFORMS_TO},
        "hasPart": [],
    }
    graph.append(root_dataset)

    # ── RO-Crate metadata descriptor ─────────────────────────────────────
    graph.append({
        "@type": "CreativeWork",
        "@id": "ro-crate-metadata.json",
        "about": {"@id": "./"},
        "conformsTo": {"@id": _ROCRATE_CONFORMS_TO},
    })

    # ── D: Dataset entity ────────────────────────────────────────────────
    d = ssv.get("d", {})
    dataset_entity = {
        "@type": "Dataset",
        "@id": f"#dataset-{ssv_id}",
        "name": f"Raw data for SSV {ssv_id}",
        "identifier": d.get("ref", ""),
        "additionalProperty": [
            _property_value("domain", d.get("domain", "")),
        ],
    }
    if d.get("metadata"):
        for k, val in d["metadata"].items():
            dataset_entity["additionalProperty"].append(_property_value(k, val))
    graph.append(dataset_entity)
    root_dataset["hasPart"].append({"@id": dataset_entity["@id"]})

    # ── I: Instrument ────────────────────────────────────────────────────
    inst = ssv.get("i", {})
    if inst.get("instrument_id"):
        instrument_entity = {
            "@type": "Instrument",
            "@id": f"#instrument-{inst['instrument_id']}",
            "name": inst["instrument_id"],
            "additionalProperty": [],
        }
        for field in ("resolution", "mode", "dynamic_range"):
            if inst.get(field):
                instrument_entity["additionalProperty"].append(
                    _property_value(field, inst[field])
                )
        graph.append(instrument_entity)

    # ── T: SoftwareApplication + CreateAction ────────────────────────────
    transforms = ssv.get("t", [])
    for idx, tr in enumerate(transforms):
        sw_id = f"#software-{idx}"
        sw_entity = {
            "@type": "SoftwareApplication",
            "@id": sw_id,
            "name": tr.get("name", f"transform-{idx}"),
            "softwareVersion": tr.get("software_version", ""),
            "additionalProperty": [],
        }
        params = tr.get("parameters", {})
        if isinstance(params, dict):
            for k, val in params.items():
                sw_entity["additionalProperty"].append(_property_value(k, val))
        graph.append(sw_entity)

        action_entity = {
            "@type": "CreateAction",
            "@id": f"#action-{idx}",
            "name": f"Execute {tr.get('algorithm', '')}",
            "instrument": {"@id": sw_id},
            "object": {"@id": dataset_entity["@id"]},
            "result": {"@id": f"#result-{ssv_id}"},
        }
        if run:
            action_entity["startTime"] = run.get("started_at", "")
            action_entity["endTime"] = run.get("finished_at", "")
        graph.append(action_entity)

    # ── R: Results as output entity ──────────────────────────────────────
    r = ssv.get("r", {})
    result_entity = {
        "@type": "PropertyValue",
        "@id": f"#result-{ssv_id}",
        "name": "Inference results",
        "additionalProperty": [],
    }
    quantities = r.get("quantities", {})
    if isinstance(quantities, dict):
        for k, val in quantities.items():
            result_entity["additionalProperty"].append(_property_value(k, val))
    graph.append(result_entity)
    root_dataset["hasPart"].append({"@id": result_entity["@id"]})

    # ── A: Assumptions as PropertyValue annotations ──────────────────────
    assumptions = ssv.get("a", [])
    for idx, assumption in enumerate(assumptions):
        a_id = f"#assumption-{idx}"
        a_entity = {
            "@type": "PropertyValue",
            "@id": a_id,
            "propertyID": f"{_SS_NAMESPACE}Assumption",
            "name": assumption.get("description", f"assumption-{idx}"),
            "value": assumption.get("type", ""),
        }
        if assumption.get("assumption_id"):
            a_entity["identifier"] = assumption["assumption_id"]
        graph.append(a_entity)
        root_dataset["hasPart"].append({"@id": a_id})

    # ── U: Uncertainty as custom properties ──────────────────────────────
    u = ssv.get("u", {})
    if u and any(u.get(k) for k in ("measurement_error", "confidence_intervals")):
        u_entity = {
            "@type": "PropertyValue",
            "@id": f"#uncertainty-{ssv_id}",
            "propertyID": f"{_SS_NAMESPACE}Uncertainty",
            "name": "Uncertainty model",
            "additionalProperty": [],
        }
        if isinstance(u.get("measurement_error"), dict):
            for k, val in u["measurement_error"].items():
                u_entity["additionalProperty"].append(
                    _property_value(f"measurement_error.{k}", val)
                )
        if u.get("propagation_method"):
            u_entity["additionalProperty"].append(
                _property_value("propagation_method", u["propagation_method"])
            )
        graph.append(u_entity)
        root_dataset["hasPart"].append({"@id": u_entity["@id"]})

    # ── V: Validity domain as spatial/temporal extents ────────────────────
    v = ssv.get("v", {})
    if v.get("conditions"):
        v_entity = {
            "@type": "PropertyValue",
            "@id": f"#validity-{ssv_id}",
            "propertyID": f"{_SS_NAMESPACE}ValidityDomain",
            "name": "Validity domain",
            "value": "; ".join(str(c) for c in v["conditions"]),
            "additionalProperty": [],
        }
        if v.get("exclusions"):
            for exc in v["exclusions"]:
                v_entity["additionalProperty"].append(
                    _property_value("exclusion", exc)
                )
        graph.append(v_entity)
        root_dataset["hasPart"].append({"@id": v_entity["@id"]})

    # ── P: Provenance (PROV-O statements, quantum metadata) ──────────────
    ew = p.get("execution_witness", {})
    prov_entity = {
        "@type": "PropertyValue",
        "@id": f"#provenance-{ssv_id}",
        "propertyID": f"{_SS_NAMESPACE}Provenance",
        "name": "Execution provenance",
        "additionalProperty": [
            _property_value("compute_class", ew.get("compute_class", "classical")),
            _property_value("backend_id", ew.get("backend_id", "unknown")),
        ],
    }

    # Quantum metadata from P field (W1 output)
    qm = p.get("quantum_metadata")
    if qm and isinstance(qm, dict):
        for k, val in qm.items():
            prov_entity["additionalProperty"].append(
                _property_value(f"quantum.{k}", val)
            )

    # Hybrid execution witnesses
    if p.get("execution_witnesses"):
        for widx, w in enumerate(p["execution_witnesses"]):
            if isinstance(w, dict):
                for k, val in w.items():
                    prov_entity["additionalProperty"].append(
                        _property_value(f"witness_{widx}.{k}", val)
                    )

    # Exploratory flag
    if p.get("exploratory"):
        prov_entity["additionalProperty"].append(
            _property_value("exploratory", True)
        )

    graph.append(prov_entity)
    root_dataset["hasPart"].append({"@id": prov_entity["@id"]})

    return {
        "@context": _ROCRATE_CONTEXT,
        "@graph": graph,
    }


def _property_value(name: str, value: object) -> dict:
    """Create a schema.org PropertyValue."""
    return {
        "@type": "PropertyValue",
        "name": name,
        "value": value,
    }
