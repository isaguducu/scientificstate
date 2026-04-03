"""
domain_manifest.py — PolymerScienceDomain entry point.

Implements scientificstate.DomainModule interface (registry.py).
Entry point group: scientificstate.domains
Entry point name:  polymer_science

Source: NitechLAB (read-only extraction — NitechLAB/ is not modified).

Phase 1 changes:
  - list_methods(): aligned with MethodManifest schema (name, produces_validity_scope
    as boolean, compute_class, quantum_contract)
  - execute_method(): added diagnostics + MethodErrorCode enum; error field kept for
    backward-compat; ValueError → INVALID_PARAMS, unknown method → UNKNOWN_METHOD
  - _load_data_ref() / _merge_data_ref(): optional CSV / JSON data_ref loading
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


class PolymerScienceDomain(DomainModule):
    """
    ScientificState domain plugin for polymer Py-GC-MS analysis.

    Provides:
      - PCA (JMP-compatible, correlation-based)
      - HCA Two-Way (unconstrained / temperature / sequence-constrained Ward)
      - KMD homolog series assignment per cluster
      - Deisotoping (greedy envelope grouping)
      - Fragment matching against fragment_db.json

    Compute substrate: classical only (M1 milestone).
    Quantum-ready: False (M3 future scope).
    """

    # ── DomainModule abstract properties ─────────────────────────────────────

    @property
    def domain_id(self) -> str:
        return "polymer_science"

    @property
    def domain_name(self) -> str:
        return "Polymer Science (Py-GC-MS, DSC/TGA)"

    @property
    def supported_data_types(self) -> list[str]:
        return ["pygcms_csv", "pygcms_txt", "dsc_csv", "tga_csv"]

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def taxonomy(self) -> dict | None:
        return {
            "field": "chemistry",
            "subfield": "polymer_science",
            "specialization": "characterization",
        }

    # ── Fragment database (lazy-loaded) ───────────────────────────────────────

    def __init__(self) -> None:
        self._fragment_db: dict | None = None

    def get_fragment_db(self) -> dict:
        if self._fragment_db is None:
            data_path = Path(__file__).parent / "data" / "fragment_db.json"
            with open(data_path, "r", encoding="utf-8") as f:
                self._fragment_db = json.load(f)
        return self._fragment_db

    # ── DomainModule.list_methods ─────────────────────────────────────────────

    def list_methods(self) -> list[dict]:
        """
        Return method manifests aligned with domain-module.schema.json §$defs/MethodManifest.

        Required fields per schema: method_id, domain_id, name, required_data_types,
        produces_uncertainty (const: true), produces_validity_scope (const: true).
        """
        return [
            {
                "method_id": "pca",
                "domain_id": self.domain_id,
                "name": "Principal Component Analysis (JMP-Compatible)",
                "description": "JMP-compatible PCA (correlation-based, TIC normalized)",
                "required_data_types": ["pygcms_txt", "pygcms_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "hca",
                "domain_id": self.domain_id,
                "name": "Hierarchical Cluster Analysis (Two-Way Ward)",
                "description": "Two-Way HCA (Ward; dendrogram / temperature / constrained)",
                "required_data_types": ["pygcms_txt", "pygcms_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "kmd_analysis",
                "domain_id": self.domain_id,
                "name": "Kendrick Mass Defect Homolog Series",
                "description": "KMD homolog series assignment per HCA cluster",
                "required_data_types": ["pygcms_txt", "pygcms_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "deisotoping",
                "domain_id": self.domain_id,
                "name": "Isotope Envelope Deisotoping",
                "description": "Greedy isotope envelope grouping for centroid peaks",
                "required_data_types": ["pygcms_txt", "pygcms_csv"],
                "produces_uncertainty": True,
                "produces_validity_scope": True,
                "compute_class": "classical",
                "quantum_contract": None,
            },
            {
                "method_id": "fragment_matching",
                "domain_id": self.domain_id,
                "name": "Fragment Library Matching",
                "description": "Fragment library matching against fragment_db.json",
                "required_data_types": ["pygcms_txt", "pygcms_csv"],
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
        """
        Execute a domain method and return a result dict.

        Constitutional constraint: this method performs computation only.
        It must not assert scientific claims or validity — those belong to
        the gate layer and the human researcher.

        Args:
            method_id: One of 'pca', 'hca', 'kmd_analysis', 'deisotoping',
                       'fragment_matching'.
            data_ref: Path or identifier for the input data. If non-empty and the
                      expected param key (blocks_data / peaks) is absent, the file
                      is loaded automatically (CSV or JSON).
            assumptions: List of assumption dicts attached to this execution.
            params: Method-specific parameters (passed through to the method).

        Returns:
            Dict with fields: method_id, domain_id, status, result | error,
            error_code (on error), diagnostics.

        Note on error_code backward-compat:
            The legacy ``error`` key is preserved alongside the new ``error_code``
            and ``message`` keys so that existing callers are not broken.
        """
        dispatch = {
            "pca": self._execute_pca,
            "hca": self._execute_hca,
            "kmd_analysis": self._execute_kmd,
            "deisotoping": self._execute_deisotoping,
            "fragment_matching": self._execute_fragment_matching,
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
            msg = str(exc)
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "error",
                "error_code": MethodErrorCode.INVALID_PARAMS,
                "error": msg,
                "diagnostics": {},
            }
        except Exception as exc:
            msg = str(exc)
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "error",
                "error_code": MethodErrorCode.EXECUTION_ERROR,
                "error": msg,
                "diagnostics": {},
            }

    # ── Data-ref helpers ─────────────────────────────────────────────────────

    def _load_data_ref(self, data_ref: str) -> dict | list | None:
        """
        Load a CSV or JSON file referenced by data_ref.

        Returns:
            - dict  for JSON object files
            - list  for JSON array files or CSV (list of row dicts)
            - None  if the path does not exist or extension is unsupported
        """
        path = Path(data_ref)
        if not path.exists():
            return None
        suffix = path.suffix.lower()
        if suffix == ".json":
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        if suffix == ".csv":
            import pandas as pd
            return pd.read_csv(path).to_dict(orient="records")
        return None

    def _merge_data_ref(self, data_ref: str, method_id: str, params: dict) -> dict:
        """
        If the expected param key (blocks_data / peaks) is absent from params,
        attempt to load it from data_ref.  Existing params always take precedence.
        """
        _blocks_methods = {"pca", "hca", "kmd_analysis"}
        _peaks_methods = {"deisotoping", "fragment_matching"}

        try:
            loaded = self._load_data_ref(data_ref)
        except Exception:
            return params  # cannot parse — fall back to existing params

        if loaded is None:
            return params

        params = dict(params)  # shallow copy — do not mutate caller's dict
        if method_id in _blocks_methods and "blocks_data" not in params:
            params["blocks_data"] = loaded
        elif method_id in _peaks_methods and "peaks" not in params:
            params["peaks"] = loaded
        return params

    # ── Private dispatch helpers ──────────────────────────────────────────────

    def _execute_pca(self, data_ref: str, assumptions: list, params: dict) -> dict:
        blocks_data = params.get("blocks_data")
        if blocks_data is None:
            raise ValueError("params['blocks_data'] is required for pca.")
        from .methods.pca import compute_pca
        return compute_pca(
            blocks_data,
            n_components=params.get("n_components", 3),
            mz_min=params.get("mz_min", 40.0),
            mz_max=params.get("mz_max", 1200.0),
            mz_bin=params.get("mz_bin", 1.0),
            mode=params.get("mode", "raw_time"),
        )

    def _execute_hca(self, data_ref: str, assumptions: list, params: dict) -> dict:
        blocks_data = params.get("blocks_data")
        if blocks_data is None:
            raise ValueError("params['blocks_data'] is required for hca.")
        from .methods.hca import compute_hca
        return compute_hca(
            blocks_data,
            n_clusters=params.get("n_clusters"),
            method=params.get("method", "ward"),
            mz_min=params.get("mz_min", 40.0),
            mz_max=params.get("mz_max", 1200.0),
            mz_bin=params.get("mz_bin", 1.0),
            mode=params.get("mode", "raw_time"),
            order_mode=params.get("order_mode", "dendrogram"),
        )

    def _execute_kmd(self, data_ref: str, assumptions: list, params: dict) -> dict:
        hca_result = params.get("hca_result")
        blocks_data = params.get("blocks_data")
        if hca_result is None or blocks_data is None:
            raise ValueError(
                "params['hca_result'] and params['blocks_data'] are required for kmd_analysis."
            )
        from .methods.kmd_analysis import analyze_clusters
        return analyze_clusters(
            hca_result,
            blocks_data,
            polymer=params.get("polymer", "PS"),
            kmd_tol=params.get("kmd_tol", 0.02),
        )

    def _execute_deisotoping(self, data_ref: str, assumptions: list, params: dict) -> dict:
        peaks = params.get("peaks")
        if peaks is None:
            raise ValueError("params['peaks'] is required for deisotoping.")
        from .methods.deisotoping import process_total_spectrum_peaks
        return process_total_spectrum_peaks(
            peaks,
            top_n=params.get("top_n", 200),
            charge_state=params.get("charge_state", 1),
        )

    def _execute_fragment_matching(self, data_ref: str, assumptions: list,
                                   params: dict) -> dict:
        peaks = params.get("peaks")
        if peaks is None:
            raise ValueError("params['peaks'] is required for fragment_matching.")
        from .methods.fragment_matching import match_peaks
        matches = match_peaks(
            peaks,
            self.get_fragment_db(),
            polymer=params.get("polymer", "PS"),
            abs_tol=params.get("abs_tol", 0.5),
        )
        return {"matches": matches}
