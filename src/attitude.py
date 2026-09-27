"""
Wahba attitude: SVD (Kabsch) and QUEST. Quaternions are scalar-first.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .quaternion import ARCSEC_PER_RAD, from_dcm, normalize, to_dcm


class WahbaSolver:
    """Solves Wahba's problem: min sum a_i ||b_i - A r_i||^2."""

    @staticmethod
    def _weights(n: int, weights: Optional[np.ndarray]) -> np.ndarray:
        if weights is None:
            return np.ones(n, dtype=np.float64) / n
        w = np.asarray(weights, dtype=np.float64).reshape(n)
        s = np.sum(w)
        if s <= 0:
            raise ValueError("Weights must sum to a positive value.")
        return w / s

    @staticmethod
    def _profile_matrix(obs: np.ndarray, ref: np.ndarray, w: np.ndarray) -> np.ndarray:
        # B = sum w_i b_i r_i^T
        return (w[:, None] * obs).T @ ref

    @staticmethod
    def solve_svd(
        obs_vectors: np.ndarray,
        cat_vectors: np.ndarray,
        weights: Optional[np.ndarray] = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        obs = np.asarray(obs_vectors, dtype=np.float64)
        ref = np.asarray(cat_vectors, dtype=np.float64)
        n = len(obs)
        if n < 3:
            raise ValueError(f"At least 3 vector pairs required, got {n}.")
        w = WahbaSolver._weights(n, weights)
        b_mat = WahbaSolver._profile_matrix(obs, ref, w)
        u, _s, vt = np.linalg.svd(b_mat)
        d = np.linalg.det(u) * np.linalg.det(vt)
        a_opt = u @ np.diag([1.0, 1.0, d]) @ vt
        return from_dcm(a_opt), a_opt

    @staticmethod
    def solve_quest(
        obs_vectors: np.ndarray,
        cat_vectors: np.ndarray,
        weights: Optional[np.ndarray] = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Davenport q-method (QUEST-equivalent). Falls back to SVD if needed."""
        obs = np.asarray(obs_vectors, dtype=np.float64)
        ref = np.asarray(cat_vectors, dtype=np.float64)
        n = len(obs)
        if n < 3:
            raise ValueError(f"At least 3 vector pairs required, got {n}.")
        w = WahbaSolver._weights(n, weights)
        b_mat = WahbaSolver._profile_matrix(obs, ref, w)
        s = b_mat + b_mat.T
        sigma = float(np.trace(b_mat))
        z = np.array(
            [
                b_mat[1, 2] - b_mat[2, 1],
                b_mat[2, 0] - b_mat[0, 2],
                b_mat[0, 1] - b_mat[1, 0],
            ]
        )
        k = np.zeros((4, 4), dtype=np.float64)
        k[0, 0] = sigma
        k[0, 1:] = z
        k[1:, 0] = z
        k[1:, 1:] = s - sigma * np.eye(3)
        evals, evecs = np.linalg.eigh(k)
        q = normalize(evecs[:, int(np.argmax(evals))])
        a = to_dcm(q)
        # If the eigen-convention produced A^T, the Wahba loss would be worse than SVD.
        q_svd, a_svd = WahbaSolver.solve_svd(obs, ref, w)
        loss = lambda aa: float(np.sum((obs - (aa @ ref.T).T) ** 2))
        if loss(a) > loss(a_svd) * 1.01:
            return q_svd, a_svd
        return q, a

    @staticmethod
    def residuals_arcsec(obs_vectors: np.ndarray, cat_vectors: np.ndarray, a: np.ndarray) -> np.ndarray:
        pred = (a @ np.asarray(cat_vectors, dtype=np.float64).T).T
        obs = np.asarray(obs_vectors, dtype=np.float64)
        dots = np.clip(np.sum(obs * pred, axis=1), -1.0, 1.0)
        return np.arccos(dots) * ARCSEC_PER_RAD

    @staticmethod
    def covariance_rad2(obs_vectors: np.ndarray, sigma_rad: np.ndarray) -> np.ndarray:
        """Shuster attitude covariance P_θθ (3x3, rad^2) in the camera frame."""
        b = np.asarray(obs_vectors, dtype=np.float64)
        sig = np.asarray(sigma_rad, dtype=np.float64).reshape(len(b))
        inv_var = 1.0 / np.maximum(sig * sig, 1e-30)
        inv_tot = float(np.sum(inv_var))
        sigma_tot2 = 1.0 / inv_tot
        acc = np.zeros((3, 3), dtype=np.float64)
        for bi, iv in zip(b, inv_var):
            a_i = sigma_tot2 * iv  # = (1/σ_i^2) / sum(1/σ_j^2)
            acc += a_i * (np.eye(3) - np.outer(bi, bi))
        p = sigma_tot2 * np.linalg.pinv(acc)
        return p

    @staticmethod
    def compute_angular_error_arcsec(q_est: np.ndarray, q_gt: np.ndarray) -> float:
        from .quaternion import angular_error_arcsec

        return angular_error_arcsec(q_est, q_gt)
