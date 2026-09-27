#!/usr/bin/env python3
"""Star-tracker laptop app: render, solve, compare q_GT vs q_est."""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import matplotlib

matplotlib.use("Agg")

app = Flask(
    __name__,
    template_folder=str(BASE / "web" / "templates"),
    static_folder=str(BASE / "web" / "static"),
)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024
app.jinja_env.auto_reload = True
app.jinja_env.cache = {}

from src.demo_session import DemoEngine, RunRequest, SIM_METHOD
from src.quaternion import (
    format_dec_both,
    format_dec_stellarium,
    format_ra_both,
    format_ra_hms,
    parse_dec_deg,
    parse_ra_deg,
    split_radec_text,
)
from src.starnames import n_iau_names, n_named_hr

ENGINE = DemoEngine(BASE)
LOCK = threading.Lock()


class EngineBusy(RuntimeError):
    """A previous /api/run is still holding the demo engine."""


def _body_float(body: dict, key: str, default: float | None) -> float | None:
    if key not in body or body[key] is None or body[key] == "":
        return default
    return float(body[key])


def _opt_float(getter, key: str) -> float | None:
    raw = getter(key)
    if raw is None or str(raw).strip() == "":
        return None
    return float(raw)


def _opt_int(getter, key: str) -> int | None:
    raw = getter(key)
    if raw is None or str(raw).strip() == "":
        return None
    return int(float(raw))


def _optics_from(getter) -> dict:
    return {
        "focal_mm": _opt_float(getter, "focal_mm"),
        "pixel_um": _opt_float(getter, "pixel_um"),
        "image_width": _opt_int(getter, "image_width"),
        "image_height": _opt_int(getter, "image_height"),
        "angular_tol_arcsec": _opt_float(getter, "angular_tol_arcsec"),
    }


def _body_radec(body: dict) -> tuple[float | None, float | None]:
    paste = body.get("radec_paste")
    ra_raw = body.get("ra_deg")
    dec_raw = body.get("dec_deg")
    if paste is not None and str(paste).strip():
        blob = str(paste).strip()
        parts = split_radec_text(blob)
        if parts:
            ra_raw, dec_raw = parts
        elif ra_raw is None or str(ra_raw).strip() == "":
            ra_raw = blob
    elif ra_raw is not None and str(ra_raw).strip():
        parts = split_radec_text(str(ra_raw))
        if parts and (dec_raw is None or str(dec_raw).strip() == ""):
            ra_raw, dec_raw = parts
    empty_ra = ra_raw is None or str(ra_raw).strip() == ""
    empty_dec = dec_raw is None or str(dec_raw).strip() == ""
    if empty_ra and empty_dec:
        return None, None
    if empty_ra or empty_dec:
        raise ValueError(
            "Cần cả RA và Dec. Dán một dòng Stellarium: 18h 37m51.2s   +38°48'46.2\""
        )
    fmt = str(body.get("radec_fmt") or "auto")
    return parse_ra_deg(ra_raw, fmt=fmt), parse_dec_deg(dec_raw, fmt=fmt)


def _run_locked(req: RunRequest) -> dict:
    if not LOCK.acquire(timeout=0.15):
        raise EngineBusy(
            "Engine đang xử lý request khác. Đợi xong (hoặc F5) rồi bấm lại — không tự chạy khi vừa mở trang."
        )
    try:
        out = ENGINE.run(req)
    finally:
        LOCK.release()
    payload = dict(out.payload)
    payload["image_url"] = "/output/demo_result.png"
    payload["input_url"] = "/output/demo_input.png"
    payload["output_url"] = "/output/demo_output.png"
    return payload


@app.after_request
def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.get("/")
def index():
    frames = ENGINE.list_dataset_frames()
    return render_template(
        "index.html",
        hardware=ENGINE.specs,
        sim_method=SIM_METHOD,
        frames=frames,
        n_frames=len(frames),
        n_iau_names=n_iau_names(),
        n_named_hr=n_named_hr(),
    )


@app.get("/api/frames")
def api_frames():
    return jsonify({"frames": ENGINE.list_dataset_frames()})


@app.post("/api/parse-radec")
def api_parse_radec():
    body = request.get_json(silent=True) or {}
    try:
        ra, dec = _body_radec(body)
        if ra is None:
            return jsonify({"ok": False, "empty": True})
        return jsonify(
            {
                "ok": True,
                "ra_deg": ra,
                "dec_deg": dec,
                "ra_hms": format_ra_hms(ra),
                "dec_dms": format_dec_stellarium(dec),
                "ra_both": format_ra_both(ra),
                "dec_both": format_dec_both(dec),
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/run")
def api_run():
    body = request.get_json(silent=True) or {}
    try:
        image_rel = body.get("image")
        image_path = None
        if image_rel:
            image_path = ENGINE.resolve_dataset_image(str(image_rel))
        ra, dec = _body_radec(body)
        req = RunRequest(
            mode=str(body.get("mode") or "fast"),
            seed=int(_body_float(body, "seed", 42.0)),
            catalog=str(body.get("catalog") or "bsc5"),
            max_mag=float(_body_float(body, "max_mag", 6.0)),
            omega=float(_body_float(body, "omega", 0.06)),
            omega_axis=str(body.get("omega_axis") or "y"),
            exposure=float(_body_float(body, "exposure", 0.15)),
            glare=str(body.get("glare") or "none"),
            sky_clutter=str(body.get("sky_clutter") or "none"),
            false_stars=int(_body_float(body, "false_stars", 0.0)),
            solver=str(body.get("solver") or "svd"),
            centroid_backend=str(body.get("centroid_backend") or "classical"),
            point_hr=(int(body["point_hr"]) if body.get("point_hr") else None),
            ra_deg=ra,
            dec_deg=dec,
            image=image_path,
            out_dir=BASE / "data" / "outputs",
            lookup=True,
            save_png=True,
            **_optics_from(body.get),
        )
        if req.mode not in {"fast", "full"}:
            return jsonify({"error": "mode must be fast or full"}), 400
        if req.centroid_backend not in {"classical", "cnn", "cnn_zhao2024", "zhao", "mobileunet"}:
            return jsonify({"error": "centroid_backend must be classical or cnn"}), 400
        payload = _run_locked(req)
        return jsonify(payload)
    except EngineBusy as exc:
        return jsonify({"error": str(exc), "busy": True}), 409
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/run-upload")
def api_run_upload():
    img_file = request.files.get("image")
    if img_file is None or not img_file.filename:
        return jsonify({"error": "Chưa chọn file ảnh"}), 400
    from werkzeug.utils import secure_filename

    name = secure_filename(img_file.filename)
    suffix = Path(name).suffix.lower()
    if suffix not in {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp"}:
        return jsonify({"error": "Nhận TIFF, PNG, JPEG hoặc WebP. Ảnh nén sẽ kèm cảnh báo tâm sao."}), 400
    dest_dir = BASE / "data" / "uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    img_path = dest_dir / name
    img_file.save(img_path)
    sidecar_path = None
    side = request.files.get("sidecar")
    if side is not None and side.filename:
        sname = secure_filename(side.filename)
        if Path(sname).suffix.lower() != ".json":
            return jsonify({"error": "Nhãn phải là file .json (q_gt, stars_in_fov)."}), 400
        sidecar_path = dest_dir / sname
        side.save(sidecar_path)
    try:
        req = RunRequest(
            mode=str(request.form.get("mode") or "fast"),
            seed=int(float(request.form.get("seed") or 42)),
            catalog=str(request.form.get("catalog") or "bsc5"),
            omega=float(request.form.get("omega") or 0.06),
            omega_axis=str(request.form.get("omega_axis") or "y"),
            exposure=float(request.form.get("exposure") or 0.15),
            glare=str(request.form.get("glare") or "none"),
            sky_clutter=str(request.form.get("sky_clutter") or "none"),
            false_stars=int(float(request.form.get("false_stars") or 0)),
            solver=str(request.form.get("solver") or "svd"),
            centroid_backend=str(request.form.get("centroid_backend") or "classical"),
            image=img_path,
            sidecar=sidecar_path,
            out_dir=BASE / "data" / "outputs",
            lookup=True,
            save_png=True,
            **_optics_from(request.form.get),
        )
        payload = _run_locked(req)
        payload["source"] = "upload"
        payload["source_image"] = str(img_path)
        return jsonify(payload)
    except EngineBusy as exc:
        return jsonify({"error": str(exc), "busy": True}), 409
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/output/<path:name>")
def output_file(name: str):
    folder = (BASE / "data" / "outputs").resolve()
    path = (folder / name).resolve()
    path.relative_to(folder)
    if not path.is_file():
        return jsonify({"error": "missing output"}), 404
    return send_from_directory(folder, name)


def main() -> None:
    port = 8765
    url = f"http://127.0.0.1:{port}/"
    print("=" * 60)
    print("  Star tracker  —  Star Tracker demo app")
    print(f"  Open {url}")
    print("  Demo camera: APS-C 6000x4000, 3.72 um, 50 mm")
    print("  Images are generated by src.simulator.SkySimulator (not night-sky)")
    print("=" * 60)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
