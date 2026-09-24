"""Generate synthetic star tracker frames and ground-truth JSON sidecars."""
from argparse import ArgumentParser
from json import dumps as json_dumps
from pathlib import Path
import sys
from cv2 import imwrite
from numpy import clip, degrees, float32, uint8
from numpy.linalg import norm
from numpy.random import default_rng
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.camera import demo_camera
from src.catalog import CatalogManager, vectors_to_ra_dec
from src.demo_session import load_specs, radiometry_from_specs
from src.quaternion import boresight_ra_dec_deg, format_dec_dms, format_ra_hms, random_quaternion
from src.simulator import SkySimulator
from src.starnames import label_hr, lookup_hr

def load_radiometry() -> object:
    return radiometry_from_specs(load_specs(ROOT))

def star_rows(cat: object, truth: object) -> object:
    ra_r, dec_r = vectors_to_ra_dec(cat.vectors[truth.cat_idx])
    entries: object = []
    for pos, c_idx in enumerate(truth.cat_idx):
        hr_num: object = int(cat.ids[c_idx])
        iau_info: object = lookup_hr(hr_num) or {}
        entries.append(dict(catalog_idx=int(c_idx), hr=hr_num, iau_name=iau_info.get('name'), designation=iau_info.get('designation') or None, label=label_hr(hr_num, compact=False), mag=float(truth.vis_mags[pos]), u_px=float(truth.uv_mid[pos, 0]), v_px=float(truth.uv_mid[pos, 1]), ra_deg=float(degrees(ra_r[pos])), dec_deg=float(degrees(dec_r[pos]))))
    return entries

def write_frame(out_dir: object, stem: object, img: object, meta: object) -> object:
    dest: object = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    tif_file: object = dest / f'{stem}.tif'
    if not imwrite(str(tif_file), img):
        raise RuntimeError(f'cv2.imwrite failed: {tif_file}')
    dest.joinpath(f'{stem}.json').write_text(json_dumps(meta, indent=2), encoding='utf-8')
    thumb: object = clip(img.astype(float32) * (1.0 / 16.0), 0.0, 255.0).astype(uint8)
    imwrite(str(dest / f'{stem}_preview.png'), thumb)

def main() -> object:
    cli: object = ArgumentParser(description='Synthetic demo-camera star-tracker dataset')
    cli.add_argument('--n-fast', type=int, default=40)
    cli.add_argument('--n-full', type=int, default=3)
    cli.add_argument('--seed', type=int, default=1)
    cli.add_argument('--out', type=Path, default=ROOT.joinpath('data', 'sim_dataset'))
    opts: object = cli.parse_args()
    cat_dir: object = ROOT.joinpath('data', 'catalogs')
    npz_file: object = cat_dir / 'bsc5_v6.0.npz'
    if npz_file.exists():
        cat: object = CatalogManager.load_npz(npz_file)
    else:
        bsc_bin: object = cat_dir / 'BSC5'
        CatalogManager.fetch_bsc5(bsc_bin)
        raw_cat: object = CatalogManager.load_bsc5(bsc_bin, max_mag=6.0, epoch_year=2026.7)
        cat: object = CatalogManager.filter_close_pairs(raw_cat, 60.0)
        CatalogManager.save_npz(cat, npz_file)
    rad_cfg: object = load_radiometry()
    full_cam: object = demo_camera()
    fast_cam: object = full_cam.downscaled(4)
    gen: object = default_rng(opts.seed)
    manifest: object = dict(note='Synthetic lost-in-space frames. Demo optics: APS-C 6000x4000, 3.72 um, 50 mm. Not a night-sky photo. Radiometry.assumption=true. Method class: catalog pinhole + PSF + detector noise + quaternion GT (same class as UW LOST --generate / tetra3+COTS practice). Not ISO/CCSDS.', catalog=cat.source, n_catalog=cat.num_stars, frames=[])
    batches: object = (('fast', fast_cam, opts.n_fast), ('full', full_cam, opts.n_full))
    for mode_tag, cam_obj, count in batches:
        sim: object = SkySimulator(cam_obj, cat, radiometry=rad_cfg, seed=opts.seed)
        sub_out: object = opts.out / mode_tag
        for idx in range(int(count)):
            q_true: object = random_quaternion(gen)
            rnd_vec: object = gen.normal(size=3)
            omega_vec: object = rnd_vec * (0.06 / float(norm(rnd_vec)))
            spurious_n: object = int(gen.integers(0, 3))
            frame, truth = sim.render(q_true, omega_deg_s=omega_vec, t_exp_s=0.15, false_stars=spurious_n, add_noise=True)
            ra_d, dec_d = boresight_ra_dec_deg(q_true)
            stem: object = f'{idx:04d}'
            sidecar_meta: object = dict(mode=mode_tag, seed_base=opts.seed, index=idx, q_gt=q_true.tolist(), omega_deg_s=omega_vec.tolist(), t_exp_s=0.15, false_stars=spurious_n, boresight=dict(ra_deg=ra_d, dec_deg=dec_d, ra_hms=format_ra_hms(ra_d), dec_dms=format_dec_dms(dec_d), frame='J2000 camera +Z'), camera=dict(width=cam_obj.width, height=cam_obj.height, pixel_um=cam_obj.pixel_um, focal_mm=cam_obj.focal_mm), stars_in_fov=star_rows(cat, truth), image=f'{mode_tag}/{stem}.tif')
            write_frame(sub_out, stem, frame, sidecar_meta)
            manifest['frames'].append(dict(file=f'{mode_tag}/{stem}.tif', sidecar=f'{mode_tag}/{stem}.json', n_stars=len(truth.cat_idx), ra_deg=ra_d, dec_deg=dec_d))
            print(f'  wrote {mode_tag}/{stem}.tif  stars={len(truth.cat_idx)}  RA={ra_d:.2f} Dec={dec_d:+.2f}')
    opts.out.mkdir(parents=True, exist_ok=True)
    opts.out.joinpath('manifest.json').write_text(json_dumps(manifest, indent=2), encoding='utf-8')
    readme_txt: object = '# Simulated demo-camera frames\n\n- Raw: `fast/*.tif`, `full/*.tif` (uint16, 12-bit DN 0–4095).\n- Ground truth: sidecar `.json` (`q_gt`, boresight RA/Dec, HR + IAU name if any).\n- Preview: `*_preview.png` (8-bit stretch for viewing only).\n\nTest one frame:\n\n```\npython demo_star_tracker.py --image data/sim_dataset/fast/0000.tif --lookup --no-show\n```\n'
    opts.out.joinpath('README.md').write_text(readme_txt, encoding='utf-8')
    print('manifest', opts.out / 'manifest.json', 'n=', len(manifest['frames']))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
