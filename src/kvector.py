"""
Mortari K-vector index on inter-star angles (radians).

Query time is O(1) plus a tiny exact filter of the liberal bin range.
Pairs are built with blocked matrix multiplies (no Python loop over pairs).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .catalog import StarCatalog


@dataclass
class KVectorTable:
    pairs: np.ndarray  # (P, 2) int32, sorted by angle
    angles: np.ndarray  # (P,) float64 rad
    m: float
    q: float
    n_bins: int
    theta_min: float
    theta_max: float
    catalog_fingerprint: str = ""

    def __post_init__(self):
        self.num_pairs = int(len(self.angles))

    @classmethod
    def build(
        cls,
        cat: StarCatalog,
        theta_min_deg: float = 0.02,
        theta_max_deg: float = 30.5,
        n_bins: int | None = None,
        block: int = 512,
    ) -> "KVectorTable":
        theta_min = np.radians(theta_min_deg)
        theta_max = np.radians(theta_max_deg)
        vecs = cat.vectors
        n = cat.num_stars
        pair_i: list[np.ndarray] = []
        pair_j: list[np.ndarray] = []
        angs: list[np.ndarray] = []
        for i0 in range(0, n, block):
            i1 = min(i0 + block, n)
            dots = vecs[i0:i1] @ vecs.T
            dots = np.clip(dots, -1.0, 1.0)
            for li, i in enumerate(range(i0, i1)):
                d = dots[li, i + 1 :]
                ang = np.arccos(d)
                mask = (ang >= theta_min) & (ang <= theta_max)
                if not np.any(mask):
                    continue
                js = np.nonzero(mask)[0] + (i + 1)
                pair_i.append(np.full(js.shape, i, dtype=np.int32))
                pair_j.append(js.astype(np.int32, copy=False))
                angs.append(ang[mask].astype(np.float64, copy=False))
        if not angs:
            raise ValueError("No star pairs found in the requested angle range.")
        angles = np.concatenate(angs)
        pairs = np.column_stack((np.concatenate(pair_i), np.concatenate(pair_j)))
        order = np.argsort(angles, kind="mergesort")
        angles = np.ascontiguousarray(angles[order])
        pairs = np.ascontiguousarray(pairs[order])
        n_pairs = len(angles)
        bins = n_pairs if n_bins is None else int(n_bins)
        if bins < 2:
            bins = 2
        y1 = float(angles[0])
        yn = float(angles[-1])
        xi = (np.finfo(np.float64).eps * max(abs(yn), 1.0)) * 10.0
        m = (yn - y1 + 2.0 * xi) / (n_pairs - 1)
        q = y1 - m - xi
        return cls(
            pairs=pairs,
            angles=angles,
            m=float(m),
            q=float(q),
            n_bins=n_pairs,
            theta_min=float(theta_min),
            theta_max=float(theta_max),
            catalog_fingerprint=cat.fingerprint(),
        )

    def _k_index(self, y: float) -> int:
        """1-based Mortari k such that z(k) = m k + q; clamp to [1, n]."""
        n = self.num_pairs
        k = int(np.floor((y - self.q) / self.m))
        return int(np.clip(k, 1, n))

    def query(self, theta_rad: float, eps_rad: float) -> np.ndarray:
        """Return pairs whose angle is in [theta-eps, theta+eps].

        Uses binary search on the sorted angle array (Mortari K-vector range is
        an O(1) hint; searchsorted is exact and O(log P)).
        """
        y_a = float(theta_rad) - float(eps_rad)
        y_b = float(theta_rad) + float(eps_rad)
        i0 = int(np.searchsorted(self.angles, y_a, side="left"))
        i1 = int(np.searchsorted(self.angles, y_b, side="right"))
        if i1 <= i0:
            return np.empty((0, 2), dtype=np.int32)
        return self.pairs[i0:i1]

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            pairs=self.pairs,
            angles=self.angles,
            m=np.array([self.m]),
            q=np.array([self.q]),
            n_bins=np.array([self.n_bins]),
            theta_min=np.array([self.theta_min]),
            theta_max=np.array([self.theta_max]),
            catalog_fingerprint=np.array([self.catalog_fingerprint]),
        )
        return path

    @classmethod
    def load(cls, path: Path) -> "KVectorTable":
        data = np.load(path, allow_pickle=False)
        return cls(
            pairs=data["pairs"],
            angles=data["angles"],
            m=float(data["m"][0]),
            q=float(data["q"][0]),
            n_bins=int(data["n_bins"][0]),
            theta_min=float(data["theta_min"][0]),
            theta_max=float(data["theta_max"][0]),
            catalog_fingerprint=str(data["catalog_fingerprint"][0]),
        )


def cache_path_for(cat: StarCatalog, cache_dir: Path, theta_min_deg: float, theta_max_deg: float) -> Path:
    name = f"kvec_{cat.source}_{cat.fingerprint()}_{theta_min_deg}_{theta_max_deg}.npz"
    return Path(cache_dir) / name


def build_or_load(
    cat: StarCatalog,
    cache_dir: Path,
    theta_min_deg: float = 0.02,
    theta_max_deg: float = 30.5,
) -> KVectorTable:
    path = cache_path_for(cat, cache_dir, theta_min_deg, theta_max_deg)
    if path.exists():
        table = KVectorTable.load(path)
        if table.catalog_fingerprint == cat.fingerprint():
            return table
    table = KVectorTable.build(cat, theta_min_deg=theta_min_deg, theta_max_deg=theta_max_deg)
    table.save(path)
    return table
