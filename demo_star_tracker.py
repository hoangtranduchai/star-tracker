#!/usr/bin/env python3
"""
Standalone laptop demo: APS-C 24 MP camera and a 50 mm lens.
Deterministic pipeline: sub-pixel CoG → Mortari Pyramid → Wahba SVD/QUEST.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.demo_session import DemoEngine, RunRequest


def print_star_table(title: str, rows: list[dict]) -> None:
    print(f"  {title} ({len(rows)})")
    if not rows:
        print("    (none)")
        return
    print("    {:>8}  {:>6}  {:<28}  {:>8}  {:>8}".format("ID", "mag", "name", "u_px", "v_px"))
    for row in rows:
        mag = row.get("mag")
        mag_s = f"{mag:.2f}" if mag is not None else "n/a"
        u = row.get("u_px")
        v = row.get("v_px")
        print(
            "    {:>8}  {:>6}  {:<28}  {:>8}  {:>8}".format(
                f"{row.get('id_scheme', 'ID')} {row['id']}",
                mag_s,
                (row.get("iau_name") or "-")[:28],
                f"{u:.1f}" if u is not None else "n/a",
                f"{v:.1f}" if v is not None else "n/a",
            )
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Star tracker laptop demo")
    parser.add_argument("--mode", choices=["fast", "full"], default="fast")
    parser.add_argument("--scale", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--catalog", choices=["bsc5", "hipparcos", "synthetic"], default="bsc5")
    parser.add_argument("--max-mag", type=float, default=6.0)
    parser.add_argument("--omega", type=float, default=0.06)
    parser.add_argument("--omega-axis", choices=["random", "x", "y", "z"], default="y")
    parser.add_argument("--exposure", type=float, default=0.15)
    parser.add_argument("--glare", choices=["none", "earth", "sun", "sun_strong", "moon"], default="none")
    parser.add_argument(
        "--centroid",
        choices=["classical", "cnn"],
        default="classical",
        help="Centroid mode: classical CoG (default) or CNN MobileUNet public weights",
    )
    parser.add_argument(
        "--sky-clutter",
        choices=["none", "galactic", "galaxy", "nebula", "cloud", "typical", "milky_way", "andromeda", "both"],
        default="none",
    )
    parser.add_argument("--false-stars", type=int, default=0)
    parser.add_argument("--solver", choices=["svd", "quest"], default="svd")
    parser.add_argument("--no-show", action="store_true")
    parser.add_argument("--out", type=Path, default=BASE_DIR / "data" / "outputs")
    parser.add_argument("--lookup", action="store_true")
    parser.add_argument("--image", type=Path, default=None)
    parser.add_argument("--save-raw", action="store_true")
    args = parser.parse_args(argv)

    print("=" * 70)
    print("   STAR TRACKER - STAR TRACKER DEMO (LAPTOP RUNTIME)")
    print("=" * 70)

    engine = DemoEngine(BASE_DIR)
    specs = engine.specs
    print(f"[*] Hardware: {specs['sensor']['model']} + {specs['lens']['model']}")
    print(f"[*] Pixel {specs['sensor']['pixel_size_um']} um (not the 3.45 um lens rating)")
    if engine.radiometry.assumption:
        print("[*] Radiometry parameters are simulation assumptions, not a camera datasheet.")

    req = RunRequest(
        mode=args.mode,
        scale=args.scale,
        seed=args.seed,
        catalog=args.catalog,
        max_mag=args.max_mag,
        omega=args.omega,
        omega_axis=args.omega_axis,
        exposure=args.exposure,
        glare=args.glare,
        sky_clutter=args.sky_clutter,
        false_stars=args.false_stars,
        solver=args.solver,
        centroid_backend=args.centroid,
        image=args.image,
        out_dir=args.out,
        lookup=bool(args.lookup),
        save_png=True,
        save_raw=args.save_raw,
        show=not args.no_show,
    )

    print("[1/5] Loading catalog + K-vector...")
    print("[2/5] Rendering or loading frame...")
    out = engine.run(req)
    p = out.payload
    cam = p["camera"]
    print(f"[1/5] Catalog {p['catalog_source']}: {p['n_catalog']} stars  V<={args.max_mag}")
    print(
        f"[*] Mode={p['mode']}  {cam['width']}x{cam['height']}  "
        f"FOV={cam['fov_deg'][0]:.2f}x{cam['fov_deg'][1]:.2f} deg  IFOV={cam['ifov_arcsec']:.2f} arcsec/px"
    )
    if out.have_gt:
        print(f"      q_GT = {p['q_gt_text']}")
        gt = p["boresight_gt"]
        print(
            f"      GT boresight RA={gt['ra_deg']:.4f} deg ({gt['ra_hms']})  "
            f"Dec={gt['dec_deg']:+.4f} deg ({gt['dec_dms']})"
        )
        print(f"      stars in FOV={p['metrics']['n_truth']}")
    print(f"      image {cam['width']}x{cam['height']}  source={p['source']}")
    print("[3/5] Running deterministic pipeline...")
    print("[4/5] Results")
    print("-" * 55)
    t = p["timing_ms"]
    print(f"  Centroiding : {t.get('centroiding_ms', 0):.2f} ms")
    print(f"  Star ID     : {t.get('identification_ms', 0):.2f} ms")
    print(f"  Wahba       : {t.get('attitude_ms', 0):.2f} ms")
    print(f"  Total       : {t.get('total_pipeline_ms', 0):.2f} ms")
    print("-" * 55)
    if out.success:
        print(f"  q_est       : {p['q_est_text']}")
        be = p.get("boresight_est") or {}
        if be:
            print(
                f"  boresight   : RA {be['ra_deg']:.4f} deg ({be['ra_hms']})   "
                f"Dec {be['dec_deg']:+.4f} deg ({be['dec_dms']})"
            )
            print("               (camera +Z on J2000 sky; not satellite lat/lon; not constellation)")
        err = p["metrics"].get("attitude_error_arcsec")
        if err is not None:
            print(f"  att err     : {err:.3f} arcsec")
        print(f"  downlink    : {p['downlink_hex']}  ({p['downlink_bytes']} bytes)")
        print(f"  verdict     : {p['metrics'].get('verdict')}")
        if p.get("matched_catalog_ids"):
            print(f"  matched HR  : {', '.join(str(int(x)) for x in p['matched_catalog_ids'])}")
    else:
        print(f"  FAILED: {out.error}")

    if args.lookup:
        print("-" * 55)
        print("  LOOKUP  Yale HR + IAU WGSN name (overlay; not used by Pyramid/Wahba)")
        if out.have_gt:
            print_star_table("Stars in FOV (sim GT)", p["stars_in_fov"])
        print_star_table("Identified", p["identified_stars"])
        if p.get("n_unidentified"):
            print(f"  Unidentified detections: {p['n_unidentified']}")

    print(f"[5/5] Wrote {out.png_path} and {args.out / 'demo_result.json'}")
    print("=" * 70)
    return 0 if out.success else 1


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--full-res" in argv:
        argv = [a for a in argv if a != "--full-res"] + ["--mode", "full"]
    raise SystemExit(main(argv))
