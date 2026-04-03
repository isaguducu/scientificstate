"""
pygcms_reader.py — Py-GC-MS block data reader.

Extracted from NitechLAB/data_engine.py (file I/O and data model parts only).
UI-coupled code (tkinter, display, export) is not included.

Changes from source:
  - Removed all tkinter / UI references.
  - Removed DataEngine._ensure_directories() auto-directory creation.
  - Removed export / CSV write methods.
  - Kept: BlockData, DataPoint, read_block, read_all_blocks, load_block_names.
  - All scientific logic preserved verbatim.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
from scipy.signal import find_peaks


# ============================================================================
# CONSTANTS
# ============================================================================

NUM_BLOCKS = 100
MAX_ROWS_PER_BLOCK = 10_000_000
DEFAULT_DATA_DIR = "data_blocks"


# ============================================================================
# DATA CLASSES
# ============================================================================

class SortOrder(Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"


class SortColumn(Enum):
    MZ = "m/z"
    INTENSITY = "intensity"
    INDEX = "index"


class FilterMode(Enum):
    GREATER_THAN = ">"
    LESS_THAN = "<"
    EQUAL = "="
    BETWEEN = "between"
    TOP_N = "top_n"
    BOTTOM_N = "bottom_n"
    PERCENTILE = "percentile"


@dataclass
class DataPoint:
    mz: float
    intensity: float
    index: int = 0
    block_id: int = 0


@dataclass
class BlockData:
    block_id: int
    name: str
    data: List[DataPoint] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return len(self.data)

    @property
    def mz_values(self) -> np.ndarray:
        return np.array([p.mz for p in self.data])

    @property
    def intensity_values(self) -> np.ndarray:
        return np.array([p.intensity for p in self.data])

    def to_blocks_dict(self) -> Dict:
        """Convert to the standard blocks_data dict used by PCA/HCA methods."""
        return {
            "block_id": self.block_id,
            "mz": self.mz_values,
            "intensity": self.intensity_values,
            "temperature": self.metadata.get("temperature"),
            "name": self.name,
        }


# ============================================================================
# BLOCK READER
# ============================================================================

class PyGCMSReader:
    """
    Reads Py-GC-MS block files from a directory of block_XXX.txt files.

    File format (per block):
      Each row: m/z [tab or space] intensity
      Optional block_names.txt: block_id,name_string (one per line)
    """

    def __init__(self, data_dir: str = DEFAULT_DATA_DIR,
                 resolution: float = 22000.0):
        self.data_dir = data_dir
        self.resolution = resolution
        self.block_names: Dict[int, str] = {}
        if os.path.isdir(data_dir):
            self._load_block_names()

    def _get_block_path(self, block_id: int) -> str:
        return os.path.join(self.data_dir, f"block_{block_id:03d}.txt")

    def _load_block_names(self) -> None:
        meta_path = os.path.join(self.data_dir, "block_names.txt")
        if not os.path.exists(meta_path):
            return
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(",", 1)
                    if len(parts) >= 2:
                        try:
                            bid = int(parts[0].strip())
                            self.block_names[bid] = parts[1].strip()
                        except ValueError:
                            pass
        except OSError:
            pass

    def load_experimental_params(self, file_path: str) -> bool:
        """Load instrument resolution from an experimental parameters file."""
        try:
            import re
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            match = re.search(r'Resolution\s+(\d+)', content)
            if match:
                self.resolution = float(match.group(1))
                return True
        except Exception:
            pass
        return False

    def calculate_tolerance(self, mz: float, sigma: float = 5.0) -> float:
        """Calculate m/z tolerance based on instrument resolution."""
        fwhm = mz / self.resolution
        return fwhm * sigma

    def read_block(
        self,
        block_id: int,
        max_rows: Optional[int] = MAX_ROWS_PER_BLOCK,
        use_cache: bool = True,
    ) -> Optional[BlockData]:
        """
        Read a single block from disk.

        Returns None if file is missing or empty.
        """
        path = self._get_block_path(block_id)
        if not os.path.exists(path):
            return None

        name = self.block_names.get(block_id, f"Block {block_id}")
        data: List[DataPoint] = []
        row_count = 0

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if max_rows is not None and row_count >= max_rows:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.replace("\t", " ").split()
                    if len(parts) < 2:
                        continue
                    try:
                        mz = float(parts[0])
                        intensity = float(parts[1])
                        data.append(DataPoint(
                            mz=mz, intensity=intensity,
                            index=i, block_id=block_id,
                        ))
                        row_count += 1
                    except ValueError:
                        continue
        except OSError:
            return None

        return BlockData(
            block_id=block_id,
            name=name,
            data=data,
            metadata={"row_count": row_count},
        )

    def group_peaks(self, data: List[DataPoint]) -> List[DataPoint]:
        """
        Find local maxima (chromatographic peaks) using scipy find_peaks.

        Returns centroid peaks only (reduces data before clustering).
        """
        if not data:
            return []

        sorted_data = sorted(data, key=lambda p: p.mz)
        mz_values = np.array([p.mz for p in sorted_data])
        intensity_values = np.array([p.intensity for p in sorted_data])

        if len(intensity_values) < 3:
            return sorted_data

        max_intensity = np.max(intensity_values)
        peak_indices, _ = find_peaks(
            intensity_values,
            prominence=max_intensity * 0.01,
            distance=2,
            height=max_intensity * 0.001,
        )

        if len(peak_indices) == 0:
            n_top = max(10, len(sorted_data) // 10)
            peak_indices = np.sort(np.argsort(intensity_values)[-n_top:])

        return [DataPoint(mz=mz_values[i], intensity=intensity_values[i])
                for i in peak_indices]

    def read_block_grouped(self, block_id: int) -> Optional[BlockData]:
        """Read a block and return centroid-grouped peaks."""
        raw = self.read_block(block_id, max_rows=None, use_cache=False)
        if raw is None or not raw.data:
            return raw
        grouped = self.group_peaks(raw.data)
        return BlockData(
            block_id=raw.block_id,
            name=raw.name,
            data=grouped,
            metadata={
                "raw_count": len(raw.data),
                "grouped_count": len(grouped),
                "resolution": self.resolution,
            },
        )

    def read_all_blocks(
        self,
        block_ids: Optional[List[int]] = None,
        grouped: bool = True,
    ) -> List[Dict]:
        """
        Read multiple blocks and return as blocks_data list for PCA/HCA.

        Args:
            block_ids: Block IDs to load. None → auto-discover from directory.
            grouped: Apply find_peaks grouping if True (default).

        Returns:
            List of dicts: {block_id, mz, intensity, temperature, name}
        """
        if block_ids is None:
            block_ids = self._discover_block_ids()

        results: List[Dict] = []
        for bid in sorted(block_ids):
            blk = self.read_block_grouped(bid) if grouped else self.read_block(bid)
            if blk is None:
                continue
            temp = self._parse_temperature(blk.name) or (bid * 10 + 50)
            results.append({
                "block_id": blk.block_id,
                "mz": blk.mz_values,
                "intensity": blk.intensity_values,
                "temperature": temp,
                "name": blk.name,
            })

        return results

    def _discover_block_ids(self) -> List[int]:
        """Find all block_XXX.txt files in data_dir."""
        ids: List[int] = []
        if not os.path.isdir(self.data_dir):
            return ids
        for fname in os.listdir(self.data_dir):
            if fname.startswith("block_") and fname.endswith(".txt"):
                try:
                    bid = int(fname[6:-4])
                    ids.append(bid)
                except ValueError:
                    pass
        return sorted(ids)

    @staticmethod
    def _parse_temperature(name: str) -> Optional[float]:
        """Extract temperature (°C) from a block name string like '60 derece'."""
        import re
        match = re.search(r'(\d+(?:\.\d+)?)\s*(?:derece|°C|C)', name, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None
