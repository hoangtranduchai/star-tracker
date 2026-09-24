"""Monte Carlo evaluation of lost-in-space solve rate and 3-axis attitude error."""
from argparse import ArgumentParser
from json import dumps as json_dumps, loads as json_loads
from pathlib import Path
import sys
from time import perf_counter
from numpy import abs as npabs, arcsin, arctan2, asarray, clip, degrees, empty, float64, linspace, mean, median, mod, percentile, pi, sort as npsort, sqrt
from numpy.linalg import norm
from numpy.random import default_rng
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.camera import demo_camera
from src.catalog import CatalogManager
from src.kvector import build_or_load
from src.pipeline import PipelineConfig, StarTrackerPipeline
from src.quaternion import angular_error_arcsec, axis_error_arcsec, random_quaternion, to_dcm
from src.simulator import Radiometry, SkySimulator

def load_cfg(mode: object) -> object:
    cfg_path: object = ROOT.joinpath('config', 'pipeline_default.json')
    raw_map: object = json_loads(cfg_path.read_text(encoding='utf-8'))
    return PipelineConfig.from_dict(raw_map[mode])

def _resolve_mc_catalog(catalog_kind: object, cache_dir: object) -> object:
    bsc_file: object = cache_dir / 'BSC5'
    if catalog_kind == 'bsc5' and bsc_file.exists():
        raw_cat: object = CatalogManager.load_bsc5(bsc_file, max_mag=6.0, epoch_year=2026.7)
        return CatalogManager.filter_close_pairs(raw_cat, 60.0)
    return CatalogManager.synthetic(3500, 6.0, seed=123)

def run_mc(num_trials: object, mode: object, seed: object=0, catalog_kind: object='synthetic') -> object:
    base_cam: object = demo_camera()
    cam: object = base_cam.downscaled(4) if mode == 'fast' else base_cam
    cat_dir: object = ROOT.joinpath('data', 'catalogs')
    cat: object = _resolve_mc_catalog(catalog_kind, cat_dir)
    kv_tbl: object = build_or_load(cat, cat_dir)
    cfg: object = load_cfg(mode)
    pipe: object = StarTrackerPipeline(cam, cat, kv_tbl, cfg)
    clean_rad: object = Radiometry(hot_pixel_frac=0.0, cosmic_rate_per_frame=0.0)
    sim: object = SkySimulator(cam, cat, radiometry=clean_rad, seed=seed)
    gen: object = default_rng(seed)
    n_ok, n_usable = (0, 0)
    err_list, ax_list, lat_list = ([], [], [])
    fov_cnts, ra_list, dec_list = ([], [], [])
    ms_cent, ms_id, ms_wahba = ([], [], [])
    err_cap: object = cfg.attitude_error_limit_arcsec
    total_t: object = int(num_trials)
    for idx in range(1, total_t + 1):
        q_true: object = random_quaternion(gen)
        rand_axis: object = gen.normal(size=3)
        omega_vec: object = rand_axis * (0.06 / float(norm(rand_axis)))
        spurious_n: object = int(gen.integers(0, 3))
        frame, truth = sim.render(q_true, omega_deg_s=omega_vec, t_exp_s=0.15, false_stars=spurious_n, add_noise=True)
        if len(truth.cat_idx) < 4:
            continue
        n_usable += 1
        t_start: object = perf_counter()
        out: object = pipe.process_frame(frame)
        elapsed_ms: object = (perf_counter() - t_start) * 1000.0
        z_bore: object = to_dcm(q_true)[2]
        ra_list.append(float(degrees(mod(arctan2(z_bore[1], z_bore[0]), 2.0 * pi))))
        dec_list.append(float(degrees(arcsin(clip(z_bore[2], -1.0, 1.0)))))
        fov_cnts.append(int(len(truth.cat_idx)))
        if out.success:
            ang_err: object = angular_error_arcsec(out.q, q_true)
            if ang_err < err_cap:
                n_ok += 1
            err_list.append(ang_err)
            ax_list.append(axis_error_arcsec(out.q, q_true))
            lat_list.append(elapsed_ms)
            t_dict: object = out.timing_ms
            ms_cent.append(t_dict.get('centroiding_ms', 0.0))
            ms_id.append(t_dict.get('identification_ms', 0.0))
            ms_wahba.append(t_dict.get('attitude_ms', 0.0))
        if idx % 10 == 0 or idx == total_t:
            pct: object = 100.0 * n_ok / float(max(idx, 1))
            print(f'    Trial {idx:4d}/{total_t}: solve-within-limit = {pct:.1f}%', flush=True)
    err_arr: object = asarray(err_list, dtype=float64) if err_list else empty(0, dtype=float64)
    ax_arr: object = asarray(ax_list, dtype=float64) if ax_list else empty((0, 3), dtype=float64)
    has_e: object = bool(err_arr.size)
    return dict(mode=mode, trials=total_t, usable_fov=n_usable, successes_within_limit=n_ok, solve_rate_pct=100.0 * n_ok / float(max(total_t, 1)), limit_arcsec=err_cap, mean_error_arcsec=float(mean(err_arr)) if has_e else None, median_error_arcsec=float(median(err_arr)) if has_e else None, p95_error_arcsec=float(percentile(err_arr, 95)) if has_e else None, max_error_arcsec=float(err_arr.max()) if has_e else None, rms_error_arcsec=float(sqrt(mean(err_arr * err_arr))) if has_e else None, mean_axis_arcsec=mean(npabs(ax_arr), axis=0).tolist() if ax_arr.size else None, mean_latency_ms=float(mean(lat_list)) if lat_list else None, median_centroid_ms=float(median(ms_cent)) if ms_cent else None, median_id_ms=float(median(ms_id)) if ms_id else None, median_wahba_ms=float(median(ms_wahba)) if ms_wahba else None, n_fov_mean=float(mean(fov_cnts)) if fov_cnts else None, ra_deg=ra_list, dec_deg=dec_list, errors_arcsec=err_arr.tolist(), n_fov=fov_cnts, latencies_ms=lat_list, catalog=cat.source, n_catalog=cat.num_stars)

def save_report(summary: object, out_dir: object) -> object:
    import matplotlib.pyplot as plt
    dest_dir: object = Path(out_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem: object = f"mc_{summary['mode']}_{summary['trials']}"
    json_file: object = dest_dir / f'{stem}.json'
    png_file: object = dest_dir / f'{stem}.png'
    omit_keys: object = {'ra_deg', 'dec_deg', 'errors_arcsec', 'n_fov', 'latencies_ms'}
    compact: object = {k: v for k, v in summary.items() if k not in omit_keys}
    json_file.write_text(json_dumps(compact, indent=2), encoding='utf-8')
    err_arr: object = asarray(summary['errors_arcsec'], dtype=float64)
    fig, grid_ax = plt.subplots(2, 2, figsize=(11, 8), facecolor='#0F172A')
    (ax_hist, ax_cdf), (ax_fov, ax_sky) = grid_ax
    for panel, title_txt in ((ax_hist, 'Attitude error (arcsec)'), (ax_cdf, 'CDF'), (ax_fov, 'Error vs stars in FOV'), (ax_sky, 'Boresight RA/Dec sample')):
        panel.set_facecolor('#1E293B')
        panel.set_title(title_txt, color='white')
        panel.tick_params(colors='#94A3B8')
    if err_arr.size:
        ax_hist.hist(err_arr, bins=30, color='#38BDF8', edgecolor='white')
        ordered: object = npsort(err_arr)
        ax_cdf.plot(ordered, linspace(0.0, 1.0, len(ordered)), color='#4ADE80')
    if summary['n_fov']:
        ax_fov.scatter(summary['n_fov'][:len(err_arr)], err_arr, s=8, c='#FBBF24')
    if summary['ra_deg']:
        ax_sky.scatter(summary['ra_deg'], summary['dec_deg'], s=8, c='#94A3B8')
    fig.tight_layout()
    fig.savefig(png_file, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f'wrote {json_file} and {png_file}')

def main() -> object:
    cli: object = ArgumentParser()
    cli.add_argument('--trials', type=int, default=100)
    cli.add_argument('--mode', choices=('fast', 'full'), default='fast')
    cli.add_argument('--seed', type=int, default=0)
    cli.add_argument('--catalog', choices=('synthetic', 'bsc5'), default='synthetic')
    opts: object = cli.parse_args()
    print(f'[*] Monte Carlo {opts.trials} trials  mode={opts.mode}', flush=True)
    report: object = run_mc(opts.trials, opts.mode, seed=opts.seed, catalog_kind=opts.catalog)
    print('=' * 50)
    scalar_view: object = {k: v for k, v in report.items() if not isinstance(v, list)}
    print(json_dumps(scalar_view, indent=2))
    save_report(report, ROOT.joinpath('data', 'outputs'))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
