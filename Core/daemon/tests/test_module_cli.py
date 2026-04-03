"""Tests for module_cli — argument parsing and handler dispatch."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parents[1]))

from src.cli.module_cli import main


def test_cli_list_help():
    """CLI 'list' subcommand is recognized."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["prog", "list", "--help"]):
            main()
    # --help exits with 0
    assert exc_info.value.code == 0


def test_cli_search_help():
    """CLI 'search' subcommand is recognized."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["prog", "search", "--help"]):
            main()
    assert exc_info.value.code == 0


def test_cli_no_command_exits():
    """CLI without subcommand exits with error."""
    with pytest.raises(SystemExit) as exc_info:
        with patch("sys.argv", ["prog"]):
            main()
    assert exc_info.value.code != 0
