"""Scalar-first unit quaternion math (`q = [q0, q1, q2, q3]`) and celestial coordinate parsers."""
from re import DOTALL, compile as re_compile, findall, match as re_match, sub as re_sub
from numpy import arccos, arcsin, arctan2, argmax, asarray, clip, cos, cross, degrees, dot, eye, float64, mod, outer, pi, radians, sin, sqrt, vstack
from numpy.linalg import norm
from numpy.random import default_rng
ARCSEC_PER_RAD = 648000.0 / float(pi)

def normalize(q: object) -> object:
    """Normalize a 4-vector to a scalar-first unit quaternion with `q0 >= 0`."""
    vec: object = asarray(q, dtype=float64).ravel()
    mag: object = float(norm(vec))
    if not mag > 0.0:
        raise ValueError('Zero quaternion cannot be normalized.')
    scale: object = (-1.0 if float(vec[0]) < 0.0 else 1.0) / mag
    return vec * scale

def multiply(p: object, q: object) -> object:
    """Hamilton product `p (x) q` for scalar-first quaternions."""
    p0, p1, p2, p3 = asarray(p, dtype=float64).ravel()
    q0, q1, q2, q3 = asarray(q, dtype=float64).ravel()
    pv: object = asarray([p1, p2, p3], dtype=float64)
    qv: object = asarray([q1, q2, q3], dtype=float64)
    w_part: object = float(p0 * q0 - dot(pv, qv))
    vx, vy, vz = p0 * qv + q0 * pv + cross(pv, qv)
    return asarray([w_part, vx, vy, vz], dtype=float64)

def conjugate(q: object) -> object:
    w, x, y, z = asarray(q, dtype=float64).ravel()
    return asarray([w, -x, -y, -z], dtype=float64)

def inverse(q: object) -> object:
    return conjugate(normalize(q))

def to_dcm(q: object) -> object:
    """Convert scalar-first unit quaternion to 3x3 direction cosine matrix `A` (`b = A @ r`)."""
    q0, q1, q2, q3 = normalize(q)
    qv: object = asarray([q1, q2, q3], dtype=float64)
    skew: object = asarray([[0.0, -q3, q2], [q3, 0.0, -q1], [-q2, q1, 0.0]], dtype=float64)
    diag_term: object = float(q0 * q0 - dot(qv, qv))
    return eye(3, dtype=float64) * diag_term + 2.0 * (outer(qv, qv) + q0 * skew)

def from_dcm(a: object) -> object:
    """Shepperd method converting a 3x3 direction cosine matrix to scalar-first quaternion."""
    (m00, m01, m02), (m10, m11, m12), (m20, m21, m22) = asarray(a, dtype=float64).reshape(3, 3)
    cands: object = asarray([1.0 + m00 + m11 + m22, 1.0 + m00 - m11 - m22, 1.0 - m00 + m11 - m22, 1.0 - m00 - m11 + m22], dtype=float64)
    branch: object = int(argmax(cands))
    s_val: object = 2.0 * float(sqrt(max(float(cands[branch]), 1e-16)))
    inv_s: object = 1.0 / s_val
    table: object = ((0.25 * s_val, (m21 - m12) * inv_s, (m02 - m20) * inv_s, (m10 - m01) * inv_s), ((m21 - m12) * inv_s, 0.25 * s_val, (m01 + m10) * inv_s, (m02 + m20) * inv_s), ((m02 - m20) * inv_s, (m01 + m10) * inv_s, 0.25 * s_val, (m12 + m21) * inv_s), ((m10 - m01) * inv_s, (m02 + m20) * inv_s, (m12 + m21) * inv_s, 0.25 * s_val))
    return normalize(asarray(table[branch], dtype=float64))

def looking_at(r_j2000: object) -> object:
    """Build attitude quaternion pointing camera `+Z` along J2000 vector `r_j2000`."""
    z_vec: object = asarray(r_j2000, dtype=float64).ravel()
    z_len: object = float(norm(z_vec))
    if not z_len > 0.0:
        raise ValueError('looking_at requires a non-zero vector')
    z_hat: object = z_vec * (1.0 / z_len)
    pole: object = asarray([0.0, 0.0, 1.0], dtype=float64)
    x_raw: object = cross(pole, z_hat)
    if float(norm(x_raw)) < 1e-08:
        x_raw: object = cross(asarray([1.0, 0.0, 0.0], dtype=float64), z_hat)
    x_hat: object = x_raw * (1.0 / float(norm(x_raw)))
    y_raw: object = cross(z_hat, x_hat)
    y_hat: object = y_raw * (1.0 / float(norm(y_raw)))
    return from_dcm(vstack((x_hat, y_hat, z_hat)))
_PAT_RA_H = re_compile('[hH]')
_PAT_DEC_D = re_compile('[dD°º]')
_PAT_HMS_LINE = re_compile('(?P<ra>\\d{1,2}(?:\\.\\d+)?\\s*[hH].*?)\\s*(?P<dec>[+\\-]\\s*\\d{1,3}.*)\\Z', DOTALL)
_PAT_COLON_LINE = re_compile('(?P<ra>\\d{1,2}:\\d{1,2}(?::\\d+(?:\\.\\d+)?)?)\\s+(?P<dec>[+\\-]\\d{1,2}:\\d{1,2}(?::\\d+(?:\\.\\d+)?)?)\\Z')
_PAT_FLOAT = re_compile('\\d+(?:\\.\\d+)?')
_CHAR_MAP = str.maketrans({',': '.', '\xa0': ' ', '−': '-', '–': '-', '°': 'd', 'º': 'd', '′': "'", '’': "'", 'ʹ': "'", '″': '"', '“': '"', '”': '"'})

def _sexagesimal_nums(text: object) -> object:
    cleaned: object = str(text).strip().translate(_CHAR_MAP)
    sgn: object = -1.0 if re_match('^\\s*-', cleaned) else 1.0
    vals: object = [float(tok) for tok in _PAT_FLOAT.findall(cleaned)]
    return (cleaned, sgn, vals)

def split_radec_text(text: object) -> object:
    """Split a one-line Stellarium coordinate string into `(ra_str, dec_str)`."""
    norm_t: object = re_sub('[ \\t]+', ' ', str(text).replace('\xa0', ' ').replace('−', '-').replace('–', '-').strip())
    for rx in (_PAT_HMS_LINE, _PAT_COLON_LINE):
        hit: object = rx.search(norm_t)
        if hit is not None:
            return (hit.group('ra').strip(), hit.group('dec').strip())
    return None

def parse_radec_pair(text: object, *, fmt: object='auto') -> object:
    """Parse a combined RA/Dec string into `(ra_deg, dec_deg)`."""
    split_res: object = split_radec_text('' if text is None else str(text))
    if not split_res:
        raise ValueError('Cần cả RA và Dec. Dán một dòng Stellarium, ví dụ: 18h 37m51.2s   +38°48\'46.2"')
    ra_part, dec_part = split_res
    return (parse_ra_deg(ra_part, fmt=fmt), parse_dec_deg(dec_part, fmt=fmt))
_FMT_ALIASES = {'sexagesimal': 'hms', 'hms': 'hms', 'stellarium': 'hms', 'hms/dms': 'hms', 'decimal': 'decimal', 'deg': 'decimal', 'degree': 'decimal', 'degrees': 'decimal', 'auto': 'auto', '': 'auto', 'none': 'auto'}

def _normalize_radec_fmt(fmt: object) -> object:
    tag: object = _FMT_ALIASES.get(str(fmt or 'auto').strip().lower())
    if tag is None:
        raise ValueError('Định dạng RA/Dec phải là decimal (độ) hoặc sexagesimal (Stellarium)')
    return tag

def _ra_from_hms(nums: object) -> object:
    h_val, m_val, s_val = (list(nums) + [0.0, 0.0, 0.0])[:3]
    if not (0.0 <= h_val < 24.0 and 0.0 <= m_val < 60.0 and (0.0 <= s_val < 60.0)):
        raise ValueError('RA giờ-phút-giây: giờ 0–23, phút/giây 0–59.9')
    return float((h_val + m_val / 60.0 + s_val / 3600.0) * 15.0 % 360.0)

def parse_ra_deg(value: object, *, fmt: object='auto') -> object:
    """Convert decimal or sexagesimal Right Ascension input into degrees `[0, 360)`."""
    mode: object = _normalize_radec_fmt(fmt)
    if value is None or (isinstance(value, str) and (not value.strip())):
        raise ValueError('RA trống')
    if isinstance(value, str):
        maybe_pair: object = split_radec_text(value)
        if maybe_pair:
            value: object = maybe_pair[0]
    if isinstance(value, (int, float)) and (not isinstance(value, bool)):
        val_f: object = float(value)
        if mode == 'hms':
            if 0.0 <= val_f < 24.0:
                return float(val_f * 15.0 % 360.0)
            raise ValueError('Mode Stellarium: RA số trần là giờ 0–24, không phải 183751.2')
        if 0.0 <= val_f <= 360.0:
            return float(val_f % 360.0)
        raise ValueError('Mode độ: RA 0–360°. Stellarium hãy chọn mode h m s, dán 18h 37m 51.2s — không dán 183751.2')
    cleaned, _, tokens = _sexagesimal_nums(value)
    if not tokens:
        raise ValueError('RA không đọc được. Ví dụ: 18h 37m 51.2s hoặc 279.234°')
    lowered: object = cleaned.lower()
    has_h: object = bool(_PAT_RA_H.search(lowered) or 'hour' in lowered)
    has_colon: object = ':' in cleaned
    if mode == 'hms' or has_h or (has_colon and tokens[0] < 24.0):
        if mode == 'hms' and (not has_h) and (not has_colon) and (len(tokens) == 1):
            hr: object = tokens[0]
            if 0.0 <= hr < 24.0:
                return float(hr * 15.0 % 360.0)
            raise ValueError('Mode Stellarium: RA số trần là giờ 0–24. Dán 18h 37m 51.2s')
        return _ra_from_hms(tokens)
    if has_colon and tokens[0] >= 24.0:
        d_val, m_val, s_val = (tokens + [0.0, 0.0, 0.0])[:3]
        total_deg: object = d_val + m_val / 60.0 + s_val / 3600.0
        if not 0.0 <= total_deg <= 360.0:
            raise ValueError('RA độ phải 0–360')
        return float(total_deg % 360.0)
    if len(tokens) == 1:
        single: object = tokens[0]
        if mode == 'hms':
            if 0.0 <= single < 24.0:
                return float(single * 15.0 % 360.0)
            raise ValueError('Mode Stellarium: RA số trần là giờ 0–24. Dán 18h 37m 51.2s, không dán 183751.2')
        if 0.0 <= single <= 360.0:
            return float(single % 360.0)
        raise ValueError('RA số phải là độ 0–360. Dán 18h 37m 51.2s (mode Stellarium), không dán 183751.2')
    raise ValueError('Định dạng RA không hợp lệ (ví dụ chuẩn Stellarium: 18h 37m 51.2s)')

def parse_dec_deg(value: object, *, fmt: object='auto') -> object:
    """Convert decimal or DMS Declination input into degrees `[-90, +90]`."""
    mode: object = _normalize_radec_fmt(fmt)
    if value is None or (isinstance(value, str) and (not value.strip())):
        raise ValueError('Dec trống')
    if isinstance(value, str):
        maybe_pair: object = split_radec_text(value)
        if maybe_pair:
            value: object = maybe_pair[1]
    if isinstance(value, (int, float)) and (not isinstance(value, bool)):
        val_f: object = float(value)
        if -90.0 <= val_f <= 90.0:
            return val_f
        raise ValueError("Dec số phải là độ −90…+90. Stellarium dán +38° 48' 46.2″, không dán +384846.2")
    cleaned, sgn, tokens = _sexagesimal_nums(value)
    if not tokens:
        raise ValueError("Dec không đọc được. Ví dụ: +38° 48' 46.2″ hoặc +38.8128")
    lowered: object = cleaned.lower()
    has_dms: object = bool(_PAT_DEC_D.search(cleaned) or "'" in cleaned or '"' in cleaned or ('deg' in lowered))
    has_colon: object = ':' in cleaned
    if has_dms or has_colon or len(tokens) >= 2 or (mode == 'hms'):
        if mode == 'hms' and (not has_dms) and (not has_colon) and (len(tokens) == 1):
            deg_only: object = sgn * tokens[0]
            if -90.0 <= deg_only <= 90.0:
                return float(deg_only)
            raise ValueError("Dec số phải là độ −90…+90. Dán +38° 48' 46.2″, không dán +384846.2")
        d_val, m_val, s_val = (tokens + [0.0, 0.0, 0.0])[:3]
        if m_val >= 60.0 or s_val >= 60.0:
            raise ValueError('Dec phút/giây phải 0–59.9')
        deg_total: object = sgn * (d_val + m_val / 60.0 + s_val / 3600.0)
        if not -90.0 <= deg_total <= 90.0:
            raise ValueError('Dec phải trong −90…+90 độ')
        return float(deg_total)
    deg_single: object = sgn * tokens[0]
    if -90.0 <= deg_single <= 90.0:
        return float(deg_single)
    raise ValueError("Dec số phải là độ −90…+90. Dán +38° 48' 46.2″ (chuẩn có dấu phân cách đơn vị, không viết liền +384846.2)")

def looking_at_ra_dec(ra_deg: object, dec_deg: object) -> object:
    """Build quaternion pointing camera `+Z` at `(ra_deg, dec_deg)` (accepts strings or degrees)."""
    ra_r: object = float(radians(parse_ra_deg(ra_deg)))
    dec_r: object = float(radians(parse_dec_deg(dec_deg)))
    cd: object = float(cos(dec_r))
    unit_vec: object = asarray([cd * float(cos(ra_r)), cd * float(sin(ra_r)), float(sin(dec_r))], dtype=float64)
    return looking_at(unit_vec)

def to_scipy_xyzw(q: object) -> object:
    w, x, y, z = normalize(q)
    return asarray([x, y, z, w], dtype=float64)

def from_scipy_xyzw(xyzw: object) -> object:
    x, y, z, w = asarray(xyzw, dtype=float64).ravel()
    return normalize(asarray([w, x, y, z], dtype=float64))

def random_quaternion(rng: object=None) -> object:
    """Draw a Haar-uniform random unit quaternion on SO(3)."""
    gen: object = default_rng() if rng is None else rng
    return normalize(gen.normal(size=4))

def propagate(q: object, omega_rad_s: object, dt_s: object) -> object:
    """Integrate quaternion `q(t + dt) = q (x) dq(omega * dt)` over `dt_s` seconds."""
    wx, wy, wz = asarray(omega_rad_s, dtype=float64).ravel()
    rate: object = float(sqrt(wx * wx + wy * wy + wz * wz))
    theta: object = rate * float(dt_s)
    if abs(theta) < 1e-18:
        return normalize(q)
    half_ang: object = 0.5 * theta
    scale: object = float(sin(half_ang)) / rate
    dq: object = asarray([float(cos(half_ang)), wx * scale, wy * scale, wz * scale], dtype=float64)
    return normalize(multiply(q, dq))

def angular_error_arcsec(q_est: object, q_gt: object) -> object:
    u_est, u_gt = (normalize(q_est), normalize(q_gt))
    cos_half: object = float(clip(abs(dot(u_est, u_gt)), 0.0, 1.0))
    return float(2.0 * arccos(cos_half) * ARCSEC_PER_RAD)

def axis_error_arcsec(q_est: object, q_gt: object) -> object:
    """Small-angle 3-axis rotation error vector `(dx, dy, dz)` in arcseconds."""
    dq: object = multiply(normalize(q_est), inverse(q_gt))
    signed: object = -dq if float(dq[0]) < 0.0 else dq
    return 2.0 * ARCSEC_PER_RAD * signed[1:4]

def boresight_ra_dec_deg(q: object) -> object:
    """Compute J2000 `(ra_deg, dec_deg)` of the camera `+Z` boresight axis."""
    rx, ry, rz = to_dcm(q)[2]
    ra_val: object = float(degrees(mod(arctan2(ry, rx), 2.0 * pi)))
    dec_val: object = float(degrees(arcsin(clip(rz, -1.0, 1.0))))
    return (ra_val, dec_val)

def _split_sexagesimal(value: object) -> object:
    whole: object = int(value)
    rem_m: object = (value - whole) * 60.0
    mins: object = int(rem_m)
    secs: object = (rem_m - mins) * 60.0
    return (whole, mins, secs)

def format_ra_hms(ra_deg: object) -> object:
    hrs: object = float(ra_deg) % 360.0 / 15.0
    h_i, m_i, s_f = _split_sexagesimal(hrs)
    return f'{h_i:02d}h {m_i:02d}m {s_f:05.2f}s'

def format_dec_dms(dec_deg: object) -> object:
    val: object = float(dec_deg)
    sgn: object = '+' if val >= 0.0 else '-'
    d_i, m_i, s_f = _split_sexagesimal(abs(val))
    return f'{sgn}{d_i:02d}d {m_i:02d}m {s_f:04.1f}s'

def format_dec_stellarium(dec_deg: object) -> object:
    val: object = float(dec_deg)
    sgn: object = '+' if val >= 0.0 else '-'
    d_i, m_i, s_f = _split_sexagesimal(abs(val))
    return f'''{sgn}{d_i:02d}° {m_i:02d}' {s_f:04.1f}"'''

def format_ra_both(ra_deg: object) -> object:
    wrapped: object = float(ra_deg) % 360.0
    return f'{wrapped:.5f}°  ({format_ra_hms(ra_deg)})'

def format_dec_both(dec_deg: object) -> object:
    return f'{float(dec_deg):+.5f}°  ({format_dec_stellarium(dec_deg)})'
