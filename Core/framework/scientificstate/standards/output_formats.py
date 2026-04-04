"""
Parquet / Zarr output — result dict → binary scientific formats.

Supports:
  - Parquet: columnar format via pyarrow (optional dependency)
  - Zarr: chunked N-dimensional arrays via zarr (optional dependency)

Large dataset support: chunked write for both formats.

Pure function: writes to caller-provided path, no database, no network.
"""
from __future__ import annotations

import json
from pathlib import Path


def result_to_parquet(result: dict, output_path: str | Path) -> Path:
    """Write a result dict to a Parquet file.

    Args:
        result: dict of {column_name: value_or_list} — flat or column-oriented data.
        output_path: file path for the Parquet output.

    Returns:
        Path to the written Parquet file.

    Raises:
        ImportError: if pyarrow is not installed.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalize: ensure all values are lists of equal length
    table_data = _normalize_to_columns(result)

    table = pa.table(table_data)
    pq.write_table(table, str(output_path))

    return output_path


def parquet_read_back(parquet_path: str | Path) -> dict:
    """Read a Parquet file back to a dict.

    Args:
        parquet_path: path to the Parquet file.

    Returns:
        dict of {column_name: list_of_values}
    """
    import pyarrow.parquet as pq

    table = pq.read_table(str(parquet_path))
    return {col: table[col].to_pylist() for col in table.column_names}


def result_to_zarr(result: dict, output_path: str | Path) -> Path:
    """Write a result dict to a Zarr archive (directory store).

    Args:
        result: dict of {array_name: value_or_list} — each entry becomes a Zarr array.
        output_path: directory path for the Zarr store.

    Returns:
        Path to the Zarr store directory.

    Raises:
        ImportError: if zarr is not installed.
    """
    import numpy as np
    import zarr
    from zarr.storage import LocalStore

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    store = LocalStore(str(output_path))
    root = zarr.open_group(store, mode="w")

    for key, value in result.items():
        if isinstance(value, list):
            arr = np.array(value)
            root.create_array(key, data=arr)
        elif isinstance(value, (int, float)):
            root.create_array(key, data=np.array([value]))
        elif isinstance(value, dict):
            # Store nested dicts as JSON string in a single-element array
            root.create_array(key, data=np.array([json.dumps(value)]))
        else:
            root.create_array(key, data=np.array([str(value)]))

    # Store metadata
    root.attrs["scientificstate_version"] = "0.1.0"
    root.attrs["format"] = "zarr"

    return output_path


def zarr_read_back(zarr_path: str | Path) -> dict:
    """Read a Zarr archive back to a dict.

    Args:
        zarr_path: path to the Zarr store directory.

    Returns:
        dict of {array_name: list_of_values}
    """
    import zarr
    from zarr.storage import LocalStore

    store = LocalStore(str(zarr_path))
    root = zarr.open_group(store, mode="r")

    data: dict = {}
    for name, node in root.members():
        if isinstance(node, zarr.Array):
            data[name] = node[:].tolist()

    return data


def _normalize_to_columns(data: dict) -> dict:
    """Normalize a flat or mixed dict into column-oriented data for Parquet.

    Scalar values are wrapped in single-element lists.
    All columns are padded to equal length.
    """
    columns: dict = {}
    max_len = 0

    for key, value in data.items():
        if isinstance(value, list):
            columns[key] = value
            max_len = max(max_len, len(value))
        elif isinstance(value, dict):
            columns[key] = [json.dumps(value)]
            max_len = max(max_len, 1)
        else:
            columns[key] = [value]
            max_len = max(max_len, 1)

    # Pad shorter columns with None
    for key in columns:
        if len(columns[key]) < max_len:
            columns[key] = columns[key] + [None] * (max_len - len(columns[key]))

    return columns
