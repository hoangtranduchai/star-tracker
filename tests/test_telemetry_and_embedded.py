"""Unit tests for CCSDS-inspired CRC-16-CCITT telemetry framing and SEU bit-flip rejection."""
from __future__ import annotations

import numpy as np

from src.pipeline import TrackerResult
from src.telemetry import (
    FRAME_BYTES,
    SYNC_WORD,
    crc16_ccitt,
    pack_telemetry_frame,
    unpack_telemetry_frame,
)


def _dummy_solved_result() -> TrackerResult:
    q = np.array([0.5, -0.5, 0.5, 0.5], dtype=np.float64)
    return TrackerResult(
        success=True,
        q=q,
        a=np.eye(3),
        centroids=None,
        ident=None,
        residuals_arcsec=np.array([1.2, 1.5, 0.9, 1.1]),
        cov_rad2=None,
        timing_ms={'total': 84.3},
        quality={'centroid_detector': 'classical', 'auto_router_used': True, 'auto_router_selected': 'classical'},
        status='SOLVED',
        reject_code=None,
        match_stats={'n_valid_pairs': 18, 'rms_residual_arcsec': 1.24},
    )


def _dummy_lost_result() -> TrackerResult:
    return TrackerResult(
        success=False,
        q=None,
        a=None,
        centroids=None,
        ident=None,
        residuals_arcsec=None,
        cov_rad2=None,
        timing_ms={'total': 41.0},
        quality={'centroid_detector': 'classical'},
        status='LOST',
        reject_code='INSUFFICIENT_INLIER_PAIRS',
        match_stats={'n_valid_pairs': 2, 'rms_residual_arcsec': None},
    )


def test_crc16_ccitt_known_vector() -> None:
    # Standard CRC-16/CCITT-FALSE check value for ASCII "123456789" is 0x29B1
    assert crc16_ccitt(b'123456789') == 0x29B1


def test_telemetry_roundtrip_solved_and_lost() -> None:
    res_ok = _dummy_solved_result()
    raw_ok = pack_telemetry_frame(res_ok, seq_id=77)
    assert len(raw_ok) == FRAME_BYTES
    assert raw_ok[:4] == SYNC_WORD.to_bytes(4, 'big')

    dec_ok = unpack_telemetry_frame(raw_ok)
    assert dec_ok['valid'] is True
    assert dec_ok['status'] == 'SOLVED'
    assert dec_ok['seq_id'] == 77
    assert dec_ok['n_valid_pairs'] == 18
    assert abs(dec_ok['rms_residual_arcsec'] - 1.24) < 0.02
    assert dec_ok['reject_code'] is None
    assert np.allclose(dec_ok['q'], [0.5, -0.5, 0.5, 0.5], atol=1e-6)

    res_lost = _dummy_lost_result()
    raw_lost = res_lost.to_telemetry_frame(seq_id=78)
    assert len(raw_lost) == FRAME_BYTES
    assert raw_lost[8:24] == b'\x00' * 16
    dec_lost = unpack_telemetry_frame(raw_lost)
    assert dec_lost['valid'] is True
    assert dec_lost['status'] == 'LOST'
    assert dec_lost['q'] is None
    assert dec_lost['reject_code'] == 'INSUFFICIENT_INLIER_PAIRS'


def test_seu_exhaustive_single_bit_flips_100pct_detected() -> None:
    raw = pack_telemetry_frame(_dummy_solved_result(), seq_id=101)
    for bit_idx in range(FRAME_BYTES * 8):
        corrupted = bytearray(raw)
        corrupted[bit_idx // 8] ^= 1 << (bit_idx % 8)
        dec = unpack_telemetry_frame(bytes(corrupted))
        assert dec['valid'] is False, f'SEU 1-bit flip at bit {bit_idx} was not detected!'
