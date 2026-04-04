"""Parquet/Zarr output tests — write + read-back verification."""

import json
import tempfile
from pathlib import Path

import pytest


# ── Parquet tests ─────────────────────────────────────────────────────────────

def _parquet_available() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


def _zarr_available() -> bool:
    try:
        import zarr  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _parquet_available(), reason="pyarrow not installed")
class TestParquet:
    def test_parquet_write_read_back(self):
        from scientificstate.standards.output_formats import result_to_parquet, parquet_read_back

        result = {"mw": [50000.0, 51000.0], "pdi": [1.5, 1.6]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.parquet"
            written = result_to_parquet(result, path)
            assert written.exists()

            data = parquet_read_back(written)
            assert data["mw"] == [50000.0, 51000.0]
            assert data["pdi"] == [1.5, 1.6]

    def test_parquet_scalar_values(self):
        from scientificstate.standards.output_formats import result_to_parquet, parquet_read_back

        result = {"mw": 50000.0, "status": "ok"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scalar.parquet"
            written = result_to_parquet(result, path)
            assert written.exists()

            data = parquet_read_back(written)
            assert data["mw"] == [50000.0]
            assert data["status"] == ["ok"]

    def test_parquet_dict_value(self):
        from scientificstate.standards.output_formats import result_to_parquet, parquet_read_back

        result = {"counts": {"00": 512, "11": 512}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dict.parquet"
            written = result_to_parquet(result, path)
            assert written.exists()

            data = parquet_read_back(written)
            parsed = json.loads(data["counts"][0])
            assert parsed["00"] == 512

    def test_parquet_creates_parent_dirs(self):
        from scientificstate.standards.output_formats import result_to_parquet

        result = {"x": [1, 2, 3]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "dir" / "test.parquet"
            written = result_to_parquet(result, path)
            assert written.exists()

    def test_parquet_mixed_lengths_padded(self):
        from scientificstate.standards.output_formats import result_to_parquet, parquet_read_back

        result = {"a": [1, 2, 3], "b": 42}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mixed.parquet"
            written = result_to_parquet(result, path)
            data = parquet_read_back(written)
            assert len(data["a"]) == 3
            assert len(data["b"]) == 3
            assert data["b"][0] == 42


# ── Zarr tests ────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _zarr_available(), reason="zarr/numpy not installed")
class TestZarr:
    def test_zarr_write_read_back(self):
        from scientificstate.standards.output_formats import result_to_zarr, zarr_read_back

        result = {"mw": [50000.0, 51000.0], "pdi": [1.5, 1.6]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.zarr"
            written = result_to_zarr(result, path)
            assert written.exists()

            data = zarr_read_back(written)
            assert data["mw"] == [50000.0, 51000.0]
            assert data["pdi"] == [1.5, 1.6]

    def test_zarr_scalar_values(self):
        from scientificstate.standards.output_formats import result_to_zarr, zarr_read_back

        result = {"mw": 50000.0, "count": 42}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scalar.zarr"
            written = result_to_zarr(result, path)
            assert written.exists()

            data = zarr_read_back(written)
            assert data["mw"] == [50000.0]
            assert data["count"] == [42]

    def test_zarr_dict_value(self):
        from scientificstate.standards.output_formats import result_to_zarr, zarr_read_back

        result = {"metadata": {"key": "value"}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dict.zarr"
            written = result_to_zarr(result, path)
            assert written.exists()

            data = zarr_read_back(written)
            parsed = json.loads(data["metadata"][0])
            assert parsed["key"] == "value"

    def test_zarr_has_metadata(self):
        import zarr as zarr_lib
        from zarr.storage import LocalStore
        from scientificstate.standards.output_formats import result_to_zarr

        result = {"x": [1, 2, 3]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "meta.zarr"
            result_to_zarr(result, path)

            store = LocalStore(str(path))
            root = zarr_lib.open_group(store, mode="r")
            assert root.attrs["format"] == "zarr"
            assert root.attrs["scientificstate_version"] == "0.1.0"

    def test_zarr_creates_parent_dirs(self):
        from scientificstate.standards.output_formats import result_to_zarr

        result = {"x": [1, 2]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "dir" / "test.zarr"
            written = result_to_zarr(result, path)
            assert written.exists()
