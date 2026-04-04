"""Gel electrophoresis band analysis tests."""

import numpy as np
import pytest

from biology.methods.gel_electrophoresis import compute_gel_electrophoresis


# -- Fixtures ----------------------------------------------------------------


def _synthetic_gel(
    band_positions: list[float] | None = None,
    band_heights: list[float] | None = None,
    n_points: int = 200,
    noise_level: float = 0.02,
) -> tuple[list, list]:
    """Generate synthetic gel intensity profile with Gaussian bands."""
    if band_positions is None:
        band_positions = [30.0, 60.0, 100.0, 140.0]
    if band_heights is None:
        band_heights = [0.8, 1.0, 0.6, 0.4]

    distances = np.linspace(0, 200, n_points)
    intensities = np.zeros(n_points)

    for pos, height in zip(band_positions, band_heights):
        sigma = 5.0
        intensities += height * np.exp(-0.5 * ((distances - pos) / sigma) ** 2)

    rng = np.random.default_rng(42)
    intensities += noise_level * rng.normal(size=n_points)
    intensities = np.maximum(intensities, 0)

    return distances.tolist(), intensities.tolist()


def _single_band_gel(position: float = 100.0, n_points: int = 200) -> tuple[list, list]:
    """Single-band gel profile."""
    distances = np.linspace(0, 200, n_points)
    intensities = np.exp(-0.5 * ((distances - position) / 5.0) ** 2)
    return distances.tolist(), intensities.tolist()


def _dna_ladder() -> tuple[list, list]:
    """Standard DNA ladder (distances and sizes in bp)."""
    ladder_distances = [20.0, 40.0, 60.0, 80.0, 100.0, 130.0, 160.0]
    ladder_sizes = [10000, 5000, 3000, 1500, 1000, 500, 200]
    return ladder_distances, ladder_sizes


# -- Basic functionality ----------------------------------------------------


def test_gel_detects_bands():
    dist, intens = _synthetic_gel()
    result = compute_gel_electrophoresis(dist, intens)
    assert result["band_count"] > 0


def test_gel_band_count_correct():
    dist, intens = _synthetic_gel(band_positions=[30, 60, 100, 140])
    result = compute_gel_electrophoresis(dist, intens)
    assert result["band_count"] == 4


def test_gel_band_positions():
    dist, intens = _synthetic_gel(band_positions=[50, 100, 150])
    result = compute_gel_electrophoresis(dist, intens)
    detected_positions = [b["distance"] for b in result["bands"]]
    for expected in [50, 100, 150]:
        closest = min(detected_positions, key=lambda x: abs(x - expected))
        assert abs(closest - expected) < 10


def test_gel_band_intensities():
    dist, intens = _synthetic_gel()
    result = compute_gel_electrophoresis(dist, intens)
    for band in result["bands"]:
        assert band["intensity"] > 0
        assert 0 < band["relative_intensity"] <= 1.0


def test_gel_band_prominences():
    dist, intens = _synthetic_gel()
    result = compute_gel_electrophoresis(dist, intens)
    for band in result["bands"]:
        assert band["prominence"] > 0


def test_gel_single_band():
    dist, intens = _single_band_gel(position=100.0)
    result = compute_gel_electrophoresis(dist, intens)
    assert result["band_count"] == 1
    assert abs(result["bands"][0]["distance"] - 100.0) < 5


def test_gel_distance_range():
    dist, intens = _synthetic_gel()
    result = compute_gel_electrophoresis(dist, intens)
    assert result["distance_range"]["min"] < result["distance_range"]["max"]


# -- Ladder calibration ------------------------------------------------------


def test_gel_with_ladder_sizes():
    dist, intens = _synthetic_gel()
    ladder_dist, ladder_sizes = _dna_ladder()
    result = compute_gel_electrophoresis(
        dist, intens,
        ladder_distances=ladder_dist,
        ladder_sizes=ladder_sizes,
    )
    assert result["ladder_calibration"] is not None
    assert result["ladder_calibration"]["r_squared"] > 0.9


def test_gel_ladder_estimated_sizes():
    dist, intens = _synthetic_gel()
    ladder_dist, ladder_sizes = _dna_ladder()
    result = compute_gel_electrophoresis(
        dist, intens,
        ladder_distances=ladder_dist,
        ladder_sizes=ladder_sizes,
    )
    assert len(result["band_sizes_bp"]) > 0
    for size in result["band_sizes_bp"]:
        assert size > 0


def test_gel_no_ladder():
    dist, intens = _synthetic_gel()
    result = compute_gel_electrophoresis(dist, intens)
    assert result["ladder_calibration"] is None
    assert len(result["band_sizes_bp"]) == 0


def test_gel_ladder_calibration_fields():
    dist, intens = _synthetic_gel()
    ladder_dist, ladder_sizes = _dna_ladder()
    result = compute_gel_electrophoresis(
        dist, intens,
        ladder_distances=ladder_dist,
        ladder_sizes=ladder_sizes,
    )
    cal = result["ladder_calibration"]
    assert "slope" in cal
    assert "intercept" in cal
    assert "r_squared" in cal
    assert "ladder_points" in cal


# -- Assumptions / uncertainty / validity ------------------------------------


def test_gel_assumptions():
    dist, intens = _synthetic_gel()
    result = compute_gel_electrophoresis(dist, intens)
    assert isinstance(result["assumptions"], list)
    assert len(result["assumptions"]) >= 2


def test_gel_uncertainty():
    dist, intens = _synthetic_gel()
    result = compute_gel_electrophoresis(dist, intens)
    assert "band_detection" in result["uncertainty"]


def test_gel_validity_domain():
    dist, intens = _synthetic_gel()
    result = compute_gel_electrophoresis(dist, intens)
    assert "conditions" in result["validity_domain"]


def test_gel_transformations():
    dist, intens = _synthetic_gel()
    result = compute_gel_electrophoresis(dist, intens)
    assert len(result["transformations"]) == 1
    assert result["transformations"][0]["name"] == "gel_electrophoresis"


# -- Edge cases --------------------------------------------------------------


def test_gel_too_few_points():
    with pytest.raises(ValueError, match="At least 10"):
        compute_gel_electrophoresis([1, 2, 3], [0.1, 0.2, 0.3])


def test_gel_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        compute_gel_electrophoresis(list(range(100)), [0.1] * 50)


def test_gel_zero_intensities():
    with pytest.raises(ValueError, match="zero or negative"):
        compute_gel_electrophoresis(list(range(20)), [0.0] * 20)


def test_gel_custom_prominence():
    dist, intens = _synthetic_gel()
    r_low = compute_gel_electrophoresis(dist, intens, min_prominence=0.01)
    r_high = compute_gel_electrophoresis(dist, intens, min_prominence=0.5)
    assert r_low["band_count"] >= r_high["band_count"]
