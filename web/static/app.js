/* Star Tracker — Cosmos Observatory Frontend Controller */
(function () {
  "use strict";

  const form = document.getElementById("run-form");
  const btnRun = document.getElementById("btn-run");
  const btnDrawerRun = document.getElementById("btn-drawer-run");
  const btnSeed = document.getElementById("btn-seed42");
  const btnGlarePreset = document.getElementById("btn-glare-preset");
  const btnMountPreset = document.getElementById("btn-mount-preset");
  const btnTetra3Preset = document.getElementById("btn-tetra3-preset");
  const btnWelcomeRun = document.getElementById("btn-welcome-run");
  const btnThemeToggle = document.getElementById("btn-theme-toggle");
  const themeToggleIcon = document.getElementById("theme-toggle-icon");
  const themeToggleLabel = document.getElementById("theme-toggle-label");
  const btnOpenDrawer = document.getElementById("btn-open-drawer");
  const btnCloseDrawer = document.getElementById("btn-close-drawer");
  const btnPipExpand = document.getElementById("btn-pip-expand");
  const btnRadec = document.getElementById("btn-radec");
  const btnLoad = document.getElementById("btn-load");
  const btnUpload = document.getElementById("btn-upload");

  const configDrawer = document.getElementById("config-drawer");
  const drawerBackdrop = document.getElementById("drawer-backdrop");

  const localImage = document.getElementById("local-image");
  const localSidecar = document.getElementById("local-sidecar");
  const localFileHint = document.getElementById("local-file-hint");
  const detailsOptics = document.getElementById("details-optics");
  const detailsDataset = document.getElementById("details-dataset");

  const opticsCustom = document.getElementById("optics-custom");
  const opticsReadout = document.getElementById("optics-readout");
  const opticsPreset = document.getElementById("optics-preset");
  const focalInput = document.getElementById("focal-mm");
  const pixelInput = document.getElementById("pixel-um");
  const widthInput = document.getElementById("image-width");
  const heightInput = document.getElementById("image-height");
  const tolInput = document.getElementById("angular-tol");

  const btnRndSeed = document.getElementById("btn-rnd-seed");
  const seedInput = document.getElementById("seed-input");
  const frameSelect = document.getElementById("frame-select");

  const statusEl = document.getElementById("status");
  const verdictEl = document.getElementById("verdict");
  const kpiStatusBadge = document.getElementById("kpi-status-badge");
  const kpiVerdictSub = document.getElementById("kpi-verdict-sub");
  const falseStarsSlider = document.getElementById("false-stars-slider");
  const falseStarsVal = document.getElementById("false-stars-val");

  const kpiAttErrVal = document.getElementById("kpi-att-err-val");
  const kpiAttErrBadge = document.getElementById("kpi-att-err-badge");
  const kpiAttErrSub = document.getElementById("kpi-att-err-sub");
  const kpiTimeVal = document.getElementById("kpi-time-val");
  const kpiTimeBreakdown = document.getElementById("kpi-time-breakdown");
  const kpiStarsVal = document.getElementById("kpi-stars-val");
  const kpiStarPct = document.getElementById("kpi-star-pct");
  const kpiStarsSub = document.getElementById("kpi-stars-sub");
  const kpiBoresightVal = document.getElementById("kpi-boresight-val");
  const kpiBoresightSub = document.getElementById("kpi-boresight-sub");

  const downlinkHexDisplay = document.getElementById("downlink-hex-display");
  const decodeQ0 = document.getElementById("decode-q0");
  const decodeQ1 = document.getElementById("decode-q1");
  const decodeQ2 = document.getElementById("decode-q2");
  const decodeQ3 = document.getElementById("decode-q3");

  const barCentroid = document.getElementById("bar-centroid");
  const barId = document.getElementById("bar-id");
  const barWahba = document.getElementById("bar-wahba");
  const tCentroid = document.getElementById("t-centroid");
  const tId = document.getElementById("t-id");
  const tWahba = document.getElementById("t-wahba");
  const tTotal = document.getElementById("t-total");

  const compareBody = document.querySelector("#compare-table tbody");
  const metaDl = document.getElementById("meta-dl");
  const fovBody = document.querySelector("#fov-table tbody");
  const idBody = document.querySelector("#id-table tbody");
  const fovCount = document.getElementById("fov-count");
  const idCount = document.getElementById("id-count");
  const starSearchInput = document.getElementById("star-search-input");

  const viewStage3d = document.getElementById("view-stage3d");
  const viewSplit = document.getElementById("view-split");
  const viewOutput = document.getElementById("view-output");
  const viewHud = document.getElementById("view-hud");

  const btnCompare3dRaw = document.getElementById("btn-compare3d-raw");
  const btnCompare3dAnnotated = document.getElementById("btn-compare3d-annotated");
  const btnImgBright = document.getElementById("btn-img-bright");
  const imgBrightLabel = document.getElementById("img-bright-label");
  const btnZoomSensor = document.getElementById("btn-zoom-sensor");
  const compare3dImg = document.getElementById("compare3d-img");
  const slotCompare3d = document.getElementById("slot-compare3d");
  const capCompare3d = document.getElementById("cap-compare3d");
  const sensorLiveDot = document.getElementById("sensor-live-dot");
  const sensorStageWrap = document.getElementById("sensor-stage-wrap");
  const sensorOverlayCanvas = document.getElementById("sensor-overlay-canvas");
  const sensorStarTooltip = document.getElementById("sensor-star-tooltip");

  const capOrbit3d = document.getElementById("cap-orbit3d");
  const orbit3dRoot = document.getElementById("orbit3d-root");
  const welcomeHudCard = document.getElementById("welcome-hud-card");
  const pipSensorCard = document.getElementById("pip-sensor-card");
  const pipSensorImg = document.getElementById("pip-sensor-img");
  const pipSensorBadge = document.getElementById("pip-sensor-badge");
  const pipSensorMeta = document.getElementById("pip-sensor-meta");

  const imgIn = document.getElementById("input-img");
  const imgOut = document.getElementById("output-img");
  const imgOutLarge = document.getElementById("output-img-large");
  const imgHud = document.getElementById("hud-img");
  const slotIn = document.getElementById("slot-in");
  const slotOut = document.getElementById("slot-out");
  const capIn = document.getElementById("cap-in");
  const capOut = document.getElementById("cap-out");
  const shaIntegrityText = document.getElementById("sha-integrity-text");

  const imageModal = document.getElementById("image-modal");
  const modalImg = document.getElementById("modal-img");
  const modalTitle = document.getElementById("modal-title");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const btnZoomIn = document.getElementById("btn-zoom-in");
  const btnZoomOut = document.getElementById("btn-zoom-out");
  const btnZoomReset = document.getElementById("btn-zoom-reset");

  const radecConvertedEl = document.getElementById("radec-converted");
  const radecPaste = document.getElementById("radec-paste");
  const raHms = document.getElementById("ra-hms");
  const decDms = document.getElementById("dec-dms");
  const raDecimal = document.getElementById("ra-decimal");
  const decDecimal = document.getElementById("dec-decimal");
  const btnClearRadec = document.getElementById("btn-clear-radec");
  const presetIndicator = document.getElementById("preset-active-indicator");

  let modalZoomLevel = 1.0;
  let activePointHr = null;
  let activePointingMode = "target-seed";
  let radecSyncing = false;
  let radecTimer = 0;
  let storedFovRows = [];
  let storedIdRows = [];

  // Default to full-screen 3D cosmos on initial idle load; switch to 50/50 compare3d on first solve
  let currentViewMode = "orbit3d";
  let userPinnedOrbitFullscreen = false;
  let hasCompletedRun = false;

  // Sensor viewer state
  let compare3dSource = "annotated"; // "raw" | "annotated"
  let usingCleanImage = false;
  let lastCleanUrl = "";
  let lastInUrl = "";
  let lastOutUrl = "";
  let lastSensorPayload = null;
  let sensorOverlayPoints = [];
  let hoveredSensorStar = null;
  let catalogSelectedStarId = null;

  if (form) {
    form.addEventListener("submit", (ev) => ev.preventDefault());
  }

  /* =======================================================================
     UI Theme Toggle (Luminous Space Navy <-> Daylight White Studio)
     & 2D Starfield Brightness Boost Controls
     ======================================================================= */
  const ICON_SUN_SVG =
    '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round">' +
    '<circle cx="12" cy="12" r="4"/><path d="M12 2v2.2M12 19.8V22M4.93 4.93l1.55 1.55M17.52 17.52l1.55 1.55M2 12h2.2M19.8 12H22M4.93 19.07l1.55-1.55M17.52 6.48l1.55-1.55"/></svg>';
  const ICON_MOON_SVG =
    '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';

  let activeTheme = "cosmos";
  function applyUiTheme(mode, persist = true) {
    activeTheme = mode === "light" ? "light" : "cosmos";
    if (activeTheme === "light") {
      document.documentElement.dataset.theme = "light";
    } else {
      delete document.documentElement.dataset.theme;
    }
    if (btnThemeToggle) {
      btnThemeToggle.setAttribute("aria-pressed", activeTheme === "light" ? "true" : "false");
    }
    if (themeToggleIcon) {
      themeToggleIcon.innerHTML = activeTheme === "light" ? ICON_MOON_SVG : ICON_SUN_SVG;
    }
    if (themeToggleLabel) {
      themeToggleLabel.textContent = activeTheme === "light" ? "Nền Tối" : "Nền Sáng";
    }
    if (persist) {
      try {
        window.localStorage.setItem("st_ui_theme", activeTheme);
      } catch (_) {
        // Ignore storage restrictions
      }
    }
  }

  try {
    const savedTheme = window.localStorage.getItem("st_ui_theme");
    if (savedTheme === "light") {
      applyUiTheme("light", false);
    } else {
      applyUiTheme("cosmos", false);
    }
  } catch (_) {
    applyUiTheme("cosmos", false);
  }

  if (btnThemeToggle) {
    btnThemeToggle.addEventListener("click", () => {
      applyUiTheme(activeTheme === "light" ? "cosmos" : "light", true);
    });
  }

  const IMG_BRIGHT_PRESETS = [
    { id: "std", label: "Sáng rõ (1.4×)", cls: "img-bright-std", boost: true },
    { id: "vivid", label: "Rực rỡ (2.0×)", cls: "img-bright-vivid", boost: true },
    { id: "raw", label: "Gốc (1.0×)", cls: "img-bright-raw", boost: false }
  ];
  let imgBrightIdx = 0;

  function applyImgBrightnessPreset(idx) {
    imgBrightIdx = ((idx % IMG_BRIGHT_PRESETS.length) + IMG_BRIGHT_PRESETS.length) % IMG_BRIGHT_PRESETS.length;
    const preset = IMG_BRIGHT_PRESETS[imgBrightIdx];
    [compare3dImg, pipSensorImg, imgIn].forEach((el) => {
      if (!el) return;
      el.classList.remove("img-bright-std", "img-bright-vivid", "img-bright-raw");
      el.classList.add(preset.cls);
    });
    if (imgBrightLabel) imgBrightLabel.textContent = preset.label;
    if (btnImgBright) btnImgBright.classList.toggle("is-bright-boost", preset.boost);
  }

  applyImgBrightnessPreset(0);

  if (btnImgBright) {
    btnImgBright.addEventListener("click", () => {
      applyImgBrightnessPreset(imgBrightIdx + 1);
    });
  }

  /* =======================================================================
     Slide-Over Configuration Drawer Controls
     ======================================================================= */
  function openDrawer() {
    if (!configDrawer || !drawerBackdrop) return;
    drawerBackdrop.hidden = false;
    configDrawer.hidden = false;
  }

  function closeDrawer() {
    if (!configDrawer || !drawerBackdrop) return;
    configDrawer.hidden = true;
    drawerBackdrop.hidden = true;
  }

  if (btnOpenDrawer) btnOpenDrawer.addEventListener("click", openDrawer);
  if (btnCloseDrawer) btnCloseDrawer.addEventListener("click", closeDrawer);
  if (drawerBackdrop) drawerBackdrop.addEventListener("click", closeDrawer);

  /* =======================================================================
     Formatting & Comparison Helpers
     ======================================================================= */
  function fmt(v, digits = 5) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    if (typeof v === "number") {
      if (Number.isInteger(v)) return String(v);
      return v.toFixed(digits);
    }
    return String(v);
  }

  function fmtCompareCell(row, key) {
    const v = row[key];
    if (v === null || v === undefined) return "—";
    if (typeof v === "string") return v;
    if (typeof v !== "number" || Number.isNaN(v)) return "—";
    const p = String(row.param || "");
    if (p.startsWith("q")) return v.toFixed(8);
    if (row.unit === "arcsec") return `${v.toFixed(3)} ″`;
    if (row.unit === "deg" && key === "delta") {
      return `${v.toFixed(6)}° (${(v * 3600).toFixed(2)}″)`;
    }
    if (Number.isInteger(v)) return String(v);
    return v.toFixed(5);
  }

  function deltaPillClass(row) {
    const d = row.delta;
    if (d === null || d === undefined) return "count-pill delta-na";
    if (typeof d === "string") {
      if (
        row.est === "LOST" ||
        d === "LOST" ||
        d === "FALSE_LOCK" ||
        d.includes("INSUFFICIENT") ||
        d.includes("FAILED") ||
        d.includes("DEGENERATE") ||
        d.includes("EXCESSIVE") ||
        d.includes("CONSISTENCY")
      ) {
        return "count-pill delta-fail";
      }
      if (String(row.param || "").includes("ngoại lai") && d !== "-0 ngoại lai") {
        return "count-pill delta-warn";
      }
      return "count-pill highlight";
    }
    if (typeof d !== "number" || Number.isNaN(d)) return "count-pill delta-na";
    if (row.unit === "arcsec") {
      return Math.abs(d) < (row.limit_arcsec || 10) ? "count-pill highlight" : "count-pill delta-warn";
    }
    if (row.unit === "deg") {
      return Math.abs(d) * 3600 < 10 ? "count-pill highlight" : "count-pill delta-warn";
    }
    if (String(row.param || "").startsWith("q") && Math.abs(d) < 1e-4) {
      return "count-pill highlight";
    }
    return "count-pill";
  }

  let abortCtrl = null;
  function setBusy(on, msg) {
    [
      btnRun,
      btnDrawerRun,
      btnSeed,
      btnGlarePreset,
      btnMountPreset,
      btnTetra3Preset,
      btnWelcomeRun,
      btnLoad,
      btnRadec,
      btnUpload
    ].forEach((b) => {
      if (!b) return;
      b.disabled = on;
      b.classList.toggle("busy", on);
    });
    if (on && statusEl) {
      statusEl.className = "status-banner";
      statusEl.innerHTML = `<span class="busy-dot"></span><strong>Đang xử lý:</strong> ${msg}`;
      statusEl.title = msg;
    }
  }

  async function fetchJson(url, opts, timeoutMs) {
    if (abortCtrl) abortCtrl.abort();
    abortCtrl = new AbortController();
    const timer = setTimeout(() => abortCtrl.abort(), timeoutMs || 120000);
    try {
      const res = await fetch(url, { ...opts, signal: abortCtrl.signal });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    } catch (err) {
      if (err && err.name === "AbortError") {
        throw new Error("Yêu cầu quá thời gian chờ hoặc đã bị hủy. Vui lòng thử lại.");
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  /* =======================================================================
     Interactive 2D Sensor Starfield Canvas Overlay & 3D Hover Sync
     ======================================================================= */
  function drawSensorOverlay() {
    if (!sensorOverlayCanvas || !sensorStageWrap) return;
    const cw = sensorStageWrap.clientWidth;
    const ch = sensorStageWrap.clientHeight;
    if (cw < 8 || ch < 8) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const targetW = Math.round(cw * dpr);
    const targetH = Math.round(ch * dpr);
    if (sensorOverlayCanvas.width !== targetW || sensorOverlayCanvas.height !== targetH) {
      sensorOverlayCanvas.width = targetW;
      sensorOverlayCanvas.height = targetH;
    }

    const ctx = sensorOverlayCanvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cw, ch);

    sensorOverlayPoints = [];
    if (!usingCleanImage || !lastSensorPayload || !compare3dImg || compare3dImg.hidden) {
      return;
    }

    const cam = lastSensorPayload.camera || {};
    const st = lastSensorPayload.input_stats || {};
    const camW = Number(cam.width || st.width || compare3dImg.naturalWidth || 1500);
    const camH = Number(cam.height || st.height || compare3dImg.naturalHeight || 1000);
    if (!(camW > 0 && camH > 0)) return;

    const scale = Math.min(cw / camW, ch / camH);
    const drawW = camW * scale;
    const drawH = camH * scale;
    const offX = (cw - drawW) * 0.5;
    const offY = (ch - drawH) * 0.5;

    const identList = Array.isArray(lastSensorPayload.identified_stars) ? lastSensorPayload.identified_stars : [];
    const detUv = Array.isArray(lastSensorPayload.detected_uv) ? lastSensorPayload.detected_uv : [];

    const matchedPts = [];
    for (let i = 0; i < identList.length; i++) {
      const s = identList[i];
      if (!s || !Number.isFinite(Number(s.u_px)) || !Number.isFinite(Number(s.v_px))) continue;
      const u = Number(s.u_px);
      const v = Number(s.v_px);
      const sx = offX + (u + 0.5) * scale;
      const sy = offY + (v + 0.5) * scale;
      const scheme = String(s.id_scheme || "HR").toUpperCase();
      const code = `${scheme} ${s.id}`;
      const displayName = s.iau_name || code;
      const pt = {
        isIdentified: true,
        id: Number(s.id),
        displayName,
        hasIau: Boolean(s.iau_name),
        code,
        mag: Number(s.mag),
        u,
        v,
        sx,
        sy
      };
      matchedPts.push(pt);
      sensorOverlayPoints.push(pt);
    }

    const unmatchedPts = [];
    for (let i = 0; i < detUv.length; i++) {
      const pair = detUv[i];
      if (!Array.isArray(pair) || pair.length < 2) continue;
      const u = Number(pair[0]);
      const v = Number(pair[1]);
      if (!Number.isFinite(u) || !Number.isFinite(v)) continue;
      let dup = false;
      for (let j = 0; j < matchedPts.length; j++) {
        if (Math.hypot(matchedPts[j].u - u, matchedPts[j].v - v) < 2.6) {
          dup = true;
          break;
        }
      }
      if (dup) continue;
      const sx = offX + (u + 0.5) * scale;
      const sy = offY + (v + 0.5) * scale;
      const pt = {
        isIdentified: false,
        id: null,
        displayName: "Tâm sáng phát hiện",
        hasIau: false,
        code: "",
        mag: null,
        u,
        v,
        sx,
        sy
      };
      unmatchedPts.push(pt);
      sensorOverlayPoints.push(pt);
    }

    if (compare3dSource === "annotated") {
      // 1. Crisp optical boresight center crosshair
      const cx = offX + drawW * 0.5;
      const cy = offY + drawH * 0.5;
      ctx.save();
      ctx.strokeStyle = "rgba(56, 189, 248, 0.48)";
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(cx - 20, cy);
      ctx.lineTo(cx - 6, cy);
      ctx.moveTo(cx + 6, cy);
      ctx.lineTo(cx + 20, cy);
      ctx.moveTo(cx, cy - 20);
      ctx.lineTo(cx, cy - 6);
      ctx.moveTo(cx, cy + 6);
      ctx.lineTo(cx, cy + 20);
      ctx.stroke();

      // Crisp sensor boundary frame
      ctx.strokeStyle = "rgba(125, 211, 252, 0.32)";
      ctx.lineWidth = 1.2;
      ctx.strokeRect(offX + 0.5, offY + 0.5, Math.max(0, drawW - 1), Math.max(0, drawH - 1));
      ctx.restore();

      // 2. Unidentified detected centroids (vivid sky-cyan rings)
      ctx.save();
      ctx.strokeStyle = "#38BDF8";
      ctx.lineWidth = 1.8;
      for (let i = 0; i < unmatchedPts.length; i++) {
        const p = unmatchedPts[i];
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, 5.4, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();

      // 3. Identified catalog stars (bright emerald astrograph reticles + high-contrast pill labels)
      ctx.save();
      for (let i = 0; i < matchedPts.length; i++) {
        const p = matchedPts[i];
        ctx.strokeStyle = "#34D399";
        ctx.lineWidth = 1.95;
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, 8.0, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = "#38BDF8";
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(p.sx - 12.0, p.sy);
        ctx.lineTo(p.sx - 8.6, p.sy);
        ctx.moveTo(p.sx + 8.6, p.sy);
        ctx.lineTo(p.sx + 12.0, p.sy);
        ctx.moveTo(p.sx, p.sy - 12.0);
        ctx.lineTo(p.sx, p.sy - 8.6);
        ctx.moveTo(p.sx, p.sy + 8.6);
        ctx.lineTo(p.sx, p.sy + 12.0);
        ctx.stroke();
      }

      const sortedLabels = matchedPts
        .slice()
        .sort((a, b) => (a.hasIau !== b.hasIau ? (a.hasIau ? -1 : 1) : (a.mag || 9) - (b.mag || 9)));

      ctx.font = "700 11.5px Inter, -apple-system, sans-serif";
      ctx.textBaseline = "middle";
      const placed = [];
      const maxLabels = 20;
      let countLbl = 0;

      for (let i = 0; i < sortedLabels.length && countLbl < maxLabels; i++) {
        const p = sortedLabels[i];
        const txt = p.displayName;
        const tw = ctx.measureText(txt).width;
        const pw = tw + 12;
        const ph = 19;
        let lx = p.sx + 11;
        let ly = p.sy - ph * 0.5;
        if (lx + pw > offX + drawW - 6) {
          lx = p.sx - 11 - pw;
        }
        ly = Math.max(offY + 6, Math.min(offY + drawH - ph - 6, ly));

        let collide = false;
        for (let k = 0; k < placed.length; k++) {
          const b = placed[k];
          if (lx < b[2] && lx + pw > b[0] && ly < b[3] && ly + ph > b[1]) {
            collide = true;
            break;
          }
        }
        if (collide) continue;
        placed.push([lx - 3, ly - 2, lx + pw + 3, ly + ph + 2]);
        countLbl++;

        ctx.fillStyle = "rgba(15, 23, 42, 0.88)";
        ctx.strokeStyle = p.hasIau ? "rgba(56, 189, 248, 0.78)" : "rgba(52, 211, 153, 0.62)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(lx, ly, pw, ph, 9);
        } else {
          ctx.rect(lx, ly, pw, ph);
        }
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#FFFFFF";
        ctx.fillText(txt, lx + 6, ly + ph * 0.5 + 0.5);
      }
      ctx.restore();
    }

    // 4. Active hovered or catalog-selected highlight ring
    const activeTarget =
      hoveredSensorStar ||
      (catalogSelectedStarId != null
        ? matchedPts.find((m) => m.id === catalogSelectedStarId) || null
        : null);

    if (activeTarget) {
      ctx.save();
      ctx.strokeStyle = "#67E8F9";
      ctx.lineWidth = 2;
      ctx.shadowColor = "rgba(103, 232, 249, 0.85)";
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(activeTarget.sx, activeTarget.sy, 12.5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
  }

  if (sensorOverlayCanvas && sensorStageWrap) {
    sensorOverlayCanvas.addEventListener("pointermove", (ev) => {
      if (!sensorOverlayPoints.length) return;
      const rect = sensorOverlayCanvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;

      let best = null;
      let bestDist = 24;
      for (let i = 0; i < sensorOverlayPoints.length; i++) {
        const pt = sensorOverlayPoints[i];
        const d = Math.hypot(pt.sx - mx, pt.sy - my);
        // Slightly favor identified catalog stars when cursor is near both
        const effD = pt.isIdentified ? d * 0.85 : d;
        if (d <= 24 && effD < bestDist) {
          bestDist = effD;
          best = pt;
        }
      }

      if (best !== hoveredSensorStar) {
        hoveredSensorStar = best;
        catalogSelectedStarId = null;
        drawSensorOverlay();
        if (best && best.isIdentified) {
          window.StarTrackerOrbit3D?.highlightStar(best.id);
        } else {
          window.StarTrackerOrbit3D?.highlightStar(null);
        }
      }

      if (best && sensorStarTooltip) {
        if (best.isIdentified) {
          const magStr = Number.isFinite(best.mag) ? (best.mag >= 0 ? `+${best.mag.toFixed(2)}` : best.mag.toFixed(2)) : "—";
          const codePart = best.hasIau ? ` · ${best.code}` : "";
          sensorStarTooltip.innerHTML =
            `<strong>${best.displayName}</strong>` +
            `<span class="tt-mono">${codePart} · V ${magStr} · (${best.u.toFixed(1)}, ${best.v.toFixed(1)})</span>`;
        } else {
          sensorStarTooltip.innerHTML =
            `<strong>Tâm sáng phát hiện</strong>` +
            `<span class="tt-mono"> · (${best.u.toFixed(1)}, ${best.v.toFixed(1)}) px</span>`;
        }
        sensorStarTooltip.hidden = false;
        const tw = sensorStarTooltip.offsetWidth || 190;
        const th = sensorStarTooltip.offsetHeight || 28;
        let tx = best.sx + 14;
        let ty = best.sy - th - 10;
        if (tx + tw > rect.width - 8) tx = Math.max(8, best.sx - tw - 14);
        if (ty < 46) ty = Math.min(rect.height - th - 8, best.sy + 14);
        sensorStarTooltip.style.transform = `translate3d(${Math.round(tx)}px, ${Math.round(ty)}px, 0)`;
      } else if (sensorStarTooltip) {
        sensorStarTooltip.hidden = true;
      }
    });

    sensorOverlayCanvas.addEventListener("pointerleave", () => {
      if (hoveredSensorStar) {
        hoveredSensorStar = null;
        drawSensorOverlay();
        window.StarTrackerOrbit3D?.highlightStar(null);
      }
      if (sensorStarTooltip) sensorStarTooltip.hidden = true;
    });

    sensorOverlayCanvas.addEventListener("click", () => {
      if (hoveredSensorStar && hoveredSensorStar.isIdentified) {
        window.StarTrackerOrbit3D?.highlightStar(hoveredSensorStar.id, { focus: true });
      }
    });

    if (typeof ResizeObserver === "function") {
      const sensorRo = new ResizeObserver(() => drawSensorOverlay());
      sensorRo.observe(sensorStageWrap);
    }
  }

  /* =======================================================================
     Stage View Modes & Navigation Tabs
     ======================================================================= */
  function setStageViewMode(mode, fromUserClick = false) {
    currentViewMode = mode;
    if (fromUserClick && hasCompletedRun) {
      userPinnedOrbitFullscreen = mode === "orbit3d";
    }
    document.querySelectorAll(".view-mode-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-mode") === mode);
    });
    const is3d = mode === "compare3d" || mode === "orbit3d";
    if (viewStage3d) {
      viewStage3d.hidden = !is3d;
      viewStage3d.classList.toggle("is-compare3d", mode === "compare3d");
      viewStage3d.classList.toggle("is-orbit3d", mode === "orbit3d");
    }
    if (viewSplit) viewSplit.hidden = mode !== "split";
    if (viewOutput) viewOutput.hidden = mode !== "output";
    if (viewHud) viewHud.hidden = mode !== "hud";
    if (is3d) {
      requestAnimationFrame(() => {
        window.StarTrackerOrbit3D?.resize();
        drawSensorOverlay();
      });
    }
  }

  function syncCompare3dImage() {
    if (!compare3dImg) return;
    if (lastCleanUrl) {
      usingCleanImage = true;
      compare3dImg.hidden = false;
      if (compare3dImg.src !== lastCleanUrl && !compare3dImg.src.endsWith(lastCleanUrl)) {
        compare3dImg.src = lastCleanUrl;
      }
      compare3dImg.alt = "Khung ảnh cảm biến sao thuần khiết";
      if (slotCompare3d) slotCompare3d.classList.add("hidden");
      drawSensorOverlay();
      return;
    }
    usingCleanImage = false;
    const fallbackUrl = compare3dSource === "annotated" ? lastOutUrl : lastInUrl;
    if (!fallbackUrl) return;
    compare3dImg.hidden = false;
    compare3dImg.src = fallbackUrl;
    compare3dImg.alt =
      compare3dSource === "annotated"
        ? "Ảnh nhận diện sao đối chiếu với bầu trời 3D"
        : "Ảnh gốc cảm biến đối chiếu với bầu trời 3D";
    if (slotCompare3d) slotCompare3d.classList.add("hidden");
    drawSensorOverlay();
  }

  if (compare3dImg) {
    compare3dImg.addEventListener("load", () => {
      drawSensorOverlay();
    });
    compare3dImg.addEventListener("error", () => {
      if (usingCleanImage && (lastInUrl || lastOutUrl)) {
        lastCleanUrl = "";
        usingCleanImage = false;
        syncCompare3dImage();
      }
    });
  }

  function setCompare3dSource(srcKind) {
    compare3dSource = srcKind === "raw" ? "raw" : "annotated";
    if (btnCompare3dRaw) btnCompare3dRaw.classList.toggle("active", compare3dSource === "raw");
    if (btnCompare3dAnnotated) btnCompare3dAnnotated.classList.toggle("active", compare3dSource === "annotated");
    syncCompare3dImage();
  }

  if (btnCompare3dRaw) {
    btnCompare3dRaw.addEventListener("click", () => setCompare3dSource("raw"));
  }
  if (btnCompare3dAnnotated) {
    btnCompare3dAnnotated.addEventListener("click", () => setCompare3dSource("annotated"));
  }
  if (btnPipExpand) {
    btnPipExpand.addEventListener("click", () => {
      userPinnedOrbitFullscreen = false;
      setStageViewMode("compare3d", true);
    });
  }

  document.querySelectorAll(".view-mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-mode") || "compare3d";
      setStageViewMode(mode, true);
    });
  });

  function activateTab(tabId) {
    document.querySelectorAll(".tab-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-tab") === tabId);
    });
    document.querySelectorAll(".tab-pane").forEach((p) => {
      const isMatch = p.id === tabId;
      p.classList.toggle("active", isMatch);
      p.hidden = !isMatch;
      if (isMatch) p.scrollTop = 0;
    });
    if (tabId === "tab-imagery" && (currentViewMode === "compare3d" || currentViewMode === "orbit3d")) {
      requestAnimationFrame(() => {
        window.StarTrackerOrbit3D?.resize();
        drawSensorOverlay();
      });
    }
  }

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      if (tabId) activateTab(tabId);
    });
  });

  document.querySelectorAll(".sub-tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".sub-tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".sub-tab-pane").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      const targetId = btn.getAttribute("data-target");
      activePointingMode = targetId;
      const target = document.getElementById(targetId);
      if (target) target.classList.add("active");
      if (targetId !== "target-presets" && activePointHr !== null) {
        activePointHr = null;
        document.querySelectorAll(".preset-chip").forEach((c) => c.classList.remove("active"));
        if (presetIndicator) {
          presetIndicator.textContent = "Chọn một ngôi sao để hướng thẳng tâm kính";
          presetIndicator.className = "preset-indicator muted";
        }
      }
    });
  });

  function setCentroidBackend(mode) {
    const classical = document.getElementById("centroid-classical");
    const cnn = document.getElementById("centroid-cnn");
    if (mode === "cnn") {
      if (cnn) cnn.checked = true;
    } else if (classical) {
      classical.checked = true;
    }
  }

  if (falseStarsSlider && falseStarsVal) {
    falseStarsSlider.addEventListener("input", () => {
      falseStarsVal.textContent = falseStarsSlider.value;
    });
  }

  if (btnRndSeed && seedInput) {
    btnRndSeed.addEventListener("click", () => {
      seedInput.value = Math.floor(Math.random() * 100000);
      setCentroidBackend("classical");
      closeDrawer();
      postRun(gatherFormData());
    });
  }

  document.querySelectorAll(".preset-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".preset-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      const hr = parseInt(chip.getAttribute("data-hr"), 10);
      const name = chip.getAttribute("data-name");
      activePointHr = hr;
      if (presetIndicator) {
        presetIndicator.textContent = `Đang hướng tâm kính vào ${name} (HR ${hr})`;
        presetIndicator.className = "preset-indicator active";
      }
      clearRadecFields();
      setCentroidBackend("classical");
      closeDrawer();
      postRun(gatherFormData());
    });
  });

  /* =======================================================================
     RA / Dec Sexagesimal & Decimal Input Parsing
     ======================================================================= */
  if (btnClearRadec) {
    btnClearRadec.addEventListener("click", () => {
      clearRadecFields();
    });
  }

  function clearRadecFields() {
    radecSyncing = true;
    if (radecPaste) radecPaste.value = "";
    if (raHms) raHms.value = "";
    if (decDms) decDms.value = "";
    if (raDecimal) raDecimal.value = "";
    if (decDecimal) decDecimal.value = "";
    radecSyncing = false;
    setRadecSummary("Chưa nhập", "Chưa nhập", false);
  }

  function setRadecSummary(raText, decText, isErr) {
    const raEl = document.getElementById("radec-line-ra");
    const decEl = document.getElementById("radec-line-dec");
    if (!radecConvertedEl || !raEl || !decEl) return;
    radecConvertedEl.classList.toggle("err", !!isErr);
    radecConvertedEl.classList.toggle("muted", !isErr && (!raText || raText === "Chưa nhập"));
    raEl.textContent = raText || "Chưa nhập";
    decEl.textContent = decText || "Chưa nhập";
  }

  function splitRadecPaste(text) {
    const t = String(text || "")
      .replace(/\u00a0/g, " ")
      .replace(/[−–]/g, "-")
      .trim();
    if (!t) return null;
    const hms = t.match(/^(\d{1,2}(?:\.\d+)?\s*[hH][\s\S]*?)\s*([+\-]\s*\d{1,3}[\s\S]*)$/);
    if (hms) return { ra: hms[1].trim(), dec: hms[2].trim() };
    const colon = t.match(/^(\d{1,2}:\d{1,2}(?::\d+(?:\.\d+)?)?)\s+([+\-]?\d{1,2}:\d{1,2}(?::\d+(?:\.\d+)?)?)$/);
    if (colon) return { ra: colon[1], dec: colon[2] };
    const comma = t.match(/^([\d.]+)\s*,\s*([+\-]?[\d.]+)$/);
    if (comma) return { ra: comma[1], dec: comma[2] };
    return null;
  }

  let radecSource = null;
  async function syncRadecWithApi() {
    const source = radecSource;
    const paste = String(radecPaste?.value || "").trim();
    const raH = String(raHms?.value || "").trim();
    const decD = String(decDms?.value || "").trim();
    const body = { radec_fmt: "auto" };
    if (source === radecPaste) {
      const fromPaste = splitRadecPaste(paste);
      if (fromPaste) {
        body.ra_deg = fromPaste.ra;
        body.dec_deg = fromPaste.dec;
      } else if (paste) {
        body.radec_paste = paste;
      } else {
        setRadecSummary("Chưa nhập", "Chưa nhập", false);
        return;
      }
    } else if (raH && decD) {
      body.ra_deg = raH;
      body.dec_deg = decD;
    } else if (paste) {
      const fromPaste = splitRadecPaste(paste);
      if (fromPaste) {
        body.ra_deg = fromPaste.ra;
        body.dec_deg = fromPaste.dec;
      } else {
        body.radec_paste = paste;
      }
    } else {
      setRadecSummary("Chưa nhập", "Chưa nhập", false);
      return;
    }
    try {
      const res = await fetch("/api/parse-radec", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!data.ok) {
        setRadecSummary(data.error || "Không đọc được tọa độ", "", true);
        return;
      }
      radecSyncing = true;
      if (source === radecPaste) {
        if (raHms && document.activeElement !== raHms) raHms.value = data.ra_hms;
        if (decDms && document.activeElement !== decDms) decDms.value = data.dec_dms;
      }
      if (raDecimal) raDecimal.value = Number(data.ra_deg).toFixed(5);
      if (decDecimal) decDecimal.value = (data.dec_deg >= 0 ? "+" : "") + Number(data.dec_deg).toFixed(5);
      radecSyncing = false;
      setRadecSummary(
        `${data.ra_hms} (${Number(data.ra_deg).toFixed(4)}°)`,
        `${data.dec_dms} (${Number(data.dec_deg).toFixed(4)}°)`,
        false
      );
    } catch (err) {
      radecSyncing = false;
      setRadecSummary(String(err.message || err), "", true);
    }
  }

  [radecPaste, raHms, decDms].forEach((el) => {
    if (!el) return;
    const queue = (ev) => {
      if (radecSyncing || (ev && ev.isComposing)) return;
      radecSource = el;
      clearTimeout(radecTimer);
      radecTimer = setTimeout(syncRadecWithApi, 420);
    };
    el.addEventListener("input", queue);
    el.addEventListener("compositionend", () => queue(null));
  });

  /* =======================================================================
     Zoom Lightbox Modal
     ======================================================================= */
  function openLightbox(src, title) {
    if (!imageModal || !modalImg || !src) return;
    modalImg.src = src;
    const isRawLike = src.includes("demo_clean") || src.includes("demo_input");
    modalImg.classList.remove("img-bright-std", "img-bright-vivid", "img-bright-raw");
    if (isRawLike) {
      modalImg.classList.add(IMG_BRIGHT_PRESETS[imgBrightIdx].cls);
    }
    if (modalTitle) modalTitle.textContent = title || "Chi tiết Khung ảnh Quang học";
    modalZoomLevel = 1.0;
    modalImg.style.transform = "scale(1)";
    imageModal.hidden = false;
  }

  function closeLightbox() {
    if (!imageModal) return;
    imageModal.hidden = true;
  }

  if (btnCloseModal) btnCloseModal.addEventListener("click", closeLightbox);
  const modalBackdrop = document.querySelector(".modal-backdrop");
  if (modalBackdrop) modalBackdrop.addEventListener("click", closeLightbox);
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (imageModal && !imageModal.hidden) closeLightbox();
      else if (configDrawer && !configDrawer.hidden) closeDrawer();
    }
  });

  if (btnZoomIn) {
    btnZoomIn.addEventListener("click", () => {
      modalZoomLevel = Math.min(modalZoomLevel + 0.3, 4.5);
      if (modalImg) modalImg.style.transform = `scale(${modalZoomLevel})`;
    });
  }
  if (btnZoomOut) {
    btnZoomOut.addEventListener("click", () => {
      modalZoomLevel = Math.max(modalZoomLevel - 0.3, 0.5);
      if (modalImg) modalImg.style.transform = `scale(${modalZoomLevel})`;
    });
  }
  if (btnZoomReset) {
    btnZoomReset.addEventListener("click", () => {
      modalZoomLevel = 1.0;
      if (modalImg) modalImg.style.transform = "scale(1)";
    });
  }

  if (btnZoomSensor) {
    btnZoomSensor.addEventListener("click", () => {
      const zoomSrc = compare3dSource === "annotated" ? lastOutUrl || lastCleanUrl : lastCleanUrl || lastInUrl;
      if (zoomSrc) {
        openLightbox(zoomSrc, "Khung ảnh cảm biến quang học");
      }
    });
  }

  document.querySelectorAll(".btn-inspect").forEach((btn) => {
    btn.addEventListener("click", () => {
      const imgId = btn.getAttribute("data-img");
      const targetImg = document.getElementById(imgId);
      if (targetImg && targetImg.src && !targetImg.hidden) {
        openLightbox(targetImg.src, targetImg.alt || "Chi tiết Khung ảnh");
      }
    });
  });

  [imgIn, imgOut, imgOutLarge, imgHud].forEach((img) => {
    if (!img) return;
    img.addEventListener("click", () => {
      if (img.src && !img.hidden) {
        openLightbox(img.src, img.alt || "Chi tiết Khung ảnh");
      }
    });
  });

  /* =======================================================================
     Form Data Gathering & Star Directory Rendering
     ======================================================================= */
  function gatherFormData() {
    const rawData = form ? Object.fromEntries(new FormData(form).entries()) : {};
    const checkedMode = document.querySelector('input[name="mode"]:checked');
    const checkedCentroid = document.querySelector('input[name="centroid_backend"]:checked');

    const payload = {
      mode: String((checkedMode && checkedMode.value) || rawData.mode || "fast"),
      seed: Number(rawData.seed || 42),
      catalog: String(rawData.catalog || "bsc5"),
      solver: String(rawData.solver || "svd"),
      centroid_backend: String((checkedCentroid && checkedCentroid.value) || rawData.centroid_backend || "classical"),
      omega: Number(rawData.omega || 0.06),
      omega_axis: String(rawData.omega_axis || "y"),
      exposure: Number(rawData.exposure || 0.15),
      glare: String(rawData.glare || "none"),
      sky_clutter: String(rawData.sky_clutter || "none"),
      false_stars: Number(rawData.false_stars || 0)
    };

    if (String(rawData.optics || "locked") === "custom") {
      const putNum = (key, raw) => {
        const text = String(raw ?? "").trim();
        if (!text) return;
        const value = Number(text);
        if (Number.isFinite(value)) payload[key] = value;
      };
      putNum("focal_mm", rawData.focal_mm);
      putNum("pixel_um", rawData.pixel_um);
      putNum("image_width", rawData.image_width);
      putNum("image_height", rawData.image_height);
      putNum("angular_tol_arcsec", rawData.angular_tol_arcsec);
    }

    if (activePointingMode === "target-presets" && activePointHr !== null) {
      payload.point_hr = activePointHr;
    } else if (activePointingMode === "target-radec") {
      const paste = String(radecPaste?.value || "").trim();
      const fromPaste = splitRadecPaste(paste);
      if (fromPaste) {
        payload.ra_deg = fromPaste.ra;
        payload.dec_deg = fromPaste.dec;
      } else if (raHms?.value && decDms?.value) {
        payload.ra_deg = String(raHms.value).trim();
        payload.dec_deg = String(decDms.value).trim();
      } else if (raDecimal?.value && decDecimal?.value) {
        payload.ra_deg = String(raDecimal.value).trim();
        payload.dec_deg = String(decDecimal.value).trim();
      }
    }
    return payload;
  }

  function renderStarTable(tbody, countBadge, rows, query = "") {
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!rows || !rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty">Không có sao trong danh sách</td></tr>';
      if (countBadge) countBadge.textContent = "0 sao";
      return;
    }
    const q = query.toLowerCase().trim();
    const filtered = rows.filter((r) => {
      if (!q) return true;
      const name = String(r.iau_name || "").toLowerCase();
      const id = String(r.id || "");
      const scheme = String(r.id_scheme || "").toLowerCase();
      return name.includes(q) || id.includes(q) || scheme.includes(q);
    });
    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty">Không tìm thấy ngôi sao phù hợp</td></tr>';
      if (countBadge) countBadge.textContent = `0 / ${rows.length} sao`;
      return;
    }
    for (const r of filtered) {
      const tr = document.createElement("tr");
      const name = r.iau_name || (r.designation ? r.designation : "—");
      const hasName = Boolean(r.iau_name);
      tr.title = "Nhấp để định vị ngôi sao này trên không gian 3D & khung ảnh cảm biến";
      tr.innerHTML = `
        <td><strong>${r.id_scheme || "HR"} ${r.id}</strong></td>
        <td><span class="count-pill">V ${fmt(r.mag, 2)}</span></td>
        <td class="${hasName ? "named" : ""}">${hasName ? '<span class="star-dot"></span>' + name : "—"}</td>
        <td>${fmt(r.u_px, 1)}</td>
        <td>${fmt(r.v_px, 1)}</td>
      `;
      tr.addEventListener("click", () => {
        catalogSelectedStarId = Number(r.id);
        activateTab("tab-imagery");
        if (currentViewMode !== "compare3d" && currentViewMode !== "orbit3d") {
          setStageViewMode("compare3d", false);
        }
        requestAnimationFrame(() => {
          drawSensorOverlay();
          window.StarTrackerOrbit3D?.highlightStar(r.id, { focus: true });
        });
      });
      tbody.appendChild(tr);
    }
    if (countBadge) countBadge.textContent = `${filtered.length} sao`;
  }

  if (starSearchInput) {
    starSearchInput.addEventListener("input", (e) => {
      const q = e.target.value;
      renderStarTable(fovBody, fovCount, storedFovRows, q);
      renderStarTable(idBody, idCount, storedIdRows, q);
    });
  }

  /* =======================================================================
     Render Solver Payload across Telemetry, Sensor Overlay & 3D Sky
     ======================================================================= */
  function renderPayload(payload) {
    hasCompletedRun = true;
    lastSensorPayload = payload;
    hoveredSensorStar = null;
    catalogSelectedStarId = null;

    const metrics = payload.metrics || {};
    const mstats = payload.match_stats || {};
    const status = String(payload.status || metrics.status || mstats.status || (payload.success ? "SOLVED" : "LOST"));
    const rejectCode = payload.reject_code ?? metrics.reject_code ?? mstats.reject_code ?? null;
    const verdict = metrics.verdict || (status === "SOLVED" ? "SOLVED" : "LOST");
    const attErr = metrics.attitude_error_arcsec;
    const attOk = typeof attErr === "number" && Number.isFinite(attErr);

    const fov = payload.stars_in_fov || [];
    const ident = payload.identified_stars || [];
    storedFovRows = fov;
    storedIdRows = ident;

    const nDet = metrics.n_detected ?? mstats.n_detected ?? (payload.detected_uv ? payload.detected_uv.length : fov.length);
    const nMatched = metrics.n_matched ?? ident.length;
    const nInit = mstats.n_initial_matched ?? metrics.n_initial_matched;
    const nValid = mstats.n_valid_pairs ?? metrics.n_valid_pairs ?? nMatched;
    const nRejected = mstats.n_rejected_outliers ?? metrics.n_rejected_outliers ?? 0;
    const minReq = mstats.min_pairs_required ?? metrics.min_pairs_required ?? 4;
    const rmsRes = mstats.rms_residual_arcsec ?? metrics.rms_residual_arcsec;
    const maxRes = mstats.max_residual_arcsec ?? metrics.max_residual_arcsec;
    const rmsTxt = typeof rmsRes === "number" && Number.isFinite(rmsRes) ? `${rmsRes.toFixed(2)}″` : "—";
    const maxTxt = typeof maxRes === "number" && Number.isFinite(maxRes) ? `${maxRes.toFixed(2)}″` : "—";

    const cPrec = metrics.centroid_precision;
    const cRec = metrics.centroid_recall;
    const hasPrecRec =
      (typeof cPrec === "number" && Number.isFinite(cPrec)) ||
      (typeof cRec === "number" && Number.isFinite(cRec));
    const precTxt = typeof cPrec === "number" && Number.isFinite(cPrec) ? `${(cPrec * 100).toFixed(1)}%` : "—";
    const recTxt = typeof cRec === "number" && Number.isFinite(cRec) ? `${(cRec * 100).toFixed(1)}%` : "—";

    // Bottom Flight Telemetry Ribbon
    if (kpiStatusBadge) {
      kpiStatusBadge.textContent = status;
      kpiStatusBadge.className = `kpi-badge status-pill ${status}`;
    }
    if (verdictEl) {
      const pillKey = status === "LOST" ? "LOST" : verdict;
      const pillLabel =
        status === "LOST"
          ? "Chưa khóa hướng"
          : pillKey === "PASS" || pillKey === "SOLVED" || pillKey === "SOLVED_NO_GT"
            ? "Đã khóa hướng"
            : pillKey;
      verdictEl.textContent = pillLabel;
      verdictEl.className = `verdict-pill ${pillKey}`;
    }
    if (kpiVerdictSub) {
      if (status === "LOST") {
        const rc = rejectCode || "REJECTED";
        kpiVerdictSub.textContent = rc;
        kpiVerdictSub.title = `Từ chối khóa: ${rc}`;
      } else {
        kpiVerdictSub.textContent = `RMS ${rmsTxt}`;
        kpiVerdictSub.title = `Phần dư khớp góc: RMS ${rmsTxt} · Cực đại ${maxTxt}`;
      }
    }

    if (kpiAttErrVal) {
      if (attOk) {
        kpiAttErrVal.textContent = `${attErr.toFixed(3)}″`;
        const lim = Number(metrics.limit_arcsec);
        const gate = Number.isFinite(lim) ? lim : 10.0;
        const pass = attErr < gate;
        if (kpiAttErrBadge) kpiAttErrBadge.textContent = pass ? `< ${gate}″` : `≥ ${gate}″`;
        if (kpiAttErrSub) {
          kpiAttErrSub.textContent = hasPrecRec ? `P ${precTxt} · R ${recTxt}` : "So với nhãn chuẩn";
        }
      } else {
        kpiAttErrVal.textContent = "—";
        if (status === "LOST") {
          if (kpiAttErrBadge) kpiAttErrBadge.textContent = "LOST";
          if (kpiAttErrSub) kpiAttErrSub.textContent = "Chưa đủ sao khớp hợp lệ";
        } else {
          if (kpiAttErrBadge) kpiAttErrBadge.textContent = "Ảnh thực";
          if (kpiAttErrSub) kpiAttErrSub.textContent = `RMS ${rmsTxt}`;
        }
      }
    }

    const t = payload.timing_ms || {};
    if (kpiTimeVal) {
      kpiTimeVal.textContent = `${fmt(t.total_pipeline_ms, 1)} ms`;
      if (kpiTimeBreakdown) {
        kpiTimeBreakdown.textContent = `Tâm ${fmt(t.centroiding_ms, 1)} · Khớp ${fmt(t.identification_ms, 1)} ms`;
        kpiTimeBreakdown.title = `Tâm sao ${fmt(t.centroiding_ms, 2)} ms · Khớp ${fmt(t.identification_ms, 2)} ms · Wahba ${fmt(t.attitude_ms, 2)} ms`;
      }
    }

    if (kpiStarsVal) {
      kpiStarsVal.textContent = `${nValid} / ${nDet}`;
      const pct = nDet > 0 ? Math.round((nValid / nDet) * 100) : 0;
      if (kpiStarPct) kpiStarPct.textContent = `${pct}%`;
    }
    if (kpiStarsSub) {
      kpiStarsSub.textContent = `Hợp lệ: ${nValid} · Loại nhiễu: ${nRejected}`;
    }

    const boresight = payload.boresight_est || payload.boresight_gt;
    if (kpiBoresightVal) {
      if (boresight) {
        kpiBoresightVal.textContent = `RA ${fmt(boresight.ra_deg, 2)}° · Dec ${fmt(boresight.dec_deg, 2)}°`;
        if (kpiBoresightSub) {
          kpiBoresightSub.textContent = `${boresight.ra_hms || ""} ${boresight.dec_dms || ""}`.trim();
        }
      } else {
        kpiBoresightVal.textContent = "RA -- · Dec --";
        if (kpiBoresightSub) kpiBoresightSub.textContent = "Chưa khóa";
      }
    }

    // 16-Byte Packet & Telemetry Tab
    if (downlinkHexDisplay && payload.downlink_hex) {
      const hex = payload.downlink_hex.match(/.{1,2}/g)?.join(" ") || payload.downlink_hex;
      downlinkHexDisplay.textContent = hex.toUpperCase();
    }

    const qEst = payload.q_est;
    if (qEst && qEst.length === 4) {
      if (decodeQ0) decodeQ0.textContent = Number(qEst[0]).toFixed(5);
      if (decodeQ1) decodeQ1.textContent = Number(qEst[1]).toFixed(5);
      if (decodeQ2) decodeQ2.textContent = Number(qEst[2]).toFixed(5);
      if (decodeQ3) decodeQ3.textContent = Number(qEst[3]).toFixed(5);
    } else {
      if (decodeQ0) decodeQ0.textContent = "--";
      if (decodeQ1) decodeQ1.textContent = "--";
      if (decodeQ2) decodeQ2.textContent = "--";
      if (decodeQ3) decodeQ3.textContent = "--";
    }

    const totalT = Math.max(t.total_pipeline_ms || 1, 0.1);
    const pCentroid = Math.min(((t.centroiding_ms || 0) / totalT) * 100, 100);
    const pId = Math.min(((t.identification_ms || 0) / totalT) * 100, 100);
    const pWahba = Math.min(((t.attitude_ms || 0) / totalT) * 100, 100);
    if (barCentroid) barCentroid.style.width = `${pCentroid}%`;
    if (barId) barId.style.width = `${pId}%`;
    if (barWahba) barWahba.style.width = `${pWahba}%`;
    if (tCentroid) tCentroid.textContent = `${fmt(t.centroiding_ms, 2)} ms`;
    if (tId) tId.textContent = `${fmt(t.identification_ms, 2)} ms`;
    if (tWahba) tWahba.textContent = `${fmt(t.attitude_ms, 2)} ms`;
    if (tTotal) tTotal.textContent = `${fmt(t.total_pipeline_ms, 2)} ms`;

    if (compareBody) {
      compareBody.innerHTML = "";
      for (const row of payload.compare || []) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${row.param}</strong></td>
          <td>${fmtCompareCell(row, "gt")}</td>
          <td>${fmtCompareCell(row, "est")}</td>
          <td><span class="${deltaPillClass(row)}">${fmtCompareCell(row, "delta")}</span></td>
        `;
        compareBody.appendChild(tr);
      }
    }

    const modeFull = document.getElementById("mode-full");
    const modeFast = document.getElementById("mode-fast");
    if (payload.mode === "full" && modeFull) modeFull.checked = true;
    if (payload.mode === "fast" && modeFast) modeFast.checked = true;

    const cam = payload.camera || {};
    if (metaDl) {
      const initTxt = nInit != null ? String(nInit) : "—";
      const prLine = hasPrecRec ? `<dt>Độ chụm tâm sao</dt><dd>Precision ${precTxt} · Recall ${recTxt}</dd>` : "";
      const fovSpan = Array.isArray(cam.fov_deg) ? cam.fov_deg.map((x) => Number(x).toFixed(2)).join("° × ") + "°" : "—";
      metaDl.innerHTML = `
        <dt>Trạng thái</dt><dd>${status}${rejectCode ? ` (${rejectCode})` : ""}</dd>
        <dt>Cặp sao hợp lệ</dt><dd>${nValid} hợp lệ / ${nRejected} loại nhiễu (sơ bộ ${initTxt}, tối thiểu ${minReq})</dd>
        <dt>Phần dư khớp góc</dt><dd>RMS ${rmsTxt} · Cực đại ${maxTxt}</dd>
        ${prLine}
        <dt>Nguồn dữ liệu</dt><dd>${payload.source === "simulator" ? "Mô phỏng quang học bầu trời sao" : payload.source_image}</dd>
        <dt>Hệ quang học</dt><dd>f = ${fmt(cam.focal_mm, 3)} mm · điểm ảnh ${fmt(cam.pixel_um, 3)} µm · ${cam.width}×${cam.height} px · ${fmt(cam.ifov_arcsec, 2)}″/px · FOV ${fovSpan}</dd>
        <dt>Chỉ mục tra góc</dt><dd>${(payload.angle_table && payload.angle_table.note) || "—"}</dd>
        <dt>Danh mục sao</dt><dd>${payload.catalog_source} (${payload.n_catalog} sao J2000, V ≤ 6.0)</dd>
        <dt>Gói tin 16-byte</dt><dd><code>${payload.downlink_hex}</code> (${payload.downlink_bytes} byte float32)</dd>
        <dt>Quaternion chuẩn</dt><dd>${payload.q_gt_text}</dd>
        <dt>Quaternion ước lượng</dt><dd>${payload.q_est_text}</dd>
      `;
    }

    // Image URLs (prefer borderless clean_url for primary optical viewer & PiP)
    const tstamp = Date.now();
    const cleanUrl = payload.clean_url ? `${payload.clean_url}?t=${tstamp}` : "";
    const inUrl = `${payload.input_url || "/output/demo_input.png"}?t=${tstamp}`;
    const outUrl = `${payload.output_url || "/output/demo_output.png"}?t=${tstamp}`;
    const hudUrl = `${payload.image_url || "/output/demo_result.png"}?t=${tstamp}`;
    lastCleanUrl = cleanUrl;
    lastInUrl = inUrl;
    lastOutUrl = outUrl;

    if (imgIn) {
      imgIn.hidden = false;
      imgIn.src = inUrl;
    }
    if (imgOut) {
      imgOut.hidden = false;
      imgOut.src = outUrl;
    }
    if (imgOutLarge) imgOutLarge.src = outUrl;
    if (imgHud) imgHud.src = hudUrl;
    if (slotIn) slotIn.classList.add("hidden");
    if (slotOut) slotOut.classList.add("hidden");

    const st = payload.input_stats || {};
    const sha = st.sha256_12 || "--";
    const dimTxt = st.width && st.height ? `${st.width}×${st.height} px` : "";
    const usedCent = String(payload.centroid_detector || payload.centroid_backend || "classical");
    const centTag = usedCent.includes("cnn") ? "CNN" : "CoG";

    if (sensorLiveDot) {
      sensorLiveDot.className = `sensor-dot ${status === "SOLVED" ? "is-solved" : "is-lost"}`;
    }
    if (capCompare3d) {
      capCompare3d.textContent = `${dimTxt} · Khớp ${nValid}/${nDet} sao · ${centTag}`.replace(/^\s*·\s*/, "");
    }
    if (capIn) {
      capIn.textContent = `${dimTxt} ${st.dtype || ""} · DN ${st.dn_min ?? "?"}–${st.dn_max ?? "?"}`.trim();
    }
    if (capOut) {
      capOut.textContent = `Khớp ${nValid} sao hợp lệ · Phát hiện ${nDet} tâm sáng`;
    }
    if (capOrbit3d) {
      capOrbit3d.textContent =
        status === "SOLVED" && Array.isArray(cam.fov_deg)
          ? `${payload.catalog_source || "Yale BSC5"} · FOV ${cam.fov_deg.map((x) => Number(x).toFixed(1)).join("° × ")}°`
          : "5.023 sao Yale BSC5 · Thiên cầu thực J2000";
    }
    if (shaIntegrityText) {
      shaIntegrityText.textContent = `SHA-256: ${sha}`;
    }

    // Floating Welcome -> Floating PiP Sensor Card transition
    if (welcomeHudCard) welcomeHudCard.hidden = true;
    if (pipSensorCard) {
      pipSensorCard.hidden = false;
      if (pipSensorImg) pipSensorImg.src = cleanUrl || inUrl;
      if (pipSensorBadge) {
        pipSensorBadge.textContent = status === "SOLVED" ? `Khớp ${nValid} sao` : "LOST";
        pipSensorBadge.classList.toggle("is-lost", status !== "SOLVED");
      }
      if (pipSensorMeta) {
        pipSensorMeta.textContent = dimTxt || "Khung cảm biến";
      }
    }

    syncCompare3dImage();

    if (window.StarTrackerOrbit3D) {
      window.StarTrackerOrbit3D.updateFromPayload(payload);
    }

    if (status === "SOLVED") {
      setStageViewMode(userPinnedOrbitFullscreen ? "orbit3d" : "compare3d", false);
    } else {
      setStageViewMode(cleanUrl ? "compare3d" : "split", false);
    }

    const currentQ = starSearchInput ? starSearchInput.value : "";
    renderStarTable(fovBody, fovCount, fov, currentQ);
    renderStarTable(idBody, idCount, ident, currentQ);

    // Concise, natural human Vietnamese inline status
    const reqCent = String(payload.centroid_backend || "classical");
    const fellBack = Boolean(payload.centroid_fallback) || (reqCent !== "classical" && usedCent === "classical");
    let centBit = "";
    if (reqCent !== "classical") {
      centBit = fellBack ? " · Chuyển tự động về CoG" : " · Tách tâm MobileUNet";
    }

    if (statusEl) {
      if (payload.success && status === "SOLVED") {
        const errPart = attOk ? `Sai số ${attErr.toFixed(3)}″ · ` : "";
        statusEl.className = fellBack ? "status-banner err" : "status-banner success";
        statusEl.innerHTML =
          `<strong>Đã khóa hướng (${fmt(t.total_pipeline_ms, 1)} ms):</strong> ` +
          `${errPart}Khớp <strong>${nValid}/${nDet}</strong> sao, RMS ${rmsTxt}${centBit}.`;
        statusEl.title = statusEl.textContent || "";
      } else {
        const why = payload.error || metrics.error || "Không đủ sao khớp nhất quán hình học.";
        const rcTag = rejectCode ? ` (${rejectCode})` : "";
        statusEl.className = "status-banner err";
        statusEl.innerHTML =
          `<strong>Chưa khóa hướng${rcTag}:</strong> ${why} (hợp lệ ${nValid}/${minReq} sao)${centBit}.`;
        statusEl.title = statusEl.textContent || "";
      }
    }

    if (opticsReadout && payload.angle_table && payload.camera) {
      opticsReadout.className = "radec-status-card";
      opticsReadout.textContent = payload.angle_table.note || "";
    }
  }

  /* =======================================================================
     Optics Geometry & Wide-FOV Table Estimator
     ======================================================================= */
  const ARCSEC_PER_RAD = (180 * 3600) / Math.PI;
  const TOL_PER_PIXEL = 0.88;
  const TABLE_DEG = 30.5;

  function modeFrame() {
    const full = document.getElementById("mode-full") && document.getElementById("mode-full").checked;
    return full
      ? { w: 6000, h: 4000, pixel: 3.72, focal: 50 }
      : { w: 1500, h: 1000, pixel: 14.88, focal: 50 };
  }

  function opticsIsCustom() {
    const picked = document.querySelector('input[name="optics"]:checked');
    return Boolean(picked && picked.value === "custom");
  }

  function plateOf(focalMm, pixelUm, width, height) {
    const pMm = pixelUm * 1e-3;
    const fx = focalMm / pMm;
    const ifov = (pMm / focalMm) * ARCSEC_PER_RAD;
    const hDeg = 2 * Math.atan((width * pMm) / (2 * focalMm)) * (180 / Math.PI);
    const vDeg = 2 * Math.atan((height * pMm) / (2 * focalMm)) * (180 / Math.PI);
    const diagMm = Math.hypot(width * pMm, height * pMm);
    const dDeg = 2 * Math.atan(diagMm / (2 * focalMm)) * (180 / Math.PI);
    let theta = TABLE_DEG;
    if (dDeg > TABLE_DEG) {
      theta = Math.min(180, Math.ceil((dDeg + 0.5) * 2 - 1e-9) / 2);
    }
    const tolText = tolInput && String(tolInput.value || "").trim();
    const tol = tolText ? Number(tolText) : TOL_PER_PIXEL * ifov;
    return { fx, ifov, hDeg, vDeg, dDeg, theta, tol };
  }

  function previewOptics() {
    const frame = modeFrame();
    if (!opticsIsCustom()) {
      return plateOf(frame.focal, frame.pixel, frame.w, frame.h);
    }
    const focal = Number(focalInput && focalInput.value);
    const pixel = Number(pixelInput && pixelInput.value);
    const wText = widthInput && String(widthInput.value || "").trim();
    const hText = heightInput && String(heightInput.value || "").trim();
    const width = wText ? Number(wText) : frame.w;
    const height = hText ? Number(hText) : frame.h;
    if (!(focal > 0) || !(pixel > 0) || !(width >= 16) || !(height >= 16)) return null;
    return plateOf(focal, pixel, width, height);
  }

  function bodyNeedsWideTable(body) {
    if (!body || (body.focal_mm == null && body.pixel_um == null && body.image_width == null)) {
      return false;
    }
    const frame = modeFrame();
    const focal = Number(body.focal_mm || frame.focal);
    const pixel = Number(body.pixel_um || frame.pixel);
    const width = Number(body.image_width || frame.w);
    const height = Number(body.image_height || frame.h);
    const geom = plateOf(focal, pixel, width, height);
    return geom.dDeg > TABLE_DEG;
  }

  function refreshOptics() {
    const isCustom = opticsIsCustom();
    if (opticsCustom) opticsCustom.hidden = !isCustom;
    if (isCustom && detailsOptics) detailsOptics.open = true;
    if (!opticsReadout) return;
    const geom = previewOptics();
    if (!geom) {
      opticsReadout.className = "radec-status-card err";
      opticsReadout.textContent = "Vui lòng nhập tiêu cự (mm) và cỡ điểm ảnh (µm) lớn hơn 0.";
      return;
    }
    const tableLine =
      geom.dDeg <= TABLE_DEG
        ? "Thuộc phạm vi bảng góc 30,5° sẵn có."
        : `Đường chéo ${geom.dDeg.toFixed(1)}° rộng hơn 30,5° (lần chạy đầu tạo bảng góc tới ${geom.theta.toFixed(1)}°).`;
    opticsReadout.className = "radec-status-card";
    opticsReadout.textContent =
      `FOV ${geom.hDeg.toFixed(2)}° × ${geom.vDeg.toFixed(2)}° (chéo ${geom.dDeg.toFixed(2)}°) · ` +
      `${geom.ifov.toFixed(2)}″/px · dung sai ${geom.tol.toFixed(2)}″. ${tableLine}`;
  }

  function applyModeFrameIfPreset() {
    if (!opticsIsCustom() || !focalInput || !pixelInput) return;
    const focal = Number(focalInput.value);
    const pixel = Number(pixelInput.value);
    const sizeEmpty =
      !(widthInput && String(widthInput.value || "").trim()) &&
      !(heightInput && String(heightInput.value || "").trim());
    const stillLockedPreset = focal === 50 && (pixel === 3.72 || pixel === 14.88);
    if (!sizeEmpty || !stillLockedPreset) return;
    const frame = modeFrame();
    focalInput.value = String(frame.focal);
    pixelInput.value = String(frame.pixel);
  }

  document.querySelectorAll('input[name="optics"], input[name="mode"]').forEach((el) => {
    el.addEventListener("change", () => {
      applyModeFrameIfPreset();
      refreshOptics();
    });
  });

  [focalInput, pixelInput, widthInput, heightInput, tolInput].forEach((el) => {
    if (el) el.addEventListener("input", refreshOptics);
  });

  if (opticsPreset) {
    opticsPreset.addEventListener("change", () => {
      if (opticsPreset.value === "full") {
        if (focalInput) focalInput.value = "50";
        if (pixelInput) pixelInput.value = "3.72";
        if (widthInput) widthInput.value = "6000";
        if (heightInput) heightInput.value = "4000";
        const modeFull = document.getElementById("mode-full");
        if (modeFull) modeFull.checked = true;
      } else if (opticsPreset.value === "fast") {
        if (focalInput) focalInput.value = "50";
        if (pixelInput) pixelInput.value = "14.88";
        if (widthInput) widthInput.value = "1500";
        if (heightInput) heightInput.value = "1000";
        const modeFast = document.getElementById("mode-fast");
        if (modeFast) modeFast.checked = true;
      } else if (opticsPreset.value === "mount_lost") {
        if (focalInput) focalInput.value = "4.2";
        if (pixelInput) pixelInput.value = "4.1";
        if (widthInput) widthInput.value = "1024";
        if (heightInput) heightInput.value = "1024";
        const customRadio = document.getElementById("optics-custom-radio");
        if (customRadio) customRadio.checked = true;
        if (opticsCustom) opticsCustom.hidden = false;
      } else if (opticsPreset.value === "tetra3_alt60") {
        if (focalInput) focalInput.value = "35.2911";
        if (pixelInput) pixelInput.value = "6.9";
        if (widthInput) widthInput.value = "1024";
        if (heightInput) heightInput.value = "768";
        const customRadio = document.getElementById("optics-custom-radio");
        if (customRadio) customRadio.checked = true;
        if (opticsCustom) opticsCustom.hidden = false;
      }
      refreshOptics();
    });
  }

  refreshOptics();

  /* =======================================================================
     Solver Execution & Quick Experience Scenarios
     ======================================================================= */
  function highlightActiveScenario(activeBtn) {
    [btnSeed, btnTetra3Preset, btnMountPreset, btnGlarePreset].forEach((b) => {
      if (!b) return;
      b.classList.toggle("is-active", b === activeBtn);
    });
  }

  async function postRun(body) {
    const isDataset = Boolean(body.image);
    const wide = bodyNeedsWideTable(body);
    const busy = isDataset
      ? "Đang trích xuất tâm sao và giải tư thế trên khung ảnh thực..."
      : body.focal_mm
        ? "Đang dựng khung sao theo hệ quang học tùy chỉnh..."
        : "Đang mô phỏng bầu trời sao và định hướng vệ tinh J2000...";
    setBusy(true, wide ? `${busy} (khởi tạo bảng góc rộng > 30,5°)` : busy);
    try {
      const data = await fetchJson(
        "/api/run",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        },
        wide ? 600000 : 120000
      );
      activateTab("tab-imagery");
      renderPayload(data);
    } catch (err) {
      if (statusEl) {
        statusEl.className = "status-banner err";
        statusEl.innerHTML = `<strong>Không thể thực thi:</strong> ${err.message || err}`;
      }
      if (kpiStatusBadge) {
        kpiStatusBadge.textContent = "ERROR";
        kpiStatusBadge.className = "kpi-badge status-pill LOST";
      }
      if (verdictEl) {
        verdictEl.textContent = "Lỗi xử lý";
        verdictEl.className = "verdict-pill FAIL";
      }
    } finally {
      setBusy(false);
    }
  }

  if (btnRun) {
    btnRun.addEventListener("click", () => {
      highlightActiveScenario(null);
      closeDrawer();
      postRun(gatherFormData());
    });
  }

  if (btnDrawerRun) {
    btnDrawerRun.addEventListener("click", () => {
      highlightActiveScenario(null);
      closeDrawer();
      postRun(gatherFormData());
    });
  }

  function resetStandardSimControls(seedVal, glareVal) {
    const modeFast = document.getElementById("mode-fast");
    if (modeFast) modeFast.checked = true;
    const opticsLocked = document.getElementById("optics-locked");
    if (opticsLocked) opticsLocked.checked = true;
    if (opticsCustom) opticsCustom.hidden = true;
    refreshOptics();
    if (seedInput) seedInput.value = seedVal;
    const catalogSelect = document.getElementById("catalog-select");
    if (catalogSelect) catalogSelect.value = "bsc5";
    const solverSelect = document.getElementById("solver-select");
    if (solverSelect) solverSelect.value = "svd";
    setCentroidBackend("classical");
    if (form) {
      if (form.omega) form.omega.value = "0.06";
      if (form.omega_axis) form.omega_axis.value = "y";
      if (form.exposure) form.exposure.value = "0.15";
      if (form.glare) form.glare.value = glareVal;
      if (form.sky_clutter) form.sky_clutter.value = "none";
    }
    if (falseStarsSlider) falseStarsSlider.value = "0";
    if (falseStarsVal) falseStarsVal.textContent = "0";
    const seedTabBtn = document.querySelector('.sub-tab-btn[data-target="target-seed"]');
    if (seedTabBtn) seedTabBtn.click();
    clearRadecFields();
    setCompare3dSource("annotated");
  }

  if (btnSeed) {
    btnSeed.addEventListener("click", () => {
      highlightActiveScenario(btnSeed);
      closeDrawer();
      resetStandardSimControls(42, "none");
      postRun(gatherFormData());
    });
  }

  if (btnGlarePreset) {
    btnGlarePreset.addEventListener("click", () => {
      highlightActiveScenario(btnGlarePreset);
      closeDrawer();
      resetStandardSimControls(11, "sun_strong");
      postRun(gatherFormData());
    });
  }

  if (btnMountPreset) {
    btnMountPreset.addEventListener("click", () => {
      highlightActiveScenario(btnMountPreset);
      closeDrawer();
      const opticsLocked = document.getElementById("optics-locked");
      if (opticsLocked) opticsLocked.checked = true;
      if (opticsCustom) opticsCustom.hidden = true;
      refreshOptics();
      const catalogSelect = document.getElementById("catalog-select");
      if (catalogSelect) catalogSelect.value = "bsc5";
      const solverSelect = document.getElementById("solver-select");
      if (solverSelect) solverSelect.value = "svd";
      setCentroidBackend("cnn");
      if (form && form.glare) form.glare.value = "none";
      if (form && form.sky_clutter) form.sky_clutter.value = "none";
      if (falseStarsSlider) falseStarsSlider.value = "0";
      if (falseStarsVal) falseStarsVal.textContent = "0";
      clearRadecFields();
      setCompare3dSource("annotated");
      const body = gatherFormData();
      body.image = "uploads/mount_st_helens_1.png";
      body.focal_mm = 4.2;
      body.pixel_um = 4.1;
      body.centroid_backend = "cnn";
      postRun(body);
    });
  }

  function runTetra3RealSky() {
    highlightActiveScenario(btnTetra3Preset);
    closeDrawer();
    const opticsLocked = document.getElementById("optics-locked");
    if (opticsLocked) opticsLocked.checked = true;
    if (opticsCustom) opticsCustom.hidden = true;
    refreshOptics();
    const catalogSelect = document.getElementById("catalog-select");
    if (catalogSelect) catalogSelect.value = "bsc5";
    const solverSelect = document.getElementById("solver-select");
    if (solverSelect) solverSelect.value = "svd";
    setCentroidBackend("classical");
    if (form && form.glare) form.glare.value = "none";
    if (form && form.sky_clutter) form.sky_clutter.value = "none";
    if (falseStarsSlider) falseStarsSlider.value = "0";
    if (falseStarsVal) falseStarsVal.textContent = "0";
    clearRadecFields();
    setCompare3dSource("annotated");
    const body = gatherFormData();
    body.image = "tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff";
    body.focal_mm = 35.2911;
    body.pixel_um = 6.9;
    postRun(body);
  }

  if (btnTetra3Preset) {
    btnTetra3Preset.addEventListener("click", runTetra3RealSky);
  }
  if (btnWelcomeRun) {
    btnWelcomeRun.addEventListener("click", runTetra3RealSky);
  }

  if (btnRadec) {
    btnRadec.addEventListener("click", () => {
      const paste = String(radecPaste?.value || "").trim();
      const ra = String(raHms?.value || "").trim();
      const dec = String(decDms?.value || "").trim();
      if (!paste && (!ra || !dec)) {
        if (statusEl) {
          statusEl.className = "status-banner err";
          statusEl.innerHTML = "<strong>Thiếu tọa độ:</strong> Hãy nhập đủ cả RA và Dec trước khi ngắm.";
        }
        const radecTabBtn = document.querySelector('.sub-tab-btn[data-target="target-radec"]');
        if (radecTabBtn) radecTabBtn.click();
        return;
      }
      if (form && form.glare) form.glare.value = "none";
      if (falseStarsSlider) falseStarsSlider.value = "0";
      if (falseStarsVal) falseStarsVal.textContent = "0";
      setCentroidBackend("classical");
      highlightActiveScenario(null);
      closeDrawer();
      postRun(gatherFormData());
    });
  }

  if (btnLoad && frameSelect) {
    btnLoad.addEventListener("click", () => {
      const file = frameSelect.value;
      if (!file) return;
      const opticsLocked = document.getElementById("optics-locked");
      if (opticsLocked) opticsLocked.checked = true;
      if (opticsCustom) opticsCustom.hidden = true;
      refreshOptics();
      if (form && form.glare) form.glare.value = "none";
      if (form && form.sky_clutter) form.sky_clutter.value = "none";
      if (falseStarsSlider) falseStarsSlider.value = "0";
      if (falseStarsVal) falseStarsVal.textContent = "0";
      setCentroidBackend("classical");
      highlightActiveScenario(null);
      closeDrawer();
      postRun({ ...gatherFormData(), image: file });
    });
  }

  function refreshLocalHint() {
    if (!localFileHint) return;
    const imgName = localImage && localImage.files && localImage.files[0] ? localImage.files[0].name : "";
    const jsName = localSidecar && localSidecar.files && localSidecar.files[0] ? localSidecar.files[0].name : "";
    if (!imgName) {
      localFileHint.textContent =
        "Ưu tiên ảnh TIFF/PNG không nén. Với ảnh chụp từ máy ảnh riêng, hãy nhập tiêu cự và cỡ điểm ảnh ở mục Quang học bên dưới.";
      return;
    }
    localFileHint.textContent = jsName
      ? `Đã chọn ảnh: ${imgName} · Nhãn: ${jsName}`
      : `Đã chọn ảnh: ${imgName}`;
  }

  if (localImage) localImage.addEventListener("change", refreshLocalHint);
  if (localSidecar) localSidecar.addEventListener("change", refreshLocalHint);

  if (btnUpload) {
    btnUpload.addEventListener("click", async () => {
      if (!localImage || !localImage.files || !localImage.files[0]) {
        if (detailsDataset) detailsDataset.open = true;
        if (statusEl) {
          statusEl.className = "status-banner err";
          statusEl.innerHTML = "<strong>Chưa chọn tệp ảnh:</strong> Hãy chọn tệp TIFF, PNG hoặc JPEG từ máy tính.";
        }
        return;
      }
      const fd = new FormData();
      fd.append("image", localImage.files[0]);
      if (localSidecar && localSidecar.files && localSidecar.files[0]) {
        fd.append("sidecar", localSidecar.files[0]);
      }
      const body = gatherFormData();
      Object.entries(body).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== "") fd.append(k, String(v));
      });
      const customUpload = body.focal_mm != null || body.pixel_um != null || body.image_width != null;
      highlightActiveScenario(null);
      closeDrawer();
      setBusy(
        true,
        customUpload
          ? "Đang tải tệp ảnh và giải tư thế theo cấu hình quang học tùy chỉnh..."
          : "Đang tải tệp ảnh lên và nhận diện bầu trời sao..."
      );
      try {
        const data = await fetchJson("/api/run-upload", { method: "POST", body: fd }, customUpload ? 600000 : 180000);
        activateTab("tab-imagery");
        renderPayload(data);
      } catch (err) {
        if (statusEl) {
          statusEl.className = "status-banner err";
          statusEl.innerHTML = `<strong>Không thể xử lý tệp tải lên:</strong> ${err.message || err}`;
        }
        if (kpiStatusBadge) {
          kpiStatusBadge.textContent = "ERROR";
          kpiStatusBadge.className = "kpi-badge status-pill LOST";
        }
        if (verdictEl) {
          verdictEl.textContent = "Lỗi xử lý";
          verdictEl.className = "verdict-pill FAIL";
        }
      } finally {
        setBusy(false);
      }
    });
  }

  // Initialize full-screen 3D Earth-orbit & real 5,023-star J2000 sky immediately
  window.StarTrackerOrbit3D?.init(orbit3dRoot);
})();
