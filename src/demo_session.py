"""Shared execution session for CLI and Web UI: synthetic sky generation and lost-in-space solving."""
from json import dumps as json_dumps, loads as json_loads
from math import ceil as math_ceil, isfinite as math_isfinite
from pathlib import Path
from cv2 import COLOR_BGR2GRAY, IMREAD_UNCHANGED, cvtColor, imread, imwrite
from numpy import asarray, clip, column_stack, degrees, float32, float64, floating, full, integer, mean, ndarray, sqrt, where, zeros, zeros_like
from numpy.linalg import norm
from numpy.random import default_rng
from .camera import CameraModel, demo_camera
from .catalog import CatalogManager
from .kvector import build_or_load, cache_path_for
from .metrics import evaluate
from .pipeline import PipelineConfig, StarTrackerPipeline
from .quaternion import ARCSEC_PER_RAD, format_dec_both, format_ra_both, looking_at, looking_at_ra_dec
from .simulator import GlareSpec, Radiometry, RenderTruth, SkySimulator
from .starnames import describe_index, n_iau_names, n_named_hr
from .visualize import image_stats, plot_frame, save_clean_png, save_input_png, save_output_png
ROOT = Path(__file__).resolve().parents[1]
_LOCKED_CAM = demo_camera()
TOL_ARCSEC_PER_PIXEL = 0.88
THETA_MIN_DEG = 0.02
THETA_MAX_LOCKED_DEG = 30.5
MAX_SIM_PIXELS = 20000000
_RAD_DEFAULTS = dict(e_per_s_v0=3300000.0, qe=1.0, read_noise_e=5.0, dark_e_per_s=10.0, gain_dn_per_e=1.0, full_well_e=12000.0, bit_depth=12, bias_dn=64.0, hot_pixel_frac=1e-05, cosmic_rate_per_frame=2.0)
_RUN_REQ_DEFAULTS = dict(mode='fast', scale=None, seed=42, catalog='bsc5', max_mag=6.0, omega=0.06, omega_axis='y', exposure=0.15, glare='none', sky_clutter='none', false_stars=0, solver='svd', centroid_backend='classical', image=None, sidecar=None, out_dir=None, lookup=True, save_png=True, save_raw=False, show=False, point_hr=None, ra_deg=None, dec_deg=None, focal_mm=None, pixel_um=None, image_width=None, image_height=None, angular_tol_arcsec=None, k1=None, k2=None)

def load_specs(root: object=None) -> object:
    cfg_file: object = Path(root or ROOT).joinpath('config', 'camera_specs.json')
    return json_loads(cfg_file.read_text(encoding='utf-8'))

def load_pipeline_cfg(mode: object, root: object=None) -> object:
    cfg_file: object = Path(root or ROOT).joinpath('config', 'pipeline_default.json')
    all_modes: object = json_loads(cfg_file.read_text(encoding='utf-8'))
    return PipelineConfig.from_dict(all_modes[mode])

def radiometry_from_specs(specs: object) -> object:
    raw_r: object = specs.get('radiometry') or {}
    kw: object = {k: int(raw_r.get(k, dv)) if k == 'bit_depth' else float(raw_r.get(k, dv)) for k, dv in _RAD_DEFAULTS.items()}
    return Radiometry(assumption=True, **kw)

def load_catalog(kind: object, max_mag: object, cache_dir: object) -> object:
    c_dir: object = Path(cache_dir)
    if kind == 'synthetic':
        return (CatalogManager.synthetic(3500, max_mag, seed=123), True)
    if kind == 'hipparcos':
        hip_cache: object = c_dir / 'hipparcos_v6.npz'
        if hip_cache.exists():
            return (CatalogManager.load_npz(hip_cache), False)
        tsv_candidates: object = (c_dir / 'hipparcos_v6.tsv', c_dir / 'starcat.tsv')
        tsv_file: object = next((p for p in tsv_candidates if p.exists()), None)
        if tsv_file is not None:
            raw_cat: object = CatalogManager.load_hipparcos_tsv(tsv_file, max_mag=max_mag, epoch_year=2026.7)
            pruned: object = CatalogManager.filter_close_pairs(raw_cat, 60.0)
            CatalogManager.save_npz(pruned, hip_cache)
            return (pruned, False)
        kind: object = 'bsc5'
    bsc_cache: object = c_dir / f'bsc5_v{max_mag}.npz'
    if kind == 'bsc5' and bsc_cache.exists():
        return (CatalogManager.load_npz(bsc_cache), False)
    bsc_bin: object = c_dir / 'BSC5'
    try:
        CatalogManager.fetch_bsc5(bsc_bin)
        raw_cat: object = CatalogManager.load_bsc5(bsc_bin, max_mag=max_mag, epoch_year=2026.7)
        pruned: object = CatalogManager.filter_close_pairs(raw_cat, 60.0)
        CatalogManager.save_npz(pruned, bsc_cache)
        return (pruned, False)
    except FileNotFoundError:
        return (CatalogManager.synthetic(3500, max_mag, seed=123), True)

def glare_spec_from_req(req: object, camera: object) -> object:
    tag: object = str(req.glare or 'none').lower()
    if tag == 'earth':
        return GlareSpec(kind='earth', peak_dn=2800, edge_frac=0.7)
    u_pos, v_pos = (0.18 * camera.width, 0.22 * camera.height)
    short_side: object = min(camera.width, camera.height)
    if tag == 'sun':
        return GlareSpec(kind='sun', u=u_pos, v=v_pos, sigma_px=max(18.0, 0.12 * short_side), peak_dn=4095)
    if tag in ('sun_strong', 'glare_demo', 'stray'):
        return GlareSpec(kind='sun', u=u_pos, v=v_pos, sigma_px=max(40.0, 0.28 * short_side), peak_dn=4095)
    if tag == 'moon':
        return GlareSpec(kind='moon', u=u_pos, v=v_pos, peak_dn=2400)
    return None

def find_sidecar(image_path: object, root: object) -> object:
    img_p: object = Path(image_path)
    adj_json: object = img_p.with_suffix('.json')
    if adj_json.is_file():
        return adj_json
    sim_dir: object = Path(root).joinpath('data', 'sim_dataset').resolve()
    if sim_dir.is_dir():
        found: object = list(sim_dir.rglob(f'{img_p.stem}.json'))
        if found:
            return found[0]
    return None

def apply_loaded_stress(image: object, camera: object, catalog: object, radiometry: object, req: object) -> object:
    """Inject synthetic glare, sky clutter, or false stars onto an existing image."""
    g_spec: object = glare_spec_from_req(req, camera)
    clutter_tag: object = str(req.sky_clutter or 'none')
    num_spurious: object = int(req.false_stars or 0)
    if g_spec is None and num_spurious <= 0 and (clutter_tag in ('', 'none')):
        return image
    sim: object = SkySimulator(camera, catalog, radiometry=radiometry, seed=int(req.seed))
    work: object = asarray(image, dtype=float32).copy()
    if num_spurious > 0:
        layer: object = zeros_like(work)
        sp_uv: object = column_stack((sim.rng.uniform(10.0, camera.width - 10.0, size=num_spurious), sim.rng.uniform(10.0, camera.height - 10.0, size=num_spurious)))
        sp_elec: object = sim.electrons(full(num_spurious, 4.0), float(req.exposure or 0.15))
        sim._stamp_gaussians(layer, sp_uv, sp_elec, 1.2, 5)
        work: object = work + layer * radiometry.gain_dn_per_e
    if g_spec is not None:
        work: object = work + sim._glare_dn(g_spec)
    if clutter_tag not in ('', 'none'):
        work: object = work + sim._clutter_dn(clutter_tag)
    return clip(work, 0, radiometry.max_dn).astype('uint16')

def omega_vector(axis: object, mag: object, rng: object) -> object:
    rate: object = float(mag)
    if axis == 'random':
        rnd: object = rng.normal(size=3)
        return rnd * (rate / float(norm(rnd)))
    basis: object = {'x': (rate, 0.0, 0.0), 'y': (0.0, rate, 0.0), 'z': (0.0, 0.0, rate)}
    return asarray(basis[axis], dtype=float64)

def load_frame(path: object) -> object:
    raw: object = imread(str(path), IMREAD_UNCHANGED)
    if raw is None:
        raise FileNotFoundError(f'Cannot read image: {path}')
    return cvtColor(raw, COLOR_BGR2GRAY) if raw.ndim == 3 else raw

def camera_for_image(img: object, cam_full: object) -> object:
    h_px, w_px = img.shape[:2]
    if (w_px, h_px) == (cam_full.width, cam_full.height):
        return (cam_full, 1, 'full')
    fast_cam: object = cam_full.downscaled(4)
    if (w_px, h_px) == (fast_cam.width, fast_cam.height):
        return (fast_cam, 4, 'fast')
    if (w_px, h_px) == (1024, 683):
        hd_cam: object = CameraModel(width=1024, height=683, pixel_um=cam_full.pixel_um * (cam_full.width / 1024.0), focal_mm=cam_full.focal_mm)
        return (hd_cam, 6, 'fast')
    if (w_px, h_px) == (1024, 1024):
        mnt_cam: object = CameraModel(width=1024, height=1024, pixel_um=4.1, focal_mm=4.163043225470905, k1=0.08897545958095043, k2=-0.09770961126729949)
        return (mnt_cam, 1, 'custom')
    if (w_px, h_px) == (1024, 768):
        tetra_cam: object = CameraModel(width=1024, height=768, pixel_um=6.9, focal_mm=35.291113627236776, k1=0.10021753616812087)
        return (tetra_cam, 1, 'custom')
    raise ValueError(f'Ảnh {w_px}×{h_px} không khớp kích thước mẫu {cam_full.width}×{cam_full.height} (FULL) hay {fast_cam.width}×{fast_cam.height} (FAST). Vui lòng nhập tiêu cự (mm) và kích thước pixel (µm) của máy ảnh.')

def uses_custom_optics(req: object) -> object:
    opt_fields: object = (req.focal_mm, req.pixel_um, req.image_width, req.image_height, req.angular_tol_arcsec)
    return any((val is not None for val in opt_fields))

def theta_max_deg_for_fov(diag_deg: object) -> object:
    d_val: object = float(diag_deg)
    if d_val <= THETA_MAX_LOCKED_DEG + 1e-09:
        return THETA_MAX_LOCKED_DEG
    rounded_half: object = math_ceil((d_val + 0.5) * 2.0 - 1e-09) * 0.5
    return float(min(180.0, rounded_half))

def _camera_from_numbers(width: object, height: object, pixel_um: object, focal_mm: object, k1: object=None, k2: object=None) -> object:
    w_i, h_i = (int(width), int(height))
    px_f, fl_f = (float(pixel_um), float(focal_mm))
    if w_i < 16 or h_i < 16:
        raise ValueError('Số cột và số hàng phải từ 16 trở lên.')
    if fl_f <= 0.0 or px_f <= 0.0:
        raise ValueError('Tiêu cự (mm) và cạnh pixel (µm) phải là số dương.')
    if fl_f > 5000.0 or px_f > 200.0:
        raise ValueError('Tiêu cự hoặc cạnh pixel nằm ngoài khoảng dùng để giải.')
    return CameraModel(width=w_i, height=h_i, pixel_um=px_f, focal_mm=fl_f, k1=0.0 if k1 is None else float(k1), k2=0.0 if k2 is None else float(k2))

def _locked_camera_for_size(width: object, height: object, cam_full: object) -> object:
    if (width, height) == (cam_full.width, cam_full.height):
        return cam_full
    fast_cam: object = cam_full.downscaled(4)
    if (width, height) == (fast_cam.width, fast_cam.height):
        return fast_cam
    if (width, height) == (1024, 683):
        return CameraModel(width=1024, height=683, pixel_um=cam_full.pixel_um * (cam_full.width / 1024.0), focal_mm=cam_full.focal_mm)
    return None

def resolve_run_camera(req: object, image: object, cam_full: object) -> object:
    is_custom: object = uses_custom_optics(req)
    if image is not None:
        h_px, w_px = (int(image.shape[0]), int(image.shape[1]))
        if not is_custom:
            cam, sc, md = camera_for_image(image, cam_full)
            return (cam, sc, md, md != 'custom')
        preset: object = _locked_camera_for_size(w_px, h_px, cam_full)
        fl: object = req.focal_mm if req.focal_mm is not None else preset.focal_mm if preset else None
        px: object = req.pixel_um if req.pixel_um is not None else preset.pixel_um if preset else None
        if fl is None or px is None:
            fast_c: object = cam_full.downscaled(4)
            raise ValueError(f'Ảnh {w_px}×{h_px} không khớp kích thước mẫu {cam_full.width}×{cam_full.height} hoặc {fast_c.width}×{fast_c.height}. Vui lòng nhập tiêu cự (mm) và kích thước pixel (µm) của máy ảnh.')
        return (_camera_from_numbers(w_px, h_px, px, fl, k1=getattr(req, 'k1', None), k2=getattr(req, 'k2', None)), 1, 'custom', False)
    sc: object = int(req.scale) if req.scale is not None else 4 if req.mode == 'fast' else 1
    if sc < 1:
        raise ValueError('scale phải ≥ 1')
    base_cam: object = cam_full if sc == 1 else cam_full.downscaled(sc)
    if not is_custom:
        md: object = req.mode if req.mode in ('fast', 'full') else 'full'
        return (base_cam, sc, md, True)
    if (req.image_width is None) != (req.image_height is None):
        raise ValueError('Nhập cả số cột và số hàng, hoặc để trống cả hai.')
    w_px: object = int(req.image_width or base_cam.width)
    h_px: object = int(req.image_height or base_cam.height)
    fl: object = float(req.focal_mm if req.focal_mm is not None else base_cam.focal_mm)
    px: object = float(req.pixel_um if req.pixel_um is not None else base_cam.pixel_um)
    if w_px * h_px > MAX_SIM_PIXELS:
        raise ValueError('Ảnh sinh ra vượt 20 triệu pixel. Giảm số cột và số hàng, hoặc nạp file có sẵn.')
    return (_camera_from_numbers(w_px, h_px, px, fl), 1, 'custom', False)

def match_tolerance_arcsec(camera: object, override: object=None) -> object:
    if override is not None:
        val: object = float(override)
        if val <= 0.0:
            raise ValueError('Dung sai góc (arcsec) phải là số dương.')
        return val
    return float(TOL_ARCSEC_PER_PIXEL * camera.ifov_arcsec)

def angle_table_note(diag_deg: object, theta_max_deg: object, n_pairs: object, built_now: object) -> object:
    pairs_txt: object = f'{int(n_pairs):,}'.replace(',', '.')
    tail: object = f'Bảng góc 0,02°–{theta_max_deg:.1f}° ({pairs_txt} cặp sao).'
    if diag_deg <= THETA_MAX_LOCKED_DEG + 1e-06 and abs(theta_max_deg - THETA_MAX_LOCKED_DEG) < 1e-06:
        return f'Trường nhìn chéo {diag_deg:.2f}° dùng sẵn bảng góc mặc định {THETA_MAX_LOCKED_DEG:.1f}°. {tail}'
    if built_now:
        return f'Trường nhìn chéo {diag_deg:.2f}° vượt mức mặc định {THETA_MAX_LOCKED_DEG:.1f}° — vừa tạo và lưu bảng góc mới tới {theta_max_deg:.1f}°. {tail}'
    return f'Trường nhìn chéo {diag_deg:.2f}° dùng bảng góc mở rộng {theta_max_deg:.1f}° đã lưu sẵn. {tail}'

def empty_truth() -> object:
    return RenderTruth(q_gt=asarray([1.0, 0.0, 0.0, 0.0], dtype=float64), uv_mid=zeros((0, 2), dtype=float64), cat_idx=zeros(0, dtype=int), streak_px=zeros(0, dtype=float64), omega_deg_s=zeros(3, dtype=float64), vis_mags=zeros(0, dtype=float64))

def truth_from_sidecar(meta: object, catalog: object) -> object:
    q_gt: object = asarray(meta['q_gt'], dtype=float64)
    fov_list: object = meta.get('stars_in_fov') or []
    uv_pts: object = asarray([[item['u_px'], item['v_px']] for item in fov_list], dtype=float64) if fov_list else zeros((0, 2), dtype=float64)
    mags: object = asarray([float(item.get('mag', 0.0)) for item in fov_list], dtype=float64) if fov_list else zeros(0, dtype=float64)
    if fov_list and 'catalog_idx' in fov_list[0]:
        c_idx: object = asarray([int(item['catalog_idx']) for item in fov_list], dtype=int)
    else:
        lookup_id: object = {int(star_id): pos for pos, star_id in enumerate(catalog.ids)}
        c_idx: object = asarray([lookup_id[int(item['hr'])] for item in fov_list if item.get('hr') is not None and int(item['hr']) in lookup_id], dtype=int)
        if len(c_idx) != len(fov_list):
            uv_pts: object = uv_pts[:len(c_idx)]
            mags: object = mags[:len(c_idx)]
    omega: object = asarray(meta.get('omega_deg_s') or [0.0, 0.0, 0.0], dtype=float64)
    return RenderTruth(q_gt=q_gt, uv_mid=uv_pts, cat_idx=c_idx, streak_px=zeros(len(c_idx), dtype=float64), omega_deg_s=omega, vis_mags=mags)

def star_rows_from_indices(catalog: object, indices: object, uv: object=None, mags: object=None) -> object:
    out_rows: object = []
    for pos, c_idx in enumerate(indices):
        rec: object = describe_index(catalog, int(c_idx))
        if uv is not None and pos < len(uv):
            rec['u_px'] = float(uv[pos, 0])
            rec['v_px'] = float(uv[pos, 1])
        if mags is not None and pos < len(mags):
            rec['mag'] = float(mags[pos])
        out_rows.append(rec)
    return out_rows

def _jsonable(value: object) -> object:
    if isinstance(value, ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (floating, integer)):
        value = value.item()
    if isinstance(value, float):
        return value if math_isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value

def _ingest_note(path: object) -> object:
    if path is not None and Path(path).suffix.lower() in ('.jpg', '.jpeg', '.webp'):
        return 'Lưu ý: ảnh JPEG/WebP đã qua nén nên vị trí tâm sao có thể kém chính xác hơn ảnh gốc TIFF.'
    return None

def fmt_q(q: object) -> object:
    if q is None:
        return 'n/a'
    q0, q1, q2, q3 = asarray(q, dtype=float64).ravel()
    return f'[{q0:.5f}, {q1:.5f}, {q2:.5f}, {q3:.5f}]'

class RunRequest:
    """Parameters controlling a single synthetic or dataset star tracker run."""

    def __init__(self, **kwargs) -> object:
        state: object = dict(_RUN_REQ_DEFAULTS)
        state.update(kwargs)
        self.__dict__.update(state)

class RunOutcome:
    """Complete result bundle returned by `DemoEngine.run`."""

    def __init__(self, success: object, payload: object, image: object, result: object, truth: object, metrics: object, catalog: object, camera: object, png_path: object, have_gt: object, error: object=None) -> object:
        self.success, self.payload, self.image, self.result, self.truth, self.metrics, self.catalog, self.camera, self.png_path, self.have_gt, self.error = (bool(success), payload, image, result, truth, metrics, catalog, camera, png_path, bool(have_gt), error)

def _compare_rows(q_gt: object, q_est: object, metrics: object, have_gt: object, cfg: object, match_stats: object=None) -> object:
    mstats: object = match_stats if isinstance(match_stats, dict) else {}
    q_labels: object = ('q0 (vô hướng)', 'q1', 'q2', 'q3')
    rows: object = [dict(param=lbl, gt=None if not have_gt or q_gt is None else float(q_gt[idx]), est=None if q_est is None else float(q_est[idx]), delta=None if not have_gt or q_gt is None or q_est is None else float(q_est[idx] - q_gt[idx]), unit='', note='thành phần vô hướng đứng đầu (q và -q cùng chỉ một hướng)' if idx == 0 else '') for idx, lbl in enumerate(q_labels)]
    status_val: object = str(metrics.get('status') or mstats.get('status') or ('SOLVED' if metrics.get('success') else 'LOST'))
    reject_code: object = metrics.get('reject_code') if metrics.get('reject_code') is not None else mstats.get('reject_code')
    rows.append(dict(param='Trạng thái định hướng', gt='SOLVED' if have_gt else '—', est=status_val, delta=reject_code or ('PASS' if status_val == 'SOLVED' else 'LOST'), unit='', note='kiểm tra độ tin cậy hình học trước khi khóa hướng'))
    coord_specs: object = (('RA', 'boresight_gt_ra_deg', 'boresight_est_ra_deg', format_ra_both), ('Dec', 'boresight_gt_dec_deg', 'boresight_est_dec_deg', format_dec_both))
    for tag, gt_key, est_key, fmt_fn in coord_specs:
        g_val, e_val = (metrics.get(gt_key), metrics.get(est_key))
        rows.append(dict(param=f'Hướng ngắm {tag} (J2000)', gt=None if g_val is None else fmt_fn(g_val), est=None if e_val is None else fmt_fn(e_val), delta=None if g_val is None or e_val is None else float(e_val - g_val), unit='deg', gt_deg=g_val, est_deg=e_val, note='tọa độ xích đạo thiên cầu của tâm khung ảnh'))
    att_err: object = metrics.get('attitude_error_arcsec')
    lim_arc: object = float(cfg.attitude_error_limit_arcsec)
    rows.append(dict(param='Sai số tư thế 3 trục', gt='0″ (lý tưởng)' if have_gt else '—', est=att_err, delta=att_err, unit='arcsec', limit_arcsec=lim_arc, note=f"ngưỡng đạt {lim_arc:g}″ ({metrics.get('verdict')})"))
    nt, nd, nm = (metrics.get('n_truth'), metrics.get('n_detected'), metrics.get('n_matched'))
    rows.append(dict(param='Số sao (Khung nhìn / Phát hiện / Khớp)', gt=None if nt is None else f'{int(nt)} trong khung', est=None if nd is None else f'{int(nd)} phát hiện', delta=None if nm is None else f'{int(nm)} khớp', unit='', note='tổng sao thực tế, sao tìm thấy và sao nhận diện được'))
    n_init: object = mstats.get('n_initial_matched', metrics.get('n_initial_matched'))
    n_valid: object = mstats.get('n_valid_pairs', metrics.get('n_valid_pairs'))
    n_rej: object = mstats.get('n_rejected_outliers', metrics.get('n_rejected_outliers'))
    rows.append(dict(param='Cặp hợp lệ / Loại ngoại lai', gt=None if n_init is None else f'{int(n_init)} ban đầu', est=None if n_valid is None else f'{int(n_valid)} hợp lệ', delta=None if n_rej is None else f'-{int(n_rej)} ngoại lai', unit='', note='số sao giữ lại sau bước lọc sai số góc'))
    rms_res: object = mstats.get('rms_residual_arcsec', metrics.get('rms_residual_arcsec'))
    max_res: object = mstats.get('max_residual_arcsec', metrics.get('max_residual_arcsec'))
    rows.append(dict(param='Phần dư khớp sao (RMS / Max)', gt=f'≤ {lim_arc:g}″', est=rms_res, delta=max_res, unit='arcsec', limit_arcsec=lim_arc, note='sai số góc trung bình và lớn nhất của các sao khớp'))
    rows.append(dict(param='Độ lệch tâm sao (RMS)', gt=None, est=metrics.get('centroid_rms_px'), delta=None, unit='px', note='độ lệch vị trí tâm sao so với nhãn chuẩn (pixel)'))
    c_prec: object = metrics.get('centroid_precision')
    c_rec: object = metrics.get('centroid_recall')
    if have_gt and (c_prec is not None or c_rec is not None):
        rows.append(dict(param='Độ chính xác / Độ phủ tâm sao', gt='100.0% / 100.0%', est=None if c_prec is None else f'{float(c_prec) * 100.0:.1f}%', delta=None if c_rec is None else f'Độ phủ {float(c_rec) * 100.0:.1f}%', unit='', note='tỷ lệ điểm sáng đúng là sao và tỷ lệ sao tìm thấy (≤ 5 px)'))
    return rows
SIM_METHOD = dict(generated_by_code=True, module='src.simulator.SkySimulator.render', not_iso_ccsds=True, evaluation_scope='PC/laptop software demo (not flight-qualified spacecraft hardware)', practice_class='catalog + pinhole + PSF + detector noise + quaternion GT', same_class_as=['UW LOST --generate', 'ESA tetra3 synthetic tests', 'NASA COTS (math, not NOSA copy)'], demo_optics='APS-C 6000x4000, 3.72 um, 50 mm lens', radiometry='assumption=true, not a camera datasheet', steps=['Sinh quaternion chuẩn q_GT phân bố đều trên SO(3) từ seed cố định', 'Trích xuất vector đơn vị J2000 từ danh mục sao sáng Yale BSC5 (V<=6.0)', 'Chiếu tâm lỗ kim các tia sao b = A(q_GT)*r lên mặt phẳng cảm biến APS-C', 'Mô phỏng hàm truyền điểm PSF Gauss và vệt dịch chuyển theo vận tốc góc', 'Cộng nhiễu hạt photon, nhiễu đọc và lượng tử hóa về ảnh số 12-bit (uint16)', 'Thuật toán giải mù từ mảng điểm ảnh để khôi phục tư thế q_est (demo trên máy tính cá nhân)'])

def _extract_match_verification(result: object, metrics: object, cfg: object) -> object:
    status_val: object = str(metrics.get('status') or getattr(result, 'status', None) or ('SOLVED' if result.success else 'LOST'))
    reject_val: object = metrics.get('reject_code')
    if reject_val is None:
        reject_val = getattr(result, 'reject_code', None)
    raw_stats: object = getattr(result, 'match_stats', None)
    if not isinstance(raw_stats, dict):
        qual: object = getattr(result, 'quality', None)
        raw_stats = qual if isinstance(qual, dict) else {}
    res_raw: object = getattr(result, 'residuals_arcsec', None)
    res_arr: object = None if res_raw is None else asarray(res_raw, dtype=float64)
    rms_fb: object = float(sqrt(mean(res_arr * res_arr))) if res_arr is not None and res_arr.size else None
    max_fb: object = float(res_arr.max()) if res_arr is not None and res_arr.size else None
    min_req_default: object = max(int(getattr(cfg, 'min_stars', 4)), 3)
    match_stats: object = dict(raw_stats)
    match_stats['status'] = status_val
    match_stats['reject_code'] = reject_val
    for key, fallback in (
        ('n_detected', metrics.get('n_detected')),
        ('n_initial_matched', metrics.get('n_initial_matched', metrics.get('n_matched'))),
        ('n_rejected_outliers', metrics.get('n_rejected_outliers', 0)),
        ('n_valid_pairs', metrics.get('n_valid_pairs', metrics.get('n_matched'))),
        ('min_pairs_required', metrics.get('min_pairs_required', min_req_default)),
        ('rms_residual_arcsec', metrics.get('rms_residual_arcsec', rms_fb)),
        ('max_residual_arcsec', metrics.get('max_residual_arcsec', max_fb)),
        ('fov_expected_stars', metrics.get('fov_expected_stars')),
    ):
        if match_stats.get(key) is None:
            match_stats[key] = fallback
    metrics['status'] = status_val
    metrics['reject_code'] = reject_val
    for key in ('n_initial_matched', 'n_rejected_outliers', 'n_valid_pairs', 'min_pairs_required', 'rms_residual_arcsec', 'max_residual_arcsec', 'fov_expected_stars'):
        if metrics.get(key) is None:
            metrics[key] = match_stats.get(key)
    return (status_val, reject_val, match_stats)

class DemoEngine:
    """Stateful runner caching star catalogs, K-vector indices, and MobileUNet weights across runs."""

    def __init__(self, root: object=None) -> object:
        self.root = Path(root) if root else ROOT
        self.specs = load_specs(self.root)
        self.cam_full = demo_camera()
        self.radiometry = radiometry_from_specs(self.specs)
        self._stack = {}
        self._cnn_cache = None
        self.last_angle_build = False

    def _normalize_backend(self, raw_be: object) -> str:
        be_key: str = str(raw_be or 'classical').lower().strip()
        if be_key in ('cnn', 'cnn_hybrid', 'cnn_zhao2024', 'zhao', 'mobileunet'):
            return 'cnn'
        if be_key in ('cnn_raw', 'cnn_trilateration'):
            return 'cnn_raw'
        if be_key in ('tetra3', 'tetra3_threshold'):
            return 'tetra3'
        return 'classical'

    def _build_pipeline(self, camera: object, catalog: object, kvector: object, cfg: object) -> object:
        pipe: object = StarTrackerPipeline(camera, catalog, kvector, cfg)
        if cfg.centroid_backend in ('cnn', 'cnn_raw'):
            det = pipe.centroid_detector
            if self._cnn_cache is not None and getattr(self._cnn_cache, '_model', None) is not None:
                det._model = self._cnn_cache._model
                det._torch = self._cnn_cache._torch
                det._normalize = self._cnn_cache._normalize
                det._device = self._cnn_cache._device
                det.device_name = self._cnn_cache.device_name
            else:
                self._cnn_cache = det
        return pipe

    def _manifest_truth_for(self, image_path: object) -> tuple:
        """Look up calibrated ground-truth metadata for known real-sky demo frames."""
        if image_path is None:
            return (None, None)
        manifest_p: object = self.root.joinpath('data', 'real_calibrated', 'manifest_real_calibrated.json')
        if not manifest_p.is_file():
            return (None, None)
        try:
            m_data: object = json_loads(manifest_p.read_text(encoding='utf-8'))
            fname: str = Path(image_path).name.lower()
            for entry in (m_data.get('frames') or []):
                if Path(str(entry.get('path', ''))).name.lower() == fname and entry.get('q_gt') is not None:
                    q_gt = asarray(entry['q_gt'], dtype=float64)
                    stars = entry.get('stars_in_fov') or []
                    uv_pts = asarray([[s['u_px'], s['v_px']] for s in stars], dtype=float64) if stars else zeros((0, 2), dtype=float64)
                    mags = asarray([float(s.get('mag', 0.0)) for s in stars], dtype=float64) if stars else zeros(0, dtype=float64)
                    truth = RenderTruth(
                        q_gt=q_gt,
                        uv_mid=uv_pts,
                        cat_idx=zeros(len(stars), dtype=int),
                        streak_px=zeros(len(stars), dtype=float64),
                        omega_deg_s=zeros(3, dtype=float64),
                        vis_mags=mags,
                    )
                    return (truth, str(entry.get('gt_source') or 'manifest_real_calibrated'))
        except Exception:
            return (None, None)
        return (None, None)

    def stack(self, kind: object, max_mag: object, theta_max_deg: object=THETA_MAX_LOCKED_DEG) -> object:
        cache_key: object = (kind, float(max_mag), float(theta_max_deg))
        if cache_key in self._stack:
            self.last_angle_build = False
            return self._stack[cache_key]
        cat_dir: object = self.root.joinpath('data', 'catalogs')
        cat, is_syn = load_catalog(kind, max_mag, cat_dir)
        kv_file: object = cache_path_for(cat, cat_dir, THETA_MIN_DEG, float(theta_max_deg))
        was_cached: object = kv_file.exists()
        if not was_cached:
            print(f'Building angle table 0.02-{float(theta_max_deg):.1f} deg for {cat.source} (first time, then cached).', flush=True)
        kv_tbl: object = build_or_load(cat, cat_dir, theta_min_deg=THETA_MIN_DEG, theta_max_deg=float(theta_max_deg))
        self.last_angle_build = not was_cached
        self._stack[cache_key] = (cat, is_syn, kv_tbl)
        return self._stack[cache_key]

    def list_dataset_frames(self) -> object:
        entries: object = []
        sim_root: object = self.root.joinpath('data', 'sim_dataset').resolve()
        if sim_root.exists():
            for sub_dir in sorted((p for p in sim_root.iterdir() if p.is_dir())):
                md_name: object = sub_dir.name
                for tif_p in sorted(sub_dir.glob('*.tif')):
                    sc_p: object = tif_p.with_suffix('.json')
                    meta: object = json_loads(sc_p.read_text(encoding='utf-8')) if sc_p.exists() else {}
                    bore: object = meta.get('boresight') or {}
                    entries.append(dict(id=f'{md_name}/{tif_p.stem}', file=f'{md_name}/{tif_p.name}', mode=md_name, n_stars=len(meta.get('stars_in_fov') or []), ra_deg=bore.get('ra_deg'), dec_deg=bore.get('dec_deg')))
        tetra_root: object = self.root.joinpath('data', 'tetra3').resolve()
        if tetra_root.exists():
            manifest_map: object = {}
            manifest_p: object = self.root.joinpath('data', 'real_calibrated', 'manifest_real_calibrated.json')
            if manifest_p.is_file():
                try:
                    m_data: object = json_loads(manifest_p.read_text(encoding='utf-8'))
                    manifest_map = {str(item.get('path', '')).replace('\\', '/'): item for item in (m_data.get('frames') or [])}
                except Exception:
                    manifest_map = {}
            for tiff_p in sorted((p for p in tetra_root.iterdir() if p.is_file() and p.suffix.lower() in ('.tif', '.tiff'))):
                m_entry: object = manifest_map.get(f'data/tetra3/{tiff_p.name}', {})
                entries.append(dict(id=f'tetra3/{tiff_p.stem}', file=f'tetra3/{tiff_p.name}', mode='tetra3', n_stars=len(m_entry.get('stars_in_fov') or []), ra_deg=m_entry.get('boresight_ra_deg'), dec_deg=m_entry.get('boresight_dec_deg'), focal_mm=float(m_entry.get('focal_mm') or 35.2911), pixel_um=float(m_entry.get('pixel_um') or 6.9)))
        return entries

    def resolve_dataset_image(self, rel: object) -> object:
        clean_rel: object = str(rel).replace('\\', '/').lstrip('/')
        if clean_rel.startswith('uploads/'):
            base_dir: object = self.root.joinpath('data', 'uploads').resolve()
            resolved: object = base_dir.joinpath(clean_rel[len('uploads/'):]).resolve()
        elif clean_rel.startswith('tetra3/'):
            base_dir: object = self.root.joinpath('data', 'tetra3').resolve()
            resolved: object = base_dir.joinpath(clean_rel[len('tetra3/'):]).resolve()
        else:
            base_dir: object = self.root.joinpath('data', 'sim_dataset').resolve()
            resolved: object = base_dir.joinpath(clean_rel).resolve()
        resolved.relative_to(base_dir)
        valid_exts: object = ('.tif', '.tiff', '.png', '.jpg', '.jpeg')
        if resolved.suffix.lower() not in valid_exts or not resolved.is_file():
            raise ValueError(f'Not a dataset frame: {rel}')
        return resolved

    def _prepare_frame(self, req: object, loaded_img: object, camera: object, catalog: object) -> object:
        if loaded_img is not None:
            sc_path: object = Path(req.sidecar) if req.sidecar else find_sidecar(Path(req.image), self.root)
            if sc_path is not None and sc_path.is_file():
                sc_meta: object = json_loads(sc_path.read_text(encoding='utf-8'))
                truth: object = truth_from_sidecar(sc_meta, catalog)
                have_gt: object = True
            else:
                sc_meta, truth, have_gt = (None, empty_truth(), False)
            omega: object = asarray((sc_meta or {}).get('omega_deg_s') or [0.0, 0.0, 0.0], dtype=float64)
            stressed: object = apply_loaded_stress(loaded_img, camera, catalog, self.radiometry, req)
            return (stressed, truth, truth.q_gt, omega, have_gt)
        gen: object = default_rng(req.seed)
        sim: object = SkySimulator(camera, catalog, radiometry=self.radiometry, seed=req.seed)
        if req.point_hr is not None:
            matches: object = where(catalog.ids == int(req.point_hr))[0]
            if not matches.size:
                raise ValueError(f'HR {req.point_hr} is not in {catalog.source} (V<={req.max_mag})')
            q_gt: object = looking_at(catalog.vectors[int(matches[0])])
        elif req.ra_deg is not None and req.dec_deg is not None:
            q_gt: object = looking_at_ra_dec(float(req.ra_deg), float(req.dec_deg))
        elif req.ra_deg is not None or req.dec_deg is not None:
            raise ValueError('Cần cả RA và Dec (độ, ICRS/J2000), không chỉ một trong hai')
        else:
            q_gt: object = SkySimulator.generate_random_quaternion(req.seed)
        omega: object = omega_vector(req.omega_axis, req.omega, gen)
        g_spec: object = glare_spec_from_req(req, camera)
        rendered, truth = sim.render(q_gt, omega_deg_s=omega, t_exp_s=req.exposure, glare=g_spec, false_stars=req.false_stars, add_noise=True, sky_clutter=str(req.sky_clutter or 'none'))
        return (rendered, truth, q_gt, omega, True)

    def run(self, req: object) -> object:
        loaded_img: object = load_frame(Path(req.image)) if req.image is not None else None
        camera, scale, mode, locked = resolve_run_camera(req, loaded_img, self.cam_full)
        t_max: object = theta_max_deg_for_fov(float(camera.fov_deg[2]))
        catalog, synthetic, kvector = self.stack(req.catalog, req.max_mag, t_max)
        image, truth, q_gt, omega, have_gt = self._prepare_frame(req, loaded_img, camera, catalog)
        is_small: object = locked and scale > 1 or (not locked and camera.width * camera.height < 4000000)
        cfg: object = load_pipeline_cfg('fast' if is_small else 'full', self.root)
        tol_arc: object = None if locked else match_tolerance_arcsec(camera, req.angular_tol_arcsec)
        if tol_arc is not None:
            cfg.angular_tol_rad = float(tol_arc) / ARCSEC_PER_RAD
            cfg.attitude_error_limit_arcsec = float(tol_arc)
            cfg.tol_frac = 0.0 if (camera.has_distortion and float(camera.fov_deg[2]) > 40.0) else 0.008
        if float(camera.fov_deg[2]) > 40.0:
            cfg.cutoff = min(int(cfg.cutoff), 400)
        cfg.solver = req.solver
        cfg.centroid_backend = self._normalize_backend(req.centroid_backend)
        pipe: object = self._build_pipeline(camera, catalog, kvector, cfg)
        result: object = pipe.process_frame(image)
        if cfg.centroid_backend in ('cnn', 'cnn_raw') and getattr(pipe.centroid_detector, '_model', None) is not None:
            self._cnn_cache = pipe.centroid_detector
        metrics: object = evaluate(result, truth, cfg.attitude_error_limit_arcsec, have_gt=have_gt)
        status_val, reject_val, match_stats = _extract_match_verification(result, metrics, cfg)
        fov_rows: object = star_rows_from_indices(catalog, truth.cat_idx, uv=truth.uv_mid, mags=truth.vis_mags)
        ident_rows: object = []
        if result.ident is not None and len(result.ident.cat_idx):
            obs_indices: object = result.ident.obs_idx
            id_uv: object = result.centroids.uv[obs_indices] if result.centroids is not None and result.centroids.uv is not None else None
            ident_rows = star_rows_from_indices(catalog, result.ident.cat_idx, uv=id_uv)
            for row_rec, obs_i in zip(ident_rows, obs_indices):
                row_rec['obs_idx'] = int(obs_i)
        det_uv_list: object = [[round(float(u), 2), round(float(v), 2)] for u, v in asarray(result.centroids.uv, dtype=float64)] if result.centroids is not None and getattr(result.centroids, 'uv', None) is not None and len(result.centroids.uv) else []
        fov: object = camera.fov_deg
        out_dir: object = Path(req.out_dir) if req.out_dir else self.root.joinpath('data', 'outputs')
        out_dir.mkdir(parents=True, exist_ok=True)
        png_path: object = out_dir / 'demo_result.png'
        input_png: object = out_dir / 'demo_input.png'
        output_png: object = out_dir / 'demo_output.png'
        clean_png: object = out_dir / 'demo_clean.png'
        stats: object = image_stats(image)
        if req.save_png:
            if not req.show:
                import matplotlib
                matplotlib.use('Agg')
            save_clean_png(image, clean_png)
            save_input_png(image, input_png, stats=stats)
            save_output_png(image, result, output_png, catalog=catalog, lookup=req.lookup, stats=stats)
            cam_lbl: object = f'Optics     : f {camera.focal_mm:.4g} mm   pixel {camera.pixel_um:.4g} um\nFrame      : {camera.width} x {camera.height}   fx {camera.fx:.1f} px\nFOV        : {fov[0]:.2f} x {fov[1]:.2f} deg   diag {fov[2]:.2f} deg'
            plot_frame(image, result, truth, metrics, cam_lbl, png_path, show=req.show, catalog=catalog, lookup=req.lookup)
        q_est: object = None if result.q is None else asarray(result.q, dtype=float64)
        det_obj: object = pipe.centroid_detector
        dl_bytes: object = result.to_downlink_bytes()
        theta_max_actual: object = float(degrees(kvector.theta_max))
        bore_est_dict: object = None if metrics.get('boresight_est_ra_deg') is None else dict(ra_deg=metrics['boresight_est_ra_deg'], dec_deg=metrics['boresight_est_dec_deg'], ra_hms=metrics['boresight_est_ra_hms'], dec_dms=metrics['boresight_est_dec_dms'], frame='Trục quang học +Z trong hệ quy chiếu J2000')
        bore_gt_dict: object = None if not have_gt else dict(ra_deg=metrics['boresight_gt_ra_deg'], dec_deg=metrics['boresight_gt_dec_deg'], ra_hms=metrics['boresight_gt_ra_hms'], dec_dms=metrics['boresight_gt_dec_dms'])
        payload: object = dict(mode=mode, scale=scale, seed=None if req.image is not None else req.seed, source='dataset' if req.image is not None else 'simulator', source_image=None if req.image is None else str(req.image), synthetic_catalog=synthetic, catalog_source=catalog.source, n_catalog=catalog.num_stars, radiometry_assumption=True, glare=req.glare, centroid_backend=cfg.centroid_backend, centroid_detector=getattr(det_obj, 'last_backend', cfg.centroid_backend), centroid_fallback=bool(getattr(det_obj, 'last_fallback', False)), centroid_error=getattr(det_obj, 'last_error', None), centroid_n_raw=getattr(det_obj, 'last_n_raw', None), centroid_n_after_gate=getattr(det_obj, 'last_n_after_gate', None), sky_clutter=req.sky_clutter, have_gt=have_gt, success=bool(result.success), status=status_val, reject_code=reject_val, match_stats=_jsonable(match_stats), error=result.error, q_gt=q_gt.tolist() if have_gt else None, q_est=None if q_est is None else q_est.tolist(), q_gt_text=fmt_q(q_gt) if have_gt else 'n/a', q_est_text=fmt_q(q_est), boresight_est=bore_est_dict, boresight_gt=bore_gt_dict, metrics=_jsonable(metrics), timing_ms=result.timing_ms, downlink_hex=dl_bytes.hex(), downlink_bytes=len(dl_bytes), camera=dict(width=camera.width, height=camera.height, pixel_um=camera.pixel_um, focal_mm=camera.focal_mm, fx_px=float(camera.fx), fov_deg=[float(fov[0]), float(fov[1])], fov_diag_deg=float(fov[2]), ifov_arcsec=float(camera.ifov_arcsec), principal_point=[float(camera.cx), float(camera.cy)], optics='locked' if locked else 'custom', match_tol_arcsec=float(cfg.angular_tol_rad) * ARCSEC_PER_RAD), angle_table=dict(theta_min_deg=THETA_MIN_DEG, theta_max_deg=theta_max_actual, n_pairs=int(kvector.num_pairs), fov_diagonal_deg=float(fov[2]), built_now=bool(self.last_angle_build), note=angle_table_note(float(fov[2]), theta_max_actual, int(kvector.num_pairs), bool(self.last_angle_build))), ingest_note=_ingest_note(req.image), hardware=dict(platform='laptop demo', camera='APS-C 24 MP, 50 mm lens', array=f'{camera.width} x {camera.height}', pixel_um=float(camera.pixel_um), focal_mm=float(camera.focal_mm), fov=f'{fov[0]:.2f} x {fov[1]:.2f} deg'), matched_catalog_ids=catalog.ids[result.ident.cat_idx].tolist() if result.ident is not None and len(result.ident.cat_idx) else [], detected_uv=det_uv_list, stars_in_fov=fov_rows, identified_stars=ident_rows, n_unidentified=max(0, int(metrics['n_detected'] - metrics['n_matched'])), compare=_jsonable(_compare_rows(q_gt if have_gt else None, q_est, metrics, have_gt, cfg, match_stats=match_stats)), sim_method=SIM_METHOD, point_hr=req.point_hr, point_ra_deg=req.ra_deg, point_dec_deg=req.dec_deg, n_iau_hr_names=n_named_hr(), n_iau_names=n_iau_names(), png='data/outputs/demo_result.png' if req.save_png else None, input_png='data/outputs/demo_input.png' if req.save_png else None, output_png='data/outputs/demo_output.png' if req.save_png else None, clean_png='data/outputs/demo_clean.png' if req.save_png else None, input_stats=stats)
        out_dir.joinpath('demo_result.json').write_text(json_dumps(payload, indent=2), encoding='utf-8')
        if req.save_raw and req.image is None:
            imwrite(str(out_dir / 'demo_raw.tif'), image)
            raw_meta: object = dict(q_gt=q_gt.tolist(), omega_deg_s=asarray(omega).tolist(), t_exp_s=req.exposure, stars_in_fov=fov_rows)
            out_dir.joinpath('demo_raw.json').write_text(json_dumps(raw_meta, indent=2), encoding='utf-8')
        return RunOutcome(success=bool(result.success), payload=payload, image=image, result=result, truth=truth, metrics=metrics, catalog=catalog, camera=camera, png_path=png_path if req.save_png else None, have_gt=have_gt, error=result.error)

    def compare(self, req: object, backends: tuple[str, ...]=('classical', 'tetra3', 'cnn')) -> dict:
        """Run multiple centroid backends on the exact same pixel frame for live head-to-head comparison."""
        loaded_img: object = load_frame(Path(req.image)) if req.image is not None else None
        camera, scale, mode, locked = resolve_run_camera(req, loaded_img, self.cam_full)
        t_max: object = theta_max_deg_for_fov(float(camera.fov_deg[2]))
        catalog, synthetic, kvector = self.stack(req.catalog, req.max_mag, t_max)
        image, truth, q_gt, _, have_gt = self._prepare_frame(req, loaded_img, camera, catalog)
        gt_source: str = 'simulator_ground_truth' if (req.image is None) else ('sidecar_json' if have_gt else 'none')
        if not have_gt and req.image is not None:
            m_truth, m_src = self._manifest_truth_for(req.image)
            if m_truth is not None:
                truth = m_truth
                q_gt = m_truth.q_gt
                have_gt = True
                gt_source = str(m_src)

        out_dir: object = Path(req.out_dir) if req.out_dir else self.root.joinpath('data', 'outputs')
        out_dir.mkdir(parents=True, exist_ok=True)
        clean_png: object = out_dir / 'demo_compare_clean.png'
        save_clean_png(image, clean_png)
        stats: object = image_stats(image)
        fov: object = camera.fov_deg
        is_small: object = locked and scale > 1 or (not locked and camera.width * camera.height < 4000000)

        labels = {
            'classical': 'CoG (Nhóm)',
            'tetra3': 'Ngưỡng kiểu tetra3',
            'cnn': 'CNN-Hybrid (MobileUNet + CoG)',
            'cnn_raw': 'CNN gốc (Trilateration)',
        }
        methods_out: dict = {}
        for raw_be in backends:
            be_norm = self._normalize_backend(raw_be)
            cfg: object = load_pipeline_cfg('fast' if is_small else 'full', self.root)
            tol_arc: object = None if locked else match_tolerance_arcsec(camera, req.angular_tol_arcsec)
            if tol_arc is not None:
                cfg.angular_tol_rad = float(tol_arc) / ARCSEC_PER_RAD
                cfg.attitude_error_limit_arcsec = float(tol_arc)
                cfg.tol_frac = 0.0 if (camera.has_distortion and float(camera.fov_deg[2]) > 40.0) else 0.008
            if float(camera.fov_deg[2]) > 40.0:
                cfg.cutoff = min(int(cfg.cutoff), 400)
            cfg.solver = req.solver
            cfg.centroid_backend = be_norm
            pipe: object = self._build_pipeline(camera, catalog, kvector, cfg)
            result: object = pipe.process_frame(image)
            if be_norm in ('cnn', 'cnn_raw') and getattr(pipe.centroid_detector, '_model', None) is not None:
                self._cnn_cache = pipe.centroid_detector
            metrics: object = evaluate(result, truth, cfg.attitude_error_limit_arcsec, have_gt=have_gt)
            status_val, reject_val, match_stats = _extract_match_verification(result, metrics, cfg)
            ident_rows: object = []
            if result.ident is not None and len(result.ident.cat_idx):
                obs_indices: object = result.ident.obs_idx
                id_uv: object = result.centroids.uv[obs_indices] if result.centroids is not None and result.centroids.uv is not None else None
                ident_rows = star_rows_from_indices(catalog, result.ident.cat_idx, uv=id_uv)
                for row_rec, obs_i in zip(ident_rows, obs_indices):
                    row_rec['obs_idx'] = int(obs_i)
            det_uv_list: object = [[round(float(u), 2), round(float(v), 2)] for u, v in asarray(result.centroids.uv, dtype=float64)] if result.centroids is not None and getattr(result.centroids, 'uv', None) is not None and len(result.centroids.uv) else []
            bore_est = None if metrics.get('boresight_est_ra_deg') is None else dict(
                ra_deg=metrics['boresight_est_ra_deg'],
                dec_deg=metrics['boresight_est_dec_deg'],
                ra_hms=metrics['boresight_est_ra_hms'],
                dec_dms=metrics['boresight_est_dec_dms'],
            )
            det_obj = pipe.centroid_detector
            methods_out[be_norm] = _jsonable(dict(
                key=be_norm,
                label=labels.get(be_norm, be_norm),
                status=status_val,
                success=bool(result.success),
                reject_code=reject_val,
                verdict=metrics.get('verdict'),
                e2e_outcome=metrics.get('e2e_outcome'),
                attitude_error_arcsec=metrics.get('attitude_error_arcsec'),
                limit_arcsec=float(cfg.attitude_error_limit_arcsec),
                n_detected=int(metrics.get('n_detected') or 0),
                n_initial_matched=match_stats.get('n_initial_matched'),
                n_valid_pairs=int(match_stats.get('n_valid_pairs') or 0),
                n_rejected_outliers=int(match_stats.get('n_rejected_outliers') or 0),
                rms_residual_arcsec=match_stats.get('rms_residual_arcsec'),
                max_residual_arcsec=match_stats.get('max_residual_arcsec'),
                centroid_precision=metrics.get('centroid_precision'),
                centroid_recall=metrics.get('centroid_recall'),
                centroid_f1=metrics.get('centroid_f1'),
                centroid_n_false_pos=metrics.get('centroid_n_false_pos'),
                centroid_rms_5px=metrics.get('centroid_rms_5px'),
                timing_ms=result.timing_ms,
                boresight_est=bore_est,
                centroid_detector=getattr(det_obj, 'last_backend', be_norm),
                centroid_mode=getattr(det_obj, 'last_mode', be_norm),
                centroid_fallback=bool(getattr(det_obj, 'last_fallback', False)),
                detected_uv=det_uv_list,
                identified_stars=ident_rows,
                error=result.error,
            ))

        gt_uv_list = [[round(float(u), 2), round(float(v), 2)] for u, v in asarray(truth.uv_mid, dtype=float64)] if have_gt and len(truth.uv_mid) else []
        return _jsonable(dict(
            clean_url='/output/demo_compare_clean.png',
            source='dataset' if req.image is not None else 'simulator',
            source_image=None if req.image is None else str(Path(req.image).name),
            seed=None if req.image is not None else req.seed,
            glare=req.glare,
            sky_clutter=req.sky_clutter,
            have_gt=have_gt,
            gt_source=gt_source,
            n_gt_stars=len(gt_uv_list),
            gt_uv=gt_uv_list,
            catalog_source=catalog.source,
            synthetic_catalog=synthetic,
            camera=dict(
                width=camera.width,
                height=camera.height,
                pixel_um=float(camera.pixel_um),
                focal_mm=float(camera.focal_mm),
                fov_deg=[float(fov[0]), float(fov[1])],
                fov_diag_deg=float(fov[2]),
                ifov_arcsec=float(camera.ifov_arcsec),
                has_distortion=bool(camera.has_distortion),
            ),
            input_stats=stats,
            order=[self._normalize_backend(b) for b in backends],
            methods=methods_out,
        ))
