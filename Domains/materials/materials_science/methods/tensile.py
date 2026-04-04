"""
Tensile test analysis — stress-strain curve processing.

Input: strain (mm/mm or %) and stress (MPa) arrays
Output: Young's modulus, yield strength (0.2% offset), UTS, elongation at break

Core equations:
  Young's modulus: E = σ/ε (slope of elastic region via linear regression)
  Yield strength: 0.2% offset method — intersection of stress-strain with
    a line parallel to elastic slope, offset by 0.002 strain
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats


def compute_tensile(
    strain: list[float] | np.ndarray,
    stress: list[float] | np.ndarray,
    offset_pct: float = 0.002,
    elastic_range_pct: float = 0.05,
) -> dict[str, Any]:
    """Compute tensile test properties from stress-strain data.

    Args:
        strain: Engineering strain values (dimensionless, e.g. mm/mm).
        stress: Engineering stress values in MPa.
        offset_pct: Strain offset for yield strength determination (default 0.2% = 0.002).
        elastic_range_pct: Maximum strain to consider for elastic region regression.

    Returns:
        Dict with keys: youngs_modulus, yield_strength, ultimate_tensile_strength,
        elongation_at_break, assumptions, uncertainty, validity_domain, transformations.

    Raises:
        ValueError: If inputs are invalid or insufficient.
    """
    strain = np.asarray(strain, dtype=float)
    stress = np.asarray(stress, dtype=float)

    if len(strain) < 5:
        raise ValueError("At least 5 data points required for tensile analysis.")
    if len(strain) != len(stress):
        raise ValueError(
            f"strain ({len(strain)}) and stress ({len(stress)}) must have same length."
        )
    if offset_pct <= 0:
        raise ValueError(f"offset_pct must be positive, got {offset_pct}.")

    # Sort by strain if not already sorted
    sort_idx = np.argsort(strain)
    strain = strain[sort_idx]
    stress = stress[sort_idx]

    # 1. Young's modulus — linear regression on elastic region
    elastic_mask = strain <= elastic_range_pct
    if np.sum(elastic_mask) < 2:
        # Fall back to first 10% of data points
        n_elastic = max(2, len(strain) // 10)
        elastic_mask = np.zeros(len(strain), dtype=bool)
        elastic_mask[:n_elastic] = True

    slope, intercept, r_value, p_value, std_err = stats.linregress(
        strain[elastic_mask], stress[elastic_mask]
    )
    youngs_modulus = float(slope)  # MPa
    r_squared = float(r_value ** 2)

    # 2. Yield strength — 0.2% offset method
    # Offset line: σ_offset = E × (ε - offset_pct)
    offset_stress = youngs_modulus * (strain - offset_pct)

    # Find intersection with the actual stress-strain curve
    diff = stress - offset_stress
    yield_strength = None
    yield_strain = None

    # Find where diff changes sign (from positive to negative)
    sign_changes = np.where(np.diff(np.sign(diff)))[0]
    for idx in sign_changes:
        if strain[idx] > offset_pct:
            # Linear interpolation between idx and idx+1
            frac = diff[idx] / (diff[idx] - diff[idx + 1])
            yield_strain = float(strain[idx] + frac * (strain[idx + 1] - strain[idx]))
            yield_strength = float(stress[idx] + frac * (stress[idx + 1] - stress[idx]))
            break

    if yield_strength is None:
        # Fallback: use stress at offset_pct strain
        closest = np.argmin(np.abs(strain - offset_pct))
        yield_strength = float(stress[closest])
        yield_strain = float(strain[closest])

    # 3. Ultimate tensile strength
    uts_idx = int(np.argmax(stress))
    ultimate_tensile_strength = float(stress[uts_idx])
    uts_strain = float(strain[uts_idx])

    # 4. Elongation at break (last data point)
    elongation_at_break = float(strain[-1])
    stress_at_break = float(stress[-1])

    # 5. Toughness (area under stress-strain curve)
    toughness = float(np.trapezoid(stress, strain))

    return {
        "youngs_modulus": youngs_modulus,
        "youngs_modulus_unit": "MPa",
        "yield_strength": yield_strength,
        "yield_strain": yield_strain,
        "yield_strength_unit": "MPa",
        "ultimate_tensile_strength": ultimate_tensile_strength,
        "uts_strain": uts_strain,
        "uts_unit": "MPa",
        "elongation_at_break": elongation_at_break,
        "stress_at_break": stress_at_break,
        "toughness": toughness,
        "toughness_unit": "MJ/m³",
        "elastic_modulus_r_squared": r_squared,
        "assumptions": [
            {"type": "mechanical", "description": f"Elastic region: strain ≤ {elastic_range_pct}"},
            {"type": "mechanical", "description": f"Yield offset: {offset_pct * 100:.1f}%"},
            {"type": "measurement", "description": "Engineering stress-strain (not true)"},
        ],
        "uncertainty": {
            "youngs_modulus": {
                "std_error": float(std_err),
                "r_squared": r_squared,
            },
            "yield_strength": "determined by 0.2% offset intersection",
        },
        "validity_domain": {
            "conditions": [
                f"Strain range: 0 – {elongation_at_break:.4f}",
                "Engineering stress-strain assumed",
                f"Elastic region defined as strain ≤ {elastic_range_pct}",
            ],
        },
        "transformations": [
            {
                "name": "tensile_test",
                "algorithm": "linear_regression_offset_method",
                "parameters": {
                    "offset_pct": offset_pct,
                    "elastic_range_pct": elastic_range_pct,
                },
                "software_version": "0.1.0",
            },
        ],
    }
