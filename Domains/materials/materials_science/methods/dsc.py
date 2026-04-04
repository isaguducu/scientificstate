"""
DSC (Differential Scanning Calorimetry) thermal analysis.

Input: temperature (°C) vs heat flow (mW or W/g) data
Output: Tg (glass transition), Tm (melting point), Tc (crystallization), ΔH (enthalpy)

Algorithms:
  - Tg detection: inflection point of step transition (maximum of derivative)
  - Tm/Tc detection: peak finding on heat flow curve
  - ΔH (enthalpy): numerical integration of peak area above/below baseline
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks


def compute_dsc(
    temperature: list[float] | np.ndarray,
    heat_flow: list[float] | np.ndarray,
    smoothing_window: int = 11,
    baseline_poly_order: int = 2,
) -> dict[str, Any]:
    """Compute DSC thermal analysis.

    Args:
        temperature: Temperature values in °C.
        heat_flow: Heat flow values (mW or W/g). Convention: endothermic = positive.
        smoothing_window: Window size for moving average smoothing (must be odd).
        baseline_poly_order: Polynomial order for baseline correction.

    Returns:
        Dict with keys: tg, tm, tc, enthalpy_melting, enthalpy_crystallization,
        peaks, assumptions, uncertainty, validity_domain, transformations.

    Raises:
        ValueError: If inputs are invalid.
    """
    temperature = np.asarray(temperature, dtype=float)
    heat_flow = np.asarray(heat_flow, dtype=float)

    if len(temperature) < 10:
        raise ValueError("At least 10 data points required for DSC analysis.")
    if len(temperature) != len(heat_flow):
        raise ValueError(
            f"temperature ({len(temperature)}) and heat_flow ({len(heat_flow)}) "
            "must have same length."
        )

    # Ensure smoothing_window is odd and positive
    if smoothing_window < 3:
        smoothing_window = 3
    if smoothing_window % 2 == 0:
        smoothing_window += 1

    # Sort by temperature
    sort_idx = np.argsort(temperature)
    temperature = temperature[sort_idx]
    heat_flow = heat_flow[sort_idx]

    # Smooth heat flow
    smoothed = uniform_filter1d(heat_flow, size=smoothing_window)

    # Compute derivative (dH/dT) for Tg detection
    dt = np.gradient(temperature)
    # Avoid division by zero
    dt[dt == 0] = np.finfo(float).eps
    derivative = np.gradient(smoothed) / dt

    # Baseline correction (polynomial fit on endpoints)
    baseline = _fit_baseline(temperature, smoothed, baseline_poly_order)
    corrected = smoothed - baseline

    # Detect Tg (glass transition) — inflection point = maximum of |derivative|
    tg_result = _detect_tg(temperature, derivative)

    # Detect Tm (melting point) — endothermic peak (positive heat flow peak)
    tm_result = _detect_peak(temperature, corrected, direction="positive")

    # Detect Tc (crystallization) — exothermic peak (negative heat flow peak)
    tc_result = _detect_peak(temperature, corrected, direction="negative")

    # Compute enthalpy (ΔH) via integration
    enthalpy_melting = _compute_enthalpy(temperature, corrected, direction="positive")
    enthalpy_crystallization = _compute_enthalpy(temperature, corrected, direction="negative")

    # Compile all detected thermal events
    events = []
    if tg_result is not None:
        events.append({"type": "Tg", "temperature": tg_result["temperature"]})
    if tm_result is not None:
        events.append({"type": "Tm", "temperature": tm_result["temperature"]})
    if tc_result is not None:
        events.append({"type": "Tc", "temperature": tc_result["temperature"]})

    # Temperature calibration uncertainty (typical ±0.5°C)
    temp_uncertainty = 0.5
    # Baseline uncertainty from residuals
    baseline_residual = float(np.std(smoothed[:max(5, len(smoothed) // 20)]))

    return {
        "tg": tg_result,
        "tm": tm_result,
        "tc": tc_result,
        "enthalpy_melting": enthalpy_melting,
        "enthalpy_crystallization": enthalpy_crystallization,
        "thermal_events": events,
        "event_count": len(events),
        "temperature_range": {
            "min": float(temperature[0]),
            "max": float(temperature[-1]),
        },
        "assumptions": [
            {"type": "thermal", "description": "Endothermic positive convention"},
            {"type": "instrument", "description": f"Smoothing window = {smoothing_window} points"},
            {"type": "analysis", "description": f"Baseline: polynomial order {baseline_poly_order}"},
        ],
        "uncertainty": {
            "temperature_calibration": f"±{temp_uncertainty}°C",
            "baseline_noise": float(baseline_residual),
            "enthalpy": "depends on baseline selection",
        },
        "validity_domain": {
            "conditions": [
                f"Temperature range: {float(temperature[0]):.1f}°C – {float(temperature[-1]):.1f}°C",
                "Atmosphere: assumed inert (N₂)",
            ],
        },
        "transformations": [
            {
                "name": "dsc_thermal",
                "algorithm": "derivative_peak_integration",
                "parameters": {
                    "smoothing_window": smoothing_window,
                    "baseline_poly_order": baseline_poly_order,
                },
                "software_version": "0.1.0",
            },
        ],
    }


def _fit_baseline(
    temperature: np.ndarray,
    heat_flow: np.ndarray,
    poly_order: int,
) -> np.ndarray:
    """Fit a polynomial baseline through the endpoints of the DSC curve."""
    n = len(temperature)
    # Use first and last 10% for baseline fitting
    n_ends = max(3, n // 10)
    mask = np.zeros(n, dtype=bool)
    mask[:n_ends] = True
    mask[-n_ends:] = True

    coeffs = np.polyfit(temperature[mask], heat_flow[mask], poly_order)
    return np.polyval(coeffs, temperature)


def _detect_tg(
    temperature: np.ndarray,
    derivative: np.ndarray,
) -> dict[str, float] | None:
    """Detect glass transition temperature from derivative of heat flow.

    Tg is at the inflection point of the step change — the peak of |dH/dT|.
    """
    # Ignore first and last 5% to avoid edge effects
    n = len(derivative)
    margin = max(2, n // 20)
    inner_deriv = np.abs(derivative[margin:-margin])

    if len(inner_deriv) == 0:
        return None

    # Find the position of maximum |derivative| — candidate Tg
    max_idx = int(np.argmax(inner_deriv)) + margin

    # Verify it's actually a step (derivative magnitude above 2× median)
    median_deriv = float(np.median(np.abs(derivative)))
    if median_deriv > 0 and np.abs(derivative[max_idx]) < 2.0 * median_deriv:
        return None

    return {
        "temperature": float(temperature[max_idx]),
        "derivative_magnitude": float(np.abs(derivative[max_idx])),
    }


def _detect_peak(
    temperature: np.ndarray,
    corrected: np.ndarray,
    direction: str,
) -> dict[str, float] | None:
    """Detect the most prominent peak in the given direction.

    Args:
        direction: "positive" for endothermic peaks, "negative" for exothermic.
    """
    if direction == "positive":
        signal = corrected
    else:
        signal = -corrected

    max_signal = float(np.max(signal))
    if max_signal <= 0:
        return None

    # Minimum absolute prominence to reject numerical noise
    min_prominence = max(0.01 * max_signal, 1e-6)

    indices, properties = find_peaks(
        signal,
        prominence=min_prominence,
        distance=max(3, len(signal) // 20),
    )

    if len(indices) == 0:
        return None

    # Return the most prominent peak
    prominences = properties["prominences"]
    best = int(np.argmax(prominences))
    peak_idx = indices[best]

    return {
        "temperature": float(temperature[peak_idx]),
        "heat_flow": float(corrected[peak_idx]),
        "prominence": float(prominences[best]),
    }


def _compute_enthalpy(
    temperature: np.ndarray,
    corrected: np.ndarray,
    direction: str,
) -> dict[str, float] | None:
    """Compute enthalpy by integrating the peak area.

    Args:
        direction: "positive" for melting (endothermic), "negative" for crystallization.
    """
    if direction == "positive":
        mask = corrected > 0
    else:
        mask = corrected < 0

    if not np.any(mask):
        return None

    masked_temp = temperature[mask]
    masked_flow = corrected[mask]

    area = float(np.abs(np.trapezoid(masked_flow, masked_temp)))

    return {
        "delta_h": area,
        "unit": "J/g",
        "integration_range": {
            "start": float(masked_temp[0]),
            "end": float(masked_temp[-1]),
        },
    }
