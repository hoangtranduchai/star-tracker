"""Flask web interface for the star tracker simulator and lost-in-space attitude solver."""
from math import isfinite
import os
from pathlib import Path
import sys
from threading import Lock, Timer
from webbrowser import open as open_browser
from flask import Flask, Response, jsonify, render_template, request, send_from_directory
import matplotlib
BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
matplotlib.use('Agg')
from src.demo_session import DemoEngine, RunRequest, SIM_METHOD
from src.quaternion import format_dec_both, format_dec_stellarium, format_ra_both, format_ra_hms, parse_dec_deg, parse_ra_deg, split_radec_text
from src.starnames import describe_index, n_iau_names, n_named_hr
app = Flask(__name__, template_folder=str(BASE.joinpath('web', 'templates')), static_folder=str(BASE.joinpath('web', 'static')))
app.config.update(SEND_FILE_MAX_AGE_DEFAULT=0, TEMPLATES_AUTO_RELOAD=True, MAX_CONTENT_LENGTH=80 * 1024 * 1024)
app.jinja_env.auto_reload = True
app.jinja_env.cache = {}
ENGINE = DemoEngine(BASE)
LOCK = Lock()
_SKY_CATALOG_CACHE = {}
_SKY_CACHE_LOCK = Lock()
_VALID_BACKENDS = ('classical', 'cnn', 'cnn_zhao2024', 'zhao', 'mobileunet')
_UPLOAD_EXTS = ('.tif', '.tiff', '.png', '.jpg', '.jpeg', '.webp')
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
    return dict(focal_mm=_opt_float(getter, 'focal_mm'), pixel_um=_opt_float(getter, 'pixel_um'), image_width=_opt_int(getter, 'image_width'), image_height=_opt_int(getter, 'image_height'), angular_tol_arcsec=_opt_float(getter, 'angular_tol_arcsec'))

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

def _run_locked(req: object) -> object:
    if not LOCK.acquire(timeout=0.15):
        raise EngineBusy('Hệ thống đang xử lý khung ảnh trước đó. Vui lòng đợi giây lát rồi thử lại.')
    try:
        outcome: object = ENGINE.run(req)
    finally:
        LOCK.release()
    res_dict: object = dict(outcome.payload)
    res_dict.update(
        image_url='/output/demo_result.png',
        input_url='/output/demo_input.png',
        output_url='/output/demo_output.png',
        clean_url='/output/demo_clean.png',
    )
    return res_dict

@app.after_request
def _no_cache(resp: object) -> object:
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@app.get('/')
def index() -> object:
    ds_frames: object = ENGINE.list_dataset_frames()
    return render_template('index.html', hardware=ENGINE.specs, sim_method=SIM_METHOD, frames=ds_frames, n_frames=len(ds_frames), n_iau_names=n_iau_names(), n_named_hr=n_named_hr())

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

@app.post('/api/run')
def api_run() -> object:
    body: object = request.get_json(silent=True) or {}
    try:
        rel_img: object = body.get('image')
        resolved_img: object = ENGINE.resolve_dataset_image(str(rel_img)) if rel_img else None
        ra_val, dec_val = _body_radec(body)
        hr_val: object = int(body['point_hr']) if body.get('point_hr') else None
        req: object = RunRequest(mode=str(body.get('mode') or 'fast'), seed=int(_body_float(body, 'seed', 42.0)), catalog=str(body.get('catalog') or 'bsc5'), max_mag=float(_body_float(body, 'max_mag', 6.0)), omega=float(_body_float(body, 'omega', 0.06)), omega_axis=str(body.get('omega_axis') or 'y'), exposure=float(_body_float(body, 'exposure', 0.15)), glare=str(body.get('glare') or 'none'), sky_clutter=str(body.get('sky_clutter') or 'none'), false_stars=int(_body_float(body, 'false_stars', 0.0)), solver=str(body.get('solver') or 'svd'), centroid_backend=str(body.get('centroid_backend') or 'classical'), point_hr=hr_val, ra_deg=ra_val, dec_deg=dec_val, image=resolved_img, out_dir=BASE.joinpath('data', 'outputs'), lookup=True, save_png=True, **_optics_from(body.get))
        if req.mode not in ('fast', 'full'):
            return (jsonify(dict(error='mode must be fast or full')), 400)
        if req.centroid_backend not in _VALID_BACKENDS:
            return (jsonify(dict(error='centroid_backend must be classical or cnn')), 400)
        return jsonify(_run_locked(req))
    except EngineBusy as busy_err:
        return (jsonify(dict(error=str(busy_err), busy=True)), 409)
    except Exception as err:
        return (jsonify(dict(error=str(err))), 400)

@app.post('/api/run-upload')
def api_run_upload() -> object:
    uploaded: object = request.files.get('image')
    if uploaded is None or not uploaded.filename:
        return (jsonify(dict(error='Chưa chọn file ảnh')), 400)
    from werkzeug.utils import secure_filename
    safe_name: object = secure_filename(uploaded.filename)
    if Path(safe_name).suffix.lower() not in _UPLOAD_EXTS:
        return (jsonify(dict(error='Nhận TIFF, PNG, JPEG hoặc WebP. Ảnh nén sẽ kèm cảnh báo tâm sao.')), 400)
    up_dir: object = BASE.joinpath('data', 'uploads')
    up_dir.mkdir(parents=True, exist_ok=True)
    saved_img: object = up_dir / safe_name
    uploaded.save(saved_img)
    saved_sidecar: object = None
    sc_upload: object = request.files.get('sidecar')
    if sc_upload is not None and sc_upload.filename:
        sc_safe: object = secure_filename(sc_upload.filename)
        if Path(sc_safe).suffix.lower() != '.json':
            return (jsonify(dict(error='Nhãn phải là file .json (q_gt, stars_in_fov).')), 400)
        saved_sidecar: object = up_dir / sc_safe
        sc_upload.save(saved_sidecar)
    form_get: object = request.form.get
    try:
        req: object = RunRequest(mode=str(form_get('mode') or 'fast'), seed=int(float(form_get('seed') or 42)), catalog=str(form_get('catalog') or 'bsc5'), omega=float(form_get('omega') or 0.06), omega_axis=str(form_get('omega_axis') or 'y'), exposure=float(form_get('exposure') or 0.15), glare=str(form_get('glare') or 'none'), sky_clutter=str(form_get('sky_clutter') or 'none'), false_stars=int(float(form_get('false_stars') or 0)), solver=str(form_get('solver') or 'svd'), centroid_backend=str(form_get('centroid_backend') or 'classical'), image=saved_img, sidecar=saved_sidecar, out_dir=BASE.joinpath('data', 'outputs'), lookup=True, save_png=True, **_optics_from(form_get))
        res_dict: object = _run_locked(req)
        res_dict['source'] = 'upload'
        res_dict['source_image'] = str(saved_img)
        return jsonify(res_dict)
    except EngineBusy as busy_err:
        return (jsonify(dict(error=str(busy_err), busy=True)), 409)
    except Exception as err:
        return (jsonify(dict(error=str(err))), 400)

@app.get('/output/<path:name>')
def output_file(name: object) -> object:
    out_root: object = BASE.joinpath('data', 'outputs').resolve()
    target: object = out_root.joinpath(name).resolve()
    target.relative_to(out_root)
    if not target.is_file():
        return (jsonify(dict(error='missing output')), 404)
    return send_from_directory(out_root, name)

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
