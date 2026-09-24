"""Unit tests for Mortari Pyramid star-pattern identification and chirality verification."""
from __future__ import annotations
import time
import numpy as np
from src.catalog import StarCatalog
from src.identification import StarIdentifier, _chirality
from src.kvector import KVectorTable

def _must(cond: bool, msg: str='identification test failed') -> None:
    if not cond:
        raise AssertionError(msg)

def _make_clustered_catalog(n_in_fov: int=10, n_background: int=250, rng_seed: int=0) -> object:
    prng: object = np.random.default_rng(rng_seed)
    tan_xy: object = prng.uniform(low=-0.07, high=0.07, size=(n_in_fov, 2))
    fov_dirs: object = np.hstack([tan_xy, np.ones((n_in_fov, 1), dtype=np.float64)])
    fov_dirs /= np.linalg.norm(fov_dirs, axis=-1, keepdims=True)
    cos_theta: object = prng.uniform(low=-1.0, high=1.0, size=n_background)
    phi: object = prng.uniform(low=0.0, high=2.0 * np.pi, size=n_background)
    sin_theta: object = np.sqrt(np.maximum(0.0, 1.0 - cos_theta * cos_theta))
    bg_dirs: object = np.stack([sin_theta * np.cos(phi), sin_theta * np.sin(phi), cos_theta], axis=-1)
    bg_dirs: object = bg_dirs[bg_dirs[:, 2] < 0.85]
    all_vectors: object = np.concatenate([fov_dirs, bg_dirs], axis=0)
    all_mags: object = np.concatenate([np.linspace(1.0, 4.5, n_in_fov), prng.uniform(3.0, 6.0, size=len(bg_dirs))]).astype(np.float32)
    catalog: object = StarCatalog(ids=np.arange(len(all_vectors), dtype=np.int32), vectors=all_vectors, mags=all_mags, source='SYNTHETIC')
    return (catalog, n_in_fov)

def test_identifies_noisy_fov_stars() -> object:
    catalog, count_fov = _make_clustered_catalog()
    kv_index: object = KVectorTable.build(catalog, theta_min_deg=0.02, theta_max_deg=19.5)
    solver: object = StarIdentifier(catalog, kv_index, tol_rad=float(np.deg2rad(0.02)), max_stars=12)
    prng: object = np.random.default_rng(1)
    obs_vecs: object = catalog.vectors[:count_fov].copy() + prng.normal(scale=5e-06, size=(count_fov, 3))
    obs_vecs /= np.linalg.norm(obs_vecs, axis=-1, keepdims=True)
    obs_flux: object = np.power(10.0, -0.4 * catalog.mags[:count_fov])
    match: object = solver.identify(obs_vecs, obs_flux)
    _must(bool(match.success))
    _must(len(match.obs_idx) >= 4)
    _must(set(match.cat_idx.tolist()).issubset(set(range(count_fov))))

def test_survives_three_false_stars() -> object:
    catalog, count_fov = _make_clustered_catalog(rng_seed=2)
    kv_index: object = KVectorTable.build(catalog)
    solver: object = StarIdentifier(catalog, kv_index, tol_rad=float(np.deg2rad(0.03)), max_stars=12, n_false_sky=400)
    prng: object = np.random.default_rng(2)
    spurious: object = prng.normal(size=(3, 3))
    spurious[:, 2] = np.abs(spurious[:, 2]) + 0.8
    spurious /= np.linalg.norm(spurious, axis=-1, keepdims=True)
    combined_obs: object = np.concatenate([catalog.vectors[:count_fov].copy(), spurious], axis=0)
    combined_flux: object = np.concatenate([np.linspace(10.0, 5.0, count_fov), np.asarray([9.0, 8.0, 7.0])])
    match: object = solver.identify(combined_obs, combined_flux)
    _must(bool(match.success))
    _must(set(match.cat_idx.tolist()).issubset(set(range(count_fov))))

def test_chirality_rejects_mirror() -> object:
    basis_x: object = np.asarray([1.0, 0.0, 0.0])
    basis_y: object = np.asarray([0.0, 1.0, 0.0])
    basis_z: object = np.asarray([0.0, 0.0, 1.0])
    _must(_chirality(basis_x, basis_y, basis_z) == -_chirality(basis_x, basis_z, basis_y))

def test_milky_way_capped_runtime() -> object:
    prng: object = np.random.default_rng(4)
    dense_n: object = 180
    tan_xy: object = prng.uniform(low=-0.08, high=0.08, size=(dense_n, 2))
    cluster: object = np.hstack([tan_xy, np.ones((dense_n, 1))])
    cluster /= np.linalg.norm(cluster, axis=-1, keepdims=True)
    ambient: object = prng.normal(size=(400, 3))
    ambient /= np.linalg.norm(ambient, axis=-1, keepdims=True)
    all_vecs: object = np.concatenate([cluster, ambient], axis=0)
    catalog: object = StarCatalog(ids=np.arange(len(all_vecs), dtype=np.int32), vectors=all_vecs, mags=np.clip(prng.uniform(1.0, 6.0, size=len(all_vecs)), 0.5, 6.0).astype(np.float32), source='SYNTHETIC')
    kv_index: object = KVectorTable.build(catalog, theta_min_deg=0.02, theta_max_deg=19.5)
    solver: object = StarIdentifier(catalog, kv_index, tol_rad=float(np.deg2rad(0.03)), max_stars=12, cutoff=2000)
    t_start: object = time.perf_counter()
    solver.identify(cluster[:120], np.linspace(20.0, 1.0, 120))
    elapsed_ms: object = (time.perf_counter() - t_start) * 1000.0
    _must(elapsed_ms < 25.0)
