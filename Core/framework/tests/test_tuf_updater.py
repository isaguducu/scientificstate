"""TUF updater tests — update detection and root chain validation."""
from scientificstate.modules.signer import generate_keypair
from scientificstate.modules.tuf.root import generate_root, sign_root
from scientificstate.modules.tuf.targets import generate_targets
from scientificstate.modules.tuf.updater import check_for_updates, validate_root_chain


# ── check_for_updates ─────────────────────────────────────────────────────────

def test_check_updates_no_changes():
    modules = [{"module_id": "polymer", "version": "1.0.0", "tarball_hash": "aaa"}]
    current = generate_targets(modules)
    remote = generate_targets(modules)
    result = check_for_updates(current, remote)
    assert result["targets_updated"] is False
    assert result["new_targets"] == []
    assert result["updated_targets"] == []


def test_check_updates_new_target():
    current = generate_targets([
        {"module_id": "polymer", "version": "1.0.0", "tarball_hash": "aaa"},
    ])
    remote = generate_targets([
        {"module_id": "polymer", "version": "1.0.0", "tarball_hash": "aaa"},
        {"module_id": "climate", "version": "0.5.0", "tarball_hash": "bbb"},
    ])
    result = check_for_updates(current, remote)
    assert result["targets_updated"] is True
    assert "climate/0.5.0/module.tar.gz" in result["new_targets"]
    assert result["updated_targets"] == []


def test_check_updates_changed_hash():
    current = generate_targets([
        {"module_id": "polymer", "version": "1.0.0", "tarball_hash": "aaa"},
    ])
    remote = generate_targets([
        {"module_id": "polymer", "version": "1.0.0", "tarball_hash": "bbb"},  # changed
    ])
    result = check_for_updates(current, remote)
    assert result["targets_updated"] is True
    assert result["new_targets"] == []
    assert "polymer/1.0.0/module.tar.gz" in result["updated_targets"]


def test_check_updates_removed_target():
    """Removed targets are not flagged — only additions and changes."""
    current = generate_targets([
        {"module_id": "polymer", "version": "1.0.0", "tarball_hash": "aaa"},
        {"module_id": "genomics", "version": "2.0.0", "tarball_hash": "bbb"},
    ])
    remote = generate_targets([
        {"module_id": "polymer", "version": "1.0.0", "tarball_hash": "aaa"},
    ])
    result = check_for_updates(current, remote)
    assert result["targets_updated"] is False


def test_check_updates_mixed():
    current = generate_targets([
        {"module_id": "polymer", "version": "1.0.0", "tarball_hash": "aaa"},
    ])
    remote = generate_targets([
        {"module_id": "polymer", "version": "1.0.0", "tarball_hash": "changed"},
        {"module_id": "climate", "version": "0.1.0", "tarball_hash": "new"},
    ])
    result = check_for_updates(current, remote)
    assert result["targets_updated"] is True
    assert len(result["new_targets"]) == 1
    assert len(result["updated_targets"]) == 1


# ── validate_root_chain ──────────────────────────────────────────────────────

def test_validate_root_chain_valid():
    priv, pub = generate_keypair()
    current = generate_root(pub, version=1)
    sign_root(current, priv, pub)

    new = generate_root(pub, version=2)
    sign_root(new, priv, pub)

    assert validate_root_chain(current, new, [pub]) is True


def test_validate_root_chain_invalid_version_not_incremented():
    priv, pub = generate_keypair()
    current = generate_root(pub, version=2)
    sign_root(current, priv, pub)

    new = generate_root(pub, version=2)  # same version
    sign_root(new, priv, pub)

    assert validate_root_chain(current, new, [pub]) is False


def test_validate_root_chain_invalid_version_decremented():
    priv, pub = generate_keypair()
    current = generate_root(pub, version=3)
    sign_root(current, priv, pub)

    new = generate_root(pub, version=1)  # lower version
    sign_root(new, priv, pub)

    assert validate_root_chain(current, new, [pub]) is False


def test_validate_root_chain_wrong_signer():
    priv1, pub1 = generate_keypair()
    priv2, pub2 = generate_keypair()

    current = generate_root(pub1, version=1)
    sign_root(current, priv1, pub1)

    # New root signed by different key (not trusted by current)
    new = generate_root(pub2, version=2)
    sign_root(new, priv2, pub2)

    assert validate_root_chain(current, new, [pub1, pub2]) is False


def test_validate_root_chain_unsigned_new_root():
    priv, pub = generate_keypair()
    current = generate_root(pub, version=1)
    sign_root(current, priv, pub)

    new = generate_root(pub, version=2)
    # Not signed

    assert validate_root_chain(current, new, [pub]) is False
