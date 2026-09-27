#!/usr/bin/env python3
"""Download Yale BSC5 (291 548 bytes) into star_tracker/data/catalogs/BSC5."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.catalog import BSC5_SIZE, CatalogManager  # noqa: E402


def main() -> int:
    dest = ROOT / "data" / "catalogs" / "BSC5"
    path = CatalogManager.fetch_bsc5(dest)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    header = CatalogManager.parse_bsc5_header(path)
    print(f"BSC5 path     : {path}")
    print(f"size          : {len(data)} bytes (expected {BSC5_SIZE})")
    print(f"sha256        : {digest}")
    print(f"endian        : {header['endian']}")
    print(f"STARN         : {header['STARN']}")
    print(f"NBENT         : {header['NBENT']}")
    print(f"J2000 flag    : {header['j2000']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
