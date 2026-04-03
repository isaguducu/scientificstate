"""
Registry client — multi-registry failover + offline mirror.

Priority-ordered registry list: first successful response wins.
If all registries fail (timeout / network error), falls back to offline_mirror_path.
If offline_mirror_path is also unavailable, returns empty list / None.

Timeout: 5 seconds per registry (configurable via _TIMEOUT).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_TIMEOUT: int = 5  # seconds per registry attempt


@dataclass
class RegistriesConfig:
    """Configuration for the registry client.

    registries: ordered list of registry descriptors
                Each: {"name": str, "url": str, "priority": int}
                Sorted ascending by priority (1 = highest).
    offline_mirror_path: optional local directory for offline operation.
                         Expected file: <offline_mirror_path>/available.json
    """

    registries: list[dict] = field(default_factory=list)
    offline_mirror_path: str | None = None


class RegistryClient:
    """Fetches module listings and manifests from configured registries.

    Failover strategy:
      1. Sort registries by priority (ascending).
      2. Try each in order; skip on timeout or network error.
      3. If all fail and offline_mirror_path is set, read from local mirror.
      4. If no source succeeds, return empty list / None.
    """

    def __init__(self, config: RegistriesConfig) -> None:
        self.config = config

    # ── Public API ─────────────────────────────────────────────────────────

    def list_available(self) -> list[dict]:
        """List available modules from the highest-priority reachable registry.

        Returns:
            list[dict] of module descriptors, or [] if no source available.
        """
        for registry in self._sorted_registries():
            result = self._fetch_list(registry["url"])
            if result is not None:
                return result

        # Failover to offline mirror
        return self._offline_list()

    def download_manifest(self, domain_id: str, version: str) -> dict | None:
        """Download a specific module manifest.

        Args:
            domain_id: module domain identifier
            version: SemVer version string

        Returns:
            manifest dict, or None if not found in any source.
        """
        for registry in self._sorted_registries():
            result = self._fetch_manifest(registry["url"], domain_id, version)
            if result is not None:
                return result

        # Failover to offline mirror
        return self._offline_manifest(domain_id, version)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _sorted_registries(self) -> list[dict]:
        return sorted(self.config.registries, key=lambda r: r.get("priority", 99))

    def _fetch_list(self, url: str) -> list[dict] | None:
        """Fetch module list from a registry URL. Returns None on any failure."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{url.rstrip('/')}/modules")
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read())
        except Exception:  # noqa: BLE001
            return None

    def _fetch_manifest(self, url: str, domain_id: str, version: str) -> dict | None:
        """Fetch a single manifest from a registry URL. Returns None on any failure."""
        try:
            import urllib.request
            endpoint = f"{url.rstrip('/')}/modules/{domain_id}/{version}/manifest"
            req = urllib.request.Request(endpoint)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read())
        except Exception:  # noqa: BLE001
            return None

    def _offline_list(self) -> list[dict]:
        """Read available modules from offline mirror. Returns [] if unavailable."""
        if not self.config.offline_mirror_path:
            return []
        mirror = Path(self.config.offline_mirror_path)
        available_file = mirror / "available.json"
        if available_file.exists():
            try:
                return json.loads(available_file.read_text())
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _offline_manifest(self, domain_id: str, version: str) -> dict | None:
        """Read a manifest from offline mirror. Returns None if unavailable."""
        if not self.config.offline_mirror_path:
            return None
        mirror = Path(self.config.offline_mirror_path)
        manifest_file = mirror / domain_id / version / "manifest.json"
        if manifest_file.exists():
            try:
                return json.loads(manifest_file.read_text())
            except (json.JSONDecodeError, OSError):
                return None
        return None
