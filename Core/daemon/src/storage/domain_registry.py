"""
DomainRegistry — thin adapter over Core/framework DomainRegistry.

Authority: scientificstate-framework is the source of truth.
This module ONLY wires the framework registry into the daemon's lifespan.

Usage:
    from src.storage.domain_registry import build_registry
    registry = build_registry()
    await registry.discover_and_register()
"""

from __future__ import annotations

import logging

from scientificstate.domain_registry.registry import DomainRegistry

logger = logging.getLogger("scientificstate.daemon.domain_registry_adapter")


def build_registry() -> DomainRegistry:
    """Return a fresh framework DomainRegistry instance."""
    return DomainRegistry()
