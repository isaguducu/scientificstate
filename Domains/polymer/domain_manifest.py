"""
Domains/polymer/domain_manifest.py — W5 fallback shim.

W5 adapter scans for Domains/<name>/domain_manifest.py as a fallback
discovery path (in addition to entry_points auto-discovery).

This file is a thin re-export of the real implementation.
"""
from polymer_science.domain_manifest import PolymerScienceDomain

__all__ = ["PolymerScienceDomain"]
