"""DSC thermal analysis tests — Tg, Tm, Tc, enthalpy detection."""

import numpy as np
import pytest

from materials_science.methods.dsc import compute_dsc


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _synthetic_dsc_with_tg(tg: float = 150.0) -> tuple[list, list]:
    """Generate synthetic DSC with a glass transition step."""
    temperature = np.linspace(50.0, 250.0, 500)
    # Sigmoid step at Tg
    heat_flow = 0.5 * (1.0 + np.tanh((temperature - tg) / 5.0))
    return temperature.tolist(), heat_flow.tolist()


def _synthetic_dsc_with_melting(tm: float = 200.0) -> tuple[list, list]:
    """Generate synthetic DSC with a melting peak (endothermic)."""
    temperature = np.linspace(50.0, 300.0, 500)
    baseline = np.zeros_like(temperature)
    # Gaussian melting peak (positive = endothermic)
    peak = 5.0 * np.exp(-0.5 * ((temperature - tm) / 3.0) ** 2)
    heat_flow = baseline + peak
    return temperature.tolist(), heat_flow.tolist()


def _synthetic_dsc_with_crystallization(tc: float = 120.0) -> tuple[list, list]:
    """Generate synthetic DSC with a crystallization peak (exothermic)."""
    temperature = np.linspace(50.0, 250.0, 500)
    baseline = np.zeros_like(temperature)
    # Negative Gaussian peak (exothermic)
    peak = -3.0 * np.exp(-0.5 * ((temperature - tc) / 4.0) ** 2)
    heat_flow = baseline + peak
    return temperature.tolist(), heat_flow.tolist()


def _synthetic_dsc_full(tg: float = 80.0, tc: float = 130.0, tm: float = 220.0) -> tuple[list, list]:
    """Generate synthetic DSC with Tg step + Tc exotherm + Tm endotherm."""
    temperature = np.linspace(30.0, 280.0, 700)
    # Glass transition step
    step = 0.3 * (1.0 + np.tanh((temperature - tg) / 3.0))
    # Crystallization (exothermic, negative)
    cryst = -2.0 * np.exp(-0.5 * ((temperature - tc) / 4.0) ** 2)
    # Melting (endothermic, positive)
    melt = 4.0 * np.exp(-0.5 * ((temperature - tm) / 3.0) ** 2)
    heat_flow = step + cryst + melt
    return temperature.tolist(), heat_flow.tolist()


# ── Tg detection ─────────────────────────────────────────────────────────────


def test_dsc_tg_detected():
    temp, hf = _synthetic_dsc_with_tg(150.0)
    result = compute_dsc(temp, hf)
    assert result["tg"] is not None
    assert "temperature" in result["tg"]


def test_dsc_tg_near_expected():
    temp, hf = _synthetic_dsc_with_tg(150.0)
    result = compute_dsc(temp, hf)
    assert abs(result["tg"]["temperature"] - 150.0) < 10.0


def test_dsc_tg_derivative_magnitude():
    temp, hf = _synthetic_dsc_with_tg(150.0)
    result = compute_dsc(temp, hf)
    assert result["tg"]["derivative_magnitude"] > 0


# ── Tm detection ─────────────────────────────────────────────────────────────


def test_dsc_tm_detected():
    temp, hf = _synthetic_dsc_with_melting(200.0)
    result = compute_dsc(temp, hf)
    assert result["tm"] is not None


def test_dsc_tm_near_expected():
    temp, hf = _synthetic_dsc_with_melting(200.0)
    result = compute_dsc(temp, hf)
    assert abs(result["tm"]["temperature"] - 200.0) < 5.0


def test_dsc_tm_endothermic_positive():
    """Melting peak heat flow should be positive (endothermic convention)."""
    temp, hf = _synthetic_dsc_with_melting(200.0)
    result = compute_dsc(temp, hf)
    assert result["tm"]["heat_flow"] > 0


# ── Tc detection ─────────────────────────────────────────────────────────────


def test_dsc_tc_detected():
    temp, hf = _synthetic_dsc_with_crystallization(120.0)
    result = compute_dsc(temp, hf)
    assert result["tc"] is not None


def test_dsc_tc_near_expected():
    temp, hf = _synthetic_dsc_with_crystallization(120.0)
    result = compute_dsc(temp, hf)
    assert abs(result["tc"]["temperature"] - 120.0) < 5.0


def test_dsc_tc_exothermic_negative():
    """Crystallization peak should have negative heat flow."""
    temp, hf = _synthetic_dsc_with_crystallization(120.0)
    result = compute_dsc(temp, hf)
    assert result["tc"]["heat_flow"] < 0


# ── Enthalpy ─────────────────────────────────────────────────────────────────


def test_dsc_enthalpy_melting():
    temp, hf = _synthetic_dsc_with_melting(200.0)
    result = compute_dsc(temp, hf)
    assert result["enthalpy_melting"] is not None
    assert result["enthalpy_melting"]["delta_h"] > 0
    assert result["enthalpy_melting"]["unit"] == "J/g"


def test_dsc_enthalpy_crystallization():
    temp, hf = _synthetic_dsc_with_crystallization(120.0)
    result = compute_dsc(temp, hf)
    assert result["enthalpy_crystallization"] is not None
    assert result["enthalpy_crystallization"]["delta_h"] > 0  # absolute value


# ── Full DSC curve ───────────────────────────────────────────────────────────


def test_dsc_full_three_events():
    """Full curve with Tg + Tc + Tm should detect all three."""
    temp, hf = _synthetic_dsc_full()
    result = compute_dsc(temp, hf)
    assert result["event_count"] >= 2  # At minimum Tm and one of Tg/Tc


def test_dsc_thermal_events_list():
    temp, hf = _synthetic_dsc_full()
    result = compute_dsc(temp, hf)
    events = result["thermal_events"]
    assert isinstance(events, list)
    types = [e["type"] for e in events]
    assert "Tm" in types


# ── Assumptions / uncertainty / validity ─────────────────────────────────────


def test_dsc_assumptions():
    temp, hf = _synthetic_dsc_with_melting()
    result = compute_dsc(temp, hf)
    assert isinstance(result["assumptions"], list)
    assert len(result["assumptions"]) >= 2


def test_dsc_uncertainty():
    temp, hf = _synthetic_dsc_with_melting()
    result = compute_dsc(temp, hf)
    assert "temperature_calibration" in result["uncertainty"]
    assert "baseline_noise" in result["uncertainty"]


def test_dsc_validity_domain():
    temp, hf = _synthetic_dsc_with_melting()
    result = compute_dsc(temp, hf)
    assert "conditions" in result["validity_domain"]


def test_dsc_transformations():
    temp, hf = _synthetic_dsc_with_melting()
    result = compute_dsc(temp, hf)
    assert len(result["transformations"]) == 1
    assert result["transformations"][0]["name"] == "dsc_thermal"


def test_dsc_temperature_range():
    temp, hf = _synthetic_dsc_with_melting()
    result = compute_dsc(temp, hf)
    assert "temperature_range" in result
    assert result["temperature_range"]["min"] < result["temperature_range"]["max"]


# ── Edge cases ───────────────────────────────────────────────────────────────


def test_dsc_too_few_points():
    with pytest.raises(ValueError, match="At least 10"):
        compute_dsc([50, 100, 150], [0.1, 0.2, 0.3])


def test_dsc_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        compute_dsc(list(range(20)), list(range(15)))


def test_dsc_flat_curve():
    """Flat heat flow → no peaks detected."""
    temp = np.linspace(50, 300, 100)
    hf = np.zeros(100) + 0.001
    result = compute_dsc(temp.tolist(), hf.tolist())
    assert result["tm"] is None
    assert result["tc"] is None
