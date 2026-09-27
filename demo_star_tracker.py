"""Command-line runner for the standalone star tracker pipeline (APS-C 24 MP + 50 mm lens)."""
from argparse import ArgumentParser
from pathlib import Path
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
from src.demo_session import DemoEngine, RunRequest
_CLUTTER_CHOICES = ('none', 'galactic', 'galaxy', 'nebula', 'cloud', 'typical', 'milky_way', 'andromeda', 'both')

def print_star_table(title: object, rows: object) -> object:
    print(f'  {title} ({len(rows)})')
    if not rows:
        print('    (none)')
        return
    hdr: object = f"    {'ID':>8}  {'mag':>6}  {'name':<28}  {'u_px':>8}  {'v_px':>8}"
    print(hdr)
    for item in rows:
        mag_v: object = item.get('mag')
        u_v, v_v = (item.get('u_px'), item.get('v_px'))
        tag_id: object = f"{item.get('id_scheme', 'ID')} {item['id']}"
        star_nm: object = (item.get('iau_name') or '-')[:28]
        mag_txt: object = f'{mag_v:.2f}' if mag_v is not None else 'n/a'
        u_txt: object = f'{u_v:.1f}' if u_v is not None else 'n/a'
        v_txt: object = f'{v_v:.1f}' if v_v is not None else 'n/a'
        print(f'    {tag_id:>8}  {mag_txt:>6}  {star_nm:<28}  {u_txt:>8}  {v_txt:>8}')

def _build_cli_parser() -> object:
    cli: object = ArgumentParser(description='Star tracker laptop demo')
    specs: object = ((('--mode',), dict(choices=('fast', 'full'), default='fast')), (('--scale',), dict(type=int, default=None)), (('--seed',), dict(type=int, default=42)), (('--catalog',), dict(choices=('bsc5', 'hipparcos', 'synthetic'), default='bsc5')), (('--max-mag',), dict(type=float, default=6.0)), (('--omega',), dict(type=float, default=0.06)), (('--omega-axis',), dict(choices=('random', 'x', 'y', 'z'), default='y')), (('--exposure',), dict(type=float, default=0.15)), (('--glare',), dict(choices=('none', 'earth', 'sun', 'sun_strong', 'moon'), default='none')), (('--centroid',), dict(choices=('classical', 'cnn'), default='classical', help='Centroid mode: classical CoG (default) or CNN MobileUNet public weights')), (('--sky-clutter',), dict(choices=_CLUTTER_CHOICES, default='none')), (('--false-stars',), dict(type=int, default=0)), (('--solver',), dict(choices=('svd', 'quest'), default='svd')), (('--no-show',), dict(action='store_true')), (('--out',), dict(type=Path, default=BASE_DIR.joinpath('data', 'outputs'))), (('--lookup',), dict(action='store_true')), (('--image',), dict(type=Path, default=None)), (('--save-raw',), dict(action='store_true')))
    for flags, kw in specs:
        cli.add_argument(*flags, **kw)
    return cli

def main(argv: object=None) -> object:
    opts: object = _build_cli_parser().parse_args(argv)
    sep_eq: object = '=' * 70
    sep_dash: object = '-' * 55
    print(f'{sep_eq}\n   STAR TRACKER - STAR TRACKER DEMO (LAPTOP RUNTIME)\n{sep_eq}')
    runner: object = DemoEngine(BASE_DIR)
    hw_specs: object = runner.specs
    print(f"[*] Hardware: {hw_specs['sensor']['model']} + {hw_specs['lens']['model']}")
    print(f"[*] Pixel pitch: {hw_specs['sensor']['pixel_size_um']} um")
    if runner.radiometry.assumption:
        print('[*] Radiometry parameters are simulation assumptions, not a camera datasheet.')
    req: object = RunRequest(mode=opts.mode, scale=opts.scale, seed=opts.seed, catalog=opts.catalog, max_mag=opts.max_mag, omega=opts.omega, omega_axis=opts.omega_axis, exposure=opts.exposure, glare=opts.glare, sky_clutter=opts.sky_clutter, false_stars=opts.false_stars, solver=opts.solver, centroid_backend=opts.centroid, image=opts.image, out_dir=opts.out, lookup=bool(opts.lookup), save_png=True, save_raw=opts.save_raw, show=not opts.no_show)
    print('[1/5] Loading catalog + K-vector...\n[2/5] Rendering or loading frame...')
    outcome: object = runner.run(req)
    info: object = outcome.payload
    cam_info: object = info['camera']
    fov_w, fov_h = cam_info['fov_deg']
    print(f"[1/5] Catalog {info['catalog_source']}: {info['n_catalog']} stars  V<={opts.max_mag}")
    print(f"[*] Mode={info['mode']}  {cam_info['width']}x{cam_info['height']}  FOV={fov_w:.2f}x{fov_h:.2f} deg  IFOV={cam_info['ifov_arcsec']:.2f} arcsec/px")
    if outcome.have_gt:
        gt_b: object = info['boresight_gt']
        print(f"      q_GT = {info['q_gt_text']}")
        print(f"      GT boresight RA={gt_b['ra_deg']:.4f} deg ({gt_b['ra_hms']})  Dec={gt_b['dec_deg']:+.4f} deg ({gt_b['dec_dms']})")
        print(f"      stars in FOV={info['metrics']['n_truth']}")
    print(f"      image {cam_info['width']}x{cam_info['height']}  source={info['source']}")
    print(f'[3/5] Running deterministic pipeline...\n[4/5] Results\n{sep_dash}')
    t_ms: object = info['timing_ms']
    for label_t, key_t in (('Centroiding', 'centroiding_ms'), ('Star ID    ', 'identification_ms'), ('Wahba      ', 'attitude_ms'), ('Total      ', 'total_pipeline_ms')):
        print(f'  {label_t} : {t_ms.get(key_t, 0.0):.2f} ms')
    print(sep_dash)
    if outcome.success:
        print(f"  q_est       : {info['q_est_text']}")
        est_b: object = info.get('boresight_est') or {}
        if est_b:
            print(f"  boresight   : RA {est_b['ra_deg']:.4f} deg ({est_b['ra_hms']})   Dec {est_b['dec_deg']:+.4f} deg ({est_b['dec_dms']})")
            print('               (optical axis +Z in ICRS/J2000 celestial coordinates)')
        att_err: object = info['metrics'].get('attitude_error_arcsec')
        if att_err is not None:
            print(f'  att err     : {att_err:.3f} arcsec')
        print(f"  downlink    : {info['downlink_hex']}  ({info['downlink_bytes']} bytes)")
        print(f"  verdict     : {info['metrics'].get('verdict')}")
        matched_ids: object = info.get('matched_catalog_ids') or []
        if matched_ids:
            print(f"  matched HR  : {', '.join((str(int(m)) for m in matched_ids))}")
    else:
        print(f'  FAILED: {outcome.error}')
    if opts.lookup:
        print(f'{sep_dash}\n  LOOKUP  Yale HR + IAU WGSN name (overlay; not used by Pyramid/Wahba)')
        if outcome.have_gt:
            print_star_table('Stars in FOV (sim GT)', info['stars_in_fov'])
        print_star_table('Identified', info['identified_stars'])
        if info.get('n_unidentified'):
            print(f"  Unidentified detections: {info['n_unidentified']}")
    print(f"[5/5] Wrote {outcome.png_path} and {opts.out / 'demo_result.json'}\n{sep_eq}")
    return 0 if outcome.success else 1
if __name__ == '__main__':
    cli_args = sys.argv[1:]
    if '--full-res' in cli_args:
        cli_args = [tok for tok in cli_args if tok != '--full-res'] + ['--mode', 'full']
    raise SystemExit(main(cli_args))
