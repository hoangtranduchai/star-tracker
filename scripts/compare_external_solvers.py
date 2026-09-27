#!/usr/bin/env python3
"""Run the benchmark TIFFs through ESA tetra3 and UW LOST.

The score is the angle on the sky between the solver's reported aim point and
the sky direction of that solver's own image-center pixel under the quaternion
that drew the frame. tetra3 and LOST place that center at (width/2, height/2).
The benchmark quaternion points +Z through ((width-1)/2, (height-1)/2), half a
pixel away. Those two sky directions are both recorded.

LOST reads 8-bit PNG. Each TIFF is mapped with DN/16, the same 12-bit to 8-bit
scale used for the old preview images. tetra3 reads the uint16 TIFF directly.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
STAR = ROOT / "star_tracker"
sys.path.insert(0, str(ROOT / "third_party" / "tetra3"))
sys.path.insert(0, str(STAR))

from src.camera import demo_camera  # noqa: E402
from src.quaternion import boresight_ra_dec_deg, to_dcm  # noqa: E402

LOST_BIN = "third_party/lost/lost"
LOST_DB = "third_party/lost/bsc-catalog.dat"
ATT_WIN = STAR / "data" / "benchmark_dataset" / "_lost_attitude.txt"
PNG_WIN = STAR / "data" / "benchmark_dataset" / "_lost_frame.png"


def angsep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    c = np.sin(d1) * np.sin(d2) + np.cos(d1) * np.cos(d2) * np.cos(r1 - r2)
    return float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))) * 3600.0)


def sky_of_pixel(q: np.ndarray, cam, u: float, v: float) -> tuple[float, float]:
    """J2000 RA/Dec of one pixel. Camera +Z is the boresight, +X follows columns."""
    direction = np.array([(u - cam.cx) / cam.fx, (v - cam.cy) / cam.fy, 1.0], dtype=np.float64)
    direction /= np.linalg.norm(direction)
    inertial = to_dcm(q).T @ direction
    ra = float(np.degrees(np.arctan2(inertial[1], inertial[0])) % 360.0)
    dec = float(np.degrees(np.arcsin(np.clip(inertial[2], -1.0, 1.0))))
    return ra, dec


def wsl_path(path: Path) -> str:
    text = str(path.resolve())
    drive, rest = text[0], text[2:].replace("\\", "/")
    return f"/mnt/{drive.lower()}{rest}"


def load_rows(dataset: Path) -> list[dict]:
    rows = []
    for line in (dataset / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_done(path: Path, solver: str) -> set[str]:
    if not path.is_file():
        return set()
    done = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("solver") == solver and row.get("file"):
            done.add(row["file"])
    return done


def solve_tetra(t3, image: Image.Image, fov_deg: float) -> dict:
    t0 = time.perf_counter()
    sol = t3.solve_from_image(image, fov_estimate=fov_deg, fov_max_error=0.5, distortion=0)
    elapsed = (time.perf_counter() - t0) * 1000.0
    ra = sol.get("RA")
    ok = ra is not None and not (isinstance(ra, float) and np.isnan(ra))
    return {
        "ok": bool(ok),
        "ra": None if not ok else float(ra),
        "dec": None if not ok else float(sol["Dec"]),
        "roll": None if not ok else float(sol["Roll"]),
        "fov": None if sol.get("FOV") is None else float(sol["FOV"]),
        "matches": None if sol.get("Matches") is None else int(sol["Matches"]),
        "rmse_arcsec": None if sol.get("RMSE") is None else float(sol["RMSE"]),
        "elapsed_ms": elapsed,
    }


def solve_lost(tif: Path) -> dict:
    arr = np.array(Image.open(tif))
    png = np.clip(arr.astype(np.float32) / 16.0, 0, 255).astype(np.uint8)
    Image.fromarray(png, mode="L").save(PNG_WIN)
    if ATT_WIN.exists():
        ATT_WIN.unlink()
    cmd = [
        "wsl", "-d", "Ubuntu-24.04", "-e", "bash", "-lc",
        "cd third_party/lost && ./lost pipeline "
        f"--png {wsl_path(PNG_WIN)} --focal-length 50 --pixel-size 3.72 "
        "--centroid-algo cog --centroid-mag-filter 4 --star-id-algo py --attitude-algo dqm "
        f"--database {LOST_DB} --print-attitude {wsl_path(ATT_WIN)}",
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    elapsed = (time.perf_counter() - t0) * 1000.0
    text = ATT_WIN.read_text(encoding="utf-8", errors="replace") if ATT_WIN.is_file() else ""
    fields = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            fields[parts[0]] = parts[1]
    ok = fields.get("attitude_known") == "1"
    return {
        "ok": ok,
        "ra": float(fields["attitude_ra"]) if ok else None,
        "dec": float(fields["attitude_de"]) if ok else None,
        "roll": float(fields["attitude_roll"]) if ok else None,
        "fov": None,
        "matches": None,
        "rmse_arcsec": None,
        "elapsed_ms": elapsed,
        "returncode": proc.returncode,
    }


def score_solution(sol: dict, q: np.ndarray, cam, solver: str, row: dict) -> dict:
    bore_ra, bore_dec = boresight_ra_dec_deg(q)
    center_ra, center_dec = sky_of_pixel(q, cam, cam.width / 2.0, cam.height / 2.0)
    sep_center = None
    sep_bore = None
    if sol["ok"]:
        sep_center = angsep_arcsec(sol["ra"], sol["dec"], center_ra, center_dec)
        sep_bore = angsep_arcsec(sol["ra"], sol["dec"], bore_ra, bore_dec)
    return {
        "solver": solver,
        "file": row["file"],
        "split": row.get("split"),
        "noise": row.get("noise"),
        "roll_deg": row.get("roll_deg"),
        "slew_deg_s": row.get("slew_deg_s"),
        "success": sol["ok"],
        "ra": sol["ra"],
        "dec": sol["dec"],
        "roll": sol["roll"],
        "gt_center_ra": center_ra,
        "gt_center_dec": center_dec,
        "gt_boresight_ra": bore_ra,
        "gt_boresight_dec": bore_dec,
        "sep_center_arcsec": sep_center,
        "sep_boresight_arcsec": sep_bore,
        "matches": sol["matches"],
        "rmse_arcsec": sol["rmse_arcsec"],
        "elapsed_ms": sol["elapsed_ms"],
    }


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": None, "p95": None, "max": None}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "n": int(arr.size),
        "median": float(np.median(arr)),
        "p95": float(np.percentile(arr, 95)),
        "max": float(np.max(arr)),
    }


def write_report(path: Path, rows: list[dict]) -> None:
    lines = [
        "# So sánh tetra3 và LOST trên bộ benchmark",
        "",
        "Số liệu là khoảng cách trên trời, tính bằng giây cung, giữa điểm solver báo là tâm ảnh và điểm trên trời của pixel (rộng/2, cao/2) dưới quaternion đã dùng để vẽ khung.",
        "",
        "Đó là tâm ảnh mà tetra3 và LOST dùng. Quaternion của bộ benchmark chĩa trục +Z qua pixel ((rộng-1)/2, (cao-1)/2), lệch nửa pixel, khoảng 5,6″. Cột lệch hướng nhìn riêng ghi khoảng cách tới điểm đó.",
        "",
        "LOST chỉ đọc PNG 8 bit. Mỗi TIFF được chia 16, đúng thang 12 bit sang 8 bit. Đốm một pixel bị bỏ (`--centroid-mag-filter 4`) vì hot pixel bão hòa thành một điểm sáng hơn cả sao. tetra3 đọc TIFF uint16 gốc và tự loại đốm nhỏ hơn 5 pixel.",
        "",
        "Database tetra3 là bản mặc định, trường nhìn 10–30°, catalog Hipparcos. Database LOST dựng từ Yale BSC đi kèm mã LOST, cặp sao 0,05–20°, kính khai 50 mm và pixel 2,74 µm.",
        "",
    ]
    for solver in ("tetra3", "lost"):
        group = [row for row in rows if row["solver"] == solver]
        ok = [row for row in group if row["success"] and row["sep_center_arcsec"] is not None]
        center = _stats([row["sep_center_arcsec"] for row in ok])
        bore = _stats([row["sep_boresight_arcsec"] for row in ok])
        lines.append(f"## {solver}")
        lines.append("")
        lines.append(f"- Khung đã chạy: {len(group)}")
        lines.append(f"- Giải được: {len(ok)}")
        if center["n"]:
            lines.append(
                f"- Lệch tâm ảnh của solver: trung vị {center['median']:.3f}″, "
                f"p95 {center['p95']:.3f}″, lớn nhất {center['max']:.3f}″"
            )
            lines.append(
                f"- Lệch hướng nhìn +Z của bộ benchmark: trung vị {bore['median']:.3f}″, "
                f"p95 {bore['p95']:.3f}″, lớn nhất {bore['max']:.3f}″"
            )
        lines.append("")
        lines.append("| Nhiễu | N | Giải được | Trung vị tâm ảnh ″ | p95 ″ | Lớn nhất ″ |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        noises = sorted({str(row.get("noise")) for row in group})
        for noise in noises:
            subset = [row for row in group if str(row.get("noise")) == noise]
            good = [row["sep_center_arcsec"] for row in subset if row["success"] and row["sep_center_arcsec"] is not None]
            stat = _stats(good)
            med = "—" if stat["median"] is None else f"{stat['median']:.3f}"
            p95 = "—" if stat["p95"] is None else f"{stat['p95']:.3f}"
            mx = "—" if stat["max"] is None else f"{stat['max']:.3f}"
            lines.append(f"| {noise} | {len(subset)} | {stat['n']} | {med} | {p95} | {mx} |")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare tetra3 and LOST on the benchmark set")
    parser.add_argument("--dataset", type=Path, default=STAR / "data" / "benchmark_dataset")
    parser.add_argument("--solvers", default="tetra3,lost")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    solvers = [item.strip() for item in args.solvers.split(",") if item.strip()]
    cam = demo_camera()
    fov = float(cam.fov_deg[0])
    rows = load_rows(args.dataset)
    if args.limit > 0:
        rows = rows[: args.limit]
    sink = args.dataset / "external_compare.jsonl"
    t3 = None
    if "tetra3" in solvers:
        from tetra3 import Tetra3
        t3 = Tetra3()
    q_cache: dict[str, np.ndarray] = {}
    for solver in solvers:
        done = load_done(sink, solver)
        pending = [row for row in rows if row["file"] not in done]
        print(f"[*] {solver}: {len(pending)} frames, {len(done)} already stored", flush=True)
        handle = sink.open("a", encoding="utf-8")
        t0 = time.perf_counter()
        try:
            for i, row in enumerate(pending, start=1):
                tif = args.dataset / row["file"]
                if row["file"] not in q_cache:
                    meta = json.loads(tif.with_suffix(".json").read_text(encoding="utf-8"))
                    q_cache[row["file"]] = np.asarray(meta["q_gt"], dtype=np.float64)
                try:
                    if solver == "tetra3":
                        sol = solve_tetra(t3, Image.open(tif), fov)
                    else:
                        sol = solve_lost(tif)
                except Exception as exc:
                    sol = {
                        "ok": False, "ra": None, "dec": None, "roll": None,
                        "fov": None, "matches": None, "rmse_arcsec": None,
                        "elapsed_ms": None, "error": f"{type(exc).__name__}: {exc}",
                    }
                scored = score_solution(sol, q_cache[row["file"]], cam, solver, row)
                handle.write(json.dumps(scored) + "\n")
                handle.flush()
                if i == 1 or i % 25 == 0 or i == len(pending):
                    sep = scored["sep_center_arcsec"]
                    sep_txt = "fail" if sep is None else f"{sep:.2f}"
                    rate = (time.perf_counter() - t0) / i
                    left = (len(pending) - i) * rate / 60.0
                    print(f"  {i}/{len(pending)} {row['file']} {sep_txt} arcsec  eta {left:.1f} min", flush=True)
        finally:
            handle.close()
    stored = []
    for line in sink.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                stored.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    wanted = {row["file"] for row in rows}
    stored = [row for row in stored if row["file"] in wanted and row["solver"] in solvers]
    report = args.dataset / "external_compare_report.md"
    write_report(report, stored)
    print(f"[*] report {report}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
