/* Star Tracker Web Application Controller */
(function () {
  "use strict";

  const form = document.getElementById("run-form");
  const btnRun = document.getElementById("btn-run");
  const btnSeed = document.getElementById("btn-seed42");
  const btnGlarePreset = document.getElementById("btn-glare-preset");
  const btnMountPreset = document.getElementById("btn-mount-preset");
  const btnTetra3Preset = document.getElementById("btn-tetra3-preset");
  const btnRadec = document.getElementById("btn-radec");
  const btnLoad = document.getElementById("btn-load");
  const btnUpload = document.getElementById("btn-upload");

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
  const compare3dImg = document.getElementById("compare3d-img");
  const slotCompare3d = document.getElementById("slot-compare3d");
  const capCompare3d = document.getElementById("cap-compare3d");
  const capOrbit3d = document.getElementById("cap-orbit3d");
  const orbit3dRoot = document.getElementById("orbit3d-root");

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
  let currentViewMode = "compare3d";
  let compare3dSource = "raw";
  let lastInUrl = "";
  let lastOutUrl = "";

  if (form) {
    form.addEventListener("submit", (ev) => ev.preventDefault());
  }

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
    [btnRun, btnSeed, btnGlarePreset, btnMountPreset, btnTetra3Preset, btnLoad, btnRadec, btnUpload].forEach((b) => {
      if (!b) return;
      b.disabled = on;
      b.classList.toggle("busy", on);
    });
    if (on && statusEl) {
      statusEl.className = "status-banner";
      statusEl.innerHTML = `<span class="busy-dot"></span><strong>Đang xử lý:</strong> ${msg}`;
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

  function setStageViewMode(mode) {
    currentViewMode = mode;
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
      requestAnimationFrame(() => window.StarTrackerOrbit3D?.resize());
    }
  }

  function syncCompare3dImage() {
    if (!compare3dImg) return;
    const url = compare3dSource === "annotated" ? lastOutUrl : lastInUrl;
    if (!url) return;
    compare3dImg.hidden = false;
    compare3dImg.src = url;
    compare3dImg.alt =
      compare3dSource === "annotated"
        ? "Ảnh nhận diện sao đối chiếu với bầu trời 3D"
        : "Ảnh gốc cảm biến đối chiếu với bầu trời 3D";
    if (slotCompare3d) slotCompare3d.classList.add("hidden");
  }

  function setCompare3dSource(srcKind) {
    compare3dSource = srcKind === "annotated" ? "annotated" : "raw";
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

  document.querySelectorAll(".view-mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-mode") || "compare3d";
      setStageViewMode(mode);
    });
  });

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach((p) => {
        p.classList.remove("active");
        p.hidden = true;
      });
      btn.classList.add("active");
      const tabId = btn.getAttribute("data-tab");
      const target = document.getElementById(tabId);
      if (target) {
        target.hidden = false;
        target.classList.add("active");
        target.scrollTop = 0;
      }
      if (tabId === "tab-imagery" && (currentViewMode === "compare3d" || currentViewMode === "orbit3d")) {
        requestAnimationFrame(() => window.StarTrackerOrbit3D?.resize());
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
      if (targetId !== "target-presets" && activePointHr !== null) {
        activePointHr = null;
        document.querySelectorAll(".preset-chip").forEach((c) => c.classList.remove("active"));
        if (presetIndicator) {
          presetIndicator.textContent = "Chưa chọn ngôi sao mục tiêu";
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
        presetIndicator.textContent = `Đang ngắm tâm kính vào ${name} (HR ${hr})`;
        presetIndicator.className = "preset-indicator active";
      }
      clearRadecFields();
      setCentroidBackend("classical");
      postRun(gatherFormData());
    });
  });

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
        body: JSON.stringify(body),
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
      radecTimer = setTimeout(syncRadecWithApi, 450);
    };
    el.addEventListener("input", queue);
    el.addEventListener("compositionend", () => queue(null));
  });

  function openLightbox(src, title) {
    if (!imageModal || !modalImg) return;
    modalImg.src = src;
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
      if (modalImg) modalImg.style.transform = "scale(1)";
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

  [compare3dImg, imgIn, imgOut, imgOutLarge, imgHud].forEach((img) => {
    if (!img) return;
    img.addEventListener("click", () => {
      if (img.src && !img.hidden) {
        openLightbox(img.src, img.alt || "Chi tiết Khung ảnh");
      }
    });
  });

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
      tr.innerHTML = `
        <td><strong>${r.id_scheme || "HR"} ${r.id}</strong></td>
        <td><span class="count-pill">V ${fmt(r.mag, 2)}</span></td>
        <td class="${hasName ? "named" : ""}">${hasName ? '<span class="star-dot"></span>' + name : "—"}</td>
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

  function renderPayload(payload) {
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

    const nDet = metrics.n_detected ?? mstats.n_detected ?? fov.length;
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

    if (kpiStatusBadge) {
      kpiStatusBadge.textContent = status;
      kpiStatusBadge.className = `kpi-badge status-pill ${status}`;
    }
    if (verdictEl) {
      const pillKey = status === "LOST" ? "LOST" : verdict;
      const pillLabel =
        status === "LOST"
          ? "Chưa khóa hướng"
          : pillKey === "PASS" || pillKey === "SOLVED"
            ? "Đã khóa hướng"
            : pillKey === "SOLVED_NO_GT"
              ? "Đã giải tư thế"
              : pillKey;
      verdictEl.textContent = pillLabel;
      verdictEl.className = `verdict-pill ${pillKey}`;
    }
    if (kpiVerdictSub) {
      if (status === "LOST") {
        const rc = rejectCode || "REJECTED";
        kpiVerdictSub.textContent = `Từ chối khóa: ${rc}`;
        kpiVerdictSub.title = `Lý do từ chối: ${rc}`;
      } else {
        kpiVerdictSub.textContent = `Phần dư RMS ${rmsTxt} · Cực đại ${maxTxt}`;
        kpiVerdictSub.title = kpiVerdictSub.textContent;
      }
    }

    if (kpiAttErrVal) {
      kpiAttErrVal.style.color = "";
      if (kpiAttErrBadge) kpiAttErrBadge.style.color = "";
      if (attOk) {
        kpiAttErrVal.textContent = `${attErr.toFixed(3)}″`;
        const lim = Number(metrics.limit_arcsec);
        const gate = Number.isFinite(lim) ? lim : 10.0;
        const pass = attErr < gate;
        if (kpiAttErrBadge) {
          kpiAttErrBadge.textContent = pass ? `< ${gate}″` : `≥ ${gate}″`;
        }
        if (kpiAttErrSub) {
          kpiAttErrSub.textContent = hasPrecRec
            ? `Tâm sao P ${precTxt} · R ${recTxt}`
            : "So với hướng chuẩn (Ground Truth)";
        }
      } else {
        kpiAttErrVal.textContent = "—";
        if (status === "LOST") {
          if (kpiAttErrBadge) kpiAttErrBadge.textContent = "LOST";
          if (kpiAttErrSub) kpiAttErrSub.textContent = "Không xuất tư thế khi chưa đủ sao khớp";
        } else {
          if (kpiAttErrBadge) kpiAttErrBadge.textContent = "Ảnh thực tế";
          if (kpiAttErrSub) kpiAttErrSub.textContent = `Phần dư khớp sao: RMS ${rmsTxt}`;
        }
      }
    }

    const t = payload.timing_ms || {};
    if (kpiTimeVal) {
      kpiTimeVal.textContent = `${fmt(t.total_pipeline_ms, 1)} ms`;
      if (kpiTimeBreakdown) {
        kpiTimeBreakdown.textContent = `Tâm sao ${fmt(t.centroiding_ms, 1)} · Khớp ${fmt(t.identification_ms, 1)} · Wahba ${fmt(t.attitude_ms, 2)} ms`;
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
          kpiBoresightSub.textContent = `${boresight.ra_hms || ""}  ${boresight.dec_dms || ""}`.trim();
        }
      } else {
        kpiBoresightVal.textContent = "RA -- · Dec --";
        if (kpiBoresightSub) kpiBoresightSub.textContent = "Chưa xác định được hướng ngắm";
      }
    }

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
      const prLine = hasPrecRec ? `<dt>Độ chính xác tâm sao</dt><dd>Precision ${precTxt} · Recall ${recTxt}</dd>` : "";
      const fovSpan = Array.isArray(cam.fov_deg) ? cam.fov_deg.map((x) => Number(x).toFixed(2)).join("° × ") + "°" : "—";
      metaDl.innerHTML = `
        <dt>Trạng thái</dt><dd>${status}${rejectCode ? ` (${rejectCode})` : ""}</dd>
        <dt>Cặp sao hợp lệ</dt><dd>${nValid} hợp lệ / ${nRejected} loại nhiễu (khớp sơ bộ ${initTxt}, yêu cầu tối thiểu ${minReq})</dd>
        <dt>Phần dư khớp góc</dt><dd>RMS ${rmsTxt} · Cực đại ${maxTxt}</dd>
        ${prLine}
        <dt>Nguồn dữ liệu</dt><dd>${payload.source === "simulator" ? "Mô phỏng quang học bầu trời sao" : payload.source_image}</dd>
        <dt>Thông số quang học</dt><dd>f = ${fmt(cam.focal_mm, 3)} mm · điểm ảnh ${fmt(cam.pixel_um, 3)} µm · ${cam.width}×${cam.height} px · ${fmt(cam.ifov_arcsec, 2)}″/px · FOV ${fovSpan}</dd>
        <dt>Chỉ mục tra góc</dt><dd>${(payload.angle_table && payload.angle_table.note) || "—"}</dd>
        <dt>Danh mục tham chiếu</dt><dd>${payload.catalog_source} (${payload.n_catalog} sao J2000, V ≤ 6.0)</dd>
        <dt>Gói tin 16-byte</dt><dd><code>${payload.downlink_hex}</code> (${payload.downlink_bytes} byte float32)</dd>
        <dt>Quaternion chuẩn</dt><dd>${payload.q_gt_text}</dd>
        <dt>Quaternion ước lượng</dt><dd>${payload.q_est_text}</dd>
      `;
    }

    const tstamp = Date.now();
    const inUrl = (payload.input_url || "/output/demo_input.png") + `?t=${tstamp}`;
    const outUrl = (payload.output_url || "/output/demo_output.png") + `?t=${tstamp}`;
    const hudUrl = (payload.image_url || "/output/demo_result.png") + `?t=${tstamp}`;
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
    if (imgOutLarge) {
      imgOutLarge.src = outUrl;
    }
    if (imgHud) {
      imgHud.src = hudUrl;
    }
    if (slotIn) slotIn.classList.add("hidden");
    if (slotOut) slotOut.classList.add("hidden");

    syncCompare3dImage();

    const st = payload.input_stats || {};
    const sha = st.sha256_12 || "--";
    const dimTxt = st.width && st.height ? `${st.width}×${st.height} px` : "";
    if (capIn) {
      capIn.textContent = `${dimTxt} ${st.dtype || ""} · DN ${st.dn_min ?? "?"}–${st.dn_max ?? "?"}`.trim();
    }
    if (capOut) {
      capOut.textContent = `Khớp ${nValid} sao hợp lệ · Phát hiện ${nDet} tâm sáng`;
    }
    if (capCompare3d) {
      capCompare3d.textContent = `${dimTxt} · Khớp ${nValid} sao danh mục`.replace(/^\s*·\s*/, "");
    }
    if (capOrbit3d) {
      if (status === "SOLVED") {
        const fovLbl = Array.isArray(cam.fov_deg)
          ? `Trường nhìn ${cam.fov_deg.map((x) => Number(x).toFixed(1)).join("° × ")}°`
          : "Đã khóa hướng ngắm";
        capOrbit3d.textContent = `${payload.catalog_source || "Yale BSC5"} · ${fovLbl}`;
      } else {
        capOrbit3d.textContent = "5.023 sao Yale BSC5 · Thiên cầu thực J2000";
      }
    }
    if (shaIntegrityText) {
      shaIntegrityText.textContent = `SHA-256: ${sha}`;
    }

    if (window.StarTrackerOrbit3D) {
      window.StarTrackerOrbit3D.updateFromPayload(payload);
    }

    if (status === "SOLVED") {
      setStageViewMode(currentViewMode === "orbit3d" ? "orbit3d" : "compare3d");
    } else {
      setStageViewMode("split");
    }

    const currentQ = starSearchInput ? starSearchInput.value : "";
    renderStarTable(fovBody, fovCount, fov, currentQ);
    renderStarTable(idBody, idCount, ident, currentQ);

    const attHtml = attOk ? `${attErr.toFixed(3)}″` : "không có nhãn GT";
    const ingest = payload.ingest_note ? `<br>${payload.ingest_note}` : "";
    const reqCent = String(payload.centroid_backend || "classical");
    const usedCent = String(payload.centroid_detector || reqCent);
    const fellBack = Boolean(payload.centroid_fallback) || (reqCent !== "classical" && usedCent === "classical");
    let centNote = "";
    if (reqCent !== "classical") {
      if (fellBack) {
        const why = payload.centroid_error ? ` (${payload.centroid_error})` : "";
        centNote = `<br>Chuyển tự động về trọng tâm sáng CoG${why}.`;
      } else {
        const nRaw = payload.centroid_n_raw;
        const nGate = payload.centroid_n_after_gate;
        const gateBit = nRaw != null && nGate != null ? ` (${nRaw} ứng viên → giữ ${nGate} điểm sao)` : "";
        centNote = `<br>Tách tâm sao bằng mạng <strong>MobileUNet</strong>${gateBit}.`;
      }
    }

    if (statusEl) {
      if (payload.success && status === "SOLVED") {
        statusEl.className = fellBack ? "status-banner err" : "status-banner success";
        statusEl.innerHTML =
          `<strong>Đã khóa hướng sao (${fmt(t.total_pipeline_ms, 1)} ms):</strong> ` +
          `Sai số góc <strong>${attHtml}</strong>, khớp hợp lệ <strong>${nValid}/${nDet}</strong> sao ` +
          `(loại ${nRejected} nhiễu), phần dư RMS ${rmsTxt}.${centNote}${ingest}`;
      } else {
        const why = payload.error || metrics.error || "Không đủ sao khớp nhất quán hình học.";
        const rcTag = rejectCode ? ` (${rejectCode})` : "";
        statusEl.className = "status-banner err";
        statusEl.innerHTML =
          `<strong>Chưa khóa được hướng${rcTag}:</strong> ${why} ` +
          `Phát hiện ${nDet} điểm sáng, cặp hợp lệ ${nValid}/${minReq}.${centNote}${ingest}`;
      }
    }

    if (opticsReadout && payload.angle_table && payload.camera) {
      opticsReadout.className = "radec-status-card";
      opticsReadout.textContent = payload.angle_table.note || "";
    }
  }

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
        ? "Nằm trong phạm vi bảng tra góc 30,5° có sẵn."
        : `Đường chéo ${geom.dDeg.toFixed(1)}° rộng hơn 30,5° (lần chạy đầu sẽ tạo chỉ mục góc tới ${geom.theta.toFixed(1)}°).`;
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

  async function postRun(body) {
    const isDataset = Boolean(body.image);
    const wide = bodyNeedsWideTable(body);
    const busy = isDataset
      ? "Đang đọc ảnh bầu trời sao và đối sánh tư thế..."
      : body.focal_mm
        ? "Đang dựng khung ảnh theo thông số quang học tùy chỉnh..."
        : "Đang mô phỏng bầu trời sao và xác định tư thế vệ tinh...";
    setBusy(
      true,
      wide ? `${busy} Trường nhìn rộng hơn 30,5° nên lần đầu khởi tạo bảng góc có thể mất ít phút.` : busy
    );
    try {
      const data = await fetchJson(
        "/api/run",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
        wide ? 600000 : 120000
      );
      renderPayload(data);
      const imgTab = document.querySelector('.tab-btn[data-tab="tab-imagery"]');
      if (imgTab && !imgTab.classList.contains("active")) imgTab.click();
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
      postRun(gatherFormData());
    });
  }

  if (btnSeed) {
    btnSeed.addEventListener("click", () => {
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
      const seedTabBtn = document.querySelector('.sub-tab-btn[data-target="target-seed"]');
      if (seedTabBtn) seedTabBtn.click();
      clearRadecFields();
      setCompare3dSource("raw");
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
      setCompare3dSource("raw");
      postRun(gatherFormData());
    });
  }

  if (btnMountPreset) {
    btnMountPreset.addEventListener("click", () => {
      const opticsLocked = document.getElementById("optics-locked");
      if (opticsLocked) opticsLocked.checked = true;
      if (opticsCustom) opticsCustom.hidden = true;
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
      clearRadecFields();
      const body = gatherFormData();
      body.image = "uploads/mount_st_helens_1.png";
      body.focal_mm = 4.2;
      body.pixel_um = 4.1;
      body.centroid_backend = "cnn";
      postRun(body);
    });
  }

  if (btnTetra3Preset) {
    btnTetra3Preset.addEventListener("click", () => {
      const opticsLocked = document.getElementById("optics-locked");
      if (opticsLocked) opticsLocked.checked = true;
      if (opticsCustom) opticsCustom.hidden = true;
      refreshOptics();
      const catalogSelect = document.getElementById("catalog-select");
      if (catalogSelect) catalogSelect.value = "bsc5";
      const solverSelect = document.getElementById("solver-select");
      if (solverSelect) solverSelect.value = "svd";
      setCentroidBackend("classical");
      form.glare.value = "none";
      if (form.sky_clutter) form.sky_clutter.value = "none";
      if (falseStarsSlider) falseStarsSlider.value = "0";
      if (falseStarsVal) falseStarsVal.textContent = "0";
      clearRadecFields();
      setCompare3dSource("raw");
      const body = gatherFormData();
      body.image = "tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff";
      body.focal_mm = 35.2911;
      body.pixel_um = 6.9;
      postRun(body);
    });
  }

  if (btnRadec) {
    btnRadec.addEventListener("click", () => {
      const paste = String(radecPaste?.value || "").trim();
      const ra = String(raHms?.value || "").trim();
      const dec = String(decDms?.value || "").trim();
      if (!paste && (!ra || !dec)) {
        if (statusEl) {
          statusEl.className = "status-banner err";
          statusEl.innerHTML = "<strong>Chưa có tọa độ:</strong> Hãy nhập cả RA và Dec trước khi ngắm.";
        }
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
      const opticsLocked = document.getElementById("optics-locked");
      if (opticsLocked) opticsLocked.checked = true;
      if (opticsCustom) opticsCustom.hidden = true;
      refreshOptics();
      form.glare.value = "none";
      if (form.sky_clutter) form.sky_clutter.value = "none";
      if (falseStarsSlider) falseStarsSlider.value = "0";
      if (falseStarsVal) falseStarsVal.textContent = "0";
      setCentroidBackend("classical");
      postRun({ ...gatherFormData(), image: file });
    });
  }

  function refreshLocalHint() {
    if (!localFileHint) return;
    const imgName = localImage && localImage.files && localImage.files[0] ? localImage.files[0].name : "";
    const jsName = localSidecar && localSidecar.files && localSidecar.files[0] ? localSidecar.files[0].name : "";
    if (!imgName) {
      localFileHint.textContent =
        "Khuyên dùng ảnh TIFF/PNG gốc. Với ảnh chụp từ máy ảnh khác, hãy nhập tiêu cự và cỡ điểm ảnh ở mục Hệ quang học.";
      return;
    }
    localFileHint.textContent = jsName
      ? `Đã chọn ảnh: ${imgName} · Nhãn: ${jsName}`
      : `Đã chọn ảnh: ${imgName} (tự động đối chiếu nhãn nếu trùng tên trong bộ mẫu)`;
  }

  if (localImage) localImage.addEventListener("change", refreshLocalHint);
  if (localSidecar) localSidecar.addEventListener("change", refreshLocalHint);

  if (btnUpload) {
    btnUpload.addEventListener("click", async () => {
      if (!localImage || !localImage.files || !localImage.files[0]) {
        if (detailsDataset) detailsDataset.open = true;
        if (statusEl) {
          statusEl.className = "status-banner err";
          statusEl.innerHTML = "<strong>Chưa chọn tệp ảnh:</strong> Hãy chọn một tệp TIFF, PNG hoặc JPEG từ máy tính.";
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
      setBusy(
        true,
        customUpload
          ? "Đang tải tệp ảnh và giải tư thế theo cấu hình quang học tùy chỉnh..."
          : "Đang tải tệp ảnh lên và nhận diện bầu trời sao..."
      );
      try {
        const data = await fetchJson("/api/run-upload", { method: "POST", body: fd }, customUpload ? 600000 : 180000);
        renderPayload(data);
        const imgTab = document.querySelector('.tab-btn[data-tab="tab-imagery"]');
        if (imgTab && !imgTab.classList.contains("active")) imgTab.click();
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

  window.StarTrackerOrbit3D?.init(orbit3dRoot);
})();
