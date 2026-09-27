from pathlib import Path

import numpy as np
import pytest

from src.demo_session import (
    DemoEngine,
    RunRequest,
    camera_for_image,
    find_sidecar,
    resolve_run_camera,
    theta_max_deg_for_fov,
)
from src.starnames import n_iau_names, n_named_hr
from src.visualize import image_stats, save_input_png

ROOT = Path(__file__).resolve().parent.parent


def test_save_input_png_no_overlay(tmp_path):
    img = np.zeros((64, 96), dtype=np.uint16)
    img[20, 30] = 2500
    st = image_stats(img)
    path = save_input_png(img, tmp_path / "in.png", stats=st)
    assert path.exists() and path.stat().st_size > 100
    assert st["width"] == 96 and st["dn_max"] == 2500
    assert len(st["sha256_12"]) == 12


def test_save_input_png_full_frame_does_not_hang(tmp_path):
    """A full demo frame must not freeze the save path."""
    import time

    import matplotlib

    matplotlib.use("Agg", force=True)
    img = np.zeros((4000, 6000), dtype=np.uint16)
    img[1999, 2999] = 4000
    t0 = time.perf_counter()
    path = save_input_png(img, tmp_path / "full.png")
    dt = time.perf_counter() - t0
    assert path.exists() and path.stat().st_size > 100
    assert dt < 8.0


def test_engine_seed42_alkes_and_compare():
    npz = ROOT / "data" / "catalogs" / "bsc5_v6.0.npz"
    if not npz.exists():
        pytest.skip("BSC5 cache missing")
    eng = DemoEngine(ROOT)
    out = eng.run(RunRequest(mode="fast", seed=42, save_png=False, lookup=True, show=False))
    assert out.success
    assert out.payload["downlink_bytes"] == 16
    assert out.metrics["attitude_error_arcsec"] < 40.0
    names = [r.get("iau_name") for r in out.payload["stars_in_fov"]]
    assert "Alkes" in names
    params = [row["param"] for row in out.payload["compare"]]
    assert any(p.startswith("q0") for p in params)
    assert any("Attitude error" in p for p in params)
    ra_row = next(r for r in out.payload["compare"] if "Boresight RA" in r["param"])
    assert isinstance(ra_row["gt"], str) and "°" in ra_row["gt"] and "h" in ra_row["gt"]
    star_row = next(r for r in out.payload["compare"] if "Stars FOV" in r["param"])
    assert isinstance(star_row["delta"], str) and "ID" in star_row["delta"]
    att_row = next(r for r in out.payload["compare"] if r["param"] == "Attitude error")
    assert att_row["gt"] == "0 (ideal)"
    assert out.payload["sim_method"]["generated_by_code"] is True
    assert out.payload["sim_method"]["not_iso_ccsds"] is True
    assert out.payload["input_stats"]["sha256_12"]


def test_point_at_sirius_centers_hr2491():
    npz = ROOT / "data" / "catalogs" / "bsc5_v6.0.npz"
    if not npz.exists():
        pytest.skip("BSC5 cache missing")
    eng = DemoEngine(ROOT)
    out = eng.run(
        RunRequest(
            mode="fast",
            seed=1,
            omega=0.0,
            point_hr=2491,
            save_png=False,
            lookup=True,
            show=False,
        )
    )
    fov = out.payload["stars_in_fov"]
    sirius = next(r for r in fov if r["id"] == 2491)
    assert sirius["iau_name"] == "Sirius"
    cam = out.payload["camera"]
    assert abs(sirius["u_px"] - (cam["width"] - 1) / 2) < 8
    assert abs(sirius["v_px"] - (cam["height"] - 1) / 2) < 8
    assert sirius["mag"] < 0.0
    assert out.payload["n_iau_names"] == n_iau_names()
    assert out.payload["n_iau_hr_names"] == n_named_hr()
    assert out.payload["n_iau_names"] == 640
    assert out.payload["n_iau_hr_names"] > 333


def test_point_at_ra_dec_centers_same_as_hr():
    npz = ROOT / "data" / "catalogs" / "bsc5_v6.0.npz"
    if not npz.exists():
        pytest.skip("BSC5 cache missing")
    eng = DemoEngine(ROOT)
    by_hr = eng.run(
        RunRequest(mode="fast", omega=0.0, point_hr=2491, save_png=False, lookup=True, show=False)
    )
    sirius = next(r for r in by_hr.payload["stars_in_fov"] if r["id"] == 2491)
    out = eng.run(
        RunRequest(
            mode="fast",
            omega=0.0,
            ra_deg=float(sirius["ra_deg"]),
            dec_deg=float(sirius["dec_deg"]),
            save_png=False,
            lookup=True,
            show=False,
        )
    )
    hit = next(r for r in out.payload["stars_in_fov"] if r["id"] == 2491)
    cam = out.payload["camera"]
    assert abs(hit["u_px"] - (cam["width"] - 1) / 2) < 8
    assert abs(hit["v_px"] - (cam["height"] - 1) / 2) < 8
    assert out.payload["point_ra_deg"] == pytest.approx(sirius["ra_deg"])
    assert out.payload["point_dec_deg"] == pytest.approx(sirius["dec_deg"])


def test_find_sidecar_matches_center_full_stem():
    tif = ROOT / "data" / "sim_dataset" / "center_full" / "00_hr2491.tif"
    if not tif.is_file():
        pytest.skip("center_full dataset missing")
    sc = find_sidecar(tif, ROOT)
    assert sc is not None and sc.name == "00_hr2491.json"


def test_camera_rejects_unknown_size():
    from src.camera import demo_camera

    cam = demo_camera()
    with pytest.raises(ValueError, match="tiêu cự"):
        camera_for_image(np.zeros((800, 1200), dtype=np.uint16), cam)


def test_custom_optics_accepts_other_size_and_wide_fov_limit():
    from src.camera import demo_camera

    cam = demo_camera()
    img = np.zeros((600, 800), dtype=np.uint16)
    with pytest.raises(ValueError, match="tiêu cự"):
        resolve_run_camera(RunRequest(), img, cam)
    camera, scale, mode, locked = resolve_run_camera(
        RunRequest(focal_mm=4.0, pixel_um=2.4),
        img,
        cam,
    )
    assert not locked and scale == 1 and mode == "custom"
    assert (camera.width, camera.height) == (800, 600)
    assert camera.focal_mm == 4.0 and camera.pixel_um == 2.4
    diag = camera.fov_deg[2]
    assert diag > 30.5
    assert theta_max_deg_for_fov(diag) >= diag
    assert theta_max_deg_for_fov(19.08) == 30.5
    assert theta_max_deg_for_fov(180.0) == 180.0


def test_custom_focal_keeps_existing_angle_table():
    npz = ROOT / "data" / "catalogs" / "bsc5_v6.0.npz"
    if not npz.exists():
        pytest.skip("BSC5 cache missing")
    eng = DemoEngine(ROOT)
    out = eng.run(
        RunRequest(
            mode="fast",
            omega=0.0,
            focal_mm=80.0,
            point_hr=2491,
            save_png=False,
            lookup=True,
            show=False,
        )
    )
    cam = out.payload["camera"]
    assert cam["optics"] == "custom"
    assert cam["focal_mm"] == pytest.approx(80.0)
    assert cam["pixel_um"] == pytest.approx(14.88)
    assert cam["fov_diag_deg"] < 30.5
    table = out.payload["angle_table"]
    assert table["theta_max_deg"] == pytest.approx(30.5)
    assert table["built_now"] is False
    assert table["n_pairs"] > 100_000
    assert out.success
    sirius = next(r for r in out.payload["stars_in_fov"] if r["id"] == 2491)
    assert abs(sirius["u_px"] - (cam["width"] - 1) / 2) < 8
