#!/usr/bin/env python3
"""Boresight error of the Tracker pipeline, same angle used for tetra3 and LOST.

The angle is the sky separation between the solved +Z axis and the +Z axis of
the quaternion that drew the frame. It is not the three-axis rotation.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.camera import demo_camera
from src.catalog import CatalogManager
from src.demo_session import load_pipeline_cfg
from src.kvector import build_or_load
from src.pipeline import StarTrackerPipeline
from src.quaternion import boresight_ra_dec_deg

DATASET = ROOT / "data" / "benchmark_dataset"
OUT = DATASET / "tracker_pointing.jsonl"
REPORT = DATASET / "external_compare_report.md"
EXTERNAL = DATASET / "external_compare.jsonl"


def angsep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(r1 - r2)
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))) * 3600.0)


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def pointing_stats(rows: list[dict], key: str = "sep_boresight_arcsec") -> dict:
    ok = [row for row in rows if row.get("success") and row.get(key) is not None]
    values = np.asarray([float(row[key]) for row in ok], dtype=np.float64)
    under = int(np.sum(values < 10.0)) if values.size else 0
    wild = int(np.sum(values > 3600.0)) if values.size else 0
    return {
        "n": len(rows),
        "ok": len(ok),
        "under10": under,
        "over1deg": wild,
        "median": None if not values.size else float(np.median(values)),
        "p95": None if not values.size else float(np.percentile(values, 95)),
        "max": None if not values.size else float(np.max(values)),
    }


def fmt(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1000:
        return f"{value:.0f}″"
    return f"{value:.2f}″".replace(".", ",")


def write_same_metric_table() -> None:
    ours = load_jsonl(OUT)
    external = load_jsonl(EXTERNAL)
    columns = {
        "Tracker": pointing_stats(ours),
        "tetra3": pointing_stats([row for row in external if row.get("solver") == "tetra3"]),
        "LOST": pointing_stats([row for row in external if row.get("solver") == "lost"]),
    }
    body = REPORT.read_text(encoding="utf-8")
    marker = "# So sánh tetra3 và LOST trên bộ benchmark"
    rest = body[body.index(marker):] if marker in body else ""
    lines = [
        "# So sánh ba bên trên cùng một đại lượng",
        "",
        "Đại lượng chung là khoảng cách trên trời, tính bằng giây cung, giữa hướng nhìn giải được và hướng +Z của quaternion đã dùng để vẽ khung. Đây không phải góc quay ba trục.",
        "",
        "| | Tracker | tetra3 | LOST |",
        "|---|---:|---:|---:|",
    ]
    labels = [
        ("Ra được một hướng", lambda s: f"{s['ok']} / {s['n']}"),
        ("Dưới 10″", lambda s: str(s["under10"])),
        ("Trung vị", lambda s: fmt(s["median"])),
        ("Phân vị 95", lambda s: fmt(s["p95"])),
        ("Lệch hơn 1°", lambda s: str(s["over1deg"])),
        ("Lớn nhất", lambda s: fmt(s["max"])),
    ]
    for title, getter in labels:
        lines.append("| " + title + " | " + " | ".join(getter(columns[name]) for name in columns) + " |")
    lines.extend(["", rest])
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    manifest = load_jsonl(DATASET / "manifest.jsonl")
    done = {row["file"] for row in load_jsonl(OUT)}
    pending = [row for row in manifest if row["file"] not in done]
    cam = demo_camera()
    cat = CatalogManager.load_npz(ROOT / "data" / "catalogs" / "bsc5_v6.0.npz")
    kv = build_or_load(cat, ROOT / "data" / "catalogs")
    pipe = StarTrackerPipeline(cam, cat, kv, load_pipeline_cfg("full", ROOT))
    print(f"[*] tracker pointing: {len(pending)} frames, {len(done)} stored", flush=True)
    handle = OUT.open("a", encoding="utf-8")
    t0 = time.perf_counter()
    try:
        for i, row in enumerate(pending, start=1):
            path = DATASET / row["file"]
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            sep = None
            success = False
            error = None
            try:
                if img is None:
                    raise RuntimeError(f"cannot read {path}")
                if img.ndim == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                result = pipe.process_frame(img)
                success = bool(result.success and result.q is not None)
                if success:
                    ra, dec = boresight_ra_dec_deg(result.q)
                    gt_ra, gt_dec = boresight_ra_dec_deg(np.asarray(row["q_gt"], dtype=np.float64))
                    sep = angsep_arcsec(ra, dec, gt_ra, gt_dec)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            handle.write(json.dumps({
                "solver": "tracker",
                "file": row["file"],
                "noise": row.get("noise"),
                "success": success,
                "sep_boresight_arcsec": sep,
                "error": error,
            }) + "\n")
            handle.flush()
            if i == 1 or i % 25 == 0 or i == len(pending):
                text = "fail" if sep is None else f"{sep:.2f}"
                rate = (time.perf_counter() - t0) / i
                left = (len(pending) - i) * rate / 60.0
                print(f"  {i}/{len(pending)} {row['file']} {text} arcsec  eta {left:.1f} min", flush=True)
    finally:
        handle.close()
    write_same_metric_table()
    print(f"[*] report {REPORT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
