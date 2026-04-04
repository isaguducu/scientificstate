"""
domain_manifest.py — MaterialsScienceDomain entry point.

Implements scientificstate.DomainModule interface (registry.py).
Entry point group: scientificstate.domains
Entry point name:  materials_science

Methods:
  - xrd_analysis: X-ray diffraction — peak finding, Bragg's law, phase ID
  - tensile_test: Stress-strain — Young's modulus, yield, UTS, elongation
  - dsc_thermal:  DSC — Tg, Tm, Tc, enthalpy
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from scientificstate.domain_registry import DomainModule


class MethodErrorCode(str, Enum):
    """Domain-level error codes for execute_method() responses."""

    UNKNOWN_METHOD = "UNKNOWN_METHOD"
    INVALID_PARAMS = "INVALID_PARAMS"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    DATA_REF_ERROR = "DATA_REF_ERROR"


class MaterialsScienceDomain(DomainModule):
    """
    ScientificState domain plugin for materials characterization.

    Provides:
      - XRD Analysis (peak finding, Bragg's law, d-spacing, phase ID)
      - Tensile Test (Young's modulus, yield strength, UTS, elongation)
      - DSC Thermal Analysis (Tg, Tm, Tc, enthalpy)

    Compute substrate: classical only (M1 milestone).
    """

    @property
    def domain_id(self) -> str:
        return "materials_science"

    @property
    def domain_name(self) -> str:
        return "Materials Science (XRD, Tensile, DSC)"

    @property
    def supported_data_types(self) -> list[str]:
        return ["xrd_csv", "xrd_xy", "tensile_csv", "dsc_csv"]

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def taxonomy(self) -> dict | None:
        return {
            "field": "materials_science",
            "subfield": "characterization",
            "specialization": "structural_thermal_mechanical",
        }

    # ── DomainModule.list_methods ─────────────────────────────────────────────

    def list_methods(self) -> list[dict]:
        """Return method manifests aligned with MethodManifest schema."""
        return [
            {
                "method_id": "xrd_analysis",
                "domain_id": self.domain_id,
                "name": "X-Ray Diffraction Analysis",
                "description": "Peak finding, Bragg's law d-spacing, crystal phase identification",
                "required_data_types": ["xrd_csv", "xrd_xy"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "tensile_test",
                "domain_id": self.domain_id,
                "name": "Tensile Test Analysis",
                "description": "Stress-strain analysis: Young's modulus, yield strength, UTS, elongation",
                "required_data_types": ["tensile_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "dsc_thermal",
                "domain_id": self.domain_id,
                "name": "DSC Thermal Analysis",
                "description": "Glass transition (Tg), melting (Tm), crystallization (Tc), enthalpy (ΔH)",
                "required_data_types": ["dsc_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
        ]

    # ── DomainModule.execute_method ───────────────────────────────────────────

    def execute_method(
        self,
        method_id: str,
        data_ref: str,
        assumptions: list,
        params: dict,
    ) -> dict:
        """Execute a materials science method and return a result dict."""
        dispatch = {
            "xrd_analysis": self._execute_xrd,
            "tensile_test": self._execute_tensile,
            "dsc_thermal": self._execute_dsc,
        }

        fn = dispatch.get(method_id)
        if fn is None:
            msg = (
                f"Unknown method_id: {method_id!r}. "
                f"Available: {list(dispatch.keys())}"
            )
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "error",
                "error_code": MethodErrorCode.UNKNOWN_METHOD,
                "error": msg,
                "diagnostics": {},
            }

        # Optionally inject data from data_ref when expected param is absent
        if data_ref:
            params = self._merge_data_ref(data_ref, method_id, params)

        try:
            result = fn(data_ref, assumptions, params)
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "ok",
                "result": result,
                "diagnostics": {},
            }
        except ValueError as exc:
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "error",
                "error_code": MethodErrorCode.INVALID_PARAMS,
                "error": str(exc),
                "diagnostics": {},
            }
        except Exception as exc:
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "error",
                "error_code": MethodErrorCode.EXECUTION_ERROR,
                "error": str(exc),
                "diagnostics": {},
            }

    # ── Data-ref helpers ─────────────────────────────────────────────────────

    def _load_data_ref(self, data_ref: str) -> dict | list | None:
        """Load a CSV or JSON file referenced by data_ref."""
        path = Path(data_ref)
        if not path.exists():
            return None
        suffix = path.suffix.lower()
        if suffix == ".json":
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        if suffix == ".csv":
            import numpy as np

            data = np.genfromtxt(path, delimiter=",", names=True)
            return {name: data[name].tolist() for name in data.dtype.names}
        return None

    def _merge_data_ref(self, data_ref: str, method_id: str, params: dict) -> dict:
        """Inject data from data_ref when expected param key is absent."""
        _param_keys = {
            "xrd_analysis": "two_theta",
            "tensile_test": "strain",
            "dsc_thermal": "temperature",
        }

        try:
            loaded = self._load_data_ref(data_ref)
        except Exception:
            return params

        if loaded is None:
            return params

        params = dict(params)
        key = _param_keys.get(method_id)
        if key and key not in params and isinstance(loaded, dict):
            params.update(loaded)
        return params

    # ── Private dispatch helpers ──────────────────────────────────────────────

    def _execute_xrd(self, data_ref: str, assumptions: list, params: dict) -> dict:
        two_theta = params.get("two_theta")
        intensity = params.get("intensity")
        if two_theta is None or intensity is None:
            raise ValueError(
                "params['two_theta'] and params['intensity'] are required for xrd_analysis."
            )
        from .methods.xrd import compute_xrd

        return compute_xrd(
            two_theta=two_theta,
            intensity=intensity,
            wavelength=params.get("wavelength", 1.5406),
            prominence=params.get("prominence", 0.05),
            min_distance=params.get("min_distance", 5),
        )

    def _execute_tensile(self, data_ref: str, assumptions: list, params: dict) -> dict:
        strain = params.get("strain")
        stress = params.get("stress")
        if strain is None or stress is None:
            raise ValueError(
                "params['strain'] and params['stress'] are required for tensile_test."
            )
        from .methods.tensile import compute_tensile

        return compute_tensile(
            strain=strain,
            stress=stress,
            offset_pct=params.get("offset_pct", 0.002),
            elastic_range_pct=params.get("elastic_range_pct", 0.05),
        )

    def _execute_dsc(self, data_ref: str, assumptions: list, params: dict) -> dict:
        temperature = params.get("temperature")
        heat_flow = params.get("heat_flow")
        if temperature is None or heat_flow is None:
            raise ValueError(
                "params['temperature'] and params['heat_flow'] are required for dsc_thermal."
            )
        from .methods.dsc import compute_dsc

        return compute_dsc(
            temperature=temperature,
            heat_flow=heat_flow,
            smoothing_window=params.get("smoothing_window", 11),
            baseline_poly_order=params.get("baseline_poly_order", 2),
        )
