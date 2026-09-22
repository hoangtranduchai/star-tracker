"""Shared execution session for CLI and Web UI: synthetic sky generation and lost-in-space solving."""
from json import dumps as json_dumps, loads as json_loads
from math import ceil as math_ceil
from pathlib import Path
from cv2 import COLOR_BGR2GRAY, IMREAD_UNCHANGED, cvtColor, imread, imwrite
from numpy import asarray, clip, column_stack, degrees, float32, float64, floating, full, integer, ndarray, where, zeros, zeros_like
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
from .visualize import image_stats, plot_frame, save_input_png, save_output_png
ROOT = Path(__file__).resolve().parents[1]
_LOCKED_CAM = demo_camera()
TOL_ARCSEC_PER_PIXEL = 0.88
THETA_MIN_DEG = 0.02
THETA_MAX_LOCKED_DEG = 30.5
MAX_SIM_PIXELS = 20000000
_RAD_DEFAULTS = dict(e_per_s_v0=3300000.0, qe=1.0, read_noise_e=5.0, dark_e_per_s=10.0, gain_dn_per_e=1.0, full_well_e=12000.0, bit_depth=12, bias_dn=64.0, hot_pixel_frac=1e-05, cosmic_rate_per_frame=2.0)
_RUN_REQ_DEFAULTS = dict(mode='fast', scale=None, seed=42, catalog='bsc5', max_mag=6.0, omega=0.06, omega_axis='y', exposure=0.15, glare='none', sky_clutter='none', false_stars=0, solver='svd', centroid_backend='classical', image=None, sidecar=None, out_dir=None, lookup=True, save_png=True, save_raw=False, show=False, point_hr=None, ra_deg=None, dec_deg=None, focal_mm=None, pixel_um=None, image_width=None, image_height=None, angular_tol_arcsec=None)

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
        mnt_cam: object = CameraModel(width=1024, height=1024, pixel_um=4.1, focal_mm=4.2)
        return (mnt_cam, 1, 'custom')
    raise ValueError(f'Ảnh {w_px}×{h_px} không phải khung demo {cam_full.width}×{cam_full.height} (FULL) hay {fast_cam.width}×{fast_cam.height} (FAST). Nhập tiêu cự thật (mm) và cạnh pixel của đúng file (µm).')

def uses_custom_optics(req: object) -> object:
    opt_fields: object = (req.focal_mm, req.pixel_um, req.image_width, req.image_height, req.angular_tol_arcsec)
    return any((val is not None for val in opt_fields))

def theta_max_deg_for_fov(diag_deg: object) -> object:
    d_val: object = float(diag_deg)
    if d_val <= THETA_MAX_LOCKED_DEG + 1e-09:
        return THETA_MAX_LOCKED_DEG
    rounded_half: object = math_ceil((d_val + 0.5) * 2.0 - 1e-09) * 0.5
    return float(min(180.0, rounded_half))

def _camera_from_numbers(width: object, height: object, pixel_um: object, focal_mm: object) -> object:
    w_i, h_i = (int(width), int(height))
    px_f, fl_f = (float(pixel_um), float(focal_mm))
    if w_i < 16 or h_i < 16:
        raise ValueError('Số cột và số hàng phải từ 16 trở lên.')
    if fl_f <= 0.0 or px_f <= 0.0:
        raise ValueError('Tiêu cự (mm) và cạnh pixel (µm) phải là số dương.')
    if fl_f > 5000.0 or px_f > 200.0:
        raise ValueError('Tiêu cự hoặc cạnh pixel nằm ngoài khoảng dùng để giải.')
    return CameraModel(width=w_i, height=h_i, pixel_um=px_f, focal_mm=fl_f)

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
            return (cam, sc, md, True)
        preset: object = _locked_camera_for_size(w_px, h_px, cam_full)
        fl: object = req.focal_mm if req.focal_mm is not None else preset.focal_mm if preset else None
        px: object = req.pixel_um if req.pixel_um is not None else preset.pixel_um if preset else None
        if fl is None or px is None:
            fast_c: object = cam_full.downscaled(4)
            raise ValueError(f'Ảnh {w_px}×{h_px} không khớp khung demo {cam_full.width}×{cam_full.height} hoặc {fast_c.width}×{fast_c.height}. Nhập tiêu cự thật (mm) và cạnh pixel của đúng file (µm).')
        return (_camera_from_numbers(w_px, h_px, px, fl), 1, 'custom', False)
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
    tail: object = f'Bảng K-vector (0,02°–{theta_max_deg:.1f}°) gồm {n_pairs:,} cặp sao, tra cứu O(1) trên mảng góc đơn điệu chỉ duyệt đúng dải dung sai.'
    if diag_deg <= THETA_MAX_LOCKED_DEG + 1e-06 and abs(theta_max_deg - THETA_MAX_LOCKED_DEG) < 1e-06:
        return f'Góc chéo nằm gọn trong phạm vi bảng {THETA_MAX_LOCKED_DEG:.1f}° mặc định, dùng ngay không cần tạo lại. ' + tail
    if built_now:
        return f'Chéo trường nhìn {diag_deg:.2f}° rộng hơn {THETA_MAX_LOCKED_DEG:.1f}°. Đã dựng bảng tới {theta_max_deg:.1f}° và lưu lại. ' + tail
    return f'Góc chéo {diag_deg:.2f}° tra cứu trực tiếp trên bảng {theta_max_deg:.1f}° đã lưu bộ nhớ đệm. ' + tail

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
        c_idx: object = asarray([lookup_id[int(item['hr'])] for item in fov_list if int(item['hr']) in lookup_id], dtype=int)
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
        return value.tolist()
    if isinstance(value, (floating, integer)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value

def _ingest_note(path: object) -> object:
    if path is not None and Path(path).suffix.lower() in ('.jpg', '.jpeg', '.webp'):
        return 'Ảnh JPEG/WebP đã nén và chỉnh sáng. Tâm sao có thể lệch so với TIFF tuyến tính.'
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

def _compare_rows(q_gt: object, q_est: object, metrics: object, have_gt: object, cfg: object) -> object:
    q_labels: object = ('q0 (scalar)', 'q1', 'q2', 'q3')
    rows: object = [dict(param=lbl, gt=None if not have_gt or q_gt is None else float(q_gt[idx]), est=None if q_est is None else float(q_est[idx]), delta=None if not have_gt or q_gt is None or q_est is None else float(q_est[idx] - q_gt[idx]), unit='', note='quy ước phần tử vô hướng đứng đầu (q và -q cùng biểu diễn một tư thế)' if idx == 0 else '') for idx, lbl in enumerate(q_labels)]
    coord_specs: object = (('RA', 'boresight_gt_ra_deg', 'boresight_est_ra_deg', format_ra_both), ('Dec', 'boresight_gt_dec_deg', 'boresight_est_dec_deg', format_dec_both))
    for tag, gt_key, est_key, fmt_fn in coord_specs:
        g_val, e_val = (metrics.get(gt_key), metrics.get(est_key))
        rows.append(dict(param=f'Boresight {tag} (camera +Z)', gt=None if g_val is None else fmt_fn(g_val), est=None if e_val is None else fmt_fn(e_val), delta=None if g_val is None or e_val is None else float(e_val - g_val), unit='deg', gt_deg=g_val, est_deg=e_val, note='not lat/lon; độ và h/m/s (Stellarium)'))
    att_err: object = metrics.get('attitude_error_arcsec')
    lim_arc: object = float(cfg.attitude_error_limit_arcsec)
    rows.append(dict(param='Attitude error', gt='0 (ideal)' if have_gt else '—', est=att_err, delta=att_err, unit='arcsec', limit_arcsec=lim_arc, note=f"limit {lim_arc:g} arcsec  ({metrics.get('verdict')})"))
    nt, nd, nm = (metrics.get('n_truth'), metrics.get('n_detected'), metrics.get('n_matched'))
    rows.append(dict(param='Stars FOV / detected / matched', gt=None if nt is None else f'{int(nt)} FOV', est=None if nd is None else f'{int(nd)} detect', delta=None if nm is None else f'{int(nm)} ID', unit='', note='giá trị Δ hiển thị tổng số sao khớp mẫu Pyramid'))
    rows.append(dict(param='Centroid RMS', gt=None, est=metrics.get('centroid_rms_px'), delta=None, unit='px', note='vs sim GT centroids'))
    return rows
SIM_METHOD = dict(generated_by_code=True, module='src.simulator.SkySimulator.render', not_iso_ccsds=True, practice_class='catalog + pinhole + PSF + detector noise + quaternion GT', same_class_as=['UW LOST --generate', 'ESA tetra3 synthetic tests', 'NASA COTS (math, not NOSA copy)'], demo_optics='APS-C 6000x4000, 3.72 um, 50 mm lens', radiometry='assumption=true, not a camera datasheet', steps=['Sinh quaternion chuẩn q_GT phân bố đều trên SO(3) từ seed cố định', 'Trích xuất vector đơn vị J2000 từ danh mục sao sáng Yale BSC5 (V<=6.0)', 'Chiếu tâm lỗ kim các tia sao b = A(q_GT)*r lên mặt phẳng cảm biến APS-C', 'Mô phỏng hàm truyền điểm PSF Gauss và vệt dịch chuyển theo vận tốc góc', 'Cộng nhiễu hạt photon, nhiễu đọc và lượng tử hóa về ảnh số 12-bit (uint16)', 'Thuật toán giải mù hoàn toàn từ mảng điểm ảnh để khôi phục tư thế q_est'])

class DemoEngine:
    """Stateful runner caching star catalogs and K-vector indices across runs."""

    def __init__(self, root: object=None) -> object:
        self.root = Path(root) if root else ROOT
        self.specs = load_specs(self.root)
        self.cam_full = demo_camera()
        self.radiometry = radiometry_from_specs(self.specs)
        self._stack = {}
        self.last_angle_build = False

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
        sim_root: object = self.root.joinpath('data', 'sim_dataset').resolve()
        if not sim_root.exists():
            return []
        entries: object = []
        for sub_dir in sorted((p for p in sim_root.iterdir() if p.is_dir())):
            md_name: object = sub_dir.name
            for tif_p in sorted(sub_dir.glob('*.tif')):
                sc_p: object = tif_p.with_suffix('.json')
                meta: object = json_loads(sc_p.read_text(encoding='utf-8')) if sc_p.exists() else {}
                bore: object = meta.get('boresight') or {}
                entries.append(dict(id=f'{md_name}/{tif_p.stem}', file=f'{md_name}/{tif_p.name}', mode=md_name, n_stars=len(meta.get('stars_in_fov') or []), ra_deg=bore.get('ra_deg'), dec_deg=bore.get('dec_deg')))
        return entries

    def resolve_dataset_image(self, rel: object) -> object:
        clean_rel: object = str(rel).replace('\\', '/').lstrip('/')
        if clean_rel.startswith('uploads/'):
            base_dir: object = self.root.joinpath('data', 'uploads').resolve()
            resolved: object = base_dir.joinpath(clean_rel[len('uploads/'):]).resolve()
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
            cfg.tol_frac = 0.008
        cfg.solver = req.solver
        be_key: object = str(req.centroid_backend or 'classical').lower().strip()
        cfg.centroid_backend = 'cnn' if be_key in ('cnn', 'cnn_zhao2024', 'zhao', 'mobileunet') else 'classical'
        pipe: object = StarTrackerPipeline(camera, catalog, kvector, cfg)
        result: object = pipe.process_frame(image)
        metrics: object = evaluate(result, truth, cfg.attitude_error_limit_arcsec, have_gt=have_gt)
        fov_rows: object = star_rows_from_indices(catalog, truth.cat_idx, uv=truth.uv_mid, mags=truth.vis_mags)
        ident_rows: object = []
        if result.ident is not None and len(result.ident.cat_idx):
            id_uv: object = result.centroids.uv[result.ident.obs_idx] if result.centroids is not None else None
            ident_rows: object = star_rows_from_indices(catalog, result.ident.cat_idx, uv=id_uv)
        fov: object = camera.fov_deg
        out_dir: object = Path(req.out_dir) if req.out_dir else self.root.joinpath('data', 'outputs')
        out_dir.mkdir(parents=True, exist_ok=True)
        png_path: object = out_dir / 'demo_result.png'
        input_png: object = out_dir / 'demo_input.png'
        output_png: object = out_dir / 'demo_output.png'
        stats: object = image_stats(image)
        if req.save_png:
            if not req.show:
                import matplotlib
                matplotlib.use('Agg')
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
        payload: object = dict(mode=mode, scale=scale, seed=None if req.image is not None else req.seed, source='dataset' if req.image is not None else 'simulator', source_image=None if req.image is None else str(req.image), synthetic_catalog=synthetic, catalog_source=catalog.source, n_catalog=catalog.num_stars, radiometry_assumption=True, glare=req.glare, centroid_backend=cfg.centroid_backend, centroid_detector=getattr(det_obj, 'last_backend', cfg.centroid_backend), centroid_fallback=bool(getattr(det_obj, 'last_fallback', False)), centroid_error=getattr(det_obj, 'last_error', None), centroid_n_raw=getattr(det_obj, 'last_n_raw', None), centroid_n_after_gate=getattr(det_obj, 'last_n_after_gate', None), sky_clutter=req.sky_clutter, have_gt=have_gt, success=bool(result.success), error=result.error, q_gt=q_gt.tolist() if have_gt else None, q_est=None if q_est is None else q_est.tolist(), q_gt_text=fmt_q(q_gt) if have_gt else 'n/a', q_est_text=fmt_q(q_est), boresight_est=bore_est_dict, boresight_gt=bore_gt_dict, metrics=_jsonable(metrics), timing_ms=result.timing_ms, downlink_hex=dl_bytes.hex(), downlink_bytes=len(dl_bytes), camera=dict(width=camera.width, height=camera.height, pixel_um=camera.pixel_um, focal_mm=camera.focal_mm, fx_px=float(camera.fx), fov_deg=[float(fov[0]), float(fov[1])], fov_diag_deg=float(fov[2]), ifov_arcsec=float(camera.ifov_arcsec), principal_point=[float(camera.cx), float(camera.cy)], optics='locked' if locked else 'custom', match_tol_arcsec=float(cfg.angular_tol_rad) * ARCSEC_PER_RAD), angle_table=dict(theta_min_deg=THETA_MIN_DEG, theta_max_deg=theta_max_actual, n_pairs=int(kvector.num_pairs), fov_diagonal_deg=float(fov[2]), built_now=bool(self.last_angle_build), note=angle_table_note(float(fov[2]), theta_max_actual, int(kvector.num_pairs), bool(self.last_angle_build))), ingest_note=_ingest_note(req.image), hardware=dict(platform='laptop demo', camera='APS-C 24 MP, 50 mm lens', array=f'{camera.width} x {camera.height}', pixel_um=float(camera.pixel_um), focal_mm=float(camera.focal_mm), fov=f'{fov[0]:.2f} x {fov[1]:.2f} deg'), matched_catalog_ids=catalog.ids[result.ident.cat_idx].tolist() if result.ident is not None and len(result.ident.cat_idx) else [], stars_in_fov=fov_rows, identified_stars=ident_rows, n_unidentified=int(metrics['n_detected'] - metrics['n_matched']), compare=_compare_rows(q_gt if have_gt else None, q_est, metrics, have_gt, cfg), sim_method=SIM_METHOD, point_hr=req.point_hr, point_ra_deg=req.ra_deg, point_dec_deg=req.dec_deg, n_iau_hr_names=n_named_hr(), n_iau_names=n_iau_names(), png='data/outputs/demo_result.png' if req.save_png else None, input_png='data/outputs/demo_input.png' if req.save_png else None, output_png='data/outputs/demo_output.png' if req.save_png else None, input_stats=stats)
        out_dir.joinpath('demo_result.json').write_text(json_dumps(payload, indent=2), encoding='utf-8')
        if req.save_raw and req.image is None:
            imwrite(str(out_dir / 'demo_raw.tif'), image)
            raw_meta: object = dict(q_gt=q_gt.tolist(), omega_deg_s=asarray(omega).tolist(), t_exp_s=req.exposure, stars_in_fov=fov_rows)
            out_dir.joinpath('demo_raw.json').write_text(json_dumps(raw_meta, indent=2), encoding='utf-8')
        return RunOutcome(success=bool(result.success), payload=payload, image=image, result=result, truth=truth, metrics=metrics, catalog=catalog, camera=camera, png_path=png_path if req.save_png else None, have_gt=have_gt, error=result.error)
