#!/usr/bin/env python3
"""Score stored benchmark frames against the quaternion written beside each TIFF."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
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
from src.quaternion import angular_error_arcsec


def mag_bin(mag) -> str:
    if mag is None or mag == "":
        return "lis"
    m = float(mag)
    if m < 1.0:
        return "[-inf,1)"
    if m < 2.0:
        return "[1,2)"
    if m < 3.0:
        return "[2,3)"
    if m < 4.0:
        return "[3,4)"
    if m < 5.0:
        return "[4,5)"
    if m <= 6.0:
        return "[5,6]"
    return "other"


def load_rows(dataset: Path) -> list[dict]:
    path = dataset / "manifest.jsonl"
    if not path.is_file():
        raise SystemExit(f"missing {path}")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def select_smoke(rows: list[dict]) -> list[dict]:
    """Brightest and faintest center frames, plus one frame of each factor level."""
    picked: list[dict] = []
    seen: set[str] = set()

    def take(row: dict | None) -> None:
        if row is None:
            return
        key = str(row["file"])
        if key in seen:
            return
        seen.add(key)
        picked.append(row)

    center = [row for row in rows if row.get("split") == "center"]
    ranked = []
    for row in center:
        try:
            ranked.append((float(row["mag"]), row))
        except (TypeError, ValueError, KeyError):
            continue
    if ranked:
        ranked.sort(key=lambda item: item[0])
        take(ranked[0][1])
        take(ranked[-1][1])

    factorial = [row for row in rows if row.get("split") == "factorial"]
    for key in ("noise", "roll_deg", "slew_deg_s"):
        seen_level = set()
        for row in factorial:
            level = row.get(key)
            token = json.dumps(level)
            if token in seen_level:
                continue
            seen_level.add(token)
            take(row)
    return picked


def _pct(part: int, whole: int) -> float | None:
    if whole <= 0:
        return None
    return 100.0 * part / whole


def _group_stats(items: list[dict]) -> dict:
    errors = np.asarray(
        [float(item["attitude_error_arcsec"]) for item in items if item.get("attitude_error_arcsec") is not None],
        dtype=np.float64,
    )
    times = np.asarray(
        [
            float(item["timing_ms"]["total_pipeline_ms"])
            for item in items
            if isinstance(item.get("timing_ms"), dict) and "total_pipeline_ms" in item["timing_ms"]
        ],
        dtype=np.float64,
    )
    n = len(items)
    n_success = sum(1 for item in items if item.get("success"))
    n_within = sum(1 for item in items if item.get("within_limit"))
    stats: dict = {
        "n": n,
        "n_success": n_success,
        "n_fail": n - n_success,
        "n_within_limit": n_within,
        "success_pct": _pct(n_success, n),
        "within_limit_pct": _pct(n_within, n),
        "median_error_arcsec": None,
        "p95_error_arcsec": None,
        "p99_error_arcsec": None,
        "max_error_arcsec": None,
        "mean_error_arcsec": None,
        "median_total_ms": None,
    }
    if errors.size:
        stats["median_error_arcsec"] = float(np.median(errors))
        stats["p95_error_arcsec"] = float(np.percentile(errors, 95))
        stats["p99_error_arcsec"] = float(np.percentile(errors, 99))
        stats["max_error_arcsec"] = float(np.max(errors))
        stats["mean_error_arcsec"] = float(np.mean(errors))
    if times.size:
        stats["median_total_ms"] = float(np.median(times))
    return stats


def summarize(results: list[dict]) -> dict:
    summary = {"n": len(results), "overall": _group_stats(results), "groups": {}, "failures": []}
    for key in ("split", "noise", "roll_deg", "slew_deg_s", "mag_bin"):
        buckets: dict[str, list[dict]] = defaultdict(list)
        for item in results:
            buckets[str(item.get(key))].append(item)
        summary["groups"][key] = {name: _group_stats(group) for name, group in sorted(buckets.items())}
    for item in results:
        if not item.get("success") or not item.get("within_limit"):
            summary["failures"].append(
                {
                    "file": item.get("file"),
                    "split": item.get("split"),
                    "noise": item.get("noise"),
                    "roll_deg": item.get("roll_deg"),
                    "slew_deg_s": item.get("slew_deg_s"),
                    "mag": item.get("mag"),
                    "success": item.get("success"),
                    "attitude_error_arcsec": item.get("attitude_error_arcsec"),
                    "error": item.get("error"),
                }
            )
    return summary


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}"


def write_report(path: Path, summary: dict) -> None:
    overall = summary["overall"]
    lines = [
        "# Kết quả benchmark star tracker",
        "",
        "Góc trong các bảng là góc quay nhỏ nhất đưa quaternion đúng sang quaternion giải được, đủ ba trục của camera. Đây không phải độ lệch xích kinh hay xích vĩ của hướng nhìn.",
        "",
        "Hướng nhìn là trục +Z. Xích kinh và xích vĩ trên giao diện chỉ đo trục đó. Phần còn lại của góc ba trục là xoay quanh trục nhìn: tâm bầu trời gần như đứng yên, thân camera vẫn xoay. Ngưỡng 10″ áp vào góc ba trục, không áp riêng vào xích kinh hay xích vĩ.",
        "",
        f"- Số khung: {summary['n']}",
        f"- Giải được: {overall['n_success']} / {overall['n']} ({_fmt(overall['success_pct'], 2)}%)",
        f"- Dưới ngưỡng 10″ trên góc ba trục: {overall['n_within_limit']} / {overall['n']} ({_fmt(overall['within_limit_pct'], 2)}%)",
        f"- Góc ba trục (″), chỉ khung giải được: trung vị {_fmt(overall['median_error_arcsec'])}, "
        f"p95 {_fmt(overall['p95_error_arcsec'])}, p99 {_fmt(overall['p99_error_arcsec'])}, "
        f"lớn nhất {_fmt(overall['max_error_arcsec'])}",
        f"- Thời gian pipeline, trung vị: {_fmt(overall['median_total_ms'], 1)} ms",
        "",
    ]
    titles = {
        "split": "Theo tập",
        "noise": "Theo nhiễu",
        "roll_deg": "Theo roll",
        "slew_deg_s": "Theo vận tốc góc",
        "mag_bin": "Theo cấp sao ở tâm",
    }
    for key, title in titles.items():
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Nhóm | N | Giải được | Dưới 10″ | Trung vị góc ba trục ″ | p95 ″ | Lớn nhất ″ |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for name, stats in summary["groups"][key].items():
            lines.append(
                f"| {name} | {stats['n']} | {stats['n_success']} | {stats['n_within_limit']} | "
                f"{_fmt(stats['median_error_arcsec'])} | {_fmt(stats['p95_error_arcsec'])} | "
                f"{_fmt(stats['max_error_arcsec'])} |"
            )
        lines.append("")
    fails = summary["failures"]
    lines.append(f"## Khung không giải được hoặc vượt ngưỡng ({len(fails)})")
    lines.append("")
    if not fails:
        lines.append("Không có.")
    else:
        lines.append("| File | Tập | Nhiễu | Roll | Vệt °/s | Cấp | Góc ba trục ″ | Lỗi |")
        lines.append("|---|---|---|---:|---:|---:|---:|---|")
        for item in fails:
            lines.append(
                f"| {item['file']} | {item['split']} | {item['noise']} | {item['roll_deg']} | "
                f"{item['slew_deg_s']} | {item['mag']} | {_fmt(item['attitude_error_arcsec'])} | {item['error'] or ''} |"
            )
    lines.append("")
    lines.append("Cột góc là `angular_error_arcsec`: 2 arccos(|q_est · q_gt|), đổi sang giây cung. Ngưỡng 10″ là `attitude_error_limit_arcsec` của cấu hình FULL.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def score_one(pipe: StarTrackerPipeline, dataset: Path, row: dict, limit: float) -> dict:
    path = dataset / str(row["file"])
    try:
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise RuntimeError(f"cannot read {path}")
        if img.ndim == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        result = pipe.process_frame(img)
        err = None
        if result.success and result.q is not None:
            err = float(angular_error_arcsec(result.q, np.asarray(row["q_gt"], dtype=np.float64)))
        return {
            "file": row["file"],
            "split": row.get("split"),
            "noise": row.get("noise"),
            "roll_deg": row.get("roll_deg"),
            "slew_deg_s": row.get("slew_deg_s"),
            "mag": row.get("mag"),
            "mag_bin": mag_bin(row.get("mag")),
            "success": bool(result.success),
            "attitude_error_arcsec": err,
            "within_limit": bool(err is not None and err < limit),
            "limit_arcsec": limit,
            "n_matched": int(result.ident.obs_idx.size) if result.ident is not None else 0,
            "timing_ms": result.timing_ms,
            "error": result.error,
        }
    except Exception as exc:
        return {
            "file": row["file"],
            "split": row.get("split"),
            "noise": row.get("noise"),
            "roll_deg": row.get("roll_deg"),
            "slew_deg_s": row.get("slew_deg_s"),
            "mag": row.get("mag"),
            "mag_bin": mag_bin(row.get("mag")),
            "success": False,
            "attitude_error_arcsec": None,
            "within_limit": False,
            "limit_arcsec": limit,
            "n_matched": 0,
            "timing_ms": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def score_rows(dataset: Path, rows: list[dict], sink: Path | None = None, done: set[str] | None = None) -> None:
    if not rows:
        return
    mode = str(rows[0].get("mode") or "full")
    cam = demo_camera()
    if mode == "fast":
        cam = cam.downscaled(4)
    cat = CatalogManager.load_npz(ROOT / "data" / "catalogs" / "bsc5_v6.0.npz")
    kv = build_or_load(cat, ROOT / "data" / "catalogs")
    cfg = load_pipeline_cfg(mode if mode in {"fast", "full"} else "full", ROOT)
    pipe = StarTrackerPipeline(cam, cat, kv, cfg)
    limit = float(cfg.attitude_error_limit_arcsec)
    pending = [row for row in rows if str(row["file"]) not in (done or set())]
    handle = sink.open("a", encoding="utf-8") if sink is not None else None
    t0 = time.perf_counter()
    try:
        for i, row in enumerate(pending, start=1):
            scored = score_one(pipe, dataset, row, limit)
            if handle is not None:
                handle.write(json.dumps(scored) + "\n")
                handle.flush()
            if i == 1 or i % 25 == 0 or i == len(pending):
                err = scored["attitude_error_arcsec"]
                err_txt = "none" if err is None else f"{err:.3f}"
                rate = (time.perf_counter() - t0) / i
                left = (len(pending) - i) * rate / 60.0
                print(
                    f"  {i}/{len(pending)} {row['file']}  err={err_txt} arcsec  eta {left:.1f} min",
                    flush=True,
                )
    finally:
        if handle is not None:
            handle.close()


def load_scored(path: Path) -> list[dict]:
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


def main() -> int:
    p = argparse.ArgumentParser(description="Score the stored star-tracker benchmark")
    p.add_argument("--dataset", type=Path, default=ROOT / "data" / "benchmark_dataset")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--split", choices=["center", "factorial", "all"], default="all")
    args = p.parse_args()
    rows = load_rows(args.dataset)
    if args.split != "all":
        rows = [row for row in rows if row.get("split") == args.split]
    if args.smoke:
        rows = select_smoke(rows)
    elif int(args.limit) > 0:
        rows = rows[: int(args.limit)]
    stem = "smoke_results" if args.smoke else "results"
    sink = args.dataset / f"{stem}.jsonl"
    already = [] if args.smoke else load_scored(sink)
    done = {str(item["file"]) for item in already}
    pending = [row for row in rows if str(row["file"]) not in done]
    print(f"[*] scoring {len(pending)} frames, {len(done)} already stored", flush=True)
    if args.smoke and sink.exists():
        sink.unlink()
        done = set()
        pending = rows
    score_rows(args.dataset, pending, sink=sink, done=set())
    results = load_scored(sink)
    wanted = {str(row["file"]) for row in rows}
    results = [item for item in results if str(item.get("file")) in wanted]
    summary = summarize(results)
    (args.dataset / f"{stem}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = args.dataset / f"{stem}_report.md"
    write_report(report, summary)
    print(json.dumps(summary["overall"], indent=2), flush=True)
    print(f"[*] report {report}", flush=True)
    return 0 if summary["n"] == len(rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
