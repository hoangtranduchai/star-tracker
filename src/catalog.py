"""J2000 star catalog loader: Yale BSC5 binary, Hipparcos I/239 TSV, and synthetic sky generator."""
from hashlib import sha256
from pathlib import Path
from struct import unpack
from urllib.request import Request, urlopen
from numpy import arange, arcsin, arctan2, asarray, clip, column_stack, cos, empty, float32, float64, int32, load as npload, mod, pi, radians, savez_compressed, sin, sqrt, where, zeros
from numpy.linalg import norm
from numpy.random import default_rng
BSC5_URL_HARVARD = 'http://tdc-www.harvard.edu/catalogs/BSC5'
BSC5_URL_COTS = 'https://github.com/nasa/COTS-Star-Tracker/raw/master/py_src/tools/camera_calibration/tetra/BSC5'
BSC5_SIZE = 291548
BSC5_N_ENTRIES = 9110
J2000_EPOCH = 2000.0
_MAS_TO_RAD = float(pi) / (180.0 * 3600000.0)

def ra_dec_to_vectors(ra_rad: object, dec_rad: object) -> object:
    cd: object = cos(dec_rad)
    return column_stack((cd * cos(ra_rad), cd * sin(ra_rad), sin(dec_rad)))

def vectors_to_ra_dec(vectors: object) -> object:
    vx, vy, vz = asarray(vectors, dtype=float64).T
    return (mod(arctan2(vy, vx), 2.0 * pi), arcsin(clip(vz, -1.0, 1.0)))

class StarCatalog:
    """In-memory J2000 star catalog with unit direction vectors, magnitudes, and IDs."""

    def __init__(self, ids: object, vectors: object, mags: object, epoch_year: object=J2000_EPOCH, source: object='', ra_rad: object=None, dec_rad: object=None, pm_ra_rad_yr: object=None, pm_dec_rad_yr: object=None) -> object:
        id_arr: object = asarray(ids, dtype=int32)
        vec_arr: object = asarray(vectors, dtype=float64)
        lengths: object = norm(vec_arr, axis=-1, keepdims=True)
        unit_vecs: object = vec_arr / where(lengths > 0.0, lengths, 1.0)
        mag_arr: object = asarray(mags, dtype=float32)
        if ra_rad is None or dec_rad is None:
            ra_calc, dec_calc = vectors_to_ra_dec(unit_vecs)
        else:
            ra_calc, dec_calc = (ra_rad, dec_rad)
        self.ids, self.vectors, self.mags, self.epoch_year, self.source, self.ra_rad, self.dec_rad, self.pm_ra_rad_yr, self.pm_dec_rad_yr, self.num_stars = (id_arr, unit_vecs, mag_arr, float(epoch_year), str(source), ra_calc, dec_calc, pm_ra_rad_yr, pm_dec_rad_yr, int(id_arr.size))

    @property
    def star_ids(self) -> object:
        return self.ids

    @property
    def magnitudes(self) -> object:
        return self.mags

    def fingerprint(self) -> object:
        digest: object = sha256()
        for chunk in (self.ids.tobytes(), self.vectors.tobytes(), self.mags.tobytes(), repr(self.epoch_year).encode(), self.source.encode()):
            digest.update(chunk)
        return digest.hexdigest()[:16]

    @classmethod
    def create_synthetic_hipparcos_subset(cls, num_stars: object=3500, max_mag: object=6.0, seed: object=42) -> object:
        return CatalogManager.synthetic(num_stars, max_mag, seed)

def _find_tsv_col(lowered_headers: object, *candidates) -> object:
    for alias in candidates:
        key: object = alias.lower()
        if key in lowered_headers:
            return lowered_headers.index(key)
    return None

def _safe_float(row_cells: object, col_idx: object, default: object=0.0) -> object:
    if col_idx is None or col_idx >= len(row_cells) or (not row_cells[col_idx]):
        return default
    try:
        return float(row_cells[col_idx])
    except (ValueError, TypeError):
        return default

class CatalogManager:
    """Loaders, filters, and serializers for star catalogs."""
    BSC5_URL = BSC5_URL_HARVARD
    BSC5_SIZE = BSC5_SIZE
    BSC5_PM_RA_INCLUDES_COS_DEC = True

    @staticmethod
    def fetch_bsc5(dest: object, timeout_s: object=60.0) -> object:
        out_file: object = Path(dest)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if out_file.exists() and out_file.stat().st_size == BSC5_SIZE:
            return out_file
        failures: object = []
        for endpoint in (BSC5_URL_HARVARD, BSC5_URL_COTS):
            try:
                req: object = Request(endpoint, headers={'User-Agent': 'Tracker-ST/1.0'})
                with urlopen(req, timeout=timeout_s) as stream:
                    payload: object = stream.read()
                if len(payload) == BSC5_SIZE:
                    out_file.write_bytes(payload)
                    return out_file
                failures.append(f'{endpoint}: size {len(payload)} != {BSC5_SIZE}')
            except Exception as err:
                failures.append(f'{endpoint}: {err}')
        raise FileNotFoundError('Could not download BSC5 (291548 bytes). Tried Harvard TDC and NASA COTS mirror. ' + ' | '.join(failures))

    @staticmethod
    def parse_bsc5_header(path: object) -> object:
        blob: object = Path(path).read_bytes()
        if len(blob) != BSC5_SIZE:
            raise ValueError(f'BSC5 size {len(blob)} != {BSC5_SIZE}')
        hdr_bytes: object = blob[:28]
        for byte_order in ('<', '>'):
            s0, s1, sn, stn, mpr, nmg, nbe = unpack(byte_order + '7i', hdr_bytes)
            if abs(sn) == BSC5_N_ENTRIES and nbe == 32:
                return dict(endian=byte_order, STAR0=s0, STAR1=s1, STARN=sn, STNUM=stn, MPROP=mpr, NMAG=nmg, NBENT=nbe, n_entries=abs(sn), j2000=sn < 0 or nmg < 0, raw_size=len(blob), sha256=sha256(blob).hexdigest())
        raise ValueError('BSC5 header does not match Harvard TDC binary layout (STARN=±9110, NBENT=32).')

    @staticmethod
    def load_bsc5(path: object, max_mag: object=6.0, epoch_year: object=2026.7, apply_pm: object=True) -> object:
        src_path: object = Path(path)
        blob: object = src_path.read_bytes()
        meta: object = CatalogManager.parse_bsc5_header(src_path)
        fmt_str: object = meta['endian'] + 'fdd2shff'
        stride: object = int(meta['NBENT'])
        total_rec: object = int(meta['n_entries'])
        rows_parsed: object = []
        blank_cnt: object = 0
        for idx in range(total_rec):
            offset: object = 28 + idx * stride
            xno, sra, sdec, _, mag_i, xrpm, xdpm = unpack(fmt_str, blob[offset:offset + stride])
            if sra == 0.0 and sdec == 0.0:
                blank_cnt += 1
            else:
                hr_id: object = int(round(xno)) if xno != 0.0 else idx + 1
                rows_parsed.append((hr_id, sra, sdec, mag_i * 0.01, xrpm, xdpm))
        id_col, ra_col, dec_col, mag_col, pmra_col, pmdec_col = zip(*rows_parsed)
        ra_arr: object = asarray(ra_col, dtype=float64)
        dec_arr: object = asarray(dec_col, dtype=float64)
        pm_ra: object = asarray(pmra_col, dtype=float64)
        pm_dec: object = asarray(pmdec_col, dtype=float64)
        dt_yr: object = float(epoch_year) - J2000_EPOCH
        if apply_pm and dt_yr != 0.0:
            ra_arr: object = mod(ra_arr + pm_ra / clip(cos(dec_arr), 1e-06, None) * dt_yr, 2.0 * pi)
            dec_arr: object = dec_arr + pm_dec * dt_yr
        mag_arr: object = asarray(mag_col, dtype=float32)
        bright_mask: object = mag_arr <= float(max_mag)
        ra_sel, dec_sel = (ra_arr[bright_mask], dec_arr[bright_mask])
        catalog: object = StarCatalog(ids=asarray(id_col, dtype=int32)[bright_mask], vectors=ra_dec_to_vectors(ra_sel, dec_sel), mags=mag_arr[bright_mask], epoch_year=float(epoch_year), source='BSC5', ra_rad=ra_sel, dec_rad=dec_sel, pm_ra_rad_yr=pm_ra[bright_mask], pm_dec_rad_yr=pm_dec[bright_mask])
        catalog.n_blank = blank_cnt
        catalog.n_raw_stars = total_rec - blank_cnt
        return catalog

    @staticmethod
    def load_hipparcos_tsv(path: object, max_mag: object=6.0, epoch_year: object=2026.7) -> object:
        """Parse Hipparcos I/239 TSV table and propagate proper motions to `epoch_year`."""
        tsv_path: object = Path(path)
        if not tsv_path.exists():
            raise FileNotFoundError(tsv_path)
        data_rows: object = []
        hdr_tokens: object = None
        for raw_ln in tsv_path.read_text(encoding='utf-8').splitlines():
            if not raw_ln.strip() or raw_ln.startswith('#'):
                continue
            cells: object = [tok.strip() for tok in raw_ln.replace('|', '\t').split('\t')]
            if hdr_tokens is None:
                hdr_tokens: object = cells
            elif len(cells) >= 4:
                data_rows.append(cells)
        if hdr_tokens is None:
            raise ValueError(f'Hipparcos TSV {tsv_path} has no header row.')
        lower_hdr: object = [c.lower() for c in hdr_tokens]
        c_id: object = _find_tsv_col(lower_hdr, 'hip', 'id', 'hip_id')
        c_ra: object = _find_tsv_col(lower_hdr, '_raj2000', 'ra_deg', 'ra_icrs', 'raj2000', 'ra')
        c_de: object = _find_tsv_col(lower_hdr, '_dej2000', 'dec_deg', 'de_icrs', 'dej2000', 'dec', 'de')
        c_mg: object = _find_tsv_col(lower_hdr, 'vmag', 'hpmag', 'v')
        c_pra: object = _find_tsv_col(lower_hdr, 'pmra', 'pm_ra')
        c_pde: object = _find_tsv_col(lower_hdr, 'pmde', 'pmdec', 'pm_de', 'pm_dec')
        if c_ra is None or c_de is None or c_mg is None:
            raise ValueError(f'Hipparcos TSV missing RA/Dec/Vmag columns: {hdr_tokens}')
        extracted: object = []
        mag_cap: object = float(max_mag)
        for cells in data_rows:
            v_mag: object = _safe_float(cells, c_mg, default=None)
            ra_d: object = _safe_float(cells, c_ra, default=None)
            de_d: object = _safe_float(cells, c_de, default=None)
            if v_mag is None or ra_d is None or de_d is None or (v_mag > mag_cap):
                continue
            hip_num: object = int(float(cells[c_id])) if c_id is not None else len(extracted) + 1
            extracted.append((hip_num, ra_d, de_d, v_mag, _safe_float(cells, c_pra, 0.0), _safe_float(cells, c_pde, 0.0)))
        if extracted:
            id_c, ra_c, de_c, mg_c, pra_c, pde_c = zip(*extracted)
        else:
            id_c = ra_c = de_c = mg_c = pra_c = pde_c = ()
        ra_rad: object = radians(asarray(ra_c, dtype=float64))
        dec_rad: object = radians(asarray(de_c, dtype=float64))
        pm_ra_rad: object = asarray(pra_c, dtype=float64) * _MAS_TO_RAD
        pm_de_rad: object = asarray(pde_c, dtype=float64) * _MAS_TO_RAD
        dt_yr: object = float(epoch_year) - J2000_EPOCH
        ra_prop: object = mod(ra_rad + pm_ra_rad / clip(cos(dec_rad), 1e-06, None) * dt_yr, 2.0 * pi)
        dec_prop: object = dec_rad + pm_de_rad * dt_yr
        return StarCatalog(ids=asarray(id_c, dtype=int32), vectors=ra_dec_to_vectors(ra_prop, dec_prop), mags=asarray(mg_c, dtype=float32), epoch_year=float(epoch_year), source='HIPPARCOS', ra_rad=ra_prop, dec_rad=dec_prop)

    @staticmethod
    def synthetic(n: object, max_mag: object, seed: object) -> object:
        gen: object = default_rng(seed)
        count: object = int(n)
        z_coord: object = gen.uniform(-1.0, 1.0, count)
        azim: object = gen.uniform(0.0, 2.0 * pi, count)
        rho: object = sqrt(1.0 - z_coord * z_coord)
        dirs: object = column_stack((rho * cos(azim), rho * sin(azim), z_coord))
        mags: object = clip(float(max_mag) - gen.exponential(scale=1.2, size=count), 0.5, float(max_mag)).astype(float32)
        return StarCatalog(ids=arange(1, count + 1, dtype=int32), vectors=dirs, mags=mags, epoch_year=J2000_EPOCH, source='SYNTHETIC')

    @staticmethod
    def filter_close_pairs(cat: object, min_sep_arcsec: object) -> object:
        total: object = int(cat.num_stars)
        if not total:
            return cat
        cos_thresh: object = float(cos(radians(float(min_sep_arcsec) / 3600.0)))
        rejected: object = zeros(total, dtype=bool)
        vecs, mags = (cat.vectors, cat.mags)
        step: object = 256
        for s_idx in range(0, total, step):
            e_idx: object = min(s_idx + step, total)
            sub_gram: object = vecs[s_idx:e_idx] @ vecs.T
            for rel_i, i_star in enumerate(range(s_idx, e_idx)):
                if rejected[i_star]:
                    continue
                neighbors: object = sub_gram[rel_i] >= cos_thresh
                neighbors[i_star] = False
                for j_star in where(neighbors)[0]:
                    if rejected[j_star]:
                        continue
                    i_brighter: object = mags[i_star] < mags[j_star] or (mags[i_star] == mags[j_star] and i_star < j_star)
                    if i_brighter:
                        rejected[j_star] = True
                    else:
                        rejected[i_star] = True
                        break
        mask: object = ~rejected
        opt_slice: object = lambda arr: None if arr is None else arr[mask]
        return StarCatalog(ids=cat.ids[mask], vectors=cat.vectors[mask], mags=cat.mags[mask], epoch_year=cat.epoch_year, source=cat.source + '+filt' if cat.source else 'filt', ra_rad=opt_slice(cat.ra_rad), dec_rad=opt_slice(cat.dec_rad), pm_ra_rad_yr=opt_slice(cat.pm_ra_rad_yr), pm_dec_rad_yr=opt_slice(cat.pm_dec_rad_yr))

    @staticmethod
    def save_npz(cat: object, path: object) -> object:
        out_path: object = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        empty_f: object = empty(0, dtype=float64)
        savez_compressed(out_path, ids=cat.ids, vectors=cat.vectors, mags=cat.mags, epoch_year=asarray([cat.epoch_year]), source=asarray([cat.source]), ra_rad=empty_f if cat.ra_rad is None else cat.ra_rad, dec_rad=empty_f if cat.dec_rad is None else cat.dec_rad)
        return out_path

    @staticmethod
    def load_npz(path: object) -> object:
        archive: object = npload(path, allow_pickle=False)
        get_nonempty: object = lambda k: archive[k] if k in archive and archive[k].size else None
        return StarCatalog(ids=archive['ids'], vectors=archive['vectors'], mags=archive['mags'], epoch_year=float(archive['epoch_year'][0]) if 'epoch_year' in archive else J2000_EPOCH, source=str(archive['source'][0]) if 'source' in archive else '', ra_rad=get_nonempty('ra_rad'), dec_rad=get_nonempty('dec_rad'))
