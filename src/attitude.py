"""Wahba attitude estimation via Markley SVD and Davenport q-method (QUEST)."""
from numpy import arccos, argmax, asarray, clip, diag, einsum, eye, float64, full, maximum, outer, sum as npsum, zeros
from numpy.linalg import det, eigh, pinv, svd
from .quaternion import ARCSEC_PER_RAD, angular_error_arcsec, from_dcm, normalize, to_dcm

def _norm_weights(count: object, weights: object) -> object:
    if weights is None:
        return full(count, 1.0 / float(count), dtype=float64)
    w_vec: object = asarray(weights, dtype=float64).ravel()
    total: object = float(npsum(w_vec)) if w_vec.size == count else -1.0
    if not total > 0.0:
        raise ValueError('Weights must sum to a positive value.')
    return w_vec * (1.0 / total)

def _prepare_wahba_inputs(obs_vectors: object, cat_vectors: object, weights: object) -> object:
    obs_mat: object = asarray(obs_vectors, dtype=float64)
    ref_mat: object = asarray(cat_vectors, dtype=float64)
    count: object = int(obs_mat.shape[0])
    if not count >= 3:
        raise ValueError(f'At least 3 vector pairs required, got {count}.')
    w_vec: object = _norm_weights(count, weights)
    profile: object = einsum('i,ij,ik->jk', w_vec, obs_mat, ref_mat)
    return (obs_mat, ref_mat, w_vec, profile)

class WahbaSolver:
    """Solves Wahba's weighted least-squares attitude problem."""
    _weights = staticmethod(_norm_weights)

    @staticmethod
    def _profile_matrix(obs: object, ref: object, w: object) -> object:
        return einsum('i,ij,ik->jk', asarray(w, dtype=float64), asarray(obs, dtype=float64), asarray(ref, dtype=float64))

    @staticmethod
    def solve_svd(obs_vectors: object, cat_vectors: object, weights: object=None) -> object:
        _, _, _, b_mat = _prepare_wahba_inputs(obs_vectors, cat_vectors, weights)
        u_orth, _, vt_orth = svd(b_mat)
        handed: object = float(det(u_orth) * det(vt_orth))
        dcm: object = u_orth * asarray([1.0, 1.0, handed], dtype=float64) @ vt_orth
        return (from_dcm(dcm), dcm)

    @staticmethod
    def solve_quest(obs_vectors: object, cat_vectors: object, weights: object=None) -> object:
        """Davenport q-method eigensolver with automatic SVD loss safeguard."""
        obs_m, ref_m, w_vec, b_mat = _prepare_wahba_inputs(obs_vectors, cat_vectors, weights)
        (b00, b01, b02), (b10, b11, b12), (b20, b21, b22) = b_mat
        sig: object = float(b00 + b11 + b22)
        z0, z1, z2 = (float(b12 - b21), float(b20 - b02), float(b01 - b10))
        sym_block: object = b_mat + b_mat.T - eye(3, dtype=float64) * sig
        (s00, s01, s02), (s10, s11, s12), (s20, s21, s22) = sym_block
        k_mat: object = asarray([[sig, z0, z1, z2], [z0, s00, s01, s02], [z1, s10, s11, s12], [z2, s20, s21, s22]], dtype=float64)
        eig_vals, eig_vecs = eigh(k_mat)
        quat: object = normalize(eig_vecs[:, int(argmax(eig_vals))])
        dcm: object = to_dcm(quat)
        q_svd, dcm_svd = WahbaSolver.solve_svd(obs_m, ref_m, w_vec)
        err_quest: object = float(npsum((obs_m - einsum('ij,kj->ik', ref_m, dcm)) ** 2))
        err_svd: object = float(npsum((obs_m - einsum('ij,kj->ik', ref_m, dcm_svd)) ** 2))
        return (q_svd, dcm_svd) if err_quest > err_svd * 1.01 else (quat, dcm)

    @staticmethod
    def residuals_arcsec(obs_vectors: object, cat_vectors: object, a: object) -> object:
        obs_m: object = asarray(obs_vectors, dtype=float64)
        ref_m: object = asarray(cat_vectors, dtype=float64)
        rot_m: object = asarray(a, dtype=float64)
        rotated: object = einsum('ij,kj->ik', ref_m, rot_m)
        cos_angs: object = clip(einsum('ij,ij->i', obs_m, rotated), -1.0, 1.0)
        return arccos(cos_angs) * ARCSEC_PER_RAD

    @staticmethod
    def covariance_rad2(obs_vectors: object, sigma_rad: object) -> object:
        """Shuster 3x3 attitude error covariance matrix in camera coordinates (rad^2)."""
        b_mat: object = asarray(obs_vectors, dtype=float64)
        sig_vec: object = asarray(sigma_rad, dtype=float64).ravel()
        weights_inv: object = 1.0 / maximum(sig_vec * sig_vec, 1e-30)
        sigma_tot_sq: object = 1.0 / float(npsum(weights_inv))
        rel_w: object = weights_inv * sigma_tot_sq
        info_mat: object = eye(3, dtype=float64) * float(npsum(rel_w)) - einsum('i,ij,ik->jk', rel_w, b_mat, b_mat)
        return sigma_tot_sq * pinv(info_mat)

    @staticmethod
    def compute_angular_error_arcsec(q_est: object, q_gt: object) -> object:
        return angular_error_arcsec(q_est, q_gt)
