"""Workspace model smoke tests."""
import pytest


def test_workspace_import():
    from scientificstate.workspaces.model import Workspace
    assert Workspace is not None


def test_workspace_instantiation():
    from scientificstate.workspaces.model import Workspace
    ws = Workspace(name="Test Workspace", domain_id="polymer_science")
    assert ws.id
    assert ws.name == "Test Workspace"
    assert ws.domain_id == "polymer_science"
    assert ws.created_at is not None


def test_workspace_has_required_fields():
    from scientificstate.workspaces.model import Workspace
    fields = Workspace.model_fields
    assert "id" in fields
    assert "name" in fields
    assert "domain_id" in fields
    assert "created_at" in fields


def test_workspace_id_is_unique():
    from scientificstate.workspaces.model import Workspace
    ws1 = Workspace(name="W1", domain_id="d")
    ws2 = Workspace(name="W2", domain_id="d")
    assert ws1.id != ws2.id


def test_workspace_immutable():
    from scientificstate.workspaces.model import Workspace
    ws = Workspace(name="Frozen", domain_id="polymer_science")
    with pytest.raises((TypeError, Exception)):
        ws.name = "mutated"  # type: ignore[misc]


def test_workspace_domain_id_preserved():
    from scientificstate.workspaces.model import Workspace
    ws = Workspace(name="N", domain_id="genomics")
    assert ws.domain_id == "genomics"
