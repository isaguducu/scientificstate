"""Cell viability (MTT/MTS) analysis tests."""

import numpy as np
import pytest

from biology.methods.cell_viability import compute_cell_viability


# -- Fixtures ----------------------------------------------------------------


def _dose_response(
    ic50: float = 10.0,
    hill: float = 1.0,
    top: float = 100.0,
    bottom: float = 5.0,
    n_points: int = 8,
    conc_range: tuple = (0.1, 100.0),
) -> tuple[list, list]:
    """Generate synthetic dose-response data (4PL Hill model)."""
    concs = np.logspace(np.log10(conc_range[0]), np.log10(conc_range[1]), n_points)
    # Viability = bottom + (top - bottom) / (1 + (c/IC50)^hill)
    viability = bottom + (top - bottom) / (1.0 + (concs / ic50) ** hill)
    # Convert viability % to absorbance (scale to ~0.1-1.5 OD)
    control_od = 1.5
    absorbance = viability / 100.0 * control_od
    return concs.tolist(), absorbance.tolist()


def _all_alive(n_points: int = 6) -> tuple[list, list]:
    """No cytotoxicity -- all cells viable."""
    concs = np.logspace(-1, 2, n_points)
    absorbance = [1.2] * n_points
    return concs.tolist(), absorbance


def _all_dead(n_points: int = 6) -> tuple[list, list]:
    """Complete kill -- zero viability."""
    concs = np.logspace(-1, 2, n_points)
    absorbance = [0.05] * n_points
    return concs.tolist(), absorbance


# -- Basic functionality ----------------------------------------------------


def test_viability_returns_percent():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    assert "viability_percent" in result
    assert len(result["viability_percent"]) == len(concs)


def test_viability_percent_range():
    """Viability should be in [0, ~120] range."""
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    for v in result["viability_percent"]:
        assert -5 <= v <= 120


def test_viability_decreasing():
    """Higher concentration -> lower viability."""
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    viabilities = result["viability_percent"]
    # First viability should be higher than last (dose-response)
    assert viabilities[0] > viabilities[-1]


def test_viability_ic50_detected():
    concs, absorbances = _dose_response(ic50=10.0)
    result = compute_cell_viability(concs, absorbances)
    assert result["ic50"] is not None
    assert result["ic50"]["value"] > 0


def test_viability_ic50_near_expected():
    """IC50 should be close to the input IC50."""
    concs, absorbances = _dose_response(ic50=10.0)
    result = compute_cell_viability(concs, absorbances)
    assert result["ic50"] is not None
    # Within 5x of target (log-scale interpolation)
    assert 2.0 <= result["ic50"]["value"] <= 50.0


def test_viability_mean():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    assert 0 < result["mean_viability"] < 100


def test_viability_control_absorbance():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances, control_absorbance=1.5)
    assert result["control_absorbance"] == 1.5


def test_viability_blank_correction():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances, blank_absorbance=0.05)
    assert result["blank_absorbance"] == 0.05


def test_viability_dose_response_curve():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    assert len(result["dose_response"]) == len(concs)
    for point in result["dose_response"]:
        assert "concentration" in point
        assert "absorbance" in point
        assert "viability_percent" in point


def test_viability_concentration_range():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    assert result["concentration_range"]["min"] < result["concentration_range"]["max"]


def test_viability_all_alive_no_ic50():
    """No IC50 when all cells are viable."""
    concs, absorbances = _all_alive()
    result = compute_cell_viability(concs, absorbances)
    assert result["ic50"] is None


def test_viability_all_dead_no_ic50():
    """No IC50 when all cells are dead (explicit control shows low viability)."""
    concs, absorbances = _all_dead()
    result = compute_cell_viability(concs, absorbances, control_absorbance=1.2)
    assert result["ic50"] is None
    assert result["mean_viability"] < 10


# -- Assumptions / uncertainty / validity ------------------------------------


def test_viability_assumptions():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    assert isinstance(result["assumptions"], list)
    assert len(result["assumptions"]) >= 2


def test_viability_uncertainty():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    assert "ic50" in result["uncertainty"]


def test_viability_validity_domain():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    assert "conditions" in result["validity_domain"]


def test_viability_transformations():
    concs, absorbances = _dose_response()
    result = compute_cell_viability(concs, absorbances)
    assert len(result["transformations"]) == 1
    assert result["transformations"][0]["name"] == "cell_viability"


# -- Edge cases --------------------------------------------------------------


def test_viability_too_few_points():
    with pytest.raises(ValueError, match="At least 3"):
        compute_cell_viability([1, 2], [0.5, 0.3])


def test_viability_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        compute_cell_viability([1, 2, 3, 4, 5], [0.5, 0.3, 0.2])


def test_viability_zero_control():
    with pytest.raises(ValueError, match="positive"):
        compute_cell_viability([1, 2, 3], [0.5, 0.3, 0.2], control_absorbance=0.0)
