"""HPLC chromatography analysis tests."""

import numpy as np
import pytest

from chemistry.methods.hplc import compute_hplc


# -- Fixtures ----------------------------------------------------------------


def _synthetic_chromatogram(
    retention_times: list[float] | None = None,
    peak_heights: list[float] | None = None,
    n_points: int = 500,
    noise_level: float = 0.001,
) -> tuple[list, list]:
    """Generate synthetic HPLC chromatogram with Gaussian peaks."""
    if retention_times is None:
        retention_times = [2.0, 5.0, 8.0]
    if peak_heights is None:
        peak_heights = [0.5, 1.0, 0.3]

    time = np.linspace(0, 15, n_points)
    signal = np.zeros(n_points)

    for rt, height in zip(retention_times, peak_heights):
        sigma = 0.2
        signal += height * np.exp(-0.5 * ((time - rt) / sigma) ** 2)

    rng = np.random.default_rng(42)
    signal += noise_level * rng.normal(size=n_points)
    signal = np.maximum(signal, 0)

    return time.tolist(), signal.tolist()


def _single_peak_chromatogram(
    rt: float = 5.0,
    height: float = 1.0,
    n_points: int = 300,
) -> tuple[list, list]:
    """Single peak chromatogram."""
    time = np.linspace(0, 10, n_points)
    signal = height * np.exp(-0.5 * ((time - rt) / 0.2) ** 2)
    return time.tolist(), signal.tolist()


def _baseline_chromatogram(n_points: int = 200) -> tuple[list, list]:
    """Flat baseline (no peaks)."""
    time = np.linspace(0, 10, n_points)
    signal = np.full(n_points, 0.001)
    return time.tolist(), signal.tolist()


# -- Basic functionality ----------------------------------------------------


def test_hplc_detects_peaks():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    assert result["peak_count"] > 0


def test_hplc_peak_count_correct():
    time, signal = _synthetic_chromatogram(retention_times=[2, 5, 8])
    result = compute_hplc(time, signal)
    assert result["peak_count"] == 3


def test_hplc_retention_times():
    time, signal = _synthetic_chromatogram(retention_times=[2.0, 5.0, 8.0])
    result = compute_hplc(time, signal)
    rts = result["retention_times_min"]
    for expected in [2.0, 5.0, 8.0]:
        closest = min(rts, key=lambda x: abs(x - expected))
        assert abs(closest - expected) < 0.5


def test_hplc_peak_areas_positive():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    for area in result["peak_areas"]:
        assert area > 0


def test_hplc_peak_heights():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    for peak in result["peaks"]:
        assert peak["height"] > 0


def test_hplc_peak_widths():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    for peak in result["peaks"]:
        assert peak["width_half_min"] > 0


def test_hplc_single_peak():
    time, signal = _single_peak_chromatogram(rt=5.0)
    result = compute_hplc(time, signal)
    assert result["peak_count"] == 1
    assert abs(result["peaks"][0]["retention_time_min"] - 5.0) < 0.5


def test_hplc_time_range():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    assert result["time_range"]["min"] < result["time_range"]["max"]


# -- Resolution and plate count -----------------------------------------------


def test_hplc_resolution():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    assert len(result["resolutions"]) >= 1
    for res in result["resolutions"]:
        assert res["resolution"] > 0


def test_hplc_plate_count():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal, dead_time=0.5)
    for peak in result["peaks"]:
        if peak["plate_count"] is not None:
            assert peak["plate_count"] > 0


def test_hplc_average_plate_count():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal, dead_time=0.5)
    if result["average_plate_count"] is not None:
        assert result["average_plate_count"] > 0


def test_hplc_capacity_factor():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal, dead_time=0.5)
    for peak in result["peaks"]:
        if peak["capacity_factor"] is not None:
            assert peak["capacity_factor"] >= 0


def test_hplc_no_dead_time():
    """Without dead time, capacity factor should be None."""
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal, dead_time=0.0)
    for peak in result["peaks"]:
        assert peak["capacity_factor"] is None


# -- Baseline and empty results -----------------------------------------------


def test_hplc_baseline():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    assert "baseline" in result


def test_hplc_flat_baseline():
    """Flat baseline should produce no peaks."""
    time, signal = _baseline_chromatogram()
    result = compute_hplc(time, signal)
    assert result["peak_count"] == 0
    assert len(result["peaks"]) == 0


# -- Assumptions / uncertainty / validity ------------------------------------


def test_hplc_assumptions():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    assert isinstance(result["assumptions"], list)
    assert len(result["assumptions"]) >= 2


def test_hplc_uncertainty():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    assert "retention_time" in result["uncertainty"]


def test_hplc_validity_domain():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    assert "conditions" in result["validity_domain"]


def test_hplc_transformations():
    time, signal = _synthetic_chromatogram()
    result = compute_hplc(time, signal)
    assert len(result["transformations"]) == 1
    assert result["transformations"][0]["name"] == "hplc"


# -- Edge cases ---------------------------------------------------------------


def test_hplc_too_few_points():
    with pytest.raises(ValueError, match="At least 10"):
        compute_hplc([1, 2, 3], [0.1, 0.2, 0.3])


def test_hplc_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        compute_hplc(list(range(500)), [0.1] * 100)


def test_hplc_custom_prominence():
    time, signal = _synthetic_chromatogram()
    r_low = compute_hplc(time, signal, prominence=0.001)
    r_high = compute_hplc(time, signal, prominence=0.5)
    assert r_low["peak_count"] >= r_high["peak_count"]
