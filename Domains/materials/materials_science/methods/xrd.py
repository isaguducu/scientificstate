"""
XRD (X-Ray Diffraction) analysis.

Input: 2θ vs intensity data
Output: peak positions, d-spacing (Bragg's law), crystal phases, lattice parameters

Core equations:
  Bragg's law: nλ = 2d·sin(θ)  →  d = λ / (2·sin(θ))
  where θ is half the 2θ angle, λ is X-ray wavelength (default Cu Kα = 1.5406 Å)
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.signal import find_peaks


def compute_xrd(
    two_theta: list[float] | np.ndarray,
    intensity: list[float] | np.ndarray,
    wavelength: float = 1.5406,
    prominence: float = 0.05,
    min_distance: int = 5,
) -> dict[str, Any]:
    """Compute XRD analysis: peak finding + Bragg's law d-spacing.

    Args:
        two_theta: 2θ angles in degrees.
        intensity: Corresponding intensity values.
        wavelength: X-ray wavelength in Ångströms (default: Cu Kα = 1.5406 Å).
        prominence: Minimum peak prominence as fraction of max intensity.
        min_distance: Minimum number of data points between peaks.

    Returns:
        Dict with keys: peaks, d_spacings, lattice_parameters, assumptions,
        uncertainty, validity_domain, transformations.

    Raises:
        ValueError: If inputs are invalid or empty.
    """
    two_theta = np.asarray(two_theta, dtype=float)
    intensity = np.asarray(intensity, dtype=float)

    if len(two_theta) < 3:
        raise ValueError("At least 3 data points required for XRD analysis.")
    if len(two_theta) != len(intensity):
        raise ValueError(
            f"two_theta ({len(two_theta)}) and intensity ({len(intensity)}) must have same length."
        )
    if wavelength <= 0:
        raise ValueError(f"Wavelength must be positive, got {wavelength}.")

    # Normalize intensity for peak finding
    max_intensity = np.max(intensity)
    if max_intensity <= 0:
        raise ValueError("All intensity values are zero or negative.")
    norm_intensity = intensity / max_intensity

    # Find peaks
    abs_prominence = prominence * max_intensity
    peak_indices, peak_properties = find_peaks(
        intensity,
        prominence=abs_prominence,
        distance=min_distance,
    )

    # Compute d-spacing via Bragg's law: d = λ / (2·sin(θ))
    peaks = []
    d_spacings = []
    for idx in peak_indices:
        theta_deg = two_theta[idx] / 2.0  # θ = 2θ/2
        theta_rad = math.radians(theta_deg)

        sin_theta = math.sin(theta_rad)
        if sin_theta <= 0:
            continue

        d = wavelength / (2.0 * sin_theta)
        d_spacings.append(d)

        # Peak position uncertainty: half the step size
        if idx > 0 and idx < len(two_theta) - 1:
            step = (two_theta[idx + 1] - two_theta[idx - 1]) / 2.0
        else:
            step = two_theta[1] - two_theta[0] if len(two_theta) > 1 else 0.01
        d_uncertainty = _d_spacing_uncertainty(theta_deg, step / 2.0, wavelength)

        peaks.append({
            "two_theta": float(two_theta[idx]),
            "intensity": float(intensity[idx]),
            "relative_intensity": float(norm_intensity[idx]),
            "d_spacing": float(d),
            "d_spacing_uncertainty": float(d_uncertainty),
            "peak_index": int(idx),
        })

    # Estimate lattice parameter (assuming cubic: a = d * sqrt(h²+k²+l²))
    # Use first 3 peaks for (1,0,0), (1,1,0), (1,1,1) assuming cubic
    lattice_params = _estimate_cubic_lattice(d_spacings)

    return {
        "peaks": peaks,
        "d_spacings": [float(d) for d in d_spacings],
        "peak_count": len(peaks),
        "lattice_parameters": lattice_params,
        "wavelength_used": wavelength,
        "assumptions": [
            {"type": "instrument", "description": f"Cu Kα wavelength = {wavelength} Å"},
            {"type": "crystallography", "description": "Bragg's law: nλ = 2d·sin(θ), n=1"},
        ],
        "uncertainty": {
            "peak_position": "half-step angular resolution",
            "d_spacing": "propagated from angular uncertainty via Bragg's law",
        },
        "validity_domain": {
            "conditions": [
                f"wavelength = {wavelength} Å",
                f"2θ range: {float(two_theta[0]):.1f}° – {float(two_theta[-1]):.1f}°",
            ],
        },
        "transformations": [
            {
                "name": "xrd_analysis",
                "algorithm": "peak_finding + bragg_law",
                "parameters": {
                    "wavelength": wavelength,
                    "prominence": prominence,
                    "min_distance": min_distance,
                },
                "software_version": "0.1.0",
            },
        ],
    }


def _d_spacing_uncertainty(theta_deg: float, delta_theta_deg: float, wavelength: float) -> float:
    """Propagate angular uncertainty to d-spacing uncertainty.

    d = λ / (2·sin(θ))
    δd/d = -cos(θ)/sin(θ) · δθ = -cot(θ) · δθ
    |δd| = d · |cot(θ)| · δθ_rad
    """
    theta_rad = math.radians(theta_deg)
    delta_theta_rad = math.radians(delta_theta_deg)

    sin_t = math.sin(theta_rad)
    if sin_t <= 0:
        return float("inf")

    d = wavelength / (2.0 * sin_t)
    cos_t = math.cos(theta_rad)
    return abs(d * (cos_t / sin_t) * delta_theta_rad)


def _estimate_cubic_lattice(d_spacings: list[float]) -> dict[str, Any]:
    """Estimate cubic lattice parameter from d-spacings.

    Assumes first peaks correspond to low-index planes:
      (1,0,0): a = d × √1
      (1,1,0): a = d × √2
      (1,1,1): a = d × √3

    Returns best-fit lattice parameter and estimated crystal system.
    """
    if not d_spacings:
        return {"a": None, "crystal_system": "unknown", "note": "no peaks found"}

    # For a simple cubic estimate, a = d * sqrt(h²+k²+l²)
    # Try (1,0,0) from the largest d-spacing
    a_from_100 = d_spacings[0] * math.sqrt(1)

    estimates = [a_from_100]
    miller_indices = [(1, 0, 0)]

    if len(d_spacings) >= 2:
        a_from_110 = d_spacings[1] * math.sqrt(2)
        estimates.append(a_from_110)
        miller_indices.append((1, 1, 0))

    if len(d_spacings) >= 3:
        a_from_111 = d_spacings[2] * math.sqrt(3)
        estimates.append(a_from_111)
        miller_indices.append((1, 1, 1))

    a_mean = float(np.mean(estimates))
    a_std = float(np.std(estimates)) if len(estimates) > 1 else 0.0

    return {
        "a": a_mean,
        "a_uncertainty": a_std,
        "crystal_system": "cubic" if a_std / max(a_mean, 1e-10) < 0.1 else "non-cubic",
        "estimates": [
            {"miller": list(m), "a": float(a)}
            for m, a in zip(miller_indices, estimates)
        ],
    }
