#!/usr/bin/env python3
"""Render contest slide figures from this repo only (no brand names)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle, Ellipse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "outputs" / "ai2026_figures"
OUT.mkdir(parents=True, exist_ok=True)


def fig_pipeline() -> Path:
    fig, ax = plt.subplots(figsize=(12.5, 3.6), dpi=160)
    ax.set_xlim(0, 12.5)
    ax.set_ylim(0, 3.6)
    ax.axis("off")
    boxes = [
        (0.3, 1.1, 1.9, 1.4, "Ảnh sao\n(FAST demo)"),
        (2.5, 1.1, 2.0, 1.4, "Centroid\nCoG | CNN*"),
        (4.8, 1.1, 2.2, 1.4, "Pyramid +\nK-vector"),
        (7.3, 1.1, 2.0, 1.4, "Wahba\nSVD/QUEST"),
        (9.6, 1.1, 2.4, 1.4, "Quaternion\n16 byte"),
    ]
    for x, y, w, h, label in boxes:
        ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12",
                facecolor="#e8f1fb", edgecolor="#1f4e79", linewidth=1.6,
            )
        )
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=11, color="#123")
    for x0, x1 in [(2.3, 2.5), (4.5, 4.8), (7.0, 7.3), (9.3, 9.6)]:
        ax.annotate("", xy=(x1, 1.8), xytext=(x0, 1.8),
                    arrowprops=dict(arrowstyle="->", color="#1f4e79", lw=1.8))
    ax.text(6.25, 0.35,
            "* CNN = MobileUNet công khai (Zhao et al., arXiv:2404.19108), tùy chọn — không thay lõi nhận dạng/Wahba",
            ha="center", fontsize=8.5, color="#444")
    ax.set_title("Đường ống star tracker (demo laptop)", fontsize=13, pad=8, color="#1f4e79")
    path = OUT / "pipeline.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def fig_camera_geometry() -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=160)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    # Sensor rectangle
    ax.add_patch(Rectangle((0.6, 1.6), 2.4, 1.6, fill=False, lw=2, edgecolor="#1f4e79"))
    ax.text(1.8, 2.4, "Cảm biến\nAPS-C\n6000×4000\np=3,72 µm", ha="center", va="center", fontsize=9)
    # Lens
    ax.add_patch(Ellipse((4.0, 2.4), 0.55, 1.5, fill=False, lw=2, edgecolor="#c45c26"))
    ax.text(4.0, 0.85, "f = 50 mm", ha="center", fontsize=10, color="#c45c26")
    # Rays to FOV
    ax.plot([4.3, 8.8], [3.1, 4.6], color="#1f4e79", lw=1.2)
    ax.plot([4.3, 8.8], [1.7, 0.6], color="#1f4e79", lw=1.2)
    ax.plot([4.3, 8.8], [2.4, 2.4], color="#888", lw=1.0, ls="--")
    ax.text(7.2, 4.85, "FOV ≈ 25,16° × 16,93°", fontsize=10, color="#1f4e79")
    ax.text(7.2, 0.25, "đường chéo ≈ 30,03°", fontsize=9, color="#555")
    # FAST box
    ax.add_patch(FancyBboxPatch((0.5, 3.55), 3.0, 1.35, boxstyle="round,pad=0.05",
                                facecolor="#fff4e8", edgecolor="#c45c26", lw=1.4))
    ax.text(2.0, 4.2, "FAST (bin 4×4)\n1500×1000\npixel 14,88 µm\n61,38″/pixel",
            ha="center", va="center", fontsize=9)
    ax.add_patch(FancyBboxPatch((5.5, 1.55), 4.0, 2.1, boxstyle="round,pad=0.05",
                                facecolor="#f3f7fb", edgecolor="#1f4e79", lw=1.2))
    ax.text(7.5, 2.6,
            "Thước góc đầy đủ:\n15,35″/pixel\n\nTâm ảnh:\nu₀=2999,5  v₀=1999,5",
            ha="center", va="center", fontsize=10)
    ax.set_title("Hình học camera demo (không ghi tên cảm biến/ống kính)", fontsize=12, color="#1f4e79")
    path = OUT / "camera_geometry.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def fig_starfield_and_centroids() -> Path | None:
    """One FAST frame with classical centroids overlaid."""
    try:
        from src.demo_session import DemoEngine, RunRequest
    except Exception as e:
        print("skip starfield:", e)
        return None

    engine = DemoEngine(ROOT)
    req = RunRequest(mode="fast", seed=42, catalog="bsc5", max_mag=6.0, solver="svd", glare="none")
    # Prefer a lightweight path if available
    try:
        result = engine.run(req)
    except Exception as e:
        print("demo run failed:", e)
        return None

    img = None
    cents = None
    # Pull image/centroids from common result shapes
    for attr in ("image", "frame", "raw_image", "img"):
        if hasattr(result, attr) and getattr(result, attr) is not None:
            img = np.asarray(getattr(result, attr))
            break
    if img is None and isinstance(result, dict):
        img = result.get("image") or result.get("frame")
    if img is None:
        # Fall back: inspect engine last artifacts
        art = getattr(engine, "last_artifacts", None) or getattr(engine, "last_result", None)
        if isinstance(art, dict):
            img = art.get("image")
            cents = art.get("centroids")
        elif art is not None:
            img = getattr(art, "image", None)
            cents = getattr(art, "centroids", None)

    if hasattr(result, "centroids"):
        cents = result.centroids
    elif hasattr(result, "tracker") and hasattr(result.tracker, "centroids"):
        cents = result.tracker.centroids
    elif isinstance(result, dict):
        cents = result.get("centroids")

    # Try saved outputs from run
    out_dir = ROOT / "data" / "outputs"
    candidates = sorted(out_dir.glob("**/frame*.png")) + sorted(out_dir.glob("**/*seed42*.png"))
    if img is None and candidates:
        import cv2
        img = cv2.imread(str(candidates[-1]), cv2.IMREAD_UNCHANGED)

    if img is None:
        # Direct simulator path
        from src.camera import demo_camera
        from src.catalog import CatalogManager
        from src.simulator import SkySimulator, Radiometry
        from src.demo_session import load_specs, radiometry_from_specs, load_catalog
        from src.centroid import detect_stars

        specs = load_specs(ROOT)
        cam = demo_camera(mode="fast")
        cat, _ = load_catalog("bsc5", 6.0, ROOT / "data" / "catalogs")
        rad = radiometry_from_specs(specs)
        sim = SkySimulator(cam, cat, radiometry=rad)
        q = SkySimulator.generate_random_quaternion(seed=42)
        frame, truth = sim.render(q, exposure_s=0.15, seed=42)
        img = frame
        det = detect_stars(frame, cam)
        cents = getattr(det, "centroids", None)
        if cents is None and isinstance(det, dict):
            cents = det.get("centroids")
        if cents is None and hasattr(det, "uv"):
            cents = det.uv

    img = np.asarray(img)
    if img.ndim == 3:
        gray = img.mean(axis=2)
    else:
        gray = img.astype(np.float64)
    # Display stretch
    lo, hi = np.percentile(gray, [1, 99.5])
    vis = np.clip((gray - lo) / max(hi - lo, 1e-6), 0, 1)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), dpi=150)
    axes[0].imshow(vis, cmap="gray", origin="upper")
    axes[0].set_title("Ảnh FAST mô phỏng (seed 42)")
    axes[0].axis("off")

    axes[1].imshow(vis, cmap="gray", origin="upper")
    if cents is not None:
        c = np.asarray(cents)
        if c.ndim == 2 and c.shape[1] >= 2:
            axes[1].scatter(
                c[:, 0], c[:, 1], s=55, facecolors="none",
                edgecolors="#ffdd33", linewidths=1.6, marker="o",
            )
            axes[1].scatter(c[:, 0], c[:, 1], s=8, c="#ffdd33", marker="+")
    axes[1].set_title("Tâm sao CoG (vàng)")
    axes[1].axis("off")
    fig.suptitle("Minh họa centroid trên một khung FAST", fontsize=12, color="#1f4e79")
    path = OUT / "starfield_centroid.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def fig_comparison_table(bench_path: Path) -> Path | None:
    if not bench_path.is_file():
        return None
    data = json.loads(bench_path.read_text(encoding="utf-8"))
    s = data.get("summary", data)
    cl = s.get("classical") or {}
    nn = s.get("cnn") or {}
    if cl.get("rmse_px_mean") is None:
        return None

    def row(name, block):
        if not block or block.get("rmse_px_mean") is None:
            return [name, "chưa kiểm được", "—", "—", "—"]
        return [
            name,
            f"{block['rmse_px_mean']:.4f}",
            f"{block.get('rmse_px_median', float('nan')):.4f}",
            f"{block.get('matched_stars_total', '?')}/{block.get('gt_stars_total', '?')}",
            f"{block.get('time_ms_median', float('nan')):.1f}",
        ]

    rows = [
        ["Phương án", "RMSE tb (px)", "RMSE tv (px)", "Sao khớp/GT", "ms/khung (tv)"],
        row("CoG cổ điển", cl),
        row("CNN MobileUNet (công khai)", nn),
    ]
    fig, ax = plt.subplots(figsize=(10.5, 2.8), dpi=160)
    ax.axis("off")
    table = ax.table(cellText=rows, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.15, 1.7)
    for j in range(5):
        table[0, j].set_facecolor("#1f4e79")
        table[0, j].set_text_props(color="white", weight="bold")
    n = s.get("n_requested", "?")
    ax.set_title(f"So sánh centroid trên {n} khung FAST (đo trong repo này)", fontsize=12, pad=12, color="#1f4e79")
    path = OUT / "comparison_table.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def main() -> None:
    paths = [fig_pipeline(), fig_camera_geometry()]
    sf = fig_starfield_and_centroids()
    if sf:
        paths.append(sf)
    bench = ROOT / "data" / "outputs" / "centroid_benchmark_500.json"
    ct = fig_comparison_table(bench)
    if ct:
        paths.append(ct)
    print("figures:", [str(p) for p in paths])


if __name__ == "__main__":
    main()
