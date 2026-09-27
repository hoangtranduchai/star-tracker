"""Lost-in-space star identification via Mortari's Pyramid algorithm and wide-field pair voting."""
from numpy import arange, arccos, argmin, argsort, asarray, broadcast_to, clip, concatenate, cross, dot, einsum, empty, eye, fill_diagonal, float64, full, hypot, inf, int32, isfinite, lexsort, maximum, mean, minimum, pi, radians, sign, sin, where, zeros
from numpy.linalg import det, norm, svd

class IdResult:
    """Matched observation and catalog index arrays from lost-in-space star identification."""

    def __init__(self, obs_idx: object, cat_idx: object, success: object, n_pyramids_tested: object, expected_false: object) -> object:
        self.obs_idx, self.cat_idx, self.success, self.n_pyramids_tested, self.expected_false = (obs_idx, cat_idx, bool(success), int(n_pyramids_tested), float(expected_false))

def _empty_id_result(tested: object=0) -> object:
    z_i32: object = empty(0, dtype=int32)
    return IdResult(z_i32, z_i32, False, int(tested), 0.0)

def _attitudes_from_pair(b1: object, b2: object, r1: object, r2: object) -> object:
    """Compute candidate rotation matrices aligning `(r1, r2)` with `(b1, b2)` via triad SVD."""
    b_orth, r_orth = (cross(b1, b2), cross(r1, r2))
    prof: object = b1[None, :, None] * r1[:, None, :] + b2[None, :, None] * r2[:, None, :] + b_orth[None, :, None] * r_orth[:, None, :]
    u_m, _, vt_m = svd(prof)
    d_sgn: object = sign(det(u_m) * det(vt_m))
    d_sgn: object = where(d_sgn == 0.0, 1.0, d_sgn)
    fix: object = broadcast_to(eye(3, dtype=float64), u_m.shape).copy()
    fix[:, 2, 2] = d_sgn
    return u_m @ fix @ vt_m

def _inlier_stats(attitudes: object, catalog_vectors: object, observed_uv: object, camera: object, inlier_px: object, tight_px: object) -> object:
    """Score batch of candidate attitudes by loose/tight pixel reprojection inliers."""
    num_att: object = int(len(attitudes))
    cnt_loose: object = zeros(num_att, dtype=int32)
    cnt_tight: object = zeros(num_att, dtype=int32)
    avg_err: object = full(num_att, inf, dtype=float64)
    obs_u, obs_v = (observed_uv[:, 0], observed_uv[:, 1])
    fx, fy, cx, cy = (camera.fx, camera.fy, camera.cx, camera.cy)
    for s_idx in range(0, num_att, 250):
        chunk: object = attitudes[s_idx:s_idx + 250]
        e_idx: object = s_idx + len(chunk)
        cam_xyz: object = einsum('mij,nj->mni', chunk, catalog_vectors)
        cz: object = cam_xyz[:, :, 2]
        vis: object = cz > 0.0
        inv_z: object = 1.0 / maximum(cz, 1e-12)
        pu: object = fx * (cam_xyz[:, :, 0] * inv_z) + cx
        pv: object = fy * (cam_xyz[:, :, 1] * inv_z) + cy
        err_px: object = hypot(pu[:, :, None] - obs_u[None, None, :], pv[:, :, None] - obs_v[None, None, :])
        err_px: object = where(vis[:, :, None], err_px, inf)
        min_d: object = err_px.min(axis=1)
        cnt_loose[s_idx:e_idx] = (min_d < inlier_px).sum(axis=1)
        cnt_tight[s_idx:e_idx] = (min_d < tight_px).sum(axis=1)
        avg_err[s_idx:e_idx] = mean(minimum(min_d, 50.0), axis=1)
    return (cnt_loose, cnt_tight, avg_err)

def _pair_map(pairs: object) -> object:
    adj: object = {}
    for u_i, v_i in pairs:
        a, b = (int(u_i), int(v_i))
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return adj

def _chirality(v_a: object, v_b: object, v_c: object) -> object:
    return int(sign(dot(v_a, cross(v_b, v_c))))

def _vertex_sine(origin: object, arm1: object, arm2: object) -> object:
    d1, d2 = (arm1 - origin, arm2 - origin)
    n1, n2 = (float(norm(d1)), float(norm(d2)))
    if n1 < 1e-18 or n2 < 1e-18:
        return 1.0
    cos_val: object = float(clip(dot(d1, d2) / (n1 * n2), -1.0, 1.0))
    return float(sin(arccos(cos_val)))

def _inner_sines(bi: object, bj: object, bk: object) -> object:
    return (_vertex_sine(bi, bj, bk), _vertex_sine(bj, bi, bk), _vertex_sine(bk, bi, bj))

def _iter_pyramid_indices(n_s: object) -> object:
    for dj in range(1, n_s - 2):
        for dk in range(1, n_s - dj - 1):
            for dr in range(1, n_s - dj - dk):
                for i in range(n_s - dj - dk - dr):
                    j: object = i + dj
                    k: object = j + dk
                    yield (i, j, k, k + dr)

def _iter_triangle_indices(n_s: object) -> object:
    for i in range(n_s):
        for j in range(i + 1, n_s):
            for k in range(j + 1, n_s):
                yield (i, j, k)

class StarIdentifier:
    """Mortari Pyramid star-pattern identifier with wide-FOV pair-voting fallback."""

    def __init__(self, catalog: object, kvector: object, tol_rad: object, n_false_sky: object=300, p_max: object=0.0001, max_stars: object=12, cutoff: object=2000, tol_frac: object=0.0) -> object:
        nf: object = max(int(n_false_sky), 1)
        t_rad: object = float(tol_rad)
        self.catalog, self.kvector, self.tol_rad, self.tol_frac, self.n_false_sky, self.p_max, self.max_stars, self.cutoff, self._econst = (catalog, kvector, t_rad, float(tol_frac), int(n_false_sky), float(p_max), int(max_stars), int(cutoff), nf ** 4 * t_rad ** 5 / (2.0 * float(pi) ** 2))

    def _tol(self, theta: object) -> object:
        return self.tol_rad + self.tol_frac * abs(float(theta))

    def _pack_solution(self, sel: object, b_vecs: object, ang_mat: object, seed_map: object, tested: object, efalse: object) -> object:
        full_map: object = dict(seed_map)
        full_map.update(self._identify_remaining(b_vecs, ang_mat, full_map))
        obs_arr: object = asarray([sel[k] for k in full_map], dtype=int32)
        cat_arr: object = asarray(list(full_map.values()), dtype=int32)
        return IdResult(obs_arr, cat_arr, True, tested, efalse)

    def identify(self, vectors: object, flux: object=None) -> object:
        vecs: object = asarray(vectors, dtype=float64)
        total_v: object = int(len(vecs))
        if total_v < 3:
            return _empty_id_result(0)
        rank: object = arange(total_v) if flux is None else argsort(-asarray(flux))
        sel: object = rank[:min(total_v, self.max_stars)]
        b_sub: object = vecs[sel]
        ang_mat: object = arccos(clip(b_sub @ b_sub.T, -1.0, 1.0))
        n_sub: object = int(len(sel))
        tested: object = 0
        for i, j, k, r in _iter_pyramid_indices(n_sub):
            tested += 1
            if tested > self.cutoff:
                return _empty_id_result(0)
            pyr_hit: object = self._try_pyramid(b_sub, ang_mat, i, j, k, r)
            if pyr_hit is not None:
                ci, cj, ck, cr, ef = pyr_hit
                return self._pack_solution(sel, b_sub, ang_mat, {i: ci, j: cj, k: ck, r: cr}, tested, ef)
        for i, j, k in _iter_triangle_indices(n_sub):
            tested += 1
            if tested > self.cutoff:
                return _empty_id_result(0)
            tri_hit: object = self._try_triangle(b_sub, ang_mat, i, j, k)
            if tri_hit is not None:
                ci, cj, ck, ef = tri_hit
                sol: object = self._pack_solution(sel, b_sub, ang_mat, {i: ci, j: cj, k: ck}, tested, ef)
                if len(sol.obs_idx) >= 3:
                    return sol
        return _empty_id_result(tested)

    def _false_gate(self, bi: object, bj: object, bk: object, theta_ij: object) -> object:
        si, sj, sk = _inner_sines(bi, bj, bk)
        denom: object = max(sk * max(si, sj, sk), 1e-12)
        efalse: object = float(self._econst * sin(theta_ij) / denom)
        return None if efalse > self.p_max else efalse

    def _query_adj(self, theta_val: object) -> object:
        raw_pairs: object = self.kvector.query(float(theta_val), self._tol(theta_val))
        return _pair_map(raw_pairs) if len(raw_pairs) else None

    def _triangle_matches(self, b: object, ang: object, i: object, j: object, k: object) -> object:
        if self._false_gate(b[i], b[j], b[k], float(ang[i, j])) is None:
            return None
        obs_hand: object = _chirality(b[i], b[j], b[k])
        if obs_hand == 0:
            return None
        m_ij: object = self._query_adj(ang[i, j])
        m_ik: object = self._query_adj(ang[i, k])
        m_jk: object = self._query_adj(ang[j, k])
        if m_ij is None or m_ik is None or m_jk is None:
            return None
        cat_vecs: object = self.catalog.vectors
        triplets: object = []
        for ci, js in m_ij.items():
            ik_set: object = m_ik.get(ci)
            if not ik_set:
                continue
            for cj in js:
                jk_set: object = m_jk.get(cj)
                if not jk_set:
                    continue
                for ck in ik_set & jk_set:
                    if ck != ci and ck != cj:
                        if _chirality(cat_vecs[ci], cat_vecs[cj], cat_vecs[ck]) == obs_hand:
                            triplets.append((ci, cj, ck))
        return triplets

    def _try_triangle(self, b: object, ang: object, i: object, j: object, k: object) -> object:
        triplets: object = self._triangle_matches(b, ang, i, j, k)
        if not triplets or len({tuple(sorted(t)) for t in triplets}) != 1:
            return None
        ci, cj, ck = triplets[0]
        return (ci, cj, ck, self._false_gate(b[i], b[j], b[k], float(ang[i, j])))

    def _try_pyramid(self, b: object, ang: object, i: object, j: object, k: object, r: object) -> object:
        efalse: object = self._false_gate(b[i], b[j], b[k], float(ang[i, j]))
        if efalse is None:
            return None
        triplets: object = self._triangle_matches(b, ang, i, j, k)
        if not triplets:
            return None
        dedup_tris: object = {}
        for tri in triplets:
            dedup_tris.setdefault(tuple(sorted(tri)), tri)
        m_ir: object = self._query_adj(ang[i, r]) or {}
        m_jr: object = self._query_adj(ang[j, r]) or {}
        m_kr: object = self._query_adj(ang[k, r]) or {}
        confirmed: object = []
        for ci, cj, ck in dedup_tris.values():
            common_r: object = (m_ir.get(ci, set()) & m_jr.get(cj, set()) & m_kr.get(ck, set())) - {ci, cj, ck}
            if len(common_r) == 1:
                confirmed.append((ci, cj, ck, next(iter(common_r))))
        if len({tuple(sorted(q)) for q in confirmed}) != 1:
            return None
        ci, cj, ck, cr = confirmed[0]
        return (ci, cj, ck, cr, efalse)

    def identify_wide(self, vectors: object, flux: object, camera: object, *, vote_px: object=8.0, inlier_px: object=6.0) -> object:
        """Wide-tolerance attitude hypothesis voting from the tightest observed star pair."""
        vecs: object = asarray(vectors, dtype=float64)
        total_v: object = int(len(vecs))
        if total_v < 4:
            return _empty_id_result(0)
        rank: object = (arange(total_v) if flux is None else argsort(-asarray(flux, dtype=float64)))[:min(total_v, self.max_stars)]
        obs_sub: object = vecs[rank]
        m_sub: object = int(len(obs_sub))
        ang_mat: object = arccos(clip(obs_sub @ obs_sub.T, -1.0, 1.0))
        fill_diagonal(ang_mat, inf)
        base_tol: object = max(self.tol_rad, float(vote_px) * float(camera.ifov_rad))
        min_sep: object = float(radians(0.5))
        max_sep: object = float(self.kvector.theta_max)
        seed_pair: object = None
        for flat_i in argsort(ang_mat, axis=None):
            row_i, col_j = divmod(int(flat_i), m_sub)
            if col_j <= row_i:
                continue
            sep: object = float(ang_mat[row_i, col_j])
            if min_sep <= sep <= max_sep:
                cands: object = self.kvector.query(sep, max(base_tol, self._tol(sep)))
                if 0 < len(cands) <= 15000:
                    seed_pair: object = (row_i, col_j, cands)
                    break
        if seed_pair is None:
            return _empty_id_result(0)
        row_i, col_j, cands = seed_pair
        p_left, p_right = (cands[:, 0].astype(int32), cands[:, 1].astype(int32))
        cat_a: object = concatenate((p_left, p_right))
        cat_b: object = concatenate((p_right, p_left))
        cat_vecs: object = self.catalog.vectors
        rot_bank: object = _attitudes_from_pair(obs_sub[row_i], obs_sub[col_j], cat_vecs[cat_a], cat_vecs[cat_b])
        obs_uv: object = camera.project(obs_sub)[0]
        loose_c, tight_c, avg_d = _inlier_stats(rot_bank, cat_vecs, obs_uv, camera, inlier_px, min(3.0, inlier_px))
        order_idx: object = lexsort((avg_d, -loose_c, -tight_c))
        win_idx: object = int(order_idx[0])
        run_idx: object = int(order_idx[1]) if len(order_idx) > 1 else win_idx
        if int(tight_c[win_idx]) < 4 or int(loose_c[win_idx]) < 4:
            return _empty_id_result(0)
        if int(tight_c[win_idx]) == int(tight_c[run_idx]) and int(loose_c[win_idx]) == int(loose_c[run_idx]):
            return _empty_id_result(0)
        cam_all: object = einsum('ij,kj->ik', cat_vecs, rot_bank[win_idx])
        cx_v, cy_v, cz_v = cam_all.T
        front_mask: object = cz_v > 0.0
        inv_cz: object = 1.0 / maximum(cz_v, 1e-12)
        proj_u: object = camera.fx * (cx_v * inv_cz) + camera.cx
        proj_v: object = camera.fy * (cy_v * inv_cz) + camera.cy
        claimed_cat: object = set()
        matched_obs, matched_cat = ([], [])
        for loc_i, (u_pt, v_pt) in enumerate(obs_uv):
            d_vec: object = where(front_mask, hypot(proj_u - u_pt, proj_v - v_pt), inf)
            best_c: object = int(argmin(d_vec))
            if isfinite(d_vec[best_c]) and d_vec[best_c] <= inlier_px and (best_c not in claimed_cat):
                claimed_cat.add(best_c)
                matched_obs.append(int(rank[loc_i]))
                matched_cat.append(best_c)
        if len(matched_obs) < 3:
            return _empty_id_result(0)
        return IdResult(obs_idx=asarray(matched_obs, dtype=int32), cat_idx=asarray(matched_cat, dtype=int32), success=True, n_pyramids_tested=int(len(rot_bank)), expected_false=0.0)

    def _identify_remaining(self, b: object, ang: object, mapping: object) -> object:
        added: object = {}
        anchor_obs: object = list(mapping.keys())[:3]
        if not anchor_obs:
            return added
        taken: object = set(mapping.values())
        for m_idx in range(len(b)):
            if m_idx in mapping:
                continue
            cand_sets: object = []
            for o_idx in anchor_obs:
                sep: object = float(ang[min(m_idx, o_idx), max(m_idx, o_idx)])
                adj: object = self._query_adj(sep) or {}
                cand_sets.append(adj.get(mapping[o_idx], set()))
            common: object = set.intersection(*cand_sets) - taken - set(added.values())
            if len(common) == 1:
                added[m_idx] = next(iter(common))
        return added
