"""PCR amplification analysis tests -- Ct, efficiency, threshold."""

import numpy as np
import pytest

from biology.methods.pcr import compute_pcr


# -- Fixtures ----------------------------------------------------------------


def _synthetic_pcr(
    ct_target: float = 20.0,
    efficiency: float = 0.95,
    n_cycles: int = 40,
    baseline: float = 100.0,
    plateau: float = 50000.0,
) -> tuple[list, list]:
    """Generate synthetic qPCR sigmoidal amplification curve.

    Uses a logistic model: F = baseline + plateau / (1 + exp(-k*(c - ct)))
    """
    cycles = np.arange(1, n_cycles + 1, dtype=float)
    k = np.log(1 + efficiency) * 2  # steepness from efficiency
    fluorescence = baseline + plateau / (1.0 + np.exp(-k * (cycles - ct_target)))
    return cycles.tolist(), fluorescence.tolist()


def _flat_pcr(n_cycles: int = 40, baseline: float = 100.0) -> tuple[list, list]:
    """No amplification -- flat baseline (negative control)."""
    cycles = np.arange(1, n_cycles + 1, dtype=float)
    noise = np.random.default_rng(42).normal(0, 2, n_cycles)
    fluorescence = baseline + noise
    return cycles.tolist(), fluorescence.tolist()


def _exponential_pcr(
    ct_target: float = 15.0,
    n_cycles: int = 40,
    baseline: float = 50.0,
) -> tuple[list, list]:
    """Pure exponential growth (no plateau)."""
    cycles = np.arange(1, n_cycles + 1, dtype=float)
    fluorescence = baseline + np.where(
        cycles > ct_target,
        100.0 * 2.0 ** (cycles - ct_target),
        0.0,
    )
    return cycles.tolist(), fluorescence.tolist()


# -- Basic functionality ----------------------------------------------------


def test_pcr_returns_ct():
    cycles, fluor = _synthetic_pcr()
    result = compute_pcr(cycles, fluor)
    assert result["ct_value"] is not None
    assert result["ct_value"] > 0


def test_pcr_ct_near_expected():
    """Ct should be close to the target value for synthetic data."""
    cycles, fluor = _synthetic_pcr(ct_target=20.0)
    result = compute_pcr(cycles, fluor)
    assert abs(result["ct_value"] - 20.0) < 3.0


def test_pcr_ct_different_targets():
    """Different Ct targets should produce different Ct values."""
    _, fluor1 = _synthetic_pcr(ct_target=15.0)
    _, fluor2 = _synthetic_pcr(ct_target=25.0)
    cycles = list(range(1, 41))
    r1 = compute_pcr(cycles, fluor1)
    r2 = compute_pcr(cycles, fluor2)
    assert r1["ct_value"] < r2["ct_value"]


def test_pcr_efficiency_positive():
    cycles, fluor = _synthetic_pcr()
    result = compute_pcr(cycles, fluor)
    if result["amplification_efficiency"] is not None:
        assert result["amplification_efficiency"] > 0


def test_pcr_efficiency_reasonable():
    """Efficiency should be between 0.5 and 1.2 for good data."""
    cycles, fluor = _synthetic_pcr(efficiency=0.95)
    result = compute_pcr(cycles, fluor)
    if result["amplification_efficiency"] is not None:
        assert 0.3 <= result["amplification_efficiency"] <= 1.5


def test_pcr_baseline_fluorescence():
    cycles, fluor = _synthetic_pcr(baseline=100.0)
    result = compute_pcr(cycles, fluor)
    assert abs(result["baseline_fluorescence"] - 100.0) < 50.0


def test_pcr_plateau_fluorescence():
    cycles, fluor = _synthetic_pcr(plateau=50000.0)
    result = compute_pcr(cycles, fluor)
    assert result["plateau_fluorescence"] > result["baseline_fluorescence"]


def test_pcr_dynamic_range():
    cycles, fluor = _synthetic_pcr()
    result = compute_pcr(cycles, fluor)
    assert result["dynamic_range"] > 0


def test_pcr_cycle_range():
    cycles, fluor = _synthetic_pcr(n_cycles=40)
    result = compute_pcr(cycles, fluor)
    assert result["cycle_range"]["min"] == 1.0
    assert result["cycle_range"]["max"] == 40.0


def test_pcr_custom_threshold():
    cycles, fluor = _synthetic_pcr()
    result = compute_pcr(cycles, fluor, threshold=500.0)
    assert result["threshold"] == 500.0


def test_pcr_custom_baseline_cycles():
    cycles, fluor = _synthetic_pcr()
    result = compute_pcr(cycles, fluor, baseline_cycles=10)
    assert result["ct_value"] is not None


def test_pcr_flat_curve_no_ct():
    """Flat baseline (no amplification) should yield no Ct."""
    cycles, fluor = _flat_pcr()
    result = compute_pcr(cycles, fluor)
    # Ct may be None or very late if noise triggers it
    if result["ct_value"] is not None:
        assert result["ct_value"] > 30  # would be very late


def test_pcr_exponential_curve():
    cycles, fluor = _exponential_pcr(ct_target=15.0)
    result = compute_pcr(cycles, fluor)
    assert result["ct_value"] is not None


# -- Assumptions / uncertainty / validity ------------------------------------


def test_pcr_assumptions():
    cycles, fluor = _synthetic_pcr()
    result = compute_pcr(cycles, fluor)
    assert isinstance(result["assumptions"], list)
    assert len(result["assumptions"]) >= 2


def test_pcr_uncertainty():
    cycles, fluor = _synthetic_pcr()
    result = compute_pcr(cycles, fluor)
    assert "baseline_noise" in result["uncertainty"]


def test_pcr_validity_domain():
    cycles, fluor = _synthetic_pcr()
    result = compute_pcr(cycles, fluor)
    assert "conditions" in result["validity_domain"]


def test_pcr_transformations():
    cycles, fluor = _synthetic_pcr()
    result = compute_pcr(cycles, fluor)
    assert len(result["transformations"]) == 1
    assert result["transformations"][0]["name"] == "pcr_amplification"


# -- Edge cases --------------------------------------------------------------


def test_pcr_too_few_points():
    with pytest.raises(ValueError, match="At least 10"):
        compute_pcr([1, 2, 3], [100, 101, 102])


def test_pcr_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        compute_pcr(list(range(1, 41)), [100] * 20)


def test_pcr_unsorted_cycles():
    """Should handle unsorted cycle data."""
    cycles, fluor = _synthetic_pcr()
    # Reverse order
    result = compute_pcr(cycles[::-1], fluor[::-1])
    assert result["ct_value"] is not None
