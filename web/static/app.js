/* ==========================================================================
   STAR TRACKER GROUND STATION LOGIC
   Modern Interactive ADCS Testbench Client Script
   ========================================================================== */

(function () {
  "use strict";

  // Elements
  const form = document.getElementById("run-form");
  const btnRun = document.getElementById("btn-run");
  const btnSeed = document.getElementById("btn-seed42");
  const btnGlarePreset = document.getElementById("btn-glare-preset");
  const btnMountPreset = document.getElementById("btn-mount-preset");
  const btnRadec = document.getElementById("btn-radec");
  const btnLoad = document.getElementById("btn-load");
  const btnUpload = document.getElementById("btn-upload");
  const localImage = document.getElementById("local-image");
  const localSidecar = document.getElementById("local-sidecar");
  const localFileHint = document.getElementById("local-file-hint");
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
  const falseStarsSlider = document.getElementById("false-stars-slider");
  const falseStarsVal = document.getElementById("false-stars-val");

  // KPI Elements
  const kpiAttErrVal = document.getElementById("kpi-att-err-val");
  const kpiAttErrBadge = document.getElementById("kpi-att-err-badge");
  const kpiAttErrSub = document.getElementById("kpi-att-err-sub");
  const kpiTimeVal = document.getElementById("kpi-time-val");
  const kpiTimeBreakdown = document.getElementById("kpi-time-breakdown");
  const kpiStarsVal = document.getElementById("kpi-stars-val");
  const kpiStarPct = document.getElementById("kpi-star-pct");
  const kpiBoresightVal = document.getElementById("kpi-boresight-val");
  const kpiBoresightSub = document.getElementById("kpi-boresight-sub");

  // Downlink Elements
  const downlinkHexDisplay = document.getElementById("downlink-hex-display");
  const decodeQ0 = document.getElementById("decode-q0");
  const decodeQ1 = document.getElementById("decode-q1");
  const decodeQ2 = document.getElementById("decode-q2");
  const decodeQ3 = document.getElementById("decode-q3");

  // Timing Elements
  const barCentroid = document.getElementById("bar-centroid");
  const barId = document.getElementById("bar-id");
  const barWahba = document.getElementById("bar-wahba");
  const tCentroid = document.getElementById("t-centroid");
  const tId = document.getElementById("t-id");
  const tWahba = document.getElementById("t-wahba");
  const tTotal = document.getElementById("t-total");

  // Tables & Content Elements
  const compareBody = document.querySelector("#compare-table tbody");
  const metaDl = document.getElementById("meta-dl");
  const fovBody = document.querySelector("#fov-table tbody");
  const idBody = document.querySelector("#id-table tbody");
  const fovTitle = document.getElementById("fov-title");
  const idTitle = document.getElementById("id-title");
  const fovCount = document.getElementById("fov-count");
  const idCount = document.getElementById("id-count");
  const starSearchInput = document.getElementById("star-search-input");

  // Images & Viewports
  const imgIn = document.getElementById("input-img");
  const imgOut = document.getElementById("output-img");
  const imgOutLarge = document.getElementById("output-img-large");
  const imgHud = document.getElementById("hud-img");
  const slotIn = document.getElementById("slot-in");
  const slotOut = document.getElementById("slot-out");
  const capIn = document.getElementById("cap-in");
  const capOut = document.getElementById("cap-out");
  const shaIntegrityText = document.getElementById("sha-integrity-text");

  // Lightbox Modal
  const imageModal = document.getElementById("image-modal");
  const modalImg = document.getElementById("modal-img");
  const modalTitle = document.getElementById("modal-title");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const btnZoomIn = document.getElementById("btn-zoom-in");
  const btnZoomOut = document.getElementById("btn-zoom-out");
  const btnZoomReset = document.getElementById("btn-zoom-reset");
  let modalZoomLevel = 1.0;

  // Coordinate / Stellarium Parsing State
  const radecConvertedEl = document.getElementById("radec-converted");
  const radecPaste = document.getElementById("radec-paste");
  const raHms = document.getElementById("ra-hms");
  const decDms = document.getElementById("dec-dms");
  const raDecimal = document.getElementById("ra-decimal");
  const decDecimal = document.getElementById("dec-decimal");
  const btnClearRadec = document.getElementById("btn-clear-radec");
  const presetIndicator = document.getElementById("preset-active-indicator");
  let activePointHr = null;
  let activePointingMode = "target-seed";
  let radecSyncing = false;
  let radecTimer = 0;

  if (form) {
    form.addEventListener("submit", (ev) => ev.preventDefault());
  }

  // Stored rows for star search filter
  let storedFovRows = [];
  let storedIdRows = [];

  // =========================================================================
  // HELPER FORMATTING FUNCTIONS
  // =========================================================================
  function fmt(v, digits = 5) {
    if (v === null || v === undefined || Number.isNaN(v)) return "n/a";
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
    if (typeof d === "string") return "count-pill highlight";
    if (typeof d !== "number" || Number.isNaN(d)) return "count-pill delta-na";
    if (row.unit === "arcsec") return Math.abs(d) < (row.limit_arcsec || 10) ? "count-pill highlight" : "count-pill delta-warn";
    if (row.unit === "deg") return Math.abs(d) * 3600 < 10 ? "count-pill highlight" : "count-pill delta-warn";
    if (String(row.param || "").startsWith("q") && Math.abs(d) < 1e-4) return "count-pill highlight";
    return "count-pill";
  }

  let abortCtrl = null;

  function setBusy(on, msg) {
    [btnRun, btnSeed, btnGlarePreset, btnLoad, btnRadec, btnUpload].forEach((b) => {
      if (!b) return;
      b.disabled = on;
      b.classList.toggle("busy", on);
    });
    if (on) {
      statusEl.className = "status-banner";
      statusEl.innerHTML = `⏳ <strong>Đang xử lý:</strong> ${msg}`;
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
        throw new Error("Quá thời gian chờ hoặc request bị hủy. F5 rồi bấm lại khi engine rảnh.");
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  // =========================================================================
  // TAB NAVIGATION (MAIN WORKSPACE & POINTING SUB-TABS)
  // =========================================================================
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach((p) => {
        p.classList.remove("active");
        p.hidden = true;
      });
      btn.classList.add("active");
      const target = document.getElementById(btn.getAttribute("data-tab"));
      if (target) {
        target.hidden = false;
        target.classList.add("active");
        target.scrollTop = 0;
      }
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

      // Reset preset if leaving preset tab
      if (targetId !== "target-presets" && activePointHr !== null) {
        activePointHr = null;
        document.querySelectorAll(".preset-chip").forEach((c) => c.classList.remove("active"));
        if (presetIndicator) {
          presetIndicator.textContent = "Chưa chọn preset sao";
          presetIndicator.className = "preset-indicator muted";
        }
      }
    });
  });

  // Hybrid policy: sim / catalog / dataset → classical; mountain photo → CNN.
  // Manual radio stays editable so a judge can override after a preset.
  function setCentroidBackend(mode) {
    const classical = document.getElementById("centroid-classical");
    const cnn = document.getElementById("centroid-cnn");
    if (mode === "cnn") {
      if (cnn) cnn.checked = true;
    } else if (classical) {
      classical.checked = true;
    }
  }

  // False stars slider listener
  if (falseStarsSlider && falseStarsVal) {
    falseStarsSlider.addEventListener("input", () => {
      falseStarsVal.textContent = falseStarsSlider.value;
    });
  }

  // Randomize seed button
  if (btnRndSeed && seedInput) {
    btnRndSeed.addEventListener("click", () => {
      seedInput.value = Math.floor(Math.random() * 100000);
      setCentroidBackend("classical");
      postRun(gatherFormData());
    });
  }

  // Star presets click handlers (Sirius / Sao chuẩn / … → classical)
  document.querySelectorAll(".preset-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".preset-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      const hr = parseInt(chip.getAttribute("data-hr"), 10);
      const name = chip.getAttribute("data-name");
      activePointHr = hr;
      if (presetIndicator) {
        presetIndicator.textContent = `🎯 Đã chọn: ${name} (HR ${hr})`;
        presetIndicator.className = "preset-indicator active";
      }
      clearRadecFields();
      setCentroidBackend("classical");
      postRun(gatherFormData());
    });
  });

  // Clear RA/Dec button
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

  // =========================================================================
  // STELLARIUM RA / DEC CONVERSION & BIDIRECTIONAL SYNC
  // =========================================================================
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
    const t = String(text || "").replace(/\u00a0/g, " ").replace(/[−–]/g, "-").trim();
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
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!data.ok) {
        setRadecSummary(data.error || "Không đọc được tọa độ", "", true);
        return;
      }
      radecSyncing = true;
      // A one-line paste may fill the two boxes. Never rewrite the box being typed.
      if (source === radecPaste) {
        if (raHms && document.activeElement !== raHms) raHms.value = data.ra_hms;
        if (decDms && document.activeElement !== decDms) decDms.value = data.dec_dms;
      }
      if (raDecimal) raDecimal.value = Number(data.ra_deg).toFixed(5);
      if (decDecimal) decDecimal.value = (data.dec_deg >= 0 ? "+" : "") + Number(data.dec_deg).toFixed(5);
      radecSyncing = false;
      setRadecSummary(`${data.ra_hms} (${Number(data.ra_deg).toFixed(4)}°)`, `${data.dec_dms} (${Number(data.dec_deg).toFixed(4)}°)`, false);
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
      radecTimer = setTimeout(syncRadecWithApi, 450);
    };
    el.addEventListener("input", queue);
    el.addEventListener("compositionend", () => queue(null));
  });

  // =========================================================================
  // VIEW MODE SWITCHER (SPLIT, OUTPUT, HUD)
  // =========================================================================
  document.querySelectorAll(".view-mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".view-mode-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const mode = btn.getAttribute("data-mode");

      const viewSplit = document.getElementById("view-split");
      const viewOutput = document.getElementById("view-output");
      const viewHud = document.getElementById("view-hud");

      if (viewSplit) viewSplit.hidden = mode !== "split";
      if (viewOutput) viewOutput.hidden = mode !== "output";
      if (viewHud) viewHud.hidden = mode !== "hud";
    });
  });

  // =========================================================================
  // LIGHTBOX MODAL (IMAGE INSPECTION)
  // =========================================================================
  function openLightbox(src, title) {
    if (!imageModal || !modalImg) return;
    modalImg.src = src;
    modalTitle.textContent = title || "Chi Tiết Ảnh Quang Học";
    modalZoomLevel = 1.0;
    modalImg.style.transform = `scale(1)`;
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
    if (e.key === "Escape" && imageModal && !imageModal.hidden) {
      closeLightbox();
    }
  });

  if (btnZoomIn) {
    btnZoomIn.addEventListener("click", () => {
      modalZoomLevel = Math.min(modalZoomLevel + 0.3, 4.0);
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
      if (modalImg) modalImg.style.transform = `scale(1)`;
    });
  }

  document.querySelectorAll(".btn-inspect").forEach((btn) => {
    btn.addEventListener("click", () => {
      const imgId = btn.getAttribute("data-img");
      const targetImg = document.getElementById(imgId);
      if (targetImg && targetImg.src && !targetImg.hidden) {
        openLightbox(targetImg.src, targetImg.alt || "Khung Hình Star Tracker");
      }
    });
  });

  [imgIn, imgOut, imgOutLarge, imgHud].forEach((img) => {
    if (!img) return;
    img.addEventListener("click", () => {
      if (img.src && !img.hidden) {
        openLightbox(img.src, img.alt || "Khung Hình Star Tracker");
      }
    });
  });

  // =========================================================================
  // GATHER FORM DATA FOR EXECUTION
  // =========================================================================
  function gatherFormData() {
    const rawData = Object.fromEntries(new FormData(form).entries());
    const payload = {
      mode: String(rawData.mode || "fast"),
      seed: Number(rawData.seed || 42),
      catalog: String(rawData.catalog || "bsc5"),
      solver: String(rawData.solver || "svd"),
      centroid_backend: String(rawData.centroid_backend || "classical"),
      omega: Number(rawData.omega || 0.06),
      omega_axis: String(rawData.omega_axis || "y"),
      exposure: Number(rawData.exposure || 0.15),
      glare: String(rawData.glare || "none"),
      sky_clutter: String(rawData.sky_clutter || "none"),
      false_stars: Number(rawData.false_stars || 0),
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

    // Pointing logic
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

  // =========================================================================
  // STAR TABLES & FILTERING
  // =========================================================================
  function renderStarTable(tbody, countBadge, rows, query = "") {
    tbody.innerHTML = "";
    if (!rows || !rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty">(Không có sao)</td></tr>';
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
      tbody.innerHTML = '<tr><td colspan="5" class="empty">Không tìm thấy sao khớp bộ lọc</td></tr>';
      if (countBadge) countBadge.textContent = `0 / ${rows.length} sao`;
      return;
    }

    for (const r of filtered) {
      const tr = document.createElement("tr");
      const name = r.iau_name || (r.designation ? r.designation : "—");
      const hasName = Boolean(r.iau_name);
      tr.innerHTML = `
        <td><strong>${r.id_scheme || "HR"} ${r.id}</strong></td>
        <td><span class="count-pill">V ${fmt(r.mag, 2)}</span></td>
        <td class="${hasName ? "named" : ""}">${hasName ? "⭐ " + name : "—"}</td>
        <td>${fmt(r.u_px, 1)}</td>
        <td>${fmt(r.v_px, 1)}</td>
      `;
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

  // =========================================================================
  // RENDER COMPLETE TELEMETRY PAYLOAD
  // =========================================================================
  function renderPayload(payload) {
    const metrics = payload.metrics || {};
    const verdict = metrics.verdict || (payload.success ? "SOLVED" : "FAIL");
    const attErr = metrics.attitude_error_arcsec;

    // 1. Update KPI Ribbon
    if (verdictEl) {
      verdictEl.textContent = verdict;
      verdictEl.className = `verdict-pill ${verdict}`;
    }

    if (kpiAttErrVal) {
      if (attErr !== null && attErr !== undefined) {
        kpiAttErrVal.textContent = `${attErr.toFixed(3)}″`;
        const lim = Number(metrics.limit_arcsec);
        const gate = Number.isFinite(lim) ? lim : 10.0;
        const pass = attErr < gate;
        kpiAttErrVal.style.color = pass ? "var(--emerald)" : "var(--amber)";
        kpiAttErrBadge.textContent = pass ? `PASS (< ${gate}″)` : `FAIL (≥ ${gate}″)`;
        kpiAttErrBadge.style.color = pass ? "var(--emerald)" : "var(--amber)";
      } else {
        kpiAttErrVal.textContent = "--";
        kpiAttErrBadge.textContent = "n/a";
      }
    }

    const t = payload.timing_ms || {};
    if (kpiTimeVal) {
      kpiTimeVal.textContent = `${fmt(t.total_pipeline_ms, 1)} ms`;
      kpiTimeBreakdown.textContent = `Centroid: ${fmt(t.centroiding_ms, 1)} ms | ID: ${fmt(t.identification_ms, 1)} ms | Wahba: ${fmt(t.attitude_ms, 2)} ms`;
    }

    const fov = payload.stars_in_fov || [];
    const ident = payload.identified_stars || [];
    storedFovRows = fov;
    storedIdRows = ident;

    if (kpiStarsVal) {
      const nDet = metrics.n_detected ?? fov.length;
      const nMatched = metrics.n_matched ?? ident.length;
      kpiStarsVal.textContent = `${nMatched} / ${nDet}`;
      const pct = nDet > 0 ? Math.round((nMatched / nDet) * 100) : 0;
      kpiStarPct.textContent = `${pct}% MATCH`;
    }

    const boresight = payload.boresight_est || payload.boresight_gt;
    if (kpiBoresightVal && boresight) {
      kpiBoresightVal.textContent = `RA ${fmt(boresight.ra_deg, 2)}° | Dec ${fmt(boresight.dec_deg, 2)}°`;
      kpiBoresightSub.textContent = `${boresight.ra_hms || ""}  ${boresight.dec_dms || ""}`;
    }

    // 2. Downlink Telemetry Hex & Float32 Inspector
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
    }

    // 3. Timing Meter Bar
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

    // 4. Comparison Table
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

    // 5. Metadata List
    if (metaDl) {
      const cam = payload.camera || {};
      metaDl.innerHTML = `
        <dt>Nguồn ảnh</dt><dd>${payload.source === "simulator" ? "SkySimulator (mô phỏng máy ảnh demo)" : payload.source_image}</dd>
        <dt>Quang học giải</dt><dd>${cam.optics === "custom" ? "Máy nhập" : "Kính khóa"} · f ${fmt(cam.focal_mm, 3)} mm · pixel ${fmt(cam.pixel_um, 3)} µm · ${cam.width}×${cam.height} · fx ${fmt(cam.fx_px, 1)} px · ${fmt(cam.ifov_arcsec, 2)}″/px · FOV ${Array.isArray(cam.fov_deg) ? cam.fov_deg.map((x) => Number(x).toFixed(2)).join("×") : ""}° · chéo ${fmt(cam.fov_diag_deg, 2)}° · dung sai ${fmt(cam.match_tol_arcsec, 2)}″</dd>
        <dt>Bảng góc</dt><dd>${(payload.angle_table && payload.angle_table.note) || ""}</dd>
        <dt>Danh mục sao bay</dt><dd>${payload.catalog_source} (${payload.n_catalog} sao J2000, V ≤ 6.0)</dd>
        <dt>Gói downlink</dt><dd><code>${payload.downlink_hex}</code> (${payload.downlink_bytes} byte float32)</dd>
        <dt>q_GT (Thực)</dt><dd>${payload.q_gt_text}</dd>
        <dt>q_est (Đo được)</dt><dd>${payload.q_est_text}</dd>
      `;
    }

    // 6. Starfield Images
    const tstamp = Date.now();
    const inUrl = (payload.input_url || "/output/demo_input.png") + `?t=${tstamp}`;
    const outUrl = (payload.output_url || "/output/demo_output.png") + `?t=${tstamp}`;
    const hudUrl = (payload.image_url || "/output/demo_result.png") + `?t=${tstamp}`;

    if (imgIn) {
      imgIn.hidden = false;
      imgIn.src = inUrl;
    }
    if (imgOut) {
      imgOut.hidden = false;
      imgOut.src = outUrl;
    }
    if (imgOutLarge) {
      imgOutLarge.src = outUrl;
    }
    if (imgHud) {
      imgHud.src = hudUrl;
    }

    if (slotIn) slotIn.classList.add("hidden");
    if (slotOut) slotOut.classList.add("hidden");

    const st = payload.input_stats || {};
    const sha = st.sha256_12 || "?";
    if (capIn) capIn.textContent = `${st.width || "?"}×${st.height || "?"} ${st.dtype || ""} · DN ${st.dn_min}–${st.dn_max} · sha ${sha}`;
    if (capOut) capOut.textContent = `Overlay Pyramid + Wahba · Cùng SHA ${sha}`;
    if (shaIntegrityText) shaIntegrityText.textContent = `SHA-256: ${sha} (Đồng nhất mảng pixel)`;

    // 7. Star Tables
    const currentQ = starSearchInput ? starSearchInput.value : "";
    renderStarTable(fovBody, fovCount, fov, currentQ);
    renderStarTable(idBody, idCount, ident, currentQ);

    // 8. Status completion message (FAIL has attitude_error_arcsec = null)
    const attOk = typeof attErr === "number" && Number.isFinite(attErr);
    const attHtml = attOk ? `${attErr.toFixed(3)}″` : "n/a";
    const ingest = payload.ingest_note ? `<br>${payload.ingest_note}` : "";
    const reqCent = String(payload.centroid_backend || "classical");
    const usedCent = String(payload.centroid_detector || reqCent);
    const fellBack = Boolean(payload.centroid_fallback) || (
      reqCent !== "classical" && usedCent === "classical"
    );
    let centNote = "";
    if (reqCent !== "classical") {
      if (fellBack) {
        const why = payload.centroid_error ? ` (${payload.centroid_error})` : "";
        centNote = `<br>⚠️ Centroid: chọn CNN nhưng <strong>fallback CoG</strong>${why}. KPI/overlay là classical.`;
      } else {
        const nRaw = payload.centroid_n_raw;
        const nGate = payload.centroid_n_after_gate;
        const gateBit = (nRaw != null && nGate != null) ? ` · raw ${nRaw} → gate ${nGate}` : "";
        centNote = `<br>Centroid: <strong>CNN</strong> (${usedCent})${gateBit} — detect/ID theo CNN, không phải CoG.`;
      }
    }
    if (payload.success) {
      statusEl.className = fellBack ? "status-banner err" : "status-banner success";
      statusEl.innerHTML = `✅ <strong>Hoàn thành:</strong> Giải xong tư thế sau <strong>${fmt(t.total_pipeline_ms, 1)} ms</strong>. Sai số góc: <strong>${attHtml}</strong> (${verdict}). Detect ${metrics.n_detected ?? 0}, ID ${metrics.n_matched ?? 0}.${centNote}${ingest}`;
    } else {
      const why = payload.error || metrics.error || "Không giải được tư thế (sao trên nền trời chưa đủ sau khi mask lóa).";
      statusEl.className = "status-banner err";
      statusEl.innerHTML = `⚠️ <strong>${verdict}:</strong> ${why} Detect ${metrics.n_detected ?? 0}, ID ${metrics.n_matched ?? 0}. Sai số góc: ${attHtml}.${centNote}${ingest}`;
    }
    if (opticsReadout && payload.angle_table && payload.camera) {
      opticsReadout.className = "radec-status-card";
      opticsReadout.textContent = payload.angle_table.note || "";
    }
  }

  // =========================================================================
  // CAMERA PLATE SCALE
  // =========================================================================
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
    if (!body || body.focal_mm == null && body.pixel_um == null && body.image_width == null) {
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
    if (opticsCustom) opticsCustom.hidden = !opticsIsCustom();
    if (!opticsReadout) return;
    const geom = previewOptics();
    if (!geom) {
      opticsReadout.className = "radec-status-card err";
      opticsReadout.textContent = "Nhập tiêu cự (mm) và cạnh pixel (µm) là số dương.";
      return;
    }
    const tableLine = geom.dDeg <= TABLE_DEG
      ? "Chéo trường nhìn nằm trong bảng góc 30,5° có sẵn, không dựng lại."
      : `Chéo ${geom.dDeg.toFixed(2)}° rộng hơn 30,5°. Lần giải đầu dựng bảng tới ${geom.theta.toFixed(1)}° rồi lưu.`;
    const who = opticsIsCustom() ? "Máy nhập" : "Kính demo";
    opticsReadout.className = "radec-status-card";
    opticsReadout.textContent =
      `${who}: fx ${geom.fx.toFixed(1)} px · ${geom.ifov.toFixed(2)}″/px · FOV ${geom.hDeg.toFixed(2)}°×${geom.vDeg.toFixed(2)}° · chéo ${geom.dDeg.toFixed(2)}°. Dung sai khoảng ${geom.tol.toFixed(2)}″. ${tableLine} Tra một góc vẫn là tìm nhị phân.`;
  }

  function applyModeFrameIfPreset() {
    if (!opticsIsCustom() || !focalInput || !pixelInput) return;
    const focal = Number(focalInput.value);
    const pixel = Number(pixelInput.value);
    const sizeEmpty = !(widthInput && String(widthInput.value || "").trim())
      && !(heightInput && String(heightInput.value || "").trim());
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
      }
      refreshOptics();
    });
  }
  refreshOptics();

  // =========================================================================
  // ASYNC API RUNNER
  // =========================================================================
  async function postRun(body) {
    const isDataset = Boolean(body.image);
    const wide = bodyNeedsWideTable(body);
    const busy = isDataset
      ? "Đang đọc ảnh và giải theo tiêu cự, cạnh pixel đã chọn..."
      : body.focal_mm
        ? "Đang kết xuất theo quang học đã nhập và giải tư thế..."
        : "Đang kết xuất bầu trời sao theo camera demo và giải tư thế...";
    setBusy(true, wide ? `${busy} Trường nhìn rộng hơn 30,5°: lần đầu dựng bảng góc có thể mất vài phút.` : busy);
    try {
      const data = await fetchJson("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }, wide ? 600000 : 120000);
      renderPayload(data);
      const imgTab = document.querySelector('.tab-btn[data-tab="tab-imagery"]');
      if (imgTab) imgTab.click();
    } catch (err) {
      statusEl.className = "status-banner err";
      statusEl.innerHTML = `❌ <strong>Lỗi:</strong> ${err.message || err}`;
      if (verdictEl) {
        verdictEl.textContent = "FAIL";
        verdictEl.className = "verdict-pill FAIL";
      }
    } finally {
      setBusy(false);
    }
  }

  // =========================================================================
  // ACTION BUTTON LISTENERS
  // =========================================================================
  if (btnRun) {
    btnRun.addEventListener("click", () => {
      postRun(gatherFormData());
    });
  }

  if (btnSeed) {
    btnSeed.addEventListener("click", () => {
      // Reset to fast mode benchmark seed 42 → classical (hybrid policy)
      const modeFast = document.getElementById("mode-fast");
      if (modeFast) modeFast.checked = true;
      const opticsLocked = document.getElementById("optics-locked");
      if (opticsLocked) opticsLocked.checked = true;
      if (opticsCustom) opticsCustom.hidden = true;
      refreshOptics();
      if (seedInput) seedInput.value = 42;
      const catalogSelect = document.getElementById("catalog-select");
      if (catalogSelect) catalogSelect.value = "bsc5";
      const solverSelect = document.getElementById("solver-select");
      if (solverSelect) solverSelect.value = "svd";
      setCentroidBackend("classical");
      form.omega.value = "0.06";
      form.omega_axis.value = "y";
      form.exposure.value = "0.15";
      form.glare.value = "none";
      if (form.sky_clutter) form.sky_clutter.value = "none";
      if (falseStarsSlider) falseStarsSlider.value = "0";
      if (falseStarsVal) falseStarsVal.textContent = "0";

      // Switch sub-tab to Seed
      const seedTabBtn = document.querySelector('.sub-tab-btn[data-target="target-seed"]');
      if (seedTabBtn) seedTabBtn.click();
      clearRadecFields();

      postRun(gatherFormData());
    });
  }

  if (btnGlarePreset) {
    btnGlarePreset.addEventListener("click", () => {
      const modeFast = document.getElementById("mode-fast");
      if (modeFast) modeFast.checked = true;
      const opticsLocked = document.getElementById("optics-locked");
      if (opticsLocked) opticsLocked.checked = true;
      if (opticsCustom) opticsCustom.hidden = true;
      refreshOptics();
      // Seed khớp bộ so sánh glare (scripts/benchmark_centroid_cnn_glare.py --seed 11)
      if (seedInput) seedInput.value = 11;
      const catalogSelect = document.getElementById("catalog-select");
      if (catalogSelect) catalogSelect.value = "bsc5";
      const solverSelect = document.getElementById("solver-select");
      if (solverSelect) solverSelect.value = "svd";
      setCentroidBackend("classical");
      form.omega.value = "0.06";
      form.omega_axis.value = "y";
      form.exposure.value = "0.15";
      form.glare.value = "sun_strong";
      if (form.sky_clutter) form.sky_clutter.value = "none";
      if (falseStarsSlider) falseStarsSlider.value = "0";
      if (falseStarsVal) falseStarsVal.textContent = "0";
      const seedTabBtn = document.querySelector('.sub-tab-btn[data-target="target-seed"]');
      if (seedTabBtn) seedTabBtn.click();
      clearRadecFields();
      // Sim/glare → classical; judge may still flip the radio manually.
      statusEl.className = "status-banner";
      statusEl.innerHTML = "☀ Preset lóa mạnh: glare=sun_strong · seed 11 · Centroid cổ điển. Radio vẫn đổi tay được.";
      postRun(gatherFormData());
    });
  }

  if (btnMountPreset) {
    btnMountPreset.addEventListener("click", () => {
      const customRadio = document.getElementById("optics-custom-radio");
      if (customRadio) customRadio.checked = true;
      if (opticsCustom) opticsCustom.hidden = false;
      if (opticsPreset) opticsPreset.value = "mount_lost";
      if (focalInput) focalInput.value = "4.2";
      if (pixelInput) pixelInput.value = "4.1";
      if (widthInput) widthInput.value = "1024";
      if (heightInput) heightInput.value = "1024";
      refreshOptics();
      const catalogSelect = document.getElementById("catalog-select");
      if (catalogSelect) catalogSelect.value = "bsc5";
      const solverSelect = document.getElementById("solver-select");
      if (solverSelect) solverSelect.value = "svd";
      setCentroidBackend("cnn");
      form.glare.value = "none";
      if (form.sky_clutter) form.sky_clutter.value = "none";
      if (falseStarsSlider) falseStarsSlider.value = "0";
      if (falseStarsVal) falseStarsVal.textContent = "0";
      const datasetTab = document.querySelector('.sub-tab-btn[data-target="target-dataset"]');
      if (datasetTab) datasetTab.click();
      clearRadecFields();
      statusEl.className = "status-banner";
      statusEl.innerHTML =
        "🏔 Ảnh núi thật (LOST): f=4,2 mm · pixel 4,1 µm · 1024×1024 · CNN (cấp 6+). " +
        "Radio vẫn đổi tay được để so CoG. Overlay đo sẵn: mount_st_helens_cog_vs_cnn.png";
      const body = gatherFormData();
      body.image = "uploads/mount_st_helens_1.png";
      body.focal_mm = 4.2;
      body.pixel_um = 4.1;
      body.centroid_backend = "cnn";
      postRun(body);
    });
  }

  if (btnRadec) {
    btnRadec.addEventListener("click", () => {
      const paste = String(radecPaste?.value || "").trim();
      const ra = String(raHms?.value || "").trim();
      const dec = String(decDms?.value || "").trim();
      if (!paste && (!ra || !dec)) {
        statusEl.className = "status-banner err";
        statusEl.innerHTML = "⚠️ <strong>Thiếu tọa độ:</strong> Hãy dán Stellarium hoặc nhập RA & Dec trước khi bấm.";
        const radecTabBtn = document.querySelector('.sub-tab-btn[data-target="target-radec"]');
        if (radecTabBtn) radecTabBtn.click();
        return;
      }
      form.glare.value = "none";
      if (falseStarsSlider) falseStarsSlider.value = "0";
      if (falseStarsVal) falseStarsVal.textContent = "0";
      setCentroidBackend("classical");
      postRun(gatherFormData());
    });
  }

  if (btnLoad && frameSelect) {
    btnLoad.addEventListener("click", () => {
      const file = frameSelect.value;
      if (!file) return;
      setCentroidBackend("classical");
      postRun({ ...gatherFormData(), image: file });
    });
  }

  function refreshLocalHint() {
    if (!localFileHint) return;
    const imgName = localImage && localImage.files && localImage.files[0] ? localImage.files[0].name : "";
    const jsName = localSidecar && localSidecar.files && localSidecar.files[0] ? localSidecar.files[0].name : "";
    if (!imgName) {
      localFileHint.textContent = "TIFF hoặc PNG một kênh. Máy khác cần tiêu cự thật và cạnh pixel của file. JPEG giải được nhưng tâm sao kém hơn.";
      return;
    }
    localFileHint.textContent = jsName ? `Ảnh: ${imgName} · Nhãn: ${jsName}` : `Ảnh: ${imgName} · chưa có JSON (sẽ tìm sidecar dataset nếu trùng tên)`;
  }

  if (localImage) localImage.addEventListener("change", refreshLocalHint);
  if (localSidecar) localSidecar.addEventListener("change", refreshLocalHint);

  if (btnUpload) {
    btnUpload.addEventListener("click", async () => {
      if (!localImage || !localImage.files || !localImage.files[0]) {
        statusEl.className = "status-banner err";
        statusEl.innerHTML = "⚠️ <strong>Chưa chọn ảnh:</strong> Hãy chọn TIFF, PNG hoặc JPEG. Máy khác thì nhập tiêu cự và cạnh pixel.";
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
      setBusy(
        true,
        customUpload
          ? "Đang đọc ảnh theo tiêu cự và cạnh pixel đã nhập. Nếu chéo trường nhìn vượt 30,5°, lần đầu dựng bảng góc."
          : "Đang đọc ảnh máy, cộng nhiễu form (nếu có) và giải tư thế..."
      );
      try {
        const data = await fetchJson("/api/run-upload", { method: "POST", body: fd }, customUpload ? 600000 : 180000);
        renderPayload(data);
        const imgTab = document.querySelector('.tab-btn[data-tab="tab-imagery"]');
        if (imgTab) imgTab.click();
      } catch (err) {
        statusEl.className = "status-banner err";
        statusEl.innerHTML = `❌ <strong>Lỗi:</strong> ${err.message || err}`;
        if (verdictEl) {
          verdictEl.textContent = "FAIL";
          verdictEl.className = "verdict-pill FAIL";
        }
      } finally {
        setBusy(false);
      }
    });
  }

  // Do not auto-run on load: FULL 16 MP + matplotlib used to freeze the UI and hold the engine lock.
})();
