"""Flask web interface for the star tracker simulator and lost-in-space attitude solver."""
from json import loads as json_loads
from math import isfinite
import os
from pathlib import Path
import secrets
import sys
from threading import Event, Lock, Thread, Timer
import time
from webbrowser import open as open_browser
from flask import Flask, Response, jsonify, make_response, render_template, request, send_from_directory
import matplotlib
BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
matplotlib.use('Agg')
from src.centroid_cnn import weights_available as _weights_available
from src.demo_session import DemoEngine, RunRequest, SIM_METHOD
from src.execution_log import read_execution_log, record_data_deletion, record_pipeline_run
from src.quaternion import format_dec_both, format_dec_stellarium, format_ra_both, format_ra_hms, parse_dec_deg, parse_ra_deg, split_radec_text
from src.repro_bundle import verify_repro_bundle
from src.starnames import describe_index, n_iau_names, n_named_hr
from src.upload_store import DEFAULT_SWEEP_INTERVAL_S, SESSION_COOKIE_NAME, cleanup_expired_uploads, delete_all_uploads, delete_upload, encode_png_data_uri, list_uploads, normalize_retention_mode, normalize_session_id, resolve_upload_preview, save_uploaded_files, storage_policy_summary
app = Flask(__name__, template_folder=str(BASE.joinpath('web', 'templates')), static_folder=str(BASE.joinpath('web', 'static')))
app.config.update(SEND_FILE_MAX_AGE_DEFAULT=0, TEMPLATES_AUTO_RELOAD=True, MAX_CONTENT_LENGTH=80 * 1024 * 1024)
app.jinja_env.auto_reload = True
app.jinja_env.cache = {}
ENGINE = DemoEngine(BASE)
LOCK = Lock()
_SKY_CATALOG_CACHE = {}
_SKY_CACHE_LOCK = Lock()
_PLOT_STATE_LOCK = Lock()
_PLOT_RENDER_LOCK = Lock()
_PLOT_READY = Event()
_PLOT_READY.set()
_PLOT_GEN = 0
_STATIC_PLOT_NAMES = ('demo_input.png', 'demo_output.png', 'demo_result.png')
_VALID_BACKENDS = ('auto', 'adaptive', 'hybrid_auto', 'classical', 'tetra3', 'tetra3_threshold', 'cnn', 'cnn_hybrid', 'cnn_raw', 'cnn_zhao2024', 'zhao', 'mobileunet')
_UPLOAD_EXTS = ('.tif', '.tiff', '.png', '.jpg', '.jpeg', '.webp', '.npy')
_FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="7" fill="#05070B"/>'
    '<circle cx="16" cy="16" r="9" fill="none" stroke="#38BDF8" stroke-width="1.5" opacity="0.75"/>'
    '<path d="M16 4v6M16 22v6M4 16h6M22 16h6" stroke="#7DD3FC" stroke-width="1.5" stroke-linecap="round"/>'
    '<circle cx="16" cy="16" r="2.2" fill="#F8FAFC"/>'
    '</svg>'
).encode('utf-8')

class EngineBusy(RuntimeError):
    """Raised when a concurrent `/api/run` request is already executing."""

def _is_blank(val: object) -> object:
    return val is None or not str(val).strip()

def _body_float(body: object, key: object, default: object) -> object:
    raw: object = body.get(key)
    return default if _is_blank(raw) else float(raw)

def _opt_float(getter: object, key: object) -> object:
    raw: object = getter(key)
    return None if _is_blank(raw) else float(raw)

def _opt_int(getter: object, key: object) -> object:
    raw: object = getter(key)
    return None if _is_blank(raw) else int(float(raw))

def _optics_from(getter: object) -> object:
    return dict(focal_mm=_opt_float(getter, 'focal_mm'), pixel_um=_opt_float(getter, 'pixel_um'), image_width=_opt_int(getter, 'image_width'), image_height=_opt_int(getter, 'image_height'), angular_tol_arcsec=_opt_float(getter, 'angular_tol_arcsec'), k1=_opt_float(getter, 'k1'), k2=_opt_float(getter, 'k2'))

def _body_radec(body: object) -> object:
    pasted: object = body.get('radec_paste')
    ra_in, dec_in = (body.get('ra_deg'), body.get('dec_deg'))
    if not _is_blank(pasted):
        cleaned: object = str(pasted).strip()
        split_pair: object = split_radec_text(cleaned)
        if split_pair:
            ra_in, dec_in = split_pair
        elif _is_blank(ra_in):
            ra_in: object = cleaned
    elif not _is_blank(ra_in):
        split_pair: object = split_radec_text(str(ra_in))
        if split_pair and _is_blank(dec_in):
            ra_in, dec_in = split_pair
    no_ra, no_dec = (_is_blank(ra_in), _is_blank(dec_in))
    if no_ra and no_dec:
        return (None, None)
    if no_ra or no_dec:
        raise ValueError('Vui lòng nhập đủ cả RA và Dec (ví dụ: 18h 37m 51.2s  +38°48\'46.2").')
    fmt_tag: object = str(body.get('radec_fmt') or 'auto')
    return (parse_ra_deg(ra_in, fmt=fmt_tag), parse_dec_deg(dec_in, fmt=fmt_tag))

def _kickoff_static_plots(render_cb: object) -> None:
    global _PLOT_GEN
    if render_cb is None:
        return
    with _PLOT_STATE_LOCK:
        _PLOT_GEN += 1
        my_gen = _PLOT_GEN
        _PLOT_READY.clear()

    def _worker() -> None:
        try:
            with _PLOT_RENDER_LOCK:
                with _PLOT_STATE_LOCK:
                    if my_gen != _PLOT_GEN:
                        return
                render_cb()
        except Exception:
            pass
        finally:
            with _PLOT_STATE_LOCK:
                if my_gen == _PLOT_GEN:
                    _PLOT_READY.set()

    Thread(target=_worker, name='star-tracker-plots', daemon=True).start()

def _run_locked(req: object) -> object:
    if not LOCK.acquire(timeout=0.15):
        raise EngineBusy('Hệ thống đang xử lý khung ảnh trước đó. Vui lòng đợi giây lát rồi thử lại.')
    req.async_plots = True
    try:
        outcome: object = ENGINE.run(req)
    finally:
        LOCK.release()
    _kickoff_static_plots(getattr(outcome, 'render_static_plots', None))
    res_dict: object = dict(outcome.payload)
    res_dict.update(
        image_url='/output/demo_result.png',
        input_url='/output/demo_input.png',
        output_url='/output/demo_output.png',
        clean_url='/output/demo_clean.png',
    )
    return res_dict

def _run_upload_locked(req: object) -> dict:
    """Run an uploaded frame synchronously inside its isolated UUID slot (never touches global data/outputs/demo_*.png)."""
    if not LOCK.acquire(timeout=0.15):
        raise EngineBusy('Hệ thống đang xử lý khung ảnh trước đó. Vui lòng đợi giây lát rồi thử lại.')
    req.async_plots = False
    try:
        outcome: object = ENGINE.run(req)
    finally:
        LOCK.release()
    return dict(outcome.payload)

@app.after_request
def _no_cache(resp: object) -> object:
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

def _caller_session_id() -> str | None:
    return normalize_session_id(request.cookies.get(SESSION_COOKIE_NAME))

def _checkpoint_status_now(simulate_missing: bool) -> str:
    if simulate_missing:
        return 'simulated_missing'
    return 'available' if _weights_available() else 'missing'

@app.get('/')
def index() -> object:
    ds_frames: object = ENGINE.list_dataset_frames()
    resp = make_response(render_template('index.html', hardware=ENGINE.specs, sim_method=SIM_METHOD, frames=ds_frames, n_frames=len(ds_frames), n_iau_names=n_iau_names(), n_named_hr=n_named_hr()))
    if _caller_session_id() is None:
        is_https = bool(request.is_secure or request.headers.get('X-Forwarded-Proto', '').strip().lower() == 'https')
        resp.set_cookie(
            SESSION_COOKIE_NAME,
            secrets.token_hex(16),
            httponly=True,
            samesite='Lax',
            secure=is_https,
            path='/',
        )
    return resp

@app.get('/favicon.ico')
def favicon() -> object:
    return Response(_FAVICON_SVG, mimetype='image/svg+xml')

@app.get('/api/health')
def api_health() -> object:
    return jsonify(dict(ok=True, service='star-tracker'))

@app.get('/api/frames')
def api_frames() -> object:
    return jsonify(dict(frames=ENGINE.list_dataset_frames()))

@app.get('/api/sky-catalog')
def api_sky_catalog() -> object:
    kind: object = str(request.args.get('catalog') or 'bsc5').strip().lower()
    if kind not in ('bsc5', 'hipparcos'):
        return (jsonify(dict(error='catalog must be bsc5 or hipparcos')), 400)
    raw_mag: object = request.args.get('max_mag')
    try:
        mag_val: object = 6.0 if _is_blank(raw_mag) else float(raw_mag)
    except (TypeError, ValueError):
        return (jsonify(dict(error='max_mag must be a number')), 400)
    if not isfinite(mag_val):
        mag_val = 6.0
    max_mag: object = round(min(7.5, max(1.0, mag_val)), 3)
    cache_key: object = (kind, max_mag)
    cached: object = _SKY_CATALOG_CACHE.get(cache_key)
    if cached is not None:
        return jsonify(cached)
    with _SKY_CACHE_LOCK:
        cached = _SKY_CATALOG_CACHE.get(cache_key)
        if cached is None:
            cat, is_syn, _ = ENGINE.stack(kind, max_mag)
            vecs: object = cat.vectors
            names_map: object = {}
            for idx in range(cat.num_stars):
                rec: object = describe_index(cat, idx)
                iau_name: object = rec.get('iau_name')
                if iau_name:
                    names_map[str(rec['id'])] = str(iau_name)
            cached = dict(
                source=str(cat.source),
                synthetic=bool(is_syn),
                n=int(cat.num_stars),
                ids=[int(x) for x in cat.ids],
                vx=[round(float(v), 5) for v in vecs[:, 0]],
                vy=[round(float(v), 5) for v in vecs[:, 1]],
                vz=[round(float(v), 5) for v in vecs[:, 2]],
                mag=[round(float(m), 2) for m in cat.mags],
                names=names_map,
            )
            _SKY_CATALOG_CACHE[cache_key] = cached
    return jsonify(cached)

@app.post('/api/parse-radec')
def api_parse_radec() -> object:
    payload_in: object = request.get_json(silent=True) or {}
    try:
        ra_val, dec_val = _body_radec(payload_in)
        if ra_val is None:
            return jsonify(dict(ok=False, empty=True))
        return jsonify(dict(ok=True, ra_deg=ra_val, dec_deg=dec_val, ra_hms=format_ra_hms(ra_val), dec_dms=format_dec_stellarium(dec_val), ra_both=format_ra_both(ra_val), dec_both=format_dec_both(dec_val)))
    except Exception as err:
        return (jsonify(dict(ok=False, error=str(err))), 400)

def _bool_flag(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or '').strip().lower() in ('1', 'true', 'yes', 'on')

def _log_run_payload(endpoint: str, res_dict: dict, *, source_name: str, upload_id: str | None = None, retention_mode: str | None = None, deleted_immediately: bool | None = None) -> None:
    try:
        mstats = res_dict.get('match_stats') or {}
        met = res_dict.get('metrics') or {}
        timing = res_dict.get('timing_ms') or {}
        record_pipeline_run(
            BASE,
            endpoint=endpoint,
            source_type=str(res_dict.get('source', 'simulator')),
            source_name=source_name,
            requested_backend=str(res_dict.get('requested_backend', res_dict.get('centroid_backend', 'classical'))),
            executed_backend=str(res_dict.get('executed_backend', res_dict.get('centroid_detector', 'classical'))),
            fallback_triggered=bool(res_dict.get('centroid_fallback')),
            fallback_reason=res_dict.get('fallback_reason') or res_dict.get('centroid_error'),
            auto_router_used=bool(res_dict.get('auto_router_used')),
            auto_router_selected=res_dict.get('auto_router_selected'),
            auto_router_reason=res_dict.get('auto_router_reason'),
            status=str(res_dict.get('status', 'LOST')),
            reject_code=res_dict.get('reject_code'),
            n_valid_pairs=int(mstats.get('n_valid_pairs') or met.get('n_matched') or 0),
            n_detected=int(met.get('n_detected') or 0),
            latency_ms=timing.get('total_pipeline_ms'),
            checkpoint_status=res_dict.get('checkpoint_status'),
            upload_id=upload_id,
            retention_mode=retention_mode,
            deleted_immediately=deleted_immediately,
        )
    except Exception:
        pass

@app.post('/api/run')
def api_run() -> object:
    body: object = request.get_json(silent=True) or {}
    try:
        rel_img: object = body.get('image')
        resolved_img: object = ENGINE.resolve_dataset_image(str(rel_img)) if rel_img else None
        ra_val, dec_val = _body_radec(body)
        hr_val: object = int(body['point_hr']) if body.get('point_hr') else None
        sim_missing: bool = _bool_flag(body.get('simulate_missing_weights'))
        req: object = RunRequest(mode=str(body.get('mode') or 'fast'), seed=int(_body_float(body, 'seed', 42.0)), catalog=str(body.get('catalog') or 'bsc5'), max_mag=float(_body_float(body, 'max_mag', 6.0)), omega=float(_body_float(body, 'omega', 0.06)), omega_axis=str(body.get('omega_axis') or 'y'), exposure=float(_body_float(body, 'exposure', 0.15)), glare=str(body.get('glare') or 'none'), sky_clutter=str(body.get('sky_clutter') or 'none'), false_stars=int(_body_float(body, 'false_stars', 0.0)), solver=str(body.get('solver') or 'svd'), centroid_backend=str(body.get('centroid_backend') or 'classical'), simulate_missing_weights=sim_missing, point_hr=hr_val, ra_deg=ra_val, dec_deg=dec_val, image=resolved_img, out_dir=BASE.joinpath('data', 'outputs'), lookup=True, save_png=True, **_optics_from(body.get))
        if req.mode not in ('fast', 'full'):
            return (jsonify(dict(error='mode must be fast or full')), 400)
        if req.centroid_backend not in _VALID_BACKENDS:
            return (jsonify(dict(error='centroid_backend must be auto, classical, tetra3, or cnn')), 400)
        res_dict = _run_locked(req)
        src_nm = Path(str(resolved_img)).name if resolved_img else f'seed={req.seed}'
        _log_run_payload('/api/run', res_dict, source_name=src_nm)
        return jsonify(res_dict)
    except EngineBusy as busy_err:
        return (jsonify(dict(error=str(busy_err), busy=True)), 409)
    except Exception as err:
        return (jsonify(dict(error=str(err))), 400)

@app.post('/api/compare')
def api_compare() -> object:
    body: object = request.get_json(silent=True) or {}
    try:
        rel_img: object = body.get('image')
        resolved_img: object = ENGINE.resolve_dataset_image(str(rel_img)) if rel_img else None
        ra_val, dec_val = _body_radec(body)
        hr_val: object = int(body['point_hr']) if body.get('point_hr') else None
        sim_missing: bool = _bool_flag(body.get('simulate_missing_weights'))
        raw_backends: object = body.get('backends')
        if isinstance(raw_backends, list) and raw_backends:
            backends_tuple = tuple(str(b).strip().lower() for b in raw_backends if str(b).strip().lower() in _VALID_BACKENDS)
            if not backends_tuple:
                backends_tuple = ('classical', 'tetra3', 'cnn')
        else:
            backends_tuple = ('classical', 'tetra3', 'cnn')
        req: object = RunRequest(
            mode=str(body.get('mode') or 'fast'),
            seed=int(_body_float(body, 'seed', 42.0)),
            catalog=str(body.get('catalog') or 'bsc5'),
            max_mag=float(_body_float(body, 'max_mag', 6.0)),
            omega=float(_body_float(body, 'omega', 0.06)),
            omega_axis=str(body.get('omega_axis') or 'y'),
            exposure=float(_body_float(body, 'exposure', 0.15)),
            glare=str(body.get('glare') or 'none'),
            sky_clutter=str(body.get('sky_clutter') or 'none'),
            false_stars=int(_body_float(body, 'false_stars', 0.0)),
            solver=str(body.get('solver') or 'svd'),
            simulate_missing_weights=sim_missing,
            point_hr=hr_val,
            ra_deg=ra_val,
            dec_deg=dec_val,
            image=resolved_img,
            out_dir=BASE.joinpath('data', 'outputs'),
            lookup=True,
            save_png=False,
            **_optics_from(body.get),
        )
        if req.mode not in ('fast', 'full'):
            return (jsonify(dict(error='mode must be fast or full')), 400)
        if not LOCK.acquire(timeout=0.15):
            raise EngineBusy('Hệ thống đang xử lý khung ảnh trước đó. Vui lòng đợi giây lát rồi thử lại.')
        try:
            comp_payload = ENGINE.compare(req, backends=backends_tuple)
        finally:
            LOCK.release()
        src_nm = Path(str(resolved_img)).name if resolved_img else f'seed={req.seed}'
        ckpt_st_cmp = _checkpoint_status_now(sim_missing)
        for bk, m_obj in (comp_payload.get('methods') or {}).items():
            record_pipeline_run(
                BASE,
                endpoint='/api/compare',
                source_type=str(comp_payload.get('source', 'simulator')),
                source_name=src_nm,
                requested_backend=str(bk),
                executed_backend=str(m_obj.get('executed_backend', bk)),
                fallback_triggered=bool(m_obj.get('centroid_fallback')),
                fallback_reason=m_obj.get('fallback_reason'),
                status=str(m_obj.get('status', 'LOST')),
                reject_code=m_obj.get('reject_code'),
                n_valid_pairs=int(m_obj.get('n_valid_pairs') or 0),
                n_detected=int(m_obj.get('n_detected') or 0),
                latency_ms=(m_obj.get('timing_ms') or {}).get('total_pipeline_ms'),
                checkpoint_status=ckpt_st_cmp,
            )
        return jsonify(comp_payload)
    except EngineBusy as busy_err:
        return (jsonify(dict(error=str(busy_err), busy=True)), 409)
    except Exception as err:
        return (jsonify(dict(error=str(err))), 400)

@app.post('/api/compare-upload')
def api_compare_upload() -> object:
    uploaded: object = request.files.get('image')
    if uploaded is None or not uploaded.filename:
        return (jsonify(dict(error='Chưa chọn file ảnh để so sánh')), 400)
    from werkzeug.utils import secure_filename
    safe_name: str = secure_filename(uploaded.filename)
    if Path(safe_name).suffix.lower() not in _UPLOAD_EXTS:
        return (jsonify(dict(error='Nhận TIFF, PNG, JPEG, WebP hoặc NPY.')), 400)
    sc_upload: object = request.files.get('sidecar')
    sc_safe: str | None = None
    if sc_upload is not None and sc_upload.filename:
        sc_safe = secure_filename(sc_upload.filename)
        if Path(sc_safe).suffix.lower() != '.json':
            return (jsonify(dict(error='Nhãn phải là file .json (q_gt, stars_in_fov).')), 400)
    form_get: object = request.form.get
    mode_val: str = str(form_get('mode') or 'fast')
    if mode_val not in ('fast', 'full'):
        return (jsonify(dict(error='mode must be fast or full')), 400)
    sim_missing_up: bool = _bool_flag(form_get('simulate_missing_weights'))
    ret_mode: str = normalize_retention_mode(form_get('retention_mode'))
    caller_sid: str | None = _caller_session_id()
    saved_slot = save_uploaded_files(
        BASE,
        uploaded,
        safe_name,
        sidecar_storage=sc_upload if sc_safe else None,
        safe_sidecar_name=sc_safe,
        retention_mode=ret_mode,
        endpoint='/api/compare-upload',
        owner_sid=caller_sid,
    )
    upload_id: str = saved_slot['upload_id']
    slot_dir: Path = saved_slot['slot_dir']
    saved_img: Path = saved_slot['image_path']
    saved_sidecar: Path | None = saved_slot['sidecar_path']
    meta: dict = saved_slot['meta']
    deleted_now = False
    verified_gone = False
    succeeded = False
    try:
        req: object = RunRequest(
            mode=mode_val,
            seed=int(float(form_get('seed') or 42)),
            catalog=str(form_get('catalog') or 'bsc5'),
            omega=float(form_get('omega') or 0.06),
            omega_axis=str(form_get('omega_axis') or 'y'),
            exposure=float(form_get('exposure') or 0.15),
            glare=str(form_get('glare') or 'none'),
            sky_clutter=str(form_get('sky_clutter') or 'none'),
            false_stars=int(float(form_get('false_stars') or 0)),
            solver=str(form_get('solver') or 'svd'),
            simulate_missing_weights=sim_missing_up,
            image=saved_img,
            sidecar=saved_sidecar,
            out_dir=slot_dir,
            lookup=True,
            save_png=False,
            write_result_json=False,
            **_optics_from(form_get),
        )
        if not LOCK.acquire(timeout=0.15):
            raise EngineBusy('Hệ thống đang xử lý khung ảnh trước đó. Vui lòng đợi giây lát rồi thử lại.')
        try:
            comp_payload = ENGINE.compare(req, backends=('classical', 'tetra3', 'cnn'))
        finally:
            LOCK.release()
        if ret_mode == 'ephemeral':
            comp_payload['clean_url'] = encode_png_data_uri(slot_dir / 'demo_compare_clean.png')
        else:
            comp_payload['clean_url'] = f'/api/uploads/{upload_id}/preview/demo_compare_clean.png'
        succeeded = True
    except EngineBusy as busy_err:
        return (jsonify(dict(error=str(busy_err), busy=True)), 409)
    except Exception as err:
        return (jsonify(dict(error=str(err))), 400)
    finally:
        if ret_mode == 'ephemeral' or not succeeded:
            d_res = delete_upload(BASE, upload_id, ignore_owner=True)
            deleted_now = bool(d_res.get('deleted'))
            verified_gone = bool(d_res.get('verified_gone'))
            if deleted_now:
                del_action = 'EPHEMERAL_AUTO_DELETE' if ret_mode == 'ephemeral' else 'ERROR_ROLLBACK_DELETE'
                record_data_deletion(BASE, action=del_action, upload_id=upload_id, deleted_files=d_res.get('deleted_files') or [], verified_gone=verified_gone, endpoint='/api/compare-upload')

    comp_payload['source'] = 'upload'
    comp_payload['source_image'] = safe_name
    comp_payload['storage_control'] = dict(
        upload_id=upload_id,
        retention_mode=ret_mode,
        storage_rel_dir=meta['storage_rel_dir'],
        original_image_name=safe_name,
        original_sidecar_name=sc_safe,
        overwrite_protected=True,
        previews_isolated=True,
        previews_deleted_with_slot=True,
        session_scoped=caller_sid is not None,
        deleted_immediately=deleted_now,
        verified_gone_on_disk=verified_gone,
        ttl_seconds=meta['ttl_seconds'],
        expires_at_utc=meta['expires_at_utc'],
        delete_endpoint=f'/api/uploads/{upload_id}',
    )
    ckpt_st_up = _checkpoint_status_now(sim_missing_up)
    for bk, m_obj in (comp_payload.get('methods') or {}).items():
        record_pipeline_run(
            BASE,
            endpoint='/api/compare-upload',
            source_type='upload',
            source_name=safe_name,
            requested_backend=str(bk),
            executed_backend=str(m_obj.get('executed_backend', bk)),
            fallback_triggered=bool(m_obj.get('centroid_fallback')),
            fallback_reason=m_obj.get('fallback_reason'),
            status=str(m_obj.get('status', 'LOST')),
            reject_code=m_obj.get('reject_code'),
            n_valid_pairs=int(m_obj.get('n_valid_pairs') or 0),
            n_detected=int(m_obj.get('n_detected') or 0),
            latency_ms=(m_obj.get('timing_ms') or {}).get('total_pipeline_ms'),
            checkpoint_status=ckpt_st_up,
            upload_id=upload_id,
            retention_mode=ret_mode,
            deleted_immediately=deleted_now,
        )
    return jsonify(comp_payload)

@app.get('/api/benchmark-summary')
def api_benchmark_summary() -> object:
    bench_p: Path = BASE.joinpath('data', 'outputs', 'benchmark_3way_comparison.json')
    rej_p: Path = BASE.joinpath('data', 'outputs', 'benchmark_rejection_stress.json')
    stress_p: Path = BASE.joinpath('data', 'outputs', 'benchmark_stress_curves.json')
    out: dict = dict(available=False, evaluation_scope='PC/laptop software benchmark (not flight-qualified spacecraft hardware)')
    if bench_p.is_file():
        try:
            data = json_loads(bench_p.read_text(encoding='utf-8'))
            out['available'] = True
            for k in ('generated_at', 'device', 'backends', 'sim_hd1024', 'sim_glare', 'sim_earth_clutter', 'real_calibrated'):
                if k in data:
                    out[k] = data[k]
        except Exception as err:
            out['error'] = str(err)
    if rej_p.is_file():
        try:
            rej_data = json_loads(rej_p.read_text(encoding='utf-8'))
            out['rejection_stress'] = rej_data.get('summary') or rej_data
        except Exception:
            pass
    if stress_p.is_file():
        try:
            out['stress_curves'] = json_loads(stress_p.read_text(encoding='utf-8'))
        except Exception:
            pass
    return jsonify(out)

@app.post('/api/run-upload')
def api_run_upload() -> object:
    uploaded: object = request.files.get('image')
    if uploaded is None or not uploaded.filename:
        return (jsonify(dict(error='Chưa chọn file ảnh')), 400)
    from werkzeug.utils import secure_filename
    safe_name: str = secure_filename(uploaded.filename)
    if Path(safe_name).suffix.lower() not in _UPLOAD_EXTS:
        return (jsonify(dict(error='Nhận TIFF, PNG, JPEG, WebP hoặc NPY. Ảnh nén sẽ kèm cảnh báo tâm sao.')), 400)
    sc_upload: object = request.files.get('sidecar')
    sc_safe: str | None = None
    if sc_upload is not None and sc_upload.filename:
        sc_safe = secure_filename(sc_upload.filename)
        if Path(sc_safe).suffix.lower() != '.json':
            return (jsonify(dict(error='Nhãn phải là file .json (q_gt, stars_in_fov).')), 400)
    form_get: object = request.form.get
    mode_val: str = str(form_get('mode') or 'fast')
    be_val: str = str(form_get('centroid_backend') or 'auto').strip().lower()
    if mode_val not in ('fast', 'full'):
        return (jsonify(dict(error='mode must be fast or full')), 400)
    if be_val not in _VALID_BACKENDS:
        return (jsonify(dict(error='centroid_backend must be auto, classical, tetra3, or cnn')), 400)
    ret_mode: str = normalize_retention_mode(form_get('retention_mode'))
    caller_sid: str | None = _caller_session_id()
    saved_slot = save_uploaded_files(
        BASE,
        uploaded,
        safe_name,
        sidecar_storage=sc_upload if sc_safe else None,
        safe_sidecar_name=sc_safe,
        retention_mode=ret_mode,
        endpoint='/api/run-upload',
        owner_sid=caller_sid,
    )
    upload_id: str = saved_slot['upload_id']
    slot_dir: Path = saved_slot['slot_dir']
    saved_img: Path = saved_slot['image_path']
    saved_sidecar: Path | None = saved_slot['sidecar_path']
    meta: dict = saved_slot['meta']
    deleted_now = False
    verified_gone = False
    succeeded = False
    try:
        req: object = RunRequest(
            mode=mode_val,
            seed=int(float(form_get('seed') or 42)),
            catalog=str(form_get('catalog') or 'bsc5'),
            omega=float(form_get('omega') or 0.06),
            omega_axis=str(form_get('omega_axis') or 'y'),
            exposure=float(form_get('exposure') or 0.15),
            glare=str(form_get('glare') or 'none'),
            sky_clutter=str(form_get('sky_clutter') or 'none'),
            false_stars=int(float(form_get('false_stars') or 0)),
            solver=str(form_get('solver') or 'svd'),
            centroid_backend=be_val,
            simulate_missing_weights=_bool_flag(form_get('simulate_missing_weights')),
            image=saved_img,
            sidecar=saved_sidecar,
            out_dir=slot_dir,
            lookup=True,
            save_png=True,
            write_result_json=False,
            **_optics_from(form_get),
        )
        res_dict: dict = _run_upload_locked(req)
        if ret_mode == 'ephemeral':
            res_dict.update(
                clean_url=encode_png_data_uri(slot_dir / 'demo_clean.png'),
                input_url=encode_png_data_uri(slot_dir / 'demo_input.png'),
                output_url=encode_png_data_uri(slot_dir / 'demo_output.png'),
                image_url=encode_png_data_uri(slot_dir / 'demo_result.png'),
                png=None,
                input_png=None,
                output_png=None,
                clean_png=None,
            )
        else:
            res_dict.update(
                clean_url=f'/api/uploads/{upload_id}/preview/demo_clean.png',
                input_url=f'/api/uploads/{upload_id}/preview/demo_input.png',
                output_url=f'/api/uploads/{upload_id}/preview/demo_output.png',
                image_url=f'/api/uploads/{upload_id}/preview/demo_result.png',
                png=f'data/user_uploads/{upload_id}/demo_result.png',
                input_png=f'data/user_uploads/{upload_id}/demo_input.png',
                output_png=f'data/user_uploads/{upload_id}/demo_output.png',
                clean_png=f'data/user_uploads/{upload_id}/demo_clean.png',
            )
        succeeded = True
    except EngineBusy as busy_err:
        return (jsonify(dict(error=str(busy_err), busy=True)), 409)
    except Exception as err:
        return (jsonify(dict(error=str(err))), 400)
    finally:
        if ret_mode == 'ephemeral' or not succeeded:
            d_res = delete_upload(BASE, upload_id, ignore_owner=True)
            deleted_now = bool(d_res.get('deleted'))
            verified_gone = bool(d_res.get('verified_gone'))
            if deleted_now:
                del_action = 'EPHEMERAL_AUTO_DELETE' if ret_mode == 'ephemeral' else 'ERROR_ROLLBACK_DELETE'
                record_data_deletion(BASE, action=del_action, upload_id=upload_id, deleted_files=d_res.get('deleted_files') or [], verified_gone=verified_gone, endpoint='/api/run-upload')

    res_dict['source'] = 'upload'
    res_dict['source_image'] = safe_name
    res_dict['storage_control'] = dict(
        upload_id=upload_id,
        retention_mode=ret_mode,
        storage_rel_dir=meta['storage_rel_dir'],
        original_image_name=safe_name,
        original_sidecar_name=sc_safe,
        overwrite_protected=True,
        previews_isolated=True,
        previews_deleted_with_slot=True,
        session_scoped=caller_sid is not None,
        deleted_immediately=deleted_now,
        verified_gone_on_disk=verified_gone,
        ttl_seconds=meta['ttl_seconds'],
        expires_at_utc=meta['expires_at_utc'],
        delete_endpoint=f'/api/uploads/{upload_id}',
    )
    _log_run_payload('/api/run-upload', res_dict, source_name=safe_name, upload_id=upload_id, retention_mode=ret_mode, deleted_immediately=deleted_now)
    return jsonify(res_dict)

@app.get('/api/uploads/<upload_id>/preview/<filename>')
def api_upload_preview(upload_id: str, filename: str) -> object:
    target = resolve_upload_preview(BASE, upload_id, filename, owner_sid=_caller_session_id())
    if target is None:
        return (jsonify(dict(error='Ảnh xem trước không tồn tại hoặc đã bị xóa/hết hạn TTL.')), 404)
    return send_from_directory(target.parent, target.name)

@app.get('/api/uploads')
def api_list_uploads() -> object:
    sid = _caller_session_id()
    return jsonify(dict(policy=storage_policy_summary(BASE, owner_sid=sid), uploads=list_uploads(BASE, owner_sid=sid)))

@app.delete('/api/uploads/<upload_id>')
def api_delete_upload(upload_id: str) -> object:
    res = delete_upload(BASE, upload_id, owner_sid=_caller_session_id())
    if res.get('deleted'):
        record_data_deletion(
            BASE,
            action='USER_DELETE_SINGLE',
            upload_id=res['upload_id'],
            deleted_files=res.get('deleted_files') or [],
            verified_gone=bool(res.get('verified_gone')),
            endpoint=f'DELETE /api/uploads/{upload_id}',
        )
        return jsonify(res)
    status_code = 404 if (res.get('verified_gone') or res.get('not_found_or_denied')) else 400
    return (jsonify(res), status_code)

@app.delete('/api/uploads')
def api_delete_all_uploads() -> object:
    res = delete_all_uploads(BASE, owner_sid=_caller_session_id())
    record_data_deletion(
        BASE,
        action='USER_DELETE_ALL',
        upload_id=None,
        deleted_files=res.get('deleted_files') or [],
        verified_gone=bool(res.get('verified_empty')),
        endpoint='DELETE /api/uploads',
    )
    return jsonify(res)

@app.get('/api/execution-log')
def api_execution_log() -> object:
    try:
        lim = int(request.args.get('limit') or 40)
    except Exception:
        lim = 40
    return jsonify(dict(log_file='data/outputs/execution_log.jsonl', entries=read_execution_log(BASE, limit=lim)))

@app.get('/api/repro-status')
def api_repro_status() -> object:
    bundle_root = BASE if BASE.joinpath('CHECKSUMS.sha256').is_file() else Path(__file__).resolve().parent
    return jsonify(dict(bundle=verify_repro_bundle(bundle_root), storage_policy=storage_policy_summary(BASE, owner_sid=_caller_session_id())))

@app.get('/output/<path:name>')
def output_file(name: object) -> object:
    if str(name) in _STATIC_PLOT_NAMES:
        _PLOT_READY.wait(timeout=15.0)
    out_root: object = BASE.joinpath('data', 'outputs').resolve()
    target: object = out_root.joinpath(name).resolve()
    target.relative_to(out_root)
    if not target.is_file():
        return (jsonify(dict(error='missing output')), 404)
    return send_from_directory(out_root, name)

def _preload_warmup() -> None:
    """Warm up BSC5 catalog, K-vector table, and MobileUNet weights asynchronously on server start."""
    try:
        ENGINE.stack('bsc5', 6.0, 30.5)
        from src.centroid_cnn import CNNCentroidDetector, weights_available
        if weights_available():
            import numpy as _np
            det = CNNCentroidDetector(ENGINE.cam_full.downscaled(4))
            det.detect(_np.zeros((128, 128), dtype=_np.uint16))
            ENGINE._cnn_cache = det
    except Exception:
        pass

def _ttl_sweeper_loop() -> None:
    """Proactively purge expired TTL upload directories in the background even with zero traffic."""
    while True:
        time.sleep(DEFAULT_SWEEP_INTERVAL_S)
        try:
            purged = cleanup_expired_uploads(BASE)
            if purged:
                record_data_deletion(
                    BASE,
                    action='TTL_EXPIRED_AUTO_PURGE',
                    upload_id=None,
                    deleted_files=purged,
                    verified_gone=True,
                    endpoint='BG:ttl_sweeper',
                )
        except Exception:
            pass

if os.environ.get('STAR_TRACKER_PRELOAD', '').strip().lower() in ('1', 'true', 'yes'):
    Thread(target=_preload_warmup, name='star-tracker-preload', daemon=True).start()

if 'PYTEST_CURRENT_TEST' not in os.environ and os.environ.get('STAR_TRACKER_DISABLE_SWEEPER', '').strip().lower() not in ('1', 'true', 'yes'):
    Thread(target=_ttl_sweeper_loop, name='star-tracker-ttl-sweeper', daemon=True).start()

def main() -> object:
    raw_port: object = os.environ.get('STAR_TRACKER_PORT', '').strip()
    port_num: object = int(raw_port) if raw_port else 8765
    app_url: object = f'http://127.0.0.1:{port_num}/'
    banner: object = ('=' * 60, '  Star tracker  —  Star Tracker demo app', f'  Open {app_url}', '  Demo camera: APS-C 6000x4000, 3.72 um, 50 mm', '  Synthetic starframes rendered via src.simulator.SkySimulator', '=' * 60)
    print('\n'.join(banner))
    no_browser_env: object = os.environ.get('STAR_TRACKER_NO_BROWSER', '').strip().lower() in ('1', 'true', 'yes')
    if not (no_browser_env or '--no-browser' in sys.argv):
        Timer(0.8, lambda: open_browser(app_url)).start()
    app.run(host='127.0.0.1', port=port_num, debug=False, threaded=True)
if __name__ == '__main__':
    main()
