"""XRD analysis tests — peak finding, Bragg's law, d-spacing, lattice estimation."""

import math

import numpy as np
import pytest

from materials_science.methods.xrd import compute_xrd


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _synthetic_xrd(n_peaks: int = 3, noise: float = 0.01) -> tuple[list, list]:
    """Generate synthetic XRD pattern with Gaussian peaks."""
    rng = np.random.default_rng(42)
    two_theta = np.linspace(10.0, 80.0, 700)
    intensity = np.zeros_like(two_theta) + rng.normal(0, noise, len(two_theta))

    peak_positions = [20.0, 35.0, 50.0, 60.0, 70.0][:n_peaks]
    peak_intensities = [1.0, 0.8, 0.6, 0.4, 0.3][:n_peaks]

    for pos, amp in zip(peak_positions, peak_intensities):
        intensity += amp * np.exp(-0.5 * ((two_theta - pos) / 0.5) ** 2)

    intensity = np.maximum(intensity, 0)
    return two_theta.tolist(), intensity.tolist()


# ── Basic functionality ──────────────────────────────────────────────────────


def test_xrd_returns_peaks():
    two_theta, intensity = _synthetic_xrd(3)
    result = compute_xrd(two_theta, intensity)
    assert result["peak_count"] > 0
    assert len(result["peaks"]) > 0


def test_xrd_peaks_have_required_fields():
    two_theta, intensity = _synthetic_xrd(3)
    result = compute_xrd(two_theta, intensity)
    peak = result["peaks"][0]
    for key in ("two_theta", "intensity", "relative_intensity", "d_spacing",
                "d_spacing_uncertainty", "peak_index"):
        assert key in peak, f"Missing key: {key}"


def test_xrd_d_spacing_bragg_law():
    """d-spacing computed via Bragg's law: d = λ/(2·sin(θ))."""
    two_theta, intensity = _synthetic_xrd(1)
    result = compute_xrd(two_theta, intensity, wavelength=1.5406)
    peak = result["peaks"][0]
    theta_rad = math.radians(peak["two_theta"] / 2.0)
    expected_d = 1.5406 / (2.0 * math.sin(theta_rad))
    assert abs(peak["d_spacing"] - expected_d) < 0.01


def test_xrd_d_spacings_list():
    two_theta, intensity = _synthetic_xrd(3)
    result = compute_xrd(two_theta, intensity)
    assert len(result["d_spacings"]) == result["peak_count"]
    # d-spacings should be positive
    for d in result["d_spacings"]:
        assert d > 0


def test_xrd_peak_positions_near_expected():
    """Found peaks should be near the synthetic peak positions."""
    two_theta, intensity = _synthetic_xrd(3)
    result = compute_xrd(two_theta, intensity)
    expected = [20.0, 35.0, 50.0]
    found = [p["two_theta"] for p in result["peaks"]]
    for exp in expected:
        assert any(abs(f - exp) < 1.0 for f in found), f"Peak near {exp}° not found"


def test_xrd_relative_intensity_normalized():
    two_theta, intensity = _synthetic_xrd(3)
    result = compute_xrd(two_theta, intensity)
    max_rel = max(p["relative_intensity"] for p in result["peaks"])
    assert abs(max_rel - 1.0) < 0.01


def test_xrd_wavelength_default():
    two_theta, intensity = _synthetic_xrd(1)
    result = compute_xrd(two_theta, intensity)
    assert result["wavelength_used"] == 1.5406


def test_xrd_custom_wavelength():
    two_theta, intensity = _synthetic_xrd(1)
    result = compute_xrd(two_theta, intensity, wavelength=0.7107)
    assert result["wavelength_used"] == 0.7107


# ── Lattice parameters ──────────────────────────────────────────────────────


def test_xrd_lattice_parameters_present():
    two_theta, intensity = _synthetic_xrd(3)
    result = compute_xrd(two_theta, intensity)
    lp = result["lattice_parameters"]
    assert "a" in lp
    assert "crystal_system" in lp


def test_xrd_lattice_parameter_positive():
    two_theta, intensity = _synthetic_xrd(3)
    result = compute_xrd(two_theta, intensity)
    assert result["lattice_parameters"]["a"] > 0


# ── Assumptions / uncertainty / validity ─────────────────────────────────────


def test_xrd_assumptions_present():
    two_theta, intensity = _synthetic_xrd(1)
    result = compute_xrd(two_theta, intensity)
    assert isinstance(result["assumptions"], list)
    assert len(result["assumptions"]) >= 1


def test_xrd_uncertainty_present():
    two_theta, intensity = _synthetic_xrd(1)
    result = compute_xrd(two_theta, intensity)
    assert "uncertainty" in result


def test_xrd_validity_domain_present():
    two_theta, intensity = _synthetic_xrd(1)
    result = compute_xrd(two_theta, intensity)
    assert "validity_domain" in result
    assert "conditions" in result["validity_domain"]


def test_xrd_transformations_present():
    two_theta, intensity = _synthetic_xrd(1)
    result = compute_xrd(two_theta, intensity)
    assert len(result["transformations"]) == 1
    t = result["transformations"][0]
    assert t["name"] == "xrd_analysis"


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_xrd_too_few_points():
    with pytest.raises(ValueError, match="At least 3"):
        compute_xrd([10.0, 20.0], [1.0, 2.0])


def test_xrd_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        compute_xrd([10.0, 20.0, 30.0], [1.0, 2.0])


def test_xrd_zero_intensity():
    with pytest.raises(ValueError, match="zero or negative"):
        compute_xrd([10.0, 20.0, 30.0], [0.0, 0.0, 0.0])


def test_xrd_invalid_wavelength():
    with pytest.raises(ValueError, match="positive"):
        compute_xrd([10.0, 20.0, 30.0], [1.0, 2.0, 3.0], wavelength=-1.0)
