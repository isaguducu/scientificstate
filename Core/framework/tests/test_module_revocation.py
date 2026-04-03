"""Module revocation checker tests."""


def test_revocation_import():
    from scientificstate.modules.revocation import check_revocation
    assert check_revocation is not None


def test_revoked_domain_version_returns_true():
    from scientificstate.modules.revocation import check_revocation
    revocation_list = [
        {"domain_id": "polymer_science", "version": "1.0.0",
         "reason": "critical bug", "revoked_at": "2026-04-01T00:00:00Z"},
    ]
    assert check_revocation("polymer_science", "1.0.0", revocation_list) is True


def test_active_domain_version_returns_false():
    from scientificstate.modules.revocation import check_revocation
    revocation_list = [
        {"domain_id": "polymer_science", "version": "1.0.0",
         "reason": "critical bug", "revoked_at": "2026-04-01T00:00:00Z"},
    ]
    assert check_revocation("polymer_science", "1.1.0", revocation_list) is False


def test_empty_list_returns_false():
    from scientificstate.modules.revocation import check_revocation
    assert check_revocation("polymer_science", "1.0.0", []) is False


def test_different_domain_not_revoked():
    from scientificstate.modules.revocation import check_revocation
    revocation_list = [
        {"domain_id": "genomics", "version": "2.0.0",
         "reason": "security", "revoked_at": "2026-04-01T00:00:00Z"},
    ]
    assert check_revocation("polymer_science", "2.0.0", revocation_list) is False


def test_multiple_revocations_all_checked():
    from scientificstate.modules.revocation import check_revocation
    revocation_list = [
        {"domain_id": "polymer_science", "version": "0.9.0", "reason": "A", "revoked_at": ""},
        {"domain_id": "polymer_science", "version": "1.0.0", "reason": "B", "revoked_at": ""},
        {"domain_id": "genomics", "version": "2.0.0", "reason": "C", "revoked_at": ""},
    ]
    assert check_revocation("polymer_science", "0.9.0", revocation_list) is True
    assert check_revocation("polymer_science", "1.0.0", revocation_list) is True
    assert check_revocation("polymer_science", "1.1.0", revocation_list) is False
    assert check_revocation("genomics", "2.0.0", revocation_list) is True


def test_partial_match_not_revoked():
    """domain_id AND version must both match."""
    from scientificstate.modules.revocation import check_revocation
    revocation_list = [
        {"domain_id": "polymer_science", "version": "1.0.0", "reason": "", "revoked_at": ""},
    ]
    # Same domain, different version
    assert check_revocation("polymer_science", "2.0.0", revocation_list) is False
    # Different domain, same version
    assert check_revocation("genomics", "1.0.0", revocation_list) is False
