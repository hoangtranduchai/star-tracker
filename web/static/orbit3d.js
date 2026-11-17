/* StarTrackerOrbit3D — 3D Earth-Orbit Attitude & J2000 Real Celestial Sky Visualization */
(function () {
  "use strict";

  const DEG2RAD = Math.PI / 180;
  const RAD2DEG = 180 / Math.PI;
  const R_EARTH = 1.0;
  const R_ATMOS = 1.078;
  const R_ORBIT = 1.85;
  const R_SKY = 420.0;
  const R_GRID = 418.0;
  const R_FRAME = 416.5;
  const R_RETICLE = 415.5;
  const R_DUST = 432.0;

  // Built-in J2000 bright navigation stars for instant zero-latency sky & landmark labels
  // [hr, name, raDeg, decDeg, mag]
  const LANDMARK_STARS = [
    [2491, "Sirius", 101.2872, -16.7161, -1.46],
    [2326, "Canopus", 95.9879, -52.6957, -0.74],
    [5340, "Arcturus", 213.9153, 19.1824, -0.05],
    [5459, "Rigil Kent", 219.9021, -60.8340, -0.01],
    [7001, "Vega", 279.2347, 38.7837, 0.03],
    [1708, "Capella", 79.1723, 45.9980, 0.08],
    [1713, "Rigel", 78.6345, -8.2016, 0.13],
    [2943, "Procyon", 114.8255, 5.2250, 0.34],
    [472, "Achernar", 24.4286, -57.2368, 0.46],
    [2061, "Betelgeuse", 88.7929, 7.4071, 0.50],
    [5267, "Hadar", 210.9559, -60.3730, 0.61],
    [7557, "Altair", 297.6958, 8.8683, 0.76],
    [4730, "Acrux", 186.6496, -63.0991, 0.77],
    [1457, "Aldebaran", 68.9802, 16.5093, 0.86],
    [6134, "Antares", 247.3519, -26.4320, 0.96],
    [5056, "Spica", 201.2982, -11.1613, 0.97],
    [2990, "Pollux", 116.3290, 28.0262, 1.14],
    [8728, "Fomalhaut", 344.4127, -29.6222, 1.16],
    [7924, "Deneb", 310.3580, 45.2803, 1.25],
    [4853, "Mimosa", 191.9303, -59.6888, 1.25],
    [3982, "Regulus", 152.0929, 11.9672, 1.36],
    [2618, "Adhara", 104.6565, -28.9721, 1.50],
    [2891, "Castor", 113.6494, 31.8883, 1.58],
    [4763, "Gacrux", 187.7915, -57.1132, 1.63],
    [6527, "Shaula", 263.4022, -37.1038, 1.62],
    [1790, "Bellatrix", 81.2828, 6.3497, 1.64],
    [1791, "Elnath", 81.5730, 28.6075, 1.65],
    [3685, "Miaplacidus", 138.2999, -69.7172, 1.67],
    [1903, "Alnilam", 84.0534, -1.2019, 1.69],
    [8425, "Alnair", 332.0583, -46.9610, 1.74],
    [1948, "Alnitak", 85.1897, -1.9426, 1.77],
    [4905, "Alioth", 193.5073, 55.9598, 1.77],
    [4301, "Dubhe", 165.9320, 61.7510, 1.79],
    [1017, "Mirfak", 51.0807, 49.8612, 1.79],
    [2693, "Wezen", 107.0979, -26.3932, 1.83],
    [5191, "Alkaid", 206.8852, 49.3133, 1.85],
    [1852, "Mintaka", 83.0017, -0.2991, 2.23],
    [424, "Polaris", 37.9546, 89.2641, 1.98]
  ];

  // Warm / cool spectral hints for prominent stars (subtle astronomical blackbody tint)
  const WARM_HRS = new Set([2061, 6134, 1457, 5340, 4763, 2990, 1708]);
  const COOL_HRS = new Set([2491, 7001, 1713, 5056, 7924, 4730, 4853, 5267, 1903, 1948, 1790]);

  const ICONS = {
    orbit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="4.5"/><ellipse cx="12" cy="12" rx="10" ry="4.2" transform="rotate(-24 12 12)"/></svg>',
    pov: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16"/><circle cx="12" cy="12" r="2.5"/></svg>',
    pause: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="7" y="5" width="3.5" height="14" rx="1"/><rect x="13.5" y="5" width="3.5" height="14" rx="1"/></svg>',
    play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polygon points="7,5 19,12 7,19" fill="currentColor" stroke="none"/></svg>',
    labels: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3z"/><path d="M18 16l.9 2.1L21 19l-2.1.9L18 22l-.9-2.1L15 19l2.1-.9L18 16z"/></svg>',
    grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4.2" ry="9"/><line x1="3.2" y1="12" x2="20.8" y2="12"/></svg>',
    reset: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><polyline points="3 3 3 8 8 8"/></svg>'
  };

  function clamp(v, lo, hi) {
    return v < lo ? lo : v > hi ? hi : v;
  }

  // Exact right-handed J2000 ICRS -> Three.js World mapping (det = +1):
  // J2000 +Z (North Celestial Pole) -> +Y, J2000 +X (RA=0) -> +X, J2000 +Y (RA=90) -> -Z
  function icrsToWorldXYZ(vx, vy, vz) {
    return [vx, vz, -vy];
  }

  function raDecToIcrs(raDeg, decDeg) {
    const ra = raDeg * DEG2RAD;
    const dec = decDeg * DEG2RAD;
    const cd = Math.cos(dec);
    return [cd * Math.cos(ra), cd * Math.sin(ra), Math.sin(dec)];
  }

  // Exact scalar-first unit quaternion q=[q0,q1,q2,q3] -> 3x3 DCM A (b_cam = A @ r_icrs)
  // Matches src/quaternion.py::to_dcm 1-to-1
  function quatToDcm(q) {
    if (!Array.isArray(q) || q.length < 4) return null;
    let q0 = Number(q[0]);
    let q1 = Number(q[1]);
    let q2 = Number(q[2]);
    let q3 = Number(q[3]);
    if (!Number.isFinite(q0) || !Number.isFinite(q1) || !Number.isFinite(q2) || !Number.isFinite(q3)) {
      return null;
    }
    const mag = Math.hypot(q0, q1, q2, q3);
    if (!(mag > 1e-12)) return null;
    const inv = (q0 < 0 ? -1.0 : 1.0) / mag;
    q0 *= inv;
    q1 *= inv;
    q2 *= inv;
    q3 *= inv;
    const diag = q0 * q0 - (q1 * q1 + q2 * q2 + q3 * q3);
    return [
      [diag + 2 * q1 * q1, 2 * (q1 * q2 - q0 * q3), 2 * (q1 * q3 + q0 * q2)],
      [2 * (q2 * q1 + q0 * q3), diag + 2 * q2 * q2, 2 * (q2 * q3 - q0 * q1)],
      [2 * (q3 * q1 - q0 * q2), 2 * (q3 * q2 + q0 * q1), diag + 2 * q3 * q3]
    ];
  }

  function formatRaCompact(raDeg) {
    const wrapped = ((Number(raDeg) % 360) + 360) % 360;
    const totalSec = (wrapped / 15) * 3600;
    const h = Math.floor(totalSec / 3600) % 24;
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    const hh = String(h).padStart(2, "0");
    const mm = String(m).padStart(2, "0");
    const ss = s.toFixed(1).padStart(4, "0");
    return `${hh}h ${mm}m ${ss}s`;
  }

  function formatDecCompact(decDeg) {
    const val = Number(decDeg);
    const sign = val >= 0 ? "+" : "-";
    const absDeg = Math.abs(val);
    const d = Math.floor(absDeg);
    const remMin = (absDeg - d) * 60;
    const m = Math.floor(remMin);
    const s = Math.round((remMin - m) * 60);
    const secAdj = s === 60 ? 0 : s;
    const minAdj = s === 60 ? m + 1 : m;
    return `${sign}${String(d).padStart(2, "0")}° ${String(minAdj).padStart(2, "0")}′ ${String(secAdj).padStart(2, "0")}″`;
  }

  // Fast deterministic PRNG (Mulberry32) for procedural Earth & Milky Way micro-dust
  function makePrng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // Fast 3D Lattice Value Noise on unit sphere (zero antimeridian seam, zero pole pinch)
  function createNoise3D(seed) {
    const rng = makePrng(seed);
    const perm = new Uint8Array(512);
    const vals = new Float32Array(256);
    const p = new Uint8Array(256);
    for (let i = 0; i < 256; i++) {
      p[i] = i;
      vals[i] = rng() * 2 - 1;
    }
    for (let i = 255; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      const tmp = p[i];
      p[i] = p[j];
      p[j] = tmp;
    }
    for (let i = 0; i < 512; i++) perm[i] = p[i & 255];

    return function noise3(x, y, z) {
      const xi = Math.floor(x);
      const yi = Math.floor(y);
      const zi = Math.floor(z);
      const xf = x - xi;
      const yf = y - yi;
      const zf = z - zi;
      const u = xf * xf * (3 - 2 * xf);
      const v = yf * yf * (3 - 2 * yf);
      const w = zf * zf * (3 - 2 * zf);

      const X = xi & 255;
      const Y = yi & 255;
      const Z = zi & 255;

      const A = perm[X] + Y;
      const AA = perm[A] + Z;
      const AB = perm[A + 1] + Z;
      const B = perm[X + 1] + Y;
      const BA = perm[B] + Z;
      const BB = perm[B + 1] + Z;

      const c000 = vals[perm[AA]];
      const c100 = vals[perm[BA]];
      const c010 = vals[perm[AB]];
      const c110 = vals[perm[BB]];
      const c001 = vals[perm[AA + 1]];
      const c101 = vals[perm[BA + 1]];
      const c011 = vals[perm[AB + 1]];
      const c111 = vals[perm[BB + 1]];

      const x00 = c000 + u * (c100 - c000);
      const x10 = c010 + u * (c110 - c010);
      const x01 = c001 + u * (c101 - c001);
      const x11 = c011 + u * (c111 - c011);
      const y0 = x00 + v * (x10 - x00);
      const y1 = x01 + v * (x11 - x01);
      return y0 + w * (y1 - y0);
    };
  }

  // Macro continental spherical harmonic lobes [latDeg, lonDeg, cosRadius, weight]
  // Gives recognizable Earth land silhouettes modulated by 5-octave 3D fractal coastlines
  const CONTINENT_LOBES = [
    [48, -102, 0.24, 0.62],  // North America core
    [60, -135, 0.14, 0.42],  // Alaska / W Canada
    [22, -100, 0.09, 0.34],  // Central America
    [-12, -60, 0.18, 0.60],  // South America N
    [-34, -65, 0.11, 0.44],  // Patagonia
    [73, -42, 0.11, 0.50],   // Greenland
    [16, 18, 0.24, 0.66],    // North/West Africa
    [-14, 24, 0.16, 0.56],   // Southern Africa
    [50, 14, 0.15, 0.48],    // Europe
    [56, 75, 0.32, 0.68],    // Eurasia / Siberia
    [35, 104, 0.22, 0.62],   // East Asia
    [23, 79, 0.11, 0.46],    // India
    [24, 45, 0.11, 0.46],    // Arabia
    [15, 106, 0.08, 0.42],   // Mainland SE Asia / Vietnam
    [-2, 115, 0.09, 0.30],   // Maritime SE Asia
    [-25, 134, 0.14, 0.56],  // Australia
    [-82, 30, 0.22, 0.68],   // East Antarctica
    [-80, -110, 0.16, 0.52], // West Antarctica
    [-20, 47, 0.05, 0.32],   // Madagascar
    [37, 139, 0.05, 0.30]    // Japan
  ].map(([lat, lon, rad, w]) => {
    const phi = lat * DEG2RAD;
    const lam = lon * DEG2RAD;
    return {
      x: Math.cos(phi) * Math.cos(lam),
      y: Math.sin(phi),
      z: Math.cos(phi) * Math.sin(lam),
      invR2: 1 / (rad * rad),
      w
    };
  });

  function buildEarthTextures(THREE) {
    if (typeof document === "undefined") return { dayTex: null, auxTex: null };
    const W = 1024;
    const H = 512;
    const GW = 360;
    const GH = 180;
    const n3 = createNoise3D(2026083);
    const nCloud = createNoise3D(91105023);

    // Precompute macro elevation, moisture, night-city, and cloud fields on 360x180 (0.5 deg) spherical grid
    const elevGrid = new Float32Array(GW * GH);
    const moistGrid = new Float32Array(GW * GH);
    const cityGrid = new Float32Array(GW * GH);
    const cloudGrid = new Float32Array(GW * GH);

    const cosLonG = new Float32Array(GW);
    const sinLonG = new Float32Array(GW);
    for (let gx = 0; gx < GW; gx++) {
      const lon = ((gx + 0.5) / GW - 0.5) * Math.PI * 2;
      cosLonG[gx] = Math.cos(lon);
      sinLonG[gx] = Math.sin(lon);
    }

    for (let gy = 0; gy < GH; gy++) {
      const v = (gy + 0.5) / GH;
      const lat = (0.5 - v) * Math.PI;
      const cl = Math.cos(lat);
      const sy = Math.sin(lat);
      const absLat = Math.abs(lat) * RAD2DEG;
      const subtropBelt = 0.32 * Math.exp(-Math.pow((absLat - 25) / 11, 2));
      const tradeBand = 0.12 * Math.cos(lat * 5.5);

      for (let gx = 0; gx < GW; gx++) {
        const sx = cl * cosLonG[gx];
        const sz = cl * sinLonG[gx];

        let macro = -0.34;
        for (let k = 0; k < CONTINENT_LOBES.length; k++) {
          const L = CONTINENT_LOBES[k];
          const dx = sx - L.x;
          const dy = sy - L.y;
          const dz = sz - L.z;
          const d2 = (dx * dx + dy * dy + dz * dz) * L.invR2;
          if (d2 < 3.0) {
            const t = 1.0 - d2 * 0.333333;
            macro += L.w * t * t * t;
          }
        }

        // Domain-warped 4-octave fractal coastline & mountain ridges
        const warp = 0.28 * n3(sx * 2.4 + 4.1, sy * 2.4 + 1.7, sz * 2.4 - 2.3);
        const wx = sx * 3.1 + warp;
        const wy = sy * 3.1 - warp * 0.7;
        const wz = sz * 3.1 + warp * 0.85;
        const fbm =
          0.53 * n3(wx, wy, wz) +
          0.26 * n3(wx * 2.15, wy * 2.15, wz * 2.15) +
          0.13 * n3(wx * 4.5, wy * 4.5, wz * 4.5) +
          0.08 * n3(wx * 9.5, wy * 9.5, wz * 9.5);

        const elev = macro + fbm * 0.48;
        const idx = gy * GW + gx;
        elevGrid[idx] = elev;

        const moist = 0.5 + 0.5 * n3(sx * 3.6 + 11.2, sy * 3.6 - 5.4, sz * 3.6 + 8.1) - subtropBelt;
        moistGrid[idx] = moist;

        // Subtle coastal & temperate settlement glow on night side
        let city = 0;
        if (elev > 0.015 && elev < 0.36 && absLat < 58 && absLat > 5) {
          const cluster = n3(sx * 18.0 + 3.0, sy * 18.0 - 2.0, sz * 18.0 + 6.0);
          if (cluster > 0.20) {
            const fine = n3(sx * 40.0, sy * 40.0, sz * 40.0);
            if (fine > 0.06) {
              const coastBoost = 1.0 - clamp((elev - 0.015) / 0.22, 0, 1) * 0.55;
              city = clamp((cluster - 0.20) * 1.9 * coastBoost, 0, 1);
            }
          }
        }
        cityGrid[idx] = city;

        // Swirled atmospheric cloud bands
        const swirl = 0.35 * nCloud(sx * 2.2, sy * 2.2 + 3.1, sz * 2.2);
        const cVal =
          0.55 * nCloud(sx * 3.8 + swirl, sy * 5.2, sz * 3.8 - swirl) +
          0.29 * nCloud(sx * 8.2, sy * 9.4, sz * 8.2) +
          0.16 * nCloud(sx * 16.5, sy * 16.5, sz * 16.5) +
          tradeBand;
        cloudGrid[idx] = clamp((cVal - 0.08) * 1.55, 0, 1);
      }
    }

    const dayCanvas = document.createElement("canvas");
    dayCanvas.width = W;
    dayCanvas.height = H;
    const dayCtx = dayCanvas.getContext("2d");
    const dayImg = dayCtx.createImageData(W, H);
    const dd = dayImg.data;

    const auxCanvas = document.createElement("canvas");
    auxCanvas.width = W;
    auxCanvas.height = H;
    const auxCtx = auxCanvas.getContext("2d");
    const auxImg = auxCtx.createImageData(W, H);
    const ad = auxImg.data;

    // Precompute horizontal bilinear weights once across 1024 columns
    const x0Arr = new Int32Array(W);
    const x1Arr = new Int32Array(W);
    const txArr = new Float32Array(W);
    for (let x = 0; x < W; x++) {
      const fx = ((x + 0.5) / W) * GW - 0.5;
      const x0 = Math.floor(fx);
      const x0w = ((x0 % GW) + GW) % GW;
      x0Arr[x] = x0w;
      x1Arr[x] = (x0w + 1) % GW;
      txArr[x] = fx - x0;
    }

    for (let y = 0; y < H; y++) {
      const v = (y + 0.5) / H;
      const lat = (0.5 - v) * Math.PI;
      const absLat = Math.abs(lat) * RAD2DEG;
      const fy = v * GH - 0.5;
      const y0f = Math.floor(fy);
      const y0 = clamp(y0f, 0, GH - 1);
      const y1 = clamp(y0f + 1, 0, GH - 1);
      const ty = fy - y0f;
      const r0 = y0 * GW;
      const r1 = y1 * GW;
      const latVeg = 1 - clamp(absLat / 65, 0, 1);
      const latCool = clamp(absLat / 70, 0, 1);

      for (let x = 0; x < W; x++) {
        const i00 = r0 + x0Arr[x];
        const i10 = r0 + x1Arr[x];
        const i01 = r1 + x0Arr[x];
        const i11 = r1 + x1Arr[x];
        const tx = txArr[x];

        const e0 = elevGrid[i00] + tx * (elevGrid[i10] - elevGrid[i00]);
        const e1 = elevGrid[i01] + tx * (elevGrid[i11] - elevGrid[i01]);
        // Fast deterministic fine-grain shoreline hash
        const h1 = (((x >> 1) * 374761393 + (y >> 1) * 668265263) ^ 0x5bf03635) >>> 0;
        const micro = ((h1 & 1023) / 511.5 - 1.0) * 0.014;
        const elev = e0 + ty * (e1 - e0) + micro;

        const m0 = moistGrid[i00] + tx * (moistGrid[i10] - moistGrid[i00]);
        const m1 = moistGrid[i01] + tx * (moistGrid[i11] - moistGrid[i01]);
        const moist = m0 + ty * (m1 - m0);

        const c0 = cityGrid[i00] + tx * (cityGrid[i10] - cityGrid[i00]);
        const c1 = cityGrid[i01] + tx * (cityGrid[i11] - cityGrid[i01]);
        const city = c0 + ty * (c1 - c0);

        const cl0 = cloudGrid[i00] + tx * (cloudGrid[i10] - cloudGrid[i00]);
        const cl1 = cloudGrid[i01] + tx * (cloudGrid[i11] - cloudGrid[i01]);
        const cloud = clamp(cl0 + ty * (cl1 - cl0) + micro * 1.2, 0, 1);

        let r, g, b, waterSpec;
        const polarCap = absLat + micro * 120 > 74.5;

        if (polarCap && (elev > -0.16 || absLat > 81.5)) {
          const shade = 0.88 + 0.10 * clamp(elev + 0.2, 0, 1);
          r = 216 * shade;
          g = 229 * shade;
          b = 241 * shade;
          waterSpec = 0.12;
        } else if (elev <= 0.0) {
          const depth = clamp(-elev / 0.48, 0, 1);
          const om = 1 - depth;
          const shelf = om * om * om;
          r = 5 + 14 * om + 16 * shelf;
          g = 17 + 28 * om + 36 * shelf;
          b = 38 + 46 * om + 42 * shelf;
          waterSpec = 0.92;
        } else {
          waterSpec = 0.04;
          const hNorm = clamp(elev / 0.55, 0, 1);
          const mClamp = clamp(moist, 0, 1);
          const arid = clamp(1.0 - moist * 1.25, 0, 1);
          let lr = 26 + 22 * latVeg;
          let lg = 52 + 24 * mClamp - 10 * latCool;
          let lb = 36 + 10 * mClamp;
          lr += arid * (108 - lr);
          lg += arid * (94 - lg);
          lb += arid * (68 - lb);
          if (hNorm > 0.52) {
            const rockT = clamp((hNorm - 0.52) / 0.32, 0, 1);
            lr += rockT * (92 - lr);
            lg += rockT * (89 - lg);
            lb += rockT * (86 - lb);
          }
          if (hNorm > 0.80) {
            const snowT = clamp((hNorm - 0.80) / 0.18, 0, 1);
            lr += snowT * (220 - lr);
            lg += snowT * (228 - lg);
            lb += snowT * (236 - lb);
          }
          r = lr;
          g = lg;
          b = lb;
        }

        const pIdx = (y * W + x) * 4;
        dd[pIdx] = r;
        dd[pIdx + 1] = g;
        dd[pIdx + 2] = b;
        dd[pIdx + 3] = waterSpec * 255;

        ad[pIdx] = cloud * 255;
        ad[pIdx + 1] = city * 255;
        ad[pIdx + 2] = 0;
        ad[pIdx + 3] = 255;
      }
    }

    dayCtx.putImageData(dayImg, 0, 0);
    auxCtx.putImageData(auxImg, 0, 0);

    const dayTex = new THREE.CanvasTexture(dayCanvas);
    dayTex.wrapS = THREE.RepeatWrapping;
    dayTex.wrapT = THREE.ClampToEdgeWrapping;
    dayTex.anisotropy = 4;

    const auxTex = new THREE.CanvasTexture(auxCanvas);
    auxTex.wrapS = THREE.RepeatWrapping;
    auxTex.wrapT = THREE.ClampToEdgeWrapping;
    auxTex.anisotropy = 4;

    return { dayTex, auxTex };
  }

  function buildSolarPanelTexture(THREE) {
    if (typeof document === "undefined") return null;
    const c = document.createElement("canvas");
    c.width = 256;
    c.height = 128;
    const ctx = c.getContext("2d");
    ctx.fillStyle = "#081428";
    ctx.fillRect(0, 0, 256, 128);

    // Individual monocrystalline photovoltaic cells
    const cols = 8;
    const rows = 4;
    const pad = 2;
    const cw = 256 / cols;
    const ch = 128 / rows;
    for (let r = 0; r < rows; r++) {
      for (let col = 0; col < cols; col++) {
        const grad = ctx.createLinearGradient(col * cw, r * ch, (col + 1) * cw, (r + 1) * ch);
        grad.addColorStop(0, "#0c203e");
        grad.addColorStop(0.5, "#102a52");
        grad.addColorStop(1, "#091933");
        ctx.fillStyle = grad;
        ctx.fillRect(col * cw + pad, r * ch + pad, cw - pad * 2, ch - pad * 2);

        ctx.strokeStyle = "rgba(148, 163, 184, 0.22)";
        ctx.lineWidth = 0.75;
        ctx.beginPath();
        ctx.moveTo(col * cw + cw * 0.5, r * ch + pad);
        ctx.lineTo(col * cw + cw * 0.5, (r + 1) * ch - pad);
        ctx.stroke();
      }
    }
    ctx.strokeStyle = "rgba(202, 154, 70, 0.45)";
    ctx.lineWidth = 2;
    ctx.strokeRect(1, 1, 254, 126);

    const tex = new THREE.CanvasTexture(c);
    if (THREE.SRGBColorSpace) tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    return tex;
  }

  // Controller state
  const state = {
    initialized: false,
    webglOk: false,
    container: null,
    stageEl: null,
    labelLayerEl: null,
    dotEl: null,
    telemetryTextEl: null,
    telemetryMetaEl: null,
    hintPillEl: null,
    povZoomWrapEl: null,
    btnZoomWide: null,
    btnZoomTight: null,
    btnModeOrbit: null,
    btnModePov: null,
    btnPlay: null,
    btnPlayTxt: null,
    btnPlayIcon: null,
    btnLabels: null,
    btnGrid: null,
    fallbackDescEl: null,

    // Three.js core
    renderer: null,
    scene: null,
    camera: null,
    resizeObserver: null,
    rafId: 0,
    lastTimeMs: 0,

    // Scene groups & materials
    skyGroup: null,
    starPoints: null,
    starMaterial: null,
    dustPoints: null,
    gridGroup: null,
    skyFovGroup: null,
    reticlePoints: null,
    reticleMaterial: null,

    earthGroup: null,
    earthMesh: null,
    earthMaterial: null,
    atmosMesh: null,
    atmosMaterial: null,
    sunDirWorld: null,

    orbitRingLine: null,
    satelliteGroup: null,
    attitudeGroup: null,
    spacecraftMeshes: [],
    frustumGroup: null,
    frustumConeMat: null,
    frustumEdgeMat: null,

    // Catalog storage
    catalogSource: "LANDMARK_INIT",
    catalogScheme: "HR",
    catalogCount: 0,
    catalogById: new Map(), // id -> { vx, vy, vz, mag, name }
    catalogFetchPending: false,
    catalogLoadedReal: false,

    // Attitude & Orbit state
    solveState: "idle", // 'idle' | 'solved' | 'lost'
    lastPayload: null,
    camRight: null,
    camUp: null,
    camBore: null,
    fovHDeg: 25.18,
    fovVDeg: 16.92,
    matchedStars: [], // [{ id, label, sub, wx, wy, wz, mag }]
    landmarkItems: [], // [{ hr, name, wx, wy, wz, mag, isPole }]
    labelPool: [],

    // Orbital mechanics
    orbitU: null,
    orbitV: null,
    orbitN: null,
    orbitAngle: 0.55,
    orbitSpeed: 0.24,
    earthSpin: 0.4,
    cloudSpin: 0.0,
    isPlaying: true,
    showLabels: true,
    showGrid: true,

    // Camera modes & smooth transition
    viewMode: "orbit", // 'orbit' | 'pov'
    povZoomMode: "wide", // 'wide' (Rộng quanh khung) | 'tight' (1:1 Khung ảnh)
    povBlend: 0.0, // 0 = orbit, 1 = pov
    transFromBlend: 0.0,
    transToBlend: 0.0,
    transElapsed: 1.0,
    transDuration: 0.75,

    // Damped spherical orbit controller
    sphRadius: 4.85,
    sphPhi: 1.18,
    sphTheta: 0.65,
    targetRadius: 4.85,
    targetPhi: 1.18,
    targetTheta: 0.65,
    orbitLookAt: null,
    targetLookAt: null,

    // Subtle POV pan/zoom inspection offsets
    povYawOff: 0,
    povPitchOff: 0,
    povZoomMul: 1,
    targetPovYaw: 0,
    targetPovPitch: 0,
    targetPovZoom: 1,

    // Pointer / Pinch state
    activePointers: new Map(),
    lastPinchDist: 0,
    userHasInteracted: false
  };

  function buildDomHud(container) {
    container.innerHTML = "";
    container.classList.add("orbit3d-root");

    const stageEl = document.createElement("div");
    stageEl.className = "o3d-stage";
    container.appendChild(stageEl);

    const labelLayerEl = document.createElement("div");
    labelLayerEl.className = "o3d-labels";
    container.appendChild(labelLayerEl);

    const hudLayer = document.createElement("div");
    hudLayer.className = "o3d-hud-layer";

    // Top HUD row
    const hudTop = document.createElement("div");
    hudTop.className = "o3d-hud-top";

    const pill = document.createElement("div");
    pill.className = "o3d-telemetry-pill";
    const dot = document.createElement("span");
    dot.className = "o3d-status-dot is-idle";
    const tText = document.createElement("span");
    tText.className = "o3d-telemetry-text";
    tText.textContent = "Chế độ tìm kiếm sao — chưa khóa hướng";
    const tMeta = document.createElement("span");
    tMeta.className = "o3d-telemetry-meta";
    tMeta.textContent = "Bầu trời thực J2000";
    pill.append(dot, tText, tMeta);

    const topRight = document.createElement("div");
    topRight.className = "o3d-top-right";

    const hintPill = document.createElement("div");
    hintPill.className = "o3d-hint-pill";
    hintPill.textContent = "Kéo để xoay · Cuộn thu phóng";

    const povZoomWrap = document.createElement("div");
    povZoomWrap.className = "o3d-pov-zoom";
    povZoomWrap.hidden = true;

    const btnZoomWide = document.createElement("button");
    btnZoomWide.type = "button";
    btnZoomWide.className = "o3d-mini-btn is-active";
    btnZoomWide.textContent = "Rộng quanh khung";
    btnZoomWide.addEventListener("click", () => {
      state.povZoomMode = "wide";
      state.targetPovYaw = 0;
      state.targetPovPitch = 0;
      state.targetPovZoom = 1;
      syncHudButtons();
    });

    const btnZoomTight = document.createElement("button");
    btnZoomTight.type = "button";
    btnZoomTight.className = "o3d-mini-btn";
    btnZoomTight.textContent = "1:1 Khung ảnh";
    btnZoomTight.addEventListener("click", () => {
      state.povZoomMode = "tight";
      state.targetPovYaw = 0;
      state.targetPovPitch = 0;
      state.targetPovZoom = 1;
      syncHudButtons();
    });

    povZoomWrap.append(btnZoomWide, btnZoomTight);
    topRight.append(hintPill, povZoomWrap);
    hudTop.append(pill, topRight);

    // Bottom Floating Controls
    const controls = document.createElement("div");
    controls.className = "o3d-controls";
    controls.setAttribute("role", "toolbar");
    controls.setAttribute("aria-label", "Điều khiển không gian 3D");

    const seg = document.createElement("div");
    seg.className = "o3d-seg";

    function makeBtn(svgHtml, text, extraCls, titleText) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "o3d-btn" + (extraCls ? " " + extraCls : "");
      if (titleText) b.title = titleText;
      const ic = document.createElement("span");
      ic.style.display = "inline-flex";
      ic.innerHTML = svgHtml;
      const tx = document.createElement("span");
      tx.className = "o3d-btn-txt";
      tx.textContent = text;
      b.append(ic, tx);
      return { btn: b, iconWrap: ic, txtWrap: tx };
    }

    const mOrbit = makeBtn(ICONS.orbit, "Quỹ đạo 3D", "is-active", "Góc nhìn vệ tinh trên quỹ đạo Trái Đất");
    mOrbit.btn.addEventListener("click", () => setViewMode("orbit"));

    const mPov = makeBtn(ICONS.pov, "Góc nhìn Vệ tinh", "", "Đối chiếu 1:1 từ cảm biến sao trên vệ tinh");
    mPov.btn.addEventListener("click", () => setViewMode("pov"));

    seg.append(mOrbit.btn, mPov.btn);

    const sep = document.createElement("span");
    sep.className = "o3d-sep";

    const bPlay = makeBtn(ICONS.pause, "Tạm dừng", "is-compact-icon", "Tạm dừng / Tiếp tục chuyển động quỹ đạo");
    bPlay.btn.addEventListener("click", () => togglePlay());

    const bLabels = makeBtn(ICONS.labels, "Tên sao", "is-toggle-on is-compact-icon", "Bật / tắt nhãn tên sao IAU");
    bLabels.btn.addEventListener("click", () => {
      state.showLabels = !state.showLabels;
      if (!state.showLabels && state.labelLayerEl) {
        for (let i = 0; i < state.labelPool.length; i++) {
          state.labelPool[i].style.display = "none";
        }
      }
      syncHudButtons();
    });

    const bGrid = makeBtn(ICONS.grid, "Lưới J2000", "is-toggle-on is-compact-icon", "Bật / tắt lưới tọa độ xích đạo J2000");
    bGrid.btn.addEventListener("click", () => toggleGrid());

    const bReset = makeBtn(ICONS.reset, "Đặt lại góc", "is-compact-icon", "Đặt lại góc nhìn chuẩn");
    bReset.btn.addEventListener("click", () => resetView());

    controls.append(seg, sep, bPlay.btn, bLabels.btn, bGrid.btn, bReset.btn);
    hudLayer.append(hudTop, controls);
    container.appendChild(hudLayer);

    state.stageEl = stageEl;
    state.labelLayerEl = labelLayerEl;
    state.dotEl = dot;
    state.telemetryTextEl = tText;
    state.telemetryMetaEl = tMeta;
    state.hintPillEl = hintPill;
    state.povZoomWrapEl = povZoomWrap;
    state.btnZoomWide = btnZoomWide;
    state.btnZoomTight = btnZoomTight;
    state.btnModeOrbit = mOrbit.btn;
    state.btnModePov = mPov.btn;
    state.btnPlay = bPlay.btn;
    state.btnPlayTxt = bPlay.txtWrap;
    state.btnPlayIcon = bPlay.iconWrap;
    state.btnLabels = bLabels.btn;
    state.btnGrid = bGrid.btn;
  }

  function renderWebglFallback(reason) {
    if (!state.stageEl) return;
    state.stageEl.innerHTML = "";
    const fb = document.createElement("div");
    fb.className = "o3d-fallback";
    fb.innerHTML = ICONS.orbit;
    const title = document.createElement("div");
    title.className = "o3d-fallback-title";
    title.textContent = "Mô phỏng bầu trời J2000 3D";
    const desc = document.createElement("div");
    desc.className = "o3d-fallback-desc";
    desc.textContent = reason || "Trình duyệt hiện tại chưa bật tăng tốc đồ họa WebGL để hiển thị cảnh 3D.";
    fb.append(title, desc);
    state.stageEl.appendChild(fb);
    state.fallbackDescEl = desc;
  }

  function syncHudButtons() {
    if (!state.btnModeOrbit) return;
    const isPov = state.viewMode === "pov";
    state.btnModeOrbit.classList.toggle("is-active", !isPov);
    state.btnModePov.classList.toggle("is-active", isPov);
    if (state.stageEl) {
      state.stageEl.classList.toggle("is-pov", isPov);
    }
    if (state.povZoomWrapEl) state.povZoomWrapEl.hidden = !isPov;
    if (state.hintPillEl) state.hintPillEl.hidden = isPov;
    if (state.btnZoomWide && state.btnZoomTight) {
      state.btnZoomWide.classList.toggle("is-active", state.povZoomMode === "wide");
      state.btnZoomTight.classList.toggle("is-active", state.povZoomMode === "tight");
    }
    if (state.btnPlayTxt && state.btnPlayIcon) {
      state.btnPlayTxt.textContent = state.isPlaying ? "Tạm dừng" : "Tiếp tục";
      state.btnPlayIcon.innerHTML = state.isPlaying ? ICONS.pause : ICONS.play;
      state.btnPlay.classList.toggle("is-toggle-on", !state.isPlaying);
    }
    if (state.btnLabels) {
      state.btnLabels.classList.toggle("is-toggle-on", state.showLabels);
    }
    if (state.btnGrid) {
      state.btnGrid.classList.toggle("is-toggle-on", state.showGrid);
    }
  }

  function buildCelestialGrid(THREE) {
    const group = new THREE.Group();

    // RA meridians (every 30 deg = 2h) and Dec parallels (-60, -30, +30, +60)
    const gridPos = [];
    const eqPos = [];

    for (let raDeg = 0; raDeg < 360; raDeg += 30) {
      const segs = 96;
      for (let i = 0; i < segs; i++) {
        const dec0 = -86 + (172 * i) / segs;
        const dec1 = -86 + (172 * (i + 1)) / segs;
        const p0 = icrsToWorldXYZ(...raDecToIcrs(raDeg, dec0));
        const p1 = icrsToWorldXYZ(...raDecToIcrs(raDeg, dec1));
        gridPos.push(p0[0] * R_GRID, p0[1] * R_GRID, p0[2] * R_GRID);
        gridPos.push(p1[0] * R_GRID, p1[1] * R_GRID, p1[2] * R_GRID);
      }
    }

    for (const decDeg of [-60, -30, 0, 30, 60]) {
      const segs = 128;
      const target = decDeg === 0 ? eqPos : gridPos;
      for (let i = 0; i < segs; i++) {
        const ra0 = (360 * i) / segs;
        const ra1 = (360 * (i + 1)) / segs;
        const p0 = icrsToWorldXYZ(...raDecToIcrs(ra0, decDeg));
        const p1 = icrsToWorldXYZ(...raDecToIcrs(ra1, decDeg));
        target.push(p0[0] * R_GRID, p0[1] * R_GRID, p0[2] * R_GRID);
        target.push(p1[0] * R_GRID, p1[1] * R_GRID, p1[2] * R_GRID);
      }
    }

    const gGeom = new THREE.BufferGeometry();
    gGeom.setAttribute("position", new THREE.Float32BufferAttribute(gridPos, 3));
    const gMat = new THREE.LineBasicMaterial({
      color: 0x94a3b8,
      transparent: true,
      opacity: 0.068,
      depthWrite: false
    });
    group.add(new THREE.LineSegments(gGeom, gMat));

    const eqGeom = new THREE.BufferGeometry();
    eqGeom.setAttribute("position", new THREE.Float32BufferAttribute(eqPos, 3));
    const eqMat = new THREE.LineBasicMaterial({
      color: 0x7dd3fc,
      transparent: true,
      opacity: 0.135,
      depthWrite: false
    });
    group.add(new THREE.LineSegments(eqGeom, eqMat));

    // Subtle North Celestial Pole (+Y in World) crosshair marker
    const poleSpan = 6.5;
    const poleGeom = new THREE.BufferGeometry();
    poleGeom.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(
        [
          -poleSpan, R_GRID, 0, poleSpan, R_GRID, 0,
          0, R_GRID, -poleSpan, 0, R_GRID, poleSpan
        ],
        3
      )
    );
    const poleMat = new THREE.LineBasicMaterial({
      color: 0x7dd3fc,
      transparent: true,
      opacity: 0.28,
      depthWrite: false
    });
    group.add(new THREE.LineSegments(poleGeom, poleMat));

    return group;
  }

  function buildCosmicDust(THREE) {
    // Subtle deep-space background dust concentrated near real J2000 Galactic Plane
    // North Galactic Pole: RA = 192.8595 deg, Dec = +27.1283 deg
    const ngpIcrs = raDecToIcrs(192.8595, 27.1283);
    const ngp = new THREE.Vector3(...icrsToWorldXYZ(ngpIcrs[0], ngpIcrs[1], ngpIcrs[2])).normalize();
    const gBasisU = new THREE.Vector3(1, 0, 0).cross(ngp).normalize();
    const gBasisV = new THREE.Vector3().crossVectors(ngp, gBasisU).normalize();

    const rng = makePrng(4205023);
    const count = 2200;
    const pos = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    const alphas = new Float32Array(count);

    const tmp = new THREE.Vector3();
    for (let i = 0; i < count; i++) {
      const isBand = i < 1250;
      let sinLat;
      if (isBand) {
        // Gaussian-like concentration along Milky Way plane
        const g1 = (rng() + rng() + rng()) / 3 - 0.5;
        sinLat = clamp(g1 * 0.72, -0.98, 0.98);
      } else {
        sinLat = rng() * 2 - 1;
      }
      const cosLat = Math.sqrt(Math.max(0, 1 - sinLat * sinLat));
      const lon = rng() * Math.PI * 2;
      tmp
        .set(0, 0, 0)
        .addScaledVector(gBasisU, cosLat * Math.cos(lon))
        .addScaledVector(gBasisV, cosLat * Math.sin(lon))
        .addScaledVector(ngp, sinLat)
        .normalize();

      pos[i * 3] = tmp.x * R_DUST;
      pos[i * 3 + 1] = tmp.y * R_DUST;
      pos[i * 3 + 2] = tmp.z * R_DUST;
      sizes[i] = 0.95 + rng() * 0.95;
      alphas[i] = 0.08 + rng() * 0.10;
    }

    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geom.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    geom.setAttribute("aAlpha", new THREE.BufferAttribute(alphas, 1));

    const mat = new THREE.ShaderMaterial({
      uniforms: {
        uPixelRatio: { value: 1.0 }
      },
      vertexShader: `
        attribute float aSize;
        attribute float aAlpha;
        uniform float uPixelRatio;
        varying float vAlpha;
        void main() {
          vAlpha = aAlpha;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = aSize * uPixelRatio;
        }
      `,
      fragmentShader: `
        varying float vAlpha;
        void main() {
          vec2 c = gl_PointCoord - vec2(0.5);
          float r2 = dot(c, c) * 4.0;
          if (r2 > 1.0) discard;
          float falloff = exp(-r2 * 3.5);
          gl_FragColor = vec4(vec3(0.76, 0.83, 0.94), vAlpha * falloff);
        }
      `,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });

    return new THREE.Points(geom, mat);
  }

  function createStarMaterial(THREE) {
    return new THREE.ShaderMaterial({
      uniforms: {
        uPixelRatio: { value: 1.0 },
        uZoomBoost: { value: 1.0 }
      },
      vertexShader: `
        attribute float aSize;
        attribute float aAlpha;
        attribute vec3 aColor;
        uniform float uPixelRatio;
        uniform float uZoomBoost;
        varying float vAlpha;
        varying vec3 vColor;
        void main() {
          vAlpha = aAlpha;
          vColor = aColor;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = clamp(aSize * uZoomBoost * uPixelRatio, 1.2, 42.0);
        }
      `,
      fragmentShader: `
        varying float vAlpha;
        varying vec3 vColor;
        void main() {
          vec2 uv = gl_PointCoord - vec2(0.5);
          float r = length(uv) * 2.0;
          if (r > 1.0) discard;
          float core = exp(-r * r * 9.0);
          float halo = 0.36 * exp(-r * 3.1) * (1.0 - r);
          float intensity = clamp(core + halo, 0.0, 1.0);
          vec3 col = mix(vColor, vec3(1.0), core * 0.55);
          gl_FragColor = vec4(col, intensity * vAlpha);
        }
      `,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
  }

  function starTintFor(id, mag, scheme) {
    if (scheme === "HR") {
      if (WARM_HRS.has(id)) return [1.0, 0.87, 0.74];
      if (COOL_HRS.has(id)) return [0.84, 0.92, 1.0];
    }
    const h = ((id * 2654435761) >>> 0) % 100;
    if (h < 18) return [1.0, 0.92, 0.84];       // Subtle warm F/G/K
    if (h < 52) return [0.88, 0.94, 1.0];       // Subtle cool B/A
    if (mag < 2.2) return [0.95, 0.97, 1.0];    // Crisp luminous white
    return [0.93, 0.95, 0.99];
  }

  function populateCatalogStars(data) {
    const THREE = window.THREE;
    if (!THREE || !state.skyGroup) return;

    const ids = data.ids || [];
    const vx = data.vx || [];
    const vy = data.vy || [];
    const vz = data.vz || [];
    const mags = data.mag || [];
    const names = data.names || {};
    const n = Math.min(ids.length, vx.length, vy.length, vz.length, mags.length);
    if (n === 0) return;

    const srcUpper = String(data.source || "BSC5").toUpperCase();
    const scheme = srcUpper.includes("HIP") ? "HIP" : "HR";
    state.catalogSource = data.source || "BSC5";
    state.catalogScheme = scheme;
    state.catalogCount = n;
    state.catalogById.clear();

    const pos = new Float32Array(n * 3);
    const sizes = new Float32Array(n);
    const alphas = new Float32Array(n);
    const colors = new Float32Array(n * 3);

    for (let i = 0; i < n; i++) {
      const id = Number(ids[i]);
      const x = Number(vx[i]);
      const y = Number(vy[i]);
      const z = Number(vz[i]);
      const m = Number(mags[i]);
      const iau = names[String(id)] || null;

      state.catalogById.set(id, { vx: x, vy: y, vz: z, mag: m, name: iau });

      const [wx, wy, wz] = icrsToWorldXYZ(x, y, z);
      pos[i * 3] = wx * R_SKY;
      pos[i * 3 + 1] = wy * R_SKY;
      pos[i * 3 + 2] = wz * R_SKY;

      // Astronomical magnitude -> point size & alpha
      let sz;
      if (m <= 0.5) sz = 11.5 - m * 1.6;
      else if (m <= 2.2) sz = 9.2 - (m - 0.5) * 1.9;
      else if (m <= 4.2) sz = 5.9 - (m - 2.2) * 1.35;
      else sz = Math.max(1.55, 3.2 - (m - 4.2) * 0.72);
      sizes[i] = sz;

      alphas[i] = clamp(Math.pow(10, -0.155 * (m - 0.8)), 0.24, 1.0);

      const [cr, cg, cb] = starTintFor(id, m, scheme);
      colors[i * 3] = cr;
      colors[i * 3 + 1] = cg;
      colors[i * 3 + 2] = cb;
    }

    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geom.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    geom.setAttribute("aAlpha", new THREE.BufferAttribute(alphas, 1));
    geom.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));

    if (state.starPoints) {
      state.skyGroup.remove(state.starPoints);
      state.starPoints.geometry.dispose();
    }
    state.starPoints = new THREE.Points(geom, state.starMaterial);
    state.starPoints.frustumCulled = false;
    state.skyGroup.add(state.starPoints);

    // Refresh matched stars & HUD meta if a payload was already rendered
    if (state.lastPayload) {
      rebuildMatchedStars(state.lastPayload);
    }
    updateHudTelemetry();
  }

  function seedInitialLandmarks() {
    const ids = [];
    const vx = [];
    const vy = [];
    const vz = [];
    const mag = [];
    const names = {};
    state.landmarkItems = [];

    for (let i = 0; i < LANDMARK_STARS.length; i++) {
      const [hr, name, raDeg, decDeg, m] = LANDMARK_STARS[i];
      const [ix, iy, iz] = raDecToIcrs(raDeg, decDeg);
      const [wx, wy, wz] = icrsToWorldXYZ(ix, iy, iz);
      ids.push(hr);
      vx.push(ix);
      vy.push(iy);
      vz.push(iz);
      mag.push(m);
      names[String(hr)] = name;

      if (i < 18 || hr === 424) {
        state.landmarkItems.push({
          hr,
          name: hr === 424 ? "Polaris (Bắc Cực)" : name,
          wx,
          wy,
          wz,
          mag: m,
          isPole: hr === 424
        });
      }
    }

    populateCatalogStars({ source: "BSC5", ids, vx, vy, vz, mag, names });
  }

  function fetchSkyCatalog(kind) {
    if (typeof fetch !== "function" || state.catalogFetchPending) return;
    const catParam = kind && String(kind).toLowerCase().includes("hip") ? "hipparcos" : "bsc5";
    state.catalogFetchPending = true;
    fetch(`/api/sky-catalog?catalog=${encodeURIComponent(catParam)}&max_mag=6.0`, {
      headers: { Accept: "application/json" }
    })
      .then((res) => (res && res.ok ? res.json() : null))
      .then((data) => {
        state.catalogFetchPending = false;
        if (data && Array.isArray(data.ids) && data.ids.length > 100) {
          state.catalogLoadedReal = true;
          populateCatalogStars(data);
        }
      })
      .catch(() => {
        state.catalogFetchPending = false;
      });
  }

  function buildEarthAndAtmosphere(THREE) {
    const group = new THREE.Group();
    const { dayTex, auxTex } = buildEarthTextures(THREE);
    const sunDir = new THREE.Vector3(0.76, 0.28, 0.58).normalize();
    state.sunDirWorld = sunDir;

    const earthMat = new THREE.ShaderMaterial({
      uniforms: {
        uDayMap: { value: dayTex },
        uAuxMap: { value: auxTex },
        uHasMaps: { value: dayTex ? 1.0 : 0.0 },
        uSunDir: { value: sunDir.clone() },
        uCloudShift: { value: 0.0 }
      },
      vertexShader: `
        varying vec2 vUv;
        varying vec3 vNormalWorld;
        varying vec3 vPosWorld;
        void main() {
          vUv = uv;
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vPosWorld = wp.xyz;
          vNormalWorld = normalize(mat3(modelMatrix) * normal);
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: `
        uniform sampler2D uDayMap;
        uniform sampler2D uAuxMap;
        uniform float uHasMaps;
        uniform vec3 uSunDir;
        uniform float uCloudShift;
        varying vec2 vUv;
        varying vec3 vNormalWorld;
        varying vec3 vPosWorld;

        void main() {
          vec3 N = normalize(vNormalWorld);
          vec3 V = normalize(cameraPosition - vPosWorld);
          vec3 L = normalize(uSunDir);

          vec4 daySample = uHasMaps > 0.5 ? texture2D(uDayMap, vUv) : vec4(0.05, 0.13, 0.26, 0.9);
          vec4 auxSample = uHasMaps > 0.5 ? texture2D(uAuxMap, vec2(vUv.x + uCloudShift, vUv.y)) : vec4(0.0);
          float cityMask = uHasMaps > 0.5 ? texture2D(uAuxMap, vUv).g : 0.0;

          vec3 baseAlbedo = daySample.rgb;
          float waterSpec = daySample.a;
          float cloudAmt = auxSample.r;

          float ndl = dot(N, L);
          float dayFactor = smoothstep(-0.14, 0.22, ndl);
          float diff = max(ndl, 0.0);

          // Subtle twilight scattering along terminator
          float twilight = smoothstep(-0.20, 0.02, ndl) * (1.0 - smoothstep(0.0, 0.26, ndl));
          vec3 twilightCol = vec3(0.36, 0.19, 0.11) * twilight * 0.34;

          // Solar glint over oceans
          vec3 H = normalize(L + V);
          float spec = pow(max(dot(N, H), 0.0), 46.0) * waterSpec * smoothstep(-0.02, 0.25, ndl) * 0.42;

          // Surface + cloud layer composition
          vec3 surfaceDay = baseAlbedo * (0.12 + 0.96 * diff) + vec3(0.68, 0.82, 0.98) * spec;
          vec3 cloudDay = vec3(0.88, 0.92, 0.97) * (0.14 + 0.92 * diff);
          vec3 litColor = mix(surfaceDay, cloudDay, cloudAmt * 0.68);

          // Night side ambient cosmos + delicate inhabited city lights (occluded by thick clouds)
          vec3 nightBase = baseAlbedo * 0.032 + vec3(0.008, 0.015, 0.030);
          float nightMask = smoothstep(0.05, -0.22, ndl);
          vec3 cityCol = vec3(1.0, 0.76, 0.42) * cityMask * nightMask * (1.0 - cloudAmt * 0.72) * 0.62;
          vec3 nightColor = mix(nightBase + cityCol, vec3(0.014, 0.022, 0.038), cloudAmt * 0.45);

          vec3 col = mix(nightColor, litColor, dayFactor) + twilightCol;

          // Rayleigh atmospheric limb haze
          float fresnel = pow(1.0 - max(dot(N, V), 0.0), 3.4);
          float sunLimb = smoothstep(-0.35, 0.45, ndl);
          col += vec3(0.26, 0.58, 0.95) * fresnel * (0.14 + 0.46 * sunLimb);

          gl_FragColor = vec4(col, 1.0);
        }
      `
    });

    const earthMesh = new THREE.Mesh(new THREE.SphereGeometry(R_EARTH, 88, 64), earthMat);
    group.add(earthMesh);

    // Outer Rayleigh atmosphere halo shell
    const atmosMat = new THREE.ShaderMaterial({
      uniforms: {
        uSunDir: { value: sunDir.clone() }
      },
      vertexShader: `
        varying vec3 vNormalWorld;
        varying vec3 vPosWorld;
        void main() {
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vPosWorld = wp.xyz;
          vNormalWorld = normalize(mat3(modelMatrix) * normal);
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: `
        uniform vec3 uSunDir;
        varying vec3 vNormalWorld;
        varying vec3 vPosWorld;
        void main() {
          vec3 N = normalize(vNormalWorld);
          vec3 V = normalize(cameraPosition - vPosWorld);
          // BackSide: N points outward, dot(N, V) is negative near center and 0 at limb
          float viewDot = clamp(-dot(N, V), 0.0, 1.0);
          float rim = pow(1.0 - viewDot, 3.2) * smoothstep(0.0, 0.35, viewDot + 0.12);
          float sunFacing = smoothstep(-0.42, 0.55, dot(N, normalize(uSunDir)));
          vec3 col = mix(vec3(0.10, 0.25, 0.48), vec3(0.32, 0.68, 0.98), sunFacing);
          float alpha = rim * (0.16 + 0.56 * sunFacing);
          gl_FragColor = vec4(col, alpha);
        }
      `,
      side: THREE.BackSide,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });

    const atmosMesh = new THREE.Mesh(new THREE.SphereGeometry(R_ATMOS, 64, 48), atmosMat);
    group.add(atmosMesh);

    state.earthMesh = earthMesh;
    state.earthMaterial = earthMat;
    state.atmosMesh = atmosMesh;
    state.atmosMaterial = atmosMat;
    return group;
  }

  function buildSpacecraftAndFrustum(THREE) {
    const satGroup = new THREE.Group();
    const attGroup = new THREE.Group();
    satGroup.add(attGroup);

    const panelTex = buildSolarPanelTexture(THREE);
    const meshes = [];

    function trackMesh(m) {
      m.material.transparent = true;
      meshes.push(m);
      return m;
    }

    const titaniumMat = new THREE.MeshStandardMaterial({
      color: 0x334155,
      metalness: 0.72,
      roughness: 0.34
    });
    const darkAnodizedMat = new THREE.MeshStandardMaterial({
      color: 0x161f2e,
      metalness: 0.62,
      roughness: 0.42
    });
    const goldFoilMat = new THREE.MeshStandardMaterial({
      color: 0xc4923e,
      metalness: 0.82,
      roughness: 0.28
    });
    const baffleInnerMat = new THREE.MeshBasicMaterial({
      color: 0x05080f
    });
    const lensMat = new THREE.MeshStandardMaterial({
      color: 0x38bdf8,
      emissive: 0x0c4a6e,
      emissiveIntensity: 0.65,
      metalness: 0.9,
      roughness: 0.12
    });
    const solarMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      map: panelTex,
      metalness: 0.45,
      roughness: 0.26
    });

    // Octagonal spacecraft bus (aligned so Star Tracker looks out along local -Z = +camBore)
    const bus = trackMesh(new THREE.Mesh(new THREE.CylinderGeometry(0.072, 0.072, 0.135, 8), titaniumMat));
    bus.rotation.x = Math.PI * 0.5;
    attGroup.add(bus);

    // Warm-gold MLI thermal blanket core wrap
    const foilCore = trackMesh(new THREE.Mesh(new THREE.BoxGeometry(0.098, 0.098, 0.118), goldFoilMat));
    attGroup.add(foilCore);

    // Aft adapter ring & thruster nozzle (+Z side)
    const aftRing = trackMesh(new THREE.Mesh(new THREE.CylinderGeometry(0.048, 0.058, 0.026, 16), darkAnodizedMat));
    aftRing.rotation.x = Math.PI * 0.5;
    aftRing.position.z = 0.08;
    attGroup.add(aftRing);

    // Precision Star Tracker optical head & stray-light baffle pointing along local -Z (+camBore)
    const baffleOuter = trackMesh(
      new THREE.Mesh(new THREE.CylinderGeometry(0.040, 0.028, 0.086, 24, 1, true), darkAnodizedMat)
    );
    baffleOuter.material.side = THREE.DoubleSide;
    baffleOuter.rotation.x = -Math.PI * 0.5;
    baffleOuter.position.set(0, 0, -0.108);
    attGroup.add(baffleOuter);

    const baffleRim = trackMesh(new THREE.Mesh(new THREE.TorusGeometry(0.040, 0.0032, 10, 28), titaniumMat));
    baffleRim.position.set(0, 0, -0.151);
    attGroup.add(baffleRim);

    const baffleCavity = trackMesh(new THREE.Mesh(new THREE.CircleGeometry(0.037, 24), baffleInnerMat));
    baffleCavity.rotation.y = Math.PI;
    baffleCavity.position.set(0, 0, -0.148);
    attGroup.add(baffleCavity);

    const opticsLens = trackMesh(new THREE.Mesh(new THREE.SphereGeometry(0.019, 18, 12), lensMat));
    opticsLens.scale.set(1, 1, 0.35);
    opticsLens.position.set(0, 0, -0.082);
    attGroup.add(opticsLens);

    // Sensor +Y_up tick mark on top of baffle rim (visualizes roll lock!)
    const upTick = trackMesh(new THREE.Mesh(new THREE.BoxGeometry(0.006, 0.018, 0.012), goldFoilMat));
    upTick.position.set(0, 0.044, -0.144);
    attGroup.add(upTick);

    // Dual deployable solar wings along +-X (perpendicular to optical axis)
    for (const sign of [-1, 1]) {
      const boom = trackMesh(new THREE.Mesh(new THREE.CylinderGeometry(0.0045, 0.0045, 0.065, 8), titaniumMat));
      boom.rotation.z = Math.PI * 0.5;
      boom.position.set(sign * 0.095, 0, 0);
      attGroup.add(boom);

      const wingFrame = trackMesh(new THREE.Mesh(new THREE.BoxGeometry(0.30, 0.104, 0.005), darkAnodizedMat));
      wingFrame.position.set(sign * 0.265, 0, 0);
      attGroup.add(wingFrame);

      const wingCells = trackMesh(new THREE.Mesh(new THREE.PlaneGeometry(0.288, 0.094), solarMat));
      wingCells.position.set(sign * 0.265, 0, -0.0032);
      wingCells.rotation.y = Math.PI;
      attGroup.add(wingCells);

      const wingCellsBack = trackMesh(new THREE.Mesh(new THREE.PlaneGeometry(0.288, 0.094), solarMat));
      wingCellsBack.position.set(sign * 0.265, 0, 0.0032);
      attGroup.add(wingCellsBack);
    }

    // 3D FOV Frustum Pyramid (emanating from Star Tracker aperture along -Z)
    const frustumGroup = new THREE.Group();
    frustumGroup.position.set(0, 0, -0.15);
    attGroup.add(frustumGroup);

    const coneMat = new THREE.ShaderMaterial({
      uniforms: {
        uColor: { value: new THREE.Color(0x7dd3fc) },
        uOpacity: { value: 0.14 }
      },
      vertexShader: `
        attribute float aFade;
        varying float vFade;
        void main() {
          vFade = aFade;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform float uOpacity;
        varying float vFade;
        void main() {
          gl_FragColor = vec4(uColor, uOpacity * vFade * vFade);
        }
      `,
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending
    });

    const edgeMat = new THREE.ShaderMaterial({
      uniforms: {
        uColor: { value: new THREE.Color(0x7dd3fc) },
        uOpacity: { value: 0.52 }
      },
      vertexShader: `
        attribute float aFade;
        varying float vFade;
        void main() {
          vFade = aFade;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform float uOpacity;
        varying float vFade;
        void main() {
          gl_FragColor = vec4(uColor, uOpacity * vFade);
        }
      `,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });

    state.satelliteGroup = satGroup;
    state.attitudeGroup = attGroup;
    state.spacecraftMeshes = meshes;
    state.frustumGroup = frustumGroup;
    state.frustumConeMat = coneMat;
    state.frustumEdgeMat = edgeMat;
    return satGroup;
  }

  function rebuildFrustumGeometry() {
    const THREE = window.THREE;
    if (!THREE || !state.frustumGroup) return;

    while (state.frustumGroup.children.length > 0) {
      const ch = state.frustumGroup.children.pop();
      if (ch.geometry) ch.geometry.dispose();
    }

    const L = 2.65;
    const tanH = Math.tan(clamp(state.fovHDeg, 2, 130) * 0.5 * DEG2RAD);
    const tanV = Math.tan(clamp(state.fovVDeg, 2, 130) * 0.5 * DEG2RAD);
    const hw0 = 0.036;
    const hh0 = 0.036 * clamp(tanV / Math.max(tanH, 1e-4), 0.45, 1.8);
    const hw1 = hw0 + L * tanH;
    const hh1 = hh0 + L * tanV;

    // 4 near corners at aperture (z = 0), 4 far corners at z = -L
    const n0 = [-hw0, hh0, 0];
    const n1 = [hw0, hh0, 0];
    const n2 = [hw0, -hh0, 0];
    const n3 = [-hw0, -hh0, 0];
    const f0 = [-hw1, hh1, -L];
    const f1 = [hw1, hh1, -L];
    const f2 = [hw1, -hh1, -L];
    const f3 = [-hw1, -hh1, -L];

    const quads = [
      [n0, n1, f1, f0],
      [n1, n2, f2, f1],
      [n2, n3, f3, f2],
      [n3, n0, f0, f3]
    ];
    const triPos = [];
    const triFade = [];
    for (const [a, b, c, d] of quads) {
      triPos.push(...a, ...b, ...c, ...a, ...c, ...d);
      triFade.push(1, 1, 0, 1, 0, 0);
    }

    const coneGeom = new THREE.BufferGeometry();
    coneGeom.setAttribute("position", new THREE.Float32BufferAttribute(triPos, 3));
    coneGeom.setAttribute("aFade", new THREE.Float32BufferAttribute(triFade, 1));
    state.frustumGroup.add(new THREE.Mesh(coneGeom, state.frustumConeMat));

    // 4 corner rays + subtle central boresight optical axis
    const linePos = [
      ...n0, ...f0,
      ...n1, ...f1,
      ...n2, ...f2,
      ...n3, ...f3,
      0, 0, 0, 0, 0, -L * 1.12
    ];
    const lineFade = [1, 0.06, 1, 0.06, 1, 0.06, 1, 0.06, 0.65, 0.0];
    const edgeGeom = new THREE.BufferGeometry();
    edgeGeom.setAttribute("position", new THREE.Float32BufferAttribute(linePos, 3));
    edgeGeom.setAttribute("aFade", new THREE.Float32BufferAttribute(lineFade, 1));
    state.frustumGroup.add(new THREE.LineSegments(edgeGeom, state.frustumEdgeMat));
  }

  function rebuildSkyFovFootprint() {
    const THREE = window.THREE;
    if (!THREE || !state.skyFovGroup) return;

    while (state.skyFovGroup.children.length > 0) {
      const ch = state.skyFovGroup.children.pop();
      if (ch.geometry) ch.geometry.dispose();
      if (ch.material) ch.material.dispose();
    }

    if (state.solveState !== "solved" || !state.camBore || !state.camRight || !state.camUp) {
      return;
    }

    const tanH = Math.tan(clamp(state.fovHDeg, 1, 145) * 0.5 * DEG2RAD);
    const tanV = Math.tan(clamp(state.fovVDeg, 1, 145) * 0.5 * DEG2RAD);

    function gnomonicPoint(sx, sy, radius) {
      const vx = state.camBore.x + sx * tanH * state.camRight.x + sy * tanV * state.camUp.x;
      const vy = state.camBore.y + sx * tanH * state.camRight.y + sy * tanV * state.camUp.y;
      const vz = state.camBore.z + sx * tanH * state.camRight.z + sy * tanV * state.camUp.z;
      const inv = radius / Math.hypot(vx, vy, vz);
      return [vx * inv, vy * inv, vz * inv];
    }

    // Subdivided spherical edges (projects to exact straight rectangle in PerspectiveCamera!)
    const segs = 28;
    const borderPts = [];
    const edges = [
      [-1, 1, 1, 1],
      [1, 1, 1, -1],
      [1, -1, -1, -1],
      [-1, -1, -1, 1]
    ];
    for (const [x0, y0, x1, y1] of edges) {
      for (let i = 0; i < segs; i++) {
        const t0 = i / segs;
        const t1 = (i + 1) / segs;
        const p0 = gnomonicPoint(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0, R_FRAME);
        const p1 = gnomonicPoint(x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1, R_FRAME);
        borderPts.push(...p0, ...p1);
      }
    }

    const borderGeom = new THREE.BufferGeometry();
    borderGeom.setAttribute("position", new THREE.Float32BufferAttribute(borderPts, 3));
    const borderMat = new THREE.LineBasicMaterial({
      color: 0x7dd3fc,
      transparent: true,
      opacity: 0.42,
      depthWrite: false
    });
    state.skyFovGroup.add(new THREE.LineSegments(borderGeom, borderMat));

    // Crisp viewfinder corner L-brackets + center boresight reticle + top orientation tick
    const brk = 0.13;
    const accentPts = [];
    const corners = [
      [-1, 1, 1, -1],
      [1, 1, -1, -1],
      [1, -1, -1, 1],
      [-1, -1, 1, 1]
    ];
    for (const [cx, cy, dx, dy] of corners) {
      const c0 = gnomonicPoint(cx, cy, R_FRAME * 0.999);
      const ch = gnomonicPoint(cx + dx * brk, cy, R_FRAME * 0.999);
      const cv = gnomonicPoint(cx, cy + dy * brk, R_FRAME * 0.999);
      accentPts.push(...c0, ...ch, ...c0, ...cv);
    }

    // Center boresight subtle crosshair (with open center gap)
    const chIn = 0.022;
    const chOut = 0.065;
    for (const [ax, ay] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      accentPts.push(
        ...gnomonicPoint(ax * chIn, ay * chIn, R_FRAME * 0.999),
        ...gnomonicPoint(ax * chOut, ay * chOut, R_FRAME * 0.999)
      );
    }
    // Top-edge orientation notch (shows image top v=0)
    accentPts.push(
      ...gnomonicPoint(0, 1.0, R_FRAME * 0.999),
      ...gnomonicPoint(0, 1.045, R_FRAME * 0.999)
    );

    const accentGeom = new THREE.BufferGeometry();
    accentGeom.setAttribute("position", new THREE.Float32BufferAttribute(accentPts, 3));
    const accentMat = new THREE.LineBasicMaterial({
      color: 0x7dd3fc,
      transparent: true,
      opacity: 0.88,
      depthWrite: false
    });
    state.skyFovGroup.add(new THREE.LineSegments(accentGeom, accentMat));
  }

  function createReticleMaterial(THREE) {
    return new THREE.ShaderMaterial({
      uniforms: {
        uPixelRatio: { value: 1.0 }
      },
      vertexShader: `
        uniform float uPixelRatio;
        void main() {
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = 21.0 * uPixelRatio;
        }
      `,
      fragmentShader: `
        void main() {
          vec2 uv = (gl_PointCoord - vec2(0.5)) * 2.0;
          float r = length(uv);
          if (r > 1.0) discard;
          float ring = smoothstep(0.11, 0.02, abs(r - 0.62));
          float axis = min(abs(uv.x), abs(uv.y));
          float ticks = smoothstep(0.085, 0.02, axis) * step(0.68, r) * step(r, 0.96);
          float alpha = clamp(ring * 0.86 + ticks * 0.72, 0.0, 1.0);
          if (alpha < 0.02) discard;
          vec3 col = mix(vec3(0.204, 0.827, 0.600), vec3(0.490, 0.827, 0.988), ticks);
          gl_FragColor = vec4(col, alpha);
        }
      `,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending
    });
  }

  function rebuildMatchedStars(payload) {
    const THREE = window.THREE;
    state.matchedStars = [];

    if (state.reticlePoints && state.skyGroup) {
      state.skyGroup.remove(state.reticlePoints);
      state.reticlePoints.geometry.dispose();
      state.reticlePoints = null;
    }

    if (!payload || state.solveState !== "solved") return;

    const ident = Array.isArray(payload.identified_stars) ? payload.identified_stars : [];
    const seenIds = new Set();
    const list = [];

    for (let i = 0; i < ident.length; i++) {
      const item = ident[i];
      if (!item) continue;
      const id = Number(item.id);
      if (Number.isFinite(id) && seenIds.has(id)) continue;
      if (Number.isFinite(id)) seenIds.add(id);

      const itemScheme = String(item.id_scheme || state.catalogScheme || "HR").toUpperCase();
      const catHit = itemScheme === state.catalogScheme ? state.catalogById.get(id) : null;

      let ix, iy, iz;
      if (catHit) {
        ix = catHit.vx;
        iy = catHit.vy;
        iz = catHit.vz;
      } else if (Number.isFinite(Number(item.ra_deg)) && Number.isFinite(Number(item.dec_deg))) {
        [ix, iy, iz] = raDecToIcrs(Number(item.ra_deg), Number(item.dec_deg));
      } else {
        continue;
      }

      const [wx, wy, wz] = icrsToWorldXYZ(ix, iy, iz);
      const iauName = item.iau_name || (catHit && catHit.name) || null;
      const magVal = Number.isFinite(Number(item.mag)) ? Number(item.mag) : catHit ? catHit.mag : 5.0;
      const tagId = Number.isFinite(id) ? `${itemScheme} ${id}` : "";

      list.push({
        id,
        name: iauName || tagId || "Sao khớp",
        sub: iauName ? tagId : `V ${magVal.toFixed(1)}`,
        hasIau: Boolean(iauName),
        wx,
        wy,
        wz,
        mag: magVal
      });
    }

    // Fallback to matched_catalog_ids if identified_stars was omitted
    if (list.length === 0 && Array.isArray(payload.matched_catalog_ids)) {
      for (const rawId of payload.matched_catalog_ids) {
        const id = Number(rawId);
        const catHit = state.catalogById.get(id);
        if (!catHit) continue;
        const [wx, wy, wz] = icrsToWorldXYZ(catHit.vx, catHit.vy, catHit.vz);
        list.push({
          id,
          name: catHit.name || `${state.catalogScheme} ${id}`,
          sub: catHit.name ? `${state.catalogScheme} ${id}` : `V ${catHit.mag.toFixed(1)}`,
          hasIau: Boolean(catHit.name),
          wx,
          wy,
          wz,
          mag: catHit.mag
        });
      }
    }

    // Sort brightest first so label priority favors bright named stars
    list.sort((a, b) => (a.hasIau !== b.hasIau ? (a.hasIau ? -1 : 1) : a.mag - b.mag));
    state.matchedStars = list;

    if (THREE && state.skyGroup && list.length > 0) {
      const pos = new Float32Array(list.length * 3);
      for (let i = 0; i < list.length; i++) {
        pos[i * 3] = list[i].wx * R_RETICLE;
        pos[i * 3 + 1] = list[i].wy * R_RETICLE;
        pos[i * 3 + 2] = list[i].wz * R_RETICLE;
      }
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      state.reticlePoints = new THREE.Points(geom, state.reticleMaterial);
      state.reticlePoints.frustumCulled = false;
      state.skyGroup.add(state.reticlePoints);
    }
  }

  function rebuildOrbitPlane(boreVec) {
    const THREE = window.THREE;
    if (!THREE) return;

    // Choose inclined LEO orbital plane normal ~22 deg from camBore so the satellite's
    // optical boresight points into open starry sky around the ENTIRE 360 deg orbit (never blocked by Earth!)
    const poleY = new THREE.Vector3(0, 1, 0);
    const bore = boreVec ? boreVec.clone().normalize() : new THREE.Vector3(0.45, 0.36, 0.82).normalize();
    let refAxis = Math.abs(bore.dot(poleY)) < 0.90 ? poleY.clone() : new THREE.Vector3(1, 0, 0);
    if (bore.dot(refAxis) < 0) refAxis.negate();

    const tiltAxis = new THREE.Vector3().crossVectors(bore, refAxis);
    let orbNormal;
    if (tiltAxis.lengthSq() > 1e-6) {
      tiltAxis.normalize();
      orbNormal = bore.clone().applyAxisAngle(tiltAxis, 22 * DEG2RAD).normalize();
    } else {
      orbNormal = bore.clone();
    }

    // Right-handed orbital plane basis (orbitU, orbitV, orbNormal)
    const helper = Math.abs(orbNormal.y) < 0.9 ? poleY : new THREE.Vector3(1, 0, 0);
    const orbitU = new THREE.Vector3().crossVectors(helper, orbNormal).normalize();
    const orbitV = new THREE.Vector3().crossVectors(orbNormal, orbitU).normalize();

    state.orbitN = orbNormal;
    state.orbitU = orbitU;
    state.orbitV = orbitV;

    // Update orbital ring geometry
    if (state.orbitRingLine) {
      const segs = 144;
      const pts = new Float32Array((segs + 1) * 3);
      for (let i = 0; i <= segs; i++) {
        const ang = (i / segs) * Math.PI * 2;
        const c = Math.cos(ang) * R_ORBIT;
        const s = Math.sin(ang) * R_ORBIT;
        pts[i * 3] = orbitU.x * c + orbitV.x * s;
        pts[i * 3 + 1] = orbitU.y * c + orbitV.y * s;
        pts[i * 3 + 2] = orbitU.z * c + orbitV.z * s;
      }
      state.orbitRingLine.geometry.dispose();
      const geom = new THREE.BufferGeometry();
      geom.setAttribute("position", new THREE.BufferAttribute(pts, 3));
      state.orbitRingLine.geometry = geom;
    }

    // Place initial satellite phase on upper sunlit foreground side of orbit
    state.orbitAngle = 0.62;
  }

  function computeOptimalOrbitFraming(snapImmediate) {
    const THREE = window.THREE;
    if (!THREE || !state.camBore) return;

    // Place camera on the -camBore side of Earth, offset ~25 deg sideways so Earth sits on one side,
    // the orbiting satellite + 3D FOV beam sit in midground, and the target J2000 sky FOV sits unobstructed!
    const backDir = state.camBore.clone().negate();
    const basePhi = Math.acos(clamp(backDir.y, -1, 1));
    const baseTheta = Math.atan2(backDir.x, backDir.z);

    state.targetRadius = 4.75;
    state.targetPhi = clamp(basePhi - 0.16, 0.24, Math.PI - 0.24);
    state.targetTheta = baseTheta + 0.44;
    state.targetLookAt.copy(state.camBore).multiplyScalar(0.58);

    // Orient sun so Earth exhibits a crisp ~60% illuminated crescent from this vantage
    if (state.sunDirWorld && state.earthMaterial && state.atmosMaterial) {
      const camApprox = new THREE.Vector3(
        Math.sin(state.targetPhi) * Math.sin(state.targetTheta),
        Math.cos(state.targetPhi),
        Math.sin(state.targetPhi) * Math.cos(state.targetTheta)
      );
      const rightApprox = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), camApprox).normalize();
      state.sunDirWorld
        .copy(camApprox)
        .multiplyScalar(0.45)
        .addScaledVector(rightApprox, 0.78)
        .add(new THREE.Vector3(0, 0.34, 0))
        .normalize();
      state.earthMaterial.uniforms.uSunDir.value.copy(state.sunDirWorld);
      state.atmosMaterial.uniforms.uSunDir.value.copy(state.sunDirWorld);
    }

    if (snapImmediate) {
      state.sphRadius = state.targetRadius;
      state.sphPhi = state.targetPhi;
      state.sphTheta = state.targetTheta;
      state.orbitLookAt.copy(state.targetLookAt);
    }
  }

  function updateHudTelemetry() {
    if (!state.telemetryTextEl || !state.dotEl) return;
    const payload = state.lastPayload;

    state.dotEl.classList.remove("is-solved", "is-lost", "is-idle");
    if (state.solveState === "solved" && payload) {
      state.dotEl.classList.add("is-solved");
      const bore = payload.boresight_est || {};
      let raText = "";
      let decText = "";
      if (Number.isFinite(Number(bore.ra_deg)) && Number.isFinite(Number(bore.dec_deg))) {
        raText = formatRaCompact(bore.ra_deg);
        decText = formatDecCompact(bore.dec_deg);
      } else if (state.camBore) {
        // Recover ICRS from World: vx = wx, vy = -wz, vz = wy
        const vx = state.camBore.x;
        const vy = -state.camBore.z;
        const vz = state.camBore.y;
        const raD = ((Math.atan2(vy, vx) * RAD2DEG) % 360 + 360) % 360;
        const decD = Math.asin(clamp(vz, -1, 1)) * RAD2DEG;
        raText = formatRaCompact(raD);
        decText = formatDecCompact(decD);
      }
      const nMatched =
        (payload.match_stats && Number.isFinite(payload.match_stats.n_valid_pairs)
          ? payload.match_stats.n_valid_pairs
          : null) ??
        (payload.metrics && Number.isFinite(payload.metrics.n_matched) ? payload.metrics.n_matched : null) ??
        state.matchedStars.length;

      state.telemetryTextEl.textContent = `RA ${raText} · Dec ${decText} · Khớp ${nMatched} sao`;
      if (state.telemetryMetaEl) {
        state.telemetryMetaEl.textContent = `FOV ${state.fovHDeg.toFixed(1)}° × ${state.fovVDeg.toFixed(1)}°`;
      }
      if (state.fallbackDescEl) {
        state.fallbackDescEl.textContent = `Đã khóa tư thế J2000: RA ${raText}, Dec ${decText} (${nMatched} sao khớp).`;
      }
    } else if (state.solveState === "lost") {
      state.dotEl.classList.add("is-lost");
      state.telemetryTextEl.textContent = "Chế độ tìm kiếm sao — chưa khóa hướng";
      if (state.telemetryMetaEl) {
        state.telemetryMetaEl.textContent = "Từ chối khóa sai an toàn";
      }
      if (state.fallbackDescEl) {
        state.fallbackDescEl.textContent = "Chưa đủ điều kiện hình học tin cậy — hệ thống giữ chế độ tìm kiếm sao.";
      }
    } else {
      state.dotEl.classList.add("is-idle");
      state.telemetryTextEl.textContent = "Chế độ tìm kiếm sao — chưa khóa hướng";
      if (state.telemetryMetaEl) {
        state.telemetryMetaEl.textContent =
          state.catalogCount > 100
            ? `${state.catalogCount.toLocaleString("vi-VN")} sao thực ${state.catalogSource}`
            : "Bầu trời thực J2000";
      }
    }
  }

  function ensureLabelEl(index) {
    while (state.labelPool.length <= index) {
      const el = document.createElement("div");
      el.className = "o3d-star-label";
      el.style.display = "none";
      const mainSpan = document.createElement("span");
      mainSpan.className = "o3d-star-main";
      const subSpan = document.createElement("span");
      subSpan.className = "o3d-star-sub";
      el.append(mainSpan, subSpan);
      el._main = mainSpan;
      el._sub = subSpan;
      state.labelLayerEl.appendChild(el);
      state.labelPool.push(el);
    }
    return state.labelPool[index];
  }

  function updateProjectedLabels(width, height) {
    if (!state.labelLayerEl || !state.camera) return;
    if (!state.showLabels || width < 40 || height < 40) {
      for (let i = 0; i < state.labelPool.length; i++) {
        state.labelPool[i].style.display = "none";
      }
      return;
    }

    const THREE = window.THREE;
    const camPos = state.camera.position;
    const skyOff = state.skyGroup.position;
    const isPov = state.povBlend > 0.65;
    const maxMatched = isPov ? 14 : 6;
    const placedBoxes = [];
    let used = 0;

    const projVec = new THREE.Vector3();
    const rayDir = new THREE.Vector3();

    function tryPlace(wx, wy, wz, title, subText, clsName) {
      projVec.set(skyOff.x + wx * R_SKY, skyOff.y + wy * R_SKY, skyOff.z + wz * R_SKY);

      // In Orbit view, hide HTML labels that are physically behind the solid Earth sphere
      if (state.povBlend < 0.85) {
        rayDir.subVectors(projVec, camPos).normalize();
        const bDot = camPos.dot(rayDir);
        if (bDot < 0) {
          const closestSq = camPos.lengthSq() - bDot * bDot;
          if (closestSq < 1.03 * 1.03) return false;
        }
      }

      projVec.project(state.camera);
      if (projVec.z >= 1.0 || projVec.z <= -1.0) return false;

      const sx = (projVec.x * 0.5 + 0.5) * width;
      const sy = (-projVec.y * 0.5 + 0.5) * height;
      const marginX = 28;
      const marginYTop = 44;
      const marginYBot = 52;
      if (sx < marginX || sx > width - marginX || sy < marginYTop || sy > height - marginYBot) {
        return false;
      }

      const estW = title.length * 6.8 + (subText ? subText.length * 5.6 + 14 : 12);
      const estH = 19;
      const bx0 = sx + 9;
      const by0 = sy - 10;
      const bx1 = bx0 + estW;
      const by1 = by0 + estH;
      if (bx1 > width - 8) return false;

      for (let k = 0; k < placedBoxes.length; k++) {
        const b = placedBoxes[k];
        if (bx0 < b[2] && bx1 > b[0] && by0 < b[3] && by1 > b[1]) {
          return false;
        }
      }
      placedBoxes.push([bx0 - 4, by0 - 3, bx1 + 4, by1 + 3]);

      const el = ensureLabelEl(used++);
      el.className = "o3d-star-label " + clsName;
      el._main.textContent = title;
      el._sub.textContent = subText || "";
      el._sub.style.display = subText ? "inline" : "none";
      el.style.display = "";
      el.style.transform = `translate3d(${Math.round(bx0)}px, ${Math.round(by0)}px, 0)`;
      return true;
    }

    // 1. Matched catalog stars (highest priority)
    let matchedPlaced = 0;
    for (let i = 0; i < state.matchedStars.length && matchedPlaced < maxMatched; i++) {
      const st = state.matchedStars[i];
      const showSub = isPov ? st.sub : st.hasIau ? "" : "";
      if (tryPlace(st.wx, st.wy, st.wz, st.name, showSub, "is-matched")) {
        matchedPlaced++;
      }
    }

    // 2. Major celestial landmarks (skipping any star already shown in matchedStars)
    const matchedIds = new Set(state.matchedStars.map((s) => s.id));
    for (let i = 0; i < state.landmarkItems.length; i++) {
      const lm = state.landmarkItems[i];
      if (state.catalogScheme === "HR" && matchedIds.has(lm.hr)) continue;
      const cls = lm.isPole ? "is-landmark is-pole" : "is-landmark";
      tryPlace(lm.wx, lm.wy, lm.wz, lm.name, "", cls);
    }

    for (let i = used; i < state.labelPool.length; i++) {
      state.labelPool[i].style.display = "none";
    }
  }

  function bindPointerControls(stageEl) {
    function markInteracted() {
      if (!state.userHasInteracted) {
        state.userHasInteracted = true;
        if (state.hintPillEl) state.hintPillEl.classList.add("is-dimmed");
      }
    }

    stageEl.addEventListener("pointerdown", (ev) => {
      if (ev.button !== undefined && ev.button !== 0 && ev.pointerType === "mouse") return;
      markInteracted();
      try {
        stageEl.setPointerCapture(ev.pointerId);
      } catch (_) {
        // Ignore capture errors in synthetic test events
      }
      state.activePointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY });
      stageEl.classList.add("is-dragging");

      if (state.activePointers.size === 2) {
        const pts = Array.from(state.activePointers.values());
        state.lastPinchDist = Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y);
      }
    });

    stageEl.addEventListener("pointermove", (ev) => {
      if (!state.activePointers.has(ev.pointerId)) return;
      const prev = state.activePointers.get(ev.pointerId);
      const dx = ev.clientX - prev.x;
      const dy = ev.clientY - prev.y;
      prev.x = ev.clientX;
      prev.y = ev.clientY;

      if (state.activePointers.size === 2) {
        const pts = Array.from(state.activePointers.values());
        const dist = Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y);
        if (state.lastPinchDist > 8 && dist > 8) {
          const ratio = state.lastPinchDist / dist;
          if (state.viewMode === "pov") {
            state.targetPovZoom = clamp(state.targetPovZoom * ratio, 0.35, 2.35);
          } else {
            state.targetRadius = clamp(state.targetRadius * ratio, 2.15, 16.0);
          }
        }
        state.lastPinchDist = dist;
        return;
      }

      if (state.activePointers.size === 1) {
        if (state.viewMode === "pov") {
          const fovScale = clamp(state.fovVDeg / 25.0, 0.25, 2.2);
          state.targetPovYaw = clamp(state.targetPovYaw + dx * 0.0022 * fovScale, -0.62, 0.62);
          state.targetPovPitch = clamp(state.targetPovPitch + dy * 0.0022 * fovScale, -0.62, 0.62);
        } else {
          state.targetTheta -= dx * 0.0062;
          state.targetPhi = clamp(state.targetPhi - dy * 0.0055, 0.14, Math.PI - 0.14);
        }
      }
    });

    function releasePointer(ev) {
      state.activePointers.delete(ev.pointerId);
      if (state.activePointers.size < 2) state.lastPinchDist = 0;
      if (state.activePointers.size === 0) stageEl.classList.remove("is-dragging");
    }

    stageEl.addEventListener("pointerup", releasePointer);
    stageEl.addEventListener("pointercancel", releasePointer);
    stageEl.addEventListener("lostpointercapture", releasePointer);

    stageEl.addEventListener(
      "wheel",
      (ev) => {
        ev.preventDefault();
        markInteracted();
        const factor = Math.exp(clamp(ev.deltaY, -160, 160) * 0.0011);
        if (state.viewMode === "pov") {
          state.targetPovZoom = clamp(state.targetPovZoom * factor, 0.35, 2.35);
        } else {
          state.targetRadius = clamp(state.targetRadius * factor, 2.15, 16.0);
        }
      },
      { passive: false }
    );
  }

  function computePovTargetVfovDeg(aspect) {
    const tanH = Math.tan(clamp(state.fovHDeg, 1.5, 135) * 0.5 * DEG2RAD);
    const tanV = Math.tan(clamp(state.fovVDeg, 1.5, 135) * 0.5 * DEG2RAD);
    const pad = state.povZoomMode === "tight" ? 1.045 : 1.32;
    const fitTanV = Math.max(tanV, tanH / Math.max(aspect, 0.28)) * pad * state.povZoomMul;
    return clamp(2.0 * Math.atan(fitTanV) * RAD2DEG, 6.0, 108.0);
  }

  function animateFrame(nowMs) {
    state.rafId = window.requestAnimationFrame(animateFrame);
    if (!state.webglOk || !state.renderer || !state.container) return;

    const dt = state.lastTimeMs > 0 ? Math.min((nowMs - state.lastTimeMs) * 0.001, 0.08) : 0.016;
    state.lastTimeMs = nowMs;

    const width = state.stageEl.clientWidth;
    const height = state.stageEl.clientHeight;
    if (width < 4 || height < 4) return;

    const THREE = window.THREE;
    const damp = 1.0 - Math.exp(-10.5 * dt);

    // 1. Advance Earth rotation & orbital motion
    if (state.isPlaying) {
      state.earthSpin += dt * 0.042;
      state.cloudSpin = (state.cloudSpin + dt * 0.0022) % 1.0;
      state.orbitAngle = (state.orbitAngle + dt * state.orbitSpeed) % (Math.PI * 2);

      // Gentle star-search attitude scan when idle or LOST
      if (state.solveState !== "solved") {
        const scanT = nowMs * 0.00022;
        const bx = Math.cos(scanT) * 0.78;
        const by = 0.34 + 0.22 * Math.sin(scanT * 1.7);
        const bz = Math.sin(scanT) * 0.78;
        state.camBore.set(bx, by, bz).normalize();
        const upRef = new THREE.Vector3(0, 1, 0);
        state.camRight.crossVectors(state.camBore, upRef).normalize();
        state.camUp.crossVectors(state.camRight, state.camBore).normalize();
      }
    }

    if (state.earthMesh) state.earthMesh.rotation.y = state.earthSpin;
    if (state.earthMaterial) state.earthMaterial.uniforms.uCloudShift.value = state.cloudSpin;

    // 2. Update satellite position on inclined LEO ring & lock inertial attitude
    const cosO = Math.cos(state.orbitAngle) * R_ORBIT;
    const sinO = Math.sin(state.orbitAngle) * R_ORBIT;
    const satPos = new THREE.Vector3(
      state.orbitU.x * cosO + state.orbitV.x * sinO,
      state.orbitU.y * cosO + state.orbitV.y * sinO,
      state.orbitU.z * cosO + state.orbitV.z * sinO
    );
    state.satelliteGroup.position.copy(satPos);

    // Exact 3x3 attitude matrix [camRight, camUp, -camBore] (det = +1)
    const basisMat = new THREE.Matrix4().makeBasis(
      state.camRight,
      state.camUp,
      state.camBore.clone().negate()
    );
    const sensorQuat = new THREE.Quaternion().setFromRotationMatrix(basisMat);
    state.attitudeGroup.quaternion.copy(sensorQuat);

    // 3. Advance smooth cubic camera mode transition (0.75s)
    if (state.transElapsed < state.transDuration) {
      state.transElapsed = Math.min(state.transElapsed + dt, state.transDuration);
      const u = state.transElapsed / state.transDuration;
      const eased = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
      state.povBlend = state.transFromBlend + (state.transToBlend - state.transFromBlend) * eased;
    } else {
      state.povBlend = state.transToBlend;
    }

    // 4. Compute Orbit Camera Pose
    state.sphRadius += (state.targetRadius - state.sphRadius) * damp;
    state.sphPhi += (state.targetPhi - state.sphPhi) * damp;
    state.sphTheta += (state.targetTheta - state.sphTheta) * damp;
    state.orbitLookAt.lerp(state.targetLookAt, damp);

    const sinPhi = Math.sin(state.sphPhi);
    const orbitCamPos = new THREE.Vector3(
      state.orbitLookAt.x + state.sphRadius * sinPhi * Math.sin(state.sphTheta),
      state.orbitLookAt.y + state.sphRadius * Math.cos(state.sphPhi),
      state.orbitLookAt.z + state.sphRadius * sinPhi * Math.cos(state.sphTheta)
    );
    const orbitLookMat = new THREE.Matrix4().lookAt(
      orbitCamPos,
      state.orbitLookAt,
      new THREE.Vector3(0, 1, 0)
    );
    const orbitCamQuat = new THREE.Quaternion().setFromRotationMatrix(orbitLookMat);
    const orbitVfov = 48.0;

    // 5. Compute Sensor POV Camera Pose (exact 1:1 optical alignment + optional user inspection offset)
    state.povYawOff += (state.targetPovYaw - state.povYawOff) * damp;
    state.povPitchOff += (state.targetPovPitch - state.povPitchOff) * damp;
    state.povZoomMul += (state.targetPovZoom - state.povZoomMul) * damp;

    const povCamPos = satPos.clone().addScaledVector(state.camBore, 0.16);
    const panQuat = new THREE.Quaternion().setFromEuler(
      new THREE.Euler(state.povPitchOff, state.povYawOff, 0, "YXZ")
    );
    const povCamQuat = sensorQuat.clone().multiply(panQuat);
    const aspect = width / Math.max(height, 1);
    const povVfov = computePovTargetVfovDeg(aspect);

    // 6. Blend Orbit <-> POV camera poses seamlessly
    const b = state.povBlend;
    state.camera.position.lerpVectors(orbitCamPos, povCamPos, b);
    state.camera.quaternion.slerpQuaternions(orbitCamQuat, povCamQuat, b);
    const activeVfov = orbitVfov + (povVfov - orbitVfov) * b;
    if (Math.abs(state.camera.fov - activeVfov) > 1e-4 || Math.abs(state.camera.aspect - aspect) > 1e-4) {
      state.camera.fov = activeVfov;
      state.camera.aspect = aspect;
      state.camera.updateProjectionMatrix();
    }

    // Center celestial sphere on camera in POV mode so real stars are at true infinity (0.00" parallax!)
    state.skyGroup.position.set(
      state.camera.position.x * b,
      state.camera.position.y * b,
      state.camera.position.z * b
    );

    // Smoothly fade near-field spacecraft & cone during POV entry so baffle never clips near plane
    const meshVis = 1.0 - clamp((b - 0.12) / 0.45, 0.0, 1.0);
    state.satelliteGroup.visible = meshVis > 0.01;
    if (state.satelliteGroup.visible) {
      for (let i = 0; i < state.spacecraftMeshes.length; i++) {
        state.spacecraftMeshes[i].material.opacity = meshVis;
      }
      const baseConeAlpha = state.solveState === "solved" ? 0.14 : 0.07;
      const baseEdgeAlpha = state.solveState === "solved" ? 0.50 : 0.22;
      state.frustumConeMat.uniforms.uOpacity.value = baseConeAlpha * meshVis;
      state.frustumEdgeMat.uniforms.uOpacity.value = baseEdgeAlpha * meshVis;
    }
    if (state.orbitRingLine) {
      state.orbitRingLine.visible = meshVis > 0.02;
      state.orbitRingLine.material.opacity = 0.26 * meshVis;
    }

    // Scale star PSF size gently when zoomed into narrow sensor FOV
    if (state.starMaterial) {
      state.starMaterial.uniforms.uZoomBoost.value = clamp(Math.pow(44.0 / activeVfov, 0.36), 0.92, 1.95);
    }

    state.renderer.render(state.scene, state.camera);
    updateProjectedLabels(width, height);
  }

  function init(containerEl) {
    const target = containerEl || (typeof document !== "undefined" ? document.getElementById("orbit3d-root") : null);
    if (!target) return api;

    if (state.initialized && state.container === target) {
      resize();
      return api;
    }

    // Clean up any previous instance if re-mounted to a new container
    if (state.rafId && typeof window !== "undefined" && window.cancelAnimationFrame) {
      window.cancelAnimationFrame(state.rafId);
      state.rafId = 0;
    }
    if (state.resizeObserver) {
      state.resizeObserver.disconnect();
      state.resizeObserver = null;
    }
    if (state.renderer) {
      try {
        state.renderer.dispose();
      } catch (_) {
        // Ignore disposal errors
      }
      state.renderer = null;
    }

    state.container = target;
    state.initialized = true;
    state.labelPool = [];
    state.activePointers.clear();

    buildDomHud(target);
    syncHudButtons();

    const THREE = typeof window !== "undefined" ? window.THREE : null;
    if (!THREE || typeof THREE.WebGLRenderer !== "function") {
      state.webglOk = false;
      renderWebglFallback("Không tìm thấy thư viện đồ họa Three.js để dựng cảnh 3D.");
      updateHudTelemetry();
      return api;
    }

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: false,
        powerPreference: "high-performance"
      });
    } catch (_) {
      state.webglOk = false;
      renderWebglFallback("Thiết bị hoặc môi trường kiểm thử hiện tại không hỗ trợ WebGL.");
      updateHudTelemetry();
      return api;
    }

    state.webglOk = true;
    const dpr = clamp(typeof window !== "undefined" && window.devicePixelRatio ? window.devicePixelRatio : 1, 1, 2);
    renderer.setPixelRatio(dpr);
    renderer.setClearColor(0x05070b, 1.0);
    if (THREE.SRGBColorSpace) {
      renderer.outputColorSpace = THREE.SRGBColorSpace;
    }
    renderer.domElement.className = "o3d-canvas";
    state.stageEl.appendChild(renderer.domElement);
    state.renderer = renderer;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(48, 1.4, 0.04, 1600);
    state.scene = scene;
    state.camera = camera;

    state.camRight = new THREE.Vector3(1, 0, 0);
    state.camUp = new THREE.Vector3(0, 1, 0);
    state.camBore = new THREE.Vector3(0.45, 0.36, 0.82).normalize();
    state.orbitLookAt = new THREE.Vector3(0, 0, 0);
    state.targetLookAt = new THREE.Vector3(0, 0, 0);

    // Subtle cosmos + sun lighting for the 3D spacecraft metallic bus & gold foil
    const ambient = new THREE.AmbientLight(0x8fa8c8, 0.65);
    const hemi = new THREE.HemisphereLight(0xdbeafe, 0x0f172a, 0.55);
    const sunLight = new THREE.DirectionalLight(0xfff7ed, 2.2);
    sunLight.position.set(6, 3.5, 5);
    scene.add(ambient, hemi, sunLight);

    // 1. Celestial Sky Group (J2000 stars, cosmic dust, RA/Dec grid, FOV footprint, matched reticles)
    const skyGroup = new THREE.Group();
    state.skyGroup = skyGroup;
    scene.add(skyGroup);

    const dust = buildCosmicDust(THREE);
    dust.material.uniforms.uPixelRatio.value = dpr;
    state.dustPoints = dust;
    skyGroup.add(dust);

    state.starMaterial = createStarMaterial(THREE);
    state.starMaterial.uniforms.uPixelRatio.value = dpr;

    state.reticleMaterial = createReticleMaterial(THREE);
    state.reticleMaterial.uniforms.uPixelRatio.value = dpr;

    const gridGroup = buildCelestialGrid(THREE);
    gridGroup.visible = state.showGrid;
    state.gridGroup = gridGroup;
    skyGroup.add(gridGroup);

    const skyFovGroup = new THREE.Group();
    state.skyFovGroup = skyFovGroup;
    skyGroup.add(skyFovGroup);

    // 2. Earth + Rayleigh Atmosphere
    state.earthGroup = buildEarthAndAtmosphere(THREE);
    scene.add(state.earthGroup);

    // 3. Inclined LEO Orbital Ring + Detailed 3D Spacecraft
    const ringMat = new THREE.LineBasicMaterial({
      color: 0x7dd3fc,
      transparent: true,
      opacity: 0.26,
      depthWrite: false
    });
    const ringLine = new THREE.Line(new THREE.BufferGeometry(), ringMat);
    state.orbitRingLine = ringLine;
    scene.add(ringLine);

    const satGroup = buildSpacecraftAndFrustum(THREE);
    scene.add(satGroup);

    rebuildOrbitPlane(state.camBore);
    rebuildFrustumGeometry();
    computeOptimalOrbitFraming(true);

    // Populate built-in landmarks immediately, then load full 5,023-star Yale BSC5 catalog
    seedInitialLandmarks();
    fetchSkyCatalog("bsc5");

    bindPointerControls(state.stageEl);

    if (typeof ResizeObserver === "function") {
      state.resizeObserver = new ResizeObserver(() => resize());
      state.resizeObserver.observe(target);
    }
    if (typeof window !== "undefined") {
      window.addEventListener("resize", resize);
    }

    // Apply any payload passed before init()
    if (state.lastPayload) {
      updateFromPayload(state.lastPayload);
    } else {
      updateHudTelemetry();
    }

    resize();
    state.lastTimeMs = 0;
    if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
      state.rafId = window.requestAnimationFrame(animateFrame);
    }

    return api;
  }

  function updateFromPayload(payload) {
    state.lastPayload = payload || null;
    if (!payload || typeof payload !== "object") {
      state.solveState = "idle";
      updateHudTelemetry();
      return;
    }

    // Retry real sky catalog fetch if initial request happened before server route was warm
    const reqCat = payload.catalog_source || "bsc5";
    const wantHip = String(reqCat).toUpperCase().includes("HIP");
    if (!state.catalogLoadedReal || (wantHip && state.catalogScheme !== "HIP") || (!wantHip && state.catalogScheme === "HIP")) {
      fetchSkyCatalog(wantHip ? "hipparcos" : "bsc5");
    }

    // Camera FOV extraction
    const cam = payload.camera || {};
    if (Array.isArray(cam.fov_deg) && cam.fov_deg.length >= 2) {
      const fh = Number(cam.fov_deg[0]);
      const fv = Number(cam.fov_deg[1]);
      if (Number.isFinite(fh) && fh > 0.5) state.fovHDeg = fh;
      if (Number.isFinite(fv) && fv > 0.5) state.fovVDeg = fv;
    }

    const isSolved =
      (payload.status === "SOLVED" || (payload.status === undefined && Boolean(payload.success))) &&
      Array.isArray(payload.q_est) &&
      payload.q_est.length === 4;

    const THREE = typeof window !== "undefined" ? window.THREE : null;

    if (isSolved && THREE && state.webglOk) {
      const dcm = quatToDcm(payload.q_est);
      if (dcm) {
        state.solveState = "solved";
        // Row 0 = Sensor +X (Right), Row 1 = Sensor +Y (Down -> negate for Screen +Y Up), Row 2 = Sensor +Z (Boresight)
        state.camRight.set(...icrsToWorldXYZ(dcm[0][0], dcm[0][1], dcm[0][2])).normalize();
        state.camUp.set(...icrsToWorldXYZ(-dcm[1][0], -dcm[1][1], -dcm[1][2])).normalize();
        state.camBore.set(...icrsToWorldXYZ(dcm[2][0], dcm[2][1], dcm[2][2])).normalize();

        if (state.frustumConeMat && state.frustumEdgeMat) {
          state.frustumConeMat.uniforms.uColor.value.setHex(0x7dd3fc);
          state.frustumEdgeMat.uniforms.uColor.value.setHex(0x7dd3fc);
        }

        rebuildOrbitPlane(state.camBore);
        rebuildFrustumGeometry();
        rebuildSkyFovFootprint();
        rebuildMatchedStars(payload);

        // Reset POV inspection offsets so 1:1 optical alignment is exact
        state.targetPovYaw = 0;
        state.targetPovPitch = 0;
        state.targetPovZoom = 1;
        state.povYawOff = 0;
        state.povPitchOff = 0;
        state.povZoomMul = 1;

        // Default to 3D Orbit view framed on Earth + Satellite + Target J2000 Sky Region
        setViewMode("orbit");
        computeOptimalOrbitFraming(false);
        updateHudTelemetry();
        return;
      }
    }

    // Handle LOST or non-WebGL state cleanly without bogus lock
    state.solveState = isSolved ? "solved" : "lost";
    state.matchedStars = [];
    if (THREE && state.webglOk) {
      if (state.frustumConeMat && state.frustumEdgeMat) {
        state.frustumConeMat.uniforms.uColor.value.setHex(0xfbbf24);
        state.frustumEdgeMat.uniforms.uColor.value.setHex(0xfbbf24);
      }
      rebuildFrustumGeometry();
      rebuildSkyFovFootprint();
      rebuildMatchedStars(null);
      setViewMode("orbit");
    }
    updateHudTelemetry();
  }

  function setViewMode(mode) {
    const next = mode === "pov" ? "pov" : "orbit";
    const changed = state.viewMode !== next;
    state.viewMode = next;
    if (changed) {
      state.transFromBlend = state.povBlend;
      state.transToBlend = next === "pov" ? 1.0 : 0.0;
      state.transElapsed = 0.0;
      if (next === "pov") {
        state.targetPovYaw = 0;
        state.targetPovPitch = 0;
        state.targetPovZoom = 1;
      }
    }
    syncHudButtons();
  }

  function togglePlay() {
    state.isPlaying = !state.isPlaying;
    syncHudButtons();
    return state.isPlaying;
  }

  function resetView() {
    state.targetPovYaw = 0;
    state.targetPovPitch = 0;
    state.targetPovZoom = 1;
    if (state.viewMode === "orbit") {
      if (state.camBore && state.webglOk) {
        computeOptimalOrbitFraming(false);
      } else {
        state.targetRadius = 4.85;
        state.targetPhi = 1.18;
        state.targetTheta = 0.65;
      }
    }
  }

  function toggleGrid() {
    state.showGrid = !state.showGrid;
    if (state.gridGroup) state.gridGroup.visible = state.showGrid;
    syncHudButtons();
    return state.showGrid;
  }

  function resize() {
    if (!state.webglOk || !state.renderer || !state.stageEl || !state.camera) return;
    const w = state.stageEl.clientWidth;
    const h = state.stageEl.clientHeight;
    if (w < 4 || h < 4) return;
    const dpr = clamp(typeof window !== "undefined" && window.devicePixelRatio ? window.devicePixelRatio : 1, 1, 2);
    state.renderer.setPixelRatio(dpr);
    state.renderer.setSize(w, h, false);
    if (state.starMaterial) state.starMaterial.uniforms.uPixelRatio.value = dpr;
    if (state.reticleMaterial) state.reticleMaterial.uniforms.uPixelRatio.value = dpr;
    if (state.dustPoints) state.dustPoints.material.uniforms.uPixelRatio.value = dpr;
    state.camera.aspect = w / h;
    state.camera.updateProjectionMatrix();
  }

  const api = {
    init,
    updateFromPayload,
    setViewMode,
    togglePlay,
    resetView,
    toggleGrid,
    resize
  };

  if (typeof window !== "undefined") {
    window.StarTrackerOrbit3D = api;
  }
})();
