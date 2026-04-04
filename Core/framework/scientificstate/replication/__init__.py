"""
Replication subsystem — institutional replication engine for scientific claims.

Main_Source §9A.5 M3-G: Quantum/hybrid claims require at least one
independent institutional replication before endorsement.
"""
from __future__ import annotations

from .comparison import SSVComparison
from .engine import ReplicationEngine
from .protocol import is_replication_required, validate_replication_for_endorsement

__all__ = [
    "ReplicationEngine",
    "SSVComparison",
    "is_replication_required",
    "validate_replication_for_endorsement",
]
