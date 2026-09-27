"""Lost-in-space star ID: Mortari Pyramid + K-vector + chirality + remaining stars."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .camera import CameraModel
from .catalog import StarCatalog
from .kvector import KVectorTable


@dataclass
class IdResult:
    obs_idx: np.ndarray
    cat_idx: np.ndarray
    success: bool
    n_pyramids_tested: int
    expected_false: float


def _attitudes_from_pair(
    b1: np.ndarray,
    b2: np.ndarray,
    r1: np.ndarray,
    r2: np.ndarray,
) -> np.ndarray:
    """One body-from-inertial matrix per catalog pair. The cross product fixes roll."""
    bc = np.cross(b1, b2)
    rc = np.cross(r1, r2)
    # B_ij = sum_k b_k[i] * r_k[j]
    profile = (
        b1[None, :, None] * r1[:, None, :]
        + b2[None, :, None] * r2[:, None, :]
        + bc[None, :, None] * rc[:, None, :]
    )
    left, _, right_t = np.linalg.svd(profile)
    sign = np.sign(np.linalg.det(left) * np.linalg.det(right_t))
    sign = np.where(sign == 0.0, 1.0, sign)
    repair = np.broadcast_to(np.eye(3), left.shape).copy()
    repair[:, 2, 2] = sign
    return left @ repair @ right_t


def _inlier_stats(
    attitudes: np.ndarray,
    catalog_vectors: np.ndarray,
    observed_uv: np.ndarray,
    camera: CameraModel,
    inlier_px: float,
    tight_px: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Loose hits, tight hits, and mean nearest-star distance for each attitude."""
    loose = np.zeros(len(attitudes), dtype=np.int32)
    tight = np.zeros(len(attitudes), dtype=np.int32)
    mean_dist = np.full(len(attitudes), np.inf)
    for start in range(0, len(attitudes), 250):
        block = attitudes[start : start + 250]
        cam_v = np.einsum("mij,nj->mni", block, catalog_vectors)
        front = cam_v[:, :, 2] > 0.0
        scale = np.maximum(cam_v[:, :, 2], 1e-12)
        u = camera.fx * cam_v[:, :, 0] / scale + camera.cx
        v = camera.fy * cam_v[:, :, 1] / scale + camera.cy
        du = u[:, :, None] - observed_uv[None, None, :, 0]
        dv = v[:, :, None] - observed_uv[None, None, :, 1]
        dist = np.hypot(du, dv)
        dist = np.where(front[:, :, None], dist, np.inf)
        nearest = dist.min(axis=1)
        stop = start + len(block)
        loose[start:stop] = (nearest < inlier_px).sum(axis=1)
        tight[start:stop] = (nearest < tight_px).sum(axis=1)
        mean_dist[start:stop] = np.mean(np.minimum(nearest, 50.0), axis=1)
    return loose, tight, mean_dist


def _pair_map(pairs: np.ndarray) -> dict[int, set[int]]:
    m: dict[int, set[int]] = {}
    for a, b in pairs:
        ia, ib = int(a), int(b)
        m.setdefault(ia, set()).add(ib)
        m.setdefault(ib, set()).add(ia)
    return m


def _chirality(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> int:
    return int(np.sign(np.dot(a, np.cross(b, c))))


def _inner_sines(bi, bj, bk) -> tuple[float, float, float]:
    def s_at(p, q, r):
        vq = q - p
        vr = r - p
        nq = np.linalg.norm(vq)
        nr = np.linalg.norm(vr)
        if nq < 1e-18 or nr < 1e-18:
            return 1.0
        c = float(np.clip(np.dot(vq, vr) / (nq * nr), -1.0, 1.0))
        return float(np.sin(np.arccos(c)))

    return s_at(bi, bj, bk), s_at(bj, bi, bk), s_at(bk, bi, bj)


class StarIdentifier:
    def __init__(
        self,
        catalog: StarCatalog,
        kvector: KVectorTable,
        tol_rad: float,
        n_false_sky: int = 300,
        p_max: float = 1e-4,
        max_stars: int = 12,
        cutoff: int = 2000,
        tol_frac: float = 0.0,
    ):
        self.catalog = catalog
        self.kvector = kvector
        self.tol_rad = float(tol_rad)
        self.tol_frac = float(tol_frac)
        self.n_false_sky = int(n_false_sky)
        self.p_max = float(p_max)
        self.max_stars = int(max_stars)
        self.cutoff = int(cutoff)
        nf = max(self.n_false_sky, 1)
        self._econst = (nf**4) * (self.tol_rad**5) / (2.0 * np.pi**2)

    def _tol(self, theta: float) -> float:
        """Base window plus a fraction of the pair angle.

        A datasheet focal length can be about 1% off the plate in the file.
        On a 10° pair that is a few arcminutes, larger than a one-pixel window.
        """
        return self.tol_rad + self.tol_frac * abs(float(theta))

    def identify(self, vectors: np.ndarray, flux: np.ndarray | None = None) -> IdResult:
        vecs = np.asarray(vectors, dtype=np.float64)
        n = len(vecs)
        empty = IdResult(
            obs_idx=np.empty(0, dtype=np.int32),
            cat_idx=np.empty(0, dtype=np.int32),
            success=False,
            n_pyramids_tested=0,
            expected_false=0.0,
        )
        if n < 3:
            return empty
        if flux is None:
            order = np.arange(n)
        else:
            order = np.argsort(-np.asarray(flux))
        n_check = min(n, self.max_stars)
        sel = order[:n_check]
        b = vecs[sel]
        dots = np.clip(b @ b.T, -1.0, 1.0)
        ang = np.arccos(dots)
        tested = 0
        n_s = n_check

        # Pyramid: i < j < k < r with Mortari-style index strides
        for dj in range(1, n_s - 2):
            for dk in range(1, n_s - dj - 1):
                for dr in range(1, n_s - dj - dk):
                    imax = n_s - dj - dk - dr
                    for i0 in range(imax):
                        i = i0
                        j = i + dj
                        k = j + dk
                        r = k + dr
                        tested += 1
                        if tested > self.cutoff:
                            return empty
                        match = self._try_pyramid(b, ang, i, j, k, r)
                        if match is None:
                            continue
                        ci, cj, ck, cr, efalse = match
                        mapping = {i: ci, j: cj, k: ck, r: cr}
                        mapping.update(self._identify_remaining(b, ang, mapping))
                        obs = np.array([sel[o] for o in mapping], dtype=np.int32)
                        cat = np.array(list(mapping.values()), dtype=np.int32)
                        return IdResult(obs, cat, True, tested, efalse)

        # Triangle fallback
        for i in range(n_s):
            for j in range(i + 1, n_s):
                for k in range(j + 1, n_s):
                    tested += 1
                    if tested > self.cutoff:
                        return empty
                    tri = self._try_triangle(b, ang, i, j, k)
                    if tri is None:
                        continue
                    ci, cj, ck, efalse = tri
                    mapping = {i: ci, j: cj, k: ck}
                    mapping.update(self._identify_remaining(b, ang, mapping))
                    if len(mapping) < 3:
                        continue
                    obs = np.array([sel[o] for o in mapping], dtype=np.int32)
                    cat = np.array(list(mapping.values()), dtype=np.int32)
                    return IdResult(obs, cat, True, tested, efalse)
        return IdResult(
            np.empty(0, dtype=np.int32),
            np.empty(0, dtype=np.int32),
            False,
            tested,
            0.0,
        )

    def _false_gate(self, bi, bj, bk, theta_ij: float) -> float | None:
        si, sj, sk = _inner_sines(bi, bj, bk)
        denom = max(sk * max(si, sj, sk), 1e-12)
        efalse = self._econst * np.sin(theta_ij) / denom
        if efalse > self.p_max:
            return None
        return float(efalse)

    def _triangle_matches(self, b, ang, i, j, k) -> list[tuple[int, int, int]] | None:
        """Catalog triangles for one observed triangle. None if the false-match gate fails."""
        if self._false_gate(b[i], b[j], b[k], float(ang[i, j])) is None:
            return None
        if _chirality(b[i], b[j], b[k]) == 0:
            return None
        pij = self.kvector.query(float(ang[i, j]), self._tol(ang[i, j]))
        pik = self.kvector.query(float(ang[i, k]), self._tol(ang[i, k]))
        pjk = self.kvector.query(float(ang[j, k]), self._tol(ang[j, k]))
        if len(pij) == 0 or len(pik) == 0 or len(pjk) == 0:
            return None
        mij, mik, mjk = _pair_map(pij), _pair_map(pik), _pair_map(pjk)
        found: list[tuple[int, int, int]] = []
        torch = _chirality(b[i], b[j], b[k])
        for ci, partners in mij.items():
            for cj in partners:
                ks_i = mik.get(ci, set())
                ks_j = mjk.get(cj, set())
                for ck in ks_i.intersection(ks_j):
                    if ck in (ci, cj):
                        continue
                    ri, rj, rk = self.catalog.vectors[ci], self.catalog.vectors[cj], self.catalog.vectors[ck]
                    if _chirality(ri, rj, rk) != torch:
                        continue
                    found.append((ci, cj, ck))
        return found

    def _try_triangle(self, b, ang, i, j, k):
        found = self._triangle_matches(b, ang, i, j, k)
        if not found:
            return None
        uniq = {tuple(sorted(t)) for t in found}
        if len(uniq) != 1:
            return None
        efalse = self._false_gate(b[i], b[j], b[k], float(ang[i, j]))
        return found[0][0], found[0][1], found[0][2], efalse

    def _try_pyramid(self, b, ang, i, j, k, r):
        efalse = self._false_gate(b[i], b[j], b[k], float(ang[i, j]))
        if efalse is None:
            return None
        found = self._triangle_matches(b, ang, i, j, k)
        if not found:
            return None
        # Several catalog triangles can share these three angles. The fourth
        # star has to leave exactly one of them.
        oriented: dict[tuple[int, int, int], tuple[int, int, int]] = {}
        for ci, cj, ck in found:
            oriented.setdefault(tuple(sorted((ci, cj, ck))), (ci, cj, ck))
        pir = self.kvector.query(float(ang[i, r]), self._tol(ang[i, r]))
        pjr = self.kvector.query(float(ang[j, r]), self._tol(ang[j, r]))
        pkr = self.kvector.query(float(ang[k, r]), self._tol(ang[k, r]))
        mir, mjr, mkr = _pair_map(pir), _pair_map(pjr), _pair_map(pkr)
        winners: list[tuple[int, int, int, int]] = []
        for ci, cj, ck in oriented.values():
            cand = mir.get(ci, set()).intersection(mjr.get(cj, set())).intersection(mkr.get(ck, set()))
            cand.discard(ci)
            cand.discard(cj)
            cand.discard(ck)
            if len(cand) != 1:
                continue
            winners.append((ci, cj, ck, next(iter(cand))))
        if len({tuple(sorted(w)) for w in winners}) != 1:
            return None
        ci, cj, ck, cr = winners[0]
        return ci, cj, ck, cr, efalse

    def identify_wide(
        self,
        vectors: np.ndarray,
        flux: np.ndarray | None,
        camera: CameraModel,
        *,
        vote_px: float = 8.0,
        inlier_px: float = 6.0,
    ) -> IdResult:
        """When no Pyramid triangle is unique, vote with the tightest pair.

        A wide plate scale puts thousands of catalog pairs inside one tolerance
        window, so Pyramid's uniqueness test never fires. Each catalog pair for
        the shortest observed pair still implies one attitude. The right one
        puts the other detected stars back on catalog stars.
        """
        empty = IdResult(
            obs_idx=np.empty(0, dtype=np.int32),
            cat_idx=np.empty(0, dtype=np.int32),
            success=False,
            n_pyramids_tested=0,
            expected_false=0.0,
        )
        vecs = np.asarray(vectors, dtype=np.float64)
        n = len(vecs)
        if n < 4:
            return empty
        if flux is None:
            order = np.arange(n)
        else:
            order = np.argsort(-np.asarray(flux, dtype=np.float64))
        order = order[: min(n, self.max_stars)]
        obs = vecs[order]
        m = len(obs)
        dots = np.clip(obs @ obs.T, -1.0, 1.0)
        ang = np.arccos(dots)
        np.fill_diagonal(ang, np.inf)
        flat = np.argsort(ang, axis=None)
        tol = max(float(self.tol_rad), float(vote_px) * float(camera.ifov_rad))
        chosen = None
        for idx in flat:
            i, j = divmod(int(idx), m)
            if j <= i:
                continue
            theta = float(ang[i, j])
            if theta < np.radians(0.5) or theta > float(self.kvector.theta_max):
                continue
            pairs = self.kvector.query(theta, max(tol, self._tol(theta)))
            if len(pairs) == 0 or len(pairs) > 15000:
                continue
            chosen = (i, j, pairs)
            break
        if chosen is None:
            return empty
        i, j, pairs = chosen
        a = pairs[:, 0].astype(np.int32)
        b = pairs[:, 1].astype(np.int32)
        ci = np.concatenate([a, b])
        cj = np.concatenate([b, a])
        attitudes = _attitudes_from_pair(obs[i], obs[j], self.catalog.vectors[ci], self.catalog.vectors[cj])
        uv = camera.project(obs)[0]
        loose, tight, mean_dist = _inlier_stats(
            attitudes, self.catalog.vectors, uv, camera, inlier_px, min(3.0, inlier_px)
        )
        # Tight hits break ties. Several wrong skies can each land 5 stars inside 6 px.
        rank = np.lexsort((mean_dist, -loose, -tight))
        best = int(rank[0])
        second = int(rank[1]) if len(rank) > 1 else best
        if int(tight[best]) < 4 or int(loose[best]) < 4:
            return empty
        if int(tight[best]) == int(tight[second]) and int(loose[best]) == int(loose[second]):
            return empty
        attitude = attitudes[best]
        cam_v = (attitude @ self.catalog.vectors.T).T
        depth = cam_v[:, 2]
        in_front = depth > 0.0
        proj_u = camera.fx * cam_v[:, 0] / np.maximum(depth, 1e-12) + camera.cx
        proj_v = camera.fy * cam_v[:, 1] / np.maximum(depth, 1e-12) + camera.cy
        used: set[int] = set()
        obs_keep: list[int] = []
        cat_keep: list[int] = []
        for local_k, (u, v) in enumerate(uv):
            dist = np.hypot(proj_u - u, proj_v - v)
            dist = np.where(in_front, dist, np.inf)
            cat_i = int(np.argmin(dist))
            if not np.isfinite(dist[cat_i]) or dist[cat_i] > inlier_px or cat_i in used:
                continue
            used.add(cat_i)
            obs_keep.append(int(order[local_k]))
            cat_keep.append(cat_i)
        if len(obs_keep) < 3:
            return empty
        return IdResult(
            obs_idx=np.asarray(obs_keep, dtype=np.int32),
            cat_idx=np.asarray(cat_keep, dtype=np.int32),
            success=True,
            n_pyramids_tested=int(len(attitudes)),
            expected_false=0.0,
        )

    def _identify_remaining(self, b, ang, mapping: dict[int, int]) -> dict[int, int]:
        extra: dict[int, int] = {}
        identified_obs = list(mapping.keys())
        n = len(b)
        for m in range(n):
            if m in mapping:
                continue
            sets: list[set[int]] = []
            for oi in identified_obs[:3]:
                theta_m = float(ang[min(m, oi), max(m, oi)])
                pairs = self.kvector.query(theta_m, self._tol(theta_m))
                pmap = _pair_map(pairs)
                sets.append(pmap.get(mapping[oi], set()))
            if not sets:
                continue
            inter = sets[0]
            for s in sets[1:]:
                inter = inter.intersection(s)
            inter -= set(mapping.values())
            inter -= set(extra.values())
            if len(inter) == 1:
                extra[m] = next(iter(inter))
        return extra
