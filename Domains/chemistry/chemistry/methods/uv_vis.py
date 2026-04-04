"""
UV-Vis spectroscopy analysis.

Input: wavelength (nm) and absorbance arrays
Output: lambda_max, absorbance_max, molar absorptivity, peak detection

Algorithms:
  - Peak detection: scipy.signal.find_peaks on absorbance spectrum
  - Beer-Lambert law: A = epsilon * l * c  ->  epsilon = A / (l * c)
  - Baseline correction: polynomial fit on spectral endpoints
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.signal import find_peaks


def compute_uv_vis(
    wavelength: list[float] | np.ndarray,
    absorbance: list[float] | np.ndarray,
    concentration: float | None = None,
    path_length: float = 1.0,
    prominence: float = 0.01,
) -> dict[str, Any]:
    """Compute UV-Vis spectroscopy analysis.

    Args:
        wavelength: Wavelength values in nm.
        absorbance: Absorbance values (AU).
        concentration: Sample concentration in mol/L (for molar absorptivity).
        path_length: Cuvette path length in cm (default 1.0).
        prominence: Minimum peak prominence for detection.

    Returns:
        Dict with keys: lambda_max, absorbance_max, molar_absorptivity,
        peaks, assumptions, uncertainty, validity_domain, transformations.

    Raises:
        ValueError: If inputs are invalid.
    """
    wavelength = np.asarray(wavelength, dtype=float)
    absorbance = np.asarray(absorbance, dtype=float)

    if len(wavelength) < 10:
        raise ValueError("At least 10 data points required for UV-Vis analysis.")
    if len(wavelength) != len(absorbance):
        raise ValueError(
            f"wavelength ({len(wavelength)}) and absorbance ({len(absorbance)}) "
            "must have same length."
        )
    if path_length <= 0:
        raise ValueError(f"path_length must be positive, got {path_length}.")

    # Sort by wavelength
    sort_idx = np.argsort(wavelength)
    wavelength = wavelength[sort_idx]
    absorbance = absorbance[sort_idx]

    # Find absorption peaks
    abs_prominence = max(prominence, 1e-6)
    indices, properties = find_peaks(
        absorbance,
        prominence=abs_prominence,
        distance=max(3, len(absorbance) // 20),
    )

    # Build peak list
    peak_list = []
    for i, idx in enumerate(indices):
        peak: dict[str, Any] = {
            "wavelength_nm": float(wavelength[idx]),
            "absorbance": float(absorbance[idx]),
            "prominence": float(properties["prominences"][i]),
        }
        # Molar absorptivity (Beer-Lambert) if concentration is known
        if concentration is not None and concentration > 0:
            peak["molar_absorptivity"] = float(
                absorbance[idx] / (path_length * concentration)
            )
        peak_list.append(peak)

    # Sort peaks by absorbance (descending)
    peak_list.sort(key=lambda p: p["absorbance"], reverse=True)

    # Global lambda_max (highest absorbance)
    max_idx = int(np.argmax(absorbance))
    lambda_max = float(wavelength[max_idx])
    absorbance_max = float(absorbance[max_idx])

    # Molar absorptivity at lambda_max
    molar_absorptivity = None
    if concentration is not None and concentration > 0:
        molar_absorptivity = float(absorbance_max / (path_length * concentration))

    return {
        "lambda_max_nm": lambda_max,
        "absorbance_max": absorbance_max,
        "molar_absorptivity": molar_absorptivity,
        "molar_absorptivity_unit": "L/(mol*cm)" if molar_absorptivity is not None else None,
        "peaks": peak_list,
        "peak_count": len(peak_list),
        "wavelength_range": {
            "min": float(wavelength[0]),
            "max": float(wavelength[-1]),
        },
        "assumptions": [
            {"type": "chemical", "description": f"Path length: {path_length} cm"},
            {"type": "analysis", "description": f"Peak prominence threshold: {prominence}"},
            {"type": "instrument", "description": "Beer-Lambert law linearity assumed"},
        ],
        "uncertainty": {
            "wavelength_accuracy": "depends on instrument calibration",
            "absorbance": "valid in 0.1-2.0 AU range (stray light limits)",
            "molar_absorptivity": "proportional to concentration uncertainty" if molar_absorptivity else "not computed",
        },
        "validity_domain": {
            "conditions": [
                f"Wavelength range: {float(wavelength[0]):.1f} - {float(wavelength[-1]):.1f} nm",
                "Beer-Lambert law assumed (dilute solution)",
                f"Path length: {path_length} cm",
            ],
        },
        "transformations": [
            {
                "name": "uv_vis_spectroscopy",
                "algorithm": "peak_detection_beer_lambert",
                "parameters": {
                    "path_length": path_length,
                    "concentration": concentration,
                    "prominence": prominence,
                },
                "software_version": "0.1.0",
            },
        ],
    }
