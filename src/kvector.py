"""Mortari K-vector index on inter-star angles (radians)."""
from pathlib import Path
from numpy import any as npany, arccos, argsort, ascontiguousarray, asarray, clip, column_stack, concatenate, empty, finfo, floor, float64, full, int32, load as npload, nonzero, radians, savez_compressed, searchsorted

def _scan_angle_blocks(vecs: object, num_stars: object, min_rad: object, max_rad: object, step: object) -> object:
    rows_acc, cols_acc, ang_acc = ([], [], [])
    for start in range(0, num_stars, step):
        stop: object = min(start + step, num_stars)
        gram_slice: object = clip(vecs[start:stop] @ vecs.T, -1.0, 1.0)
        for rel_i, abs_i in enumerate(range(start, stop)):
            tail_angles: object = arccos(gram_slice[rel_i, abs_i + 1:])
            in_band: object = (tail_angles >= min_rad) & (tail_angles <= max_rad)
            if npany(in_band):
                matched_j: object = nonzero(in_band)[0] + (abs_i + 1)
                rows_acc.append(full(matched_j.shape, abs_i, dtype=int32))
                cols_acc.append(matched_j.astype(int32, copy=False))
                ang_acc.append(tail_angles[in_band].astype(float64, copy=False))
    return (rows_acc, cols_acc, ang_acc)

class KVectorTable:
    """Sorted inter-star angle table with linear Mortari K-vector parameters."""

    def __init__(self, pairs: object, angles: object, m: object, q: object, n_bins: object, theta_min: object, theta_max: object, catalog_fingerprint: object='') -> object:
        self.pairs, self.angles, self.m, self.q, self.n_bins, self.theta_min, self.theta_max, self.catalog_fingerprint, self.num_pairs = (pairs, angles, float(m), float(q), int(n_bins), float(theta_min), float(theta_max), str(catalog_fingerprint), int(len(angles)))

    @classmethod
    def build(cls, cat: object, theta_min_deg: object=0.02, theta_max_deg: object=30.5, n_bins: object=None, block: object=512) -> object:
        rad_lo, rad_hi = (float(radians(theta_min_deg)), float(radians(theta_max_deg)))
        r_list, c_list, a_list = _scan_angle_blocks(cat.vectors, int(cat.num_stars), rad_lo, rad_hi, int(block))
        if not a_list:
            raise ValueError('No star pairs found in the requested angle range.')
        raw_angs: object = concatenate(a_list)
        raw_pairs: object = column_stack((concatenate(r_list), concatenate(c_list)))
        perm: object = argsort(raw_angs, kind='mergesort')
        s_angs: object = ascontiguousarray(raw_angs[perm])
        s_pairs: object = ascontiguousarray(raw_pairs[perm])
        total_p: object = int(s_angs.size)
        y_first, y_last = (float(s_angs[0]), float(s_angs[-1]))
        pad: object = float(finfo(float64).eps) * max(abs(y_last), 1.0) * 10.0
        slope: object = (y_last - y_first + 2.0 * pad) / float(max(total_p - 1, 1))
        intercept: object = y_first - slope - pad
        return cls(pairs=s_pairs, angles=s_angs, m=slope, q=intercept, n_bins=total_p, theta_min=rad_lo, theta_max=rad_hi, catalog_fingerprint=cat.fingerprint())

    def _k_index(self, y: object) -> object:
        raw_k: object = int(floor((float(y) - self.q) / self.m))
        return int(clip(raw_k, 1, self.num_pairs))

    def query(self, theta_rad: object, eps_rad: object) -> object:
        """Return `(M, 2)` array of catalog star pairs within `[theta_rad - eps_rad, theta_rad + eps_rad]`."""
        center, tol = (float(theta_rad), float(eps_rad))
        left_i: object = int(searchsorted(self.angles, center - tol, side='left'))
        right_i: object = int(searchsorted(self.angles, center + tol, side='right'))
        return self.pairs[left_i:right_i] if right_i > left_i else empty((0, 2), dtype=int32)

    def save(self, path: object) -> object:
        out_path: object = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        savez_compressed(out_path, pairs=self.pairs, angles=self.angles, m=asarray([self.m]), q=asarray([self.q]), n_bins=asarray([self.n_bins]), theta_min=asarray([self.theta_min]), theta_max=asarray([self.theta_max]), catalog_fingerprint=asarray([self.catalog_fingerprint]))
        return out_path

    @classmethod
    def load(cls, path: object) -> object:
        archive: object = npload(path, allow_pickle=False)
        return cls(pairs=archive['pairs'], angles=archive['angles'], m=float(archive['m'][0]), q=float(archive['q'][0]), n_bins=int(archive['n_bins'][0]), theta_min=float(archive['theta_min'][0]), theta_max=float(archive['theta_max'][0]), catalog_fingerprint=str(archive['catalog_fingerprint'][0]))

def cache_path_for(cat: object, cache_dir: object, theta_min_deg: object, theta_max_deg: object) -> object:
    fname: object = f'kvec_{cat.source}_{cat.fingerprint()}_{theta_min_deg}_{theta_max_deg}.npz'
    return Path(cache_dir) / fname

def build_or_load(cat: object, cache_dir: object, theta_min_deg: object=0.02, theta_max_deg: object=30.5) -> object:
    target_file: object = cache_path_for(cat, cache_dir, theta_min_deg, theta_max_deg)
    if target_file.exists():
        cached: object = KVectorTable.load(target_file)
        if cached.catalog_fingerprint == cat.fingerprint():
            return cached
    fresh: object = KVectorTable.build(cat, theta_min_deg=theta_min_deg, theta_max_deg=theta_max_deg)
    fresh.save(target_file)
    return fresh
