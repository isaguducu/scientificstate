"""Test /modules endpoints."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_modules_returns_list(client):
    """GET /modules returns a list (may be empty in test env)."""
    resp = await client.get("/modules")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_available_returns_list(client):
    """GET /modules/available returns a list."""
    resp = await client.get("/modules/available")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_not_installed_module_returns_404(client):
    """GET /modules/{id} for non-installed module → 404."""
    resp = await client.get("/modules/not_installed_domain")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_not_installed_module_returns_404(client):
    """DELETE /modules/{id} for non-installed module → 404."""
    resp = await client.delete("/modules/not_installed_domain")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_install_bad_base64_returns_400(client):
    """POST /modules/install with bad base64 → 400."""
    resp = await client.post(
        "/modules/install",
        json={
            "manifest_b64": "not-valid-base64!!!",
            "package_b64": "dGVzdA==",
            "public_key_b64": "dGVzdA==",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_install_unsigned_manifest_returns_403(client):
    """POST /modules/install with unsigned manifest → 403 (signature hard rule)."""
    import base64
    import json

    manifest = {
        "manifest_version": "1.0",
        "domain_id": "test_domain",
        "domain_name": "Test",
        "version": "0.1.0",
        "entry_point": "test_domain.manifest:TestDomain",
        "min_core_version": "0.1.0",
        "supported_data_types": ["csv"],
        "checksum": {"algorithm": "sha256", "value": "abc123"},
        # no signature field → unsigned → rejected
    }
    manifest_bytes = json.dumps(manifest).encode()
    package_bytes = b"fake-package"

    import os
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat
    )
    priv = Ed25519PrivateKey.generate()
    pub_der = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)

    resp = await client.post(
        "/modules/install",
        json={
            "manifest_b64": base64.b64encode(manifest_bytes).decode(),
            "package_b64": base64.b64encode(package_bytes).decode(),
            "public_key_b64": base64.b64encode(pub_der).decode(),
        },
    )
    assert resp.status_code == 403
