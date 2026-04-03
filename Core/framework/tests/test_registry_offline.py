"""Registry offline mirror tests — network unavailable → local fallback."""
import json
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import patch

from scientificstate.modules.registry_client import RegistriesConfig, RegistryClient


def _write_mirror(tmp_dir: Path, modules: list[dict]) -> Path:
    mirror = tmp_dir / "mirror"
    mirror.mkdir()
    (mirror / "available.json").write_text(json.dumps(modules))
    return mirror


def _client_with_mirror(mirror_path: str) -> RegistryClient:
    return RegistryClient(
        RegistriesConfig(
            registries=[{"name": "primary", "url": "http://primary.example", "priority": 1}],
            offline_mirror_path=mirror_path,
        )
    )


# ── Offline fallback ───────────────────────────────────────────────────────────

def test_offline_mirror_used_when_network_fails():
    with tempfile.TemporaryDirectory() as tmp:
        mirror = _write_mirror(Path(tmp), [{"domain_id": "polymer_science", "version": "1.0.0"}])
        client = _client_with_mirror(str(mirror))

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            result = client.list_available()

        assert result == [{"domain_id": "polymer_science", "version": "1.0.0"}]


def test_online_result_takes_priority_over_mirror():
    import json as _json
    with tempfile.TemporaryDirectory() as tmp:
        mirror = _write_mirror(Path(tmp), [{"domain_id": "stale_module", "version": "0.1.0"}])
        client = _client_with_mirror(str(mirror))

        from unittest.mock import MagicMock
        online_data = [{"domain_id": "fresh_module", "version": "2.0.0"}]
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = _json.dumps(online_data).encode()

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = client.list_available()

        assert result == online_data


def test_no_mirror_and_all_fail_returns_empty():
    client = RegistryClient(
        RegistriesConfig(
            registries=[{"name": "r1", "url": "http://r1.example", "priority": 1}],
            offline_mirror_path=None,
        )
    )
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("fail")):
        result = client.list_available()
    assert result == []


def test_offline_manifest_download():
    with tempfile.TemporaryDirectory() as tmp:
        mirror = Path(tmp) / "mirror"
        mirror.mkdir()
        manifest_dir = mirror / "polymer_science" / "1.0.0"
        manifest_dir.mkdir(parents=True)
        manifest_data = {"domain_id": "polymer_science", "version": "1.0.0"}
        (manifest_dir / "manifest.json").write_text(json.dumps(manifest_data))

        client = _client_with_mirror(str(mirror))

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            result = client.download_manifest("polymer_science", "1.0.0")

        assert result == manifest_data


def test_offline_manifest_not_found_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        mirror = Path(tmp) / "empty_mirror"
        mirror.mkdir()
        client = _client_with_mirror(str(mirror))

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            result = client.download_manifest("nonexistent", "9.9.9")

        assert result is None
