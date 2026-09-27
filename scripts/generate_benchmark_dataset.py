#!/usr/bin/env python3
"""Synthetic sky for the demo camera.

Two splits, one camera mode for the whole tree:

- center: each BSC5+filt star once on the boresight, no slew, nominal noise
- factorial: 24 fixed pointings x 4 rolls x 2 slew rates x 4 noise presets

Images are uint16 TIFF. Sidecars hold the mid-exposure quaternion. The solver
must not read those files. Radiometry numbers stay the project assumptions.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_sim_dataset import load_radiometry, star_rows  # noqa: E402
from src.camera import CameraModel, demo_camera
from src.catalog import CatalogManager, StarCatalog
from src.quaternion import (
    boresight_ra_dec_deg,
    format_dec_dms,
    format_ra_hms,
    looking_at,
    multiply,
    normalize,
    random_quaternion,
)
from src.simulator import Radiometry, SkySimulator
from src.starnames import label_hr, lookup_hr

EXPECTED_CATALOG = 5023
FRAME_SEED0 = 10_000_000
ROLLS_DEG = (0, 90, 180, 270)
SLEW_DEG_S = (0.0, 0.06)
NOISE_NAMES = ("clean", "nominal", "false", "harsh")
T_EXP_S = 0.15
DISK_MARGIN_BYTES = 15 * (1024**3)
MAG_EDGES = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)


def roll_quaternion(q_base: np.ndarray, roll_deg: float) -> np.ndarray:
    """Roll the camera about its +Z axis. The boresight star stays at the principal point.

    A(dq ⊗ q) = A(dq) @ A(q), so camera coordinates transform as b' = R_z @ b.
    The right-multiply used by propagate() is the other order and moves the boresight.
    """
    half = float(np.radians(roll_deg)) * 0.5
    dq = np.array([np.cos(half), 0.0, 0.0, np.sin(half)], dtype=np.float64)
    return normalize(multiply(dq, q_base))


def slew_tag(slew_deg_s: float) -> str:
    if abs(float(slew_deg_s)) < 1e-12:
        return "00"
    if abs(float(slew_deg_s) - 0.06) < 1e-9:
        return "06"
    raise ValueError(f"unsupported slew {slew_deg_s}")


def false_star_count(noise: str) -> int:
    return 2 if noise in {"false", "harsh"} else 0


def add_noise_flag(noise: str) -> bool:
    return noise != "clean"


def radiometry_for(base: Radiometry, noise: str) -> Radiometry:
    if noise == "harsh":
        return replace(base, hot_pixel_frac=1.0e-4, cosmic_rate_per_frame=20.0)
    return base


def _ra_distance(ra: np.ndarray, target: float) -> np.ndarray:
    return np.abs((ra - target + np.pi) % (2.0 * np.pi) - np.pi)


def _bin_masks(mags: np.ndarray) -> list[np.ndarray]:
    masks = []
    low = -np.inf
    for edge in MAG_EDGES:
        if edge >= 6.0:
            masks.append((mags >= low) & (mags <= edge))
        else:
            masks.append((mags >= low) & (mags < edge))
        low = edge
    return masks


def stratified_star_indices(cat: StarCatalog) -> list[int]:
    """Two stars per magnitude bin: the brightest, and the one nearest RA+180°."""
    mags = np.asarray(cat.mags, dtype=np.float64)
    ra = np.asarray(cat.ra_rad, dtype=np.float64)
    picked: list[int] = []
    for mask in _bin_masks(mags):
        idx = np.flatnonzero(mask)
        if idx.size < 2:
            raise RuntimeError(f"magnitude bin has {idx.size} stars; need 2")
        bright = int(idx[np.argmin(mags[idx])])
        target = float((ra[bright] + np.pi) % (2.0 * np.pi))
        dist = _ra_distance(ra[idx], target)
        dist[idx == bright] = np.inf
        opposite = int(idx[int(np.argmin(dist))])
        picked.extend((bright, opposite))
    return picked


def omega_hat(scene_id: int) -> np.ndarray:
    rng = np.random.default_rng(1000 + int(scene_id))
    v = rng.normal(size=3)
    return v / np.linalg.norm(v)


def build_scenes(cat: StarCatalog, cam_full: CameraModel) -> list[dict]:
    """12 magnitude-stratified boresights, then 12 lost-in-space attitudes."""
    scenes: list[dict] = []
    for catalog_idx in stratified_star_indices(cat):
        scene_id = len(scenes)
        q = looking_at(cat.vectors[catalog_idx])
        scenes.append(
            {
                "scene_id": scene_id,
                "kind": "star",
                "catalog_idx": int(catalog_idx),
                "hr": int(cat.ids[catalog_idx]),
                "mag": float(cat.mags[catalog_idx]),
                "q_base": q.tolist(),
                "omega_hat": omega_hat(scene_id).tolist(),
            }
        )
    rng = np.random.default_rng(1)
    draws = 0
    while sum(1 for s in scenes if s["kind"] == "lis") < 12:
        draws += 1
        if draws > 10000:
            raise RuntimeError("could not draw 12 lost-in-space attitudes with >= 4 stars")
        q = random_quaternion(rng)
        _uv, in_fov = cam_full.project((q_to_cam(q, cat)))
        if int(np.count_nonzero(in_fov)) < 4:
            continue
        scene_id = len(scenes)
        scenes.append(
            {
                "scene_id": scene_id,
                "kind": "lis",
                "catalog_idx": None,
                "hr": None,
                "mag": None,
                "q_base": q.tolist(),
                "omega_hat": omega_hat(scene_id).tolist(),
            }
        )
    return scenes


def q_to_cam(q: np.ndarray, cat: StarCatalog) -> np.ndarray:
    from src.quaternion import to_dcm

    return (to_dcm(q) @ cat.vectors.T).T


def build_jobs(cat: StarCatalog, cam_full: CameraModel | None = None) -> list[dict]:
    if int(cat.num_stars) != EXPECTED_CATALOG:
        raise RuntimeError(
            f"catalog has {cat.num_stars} stars; benchmark requires {EXPECTED_CATALOG}"
        )
    if str(cat.source) != "BSC5+filt":
        raise RuntimeError(f"catalog source is {cat.source!r}; benchmark requires BSC5+filt")
    cam_full = cam_full or demo_camera()
    jobs: list[dict] = []
    for catalog_idx in range(int(cat.num_stars)):
        hr = int(cat.ids[catalog_idx])
        q = looking_at(cat.vectors[catalog_idx])
        jobs.append(
            {
                "split": "center",
                "kind": "star",
                "scene_id": None,
                "catalog_idx": int(catalog_idx),
                "hr": hr,
                "mag": float(cat.mags[catalog_idx]),
                "roll_deg": 0,
                "slew_deg_s": 0.0,
                "noise": "nominal",
                "q_base": q.tolist(),
                "omega_hat": [0.0, 0.0, 0.0],
                "stem": f"c{catalog_idx:04d}_hr{hr}",
            }
        )
    for scene in build_scenes(cat, cam_full):
        hat = scene["omega_hat"]
        for roll in ROLLS_DEG:
            for slew in SLEW_DEG_S:
                for noise in NOISE_NAMES:
                    jobs.append(
                        {
                            "split": "factorial",
                            "kind": scene["kind"],
                            "scene_id": scene["scene_id"],
                            "catalog_idx": scene["catalog_idx"],
                            "hr": scene["hr"],
                            "mag": scene["mag"],
                            "roll_deg": int(roll),
                            "slew_deg_s": float(slew),
                            "noise": noise,
                            "q_base": scene["q_base"],
                            "omega_hat": hat,
                            "stem": (
                                f"s{scene['scene_id']:02d}_r{int(roll):03d}"
                                f"_w{slew_tag(slew)}_{noise}"
                            ),
                        }
                    )
    for ordinal, job in enumerate(jobs):
        job["ordinal"] = ordinal
    return jobs


def job_paths(out: Path, job: dict) -> tuple[Path, Path]:
    folder = out / job["split"]
    return folder / f"{job['stem']}.tif", folder / f"{job['stem']}.json"


def frame_done(out: Path, job: dict) -> bool:
    tif, sidecar = job_paths(out, job)
    if not tif.is_file() or not sidecar.is_file():
        return False
    try:
        json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return True


def attitude_of(job: dict) -> tuple[np.ndarray, np.ndarray]:
    q = roll_quaternion(np.asarray(job["q_base"], dtype=np.float64), float(job["roll_deg"]))
    hat = np.asarray(job["omega_hat"], dtype=np.float64)
    omega = hat * float(job["slew_deg_s"])
    return q, omega


def render_job(
    sim: SkySimulator,
    cam: CameraModel,
    cat: StarCatalog,
    job: dict,
) -> tuple[np.ndarray, dict]:
    q, omega = attitude_of(job)
    sim.rng = np.random.default_rng(FRAME_SEED0 + int(job["ordinal"]))
    noise = str(job["noise"])
    n_false = false_star_count(noise)
    img, truth = sim.render(
        q,
        omega_deg_s=omega,
        t_exp_s=T_EXP_S,
        add_noise=add_noise_flag(noise),
        false_stars=n_false,
    )
    if job["kind"] == "star":
        target = int(job["catalog_idx"])
        hit = np.flatnonzero(truth.cat_idx == target)
        if hit.size != 1:
            raise RuntimeError(f"{job['stem']}: center star {target} not in the frame")
        uv = truth.uv_mid[int(hit[0])]
        if max(abs(float(uv[0]) - cam.cx), abs(float(uv[1]) - cam.cy)) > 0.05:
            raise RuntimeError(f"{job['stem']}: center star at {uv.tolist()}, principal point {(cam.cx, cam.cy)}")
    ra, dec = boresight_ra_dec_deg(q)
    rel = f"{job['split']}/{job['stem']}.tif"
    center = None
    if job["catalog_idx"] is not None:
        idx = int(job["catalog_idx"])
        hr = int(cat.ids[idx])
        rec = lookup_hr(hr) or {}
        center = {
            "catalog_idx": idx,
            "hr": hr,
            "iau_name": rec.get("name"),
            "label": label_hr(hr, compact=False),
            "mag": float(cat.mags[idx]),
        }
    meta = {
        "split": job["split"],
        "kind": job["kind"],
        "scene_id": job["scene_id"],
        "ordinal": int(job["ordinal"]),
        "mode": "full" if cam.width == camera_for_mode("full").width else "fast",
        "center_star": center,
        "roll_deg": int(job["roll_deg"]),
        "slew_deg_s": float(job["slew_deg_s"]),
        "q_gt": q.tolist(),
        "omega_deg_s": omega.tolist(),
        "t_exp_s": T_EXP_S,
        "noise": {
            "name": noise,
            "add_noise": add_noise_flag(noise),
            "false_stars": n_false,
            "read_noise_e": float(sim.radiometry.read_noise_e),
            "dark_e_per_s": float(sim.radiometry.dark_e_per_s),
            "hot_pixel_frac": float(sim.radiometry.hot_pixel_frac) if add_noise_flag(noise) else 0.0,
            "cosmic_rate_per_frame": float(sim.radiometry.cosmic_rate_per_frame) if add_noise_flag(noise) else 0.0,
            "e_per_s_v0": float(sim.radiometry.e_per_s_v0),
            "bias_dn": float(sim.radiometry.bias_dn),
            "assumption": True,
        },
        "false_stars": n_false,
        "false_uv": np.asarray(truth.false_uv, dtype=np.float64).reshape(-1, 2).tolist(),
        "boresight": {
            "ra_deg": ra,
            "dec_deg": dec,
            "ra_hms": format_ra_hms(ra),
            "dec_dms": format_dec_dms(dec),
            "frame": "J2000 camera +Z",
        },
        "camera": {
            "width": cam.width,
            "height": cam.height,
            "pixel_um": cam.pixel_um,
            "focal_mm": cam.focal_mm,
        },
        "stars_in_fov": star_rows(cat, truth),
        "image": rel,
    }
    return img, meta


def write_frame(out: Path, job: dict, img: np.ndarray, meta: dict) -> None:
    tif, sidecar = job_paths(out, job)
    tif.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(tif), img, [int(cv2.IMWRITE_TIFF_COMPRESSION), 8])
    if not ok:
        raise RuntimeError(f"cv2.imwrite failed: {tif}")
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def load_catalog() -> StarCatalog:
    path = ROOT / "data" / "catalogs" / "bsc5_v6.0.npz"
    if not path.exists():
        raise SystemExit(f"missing catalog {path}")
    return CatalogManager.load_npz(path)


def camera_for_mode(mode: str) -> CameraModel:
    cam = demo_camera()
    if mode == "fast":
        return cam.downscaled(4)
    if mode == "full":
        return cam
    raise ValueError(mode)


def existing_wh(out: Path) -> tuple[int, int] | None:
    for split in ("center", "factorial"):
        folder = out / split
        if not folder.is_dir():
            continue
        for sidecar in folder.glob("*.json"):
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            cam = meta.get("camera") or {}
            if "width" in cam and "height" in cam:
                return int(cam["width"]), int(cam["height"])
    return None


def make_simulator(cam: CameraModel, cat: StarCatalog, rad: Radiometry, seed: int, hot_path: Path) -> SkySimulator:
    sim = SkySimulator(cam, cat, radiometry=rad, seed=seed)
    if hot_path.is_file():
        hot = np.load(hot_path)
        if hot.size and (int(hot[:, 0].max()) >= cam.height or int(hot[:, 1].max()) >= cam.width):
            raise SystemExit(f"{hot_path} does not match {cam.width}x{cam.height}")
        sim.hot_yx = hot
    else:
        hot_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(hot_path, sim.hot_yx)
    return sim


def probe_bytes(cam: CameraModel, cat: StarCatalog, base: Radiometry, out: Path) -> tuple[int, float]:
    """Return (bytes of the larger sample, seconds per noisy frame)."""
    probe = out / "_probe"
    if probe.exists():
        shutil.rmtree(probe)
    probe.mkdir(parents=True)
    sim = SkySimulator(cam, cat, radiometry=base, seed=0)
    q = looking_at(cat.vectors[int(np.argmin(cat.mags))])
    sizes = []
    noisy_s = None
    for name, add_noise in (("clean", False), ("nominal", True)):
        sim.rng = np.random.default_rng(0)
        t0 = time.perf_counter()
        img, _truth = sim.render(q, omega_deg_s=(0.0, 0.0, 0.0), t_exp_s=T_EXP_S, add_noise=add_noise, false_stars=0)
        dt = time.perf_counter() - t0
        path = probe / f"{name}.tif"
        ok = cv2.imwrite(str(path), img, [int(cv2.IMWRITE_TIFF_COMPRESSION), 8])
        if not ok:
            raise RuntimeError(f"probe write failed: {path}")
        sizes.append(path.stat().st_size)
        if add_noise:
            noisy_s = dt
        print(f"  probe {name}: {path.stat().st_size / 1e6:.2f} MB  {dt:.2f} s", flush=True)
    shutil.rmtree(probe)
    return max(sizes), float(noisy_s if noisy_s is not None else 0.0)


def choose_mode(requested: str, out: Path, n_new: int, cat: StarCatalog, base: Radiometry, no_fallback: bool) -> tuple[str, dict]:
    found = existing_wh(out)
    if found is not None:
        full_wh = (camera_for_mode("full").width, camera_for_mode("full").height)
        fast_wh = (camera_for_mode("fast").width, camera_for_mode("fast").height)
        mode = "full" if found == full_wh else "fast" if found == fast_wh else ""
        if not mode:
            raise SystemExit(f"existing frames are {found[0]}x{found[1]}; expected FULL or FAST")
        if mode != requested:
            raise SystemExit(
                f"folder already has {mode} frames; requested {requested}. "
                "Keep one camera mode for the whole dataset."
            )
        return mode, {"probed": False, "existing": True}

    def fits(mode: str) -> tuple[bool, dict]:
        cam = camera_for_mode(mode)
        print(f"[*] probe {mode}", flush=True)
        nbytes, seconds = probe_bytes(cam, cat, base, out)
        need = nbytes * int(n_new) + DISK_MARGIN_BYTES
        free = shutil.disk_usage(out).free
        info = {
            "mode": mode,
            "bytes_per_frame": nbytes,
            "seconds_per_frame": seconds,
            "n_new": int(n_new),
            "need_bytes": int(need),
            "free_bytes": int(free),
        }
        print(
            f"  {mode}: {nbytes / 1e6:.2f} MB/frame x {n_new} + 15 GB"
            f" -> {need / 1e9:.1f} GB, free {free / 1e9:.1f} GB",
            flush=True,
        )
        return free >= need, info

    ok, info = fits(requested)
    if ok:
        return requested, info
    if requested == "full" and not no_fallback:
        print("[*] FULL does not fit; switching the whole set to FAST", flush=True)
        ok_fast, info_fast = fits("fast")
        info_fast["fallback_from"] = "full"
        if ok_fast:
            return "fast", info_fast
        info = info_fast
    raise SystemExit(
        "Not enough free disk for the remaining frames "
        f"(need {info['need_bytes'] / 1e9:.1f} GB, free {info['free_bytes'] / 1e9:.1f} GB)."
    )


def index_row(meta: dict) -> dict:
    q = meta["q_gt"]
    omega = meta["omega_deg_s"]
    center = meta.get("center_star") or {}
    bore = meta["boresight"]
    return {
        "split": meta["split"],
        "file": meta["image"],
        "catalog_idx": "" if center.get("catalog_idx") is None else center.get("catalog_idx", ""),
        "hr": "" if center.get("hr") is None else center.get("hr", ""),
        "mag": "" if center.get("mag") is None else center.get("mag", ""),
        "ra_deg": bore["ra_deg"],
        "dec_deg": bore["dec_deg"],
        "roll_deg": meta["roll_deg"],
        "omega_x": omega[0],
        "omega_y": omega[1],
        "omega_z": omega[2],
        "noise": meta["noise"]["name"],
        "false_stars": meta["false_stars"],
        "n_stars": len(meta["stars_in_fov"]),
        "q0": q[0],
        "q1": q[1],
        "q2": q[2],
        "q3": q[3],
    }


def jsonl_row(meta: dict) -> dict:
    row = index_row(meta)
    row.update(
        {
            "sidecar": meta["image"].replace(".tif", ".json"),
            "kind": meta["kind"],
            "scene_id": meta["scene_id"],
            "slew_deg_s": meta["slew_deg_s"],
            "mode": meta["mode"],
            "q_gt": meta["q_gt"],
            "ordinal": meta["ordinal"],
        }
    )
    return row


def write_manifests(out: Path, jobs: list[dict], cat: StarCatalog, note: dict) -> None:
    rows = []
    missing = []
    for job in jobs:
        _tif, sidecar = job_paths(out, job)
        if not sidecar.is_file():
            missing.append(job["stem"])
            continue
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        rows.append(jsonl_row(meta))
    (out / "manifest.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    fieldnames = [
        "split", "file", "catalog_idx", "hr", "mag", "ra_deg", "dec_deg",
        "roll_deg", "omega_x", "omega_y", "omega_z", "noise", "false_stars",
        "n_stars", "q0", "q1", "q2", "q3",
    ]
    with (out / "index.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    summary = {
        "catalog": cat.source,
        "n_catalog": cat.num_stars,
        "epoch_year": cat.epoch_year,
        "n_frames": len(rows),
        "n_missing": len(missing),
        "n_center": sum(1 for row in rows if row["split"] == "center"),
        "n_factorial": sum(1 for row in rows if row["split"] == "factorial"),
        "rolls_deg": list(ROLLS_DEG),
        "slew_deg_s": list(SLEW_DEG_S),
        "noise": list(NOISE_NAMES),
        "probe": note,
    }
    (out / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if missing:
        raise SystemExit(f"missing {len(missing)} frames, first {missing[:5]}")


def write_readme(out: Path, mode: str, cat: StarCatalog) -> None:
    text = f"""# Bộ benchmark star tracker

Ảnh giả lập camera demo (APS-C 24 MP, ống 50 mm), catalog `{cat.source}` {cat.num_stars} sao, epoch {cat.epoch_year}. Mode đã ghi: **{mode}**.

Quaternion trong JSON là tư thế giữa thời gian phơi. Bộ giải không đọc JSON.

## Tập

- `center/`: mỗi sao catalog một lần trên trục +Z. Roll theo bắc thiên cầu (`looking_at`). Vận tốc góc 0. Nhiễu `nominal`. Phơi {T_EXP_S} s.
- `factorial/`: 24 hướng (12 sao phân theo cấp, 12 hướng lost-in-space seed 1) × roll 0/90/180/270° × vận tốc 0 và 0,06 °/s × nhiễu `clean`, `nominal`, `false`, `harsh`.

Roll quanh +Z của camera, sao ở tâm đứng yên: q = normalize([cos(theta/2), 0, 0, sin(theta/2)] ⊗ q_base).

| Nhiễu | Poisson + đọc | Hot pixel | Tia vũ trụ / khung | Sao giả |
|---|---|---|---|---|
| clean | tắt | 0 | 0 | 0 |
| nominal | bật | 1e-5 | 2 | 0 |
| false | bật | 1e-5 | 2 | 2 |
| harsh | bật | 1e-4 | 20 | 2 |

`clean` vẫn cộng dòng tối và bias. Radiometry là giả định trong `config/camera_specs.json`, không phải số đo của một máy ảnh.

## Sinh lại và chấm

```text
cd star_tracker
python scripts/generate_benchmark_dataset.py --mode {mode} --resume
python scripts/benchmark_stored_dataset.py --smoke
```

Chấm toàn bộ: `python scripts/benchmark_stored_dataset.py`.
"""
    (out / "README.md").write_text(text, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Generate the star-tracker benchmark image set")
    p.add_argument("--mode", choices=["full", "fast"], default="full")
    p.add_argument("--out", type=Path, default=ROOT / "data" / "benchmark_dataset")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="Render only the first N jobs of the slice")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--count", type=int, default=0)
    p.add_argument("--skip-probe", action="store_true")
    p.add_argument("--no-fallback", action="store_true")
    args = p.parse_args()

    cat = load_catalog()
    cam_full = demo_camera()
    jobs = build_jobs(cat, cam_full)
    start = max(0, int(args.start))
    count = int(args.count) if int(args.count) > 0 else len(jobs) - start
    todo = jobs[start : start + count]
    if int(args.limit) > 0:
        todo = todo[: int(args.limit)]
    args.out.mkdir(parents=True, exist_ok=True)

    base = load_radiometry()
    n_new = sum(1 for job in todo if not frame_done(args.out, job))
    note: dict = {"requested_mode": args.mode}
    if args.skip_probe or int(args.limit) > 0:
        mode = args.mode
        found = existing_wh(args.out)
        if found is not None:
            full_wh = (cam_full.width, cam_full.height)
            fast_wh = (cam_full.downscaled(4).width, cam_full.downscaled(4).height)
            locked = "full" if found == full_wh else "fast" if found == fast_wh else ""
            if not locked:
                raise SystemExit(f"existing frames are {found[0]}x{found[1]}; expected the demo FULL or FAST size")
            if locked != mode:
                raise SystemExit(f"existing frames are {locked}; this run asked for {mode}")
        note["probed"] = False
    else:
        mode, info = choose_mode(args.mode, args.out, n_new, cat, base, args.no_fallback)
        note.update(info)
    cam = camera_for_mode(mode)
    note["mode"] = mode

    scenes = build_scenes(cat, cam_full)
    (args.out / "scenes.json").write_text(json.dumps(scenes, indent=2), encoding="utf-8")
    sim_nominal = make_simulator(
        cam, cat, radiometry_for(base, "nominal"), 1, args.out / "hot_nominal.npy"
    )
    sim_harsh = make_simulator(
        cam, cat, radiometry_for(base, "harsh"), 2, args.out / "hot_harsh.npy"
    )
    write_readme(args.out, mode, cat)

    t0 = time.perf_counter()
    written = 0
    for n_done, job in enumerate(todo, start=1):
        if frame_done(args.out, job):
            continue
        sim = sim_harsh if job["noise"] == "harsh" else sim_nominal
        img, meta = render_job(sim, cam, cat, job)
        meta["mode"] = mode
        write_frame(args.out, job, img, meta)
        written += 1
        if written == 1 or written % 25 == 0:
            dt = time.perf_counter() - t0
            rate = dt / written
            left = n_new - written
            print(
                f"  {job['split']}/{job['stem']}  wrote {written}/{n_new}"
                f"  {rate:.2f} s/frame  eta {left * rate / 60:.1f} min",
                flush=True,
            )
        if n_done == len(todo):
            break
    print(f"[*] wrote {written} new frames in {time.perf_counter() - t0:.1f} s", flush=True)
    if start == 0 and (int(args.count) == 0) and int(args.limit) == 0:
        write_manifests(args.out, jobs, cat, note)
        print(f"[*] manifest {args.out / 'manifest.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
