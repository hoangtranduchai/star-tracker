"""BSC5 / synthetic catalog tests. BSC5 tests skip if the binary is absent."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.catalog import BSC5_SIZE, CatalogManager, StarCatalog, ra_dec_to_vectors

ARCSEC = 180.0 * 3600.0 / np.pi

# SIMBAD / Hipparcos J2000 (epoch 2000.0) for header stars.
SIRIUS_HR = 2491
SIRIUS_RA_DEG = 15.0 * (6.0 + 45.0 / 60.0 + 8.91728 / 3600.0)  # 06h 45m 08.91728s
SIRIUS_DEC_DEG = -(16.0 + 42.0 / 60.0 + 58.017 / 3600.0)
VEGA_HR = 7001
VEGA_RA_DEG = 15.0 * (18.0 + 36.0 / 60.0 + 56.33635 / 3600.0)
VEGA_DEC_DEG = 38.0 + 47.0 / 60.0 + 1.2802 / 3600.0


def test_synthetic_source_label():
    cat = CatalogManager.synthetic(100, 6.0, seed=1)
    assert cat.source == "SYNTHETIC"
    assert cat.num_stars == 100
    assert np.all(np.isfinite(cat.vectors))
    norms = np.linalg.norm(cat.vectors, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-12)


def test_npz_roundtrip(tmp_path: Path):
    cat = CatalogManager.synthetic(50, 6.0, seed=2)
    path = tmp_path / "c.npz"
    CatalogManager.save_npz(cat, path)
    loaded = CatalogManager.load_npz(path)
    np.testing.assert_array_equal(loaded.ids, cat.ids)
    np.testing.assert_allclose(loaded.vectors, cat.vectors)
    np.testing.assert_allclose(loaded.mags, cat.mags)
    assert loaded.source == "SYNTHETIC"


def test_filter_close_pairs_drops_fainter():
    ra = np.array([0.0, 1e-6, 1.0])
    dec = np.array([0.0, 0.0, 0.2])
    cat = StarCatalog(
        ids=np.array([1, 2, 3]),
        vectors=ra_dec_to_vectors(ra, dec),
        mags=np.array([1.0, 5.0, 3.0], dtype=np.float32),
        source="SYNTHETIC",
    )
    filtered = CatalogManager.filter_close_pairs(cat, min_sep_arcsec=60.0)
    assert 2 not in set(filtered.ids.tolist())
    assert set(filtered.ids.tolist()) == {1, 3}


def test_create_synthetic_wrapper():
    cat = StarCatalog.create_synthetic_hipparcos_subset(20, 6.0, seed=0)
    assert cat.source == "SYNTHETIC"
    assert cat.num_stars == 20


@pytest.fixture(scope="module")
def bsc5_file(bsc5_path: Path) -> Path:
    if bsc5_path.exists() and bsc5_path.stat().st_size == BSC5_SIZE:
        return bsc5_path
    try:
        return CatalogManager.fetch_bsc5(bsc5_path)
    except FileNotFoundError:
        pytest.skip("BSC5 binary not available (offline or download failed)")


def test_bsc5_header(bsc5_file: Path):
    header = CatalogManager.parse_bsc5_header(bsc5_file)
    assert header["STARN"] == -9110
    assert header["NBENT"] == 32
    assert header["n_entries"] == 9110
    assert header["j2000"] is True
    assert header["raw_size"] == BSC5_SIZE


def test_bsc5_blank_and_bright_stars(bsc5_file: Path):
    # epoch 2000, no PM: compare to J2000 catalog positions
    cat = CatalogManager.load_bsc5(bsc5_file, max_mag=8.0, epoch_year=2000.0, apply_pm=False)
    assert cat.n_blank == 14
    assert cat.n_raw_stars == 9096
    n_v6 = int(np.sum(cat.mags <= 6.0))
    print(f"BSC5 stars with V<=6.0 (epoch 2000, no PM): {n_v6}")
    assert n_v6 > 1000  # sanity, do not hard-code unpublished counts

    sirius = cat.ids == SIRIUS_HR
    vega = cat.ids == VEGA_HR
    assert np.count_nonzero(sirius) == 1
    assert np.count_nonzero(vega) == 1

    def sep_arcsec(mask, ra_deg, dec_deg) -> float:
        ra = cat.ra_rad[mask][0]
        dec = cat.dec_rad[mask][0]
        v1 = ra_dec_to_vectors(np.array([ra]), np.array([dec]))[0]
        v2 = ra_dec_to_vectors(np.array([np.radians(ra_deg)]), np.array([np.radians(dec_deg)]))[0]
        return float(np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0)) * ARCSEC)

    s_err = sep_arcsec(sirius, SIRIUS_RA_DEG, SIRIUS_DEC_DEG)
    v_err = sep_arcsec(vega, VEGA_RA_DEG, VEGA_DEC_DEG)
    print(f"Sirius J2000 residual: {s_err:.3f} arcsec")
    print(f"Vega J2000 residual  : {v_err:.3f} arcsec")
    assert s_err < 2.0
    assert v_err < 2.0


def test_bsc5_pm_ra_convention(bsc5_file: Path):
    """Decide whether XRPM is d(RA)/dt or already includes cos δ, using Sirius."""
    cat0 = CatalogManager.load_bsc5(bsc5_file, max_mag=8.0, epoch_year=2000.0, apply_pm=False)
    idx = int(np.where(cat0.ids == SIRIUS_HR)[0][0])
    dt = 26.7
    pm_ra = cat0.pm_ra_rad_yr[idx]
    pm_dec = cat0.pm_dec_rad_yr[idx]
    dec = cat0.dec_rad[idx]
    # Hipparcos Sirius: pmRA (μα cos δ) ≈ -546.01 mas/yr, pmDE ≈ -1223.07 mas/yr
    mas_to_rad = np.pi / (180.0 * 3_600_000.0)
    hip_pmra_cosd = -546.01 * mas_to_rad  # rad/yr of (μα cos δ)
    hip_pmdec = -1223.07 * mas_to_rad

    # If XRPM already includes cos δ, XRPM ≈ hip_pmra_cosd / 1 rad of RA * ... wait
    # μα cos δ [rad/yr] vs d(RA)/dt [rad/yr] = (μα cos δ) / cos δ
    as_dra_dt = pm_ra  # interpret as dRA/dt
    as_cosd = pm_ra  # interpret as μα cos δ

    err_dra = abs(as_dra_dt * np.cos(dec) - hip_pmra_cosd)
    err_cosd = abs(as_cosd - hip_pmra_cosd)
    print(
        f"Sirius XRPM={pm_ra:.6e} rad/yr, XDPM={pm_dec:.6e}; "
        f"err if dRA/dt={err_dra:.3e}, err if mu_alpha cos delta={err_cosd:.3e}"
    )
    # Document which convention the file uses; loader applies d(RA)/dt (no /cos δ).
    assert err_cosd < err_dra
    assert CatalogManager.BSC5_PM_RA_INCLUDES_COS_DEC is True
    # BSC5 proper motions are coarser than Hipparcos; 2e-7 rad/yr ≈ 41 mas/yr.
    assert err_cosd < 2e-7
    assert abs(pm_dec - hip_pmdec) < 2e-7
