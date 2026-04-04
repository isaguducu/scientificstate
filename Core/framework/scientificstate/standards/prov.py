"""
W3C PROV mapping — SSV + run → PROV-O graph.

PROV-DM model:
  Entity  — data (SSV D component, result R)
  Activity — run (computation)
  Agent   — researcher / module

Export formats:
  PROV-JSON — machine-readable (prov namespace compliant)
  PROV-N    — human-readable notation string

Quantum runs: prov:type = "ss:QuantumComputeRun"

Pure function: no I/O, no database, no network.
"""
from __future__ import annotations


_PREFIX_PROV = "prov"
_PREFIX_SS = "ss"
_NS_PROV = "http://www.w3.org/ns/prov#"
_NS_SS = "https://scientificstate.org/ontology/"


def ssv_to_prov_json(ssv: dict, run: dict | None = None) -> dict:
    """Convert SSV + optional run to a PROV-JSON document.

    Args:
        ssv: SSV dict (keys: id, d, i, a, t, r, u, v, p)
        run: optional ComputeRun dict (run_id, domain_id, method_id, status, started_at, finished_at)

    Returns:
        PROV-JSON document as dict following the W3C PROV-JSON serialization.
    """
    ssv_id = ssv.get("id", "unknown")
    p = ssv.get("p", {})
    ew = p.get("execution_witness", {})
    compute_class = ew.get("compute_class", "classical")

    doc: dict = {
        "prefix": {
            _PREFIX_PROV: _NS_PROV,
            _PREFIX_SS: _NS_SS,
        },
        "entity": {},
        "activity": {},
        "agent": {},
        "wasGeneratedBy": {},
        "used": {},
        "wasAttributedTo": {},
    }

    # ── Entities ─────────────────────────────────────────────────────────
    d = ssv.get("d", {})
    data_entity_id = f"ss:data-{ssv_id}"
    doc["entity"][data_entity_id] = {
        "prov:type": "ss:RawData",
        "ss:domain": d.get("domain", ""),
        "ss:ref": d.get("ref", ""),
    }

    result_entity_id = f"ss:result-{ssv_id}"
    r = ssv.get("r", {})
    doc["entity"][result_entity_id] = {
        "prov:type": "ss:InferenceResult",
        "ss:method": r.get("method", ""),
        "ss:quantities": r.get("quantities", {}),
    }

    ssv_entity_id = f"ss:ssv-{ssv_id}"
    doc["entity"][ssv_entity_id] = {
        "prov:type": "ss:ScientificStateVector",
        "ss:version": ssv.get("version", 1),
    }

    # ── Activity (the compute run) ───────────────────────────────────────
    run_id = run.get("run_id", ssv_id) if run else ssv_id
    activity_id = f"ss:run-{run_id}"

    activity_attrs: dict = {}
    if compute_class in ("quantum_sim", "quantum_hw", "hybrid"):
        activity_attrs["prov:type"] = "ss:QuantumComputeRun"
    else:
        activity_attrs["prov:type"] = "ss:ComputeRun"

    activity_attrs["ss:compute_class"] = compute_class
    activity_attrs["ss:backend_id"] = ew.get("backend_id", "unknown")

    if run:
        if run.get("started_at"):
            activity_attrs["prov:startTime"] = str(run["started_at"])
        if run.get("finished_at"):
            activity_attrs["prov:endTime"] = str(run["finished_at"])
        activity_attrs["ss:status"] = run.get("status", "")

    # Quantum metadata on activity
    qm = p.get("quantum_metadata")
    if qm and isinstance(qm, dict):
        for k, val in qm.items():
            activity_attrs[f"ss:quantum_{k}"] = val

    doc["activity"][activity_id] = activity_attrs

    # ── Agent ────────────────────────────────────────────────────────────
    researcher_id = p.get("researcher_id", "")
    if researcher_id:
        agent_id = f"ss:researcher-{researcher_id}"
    else:
        agent_id = "ss:researcher-unknown"
    doc["agent"][agent_id] = {
        "prov:type": "prov:Person",
    }

    domain_id = run.get("domain_id", d.get("domain", "unknown")) if run else d.get("domain", "unknown")
    module_agent_id = f"ss:module-{domain_id}"
    doc["agent"][module_agent_id] = {
        "prov:type": "prov:SoftwareAgent",
        "ss:domain_id": domain_id,
    }

    # ── Relations ────────────────────────────────────────────────────────
    doc["wasGeneratedBy"][f"_:wgb-result-{ssv_id}"] = {
        "prov:entity": result_entity_id,
        "prov:activity": activity_id,
    }
    doc["wasGeneratedBy"][f"_:wgb-ssv-{ssv_id}"] = {
        "prov:entity": ssv_entity_id,
        "prov:activity": activity_id,
    }

    doc["used"][f"_:used-{ssv_id}"] = {
        "prov:activity": activity_id,
        "prov:entity": data_entity_id,
    }

    doc["wasAttributedTo"][f"_:wat-{ssv_id}"] = {
        "prov:entity": ssv_entity_id,
        "prov:agent": agent_id,
    }

    return doc


def ssv_to_prov_n(ssv: dict, run: dict | None = None) -> str:
    """Convert SSV + optional run to PROV-N notation string.

    Args:
        ssv: SSV dict
        run: optional ComputeRun dict

    Returns:
        PROV-N string representation.
    """
    ssv_id = ssv.get("id", "unknown")
    p = ssv.get("p", {})
    d = ssv.get("d", {})
    ew = p.get("execution_witness", {})
    compute_class = ew.get("compute_class", "classical")

    lines: list[str] = [
        "document",
        f'  prefix ss <{_NS_SS}>',
        f'  prefix prov <{_NS_PROV}>',
        "",
    ]

    # Entities
    lines.append(f'  entity(ss:data-{ssv_id}, [prov:type="ss:RawData"])')
    lines.append(f'  entity(ss:result-{ssv_id}, [prov:type="ss:InferenceResult"])')
    lines.append(f'  entity(ss:ssv-{ssv_id}, [prov:type="ss:ScientificStateVector"])')
    lines.append("")

    # Activity
    run_id = run.get("run_id", ssv_id) if run else ssv_id
    if compute_class in ("quantum_sim", "quantum_hw", "hybrid"):
        prov_type = "ss:QuantumComputeRun"
    else:
        prov_type = "ss:ComputeRun"

    start_time = ""
    end_time = ""
    if run:
        start_time = str(run.get("started_at", ""))
        end_time = str(run.get("finished_at", ""))

    lines.append(
        f'  activity(ss:run-{run_id}, {start_time}, {end_time}, [prov:type="{prov_type}"])'
    )
    lines.append("")

    # Agents
    researcher_id = p.get("researcher_id", "unknown")
    domain_id = run.get("domain_id", d.get("domain", "unknown")) if run else d.get("domain", "unknown")
    lines.append(f'  agent(ss:researcher-{researcher_id}, [prov:type="prov:Person"])')
    lines.append(f'  agent(ss:module-{domain_id}, [prov:type="prov:SoftwareAgent"])')
    lines.append("")

    # Relations
    lines.append(f"  wasGeneratedBy(ss:result-{ssv_id}, ss:run-{run_id})")
    lines.append(f"  wasGeneratedBy(ss:ssv-{ssv_id}, ss:run-{run_id})")
    lines.append(f"  used(ss:run-{run_id}, ss:data-{ssv_id})")
    lines.append(f"  wasAttributedTo(ss:ssv-{ssv_id}, ss:researcher-{researcher_id})")
    lines.append("")
    lines.append("endDocument")

    return "\n".join(lines)
