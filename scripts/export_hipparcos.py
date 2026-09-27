#!/usr/bin/env python3
"""Export a Hipparcos V<=6 flight-sized catalog NPZ if a TSV is present."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.catalog import CatalogManager
from src.kvector import KVectorTable


def main() -> int:
    cache = ROOT / "data" / "catalogs"
    tsv_candidates = [
        cache / "hipparcos_v6.tsv",
        cache / "starcat.tsv",
        cache / "hip_main.dat",
    ]
    tsv = next((p for p in tsv_candidates if p.exists()), None)
    out = {"status": "missing_tsv", "note": "chưa kiểm được — Hipparcos TSV not in data/catalogs/"}
    if tsv is not None:
        try:
            cat = CatalogManager.load_hipparcos_tsv(tsv, max_mag=6.0, epoch_year=2026.7)
            cat = CatalogManager.filter_close_pairs(cat, 60.0)
            npz = cache / "hipparcos_v6.npz"
            CatalogManager.save_npz(cat, npz)
            kv = KVectorTable.build(cat)
            kv_path = cache / "hipparcos_v6_kvector.npz"
            kv.save(kv_path)
            out = {
                "status": "ok",
                "source": cat.source,
                "n_stars": cat.num_stars,
                "npz_bytes": npz.stat().st_size,
                "kvector_pairs": kv.num_pairs,
                "kvector_bytes": kv_path.stat().st_size,
                "tsv": str(tsv.name),
            }
        except Exception as exc:  # noqa: BLE001
            out = {"status": "error", "error": str(exc), "tsv": str(tsv)}
    dest = ROOT / "data" / "outputs" / "hipparcos_export.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
