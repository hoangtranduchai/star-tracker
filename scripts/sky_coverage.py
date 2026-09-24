"""Evaluate catalog star count distribution across random sky pointings."""
from argparse import ArgumentParser
from json import dumps as json_dumps
from pathlib import Path
import sys
from numpy import asarray, count_nonzero, einsum, int32, mean, median, percentile
from numpy.random import default_rng
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.camera import demo_camera
from src.catalog import CatalogManager
from src.quaternion import random_quaternion, to_dcm

def count_in_fov(catalog: object, camera: object, n_dir: object, seed: object) -> object:
    gen: object = default_rng(seed)
    cat_vecs: object = catalog.vectors
    return asarray([int(count_nonzero(camera.project(einsum('ij,kj->ik', cat_vecs, to_dcm(random_quaternion(gen))))[1])) for _ in range(int(n_dir))], dtype=int32)

def main() -> object:
    cli: object = ArgumentParser()
    cli.add_argument('--n-dir', type=int, default=2000)
    cli.add_argument('--max-mag', type=float, default=6.0)
    cli.add_argument('--seed', type=int, default=0)
    cli.add_argument('--catalog', choices=('bsc5', 'synthetic'), default='bsc5')
    opts: object = cli.parse_args()
    cam: object = demo_camera()
    if opts.catalog == 'bsc5':
        bsc_path: object = ROOT.joinpath('data', 'catalogs', 'BSC5')
        if not bsc_path.exists():
            CatalogManager.fetch_bsc5(bsc_path)
        cat: object = CatalogManager.load_bsc5(bsc_path, max_mag=opts.max_mag, epoch_year=2026.7)
    else:
        cat: object = CatalogManager.synthetic(3500, opts.max_mag, seed=123)
    star_cnts: object = count_in_fov(cat, cam, opts.n_dir, opts.seed)
    report: object = dict(catalog=cat.source, n_stars=cat.num_stars, max_mag=opts.max_mag, n_dir=opts.n_dir, mean=float(mean(star_cnts)), median=float(median(star_cnts)), p5=float(percentile(star_cnts, 5)), p95=float(percentile(star_cnts, 95)), min=int(star_cnts.min()), max=int(star_cnts.max()), frac_lt_4=float(mean(star_cnts < 4)), frac_lt_6=float(mean(star_cnts < 6)))
    dest: object = ROOT.joinpath('data', 'outputs', f'sky_coverage_{cat.source}_v{opts.max_mag}.json')
    dest.parent.mkdir(parents=True, exist_ok=True)
    formatted: object = json_dumps(report, indent=2)
    dest.write_text(formatted, encoding='utf-8')
    print(formatted)
    print(f'wrote {dest}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
