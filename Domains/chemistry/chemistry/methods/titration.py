"""
Acid-base titration analysis.

Input: volume of titrant added (mL) and pH readings
Output: equivalence point, pH at equivalence, analyte concentration

Algorithms:
  - First derivative: max of |dpH/dV| -> equivalence point
  - Second derivative: zero crossing of d2pH/dV2 -> refined equivalence
  - Analyte concentration: C_a * V_a = C_t * V_eq (stoichiometric)
"""
from __future__ import annotations

from typing import Any

import numpy as np


def compute_titration(
    volume: list[float] | np.ndarray,
    ph: list[float] | np.ndarray,
    titrant_concentration: float | None = None,
    analyte_volume: float | None = None,
) -> dict[str, Any]:
    """Compute acid-base titration analysis.

    Args:
        volume: Volume of titrant added in mL.
        ph: pH readings at each volume.
        titrant_concentration: Molarity of titrant (mol/L).
        analyte_volume: Volume of analyte solution in mL.

    Returns:
        Dict with keys: equivalence_point, ph_at_equivalence,
        analyte_concentration, half_equivalence, pka_estimate,
        assumptions, uncertainty, validity_domain, transformations.

    Raises:
        ValueError: If inputs are invalid.
    """
    volume = np.asarray(volume, dtype=float)
    ph = np.asarray(ph, dtype=float)

    if len(volume) < 5:
        raise ValueError("At least 5 data points required for titration analysis.")
    if len(volume) != len(ph):
        raise ValueError(
            f"volume ({len(volume)}) and ph ({len(ph)}) must have same length."
        )

    # Sort by volume
    sort_idx = np.argsort(volume)
    volume = volume[sort_idx]
    ph = ph[sort_idx]

    # First derivative dpH/dV
    dv = np.gradient(volume)
    dv[dv == 0] = np.finfo(float).eps
    dph_dv = np.gradient(ph) / dv

    # Equivalence point: maximum of |dpH/dV|
    # Ignore first and last 5% to avoid edge artifacts
    n = len(dph_dv)
    margin = max(1, n // 20)
    inner = np.abs(dph_dv[margin:-margin])

    if len(inner) == 0:
        eq_idx = int(np.argmax(np.abs(dph_dv)))
    else:
        eq_idx = int(np.argmax(inner)) + margin

    equivalence_volume = float(volume[eq_idx])
    ph_at_equivalence = float(ph[eq_idx])

    # Second derivative for refinement
    d2ph_dv2 = np.gradient(dph_dv) / dv
    second_deriv_info = _refine_equivalence(volume, d2ph_dv2, eq_idx)
    if second_deriv_info is not None:
        equivalence_volume = second_deriv_info["volume"]

    # Half-equivalence point (pKa estimation)
    half_eq_volume = equivalence_volume / 2.0
    pka_estimate = _estimate_pka(volume, ph, half_eq_volume)

    # Analyte concentration calculation
    analyte_concentration = None
    if titrant_concentration is not None and analyte_volume is not None and analyte_volume > 0:
        analyte_concentration = float(
            titrant_concentration * equivalence_volume / analyte_volume
        )

    # Titration curve data
    titration_curve = [
        {"volume_ml": float(volume[i]), "ph": float(ph[i])}
        for i in range(len(volume))
    ]

    return {
        "equivalence_point_ml": equivalence_volume,
        "ph_at_equivalence": ph_at_equivalence,
        "analyte_concentration_mol_l": analyte_concentration,
        "half_equivalence_ml": float(half_eq_volume),
        "pka_estimate": pka_estimate,
        "titration_curve": titration_curve,
        "max_dpH_dV": float(np.abs(dph_dv[eq_idx])),
        "volume_range": {
            "min": float(volume[0]),
            "max": float(volume[-1]),
        },
        "assumptions": [
            {"type": "chemical", "description": "Monoprotic acid-base reaction assumed"},
            {"type": "analysis", "description": "Equivalence point from first derivative maximum"},
            {"type": "instrument", "description": "pH electrode calibrated (pH 4, 7, 10)"},
        ],
        "uncertainty": {
            "equivalence_point": "depends on data density near inflection",
            "pka": "valid only for monoprotic weak acid/base" if pka_estimate else "not determined",
            "concentration": "propagated from titrant concentration and volume precision",
        },
        "validity_domain": {
            "conditions": [
                f"Volume range: {float(volume[0]):.2f} - {float(volume[-1]):.2f} mL",
                "Aqueous solution at room temperature assumed",
                "Monoprotic reaction assumed",
            ],
        },
        "transformations": [
            {
                "name": "titration",
                "algorithm": "derivative_equivalence_detection",
                "parameters": {
                    "titrant_concentration": titrant_concentration,
                    "analyte_volume": analyte_volume,
                },
                "software_version": "0.1.0",
            },
        ],
    }


def _refine_equivalence(
    volume: np.ndarray,
    d2ph_dv2: np.ndarray,
    approx_idx: int,
) -> dict[str, float] | None:
    """Refine equivalence point via second derivative zero crossing."""
    # Search in a window around approximate equivalence
    n = len(volume)
    window = max(3, n // 10)
    start = max(0, approx_idx - window)
    end = min(n - 1, approx_idx + window)

    segment = d2ph_dv2[start:end]
    if len(segment) < 3:
        return None

    # Find sign changes (zero crossings)
    for i in range(len(segment) - 1):
        if segment[i] * segment[i + 1] < 0:
            # Linear interpolation for exact crossing
            idx = start + i
            frac = abs(d2ph_dv2[idx]) / (abs(d2ph_dv2[idx]) + abs(d2ph_dv2[idx + 1]))
            refined_v = volume[idx] + frac * (volume[idx + 1] - volume[idx])
            return {"volume": float(refined_v)}

    return None


def _estimate_pka(
    volume: np.ndarray,
    ph: np.ndarray,
    half_eq_volume: float,
) -> float | None:
    """Estimate pKa from pH at half-equivalence point."""
    if half_eq_volume <= volume[0] or half_eq_volume >= volume[-1]:
        return None

    # Interpolate pH at half-equivalence volume
    pka = float(np.interp(half_eq_volume, volume, ph))
    return pka
