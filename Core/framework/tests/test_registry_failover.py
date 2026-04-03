"""Registry failover tests — primary timeout → secondary → PASS."""
import json
from unittest.mock import MagicMock, patch

from scientificstate.modules.registry_client import RegistriesConfig, RegistryClient


def _client(*urls: str, offline: str | None = None) -> RegistryClient:
    registries = [{"name": f"r{i}", "url": u, "priority": i + 1} for i, u in enumerate(urls)]
    return RegistryClient(RegistriesConfig(registries=registries, offline_mirror_path=offline))


def _module_list() -> list[dict]:
    return [{"domain_id": "polymer_science", "version": "1.0.0"}]


# ── list_available ─────────────────────────────────────────────────────────────

def test_client_import():
    from scientificstate.modules.registry_client import RegistryClient, RegistriesConfig
    assert RegistryClient is not None
    assert RegistriesConfig is not None


def test_primary_success_returns_list():
    client = _client("http://primary.example", "http://secondary.example")
    response_data = json.dumps(_module_list()).encode()

    with patch("urllib.request.urlopen") as mock_open:
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = response_data
        mock_open.return_value = mock_resp

        result = client.list_available()
    assert result == _module_list()


def test_primary_timeout_secondary_succeeds():
    """Primary fails with timeout; secondary succeeds."""
    import urllib.error

    client = _client("http://primary.example", "http://secondary.example")
    response_data = json.dumps(_module_list()).encode()

    call_count = {"n": 0}

    def side_effect(req, timeout):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise urllib.error.URLError("timed out")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = response_data
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=side_effect):
        result = client.list_available()

    assert result == _module_list()
    assert call_count["n"] == 2  # tried both


def test_all_registries_fail_returns_empty():
    import urllib.error
    client = _client("http://r1.example", "http://r2.example")

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        result = client.list_available()

    assert result == []


def test_priority_order_respected():
    """Lower priority number = tried first."""
    called_urls = []

    def side_effect(req, timeout):
        called_urls.append(req.full_url)
        raise Exception("fail")

    registries = [
        {"name": "low", "url": "http://low.example", "priority": 10},
        {"name": "high", "url": "http://high.example", "priority": 1},
    ]
    client = RegistryClient(RegistriesConfig(registries=registries))
    with patch("urllib.request.urlopen", side_effect=side_effect):
        client.list_available()

    assert called_urls[0].startswith("http://high.example")
    assert called_urls[1].startswith("http://low.example")
