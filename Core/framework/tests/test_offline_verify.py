"""OfflineTUFVerifier tests — offline TUF metadata verification."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scientificstate.modules.tuf.offline_verify import OfflineTUFVerifier


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_root_meta() -> dict:
    """Minimal valid TUF root.json structure."""
    return {
        "signed": {
            "_type": "root",
            "spec_version": "1.0.0",
            "version": 1,
            "expires": (datetime.now(tz=timezone.utc) + timedelta(days=365)).isoformat(),
            "keys": {
                "abc123": {
                    "keytype": "ed25519",
                    "scheme": "ed25519",
                    "keyval": {"public": "deadbeef" * 4},
                }
            },
            "roles": {
                "root": {"keyids": ["abc123"], "threshold": 1},
                "targets": {"keyids": ["abc123"], "threshold": 1},
            },
        },
        "signatures": [],
    }


def _make_targets_meta(
    targets: dict | None = None,
    expiry_days: int = 90,
) -> dict:
    """Minimal valid TUF targets.json structure."""
    expires = (datetime.now(tz=timezone.utc) + timedelta(days=expiry_days)).isoformat()
    return {
        "signed": {
            "_type": "targets",
            "spec_version": "1.0.0",
            "version": 1,
            "expires": expires,
            "targets": targets or {
                "polymer_science/1.0.0/module.tar.gz": {
                    "length": 1024,
                    "hashes": {"sha256": "aabbccdd" * 8},
                }
            },
        },
        "signatures": [],
    }


def _write_tuf_dir(tmp: str, root: dict | None = None, targets: dict | None = None) -> Path:
    """Write root.json and targets.json into a temp TUF directory."""
    tuf_dir = Path(tmp) / "tuf"
    tuf_dir.mkdir()
    if root is not None:
        (tuf_dir / "root.json").write_text(json.dumps(root), encoding="utf-8")
    if targets is not None:
        (tuf_dir / "targets.json").write_text(json.dumps(targets), encoding="utf-8")
    return tuf_dir


# ── Valid target ─────────────────────────────────────────────────────────────


def test_valid_target():
    """Valid target hash matches — ok=True."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = _write_tuf_dir(tmp, _make_root_meta(), _make_targets_meta())
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target(
            "polymer_science/1.0.0/module.tar.gz",
            "aabbccdd" * 8,
        )
        assert result.ok is True
        assert result.error is None


# ── Expired within grace period ──────────────────────────────────────────────


def test_expired_within_grace_period():
    """Metadata expired < 30 days ago — still ok=True."""
    with tempfile.TemporaryDirectory() as tmp:
        targets = _make_targets_meta(expiry_days=-10)  # expired 10 days ago
        tuf_dir = _write_tuf_dir(tmp, _make_root_meta(), targets)
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target(
            "polymer_science/1.0.0/module.tar.gz",
            "aabbccdd" * 8,
        )
        assert result.ok is True


# ── Expired beyond grace period ──────────────────────────────────────────────


def test_expired_beyond_grace_period():
    """Metadata expired > 30 days ago — ok=False."""
    with tempfile.TemporaryDirectory() as tmp:
        targets = _make_targets_meta(expiry_days=-60)  # expired 60 days ago
        tuf_dir = _write_tuf_dir(tmp, _make_root_meta(), targets)
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target(
            "polymer_science/1.0.0/module.tar.gz",
            "aabbccdd" * 8,
        )
        assert result.ok is False
        assert "grace period" in result.error


# ── Invalid root signature ───────────────────────────────────────────────────


def test_missing_root():
    """No root.json — ok=False."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = _write_tuf_dir(tmp, root=None, targets=_make_targets_meta())
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target("x/1.0.0/module.tar.gz", "abc123")
        assert result.ok is False
        assert "root.json" in result.error


def test_invalid_root_structure():
    """Malformed root.json (missing _type) — ok=False."""
    with tempfile.TemporaryDirectory() as tmp:
        bad_root = {"signed": {"keys": {}, "roles": {}}, "signatures": []}
        tuf_dir = _write_tuf_dir(tmp, root=bad_root, targets=_make_targets_meta())
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target("x/1.0.0/module.tar.gz", "abc123")
        assert result.ok is False
        assert "structure" in result.error


# ── Unknown target ───────────────────────────────────────────────────────────


def test_unknown_target():
    """Target not in targets.json — ok=False."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = _write_tuf_dir(tmp, _make_root_meta(), _make_targets_meta())
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target("unknown/1.0.0/module.tar.gz", "abc123")
        assert result.ok is False
        assert "not found" in result.error


# ── Hash mismatch ────────────────────────────────────────────────────────────


def test_hash_mismatch():
    """Hash does not match targets.json — ok=False."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = _write_tuf_dir(tmp, _make_root_meta(), _make_targets_meta())
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target(
            "polymer_science/1.0.0/module.tar.gz",
            "wrong_hash_value",
        )
        assert result.ok is False
        assert "mismatch" in result.error


# ── Missing targets.json ────────────────────────────────────────────────────


def test_missing_targets():
    """No targets.json — ok=False."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = _write_tuf_dir(tmp, root=_make_root_meta(), targets=None)
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target("x/1.0.0/module.tar.gz", "abc123")
        assert result.ok is False
        assert "targets.json" in result.error


# ── Properties ───────────────────────────────────────────────────────────────


def test_has_trust_chain():
    """Trust chain file detected."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = _write_tuf_dir(tmp, _make_root_meta(), _make_targets_meta())
        (tuf_dir / "trust-chain.json").write_text("{}", encoding="utf-8")
        verifier = OfflineTUFVerifier(tuf_dir)
        assert verifier.has_trust_chain is True


def test_no_trust_chain():
    """No trust chain file."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = _write_tuf_dir(tmp, _make_root_meta(), _make_targets_meta())
        verifier = OfflineTUFVerifier(tuf_dir)
        assert verifier.has_trust_chain is False


def test_root_meta_accessor():
    """root_meta property returns loaded metadata."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_root_meta()
        tuf_dir = _write_tuf_dir(tmp, root, _make_targets_meta())
        verifier = OfflineTUFVerifier(tuf_dir)
        assert verifier.root_meta is not None
        assert verifier.root_meta["signed"]["_type"] == "root"


def test_targets_meta_accessor():
    """targets_meta property returns loaded metadata."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = _write_tuf_dir(tmp, _make_root_meta(), _make_targets_meta())
        verifier = OfflineTUFVerifier(tuf_dir)
        assert verifier.targets_meta is not None
        assert "targets" in verifier.targets_meta["signed"]


# ── Corrupt JSON ─────────────────────────────────────────────────────────────


def test_corrupt_root_json():
    """Corrupted root.json file — treated as missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = Path(tmp) / "tuf"
        tuf_dir.mkdir()
        (tuf_dir / "root.json").write_text("{{not json", encoding="utf-8")
        (tuf_dir / "targets.json").write_text(
            json.dumps(_make_targets_meta()), encoding="utf-8"
        )
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target("x/1.0.0/module.tar.gz", "abc123")
        assert result.ok is False
        assert "root.json" in result.error


def test_corrupt_targets_json():
    """Corrupted targets.json file — treated as missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tuf_dir = Path(tmp) / "tuf"
        tuf_dir.mkdir()
        (tuf_dir / "root.json").write_text(
            json.dumps(_make_root_meta()), encoding="utf-8"
        )
        (tuf_dir / "targets.json").write_text("not json!", encoding="utf-8")
        verifier = OfflineTUFVerifier(tuf_dir)

        result = verifier.verify_target("x/1.0.0/module.tar.gz", "abc123")
        assert result.ok is False
        assert "targets.json" in result.error
