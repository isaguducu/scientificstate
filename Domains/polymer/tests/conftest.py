"""
conftest.py — pytest session configuration for polymer domain tests.

Adds Core/daemon to sys.path so ClassicalBackend can be imported in
test_backend_integration.py without modifying pyproject.toml.
"""
import sys
from pathlib import Path

_DAEMON_ROOT = Path(__file__).parents[3] / "Core" / "daemon"
if str(_DAEMON_ROOT) not in sys.path:
    sys.path.insert(0, str(_DAEMON_ROOT))
