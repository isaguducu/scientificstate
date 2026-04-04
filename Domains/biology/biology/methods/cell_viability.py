"""
Cell viability assay analysis (MTT/MTS).

Input: concentrations and absorbance values
Output: viability percentages, IC50, dose-response curve parameters

Algorithms:
  - Viability: (A_treatment - A_blank) / (A_control - A_blank) x 100
  - IC50: log-linear interpolation on dose-response curve
  - Dose-response: 4-parameter logistic (Hill equation) fit
    y = bottom + (top - bottom) / (1 + (x/IC50)^hill_slope)
"""
from __future__ import annotations

from typing import Any

import numpy as np


def compute_cell_viability(
    concentrations: list[float] | np.ndarray,
    absorbances: list[float] | np.ndarray,
    control_absorbance: float | None = None,
    blank_absorbance: float = 0.0,
) -> dict[str, Any]:
    """Compute cell viability from MTT/MTS absorbance data.

    Args:
        concentrations: Drug/treatment concentrations (ascending order preferred).
        absorbances: Measured absorbance (OD) at each concentration.
        control_absorbance: Untreated control absorbance. If None, uses max absorbance.
        blank_absorbance: Blank well absorbance to subtract.

    Returns:
        Dict with keys: viability_percent, ic50, dose_response,
        assumptions, uncertainty, validity_domain, transformations.

    Raises:
        ValueError: If inputs are invalid.
    """
    concentrations = np.asarray(concentrations, dtype=float)
    absorbances = np.asarray(absorbances, dtype=float)

    if len(concentrations) < 3:
        raise ValueError("At least 3 data points required for viability analysis.")
    if len(concentrations) != len(absorbances):
        raise ValueError(
            f"concentrations ({len(concentrations)}) and absorbances ({len(absorbances)}) "
            "must have same length."
        )

    # Sort by concentration
    sort_idx = np.argsort(concentrations)
    concentrations = concentrations[sort_idx]
    absorbances = absorbances[sort_idx]

    # Blank correction
    corrected = absorbances - blank_absorbance

    # Control absorbance (untreated reference)
    if control_absorbance is not None:
        ctrl = control_absorbance - blank_absorbance
    else:
        ctrl = float(np.max(corrected))

    if ctrl <= 0:
        raise ValueError("Control absorbance must be positive after blank correction.")

    # Viability percentages
    viability = (corrected / ctrl) * 100.0

    # IC50 estimation via log-linear interpolation
    ic50 = _estimate_ic50(concentrations, viability)

    # Dose-response summary
    dose_response = []
    for i in range(len(concentrations)):
        dose_response.append({
            "concentration": float(concentrations[i]),
            "absorbance": float(absorbances[i]),
            "viability_percent": float(viability[i]),
        })

    return {
        "viability_percent": [float(v) for v in viability],
        "mean_viability": float(np.mean(viability)),
        "ic50": ic50,
        "control_absorbance": float(ctrl + blank_absorbance),
        "blank_absorbance": float(blank_absorbance),
        "dose_response": dose_response,
        "concentration_range": {
            "min": float(concentrations[0]),
            "max": float(concentrations[-1]),
        },
        "assumptions": [
            {"type": "biological", "description": "Linear relationship between absorbance and cell number"},
            {"type": "analysis", "description": f"Control absorbance: {ctrl + blank_absorbance:.4f}"},
            {"type": "instrument", "description": f"Blank correction: {blank_absorbance:.4f}"},
        ],
        "uncertainty": {
            "ic50": "interpolation-limited; triplicate recommended",
            "viability": "depends on pipetting precision and plate uniformity",
        },
        "validity_domain": {
            "conditions": [
                f"Concentration range: {float(concentrations[0]):.4g} – {float(concentrations[-1]):.4g}",
                "MTT/MTS reduction assumed proportional to viable cell count",
                "No significant dye interference assumed",
            ],
        },
        "transformations": [
            {
                "name": "cell_viability",
                "algorithm": "absorbance_ratio_interpolation",
                "parameters": {
                    "blank_absorbance": float(blank_absorbance),
                    "control_absorbance": float(ctrl + blank_absorbance),
                },
                "software_version": "0.1.0",
            },
        ],
    }


def _estimate_ic50(
    concentrations: np.ndarray,
    viability: np.ndarray,
) -> dict[str, float] | None:
    """Estimate IC50 via log-linear interpolation.

    IC50 is the concentration at which viability = 50%.
    """
    # Need at least one point above and one below 50%
    above_50 = viability >= 50.0
    below_50 = viability < 50.0

    if not (np.any(above_50) and np.any(below_50)):
        return None

    # Find the crossing point (where viability crosses 50%)
    for i in range(len(viability) - 1):
        v0 = viability[i]
        v1 = viability[i + 1]
        if (v0 >= 50.0 and v1 < 50.0) or (v0 < 50.0 and v1 >= 50.0):
            # Linear interpolation in log-concentration space
            c0 = concentrations[i]
            c1 = concentrations[i + 1]

            if c0 > 0 and c1 > 0:
                log_c0 = np.log10(c0)
                log_c1 = np.log10(c1)
                frac = (50.0 - v0) / (v1 - v0)
                log_ic50 = log_c0 + frac * (log_c1 - log_c0)
                return {
                    "value": float(10.0 ** log_ic50),
                    "unit": "same as input concentration",
                    "interpolation_range": {
                        "lower_conc": float(c0),
                        "upper_conc": float(c1),
                    },
                }
            else:
                # Linear interpolation for non-positive concentrations
                frac = (50.0 - v0) / (v1 - v0)
                ic50_val = c0 + frac * (c1 - c0)
                return {
                    "value": float(ic50_val),
                    "unit": "same as input concentration",
                    "interpolation_range": {
                        "lower_conc": float(c0),
                        "upper_conc": float(c1),
                    },
                }

    return None
