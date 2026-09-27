"""Shared laptop demo run: synthetic sky + lost-in-space solve."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent

from .camera import CameraModel, demo_camera
from .catalog import CatalogManager, StarCatalog
from .kvector import KVectorTable, build_or_load, cache_path_for
from .metrics import evaluate
from .pipeline import PipelineConfig, StarTrackerPipeline, TrackerResult
from .quaternion import boresight_ra_dec_deg, format_dec_both, format_ra_both, looking_at, looking_at_ra_dec
from .simulator import GlareSpec, Radiometry, RenderTruth, SkySimulator
from .starnames import describe_index, n_iau_names, n_named_hr
from .visualize import image_stats, plot_frame, save_input_png, save_output_png


def load_specs(root: Path | None = None) -> dict:
    path = (root or ROOT) / "config" / "camera_specs.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_pipeline_cfg(mode: str, root: Path | None = None) -> PipelineConfig:
    path = (root or ROOT) / "config" / "pipeline_default.json"
    blob = json.loads(path.read_text(encoding="utf-8"))
    return PipelineConfig.from_dict(blob[mode])


def radiometry_from_specs(specs: dict) -> Radiometry:
    r = specs.get("radiometry", {})
    return Radiometry(
        assumption=True,
        e_per_s_v0=float(r.get("e_per_s_v0", 3.3e6)),
        qe=float(r.get("qe", 1.0)),
        read_noise_e=float(r.get("read_noise_e", 5.0)),
        dark_e_per_s=float(r.get("dark_e_per_s", 10.0)),
        gain_dn_per_e=float(r.get("gain_dn_per_e", 1.0)),
        full_well_e=float(r.get("full_well_e", 12000.0)),
        bit_depth=int(r.get("bit_depth", 12)),
        bias_dn=float(r.get("bias_dn", 64.0)),
        hot_pixel_frac=float(r.get("hot_pixel_frac", 1e-5)),
        cosmic_rate_per_frame=float(r.get("cosmic_rate_per_frame", 2.0)),
    )


def load_catalog(kind: str, max_mag: float, cache_dir: Path) -> tuple[StarCatalog, bool]:
    if kind == "synthetic":
        return CatalogManager.synthetic(3500, max_mag, seed=123), True
    if kind == "hipparcos":
        hip_npz = cache_dir / "hipparcos_v6.npz"
        if hip_npz.exists():
            return CatalogManager.load_npz(hip_npz), False
        tsv = next(
            (p for p in (cache_dir / "hipparcos_v6.tsv", cache_dir / "starcat.tsv") if p.exists()),
            None,
        )
        if tsv is None:
            kind = "bsc5"
        else:
            cat = CatalogManager.load_hipparcos_tsv(tsv, max_mag=max_mag, epoch_year=2026.7)
            cat = CatalogManager.filter_close_pairs(cat, 60.0)
            CatalogManager.save_npz(cat, hip_npz)
            return cat, False
    npz = cache_dir / f"bsc5_v{max_mag}.npz"
    if npz.exists() and kind == "bsc5":
        return CatalogManager.load_npz(npz), False
    bsc5 = cache_dir / "BSC5"
    try:
        CatalogManager.fetch_bsc5(bsc5)
        cat = CatalogManager.load_bsc5(bsc5, max_mag=max_mag, epoch_year=2026.7)
        cat = CatalogManager.filter_close_pairs(cat, 60.0)
        CatalogManager.save_npz(cat, npz)
        return cat, False
    except FileNotFoundError:
        return CatalogManager.synthetic(3500, max_mag, seed=123), True


def glare_spec_from_req(req: RunRequest, camera: CameraModel) -> GlareSpec | None:
    kind = str(req.glare or "none").lower()
    uw, vh = 0.18 * camera.width, 0.22 * camera.height
    if kind == "earth":
        return GlareSpec(kind="earth", peak_dn=2800, edge_frac=0.70)
    if kind == "sun":
        sig = max(18.0, 0.12 * min(camera.width, camera.height))
        return GlareSpec(kind="sun", u=uw, v=vh, sigma_px=sig, peak_dn=4095)
    if kind in {"sun_strong", "glare_demo", "stray"}:
        # Stronger stray-light bloom for the glare centroid demo (still photosphere 0.5°).
        sig = max(40.0, 0.28 * min(camera.width, camera.height))
        return GlareSpec(kind="sun", u=uw, v=vh, sigma_px=sig, peak_dn=4095)
    if kind == "moon":
        return GlareSpec(kind="moon", u=uw, v=vh, peak_dn=2400)
    return None


def find_sidecar(image_path: Path, root: Path) -> Path | None:
    sibling = image_path.with_suffix(".json")
    if sibling.is_file():
        return sibling
    ds = (root / "data" / "sim_dataset").resolve()
    if ds.is_dir():
        hits = list(ds.rglob(f"{image_path.stem}.json"))
        if hits:
            return hits[0]
    return None


def apply_loaded_stress(
    image: np.ndarray,
    camera: CameraModel,
    catalog: StarCatalog,
    radiometry: Radiometry,
    req: RunRequest,
) -> np.ndarray:
    """Overlay form glare / clutter / false stars onto an already captured frame."""
    glare = glare_spec_from_req(req, camera)
    clutter = str(req.sky_clutter or "none")
    n_false = int(req.false_stars or 0)
    if glare is None and n_false <= 0 and clutter in {"", "none"}:
        return image
    sim = SkySimulator(camera, catalog, radiometry=radiometry, seed=int(req.seed))
    img = image.astype(np.float32)
    if n_false > 0:
        acc = np.zeros_like(img)
        false_uv = np.column_stack(
            (
                sim.rng.uniform(10, camera.width - 10, size=n_false),
                sim.rng.uniform(10, camera.height - 10, size=n_false),
            )
        )
        false_e = sim.electrons(np.full(n_false, 4.0), float(req.exposure or 0.15))
        sim._stamp_gaussians(acc, false_uv, false_e, 1.2, 5)
        img = img + acc * radiometry.gain_dn_per_e
    if glare is not None:
        img = img + sim._glare_dn(glare)
    if clutter not in {"", "none"}:
        img = img + sim._clutter_dn(clutter)
    return np.clip(img, 0, radiometry.max_dn).astype(np.uint16)


def omega_vector(axis: str, mag: float, rng: np.random.Generator) -> np.ndarray:
    if axis == "random":
        v = rng.normal(size=3)
        return v / np.linalg.norm(v) * mag
    idx = {"x": 0, "y": 1, "z": 2}[axis]
    v = np.zeros(3)
    v[idx] = mag
    return v


def load_frame(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


# Match tolerance is about 0.88 of one pixel on whatever camera is in use.
_LOCKED_CAM = demo_camera()
TOL_ARCSEC_PER_PIXEL = 0.88
THETA_MIN_DEG = 0.02
THETA_MAX_LOCKED_DEG = 30.5
MAX_SIM_PIXELS = 20_000_000


def camera_for_image(img: np.ndarray, cam_full: CameraModel) -> tuple[CameraModel, int, str]:
    h, w = img.shape[:2]
    if (w, h) == (cam_full.width, cam_full.height):
        return cam_full, 1, "full"
    cam_fast = cam_full.downscaled(4)
    if (w, h) == (cam_fast.width, cam_fast.height):
        return cam_fast, 4, "fast"
    raise ValueError(
        f"Ảnh {w}×{h} không phải khung demo "
        f"{cam_full.width}×{cam_full.height} (FULL) hay "
        f"{cam_fast.width}×{cam_fast.height} (FAST). "
        "Nhập tiêu cự thật (mm) và cạnh pixel của đúng file (µm)."
    )


def uses_custom_optics(req: "RunRequest") -> bool:
    return any(
        value is not None
        for value in (
            req.focal_mm,
            req.pixel_um,
            req.image_width,
            req.image_height,
            req.angular_tol_arcsec,
        )
    )


def theta_max_deg_for_fov(diag_deg: float) -> float:
    """Pair-table limit. A narrower field keeps the stored demo table."""
    if float(diag_deg) <= THETA_MAX_LOCKED_DEG + 1e-9:
        return THETA_MAX_LOCKED_DEG
    need = float(diag_deg) + 0.5
    stepped = math.ceil(need * 2.0 - 1e-9) / 2.0
    return float(min(180.0, stepped))


def _camera_from_numbers(width: int, height: int, pixel_um: float, focal_mm: float) -> CameraModel:
    if int(width) < 16 or int(height) < 16:
        raise ValueError("Số cột và số hàng phải từ 16 trở lên.")
    if float(focal_mm) <= 0.0 or float(pixel_um) <= 0.0:
        raise ValueError("Tiêu cự (mm) và cạnh pixel (µm) phải là số dương.")
    if float(focal_mm) > 5000.0 or float(pixel_um) > 200.0:
        raise ValueError("Tiêu cự hoặc cạnh pixel nằm ngoài khoảng dùng để giải.")
    return CameraModel(
        width=int(width),
        height=int(height),
        pixel_um=float(pixel_um),
        focal_mm=float(focal_mm),
    )


def _locked_camera_for_size(width: int, height: int, cam_full: CameraModel) -> CameraModel | None:
    if (width, height) == (cam_full.width, cam_full.height):
        return cam_full
    fast = cam_full.downscaled(4)
    if (width, height) == (fast.width, fast.height):
        return fast
    return None


def resolve_run_camera(
    req: "RunRequest",
    image: np.ndarray | None,
    cam_full: CameraModel,
) -> tuple[CameraModel, int, str, bool]:
    """Return camera, scale, mode, locked.

    Demo frame sizes keep the 50 mm model when focal length and pixel pitch
    are omitted. Any other size needs both numbers. Width and height of a file
    come from the array; the form size is only for a simulated frame.
    """
    custom = uses_custom_optics(req)
    if image is not None:
        height, width = int(image.shape[0]), int(image.shape[1])
        if not custom:
            camera, scale, mode = camera_for_image(image, cam_full)
            return camera, scale, mode, True
        known = _locked_camera_for_size(width, height, cam_full)
        focal = req.focal_mm if req.focal_mm is not None else (None if known is None else known.focal_mm)
        pixel = req.pixel_um if req.pixel_um is not None else (None if known is None else known.pixel_um)
        if focal is None or pixel is None:
            raise ValueError(
                f"Ảnh {width}×{height} không khớp khung demo "
                f"{cam_full.width}×{cam_full.height} hoặc "
                f"{cam_full.downscaled(4).width}×{cam_full.downscaled(4).height}. "
                "Nhập tiêu cự thật (mm) và cạnh pixel của đúng file (µm)."
            )
        return _camera_from_numbers(width, height, pixel, focal), 1, "custom", False

    scale = req.scale if req.scale is not None else (4 if req.mode == "fast" else 1)
    if scale < 1:
        raise ValueError("scale phải ≥ 1")
    locked_cam = cam_full if scale == 1 else cam_full.downscaled(scale)
    if not custom:
        return locked_cam, scale, req.mode if req.mode in {"fast", "full"} else "full", True
    if (req.image_width is None) != (req.image_height is None):
        raise ValueError("Nhập cả số cột và số hàng, hoặc để trống cả hai.")
    width = int(req.image_width or locked_cam.width)
    height = int(req.image_height or locked_cam.height)
    focal = float(req.focal_mm if req.focal_mm is not None else locked_cam.focal_mm)
    pixel = float(req.pixel_um if req.pixel_um is not None else locked_cam.pixel_um)
    if width * height > MAX_SIM_PIXELS:
        raise ValueError(
            "Ảnh sinh ra vượt 20 triệu pixel. Giảm số cột và số hàng, hoặc nạp file có sẵn."
        )
    return _camera_from_numbers(width, height, pixel, focal), 1, "custom", False


def match_tolerance_arcsec(camera: CameraModel, override: float | None = None) -> float:
    if override is not None:
        if float(override) <= 0.0:
            raise ValueError("Dung sai góc (arcsec) phải là số dương.")
        return float(override)
    return float(TOL_ARCSEC_PER_PIXEL * camera.ifov_arcsec)


def angle_table_note(diag_deg: float, theta_max_deg: float, n_pairs: int, built_now: bool) -> str:
    scan = (
        f"Bảng góc 0,02°–{theta_max_deg:.1f}° có {n_pairs:,} cặp. "
        "Mỗi góc được tra bằng tìm nhị phân trên mảng đã sắp. "
        "Phần phải duyệt thêm chỉ là các cặp nằm trong dung sai, không phải cả bảng."
    )
    if diag_deg <= THETA_MAX_LOCKED_DEG + 1e-6 and abs(theta_max_deg - THETA_MAX_LOCKED_DEG) < 1e-6:
        return (
            f"Chéo trường nhìn nằm trong bảng {THETA_MAX_LOCKED_DEG:.1f}° có sẵn, không dựng lại. "
            + scan
        )
    if built_now:
        return (
            f"Chéo trường nhìn {diag_deg:.2f}° rộng hơn {THETA_MAX_LOCKED_DEG:.1f}°. "
            f"Đã dựng bảng tới {theta_max_deg:.1f}° và lưu lại. " + scan
        )
    return f"Chéo trường nhìn {diag_deg:.2f}° dùng bảng tới {theta_max_deg:.1f}° đã lưu. " + scan


def empty_truth() -> RenderTruth:
    return RenderTruth(
        q_gt=np.array([1.0, 0.0, 0.0, 0.0]),
        uv_mid=np.zeros((0, 2)),
        cat_idx=np.zeros(0, dtype=int),
        streak_px=np.zeros(0),
        omega_deg_s=np.zeros(3),
        vis_mags=np.zeros(0),
    )


def truth_from_sidecar(meta: dict, catalog: StarCatalog) -> RenderTruth:
    q_gt = np.asarray(meta["q_gt"], dtype=float)
    stars = meta.get("stars_in_fov") or []
    uv = (
        np.array([[s["u_px"], s["v_px"]] for s in stars], dtype=float)
        if stars
        else np.zeros((0, 2))
    )
    mags = np.array([float(s.get("mag", 0.0)) for s in stars], dtype=float) if stars else np.zeros(0)
    if stars and "catalog_idx" in stars[0]:
        cat_idx = np.array([int(s["catalog_idx"]) for s in stars], dtype=int)
    else:
        id_map = {int(i): k for k, i in enumerate(catalog.ids)}
        cat_idx = np.array(
            [id_map[int(s["hr"])] for s in stars if int(s["hr"]) in id_map],
            dtype=int,
        )
        if len(cat_idx) != len(stars):
            uv = uv[: len(cat_idx)]
            mags = mags[: len(cat_idx)]
    omega = np.asarray(meta.get("omega_deg_s") or [0.0, 0.0, 0.0], dtype=float)
    return RenderTruth(
        q_gt=q_gt,
        uv_mid=uv,
        cat_idx=cat_idx,
        streak_px=np.zeros(len(cat_idx)),
        omega_deg_s=omega,
        vis_mags=mags,
    )


def star_rows_from_indices(catalog: StarCatalog, indices, uv=None, mags=None) -> list[dict]:
    rows = []
    for i, idx in enumerate(indices):
        row = describe_index(catalog, int(idx))
        if uv is not None and i < len(uv):
            row["u_px"] = float(uv[i, 0])
            row["v_px"] = float(uv[i, 1])
        if mags is not None and i < len(mags):
            row["mag"] = float(mags[i])
        rows.append(row)
    return rows


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _ingest_note(path: Path | None) -> str | None:
    if path is None:
        return None
    if Path(path).suffix.lower() in {".jpg", ".jpeg", ".webp"}:
        return (
            "Ảnh JPEG/WebP đã nén và chỉnh sáng. Tâm sao có thể lệch so với TIFF tuyến tính."
        )
    return None


def fmt_q(q: np.ndarray | None) -> str:
    if q is None:
        return "n/a"
    q = np.asarray(q, dtype=float).reshape(4)
    return f"[{q[0]:.5f}, {q[1]:.5f}, {q[2]:.5f}, {q[3]:.5f}]"


@dataclass
class RunRequest:
    mode: str = "fast"
    scale: int | None = None
    seed: int = 42
    catalog: str = "bsc5"
    max_mag: float = 6.0
    omega: float = 0.06
    omega_axis: str = "y"
    exposure: float = 0.15
    glare: str = "none"
    sky_clutter: str = "none"
    false_stars: int = 0
    solver: str = "svd"
    # classical (default) | cnn — optional MobileUNet public weights
    centroid_backend: str = "classical"
    image: Path | None = None
    sidecar: Path | None = None
    out_dir: Path | None = None
    lookup: bool = True
    save_png: bool = True
    save_raw: bool = False
    show: bool = False
    point_hr: int | None = None
    ra_deg: float | None = None
    dec_deg: float | None = None
    focal_mm: float | None = None
    pixel_um: float | None = None
    image_width: int | None = None
    image_height: int | None = None
    angular_tol_arcsec: float | None = None


@dataclass
class RunOutcome:
    success: bool
    payload: dict
    image: np.ndarray
    result: TrackerResult
    truth: RenderTruth
    metrics: dict
    catalog: StarCatalog
    camera: CameraModel
    png_path: Path | None
    have_gt: bool
    error: str | None = None


class DemoEngine:
    """Caches catalog + K-vector so the web app can re-run without reloading BSC5."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else ROOT
        self.specs = load_specs(self.root)
        self.cam_full = demo_camera()
        self.radiometry = radiometry_from_specs(self.specs)
        self._stack: dict[tuple[str, float, float], tuple[StarCatalog, bool, KVectorTable]] = {}
        self.last_angle_build = False

    def stack(
        self,
        kind: str,
        max_mag: float,
        theta_max_deg: float = THETA_MAX_LOCKED_DEG,
    ) -> tuple[StarCatalog, bool, KVectorTable]:
        key = (kind, float(max_mag), float(theta_max_deg))
        if key in self._stack:
            self.last_angle_build = False
            return self._stack[key]
        cache = self.root / "data" / "catalogs"
        cat, synthetic = load_catalog(kind, max_mag, cache)
        path = cache_path_for(cat, cache, THETA_MIN_DEG, float(theta_max_deg))
        existed = path.exists()
        if not existed:
            print(
                f"Building angle table 0.02-{float(theta_max_deg):.1f} deg "
                f"for {cat.source} (first time, then cached).",
                flush=True,
            )
        kv = build_or_load(
            cat,
            cache,
            theta_min_deg=THETA_MIN_DEG,
            theta_max_deg=float(theta_max_deg),
        )
        self.last_angle_build = not existed
        self._stack[key] = (cat, synthetic, kv)
        return self._stack[key]

    def list_dataset_frames(self) -> list[dict]:
        root = (self.root / "data" / "sim_dataset").resolve()
        out: list[dict] = []
        if not root.exists():
            return out
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            mode = folder.name
            for tif in sorted(folder.glob("*.tif")):
                sidecar = tif.with_suffix(".json")
                meta = {}
                if sidecar.exists():
                    meta = json.loads(sidecar.read_text(encoding="utf-8"))
                bore = meta.get("boresight") or {}
                out.append(
                    {
                        "id": f"{mode}/{tif.stem}",
                        "file": f"{mode}/{tif.name}",
                        "mode": mode,
                        "n_stars": len(meta.get("stars_in_fov") or []),
                        "ra_deg": bore.get("ra_deg"),
                        "dec_deg": bore.get("dec_deg"),
                    }
                )
        return out

    def resolve_dataset_image(self, rel: str) -> Path:
        """Resolve a frame under data/sim_dataset/ or a known upload under data/uploads/."""
        rel_norm = str(rel).replace("\\", "/").lstrip("/")
        if rel_norm.startswith("uploads/"):
            root = (self.root / "data" / "uploads").resolve()
            path = (root / rel_norm[len("uploads/") :]).resolve()
            path.relative_to(root)
        else:
            root = (self.root / "data" / "sim_dataset").resolve()
            path = (root / rel_norm).resolve()
            path.relative_to(root)
        if path.suffix.lower() not in {".tif", ".tiff", ".png", ".jpg", ".jpeg"} or not path.is_file():
            raise ValueError(f"Not a dataset frame: {rel}")
        return path

    def run(self, req: RunRequest) -> RunOutcome:
        have_gt = True
        sidecar_meta = None
        loaded = load_frame(Path(req.image)) if req.image is not None else None
        camera, scale, mode, locked = resolve_run_camera(req, loaded, self.cam_full)
        theta_max_deg = theta_max_deg_for_fov(float(camera.fov_deg[2]))
        catalog, synthetic, kvector = self.stack(req.catalog, req.max_mag, theta_max_deg)
        if loaded is not None:
            image = loaded
            sidecar = Path(req.sidecar) if req.sidecar else find_sidecar(Path(req.image), self.root)
            if sidecar is not None and sidecar.is_file():
                sidecar_meta = json.loads(sidecar.read_text(encoding="utf-8"))
                truth = truth_from_sidecar(sidecar_meta, catalog)
                q_gt = truth.q_gt
            else:
                have_gt = False
                truth = empty_truth()
                q_gt = truth.q_gt
            omega = np.asarray((sidecar_meta or {}).get("omega_deg_s") or [0.0, 0.0, 0.0], dtype=float)
            image = apply_loaded_stress(image, camera, catalog, self.radiometry, req)
        else:
            rng = np.random.default_rng(req.seed)
            sim = SkySimulator(camera, catalog, radiometry=self.radiometry, seed=req.seed)
            if req.point_hr is not None:
                hits = np.where(catalog.ids == int(req.point_hr))[0]
                if hits.size == 0:
                    raise ValueError(f"HR {req.point_hr} is not in {catalog.source} (V<={req.max_mag})")
                q_gt = looking_at(catalog.vectors[int(hits[0])])
            elif req.ra_deg is not None and req.dec_deg is not None:
                q_gt = looking_at_ra_dec(float(req.ra_deg), float(req.dec_deg))
            elif req.ra_deg is not None or req.dec_deg is not None:
                raise ValueError("Cần cả RA và Dec (độ, ICRS/J2000), không chỉ một trong hai")
            else:
                q_gt = SkySimulator.generate_random_quaternion(req.seed)
            omega = omega_vector(req.omega_axis, req.omega, rng)
            glare = glare_spec_from_req(req, camera)
            clutter = str(req.sky_clutter or "none")
            image, truth = sim.render(
                q_gt,
                omega_deg_s=omega,
                t_exp_s=req.exposure,
                glare=glare,
                false_stars=req.false_stars,
                add_noise=True,
                sky_clutter=clutter,
            )

        cfg_mode = "fast" if (locked and scale > 1) or (not locked and camera.width * camera.height < 4_000_000) else "full"
        cfg = load_pipeline_cfg(cfg_mode, self.root)
        tol_arcsec = None if locked else match_tolerance_arcsec(camera, req.angular_tol_arcsec)
        if tol_arcsec is not None:
            cfg.angular_tol_rad = float(tol_arcsec) / (180.0 * 3600.0 / np.pi)
            cfg.attitude_error_limit_arcsec = float(tol_arcsec)
            # Datasheet focal length can sit about 1% off the plate in the file.
            cfg.tol_frac = 0.008
        cfg.solver = req.solver
        backend = str(req.centroid_backend or "classical").lower().strip()
        if backend in {"cnn", "cnn_zhao2024", "zhao", "mobileunet"}:
            cfg.centroid_backend = "cnn"
        else:
            cfg.centroid_backend = "classical"
        pipe = StarTrackerPipeline(camera, catalog, kvector, cfg)
        result = pipe.process_frame(image)
        metrics = evaluate(result, truth, cfg.attitude_error_limit_arcsec, have_gt=have_gt)

        fov_rows = star_rows_from_indices(catalog, truth.cat_idx, uv=truth.uv_mid, mags=truth.vis_mags)
        ident_rows: list[dict] = []
        if result.ident is not None and len(result.ident.cat_idx):
            ident_uv = result.centroids.uv[result.ident.obs_idx] if result.centroids is not None else None
            ident_rows = star_rows_from_indices(catalog, result.ident.cat_idx, uv=ident_uv)

        fov = camera.fov_deg
        out_dir = Path(req.out_dir) if req.out_dir else (self.root / "data" / "outputs")
        out_dir.mkdir(parents=True, exist_ok=True)
        png_path = out_dir / "demo_result.png"
        input_png = out_dir / "demo_input.png"
        output_png = out_dir / "demo_output.png"
        stats = image_stats(image)
        if req.save_png:
            if not req.show:
                import matplotlib

                matplotlib.use("Agg")
            save_input_png(image, input_png, stats=stats)
            save_output_png(image, result, output_png, catalog=catalog, lookup=req.lookup, stats=stats)
            label = (
                f"Optics     : f {camera.focal_mm:.4g} mm   pixel {camera.pixel_um:.4g} um\n"
                f"Frame      : {camera.width} x {camera.height}   fx {camera.fx:.1f} px\n"
                f"FOV        : {fov[0]:.2f} x {fov[1]:.2f} deg   diag {fov[2]:.2f} deg"
            )
            plot_frame(
                image,
                result,
                truth,
                metrics,
                label,
                png_path,
                show=req.show,
                catalog=catalog,
                lookup=req.lookup,
            )

        q_est = None if result.q is None else np.asarray(result.q, dtype=float)
        payload = {
            "mode": mode,
            "scale": scale,
            "seed": None if req.image is not None else req.seed,
            "source": "dataset" if req.image is not None else "simulator",
            "source_image": None if req.image is None else str(req.image),
            "synthetic_catalog": synthetic,
            "catalog_source": catalog.source,
            "n_catalog": catalog.num_stars,
            "radiometry_assumption": True,
            "glare": req.glare,
            "centroid_backend": cfg.centroid_backend,
            "centroid_detector": getattr(
                pipe.centroid_detector, "last_backend", cfg.centroid_backend
            ),
            "centroid_fallback": bool(
                getattr(pipe.centroid_detector, "last_fallback", False)
            ),
            "centroid_error": getattr(pipe.centroid_detector, "last_error", None),
            "centroid_n_raw": getattr(pipe.centroid_detector, "last_n_raw", None),
            "centroid_n_after_gate": getattr(
                pipe.centroid_detector, "last_n_after_gate", None
            ),
            "sky_clutter": req.sky_clutter,
            "have_gt": have_gt,
            "success": bool(result.success),
            "error": result.error,
            "q_gt": q_gt.tolist() if have_gt else None,
            "q_est": None if q_est is None else q_est.tolist(),
            "q_gt_text": fmt_q(q_gt) if have_gt else "n/a",
            "q_est_text": fmt_q(q_est),
            "boresight_est": None
            if metrics.get("boresight_est_ra_deg") is None
            else {
                "ra_deg": metrics["boresight_est_ra_deg"],
                "dec_deg": metrics["boresight_est_dec_deg"],
                "ra_hms": metrics["boresight_est_ra_hms"],
                "dec_dms": metrics["boresight_est_dec_dms"],
                "frame": "J2000 camera +Z (not satellite lat/lon)",
            },
            "boresight_gt": None
            if not have_gt
            else {
                "ra_deg": metrics["boresight_gt_ra_deg"],
                "dec_deg": metrics["boresight_gt_dec_deg"],
                "ra_hms": metrics["boresight_gt_ra_hms"],
                "dec_dms": metrics["boresight_gt_dec_dms"],
            },
            "metrics": _jsonable(metrics),
            "timing_ms": result.timing_ms,
            "downlink_hex": result.to_downlink_bytes().hex(),
            "downlink_bytes": len(result.to_downlink_bytes()),
            "camera": {
                "width": camera.width,
                "height": camera.height,
                "pixel_um": camera.pixel_um,
                "focal_mm": camera.focal_mm,
                "fx_px": float(camera.fx),
                "fov_deg": [float(fov[0]), float(fov[1])],
                "fov_diag_deg": float(fov[2]),
                "ifov_arcsec": float(camera.ifov_arcsec),
                "principal_point": [float(camera.cx), float(camera.cy)],
                "optics": "locked" if locked else "custom",
                "match_tol_arcsec": float(cfg.angular_tol_rad) * (180.0 * 3600.0 / math.pi),
            },
            "angle_table": {
                "theta_min_deg": THETA_MIN_DEG,
                "theta_max_deg": float(np.degrees(kvector.theta_max)),
                "n_pairs": int(kvector.num_pairs),
                "fov_diagonal_deg": float(fov[2]),
                "built_now": bool(self.last_angle_build),
                "note": angle_table_note(
                    float(fov[2]),
                    float(np.degrees(kvector.theta_max)),
                    int(kvector.num_pairs),
                    bool(self.last_angle_build),
                ),
            },
            "ingest_note": _ingest_note(req.image),
            "hardware": {
                "platform": "laptop demo",
                "camera": "APS-C 24 MP, 50 mm lens",
                "array": f"{camera.width} x {camera.height}",
                "pixel_um": float(camera.pixel_um),
                "focal_mm": float(camera.focal_mm),
                "fov": f"{fov[0]:.2f} x {fov[1]:.2f} deg",
            },
            "matched_catalog_ids": (
                catalog.ids[result.ident.cat_idx].tolist()
                if result.ident is not None and len(result.ident.cat_idx)
                else []
            ),
            "stars_in_fov": fov_rows,
            "identified_stars": ident_rows,
            "n_unidentified": int(metrics["n_detected"] - metrics["n_matched"]),
            "compare": _compare_rows(q_gt if have_gt else None, q_est, metrics, have_gt, cfg),
            "sim_method": SIM_METHOD,
            "point_hr": req.point_hr,
            "point_ra_deg": req.ra_deg,
            "point_dec_deg": req.dec_deg,
            "n_iau_hr_names": n_named_hr(),
            "n_iau_names": n_iau_names(),
            "png": str(png_path) if req.save_png else None,
            "input_png": str(input_png) if req.save_png else None,
            "output_png": str(output_png) if req.save_png else None,
            "input_stats": stats,
        }
        (out_dir / "demo_result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if req.save_raw and req.image is None:
            tif = out_dir / "demo_raw.tif"
            cv2.imwrite(str(tif), image)
            (out_dir / "demo_raw.json").write_text(
                json.dumps(
                    {
                        "q_gt": q_gt.tolist(),
                        "omega_deg_s": np.asarray(omega).tolist(),
                        "t_exp_s": req.exposure,
                        "stars_in_fov": fov_rows,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        return RunOutcome(
            success=bool(result.success),
            payload=payload,
            image=image,
            result=result,
            truth=truth,
            metrics=metrics,
            catalog=catalog,
            camera=camera,
            png_path=png_path if req.save_png else None,
            have_gt=have_gt,
            error=result.error,
        )


def _compare_rows(
    q_gt: Optional[np.ndarray],
    q_est: Optional[np.ndarray],
    metrics: dict,
    have_gt: bool,
    cfg: PipelineConfig,
) -> list[dict]:
    rows = []
    labels = ("q0 (scalar)", "q1", "q2", "q3")
    for i, lab in enumerate(labels):
        rows.append(
            {
                "param": lab,
                "gt": None if not have_gt or q_gt is None else float(q_gt[i]),
                "est": None if q_est is None else float(q_est[i]),
                "delta": None
                if (not have_gt or q_gt is None or q_est is None)
                else float(q_est[i] - q_gt[i]),
                "unit": "",
                "note": "scalar-first; q and -q same attitude" if i == 0 else "",
            }
        )
    gt_b = {
        "RA": (metrics.get("boresight_gt_ra_deg"), metrics.get("boresight_gt_ra_hms"), "deg"),
        "Dec": (metrics.get("boresight_gt_dec_deg"), metrics.get("boresight_gt_dec_dms"), "deg"),
    }
    est_b = {
        "RA": (metrics.get("boresight_est_ra_deg"), metrics.get("boresight_est_ra_hms"), "deg"),
        "Dec": (metrics.get("boresight_est_dec_deg"), metrics.get("boresight_est_dec_dms"), "deg"),
    }
    for name in ("RA", "Dec"):
        g, gtxt, unit = gt_b[name]
        e, etxt, _ = est_b[name]
        delta = None if (g is None or e is None) else float(e - g)
        both = format_ra_both if name == "RA" else format_dec_both
        rows.append(
            {
                "param": f"Boresight {name} (camera +Z)",
                "gt": None if g is None else both(g),
                "est": None if e is None else both(e),
                "delta": delta,
                "unit": "deg",
                "gt_deg": g,
                "est_deg": e,
                "note": "not lat/lon; độ và h/m/s (Stellarium)",
            }
        )
    err = metrics.get("attitude_error_arcsec")
    rows.append(
        {
            "param": "Attitude error",
            "gt": "0 (ideal)" if have_gt else "—",
            "est": err,
            "delta": err,
            "unit": "arcsec",
            "limit_arcsec": float(cfg.attitude_error_limit_arcsec),
            "note": f"limit {cfg.attitude_error_limit_arcsec:g} arcsec  ({metrics.get('verdict')})",
        }
    )
    n_truth = metrics.get("n_truth")
    n_det = metrics.get("n_detected")
    n_id = metrics.get("n_matched")
    rows.append(
        {
            "param": "Stars FOV / detected / matched",
            "gt": None if n_truth is None else f"{int(n_truth)} FOV",
            "est": None if n_det is None else f"{int(n_det)} detect",
            "delta": None if n_id is None else f"{int(n_id)} ID",
            "unit": "",
            "note": "cột Δ = số sao Pyramid khớp, không phải sai số góc",
        }
    )
    rows.append(
        {
            "param": "Centroid RMS",
            "gt": None,
            "est": metrics.get("centroid_rms_px"),
            "delta": None,
            "unit": "px",
            "note": "vs sim GT centroids",
        }
    )
    return rows


SIM_METHOD = {
    "generated_by_code": True,
    "module": "src.simulator.SkySimulator.render",
    "not_iso_ccsds": True,
    "practice_class": "catalog + pinhole + PSF + detector noise + quaternion GT",
    "same_class_as": ["UW LOST --generate", "ESA tetra3 synthetic tests", "NASA COTS (math, not NOSA copy)"],
    "demo_optics": "APS-C 6000x4000, 3.72 um, 50 mm lens",
    "radiometry": "assumption=true, not a camera datasheet",
    "steps": [
        "q_GT: 4 Gaussian numbers, normalize (uniform on SO(3)); seed makes it repeatable",
        "Catalog Yale BSC5 V<=6: unit vectors r in J2000",
        "b = A(q_GT) r, pinhole project onto the locked camera (FAST scale 4 or FULL)",
        "Gaussian PSF stamp, optional streak from omega * exposure",
        "Poisson/read/dark/hot/cosmic (radiometry assumptions) -> uint16 12-bit DN",
        "Pipeline does not see q_GT; it recovers q_est from the pixels",
    ],
}
