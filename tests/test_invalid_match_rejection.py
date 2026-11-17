"""Regression tests ensuring invalid, insufficient, collinear, or outlier matches never return an attitude."""
from __future__ import annotations
import numpy as np
import pytest
from src.attitude import WahbaSolver
from src.camera import demo_camera
from src.catalog import CatalogManager, StarCatalog
from src.centroid import Centroids
from src.demo_session import THETA_MAX_LOCKED_DEG
from src.identification import IdResult, _empty_id_result
from src.kvector import KVectorTable
from src.pipeline import PipelineConfig, StarTrackerPipeline
from src.quaternion import angular_error_arcsec, random_quaternion, to_dcm
from src.simulator import Radiometry, SkySimulator


def _must(cond: bool, msg: str = 'assertion failed') -> None:
    if not cond:
        raise AssertionError(msg)


@pytest.fixture(scope='module')
def guard_stack() -> tuple:
    optics = demo_camera().downscaled(4)
    catalog = CatalogManager.synthetic(3500, 6.0, seed=99)
    kv_table = KVectorTable.build(catalog, theta_min_deg=0.02, theta_max_deg=THETA_MAX_LOCKED_DEG)
    params = PipelineConfig(
        bg_block=32,
        angular_tol_rad=4.0 * optics.ifov_rad,
        mask_dilate_px=6,
        mask_min_area_px=8,
        max_area=80,
    )
    tracker = StarTrackerPipeline(optics, catalog, kv_table, params)
    renderer = SkySimulator(
        optics,
        catalog,
        radiometry=Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0),
        seed=99,
    )
    solved_frame = solved_gt = solved_q = solved_res = None
    for idx in range(60):
        q_cand = SkySimulator.generate_random_quaternion(seed=40 + idx)
        frame, gt = renderer.render(q_cand, omega_deg_s=(0.0, 0.0, 0.0), add_noise=True)
        if len(gt.cat_idx) >= 10:
            res = tracker.process_frame(frame)
            if res.success and len(res.ident.obs_idx) >= 8:
                solved_frame, solved_gt, solved_q, solved_res = frame, gt, q_cand, res
                break
    _must(solved_res is not None, 'Fixture failed to find a clean solvable frame')
    return (optics, catalog, kv_table, params, renderer, solved_frame, solved_gt, solved_q, solved_res)


def test_insufficient_detections_returns_lost_zero_downlink(guard_stack: tuple) -> None:
    optics, catalog, kv_table, params, renderer, _, _, _, _ = guard_stack
    tracker = StarTrackerPipeline(optics, catalog, kv_table, params)

    blank = np.full((optics.height, optics.width), 64, dtype=np.uint16)
    res_zero = tracker.process_frame(blank)
    _must(res_zero.success is False)
    _must(res_zero.status == 'LOST')
    _must(res_zero.reject_code == 'INSUFFICIENT_DETECTIONS')
    _must(res_zero.q is None and res_zero.a is None)
    _must(res_zero.to_downlink_bytes() == b'\x00' * 16)
    _must('Insufficient' in (res_zero.error or ''))
    _must(res_zero.match_stats is not None)
    _must(res_zero.match_stats['status'] == 'LOST')
    _must(res_zero.match_stats['reject_code'] == 'INSUFFICIENT_DETECTIONS')
    _must(res_zero.match_stats['n_detected'] == 0)
    _must(res_zero.match_stats['n_valid_pairs'] == 0)

    two_star_img = np.full((optics.height, optics.width), 64.0, dtype=np.float32)
    uv_two = np.asarray([[200.0, 200.0], [500.0, 350.0]], dtype=np.float64)
    renderer._stamp_gaussians(two_star_img, uv_two, np.asarray([5000.0, 4500.0]), 1.2, 5)
    res_two = tracker.process_frame(np.clip(two_star_img, 0, 4095).astype(np.uint16))
    _must(res_two.success is False)
    _must(res_two.status == 'LOST')
    _must(res_two.reject_code == 'INSUFFICIENT_DETECTIONS')
    _must(res_two.q is None)
    _must(res_two.to_downlink_bytes() == b'\x00' * 16)
    _must(res_two.match_stats['n_detected'] == 2)


def test_fewer_than_three_matched_stars_returns_identification_failed(
    guard_stack: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    optics, catalog, kv_table, params, _, solved_frame, _, _, _ = guard_stack
    tracker = StarTrackerPipeline(optics, catalog, kv_table, params)

    monkeypatch.setattr(tracker.star_identifier, 'identify', lambda *args, **kwargs: _empty_id_result(5))
    monkeypatch.setattr(tracker.star_identifier, 'identify_wide', lambda *args, **kwargs: _empty_id_result(0))
    res_none = tracker.process_frame(solved_frame)
    _must(res_none.success is False)
    _must(res_none.status == 'LOST')
    _must(res_none.reject_code == 'IDENTIFICATION_FAILED')
    _must(res_none.q is None and res_none.a is None)
    _must(res_none.to_downlink_bytes() == b'\x00' * 16)
    _must(res_none.match_stats['n_valid_pairs'] == 0)

    monkeypatch.setattr(
        tracker.star_identifier,
        'identify',
        lambda *args, **kwargs: IdResult(
            np.asarray([0, 1], dtype=np.int32),
            np.asarray([10, 20], dtype=np.int32),
            True,
            1,
            0.0,
        ),
    )
    res_two = tracker.process_frame(solved_frame)
    _must(res_two.success is False)
    _must(res_two.status == 'LOST')
    _must(res_two.reject_code == 'IDENTIFICATION_FAILED')
    _must(res_two.q is None)
    _must(res_two.to_downlink_bytes() == b'\x00' * 16)


@pytest.mark.parametrize('n_true,n_bad', [(2, 2), (2, 4), (1, 5), (0, 6), (2, 8)])
def test_regression_outlier_retention_never_locks_below_three_inliers(
    guard_stack: tuple, monkeypatch: pytest.MonkeyPatch, n_true: int, n_bad: int
) -> None:
    optics, catalog, kv_table, params, _, solved_frame, _, _, solved_res = guard_stack
    tracker = StarTrackerPipeline(optics, catalog, kv_table, params)

    true_obs = solved_res.ident.obs_idx[:n_true]
    true_cat = solved_res.ident.cat_idx[:n_true]
    all_obs = np.arange(len(solved_res.centroids.vectors), dtype=np.int32)
    unused_obs = [int(o) for o in all_obs if int(o) not in set(true_obs.tolist())]
    _must(len(unused_obs) >= n_bad, 'Need enough unused centroids for outlier injection')
    bad_obs = np.asarray(unused_obs[:n_bad], dtype=np.int32)

    # Choose catalog stars in the opposite hemisphere so they cannot align with the true attitude
    used_cat = set(true_cat.tolist())
    bad_cat_list = []
    for o_idx in bad_obs:
        obs_vec = solved_res.centroids.vectors[int(o_idx)]
        opp_scores = catalog.vectors @ (solved_res.a.T @ obs_vec)
        order = np.argsort(opp_scores)
        chosen = next(int(c) for c in order if int(c) not in used_cat)
        used_cat.add(chosen)
        bad_cat_list.append(chosen)
    bad_cat = np.asarray(bad_cat_list, dtype=np.int32)

    obs_mix = np.concatenate([true_obs, bad_obs]).astype(np.int32)
    cat_mix = np.concatenate([true_cat, bad_cat]).astype(np.int32)

    monkeypatch.setattr(
        tracker.star_identifier,
        'identify',
        lambda *args, **kwargs: IdResult(obs_mix, cat_mix, True, 1, 0.0),
    )
    monkeypatch.setattr(tracker.star_identifier, 'identify_wide', lambda *args, **kwargs: _empty_id_result(0))

    out = tracker.process_frame(solved_frame)
    _must(out.success is False)
    _must(out.status == 'LOST')
    _must(out.reject_code == 'INSUFFICIENT_INLIER_PAIRS')
    _must(out.q is None and out.a is None)
    _must(out.to_downlink_bytes() == b'\x00' * 16)
    _must(out.match_stats is not None)
    _must(out.match_stats['n_initial_matched'] == n_true + n_bad)
    _must(out.match_stats['n_valid_pairs'] < 3)
    _must(out.match_stats['n_rejected_outliers'] >= n_bad)


def test_post_association_outlier_is_stripped_without_poisoning_attitude(
    guard_stack: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    optics, catalog, kv_table, params, _, solved_frame, _, solved_q, solved_res = guard_stack

    # Append one synthetic decoy catalog star ~0.35 deg (1260 arcsec) away from a real matched star
    extra_o: int = int(solved_res.ident.obs_idx[-1])
    true_cat_for_extra: int = int(solved_res.ident.cat_idx[-1])
    base_vec = catalog.vectors[true_cat_for_extra].copy()
    ortho = np.cross(base_vec, np.asarray([1.0, 0.0, 0.0]) if abs(base_vec[0]) < 0.8 else np.asarray([0.0, 1.0, 0.0]))
    ortho /= np.linalg.norm(ortho)
    ang = np.deg2rad(0.35)
    decoy_vec = np.cos(ang) * base_vec + np.sin(ang) * ortho
    decoy_vec /= np.linalg.norm(decoy_vec)

    aug_cat = StarCatalog(
        ids=np.append(catalog.ids, np.int32(999999)),
        vectors=np.vstack([catalog.vectors, decoy_vec[None, :]]),
        mags=np.append(catalog.mags, np.float32(4.0)),
        source=catalog.source,
    )
    decoy_cat_idx: int = int(aug_cat.num_stars - 1)
    tracker = StarTrackerPipeline(optics, aug_cat, kv_table, params)

    # Seed with 8 clean pairs (excluding extra_o), then inject (extra_o, decoy_cat_idx) during _associate_remaining
    seed_obs = solved_res.ident.obs_idx[:8].copy()
    seed_cat = solved_res.ident.cat_idx[:8].copy()
    _must(extra_o not in set(seed_obs.tolist()))
    monkeypatch.setattr(
        tracker.star_identifier,
        'identify',
        lambda *args, **kwargs: IdResult(seed_obs, seed_cat, True, 1, 0.0),
    )

    orig_assoc = tracker._associate_remaining

    def _corrupted_assoc(cents: object, a: object, obs_idx: object, cat_idx: object) -> tuple:
        o_out, c_out = orig_assoc(cents, a, obs_idx, cat_idx)
        keep_mask = o_out != extra_o
        o_clean, c_clean = o_out[keep_mask], c_out[keep_mask]
        return (
            np.concatenate([o_clean, np.asarray([extra_o], dtype=np.int32)]),
            np.concatenate([c_clean, np.asarray([decoy_cat_idx], dtype=np.int32)]),
        )

    monkeypatch.setattr(tracker, '_associate_remaining', _corrupted_assoc)

    out = tracker.process_frame(solved_frame)
    _must(out.success is True, f'Expected clean solve after stripping post-assoc outlier, got {out.error}')
    _must(out.status == 'SOLVED')
    _must(out.reject_code is None)
    _must(out.match_stats['n_rejected_outliers'] >= 1)
    _must(decoy_cat_idx not in set(out.ident.cat_idx.tolist()))
    _must(angular_error_arcsec(out.q, solved_q) < 40.0)
    gate_floor = float(np.degrees(params.angular_tol_rad) * 3600.0)
    _must(float(np.max(out.residuals_arcsec)) <= gate_floor + 1e-6)


def test_collinear_stars_rejected_in_wahba_and_pipeline(
    guard_stack: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    optics, catalog, kv_table, params, _, solved_frame, _, _, _ = guard_stack
    q_rot = random_quaternion(np.random.default_rng(7))
    dcm_rot = to_dcm(q_rot)

    # 3 collinear camera vectors on v=cy (great circle plane y_cam = 0)
    b_col = np.asarray([[-0.12, 0.0, 1.0], [0.0, 0.0, 1.0], [0.12, 0.0, 1.0]], dtype=np.float64)
    b_col /= np.linalg.norm(b_col, axis=1, keepdims=True)
    r_col = (dcm_rot.T @ b_col.T).T

    with pytest.raises(ValueError, match='Degenerate or collinear'):
        WahbaSolver.solve_svd(b_col, r_col)
    with pytest.raises(ValueError, match='Degenerate or collinear'):
        WahbaSolver.solve_quest(b_col, r_col)

    # Pipeline check with 3 collinear detected stars
    tracker = StarTrackerPipeline(optics, catalog, kv_table, params)
    u_pts = np.asarray([[250.0, 200.0], [450.0, 200.0], [650.0, 200.0]], dtype=np.float64)
    b_vecs = optics.unproject(u_pts)
    col_cents = Centroids(
        uv=u_pts,
        flux=np.asarray([1000.0, 900.0, 800.0]),
        area=np.asarray([9.0, 9.0, 9.0]),
        peak=np.asarray([500.0, 450.0, 400.0]),
        mu20=np.ones(3),
        mu02=np.ones(3),
        mu11=np.zeros(3),
        axis_ratio=np.ones(3),
        angle_rad=np.zeros(3),
        vectors=b_vecs,
        sigma_px=np.full(3, 0.2),
    )
    monkeypatch.setattr(tracker.centroid_detector, 'detect', lambda *args, **kwargs: col_cents)
    monkeypatch.setattr(
        tracker.star_identifier,
        'identify',
        lambda *args, **kwargs: IdResult(
            np.asarray([0, 1, 2], dtype=np.int32),
            np.asarray([0, 1, 2], dtype=np.int32),
            True,
            1,
            0.0,
        ),
    )
    monkeypatch.setattr(tracker.star_identifier, 'identify_wide', lambda *args, **kwargs: _empty_id_result(0))

    res = tracker.process_frame(solved_frame)
    _must(res.success is False)
    _must(res.status == 'LOST')
    _must(res.reject_code == 'COLLINEAR_DEGENERATE_GEOMETRY')
    _must(res.q is None)
    _must(res.to_downlink_bytes() == b'\x00' * 16)


def test_pure_random_false_stars_never_produce_false_lock(guard_stack: tuple) -> None:
    optics, catalog, kv_table, params, renderer, _, _, _, _ = guard_stack
    tracker = StarTrackerPipeline(optics, catalog, kv_table, params)
    rng = np.random.default_rng(2026)

    for trial in range(10):
        n_false = int(rng.integers(6, 15))
        canvas = np.full((optics.height, optics.width), 64.0, dtype=np.float32)
        u_rnd = rng.uniform(20.0, optics.width - 20.0, size=n_false)
        v_rnd = rng.uniform(20.0, optics.height - 20.0, size=n_false)
        uv_rnd = np.column_stack([u_rnd, v_rnd])
        elec = rng.uniform(3500.0, 9000.0, size=n_false)
        renderer._stamp_gaussians(canvas, uv_rnd, elec, 1.2, 5)
        frame = np.clip(canvas + rng.normal(0.0, 4.0, size=canvas.shape), 0, 4095).astype(np.uint16)

        res = tracker.process_frame(frame)
        _must(res.success is False, f'False lock on random star field trial {trial}!')
        _must(res.status == 'LOST')
        _must(res.q is None and res.a is None)
        _must(res.to_downlink_bytes() == b'\x00' * 16)
        _must(res.reject_code is not None)


def test_three_star_match_rejected_when_min_stars_is_four(
    guard_stack: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    optics, catalog, kv_table, params, _, solved_frame, _, _, solved_res = guard_stack
    tracker = StarTrackerPipeline(optics, catalog, kv_table, params)

    monkeypatch.setattr(
        tracker.star_identifier,
        'identify',
        lambda *args, **kwargs: IdResult(
            solved_res.ident.obs_idx[:3],
            solved_res.ident.cat_idx[:3],
            True,
            1,
            0.0,
        ),
    )
    monkeypatch.setattr(tracker.star_identifier, 'identify_wide', lambda *args, **kwargs: _empty_id_result(0))
    monkeypatch.setattr(tracker, '_associate_remaining', lambda c, a, o, cat: (o, cat))

    res = tracker.process_frame(solved_frame)
    _must(res.success is False)
    _must(res.status == 'LOST')
    _must(res.reject_code == 'INSUFFICIENT_INLIER_PAIRS')
    _must(res.q is None)
    _must(res.match_stats['n_valid_pairs'] == 3)
    _must(res.match_stats['min_pairs_required'] == 4)


def test_max_refine_zero_still_strips_outlier_and_resolves(
    guard_stack: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    optics, catalog, kv_table, params, _, solved_frame, _, solved_q, solved_res = guard_stack
    zero_cfg = PipelineConfig(
        bg_block=params.bg_block,
        angular_tol_rad=params.angular_tol_rad,
        mask_dilate_px=params.mask_dilate_px,
        mask_min_area_px=params.mask_min_area_px,
        max_area=params.max_area,
        max_refine=0,
    )
    extra_o = int(solved_res.ident.obs_idx[-1])
    true_cat = int(solved_res.ident.cat_idx[-1])
    base_vec = catalog.vectors[true_cat].copy()
    ortho = np.cross(base_vec, np.asarray([1.0, 0.0, 0.0]) if abs(base_vec[0]) < 0.8 else np.asarray([0.0, 1.0, 0.0]))
    ortho /= np.linalg.norm(ortho)
    decoy_vec = np.cos(np.deg2rad(0.4)) * base_vec + np.sin(np.deg2rad(0.4)) * ortho
    decoy_vec /= np.linalg.norm(decoy_vec)
    aug_cat = StarCatalog(
        ids=np.append(catalog.ids, np.int32(999998)),
        vectors=np.vstack([catalog.vectors, decoy_vec[None, :]]),
        mags=np.append(catalog.mags, np.float32(4.0)),
        source=catalog.source,
    )
    decoy_idx = int(aug_cat.num_stars - 1)
    tracker = StarTrackerPipeline(optics, aug_cat, kv_table, zero_cfg)

    obs_mix = np.append(solved_res.ident.obs_idx[:8], np.int32(extra_o))
    cat_mix = np.append(solved_res.ident.cat_idx[:8], np.int32(decoy_idx))
    monkeypatch.setattr(tracker.star_identifier, 'identify', lambda *a, **k: IdResult(obs_mix, cat_mix, True, 1, 0.0))
    monkeypatch.setattr(tracker, '_associate_remaining', lambda c, a, o, cat: (o, cat))

    out = tracker.process_frame(solved_frame)
    _must(out.success is True, f'Expected clean solve with max_refine=0, got {out.error}')
    _must(out.status == 'SOLVED')
    _must(out.match_stats['n_rejected_outliers'] == 1)
    _must(decoy_idx not in set(out.ident.cat_idx.tolist()))
    _must(angular_error_arcsec(out.q, solved_q) < 40.0)


def test_excessive_postfit_residual_and_low_fov_consistency(
    guard_stack: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    optics, catalog, kv_table, params, _, solved_frame, _, _, solved_res = guard_stack

    # 1. Low FOV consistency: only 4 clean matches in a field expecting > 10 stars
    tracker_low = StarTrackerPipeline(optics, catalog, kv_table, params)
    monkeypatch.setattr(
        tracker_low.star_identifier,
        'identify',
        lambda *a, **k: IdResult(solved_res.ident.obs_idx[:4], solved_res.ident.cat_idx[:4], True, 1, 0.0),
    )
    monkeypatch.setattr(tracker_low.star_identifier, 'identify_wide', lambda *a, **k: _empty_id_result(0))
    monkeypatch.setattr(tracker_low, '_associate_remaining', lambda c, a, o, cat: (o, cat))
    res_low = tracker_low.process_frame(solved_frame)
    _must(res_low.success is False)
    _must(res_low.status == 'LOST')
    _must(res_low.reject_code == 'LOW_FOV_CONSISTENCY')
    _must(res_low.q is None)
    _must(res_low.match_stats['fov_expected_stars'] >= 8)

    # 2. Excessive post-fit RMS residual: individual residuals pass sigma gate, but collective RMS > rms_limit
    tight_cfg = PipelineConfig(
        bg_block=params.bg_block,
        angular_tol_rad=np.deg2rad(10.0 / 3600.0),
        mask_dilate_px=params.mask_dilate_px,
        mask_min_area_px=params.mask_min_area_px,
        max_area=params.max_area,
        residual_n_sigma=3.0,
    )
    tracker_rms = StarTrackerPipeline(optics, catalog, kv_table, tight_cfg)
    # sigma_px=0.5 -> gate_arc ~ 92.1 arcsec, rms_limit = 0.8 * 92.1 = 73.7 arcsec.
    # Perturb every matched star oppositely by ~0.025 deg (~90 arcsec): each residual <= 92.1, yet RMS ~ 88 > 73.7!
    cents_orig = solved_res.centroids
    wide_sig_cents = Centroids(
        uv=cents_orig.uv,
        flux=cents_orig.flux,
        area=cents_orig.area,
        peak=cents_orig.peak,
        mu20=cents_orig.mu20,
        mu02=cents_orig.mu02,
        mu11=cents_orig.mu11,
        axis_ratio=cents_orig.axis_ratio,
        angle_rad=cents_orig.angle_rad,
        vectors=cents_orig.vectors,
        sigma_px=np.full(len(cents_orig.vectors), 0.5, dtype=np.float64),
    )
    monkeypatch.setattr(tracker_rms.centroid_detector, 'detect', lambda *a, **k: wide_sig_cents)
    aug_cat2 = StarCatalog(
        ids=catalog.ids.copy(),
        vectors=catalog.vectors.copy(),
        mags=catalog.mags.copy(),
        source=catalog.source,
    )
    sel_obs = solved_res.ident.obs_idx[:8]
    sel_cat = solved_res.ident.cat_idx[:8]
    # Apply opposing ~82-arcsec shifts in orthogonal directions so Wahba cannot absorb them:
    # each residual stays <= gate_arc (~92.1 arcsec), yet collective RMS (~76.8 arcsec) > rms_limit (~73.7 arcsec)!
    ang_pert = np.deg2rad(82.0 / 3600.0)
    for k_idx, c_idx in enumerate(sel_cat.tolist()):
        base_vec = catalog.vectors[int(c_idx)].copy()
        seed_axis = np.asarray([1.0, 0.0, 0.0]) if abs(base_vec[0]) < 0.8 else np.asarray([0.0, 1.0, 0.0])
        ortho1 = np.cross(base_vec, seed_axis)
        ortho1 /= np.linalg.norm(ortho1)
        ortho2 = np.cross(base_vec, ortho1)
        ortho2 /= np.linalg.norm(ortho2)
        theta_dir = 2.0 * np.pi * (k_idx / 8.0)
        dir_vec = np.cos(theta_dir) * ortho1 + np.sin(theta_dir) * ortho2
        pert_vec = np.cos(ang_pert) * base_vec + np.sin(ang_pert) * dir_vec
        pert_vec /= np.linalg.norm(pert_vec)
        aug_cat2.vectors[int(c_idx)] = pert_vec
    tracker_rms.catalog = aug_cat2

    monkeypatch.setattr(
        tracker_rms.star_identifier,
        'identify',
        lambda *a, **k: IdResult(sel_obs, sel_cat, True, 1, 0.0),
    )
    monkeypatch.setattr(tracker_rms, '_associate_remaining', lambda c, a, o, cat: (o, cat))
    res_rms = tracker_rms.process_frame(solved_frame)
    _must(res_rms.success is False)
    _must(res_rms.status == 'LOST')
    _must(res_rms.reject_code == 'EXCESSIVE_POSTFIT_RESIDUAL')
    _must(res_rms.q is None)
    _must(res_rms.match_stats['rms_residual_arcsec'] > 70.0)
