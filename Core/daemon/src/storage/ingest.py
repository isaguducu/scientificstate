"""
Immutable raw ingest — content-addressed filesystem store.

Constitutional constraint P1 (Immutability):
- Raw data is NEVER mutated once ingested.
- Each unique file is stored exactly once (content-hash dedup).
- Attempting to re-ingest the same content → FileExistsError (→ HTTP 409).

Store layout (Main_Source_desktop.md §5.2):
  <store_root>/raw/<sha256>/original.<ext>
  <store_root>/raw/<sha256>/metadata.json
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


def ingest_raw_file(file_path: Path, store_root: Path) -> dict:
    """
    Ingest a raw file into the content-addressed store.

    Args:
        file_path:  Absolute path to the source file (must exist).
        store_root: Root directory of the immutable store.

    Returns:
        Metadata dict: {content_hash, filename, file_size, stored_path}.

    Raises:
        FileNotFoundError: If file_path does not exist.
        FileExistsError:   If content_hash already present in store (→ HTTP 409).
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"Source file not found: {file_path}")

    content = file_path.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()

    dest_dir = store_root / "raw" / content_hash
    if dest_dir.exists():
        raise FileExistsError(
            f"Dataset already ingested (content_hash={content_hash})"
        )

    dest_dir.mkdir(parents=True)

    # Preserve original extension; fall back to ".bin" if none.
    ext = file_path.suffix or ".bin"
    dest_file = dest_dir / f"original{ext}"
    shutil.copy2(file_path, dest_file)

    metadata = {
        "content_hash": content_hash,
        "filename": file_path.name,
        "file_size": len(content),
        "stored_path": str(dest_file),
    }
    (dest_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    return metadata
