"""
J2000 star catalog: Yale BSC5 binary, Hipparcos TSV, synthetic fallback.

Harvard TDC BSC5 is 291 548 bytes. Coordinates in the binary file are radians.
Proper motion is applied from J2000.0 to `epoch_year`.
"""

from __future__ import annotations

import hashlib
import struct
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

BSC5_URL_HARVARD = "http://tdc-www.harvard.edu/catalogs/BSC5"
BSC5_URL_COTS = (
    "https://github.com/nasa/COTS-Star-Tracker/raw/master/"
    "py_src/tools/camera_calibration/tetra/BSC5"
)
BSC5_SIZE = 291_548
BSC5_N_ENTRIES = 9110
J2000_EPOCH = 2000.0


def ra_dec_to_vectors(ra_rad: np.ndarray, dec_rad: np.ndarray) -> np.ndarray:
    return np.column_stack(
        (
            np.cos(dec_rad) * np.cos(ra_rad),
            np.cos(dec_rad) * np.sin(ra_rad),
            np.sin(dec_rad),
        )
    )


def vectors_to_ra_dec(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x, y, z = vectors[:, 0], vectors[:, 1], vectors[:, 2]
    ra = np.mod(np.arctan2(y, x), 2.0 * np.pi)
    dec = np.arcsin(np.clip(z, -1.0, 1.0))
    return ra, dec


@dataclass
class StarCatalog:
    ids: np.ndarray
    vectors: np.ndarray
    mags: np.ndarray
    epoch_year: float = J2000_EPOCH
    source: str = ""
    ra_rad: np.ndarray | None = None
    dec_rad: np.ndarray | None = None
    pm_ra_rad_yr: np.ndarray | None = None
    pm_dec_rad_yr: np.ndarray | None = None
    num_stars: int = field(init=False)

    def __post_init__(self):
        self.ids = np.asarray(self.ids, dtype=np.int32)
        self.vectors = np.asarray(self.vectors, dtype=np.float64)
        norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
        self.vectors = self.vectors / np.where(norms > 0, norms, 1.0)
        self.mags = np.asarray(self.mags, dtype=np.float32)
        self.num_stars = int(len(self.ids))
        if self.ra_rad is None or self.dec_rad is None:
            ra, dec = vectors_to_ra_dec(self.vectors)
            self.ra_rad = ra
            self.dec_rad = dec

    @property
    def star_ids(self) -> np.ndarray:
        return self.ids

    @property
    def magnitudes(self) -> np.ndarray:
        return self.mags

    def fingerprint(self) -> str:
        h = hashlib.sha256()
        h.update(self.ids.tobytes())
        h.update(self.vectors.tobytes())
        h.update(self.mags.tobytes())
        h.update(repr(self.epoch_year).encode())
        h.update(self.source.encode())
        return h.hexdigest()[:16]

    @classmethod
    def create_synthetic_hipparcos_subset(
        cls, num_stars: int = 3500, max_mag: float = 6.0, seed: int = 42
    ) -> "StarCatalog":
        return CatalogManager.synthetic(num_stars, max_mag, seed)


class CatalogManager:
    BSC5_URL = BSC5_URL_HARVARD
    BSC5_SIZE = BSC5_SIZE
    # Binary XRPM is the projected motion μα cos δ (rad/yr), same as V/50 ASCII pmRA.
    BSC5_PM_RA_INCLUDES_COS_DEC = True

    @staticmethod
    def fetch_bsc5(dest: Path, timeout_s: float = 60.0) -> Path:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size == BSC5_SIZE:
            return dest
        errors: list[str] = []
        for url in (BSC5_URL_HARVARD, BSC5_URL_COTS):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Tracker-ST/1.0"})
                with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                    data = resp.read()
                if len(data) != BSC5_SIZE:
                    errors.append(f"{url}: size {len(data)} != {BSC5_SIZE}")
                    continue
                dest.write_bytes(data)
                return dest
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{url}: {exc}")
        raise FileNotFoundError(
            "Could not download BSC5 (291548 bytes). Tried Harvard TDC and NASA COTS mirror. "
            + " | ".join(errors)
        )

    @staticmethod
    def parse_bsc5_header(path: Path) -> dict:
        raw = Path(path).read_bytes()
        if len(raw) != BSC5_SIZE:
            raise ValueError(f"BSC5 size {len(raw)} != {BSC5_SIZE}")
        header = raw[:28]
        for endian in ("<", ">"):
            star0, star1, starn, stnum, mprop, nmag, nbent = struct.unpack(endian + "7i", header)
            if abs(starn) == BSC5_N_ENTRIES and nbent == 32:
                return {
                    "endian": endian,
                    "STAR0": star0,
                    "STAR1": star1,
                    "STARN": starn,
                    "STNUM": stnum,
                    "MPROP": mprop,
                    "NMAG": nmag,
                    "NBENT": nbent,
                    "n_entries": abs(starn),
                    "j2000": starn < 0 or nmag < 0,
                    "raw_size": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
        raise ValueError(
            "BSC5 header does not match Harvard TDC binary layout (STARN=±9110, NBENT=32)."
        )

    @staticmethod
    def load_bsc5(
        path: Path,
        max_mag: float = 6.0,
        epoch_year: float = 2026.7,
        apply_pm: bool = True,
    ) -> StarCatalog:
        path = Path(path)
        raw = path.read_bytes()
        header = CatalogManager.parse_bsc5_header(path)
        endian = header["endian"]
        n = header["n_entries"]
        nbent = header["NBENT"]
        rec_fmt = endian + "fdd2shff"
        ids = []
        ra_list = []
        dec_list = []
        mag_list = []
        pmra_list = []
        pmdec_list = []
        n_blank = 0
        for i in range(n):
            rec = raw[28 + i * nbent : 28 + (i + 1) * nbent]
            xno, sra, sdec, _isp, mag_i, xrpm, xdpm = struct.unpack(rec_fmt, rec)
            if sra == 0.0 and sdec == 0.0:
                n_blank += 1
                continue
            mag = mag_i / 100.0
            ids.append(int(round(xno)) if xno != 0.0 else i + 1)
            ra_list.append(sra)
            dec_list.append(sdec)
            mag_list.append(mag)
            pmra_list.append(xrpm)
            pmdec_list.append(xdpm)
        ra = np.array(ra_list, dtype=np.float64)
        dec = np.array(dec_list, dtype=np.float64)
        pm_ra = np.array(pmra_list, dtype=np.float64)
        pm_dec = np.array(pmdec_list, dtype=np.float64)
        dt = float(epoch_year) - J2000_EPOCH
        if apply_pm and dt != 0.0:
            # XRPM = μα cos δ → Δα = XRPM / cos δ * dt
            cosd = np.clip(np.cos(dec), 1e-6, None)
            ra = ra + (pm_ra / cosd) * dt
            dec = dec + pm_dec * dt
            ra = np.mod(ra, 2.0 * np.pi)
        mag_arr = np.array(mag_list, dtype=np.float32)
        keep = mag_arr <= max_mag
        cat = StarCatalog(
            ids=np.array(ids, dtype=np.int32)[keep],
            vectors=ra_dec_to_vectors(ra[keep], dec[keep]),
            mags=mag_arr[keep],
            epoch_year=float(epoch_year),
            source="BSC5",
            ra_rad=ra[keep],
            dec_rad=dec[keep],
            pm_ra_rad_yr=pm_ra[keep],
            pm_dec_rad_yr=pm_dec[keep],
        )
        cat.n_blank = n_blank  # type: ignore[attr-defined]
        cat.n_raw_stars = n - n_blank  # type: ignore[attr-defined]
        return cat

    @staticmethod
    def load_hipparcos_tsv(
        path: Path,
        max_mag: float = 6.0,
        epoch_year: float = 2026.7,
    ) -> StarCatalog:
        """
        Load a Hipparcos I/239 TSV with columns including RA, Dec, Vmag.
        Hipparcos pmRA is μα cos δ in mas/yr.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        rows = []
        header = None
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = [c.strip() for c in line.replace("|", "\t").split("\t")]
                if header is None:
                    header = parts
                    continue
                if len(parts) < 4:
                    continue
                rows.append(parts)
        if header is None:
            raise ValueError(f"Hipparcos TSV {path} has no header row.")
        header_l = [c.lower() for c in header]

        def _col(*names: str) -> int | None:
            for name in names:
                if name.lower() in header_l:
                    return header_l.index(name.lower())
            return None

        i_id = _col("hip", "id", "hip_id")
        i_ra = _col("_raj2000", "ra_deg", "ra_icrs", "raj2000", "ra")
        i_dec = _col("_dej2000", "dec_deg", "de_icrs", "dej2000", "dec", "de")
        i_mag = _col("vmag", "hpmag", "v")
        i_pmra = _col("pmra", "pm_ra")
        i_pmde = _col("pmde", "pmdec", "pm_de", "pm_dec")
        if i_ra is None or i_dec is None or i_mag is None:
            raise ValueError(f"Hipparcos TSV missing RA/Dec/Vmag columns: {header}")

        ids, ra_deg, dec_deg, mags, pmra, pmde = [], [], [], [], [], []
        for parts in rows:
            try:
                mag = float(parts[i_mag])
            except (ValueError, IndexError):
                continue
            if mag > max_mag:
                continue
            try:
                ra_d = float(parts[i_ra])
                de_d = float(parts[i_dec])
            except (ValueError, IndexError):
                continue
            hip = int(float(parts[i_id])) if i_id is not None else len(ids) + 1
            ids.append(hip)
            ra_deg.append(ra_d)
            dec_deg.append(de_d)
            mags.append(mag)
            try:
                pmra.append(float(parts[i_pmra]) if i_pmra is not None and parts[i_pmra] else 0.0)
            except (ValueError, TypeError):
                pmra.append(0.0)
            try:
                pmde.append(float(parts[i_pmde]) if i_pmde is not None and parts[i_pmde] else 0.0)
            except (ValueError, TypeError):
                pmde.append(0.0)

        ra = np.radians(np.array(ra_deg, dtype=np.float64))
        dec = np.radians(np.array(dec_deg, dtype=np.float64))
        pmra_mas = np.array(pmra, dtype=np.float64)
        pmde_mas = np.array(pmde, dtype=np.float64)
        dt = float(epoch_year) - J2000_EPOCH
        mas_to_rad = np.pi / (180.0 * 3_600_000.0)
        cosd = np.clip(np.cos(dec), 1e-6, None)
        ra = np.mod(ra + (pmra_mas * mas_to_rad / cosd) * dt, 2.0 * np.pi)
        dec = dec + pmde_mas * mas_to_rad * dt
        return StarCatalog(
            ids=np.array(ids, dtype=np.int32),
            vectors=ra_dec_to_vectors(ra, dec),
            mags=np.array(mags, dtype=np.float32),
            epoch_year=float(epoch_year),
            source="HIPPARCOS",
            ra_rad=ra,
            dec_rad=dec,
        )

    @staticmethod
    def synthetic(n: int, max_mag: float, seed: int) -> StarCatalog:
        rng = np.random.default_rng(seed)
        ids = np.arange(1, n + 1, dtype=np.int32)
        u = rng.uniform(-1.0, 1.0, n)
        theta = rng.uniform(0.0, 2.0 * np.pi, n)
        vecs = np.column_stack(
            (
                np.sqrt(1.0 - u * u) * np.cos(theta),
                np.sqrt(1.0 - u * u) * np.sin(theta),
                u,
            )
        )
        mags = max_mag - rng.exponential(scale=1.2, size=n)
        mags = np.clip(mags, 0.5, max_mag).astype(np.float32)
        return StarCatalog(
            ids=ids, vectors=vecs, mags=mags, epoch_year=J2000_EPOCH, source="SYNTHETIC"
        )

    @staticmethod
    def filter_close_pairs(cat: StarCatalog, min_sep_arcsec: float) -> StarCatalog:
        n = cat.num_stars
        if n == 0:
            return cat
        min_sep = np.radians(min_sep_arcsec / 3600.0)
        min_cos = np.cos(min_sep)
        drop = np.zeros(n, dtype=bool)
        vecs = cat.vectors
        mags = cat.mags
        block = 256
        for i0 in range(0, n, block):
            i1 = min(i0 + block, n)
            dots = vecs[i0:i1] @ vecs.T
            for li, i in enumerate(range(i0, i1)):
                if drop[i]:
                    continue
                close = dots[li] >= min_cos
                close[i] = False
                js = np.where(close)[0]
                for j in js:
                    if drop[j]:
                        continue
                    if mags[i] < mags[j] or (mags[i] == mags[j] and i < j):
                        drop[j] = True
                    else:
                        drop[i] = True
                        break
        keep = ~drop
        return StarCatalog(
            ids=cat.ids[keep],
            vectors=cat.vectors[keep],
            mags=cat.mags[keep],
            epoch_year=cat.epoch_year,
            source=cat.source + "+filt" if cat.source else "filt",
            ra_rad=None if cat.ra_rad is None else cat.ra_rad[keep],
            dec_rad=None if cat.dec_rad is None else cat.dec_rad[keep],
            pm_ra_rad_yr=None if cat.pm_ra_rad_yr is None else cat.pm_ra_rad_yr[keep],
            pm_dec_rad_yr=None if cat.pm_dec_rad_yr is None else cat.pm_dec_rad_yr[keep],
        )

    @staticmethod
    def save_npz(cat: StarCatalog, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            ids=cat.ids,
            vectors=cat.vectors,
            mags=cat.mags,
            epoch_year=np.array([cat.epoch_year]),
            source=np.array([cat.source]),
            ra_rad=np.array([]) if cat.ra_rad is None else cat.ra_rad,
            dec_rad=np.array([]) if cat.dec_rad is None else cat.dec_rad,
        )
        return path

    @staticmethod
    def load_npz(path: Path) -> StarCatalog:
        data = np.load(path, allow_pickle=False)
        ra = data["ra_rad"] if "ra_rad" in data and data["ra_rad"].size else None
        dec = data["dec_rad"] if "dec_rad" in data and data["dec_rad"].size else None
        source = str(data["source"][0]) if "source" in data else ""
        epoch = float(data["epoch_year"][0]) if "epoch_year" in data else J2000_EPOCH
        return StarCatalog(
            ids=data["ids"],
            vectors=data["vectors"],
            mags=data["mags"],
            epoch_year=epoch,
            source=source,
            ra_rad=ra,
            dec_rad=dec,
        )
