"""Job list and boresight geometry for the benchmark image set."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np

from src.camera import demo_camera
from src.catalog import CatalogManager
from src.quaternion import angular_error_arcsec, looking_at
from src.simulator import Radiometry, SkySimulator

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_benchmark_dataset as bench  # noqa: E402


def _catalog():
    path = Path(__file__).resolve().parent.parent / "data" / "catalogs" / "bsc5_v6.0.npz"
    return CatalogManager.load_npz(path)


def test_center_jobs_cover_every_catalog_star():
    cat = _catalog()
    jobs = bench.build_jobs(cat)
    center = [job for job in jobs if job["split"] == "center"]
    assert [job["catalog_idx"] for job in center] == list(range(cat.num_stars))
    assert len({job["hr"] for job in center}) == cat.num_stars
    assert all(job["noise"] == "nominal" and job["roll_deg"] == 0 and job["slew_deg_s"] == 0.0 for job in center)


def test_factorial_is_a_balanced_grid():
    cat = _catalog()
    jobs = bench.build_jobs(cat)
    factorial = [job for job in jobs if job["split"] == "factorial"]
    assert len(factorial) == 24 * 4 * 2 * 4
    counts = Counter((job["roll_deg"], job["slew_deg_s"], job["noise"]) for job in factorial)
    assert len(counts) == 32
    assert set(counts.values()) == {24}
    assert Counter(job["scene_id"] for job in factorial) == {i: 32 for i in range(24)}
    assert len(jobs) == 5023 + 768


def test_center_star_stays_on_the_principal_point_for_roll():
    cat = _catalog()
    cam = demo_camera().downscaled(4)
    job = next(item for item in bench.build_jobs(cat) if item["split"] == "center" and item["hr"] == 2491)
    sim = SkySimulator(
        cam,
        cat,
        radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0),
        seed=0,
    )
    base = dict(job)
    base["noise"] = "clean"
    _img, meta = bench.render_job(sim, cam, cat, base)
    uv = next(row for row in meta["stars_in_fov"] if row["hr"] == 2491)
    np.testing.assert_allclose([uv["u_px"], uv["v_px"]], [cam.cx, cam.cy], atol=1e-3)

    rolled = dict(base)
    rolled["roll_deg"] = 90
    _img, meta_roll = bench.render_job(sim, cam, cat, rolled)
    uv_roll = next(row for row in meta_roll["stars_in_fov"] if row["hr"] == 2491)
    np.testing.assert_allclose([uv_roll["u_px"], uv_roll["v_px"]], [cam.cx, cam.cy], atol=1e-3)
    assert angular_error_arcsec(
        np.asarray(meta_roll["q_gt"]),
        looking_at(cat.vectors[int(job["catalog_idx"])]),
    ) > 1.0
