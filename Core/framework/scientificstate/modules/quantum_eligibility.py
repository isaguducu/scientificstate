"""
Quantum Eligibility — CMRE quantum eligibility assessment.

Evaluates whether a module method is eligible for quantum compute dispatch
and what constraints apply (classical baseline, translation fidelity).

Main_Source §9A.3: quantum runs are exploratory-only and require a classical
baseline reference before results feed the gate chain.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuantumEligibility:
    """Result of quantum eligibility assessment for a module method.

    eligible: True if the method declares quantum support.
    classical_baseline_required: True if a classical run must exist first.
    translation_fidelity_estimate: 0.0–1.0 confidence that the method's
        classical logic can be faithfully represented as a quantum circuit.
    branching_suggestion: recommended compute path ("classical", "quantum_sim",
        "quantum_hw", "hybrid", or "classical_only").
    reason: human-readable explanation of the assessment.
    """

    eligible: bool
    classical_baseline_required: bool = True
    translation_fidelity_estimate: float = 0.0
    branching_suggestion: str = "classical_only"
    reason: str = ""


def assess_quantum_eligibility(
    module_manifest: dict,
    method_id: str,
) -> QuantumEligibility:
    """Assess whether a module method is eligible for quantum compute.

    Args:
        module_manifest: module manifest dict containing methods and
            optional quantum_contract declarations.
        method_id: the specific method to assess.

    Returns:
        QuantumEligibility with eligibility status and constraints.
    """
    # Check for quantum_contract in manifest
    quantum_contract = module_manifest.get("quantum_contract") or {}
    supported_methods = quantum_contract.get("supported_methods") or []

    # Method must be explicitly listed in quantum_contract.supported_methods
    if method_id not in supported_methods:
        return QuantumEligibility(
            eligible=False,
            classical_baseline_required=True,
            translation_fidelity_estimate=0.0,
            branching_suggestion="classical_only",
            reason=f"Method '{method_id}' not listed in quantum_contract.supported_methods",
        )

    # Extract translation fidelity estimate if declared
    fidelity_map = quantum_contract.get("translation_fidelity") or {}
    fidelity = fidelity_map.get(method_id, 0.5)
    if not isinstance(fidelity, (int, float)):
        fidelity = 0.5
    fidelity = max(0.0, min(1.0, float(fidelity)))

    # Determine branching suggestion based on fidelity
    if fidelity >= 0.9:
        suggestion = "quantum_sim"
    elif fidelity >= 0.7:
        suggestion = "quantum_sim"
    elif fidelity >= 0.4:
        suggestion = "hybrid"
    else:
        suggestion = "classical_only"

    # Classical baseline is always required for quantum runs (Main_Source §9A.3)
    baseline_required = True

    return QuantumEligibility(
        eligible=True,
        classical_baseline_required=baseline_required,
        translation_fidelity_estimate=fidelity,
        branching_suggestion=suggestion,
        reason=f"Method '{method_id}' is quantum-eligible with fidelity {fidelity:.2f}",
    )
