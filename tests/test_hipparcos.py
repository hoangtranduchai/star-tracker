"""Hipparcos TSV loader (NASA COTS starcat.tsv = VizieR I/311 hip2)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.catalog import CatalogManager

STARCAT = Path(__file__).resolve().parent.parent / "data" / "catalogs" / "starcat.tsv"


@pytest.mark.skipif(not STARCAT.exists(), reason="starcat.tsv not cached")
def test_hipparcos_tsv_v6_count():
    cat = CatalogManager.load_hipparcos_tsv(STARCAT, max_mag=6.0, epoch_year=2000.0)
    print(f"Hipparcos Hp<=6.0 stars: {cat.num_stars}")
    assert cat.source == "HIPPARCOS"
    # A&A 2010: Hipparcos V<6 ≈ 3500. Hp is not V; allow a wide band, do not invent.
    assert 2500 <= cat.num_stars <= 5000
    assert np.all(cat.mags <= 6.0 + 1e-6)
