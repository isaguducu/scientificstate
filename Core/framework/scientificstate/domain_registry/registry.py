"""
DomainRegistry — pluggable domain module discovery and registration.

Constitutional rule: Core/framework is domain-agnostic.
  - No domain logic may live here.
  - Domains register themselves via Python entry_points (group='scientificstate.domains').
  - The registry is a directory, not an authority.

Entry point contract (each domain package must declare):
  [project.entry-points."scientificstate.domains"]
  <domain_key> = "<package>.<module>:<EntryPointClass>"

  The EntryPointClass must implement DomainModule.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from importlib.metadata import entry_points
from typing import Any


class DomainRegistrationError(Exception):
    """Raised when domain registration violates framework constraints."""


class DomainModule(ABC):
    """
    Abstract base for every domain plugin.

    Phase 0 plan contract (Execution_Plan_Phase0.md §2.3, §3.3):
      - domain_id: str         — unique lowercase key, e.g. "polymer_science"
      - domain_name: str       — human-readable, e.g. "Polymer Science (Py-GC-MS, DSC/TGA)"
      - supported_data_types: list[str]  — e.g. ["pygcms_csv", "pygcms_txt"]
      - list_methods() -> list[dict]     — method manifests
      - execute_method(method_id, data_ref, assumptions, params) -> dict
    """

    @property
    @abstractmethod
    def domain_id(self) -> str:
        """Unique, lowercase identifier. e.g. 'polymer_science'."""

    @property
    @abstractmethod
    def domain_name(self) -> str:
        """Human-readable domain name. e.g. 'Polymer Science (Py-GC-MS, DSC/TGA)'."""

    @property
    @abstractmethod
    def supported_data_types(self) -> list[str]:
        """List of accepted data type identifiers. e.g. ['pygcms_csv', 'pygcms_txt']."""

    @abstractmethod
    def list_methods(self) -> list[dict]:
        """
        Return method manifests for this domain.

        Each manifest must include at minimum:
          method_id, domain_id, required_data_types, produces_uncertainty,
          produces_validity_scope
        """

    @abstractmethod
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
        """

    def describe(self) -> dict[str, Any]:
        """Return a plain dict summary for serialization (used by daemon /domains)."""
        return {
            "domain_id": self.domain_id,
            "domain_name": self.domain_name,
            "supported_data_types": self.supported_data_types,
            "method_count": len(self.list_methods()),
        }


class DomainRegistry:
    """
    Registry of loaded domain modules.

    Domain-agnostic: the registry holds references and metadata only.
    All domain logic stays in Domains/<domain>/.

    Phase 0 API (Execution_Plan_Phase0.md §2.3, §3.4.1):
      register(module)         — add a module
      get(domain_id)           — retrieve by id (returns None if not found)
      list_domains()           — returns list[str] of registered domain_ids
      discover_and_register()  — entry_points auto-discovery
    """

    def __init__(self) -> None:
        self._domains: dict[str, DomainModule] = {}

    # ------------------------------------------------------------------
    # Core API (plan-mandated)
    # ------------------------------------------------------------------

    def register(self, module: DomainModule) -> None:
        """Register a domain module by domain_id (overwrites on conflict)."""
        self._domains[module.domain_id] = module

    def get(self, domain_id: str) -> DomainModule | None:
        """Retrieve a registered domain module. Returns None if not found."""
        return self._domains.get(domain_id)

    def list_domains(self) -> list[str]:
        """Return list of registered domain_id strings."""
        return list(self._domains.keys())

    def discover_and_register(self) -> list[str]:
        """
        Discover domain modules via Python entry_points and register them.

        Each installed package that declares:
          [project.entry-points."scientificstate.domains"]
          <key> = "<module>:<Class>"

        will be instantiated and registered.

        Returns the list of all registered domain_ids after discovery.
        Idempotent: safe to call multiple times.
        """
        eps = entry_points(group="scientificstate.domains")
        for ep in eps:
            try:
                cls = ep.load()
                instance: DomainModule = cls()
                self.register(instance)
            except Exception as exc:  # noqa: BLE001
                import warnings
                warnings.warn(
                    f"Failed to load domain plugin {ep.name!r}: {exc}",
                    stacklevel=2,
                )
        return self.list_domains()

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._domains)

    def __contains__(self, domain_id: str) -> bool:
        return domain_id in self._domains

    def __repr__(self) -> str:
        return f"DomainRegistry(domains={self.list_domains()})"
