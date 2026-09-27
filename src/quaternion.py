"""
Scalar-first unit quaternions q = [q0, q1, q2, q3]^T (q0 is the scalar part).

Attitude matrix A = R_cam←J2000 satisfies b_cam = A @ r_J2000.
"""

from __future__ import annotations

import re

import numpy as np

ARCSEC_PER_RAD = 180.0 * 3600.0 / np.pi  # 206264.806247...


def normalize(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=np.float64).reshape(4)
    n = np.linalg.norm(q)
    if n == 0.0:
        raise ValueError("Zero quaternion cannot be normalized.")
    q = q / n
    if q[0] < 0.0:
        q = -q
    return q


def multiply(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Hamilton product p ⊗ q (apply q first, then p, for vector rotation via A(p⊗q))."""
    p0, p1, p2, p3 = np.asarray(p, dtype=np.float64).reshape(4)
    q0, q1, q2, q3 = np.asarray(q, dtype=np.float64).reshape(4)
    return np.array(
        [
            p0 * q0 - p1 * q1 - p2 * q2 - p3 * q3,
            p0 * q1 + p1 * q0 + p2 * q3 - p3 * q2,
            p0 * q2 - p1 * q3 + p2 * q0 + p3 * q1,
            p0 * q3 + p1 * q2 - p2 * q1 + p3 * q0,
        ],
        dtype=np.float64,
    )


def conjugate(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=np.float64).reshape(4)
    return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float64)


def inverse(q: np.ndarray) -> np.ndarray:
    return conjugate(normalize(q))


def to_dcm(q: np.ndarray) -> np.ndarray:
    """A such that b = A @ r, from the plan formula with [qv]× the standard skew matrix."""
    q0, q1, q2, q3 = normalize(q)
    qv = np.array([q1, q2, q3])
    i3 = np.eye(3)
    skew = np.array(
        [
            [0.0, -q3, q2],
            [q3, 0.0, -q1],
            [-q2, q1, 0.0],
        ]
    )
    # Hamiltonian active rotation (matches scipy Rotation.as_matrix / spacecraft A with b = A r).
    return (q0 * q0 - qv @ qv) * i3 + 2.0 * np.outer(qv, qv) + 2.0 * q0 * skew


def from_dcm(a: np.ndarray) -> np.ndarray:
    """Shepperd conversion; returns scalar-first quaternion with q0 >= 0."""
    a = np.asarray(a, dtype=np.float64).reshape(3, 3)
    m00, m01, m02 = a[0, 0], a[0, 1], a[0, 2]
    m10, m11, m12 = a[1, 0], a[1, 1], a[1, 2]
    m20, m21, m22 = a[2, 0], a[2, 1], a[2, 2]
    trace = m00 + m11 + m22
    if trace > 0.0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (m21 - m12) * s
        y = (m02 - m20) * s
        z = (m10 - m01) * s
    elif m00 > m11 and m00 > m22:
        s = 2.0 * np.sqrt(1.0 + m00 - m11 - m22)
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = 2.0 * np.sqrt(1.0 + m11 - m00 - m22)
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = 2.0 * np.sqrt(1.0 + m22 - m00 - m11)
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s
    return normalize(np.array([w, x, y, z], dtype=np.float64))


def looking_at(r_j2000: np.ndarray) -> np.ndarray:
    """Quaternion with camera +Z along unit vector r (J2000). Roll: +X from celestial north × z."""
    z = np.asarray(r_j2000, dtype=np.float64).reshape(3)
    n = np.linalg.norm(z)
    if n <= 0:
        raise ValueError("looking_at requires a non-zero vector")
    z = z / n
    north = np.array([0.0, 0.0, 1.0])
    x = np.cross(north, z)
    if np.linalg.norm(x) < 1e-8:
        x = np.cross(np.array([1.0, 0.0, 0.0]), z)
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    y = y / np.linalg.norm(y)
    a = np.vstack((x, y, z))
    return from_dcm(a)


_RA_HMS = re.compile(r"[hH]")
_DEC_DMS = re.compile(r"[dD°º]")
_RADEC_HMS_PAIR = re.compile(
    r"(?P<ra>\d{1,2}(?:\.\d+)?\s*[hH].*?)\s*(?P<dec>[+\-]\s*\d{1,3}.*)\Z",
    re.DOTALL,
)
_RADEC_COLON_PAIR = re.compile(
    r"(?P<ra>\d{1,2}:\d{1,2}(?::\d+(?:\.\d+)?)?)\s+"
    r"(?P<dec>[+\-]\d{1,2}:\d{1,2}(?::\d+(?:\.\d+)?)?)\Z"
)


def _sexagesimal_nums(text: str) -> tuple[str, float, list[float]]:
    raw = str(text).strip().replace(",", ".")
    raw = raw.replace("\u00a0", " ").replace("−", "-").replace("–", "-")
    raw = (
        raw.replace("°", "d")
        .replace("º", "d")
        .replace("′", "'")
        .replace("’", "'")
        .replace("ʹ", "'")
        .replace("″", '"')
        .replace("“", '"')
        .replace("”", '"')
    )
    sign = -1.0 if re.match(r"^\s*-", raw) else 1.0
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", raw)]
    return raw, sign, nums


def split_radec_text(text: str) -> tuple[str, str] | None:
    """Split a Stellarium one-line paste into RA and Dec strings.

    Example: '18h 37m51.2s   +38°48'46.2\"'
    """
    t = str(text).replace("\u00a0", " ").replace("−", "-").replace("–", "-").strip()
    t = re.sub(r"[ \t]+", " ", t)
    m = _RADEC_HMS_PAIR.search(t)
    if m:
        return m.group("ra").strip(), m.group("dec").strip()
    m = _RADEC_COLON_PAIR.search(t)
    if m:
        return m.group("ra").strip(), m.group("dec").strip()
    return None


def parse_radec_pair(text, *, fmt: str = "auto") -> tuple[float, float]:
    """RA/Dec Stellarium one-line → degrees."""
    parts = split_radec_text("" if text is None else str(text))
    if not parts:
        raise ValueError(
            "Cần cả RA và Dec. Dán một dòng Stellarium, ví dụ: 18h 37m51.2s   +38°48'46.2\""
        )
    return parse_ra_deg(parts[0], fmt=fmt), parse_dec_deg(parts[1], fmt=fmt)


def _normalize_radec_fmt(fmt: str | None) -> str:
    key = str(fmt or "auto").strip().lower()
    if key in {"sexagesimal", "hms", "stellarium", "hms/dms"}:
        return "hms"
    if key in {"decimal", "deg", "degree", "degrees"}:
        return "decimal"
    if key in {"auto", "", "none"}:
        return "auto"
    raise ValueError("Định dạng RA/Dec phải là decimal (độ) hoặc sexagesimal (Stellarium)")


def _ra_from_hms(nums: list[float]) -> float:
    h, m, s = (nums + [0.0, 0.0, 0.0])[:3]
    if h < 0 or h >= 24 or m >= 60 or s >= 60:
        raise ValueError("RA giờ-phút-giây: giờ 0–23, phút/giây 0–59.9")
    return float(((h + m / 60.0 + s / 3600.0) * 15.0) % 360.0)


def parse_ra_deg(value, *, fmt: str = "auto") -> float:
    """RA → degrees.

    fmt=decimal: bare number is degrees 0–360.
    fmt=sexagesimal/hms: bare number is hours 0–24; also 18h 37m 51.2s.
    fmt=auto: markers/colon decide; bare number is degrees.
    Rejects glued Stellarium digits like 183751.2.
    """
    fmt = _normalize_radec_fmt(fmt)
    if value is None or (isinstance(value, str) and not str(value).strip()):
        raise ValueError("RA trống")
    if isinstance(value, str):
        pair = split_radec_text(value)
        if pair:
            value = pair[0]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        x = float(value)
        if fmt == "hms":
            if 0.0 <= x < 24.0:
                return float((x * 15.0) % 360.0)
            raise ValueError("Mode Stellarium: RA số trần là giờ 0–24, không phải 183751.2")
        if 0.0 <= x <= 360.0:
            return x % 360.0
        raise ValueError(
            "Mode độ: RA 0–360°. Stellarium hãy chọn mode h m s, dán 18h 37m 51.2s — không dán 183751.2"
        )
    raw, _sign, nums = _sexagesimal_nums(value)
    if not nums:
        raise ValueError("RA không đọc được. Ví dụ: 18h 37m 51.2s hoặc 279.234°")
    low = raw.lower()
    marked_hms = bool(_RA_HMS.search(low) or "hour" in low)
    colon = ":" in raw
    if fmt == "hms" or marked_hms or (colon and nums[0] < 24):
        if fmt == "hms" and not marked_hms and not colon and len(nums) == 1:
            h = nums[0]
            if 0.0 <= h < 24.0:
                return float((h * 15.0) % 360.0)
            raise ValueError("Mode Stellarium: RA số trần là giờ 0–24. Dán 18h 37m 51.2s")
        return _ra_from_hms(nums)
    if colon and nums[0] >= 24:
        d, m, s = (nums + [0.0, 0.0, 0.0])[:3]
        deg = d + m / 60.0 + s / 3600.0
        if not (0.0 <= deg <= 360.0):
            raise ValueError("RA độ phải 0–360")
        return float(deg % 360.0)
    if len(nums) == 1:
        deg = nums[0]
        if fmt == "hms":
            if 0.0 <= deg < 24.0:
                return float((deg * 15.0) % 360.0)
            raise ValueError("Mode Stellarium: RA số trần là giờ 0–24. Dán 18h 37m 51.2s, không dán 183751.2")
        if 0.0 <= deg <= 360.0:
            return float(deg % 360.0)
        raise ValueError(
            "RA số phải là độ 0–360. Dán 18h 37m 51.2s (mode Stellarium), không dán 183751.2"
        )
    raise ValueError("RA không đọc được. Chọn mode Stellarium rồi dán 18h 37m 51.2s")


def parse_dec_deg(value, *, fmt: str = "auto") -> float:
    """Dec → degrees. Decimal −90…+90 or Stellarium +38° 48' 46.2\". Rejects +384846.2."""
    fmt = _normalize_radec_fmt(fmt)
    if value is None or (isinstance(value, str) and not str(value).strip()):
        raise ValueError("Dec trống")
    if isinstance(value, str):
        pair = split_radec_text(value)
        if pair:
            value = pair[1]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        deg = float(value)
        if -90.0 <= deg <= 90.0:
            return deg
        raise ValueError(
            "Dec số phải là độ −90…+90. Stellarium dán +38° 48' 46.2″, không dán +384846.2"
        )
    raw, sign, nums = _sexagesimal_nums(value)
    if not nums:
        raise ValueError("Dec không đọc được. Ví dụ: +38° 48' 46.2″ hoặc +38.8128")
    low = raw.lower()
    dms = bool(_DEC_DMS.search(raw) or "'" in raw or '"' in raw or "deg" in low)
    colon = ":" in raw
    if dms or colon or len(nums) >= 2 or fmt == "hms":
        if fmt == "hms" and not dms and not colon and len(nums) == 1:
            deg = sign * nums[0]
            if -90.0 <= deg <= 90.0:
                return float(deg)
            raise ValueError("Dec số phải là độ −90…+90. Dán +38° 48' 46.2″, không dán +384846.2")
        d, m, s = (nums + [0.0, 0.0, 0.0])[:3]
        if m >= 60 or s >= 60:
            raise ValueError("Dec phút/giây phải 0–59.9")
        deg = sign * (d + m / 60.0 + s / 3600.0)
        if not (-90.0 <= deg <= 90.0):
            raise ValueError("Dec phải trong −90…+90 độ")
        return float(deg)
    deg = sign * nums[0]
    if -90.0 <= deg <= 90.0:
        return float(deg)
    raise ValueError(
        "Dec số phải là độ −90…+90. Dán +38° 48' 46.2″ (mode Stellarium), không dán +384846.2"
    )


def looking_at_ra_dec(ra_deg, dec_deg) -> np.ndarray:
    """Camera +Z along ICRS/J2000 RA/Dec. ra_deg/dec_deg may be sexagesimal strings."""
    ra = np.radians(parse_ra_deg(ra_deg))
    dec = np.radians(parse_dec_deg(dec_deg))
    r = np.array(
        [
            np.cos(dec) * np.cos(ra),
            np.cos(dec) * np.sin(ra),
            np.sin(dec),
        ],
        dtype=np.float64,
    )
    return looking_at(r)


def to_scipy_xyzw(q: np.ndarray) -> np.ndarray:
    q = normalize(q)
    return np.array([q[1], q[2], q[3], q[0]], dtype=np.float64)


def from_scipy_xyzw(xyzw: np.ndarray) -> np.ndarray:
    x, y, z, w = np.asarray(xyzw, dtype=np.float64).reshape(4)
    return normalize(np.array([w, x, y, z], dtype=np.float64))


def random_quaternion(rng: np.random.Generator | None = None) -> np.ndarray:
    """Uniform on SO(3) via Shoemake: four Gaussians, normalize."""
    if rng is None:
        rng = np.random.default_rng()
    return normalize(rng.normal(size=4))


def propagate(q: np.ndarray, omega_rad_s: np.ndarray, dt_s: float) -> np.ndarray:
    """q(t+dt) = q ⊗ Δq(ω dt) with ω in the camera/body frame (rad/s)."""
    omega = np.asarray(omega_rad_s, dtype=np.float64).reshape(3)
    speed = float(np.linalg.norm(omega))
    angle = speed * float(dt_s)
    if abs(angle) < 1e-18:
        return normalize(q)
    axis = omega / speed
    half = 0.5 * angle
    dq = np.array(
        [np.cos(half), axis[0] * np.sin(half), axis[1] * np.sin(half), axis[2] * np.sin(half)]
    )
    return normalize(multiply(q, dq))


def angular_error_arcsec(q_est: np.ndarray, q_gt: np.ndarray) -> float:
    q1 = normalize(q_est)
    q2 = normalize(q_gt)
    inner = float(np.clip(abs(np.dot(q1, q2)), 0.0, 1.0))
    return float(2.0 * np.arccos(inner) * ARCSEC_PER_RAD)


def axis_error_arcsec(q_est: np.ndarray, q_gt: np.ndarray) -> np.ndarray:
    """Small-angle camera-frame rotation vector 2*δq_v in arcseconds (x,y = cross, z = roll)."""
    dq = multiply(normalize(q_est), inverse(q_gt))
    if dq[0] < 0.0:
        dq = -dq
    return 2.0 * dq[1:4] * ARCSEC_PER_RAD


def boresight_ra_dec_deg(q: np.ndarray) -> tuple[float, float]:
    """J2000 RA/Dec of camera +Z (boresight). RA in [0, 360) deg, Dec in [-90, 90] deg.

    This is where the camera looks on the celestial sphere, not satellite lat/lon
    and not a constellation name.
    """
    a = to_dcm(q)
    r = a.T @ np.array([0.0, 0.0, 1.0])
    ra = float(np.degrees(np.mod(np.arctan2(r[1], r[0]), 2.0 * np.pi)))
    dec = float(np.degrees(np.arcsin(np.clip(r[2], -1.0, 1.0))))
    return ra, dec


def format_ra_hms(ra_deg: float) -> str:
    hours = (float(ra_deg) % 360.0) / 15.0
    h = int(hours)
    m_float = (hours - h) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    return f"{h:02d}h {m:02d}m {s:05.2f}s"


def format_dec_dms(dec_deg: float) -> str:
    sign = "+" if dec_deg >= 0 else "-"
    x = abs(float(dec_deg))
    d = int(x)
    m_float = (x - d) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    return f"{sign}{d:02d}d {m:02d}m {s:04.1f}s"


def format_dec_stellarium(dec_deg: float) -> str:
    sign = "+" if dec_deg >= 0 else "-"
    x = abs(float(dec_deg))
    d = int(x)
    m_float = (x - d) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    return f"{sign}{d:02d}° {m:02d}' {s:04.1f}\""


def format_ra_both(ra_deg: float) -> str:
    return f"{(float(ra_deg) % 360.0):.5f}°  ({format_ra_hms(ra_deg)})"


def format_dec_both(dec_deg: float) -> str:
    return f"{float(dec_deg):+.5f}°  ({format_dec_stellarium(dec_deg)})"
