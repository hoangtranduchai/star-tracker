"""CCSDS-inspired 32-byte binary telemetry framing with CRC-16-CCITT integrity guard.

Designed for CubeSat OBC / ADCS serial interface simulation (PC/ARM64 software validation,
NASA TRL 3-4; NOT flight-qualified hardware). Protects the 16-byte J2000 quaternion
against Single-Event Upset (SEU) bit-flips and bus corruption.

Wire layout (32 bytes, big-endian network order):
  [0..3]   uint32  CCSDS Attached Sync Marker (0x1ACFFC1D)
  [4..5]   uint16  Sequence counter (mod 65536)
  [6]      uint8   Status bitflags:
                     bit 0 (0x01): SOLVED
                     bit 1 (0x02): CNN_USED
                     bit 2 (0x04): AUTO_ESCALATED
                     bit 3 (0x08): FALLBACK_USED
  [7]      uint8   Reject code enum (0 = NONE / SOLVED)
  [8..23]  4x f32  J2000 quaternion [w, x, y, z] (or 16x 0x00 when LOST)
  [24..25] uint16  Valid inlier pair count
  [26..27] uint16  Post-fit RMS residual in centi-arcsec (0.01" units, clamped 0..65535)
  [28..29] uint16  Total pipeline latency in ms (clamped 0..65535)
  [30..31] uint16  CRC-16-CCITT (poly=0x1021, init=0xFFFF) over bytes [0..29]
"""
from __future__ import annotations

import math
from struct import pack, unpack
from typing import Any

from .quaternion import normalize

SYNC_WORD: int = 0x1ACFFC1D
FRAME_BYTES: int = 32

FLAG_SOLVED: int = 0x01
FLAG_CNN_USED: int = 0x02
FLAG_AUTO_ESCALATED: int = 0x04
FLAG_FALLBACK_USED: int = 0x08

REJECT_CODE_TO_ID: dict[str | None, int] = {
    None: 0,
    'INSUFFICIENT_DETECTIONS': 1,
    'IDENTIFICATION_FAILED': 2,
    'INSUFFICIENT_INLIER_PAIRS': 3,
    'COLLINEAR_DEGENERATE_GEOMETRY': 4,
    'EXCESSIVE_POSTFIT_RESIDUAL': 5,
    'LOW_FOV_CONSISTENCY': 6,
    'WAHBA_SOLVER_ERROR': 7,
}
ID_TO_REJECT_CODE: dict[int, str | None] = {v: k for k, v in REJECT_CODE_TO_ID.items()}


def crc16_ccitt(data: bytes) -> int:
    """Compute standard CRC-16-CCITT (False / CCSDS 0x1021, init 0xFFFF)."""
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def pack_telemetry_frame(result: Any, *, seq_id: int = 0) -> bytes:
    """Serialize a `TrackerResult` into a 32-byte CRC-16-CCITT protected frame."""
    is_solved = bool(getattr(result, 'success', False)) and getattr(result, 'q', None) is not None
    qual = getattr(result, 'quality', None) or {}
    mstats = getattr(result, 'match_stats', None) or {}
    timing = getattr(result, 'timing_ms', None) or {}

    flags = 0
    if is_solved:
        flags |= FLAG_SOLVED
    det_name = str(qual.get('centroid_detector') or qual.get('auto_router_selected') or '').lower()
    if 'cnn' in det_name:
        flags |= FLAG_CNN_USED
    if qual.get('auto_router_used') and qual.get('auto_router_selected') == 'cnn':
        flags |= FLAG_AUTO_ESCALATED
    if qual.get('centroid_fallback'):
        flags |= FLAG_FALLBACK_USED

    rej_code = getattr(result, 'reject_code', None)
    rej_id = 0 if is_solved else REJECT_CODE_TO_ID.get(str(rej_code) if rej_code else None, 255)

    if is_solved:
        w, x, y, z = normalize(result.q)
        q_vals = (float(w), float(x), float(y), float(z))
    else:
        q_vals = (0.0, 0.0, 0.0, 0.0)

    n_valid = int(mstats.get('n_valid_pairs', qual.get('n_matched', 0)) or 0)
    n_valid = max(0, min(65535, n_valid))

    rms_arcsec = mstats.get('rms_residual_arcsec', qual.get('rms_residual_arcsec', 0.0))
    rms_c = int(round(float(rms_arcsec) * 100.0)) if rms_arcsec is not None and math.isfinite(float(rms_arcsec)) else 0
    rms_c = max(0, min(65535, rms_c))

    lat_ms = timing.get('total', 0.0)
    lat_u16 = int(round(float(lat_ms))) if lat_ms is not None and math.isfinite(float(lat_ms)) else 0
    lat_u16 = max(0, min(65535, lat_u16))

    header_body = pack(
        '>IHBB4fHHH',
        SYNC_WORD,
        int(seq_id) & 0xFFFF,
        flags & 0xFF,
        rej_id & 0xFF,
        q_vals[0],
        q_vals[1],
        q_vals[2],
        q_vals[3],
        n_valid,
        rms_c,
        lat_u16,
    )
    crc = crc16_ccitt(header_body)
    return header_body + pack('>H', crc)


def unpack_telemetry_frame(raw: bytes) -> dict[str, Any]:
    """Decode and validate a 32-byte telemetry frame against SEU/bus corruption."""
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != FRAME_BYTES:
        return {'valid': False, 'error': 'INVALID_LENGTH'}

    payload_part = bytes(raw[:30])
    rx_crc = unpack('>H', raw[30:32])[0]
    calc_crc = crc16_ccitt(payload_part)
    if rx_crc != calc_crc:
        return {
            'valid': False,
            'error': 'CRC16_MISMATCH',
            'rx_crc': f'0x{rx_crc:04X}',
            'calc_crc': f'0x{calc_crc:04X}',
        }

    sync, seq_id, flags, rej_id, qw, qx, qy, qz, n_valid, rms_c, lat_u16 = unpack('>IHBB4fHHH', payload_part)
    if sync != SYNC_WORD:
        return {'valid': False, 'error': 'BAD_SYNC_WORD', 'sync': f'0x{sync:08X}'}

    q_list = [float(qw), float(qx), float(qy), float(qz)]
    if any(not math.isfinite(v) for v in q_list):
        return {'valid': False, 'error': 'NON_FINITE_QUATERNION'}

    is_solved = bool(flags & FLAG_SOLVED)
    q_norm = math.sqrt(sum(v * v for v in q_list))
    if is_solved:
        if abs(q_norm - 1.0) > 1e-3:
            return {'valid': False, 'error': 'INVALID_UNIT_QUATERNION', 'norm': q_norm}
    else:
        if q_norm > 0.0:
            return {'valid': False, 'error': 'NON_ZERO_LOST_QUATERNION', 'norm': q_norm}

    return {
        'valid': True,
        'error': None,
        'seq_id': int(seq_id),
        'status': 'SOLVED' if is_solved else 'LOST',
        'flags': int(flags),
        'cnn_used': bool(flags & FLAG_CNN_USED),
        'auto_escalated': bool(flags & FLAG_AUTO_ESCALATED),
        'fallback_used': bool(flags & FLAG_FALLBACK_USED),
        'reject_code': ID_TO_REJECT_CODE.get(int(rej_id), f'UNKNOWN_{rej_id}'),
        'q': q_list if is_solved else None,
        'n_valid_pairs': int(n_valid),
        'rms_residual_arcsec': float(rms_c) / 100.0,
        'latency_ms': int(lat_u16),
        'crc16_hex': f'{rx_crc:04X}',
    }
