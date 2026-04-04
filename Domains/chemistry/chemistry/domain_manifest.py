"""
domain_manifest.py -- ChemistryDomain entry point.

Implements scientificstate.DomainModule interface (registry.py).
Entry point group: scientificstate.domains
Entry point name:  chemistry

Methods:
  - uv_vis_spectroscopy: UV-Vis absorption -- lambda_max, Beer-Lambert, peaks
  - titration: Acid-base titration -- equivalence point, pKa, concentration
  - hplc: HPLC chromatography -- retention times, peak areas, resolution, plate count
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


class ChemistryDomain(DomainModule):
    """
    ScientificState domain plugin for chemical analysis.

    Provides:
      - UV-Vis Spectroscopy (peak detection, Beer-Lambert molar absorptivity)
      - Titration (equivalence point, pKa estimation, analyte concentration)
      - HPLC Chromatography (retention times, areas, resolution, plate count)

    Compute substrate: classical only (M1 milestone).
    """

    @property
    def domain_id(self) -> str:
        return "chemistry"

    @property
    def domain_name(self) -> str:
        return "Chemistry (UV-Vis, Titration, HPLC)"

    @property
    def supported_data_types(self) -> list[str]:
        return ["uv_vis_csv", "titration_csv", "hplc_csv"]

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def taxonomy(self) -> dict | None:
        return {
            "field": "chemistry",
            "subfield": "analytical_chemistry",
            "specialization": "spectroscopy_chromatography",
        }

    # -- DomainModule.list_methods ------------------------------------------

    def list_methods(self) -> list[dict]:
        """Return method manifests aligned with MethodManifest schema."""
        return [
            {
                "method_id": "uv_vis_spectroscopy",
                "domain_id": self.domain_id,
                "name": "UV-Vis Spectroscopy",
                "description": "UV-Visible absorption: peak detection, Beer-Lambert molar absorptivity",
                "required_data_types": ["uv_vis_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "titration",
                "domain_id": self.domain_id,
                "name": "Titration Analysis",
                "description": "Acid-base titration: equivalence point, pKa, analyte concentration",
                "required_data_types": ["titration_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "hplc",
                "domain_id": self.domain_id,
                "name": "HPLC Chromatography",
                "description": "HPLC: retention times, peak areas, resolution, theoretical plate count",
                "required_data_types": ["hplc_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
        ]

    # -- DomainModule.execute_method ----------------------------------------

    def execute_method(
        self,
        method_id: str,
        data_ref: str,
        assumptions: list,
        params: dict,
    ) -> dict:
        """Execute a chemistry method and return a result dict."""
        dispatch = {
            "uv_vis_spectroscopy": self._execute_uv_vis,
            "titration": self._execute_titration,
            "hplc": self._execute_hplc,
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

        # Optionally inject data from data_ref
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

    # -- Data-ref helpers ---------------------------------------------------

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
            "uv_vis_spectroscopy": "wavelength",
            "titration": "volume",
            "hplc": "time",
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

    # -- Private dispatch helpers -------------------------------------------

    def _execute_uv_vis(self, data_ref: str, assumptions: list, params: dict) -> dict:
        wavelength = params.get("wavelength")
        absorbance = params.get("absorbance")
        if wavelength is None or absorbance is None:
            raise ValueError(
                "params['wavelength'] and params['absorbance'] are required for uv_vis_spectroscopy."
            )
        from .methods.uv_vis import compute_uv_vis

        return compute_uv_vis(
            wavelength=wavelength,
            absorbance=absorbance,
            concentration=params.get("concentration"),
            path_length=params.get("path_length", 1.0),
            prominence=params.get("prominence", 0.01),
        )

    def _execute_titration(self, data_ref: str, assumptions: list, params: dict) -> dict:
        volume = params.get("volume")
        ph = params.get("ph")
        if volume is None or ph is None:
            raise ValueError(
                "params['volume'] and params['ph'] are required for titration."
            )
        from .methods.titration import compute_titration

        return compute_titration(
            volume=volume,
            ph=ph,
            titrant_concentration=params.get("titrant_concentration"),
            analyte_volume=params.get("analyte_volume"),
        )

    def _execute_hplc(self, data_ref: str, assumptions: list, params: dict) -> dict:
        time = params.get("time")
        signal = params.get("signal")
        if time is None or signal is None:
            raise ValueError(
                "params['time'] and params['signal'] are required for hplc."
            )
        from .methods.hplc import compute_hplc

        return compute_hplc(
            time=time,
            signal=signal,
            dead_time=params.get("dead_time", 0.0),
            prominence=params.get("prominence", 0.01),
        )
