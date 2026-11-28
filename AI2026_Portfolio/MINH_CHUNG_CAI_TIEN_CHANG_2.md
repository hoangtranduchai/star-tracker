# MINH CHỨNG CẢI TIẾN VÒNG CHUNG KẾT · CHẶNG 2 (HACKATHON)

> **Đội thi:** `DUT.StarTracker` (`AI26C0083`) · Bảng C · Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin  
> **Ngày kiểm chứng:** `28/11/2026` · **Phiên bản mã nguồn:** `v1.2.0-stage2` (nhánh `main`, commit nền `3c6d5a6`)  
> **Đề cải tiến Chặng 2 (Phiên bản 1):** *1. Tái lập pipeline và kiểm soát dữ liệu ảnh*  
> **Sản phẩm trực tuyến 24/7:** https://startracker.agentlens.dpdns.org  
> **Hướng dẫn tái lập từ bản clone sạch:** [`REPRODUCIBILITY.md`](../REPRODUCIBILITY.md) · **Bảng Checksum:** [`CHECKSUMS.sha256`](../CHECKSUMS.sha256)

---

## 1. Bảng đối chiếu 3 minh chứng bắt buộc của Đề Chặng 2

| Yêu cầu minh chứng trong Đề Chặng 2 | Bằng chứng trực tiếp trong tài liệu này | Đường dẫn xác thực trực tiếp |
|---|---|---|
| **(1) Hướng dẫn chạy từ bản tải sạch** (checkpoint, ảnh mẫu, checksum, hiệu chuẩn, lệnh benchmark) | Bảng 13/13 tệp SHA-256 (`36,02 MiB (37,77 MB)`, khóa LF đa nền tảng `.gitattributes`), xác thực `verify_repro_bundle.py` & `sha256sum -c CHECKSUMS.sha256` **13/13 OK trên cả Linux/macOS (`core.autocrlf=false`) lẫn Windows (`core.autocrlf=true`)**, log chạy `run_clean_repro.py` (`11.70s`), chứng minh Runtime Guard chặn 1-byte tamper `CHECKPOINT_SHA256_MISMATCH` trước `torch.load` và benchmark `benchmark_3way_centroid_e2e.py --real-only` đủ 20 khung clutter (`86.46s`, 0% FL) (Mục 2–3, Hình 1–2) | [`REPRODUCIBILITY.md`](../REPRODUCIBILITY.md), [`CHECKSUMS.sha256`](../CHECKSUMS.sha256), [`.gitattributes`](../.gitattributes), [`scripts/run_clean_repro.py`](../scripts/run_clean_repro.py) |
| **(2) Log mode thực thi & báo rõ Fallback CoG** | Nhật ký JSONL có cấu trúc ghi nguyên tử `os.replace` có retry khóa Windows, **cô lập theo phiên `owner_sid_hash`**, chặn tải trực tiếp `GET /output/*.jsonl` (`HTTP 404`); báo rõ `requested_backend` → `executed_backend`, `FALLBACK_TO_COG`, `fallback_reason` (lọc đường dẫn tương đối, không lộ đường dẫn OS), `checkpoint_status` (`verified`/`checksum_mismatch`/`corrupted_truncated`/`simulated_missing`), `checkpoint_sha256` và bit telemetry `FLAG_FALLBACK_USED (0x08)` trên mọi nhánh `cnn`, `auto`, `/api/compare` & CLI (Hình 3 & Mục 3, 5) | `GET /api/execution-log`, [`src/execution_log.py`](../src/execution_log.py), [`src/centroid_cnn.py`](../src/centroid_cnn.py), [`src/telemetry.py`](../src/telemetry.py) |
| **(3) Demo kiểm soát dữ liệu ảnh, chống ghi đè & xóa dữ liệu** | Cách ly tuyệt đối `data/user_uploads/<uuid4>/` + luôn ghi `meta.json` gắn cookie phiên `st_sid` (`HttpOnly`, `SameSite=Lax`, `Secure`, chống IDOR cả chế độ `ephemeral` lẫn gọi trực tiếp không cookie); mặc định `ephemeral` xóa ngay trong `finally:` (`51e66d6603744123`); tùy chọn `ttl` 15 phút (`900s`, quét dọn ngay khi khởi động + luồng nền mỗi `60s`, rollback lỗi HTTP 400/409); chống ghi đè 2 lượt tải trùng tên `mount_st_helens_1.png` (`e52cbdbd8d734c9d`, `544f376c3bd74dce`), xóa đơn & xóa tất cả (URL preview `200 → 404`, xóa sạch DOM preview `#compare3d-img`, trình duyệt B nhận `0` tệp & `404`) (Hình 4–5 & Mục 5) | `GET /api/uploads`, `DELETE /api/uploads/<id>`, `DELETE /api/uploads`, [`src/upload_store.py`](../src/upload_store.py) |

---

## 2. Kiểm chứng toàn vẹn 13/13 tệp Gói Tái lập Độc lập (`CHECKSUMS.sha256` + `.gitattributes`)

Tổng dung lượng gói tái lập đóng gói trực tiếp trong kho Git chuẩn (không cần Git LFS, khóa chuẩn xuống dòng LF đa nền tảng qua `.gitattributes`): **`36,02 MiB (37,77 MB)`** (`37,773,058 bytes`; tệp lớn nhất `MobileUNet_B10_50.pt` = **`17,71 MiB (18,57 MB)`**, `< 19 MB`; `13/13` hợp lệ, `checkpoint_status=verified`).

| Nhóm | Đường dẫn tệp trong kho | Kích thước (nhị phân) | SHA-256 (24 ký tự đầu) | Trạng thái |
|---|---|---:|---|---|
| Checkpoint CNN | `third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt` | 17.71 MiB | `e02d7723b832d12cf2535a8a…` | **verified** |
| Ảnh trời thật | `data/tetra3/2019-07-29T204726_Alt40_Azi-135_Try1.tiff` | 1.50 MiB | `f5d6c27ac7e8e2114fbeb451…` | **verified** |
| Ảnh trời thật | `data/tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff` | 1.50 MiB | `f288f6e1fb3a1299626956e3…` | **verified** |
| Ảnh trời thật | `data/real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy` | 2.34 MiB | `57ec7838e430900b438c7217…` | **verified** |
| Ảnh trời thật | `data/real_calibrated/zhao_mt9v022/verification_img.npy` | 2.34 MiB | `b9a413dc087ccea0d6c68224…` | **verified** |
| Ảnh trời thật | `data/uploads/mount_st_helens_1.png` | 1.05 MiB | `f29437dbb96e70cbeda5a9ea…` | **verified** |
| Ảnh trời thật | `data/uploads/real_sky/images/0006.png` | 9.12 MiB | `9a699a274af866bd6a7928c7…` | **verified** |
| Hiệu chuẩn / Config | `data/real_calibrated/manifest_real_calibrated.json` | 128.4 KiB | `2e2d0cd1f176f651e15dd33e…` | **verified** |
| Hiệu chuẩn / Config | `data/uploads/real_sky/metadata.yaml` | 3.1 KiB | `5283e3ccd81c5411ed1ddeea…` | **verified** |
| Hiệu chuẩn / Config | `config/camera_specs.json` | 1.5 KiB | `68b60198232c9bc041bbfa5c…` | **verified** |
| Hiệu chuẩn / Config | `config/pipeline_default.json` | 1.3 KiB | `8c178d068798f3ea6c3f869b…` | **verified** |
| Danh mục sao | `data/catalogs/BSC5` | 284.7 KiB | `e471d02eaf4eecb61c12f879…` | **verified** |
| Danh mục sao | `data/catalogs/IAU-CSN.txt` | 50.3 KiB | `910dd0d14f1c3f08f43f8365…` | **verified** |

---

## 3. Bằng chứng chạy thực tế từ bản `git clone` sạch đa nền tảng (LF Linux/macOS & Windows `autocrlf=true`)

Đội đã kiểm chứng trên **hai bản `git clone` hoàn toàn trống** với cấu hình xuống dòng Linux/macOS (`git clone -c core.autocrlf=false`) và Windows (`git clone -c core.autocrlf=true`), chạy đủ chuỗi xác thực SHA-256 (`verify_repro_bundle.py` & `sha256sum -c CHECKSUMS.sha256`), tái lập pipeline 1 lệnh (`run_clean_repro.py`), CLI fallback (`demo_star_tracker.py --simulate-cnn-fallback`), thử nghiệm sửa 1 byte checkpoint (`CHECKPOINT_SHA256_MISMATCH` chặn trước `torch.load`), và benchmark đầy đủ (`benchmark_3way_centroid_e2e.py --real-only`, mặc định 20 khung clutter):

```bash
python scripts/verify_repro_bundle.py
sha256sum -c CHECKSUMS.sha256
python scripts/run_clean_repro.py
python demo_star_tracker.py --centroid cnn --simulate-cnn-fallback --seed 42 --no-show
python scripts/benchmark_3way_centroid_e2e.py --real-only
```

### Kết quả stdout nguyên văn từ bản clone sạch (`stage2_evidence/clean_clone_terminal_log.txt`):

```text
=== Cross-Platform Clean Git Clone Verification (Stage 2 Final Hardened) ===
Timestamp (UTC): 2026-11-28T03:12:48Z

=== [A] Linux/macOS LF Clone (git clone -c core.autocrlf=false) ===
$ git clone -c core.autocrlf=false https://github.com/hoangtranduchai/star-tracker.git <CLEAN_CLONE_LF>
Cloning into '<CLEAN_CLONE_LF>'...
done.

$ python scripts/verify_repro_bundle.py
[PASS] checkpoint      third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt ( 18137.5 KB) sha256=e02d7723b832d12c...
  [PASS] sample_real_sky data/tetra3/2019-07-29T204726_Alt40_Azi-135_Try1.tiff          (  1536.3 KB) sha256=f5d6c27ac7e8e211...
  [PASS] sample_real_sky data/tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff          (  1536.3 KB) sha256=f288f6e1fb3a1299...
  [PASS] sample_real_sky data/real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy     (  2400.1 KB) sha256=57ec7838e430900b...
  [PASS] sample_real_sky data/real_calibrated/zhao_mt9v022/verification_img.npy         (  2400.1 KB) sha256=b9a413dc087ccea0...
  [PASS] sample_real_sky data/uploads/mount_st_helens_1.png                             (  1070.3 KB) sha256=f29437dbb96e70cb...
  [PASS] sample_real_sky data/uploads/real_sky/images/0006.png                          (  9337.9 KB) sha256=9a699a274af866bd...
  [PASS] calibration     data/real_calibrated/manifest_real_calibrated.json             (   128.4 KB) sha256=2e2d0cd1f176f651...
  [PASS] calibration     data/uploads/real_sky/metadata.yaml                            (     3.1 KB) sha256=5283e3ccd81c5411...
  [PASS] calibration     config/camera_specs.json                                       (     1.5 KB) sha256=68b60198232c9bc0...
  [PASS] calibration     config/pipeline_default.json                                   (     1.3 KB) sha256=8c178d068798f3ea...
  [PASS] catalog         data/catalogs/BSC5                                             (   284.7 KB) sha256=e471d02eaf4eecb6...
  [PASS] catalog         data/catalogs/IAU-CSN.txt                                      (    50.3 KB) sha256=910dd0d14f1c3f08...

[SUMMARY] verified=13/13 (36.02 MB) | checkpoint=verified | ok=True

$ sha256sum -c CHECKSUMS.sha256
third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt: OK
data/tetra3/2019-07-29T204726_Alt40_Azi-135_Try1.tiff: OK
data/tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff: OK
data/real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy: OK
data/real_calibrated/zhao_mt9v022/verification_img.npy: OK
data/uploads/mount_st_helens_1.png: OK
data/uploads/real_sky/images/0006.png: OK
data/real_calibrated/manifest_real_calibrated.json: OK
data/uploads/real_sky/metadata.yaml: OK
config/camera_specs.json: OK
config/pipeline_default.json: OK
data/catalogs/BSC5: OK
data/catalogs/IAU-CSN.txt: OK

$ python scripts/run_clean_repro.py
=== [1/4] Verifying SHA-256 Checksums (CHECKSUMS.sha256) ===
  Verified: 13/13 (36.02 MB) | ok=True
  Checkpoint SHA-256: e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062

=== [2/4] Clean-Clone Pipeline Runs (Seed 42 + Calibrated Real-Sky) ===
Building angle table 0.02-30.5 deg for BSC5+filt (first time, then cached).
  [seed42_auto           ] req=auto -> exe=classical | fallback=False | SOLVED | pairs=36 | dTh=0.45" | gt=simulator_ground_truth | t=93.6ms
  [esa_alt60_auto        ] req=auto -> exe=classical | fallback=False | SOLVED | pairs=9 | dTh=2.26" | gt=esa_tetra3_hipparcos_plus_scipy_f_k1 | t=72.4ms
  [zhao_nightsky_auto    ] req=auto -> exe=cnn_hybrid | fallback=False | SOLVED | pairs=8 | dTh=48.26" | gt=zhao_heikkila_undistort_plus_hipparcos_3dof | t=5486.3ms
Building angle table 0.02-71.5 deg for BSC5+filt (first time, then cached).
CNN centroid backend unavailable (FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt); falling back explicitly to classical CoG.
CNN centroid backend unavailable (FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt); falling back explicitly to classical CoG.
  [mount_st_helens_cnn   ] req=cnn -> exe=cnn_hybrid | fallback=False | SOLVED | pairs=72 | dTh=71.13" | gt=startracker_hipparcos_sky_only_scipy_f_k1_k2 | t=619.5ms

=== [3/4] Explicit CNN -> CoG Fallback Proof (Direct CNN & Auto-Router) ===
  [FALLBACK DIRECT] req=cnn  -> exe=classical | fallback=True | summary=cnn -> classical [FALLBACK_TO_COG] | status=SOLVED
  [FALLBACK AUTO  ] req=auto -> exe=classical | fallback=True | summary=auto -> classical [FALLBACK_TO_COG] | status=LOST (INSUFFICIENT_INLIER_PAIRS)

=== [4/4] Upload Isolation (Zero-Overwrite) & Verified Deletion Proof ===
  [DATA CONTROL] Same filename -> isolated UUIDs (4250b57c19d148b3, a1cdf81ea56445e7); deleted & verified_gone=True; remaining=0

[PASS] Clean-clone reproducibility & data-control audit completed in 11.7s -> <CLEAN_CLONE_LF>\data\outputs\clean_repro_log.json

$ python demo_star_tracker.py --centroid cnn --simulate-cnn-fallback --seed 42 --no-show
======================================================================
   STAR TRACKER - STAR TRACKER DEMO (LAPTOP RUNTIME)
======================================================================
[*] Hardware: APS-C (Tùy chỉnh) + 50mm f/1.8 (Tùy chỉnh)
[*] Pixel pitch: 3.72 um
[*] Radiometry parameters are simulation assumptions, not a camera datasheet.
[1/5] Loading catalog + K-vector...
[2/5] Rendering or loading frame...
Building angle table 0.02-30.5 deg for BSC5+filt (first time, then cached).
CNN centroid backend unavailable (FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt); falling back explicitly to classical CoG.
[1/5] Catalog BSC5+filt: 5023 stars  V<=6.0
[*] Mode=fast  1500x1000  FOV=25.16x16.93 deg  IFOV=61.38 arcsec/px
      q_GT = [0.18817, -0.64223, 0.46343, 0.58083]
      GT boresight RA=162.1367 deg (10h 48m 32.81s)  Dec=-14.7409 deg (-14d 44m 27.2s)
      stars in FOV=36
      image 1500x1000  source=simulator
[3/5] Running deterministic pipeline...
[4/5] Results
-------------------------------------------------------
  Centroiding : 35.34 ms
  Star ID     : 12.05 ms
  Wahba       : 1.22 ms
  Total       : 92.46 ms
-------------------------------------------------------
  Exec mode   : cnn -> classical [FALLBACK_TO_COG] (checkpoint=simulated_missing)
  [WARNING] FALLBACK TO CoG TRIGGERED! Reason: FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt
  Status      : SOLVED
  Valid pairs : 36 (initial=12, min_req=4)
  Rejected outliers          : 0
  Post-fit residual RMS/Max (arcsec): 3.286 / 7.037
  Centroid precision/recall  : 100.0% / 100.0%
  q_est       : [0.18817, -0.64223, 0.46343, 0.58083]
  boresight   : RA 162.1367 deg (10h 48m 32.82s)   Dec -14.7408 deg (-14d 44m 26.8s)
               (optical axis +Z in ICRS/J2000 celestial coordinates)
  att err     : 0.446 arcsec
  downlink    : a4b0403e036924bfb046ed3e7eb1143f  (16 bytes)
  verdict     : PASS
  matched HR  : 4232, 4382, 3994, 4094, 4405, 4287, 4343, 3970, 4163, 4402, 4171, 4314, 3977, 3989, 3991, 3996, 4042, 4055, 4082, 4092, 4116, 4123, 4158, 4214, 4233, 4237, 4251, 4255, 4284, 4289, 4305, 4317, 4334, 4395, 4416, 4488
[5/5] Wrote <CLEAN_CLONE_LF>\data\outputs\demo_result.png and <CLEAN_CLONE_LF>\data\outputs\demo_result.json
======================================================================

$ python -c "<tampered-checkpoint CHECKPOINT_SHA256_MISMATCH guard verification>"
CNN centroid backend unavailable (ValueError: CHECKPOINT_SHA256_MISMATCH: expected e02d7723b832d12c..., got a7899cd3d20fc86d... (third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt)); falling back explicitly to classical CoG.
[GUARD] inspect_checkpoint_status -> status=checksum_mismatch sha256=a7899cd3d20fc86d...
[GUARD] verify_checkpoint_integrity blocked torch.load -> CHECKPOINT_SHA256_MISMATCH: expected e02d7723b832d12c..., got a7899cd3d20fc86d... (third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt)
[PIPELINE] req=cnn -> exe=classical | fallback=True | checkpoint_status=checksum_mismatch | status=SOLVED | pairs=36 | dTh=0.45"
[PIPELINE] fallback_reason=ValueError: CHECKPOINT_SHA256_MISMATCH: expected e02d7723b832d12c..., got a7899cd3d20fc86d... (third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt)
[COMPARE/AUTO] summary=auto -> classical [FAST_COG] | checkpoint_status=checksum_mismatch | status=SOLVED
[RESTORED] inspect_checkpoint_status -> status=verified sha256=e02d7723b832d12c...

$ python scripts/benchmark_3way_centroid_e2e.py --real-only
[*] CNN warmed: torch=2.11.0+cu128 cuda=True device=NVIDIA GeForce RTX 5070 Laptop GPU

=== Suite: real_calibrated (6 frames x 5 backends) ===
  [INFO] Optional Hipparcos TSV (data/catalogs/starcat.tsv) not bundled on clean clone — running full primary BSC5 V<=6.0 suite and skipping supplementary Alt40 Hipparcos V<=7.0.
  [Cal/BSC5] 2019-07-29T204726_Alt40_Azi-135_Try1.tiff classical: LOST   dTh=n/a      valid=1/8 RMSE5=0.164px t=280.3ms
  [Cal/BSC5] 2019-07-29T204726_Alt40_Azi-135_Try1.tiff tetra3   : SOLVED dTh=27.08"   valid=4/23 RMSE5=0.142px t=232.5ms
  [Cal/BSC5] 2019-07-29T204726_Alt40_Azi-135_Try1.tiff cnn_raw  : LOST   dTh=n/a      valid=4/38 RMSE5=0.167px t=512.3ms
  [Cal/BSC5] 2019-07-29T204726_Alt40_Azi-135_Try1.tiff cnn      : LOST   dTh=n/a      valid=1/38 RMSE5=0.109px t=346.5ms
  [Cal/BSC5] 2019-07-29T204726_Alt40_Azi-135_Try1.tiff auto     : LOST   dTh=n/a      valid=1/38 RMSE5=0.109px t=556.5ms
  [Cal/BSC5] 2019-07-29T204726_Alt60_Azi-135_Try1.tiff classical: SOLVED dTh=2.26"    valid=9/14 RMSE5=0.162px t=106.0ms
  [Cal/BSC5] 2019-07-29T204726_Alt60_Azi-135_Try1.tiff tetra3   : SOLVED dTh=8.68"    valid=9/29 RMSE5=0.119px t=159.3ms
  [Cal/BSC5] 2019-07-29T204726_Alt60_Azi-135_Try1.tiff cnn_raw  : SOLVED dTh=4.65"    valid=9/45 RMSE5=0.114px t=149.9ms
  [Cal/BSC5] 2019-07-29T204726_Alt60_Azi-135_Try1.tiff cnn      : SOLVED dTh=6.77"    valid=9/45 RMSE5=0.102px t=188.7ms
  [Cal/BSC5] 2019-07-29T204726_Alt60_Azi-135_Try1.tiff auto     : SOLVED dTh=2.26"    valid=9/14 RMSE5=0.162px t=108.7ms
  [Cal/BSC5] nightsky_june16_2021.npy             classical: LOST   dTh=n/a      valid=3/4 RMSE5=0.627px t=249.8ms
  [Cal/BSC5] nightsky_june16_2021.npy             tetra3   : LOST   dTh=n/a      valid=5/5 RMSE5=0.486px t=273.9ms
  [Cal/BSC5] nightsky_june16_2021.npy             cnn_raw  : SOLVED dTh=54.70"   valid=8/8 RMSE5=0.380px t=117.2ms
  [Cal/BSC5] nightsky_june16_2021.npy             cnn      : SOLVED dTh=48.26"   valid=8/8 RMSE5=0.429px t=109.1ms
  [Cal/BSC5] nightsky_june16_2021.npy             auto     : SOLVED dTh=48.26"   valid=8/8 RMSE5=0.429px t=356.8ms
  [Cal/BSC5] verification_img.npy                 classical: LOST   dTh=n/a      valid=0/4 RMSE5=n/a t=453.3ms
  [Cal/BSC5] verification_img.npy                 tetra3   : LOST   dTh=n/a      valid=0/4 RMSE5=n/a t=495.1ms
  [Cal/BSC5] verification_img.npy                 cnn_raw  : LOST   dTh=n/a      valid=0/4 RMSE5=n/a t=491.0ms
  [Cal/BSC5] verification_img.npy                 cnn      : LOST   dTh=n/a      valid=0/4 RMSE5=n/a t=430.8ms
  [Cal/BSC5] verification_img.npy                 auto     : LOST   dTh=n/a      valid=0/4 RMSE5=n/a t=866.3ms
  [Cal/BSC5] mount_st_helens_1.png                classical: SOLVED dTh=49.51"   valid=83/106 RMSE5=0.561px t=293.2ms
  [Cal/BSC5] mount_st_helens_1.png                tetra3   : LOST   dTh=n/a      valid=4/80 RMSE5=0.535px t=1421.6ms
  [Cal/BSC5] mount_st_helens_1.png                cnn_raw  : SOLVED dTh=120.26"  valid=66/79 RMSE5=1.306px t=428.8ms
  [Cal/BSC5] mount_st_helens_1.png                cnn      : SOLVED dTh=71.13"   valid=72/77 RMSE5=0.976px t=592.4ms
  [Cal/BSC5] mount_st_helens_1.png                auto     : SOLVED dTh=49.51"   valid=83/106 RMSE5=0.561px t=357.1ms
Building angle table 0.02-78.5 deg for BSC5+filt (first time, then cached).
  [Uncal Stress] 0006.png: detected counts = {'classical': 2729, 'tetra3': 80, 'cnn_raw': 80, 'cnn': 80, 'auto': 2729}

=== Suite: sim_earth_clutter (20 frames x 5 backends) ===
  classical : solved=20/20 correct=20 FL=0 med_dTh=2.46" Prec= 90.2% Rec= 62.2% FP= 76 RMSE5=0.1619px
  tetra3    : solved=20/20 correct=20 FL=0 med_dTh=2.90" Prec= 90.2% Rec= 63.9% FP= 78 RMSE5=0.1886px
  cnn_raw   : solved=20/20 correct=20 FL=0 med_dTh=14.58" Prec= 86.5% Rec= 61.4% FP=108 RMSE5=0.3521px
  cnn       : solved=20/20 correct=20 FL=0 med_dTh=3.17" Prec= 90.3% Rec= 61.9% FP= 75 RMSE5=0.1672px
  auto      : solved=20/20 correct=20 FL=0 med_dTh=2.46" Prec= 90.2% Rec= 62.2% FP= 76 RMSE5=0.1619px

[DONE] Saved 4-way audited benchmark to <CLEAN_CLONE_LF>\data\outputs\benchmark_3way_clean_clone.json in 86.46s

=== [B] Windows CRLF-Config Clone (git clone -c core.autocrlf=true) ===
$ git clone -c core.autocrlf=true https://github.com/hoangtranduchai/star-tracker.git <CLEAN_CLONE_WIN>
Cloning into '<CLEAN_CLONE_WIN>'...
done.

$ python scripts/verify_repro_bundle.py
[PASS] checkpoint      third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt ( 18137.5 KB) sha256=e02d7723b832d12c...
  [PASS] sample_real_sky data/tetra3/2019-07-29T204726_Alt40_Azi-135_Try1.tiff          (  1536.3 KB) sha256=f5d6c27ac7e8e211...
  [PASS] sample_real_sky data/tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff          (  1536.3 KB) sha256=f288f6e1fb3a1299...
  [PASS] sample_real_sky data/real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy     (  2400.1 KB) sha256=57ec7838e430900b...
  [PASS] sample_real_sky data/real_calibrated/zhao_mt9v022/verification_img.npy         (  2400.1 KB) sha256=b9a413dc087ccea0...
  [PASS] sample_real_sky data/uploads/mount_st_helens_1.png                             (  1070.3 KB) sha256=f29437dbb96e70cb...
  [PASS] sample_real_sky data/uploads/real_sky/images/0006.png                          (  9337.9 KB) sha256=9a699a274af866bd...
  [PASS] calibration     data/real_calibrated/manifest_real_calibrated.json             (   128.4 KB) sha256=2e2d0cd1f176f651...
  [PASS] calibration     data/uploads/real_sky/metadata.yaml                            (     3.1 KB) sha256=5283e3ccd81c5411...
  [PASS] calibration     config/camera_specs.json                                       (     1.5 KB) sha256=68b60198232c9bc0...
  [PASS] calibration     config/pipeline_default.json                                   (     1.3 KB) sha256=8c178d068798f3ea...
  [PASS] catalog         data/catalogs/BSC5                                             (   284.7 KB) sha256=e471d02eaf4eecb6...
  [PASS] catalog         data/catalogs/IAU-CSN.txt                                      (    50.3 KB) sha256=910dd0d14f1c3f08...

[SUMMARY] verified=13/13 (36.02 MB) | checkpoint=verified | ok=True

$ sha256sum -c CHECKSUMS.sha256
third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt: OK
data/tetra3/2019-07-29T204726_Alt40_Azi-135_Try1.tiff: OK
data/tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff: OK
data/real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy: OK
data/real_calibrated/zhao_mt9v022/verification_img.npy: OK
data/uploads/mount_st_helens_1.png: OK
data/uploads/real_sky/images/0006.png: OK
data/real_calibrated/manifest_real_calibrated.json: OK
data/uploads/real_sky/metadata.yaml: OK
config/camera_specs.json: OK
config/pipeline_default.json: OK
data/catalogs/BSC5: OK
data/catalogs/IAU-CSN.txt: OK
```

### Tóm tắt kết quả định lượng từ bản clone sạch (`clean_clone_repro_log.json` & kiểm chứng tamper guard):

| Ca kiểm chứng tái lập | Chế độ yêu cầu → Thực thi | Trạng thái | Cặp sao hợp lệ | Sai số / Thời gian / Ghi chú |
|---|---|---|---|---|
| `seed42_auto` | `auto -> classical` | **SOLVED** | `36 sao` | Δθ 0.45″ · `93.6 ms` |
| `esa_alt60_auto` | `auto -> classical` | **SOLVED** | `9 sao` | Δθ 2.26″ · `72.4 ms` |
| `zhao_nightsky_auto` | `auto -> cnn_hybrid` | **SOLVED** | `8 sao` | Δθ 48.26″ · `5486.3 ms` |
| `mount_st_helens_cnn` | `cnn -> cnn_hybrid` | **SOLVED** | `72 sao` | Δθ 71.13″ · `619.5 ms` |
| `fallback_missing_checkpoint` | `cnn -> classical [FALLBACK_TO_COG]` | **SOLVED** (`fallback=True`) | `36 sao` | Lý do (đường dẫn tương đối đã lọc): `FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt` |
| `auto_router_fallback_zhao` | `auto -> classical [FALLBACK_TO_COG]` | **LOST** (`INSUFFICIENT_INLIER_PAIRS`) | `fallback=True` | Auto-Router báo lỗi checkpoint & từ chối an toàn (0% FL) |
| `tampered_1byte_sha256_guard` | `cnn -> classical [FALLBACK_TO_COG]` | **SOLVED** (`checksum_mismatch`) | `36 sao` (`Δθ 0.45″`) | `verify_checkpoint_integrity` chặn `torch.load` (`CHECKPOINT_SHA256_MISMATCH`, got `a7899cd3d20fc86d…`) |
| `upload_isolation_and_delete` | `same filename (mount_st_helens_1.png)` | **VERIFIED** (`remaining=0`) | 2 UUID: `4250b57c19d148b3`, `a1cdf81ea56445e7` | Chống ghi đè & xóa sạch đĩa (`bundled_untouched=True`) |
| `benchmark_3way --real-only` | `5 backends × (6 real + 20 clutter)` | **PASS** (`86.46s`) | `0% False Lock` | Clutter 20 khung: CoG/Auto `20/20 (2.46″)`, tetra3 `20/20 (2.90″)`, CNN-Hybrid `20/20 (3.17″, 75 FP thấp nhất)` |

> **Ghi chú đối chiếu ảnh Mount St. Helens (CoG danh nghĩa Chặng 1 vs hiệu chuẩn góc rộng Chặng 2):** Ở cấu hình quang học danh nghĩa Chặng 1 (không hệ số méo `k1/k2`), CoG trên `mount_st_helens_1.png` trả về `LOST [INSUFFICIENT_INLIER_PAIRS]` (1 inlier) nhằm minh chứng chốt chặn 0% khóa sai; khi áp dụng quang học hiệu chuẩn góc rộng (`f, cx, cy, k1, k2`) cùng bộ đối sánh wide-FOV nâng cấp, CoG giải đúng (`SOLVED 83/106, Δθ = 49,51″`) trong khi ngưỡng kiểu `tetra3` vẫn trả `LOST` và `CNN-Hybrid` giải `72/77 (Δθ = 71,13″)`.

---

## 4. Minh chứng trực tiếp trên giao diện Web UI (đồng bộ 24/7 tại `https://startracker.agentlens.dpdns.org`)

### Hình 1. Sơ đồ kiến trúc tổng thể Pipeline định hướng sao J2000 & Tầng kiểm soát dữ liệu ảnh Chặng 2 (Gói tái lập 13/13 SHA-256 36,02 MiB (37,77 MB) + .gitattributes LF, Runtime Guard trước torch.load, Auto-Router + Fallback CoG 0% fallback ngầm, Cô lập UUID4 / st_sid / Ephemeral / TTL 15 phút + quét khởi động & nền 60s, Rollback lỗi 400/409 và Nhật ký JSONL nguyên tử).

![Hình 1. Sơ đồ kiến trúc tổng thể Pipeline định hướng sao J2000 & Tầng kiểm soát dữ liệu ảnh Chặng 2 (Gói tái lập 13/13 SHA-256 36,02 MiB (37,77 MB) + .gitattributes LF, Runtime Guard trước torch.load, Auto-Router + Fallback CoG 0% fallback ngầm, Cô lập UUID4 / st_sid / Ephemeral / TTL 15 phút + quét khởi động & nền 60s, Rollback lỗi 400/409 và Nhật ký JSONL nguyên tử).](stage2_evidence/stage2_pipeline_architecture.png)

### Hình 2. Giao diện Web UI kiểm chứng trực tiếp — Tab Cấu hình, Checksum & Dữ liệu xác thực đủ 13/13 tệp SHA-256 (36,02 MiB (37,77 MB), checkpoint verified) đồng thời hiển thị rõ 3 bản ghi nhật ký thực thi thời gian thực (AUTO_ESCALATED trên Zhao nightsky, DIRECT trên Mount St. Helens và ESA Alt60).

![Hình 2. Giao diện Web UI kiểm chứng trực tiếp — Tab Cấu hình, Checksum & Dữ liệu xác thực đủ 13/13 tệp SHA-256 (36,02 MiB (37,77 MB), checkpoint verified) đồng thời hiển thị rõ 3 bản ghi nhật ký thực thi thời gian thực (AUTO_ESCALATED trên Zhao nightsky, DIRECT trên Mount St. Helens và ESA Alt60).](stage2_evidence/ev1_repro_checksums_and_audit_log.png)

### Hình 3. Minh chứng báo rõ Fallback CNN → CoG (0% fallback ngầm): kích hoạt "Thử nghiệm Fallback CNN → CoG" bật dải cảnh báo màu cam nổi bật trên đầu trang kèm đường dẫn tương đối đã lọc (không lộ đường dẫn OS), ghi nhận cả cnn -> classical [FALLBACK_TO_COG] (Seed 42 SOLVED 0,446″) và auto -> classical [FALLBACK_TO_COG] (Zhao nightsky LOST) vào execution_log.jsonl.

![Hình 3. Minh chứng báo rõ Fallback CNN → CoG (0% fallback ngầm): kích hoạt "Thử nghiệm Fallback CNN → CoG" bật dải cảnh báo màu cam nổi bật trên đầu trang kèm đường dẫn tương đối đã lọc (không lộ đường dẫn OS), ghi nhận cả cnn -> classical [FALLBACK_TO_COG] (Seed 42 SOLVED 0,446″) và auto -> classical [FALLBACK_TO_COG] (Zhao nightsky LOST) vào execution_log.jsonl.](stage2_evidence/ev2_fallback_cog_banner.png)

### Hình 4. Minh chứng chống ghi đè & lưu tạm TTL 15 phút (cô lập theo phiên st_sid): hai lượt tải liên tiếp cùng ảnh thật mount_st_helens_1.png (1,05 MiB) + sidecar mount_st_helens_1.json được cách ly vào hai thư mục UUID4 độc lập (data/user_uploads/e52cbdbd8d734c9d/ và data/user_uploads/544f376c3bd74dce/) kèm đếm ngược TTL và nút Xóa ngay / Xóa tất cả.

![Hình 4. Minh chứng chống ghi đè & lưu tạm TTL 15 phút (cô lập theo phiên st_sid): hai lượt tải liên tiếp cùng ảnh thật mount_st_helens_1.png (1,05 MiB) + sidecar mount_st_helens_1.json được cách ly vào hai thư mục UUID4 độc lập (data/user_uploads/e52cbdbd8d734c9d/ và data/user_uploads/544f376c3bd74dce/) kèm đếm ngược TTL và nút Xóa ngay / Xóa tất cả.](stage2_evidence/ev3_upload_ttl_and_zero_overwrite.png)

### Hình 5. Minh chứng quyền xóa dữ liệu tức thì & tự xóa ephemeral: sau khi bấm Xóa ngay (USER_DELETE_SINGLE cho phiên e52cbdbd8d734c9d, 7 tệp) và Xóa toàn bộ (USER_DELETE_ALL cho phiên 544f376c3bd74dce, 7 tệp) cùng phiên ephemeral trước đó (EPHEMERAL_AUTO_DELETE cho Alt60 phiên 51e66d6603744123, 6 tệp), thư mục data/user_uploads/ xác minh trống hoàn toàn (0 ảnh tạm trên đĩa, chân trang hiển thị gọn Δθ 49.506″ < 178.8″).

![Hình 5. Minh chứng quyền xóa dữ liệu tức thì & tự xóa ephemeral: sau khi bấm Xóa ngay (USER_DELETE_SINGLE cho phiên e52cbdbd8d734c9d, 7 tệp) và Xóa toàn bộ (USER_DELETE_ALL cho phiên 544f376c3bd74dce, 7 tệp) cùng phiên ephemeral trước đó (EPHEMERAL_AUTO_DELETE cho Alt60 phiên 51e66d6603744123, 6 tệp), thư mục data/user_uploads/ xác minh trống hoàn toàn (0 ảnh tạm trên đĩa, chân trang hiển thị gọn Δθ 49.506″ < 178.8″).](stage2_evidence/ev4_delete_verified_empty.png)

---

## 5. Nhật ký Mode Thực thi, Kiểm chứng Xóa Dữ liệu & Cô lập Phiên (`GET /api/execution-log`)

Chuỗi kiểm chứng trực tiếp trên trình duyệt Chromium (`stage2_evidence/live_execution_log.json`, `0` lỗi console/`pageerror`, chân trang `< 178.8″` và `ĐH Đà Nẵng` không tràn/cắt):
- **Phiên `ephemeral` (0s sau xử lý):** tải `2019-07-29T204726_Alt60_Azi-135_Try1.tiff` → slot `51e66d6603744123` → `EPHEMERAL_AUTO_DELETE` (`verified_gone=True`, xóa sạch 6 tệp ngay trong `finally:`).
- **Chống ghi đè & xóa tức thì ở `ttl` (15 phút):** tải 2 lượt liên tiếp cùng tệp `mount_st_helens_1.png + mount_st_helens_1.json` → 2 thư mục UUID4 độc lập `e52cbdbd8d734c9d` và `544f376c3bd74dce` (cả 2 preview `HTTP 200`); xóa đơn `DELETE /api/uploads/e52cbdbd8d734c9d` → `USER_DELETE_SINGLE` (7 tệp, preview slot 1 trả `404` ngay trong khi slot 2 vẫn `200`); xóa toàn bộ `DELETE /api/uploads` → `USER_DELETE_ALL` (7 tệp, preview slot 2 trả `404`, `uploads_remaining=0`, `disk_leftover_files=[]`, xóa sạch DOM `#compare3d-img`).
- **Kiểm chứng chống IDOR & chống lộ nhật ký trên trình duyệt B (phiên `st_sid` khác):** `GET /api/uploads -> 0 phiên`, `GET /api/uploads/<id>/preview/... -> 404`, `DELETE /api/uploads/<id> -> 404`, `GET /output/execution_log.jsonl -> 404`, số bản ghi upload/xóa của trình duyệt A rò sang trình duyệt B = **`0`**.

```json
[
  {
    "action": "USER_DELETE_ALL",
    "deleted_files": [
      "544f376c3bd74dce/demo_clean.png",
      "544f376c3bd74dce/demo_input.png",
      "544f376c3bd74dce/demo_output.png",
      "544f376c3bd74dce/demo_result.png",
      "544f376c3bd74dce/img_mount_st_helens_1.png",
      "544f376c3bd74dce/meta.json",
      "544f376c3bd74dce/sidecar_mount_st_helens_1.json"
    ],
    "endpoint": "DELETE /api/uploads",
    "event_id": "019bf3563e10",
    "event_type": "DATA_DELETION",
    "n_deleted_files": 7,
    "owner_sid_hash": "3227d884af98a311",
    "timestamp_epoch": 1795835892.317,
    "timestamp_utc": "2026-11-28T03:18:12Z",
    "upload_id": null,
    "verified_gone": true
  },
  {
    "action": "USER_DELETE_SINGLE",
    "deleted_files": [
      "demo_clean.png",
      "demo_input.png",
      "demo_output.png",
      "demo_result.png",
      "img_mount_st_helens_1.png",
      "meta.json",
      "sidecar_mount_st_helens_1.json"
    ],
    "endpoint": "DELETE /api/uploads/e52cbdbd8d734c9d",
    "event_id": "fb3119d7426f",
    "event_type": "DATA_DELETION",
    "n_deleted_files": 7,
    "owner_sid_hash": "3227d884af98a311",
    "timestamp_epoch": 1795835891.566,
    "timestamp_utc": "2026-11-28T03:18:11Z",
    "upload_id": "e52cbdbd8d734c9d",
    "verified_gone": true
  },
  {
    "auto_router_reason": "CoG khóa thành công tốc độ cao",
    "auto_router_selected": "classical",
    "auto_router_used": true,
    "checkpoint_sha256": "e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062",
    "checkpoint_status": "verified",
    "deleted_immediately": false,
    "endpoint": "/api/run-upload",
    "event_id": "b5e64efca4f7",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 276.4,
    "mode_summary": "auto -> classical [FAST_COG]",
    "n_detected": 106,
    "n_valid_pairs": 83,
    "owner_sid_hash": "3227d884af98a311",
    "reject_code": null,
    "requested_backend": "auto",
    "retention_mode": "ttl",
    "source_name": "mount_st_helens_1.png",
    "source_type": "upload",
    "status": "SOLVED",
    "timestamp_epoch": 1795835887.034,
    "timestamp_utc": "2026-11-28T03:18:07Z",
    "upload_id": "544f376c3bd74dce"
  },
  {
    "auto_router_reason": "CoG khóa thành công tốc độ cao",
    "auto_router_selected": "classical",
    "auto_router_used": true,
    "checkpoint_sha256": "e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062",
    "checkpoint_status": "verified",
    "deleted_immediately": false,
    "endpoint": "/api/run-upload",
    "event_id": "d192d6c890d6",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 240.7,
    "mode_summary": "auto -> classical [FAST_COG]",
    "n_detected": 106,
    "n_valid_pairs": 83,
    "owner_sid_hash": "3227d884af98a311",
    "reject_code": null,
    "requested_backend": "auto",
    "retention_mode": "ttl",
    "source_name": "mount_st_helens_1.png",
    "source_type": "upload",
    "status": "SOLVED",
    "timestamp_epoch": 1795835884.081,
    "timestamp_utc": "2026-11-28T03:18:04Z",
    "upload_id": "e52cbdbd8d734c9d"
  },
  {
    "auto_router_reason": "CoG khóa thành công tốc độ cao",
    "auto_router_selected": "classical",
    "auto_router_used": true,
    "checkpoint_sha256": "e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062",
    "checkpoint_status": "verified",
    "deleted_immediately": true,
    "endpoint": "/api/run-upload",
    "event_id": "feef8060e85a",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 60.77,
    "mode_summary": "auto -> classical [FAST_COG]",
    "n_detected": 14,
    "n_valid_pairs": 9,
    "owner_sid_hash": "3227d884af98a311",
    "reject_code": null,
    "requested_backend": "auto",
    "retention_mode": "ephemeral",
    "source_name": "2019-07-29T204726_Alt60_Azi-135_Try1.tiff",
    "source_type": "upload",
    "status": "SOLVED",
    "timestamp_epoch": 1795835880.571,
    "timestamp_utc": "2026-11-28T03:18:00Z",
    "upload_id": "51e66d6603744123"
  },
  {
    "action": "EPHEMERAL_AUTO_DELETE",
    "deleted_files": [
      "demo_clean.png",
      "demo_input.png",
      "demo_output.png",
      "demo_result.png",
      "img_2019-07-29T204726_Alt60_Azi-135_Try1.tiff",
      "meta.json"
    ],
    "endpoint": "/api/run-upload",
    "event_id": "14ad1ce04ccc",
    "event_type": "DATA_DELETION",
    "n_deleted_files": 6,
    "owner_sid_hash": "3227d884af98a311",
    "timestamp_epoch": 1795835880.57,
    "timestamp_utc": "2026-11-28T03:18:00Z",
    "upload_id": "51e66d6603744123",
    "verified_gone": true
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_sha256": null,
    "checkpoint_status": "simulated_missing",
    "deleted_immediately": null,
    "endpoint": "/api/run",
    "event_id": "cdaf329941dd",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": "FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt",
    "fallback_triggered": true,
    "latency_ms": 105.55,
    "mode_summary": "cnn -> classical [FALLBACK_TO_COG]",
    "n_detected": 36,
    "n_valid_pairs": 36,
    "owner_sid_hash": null,
    "reject_code": null,
    "requested_backend": "cnn",
    "retention_mode": null,
    "source_name": "seed=42",
    "source_type": "simulator",
    "status": "SOLVED",
    "timestamp_epoch": 1795835878.016,
    "timestamp_utc": "2026-11-28T03:17:58Z",
    "upload_id": null
  },
  {
    "auto_router_reason": "CoG trả LOST [INSUFFICIENT_INLIER_PAIRS] → thử nâng cấp CNN nhưng lỗi checkpoint (FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt) → FALLBACK về CoG",
    "auto_router_selected": "classical",
    "auto_router_used": true,
    "checkpoint_sha256": null,
    "checkpoint_status": "simulated_missing",
    "deleted_immediately": null,
    "endpoint": "/api/run",
    "event_id": "484945a88745",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": "FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt",
    "fallback_triggered": true,
    "latency_ms": 339.37,
    "mode_summary": "auto -> classical [FALLBACK_TO_COG]",
    "n_detected": 4,
    "n_valid_pairs": 3,
    "owner_sid_hash": null,
    "reject_code": "INSUFFICIENT_INLIER_PAIRS",
    "requested_backend": "auto",
    "retention_mode": null,
    "source_name": "nightsky_june16_2021.npy",
    "source_type": "dataset",
    "status": "LOST",
    "timestamp_epoch": 1795835877.513,
    "timestamp_utc": "2026-11-28T03:17:57Z",
    "upload_id": null
  },
  {
    "auto_router_reason": "CoG trả LOST [INSUFFICIENT_INLIER_PAIRS] → tự động chuyển sang CNN-Hybrid",
    "auto_router_selected": "cnn",
    "auto_router_used": true,
    "checkpoint_sha256": "e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062",
    "checkpoint_status": "verified",
    "deleted_immediately": null,
    "endpoint": "/api/run",
    "event_id": "5c149811219b",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "cnn_hybrid",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 480.1,
    "mode_summary": "auto -> cnn_hybrid [AUTO_ESCALATED]",
    "n_detected": 8,
    "n_valid_pairs": 8,
    "owner_sid_hash": null,
    "reject_code": null,
    "requested_backend": "auto",
    "retention_mode": null,
    "source_name": "nightsky_june16_2021.npy",
    "source_type": "dataset",
    "status": "SOLVED",
    "timestamp_epoch": 1795835875.278,
    "timestamp_utc": "2026-11-28T03:17:55Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_sha256": "e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062",
    "checkpoint_status": "verified",
    "deleted_immediately": null,
    "endpoint": "/api/run",
    "event_id": "d21ce8efb5cf",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "cnn_hybrid",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 5896.49,
    "mode_summary": "cnn -> cnn_hybrid [DIRECT]",
    "n_detected": 77,
    "n_valid_pairs": 72,
    "owner_sid_hash": null,
    "reject_code": null,
    "requested_backend": "cnn",
    "retention_mode": null,
    "source_name": "mount_st_helens_1.png",
    "source_type": "dataset",
    "status": "SOLVED",
    "timestamp_epoch": 1795835873.774,
    "timestamp_utc": "2026-11-28T03:17:53Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_sha256": "e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062",
    "checkpoint_status": "verified",
    "deleted_immediately": null,
    "endpoint": "/api/run",
    "event_id": "228ae42b31be",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 111.52,
    "mode_summary": "classical -> classical [DIRECT]",
    "n_detected": 14,
    "n_valid_pairs": 9,
    "owner_sid_hash": null,
    "reject_code": null,
    "requested_backend": "classical",
    "retention_mode": null,
    "source_name": "2019-07-29T204726_Alt60_Azi-135_Try1.tiff",
    "source_type": "dataset",
    "status": "SOLVED",
    "timestamp_epoch": 1795835863.269,
    "timestamp_utc": "2026-11-28T03:17:43Z",
    "upload_id": null
  }
]
```

---

## 6. Kết quả Bộ kiểm thử tự động (`pytest`) & Smoke Test triển khai trên VPS ARM64

- **Bộ kiểm thử tự động toàn dự án (`pytest -q`):** **`151 passed, 1 skipped in 80.62s (0:01:20)`** (0 lỗi), bao gồm **17 bài kiểm thử chuyên biệt Chặng 2** trong [`tests/test_stage2_repro_and_privacy.py`](../tests/test_stage2_repro_and_privacy.py): (1) SHA-256 13/13, (2) `/api/repro-status` & Fallback CoG không lộ đường dẫn OS, (3) `ephemeral` preview inline base64 + không ghi đè `mount_st_helens_1.png`, (4) tải 2 tệp trùng tên `ttl` sinh 2 UUID riêng + preview `200 → 404` sau `DELETE` + `TTL_EXPIRED_AUTO_PURGE`, (5) Auto-Router Fallback trên Zhao, (6) 0 byte NUL UTF-8 trên báo cáo/minh chứng, (7) chặn checkpoint sửa 1 byte trước `torch.load` (`CHECKPOINT_SHA256_MISMATCH`), (8) CLI `--focal-mm/--pixel-um/--k1` trên ảnh thật `Alt60`, (9) rollback 0 tệp mồ côi khi lỗi HTTP 400 ở `ttl`, (10) cô lập phiên `st_sid` Browser A vs B, (11) `checkpoint_status` & `checkpoint_sha256` + ghi nguyên tử JSONL trên `/api/compare` & `/api/compare-upload`, (12) chặn `GET /output/*.jsonl` & path traversal (`404`), (13) cô lập `/api/execution-log` theo `owner_sid_hash` (không lộ tên tệp/sidecar sang phiên khác, không ghi raw `st_sid` ra đĩa), (14) upload không cookie tự cấp `st_sid` + luôn ghi `meta.json` (cả `ephemeral`) chặn IDOR & giữ hậu tố tên tệp không phải Latin (`星空.png`), (15) quét dọn slot `ephemeral` mồ côi ngay khi khởi động (`_run_startup_sweep`) & lazy TTL purge, (16) rollback lỗi ở `ephemeral` (`ERROR_ROLLBACK_DELETE`) & retry `os.replace` khi gặp `PermissionError` khóa tệp trên Windows, và (17) `/api/compare` nhánh `auto` với checkpoint sửa 1 byte (`checksum_mismatch`) & checkpoint cụt `<1 MB` (`corrupted_truncated`) không gọi `torch.load`.
- **Nhật ký triển khai Docker ARM64 & kiểm chứng HTTPS trên VPS (`https://startracker.agentlens.dpdns.org`, tệp `stage2_evidence/vps_deploy_and_smoke.txt`):**

```text
# DUT.StarTracker Stage 2 VPS Deploy & Live HTTPS Verification Log
# Timestamp (UTC): 2026-11-28T03:50:25Z
# Source Commit: 3c6d5a6 (main, v1.2.0-stage2)

=== [1/2] ARM64 VPS DOCKER DEPLOY & INTERNAL SMOKE ===
[1/4] Packed LF-normalized 3c6d5a6 app bundle (528.8 KB) + runtime_data LF delta (1,339.7 KB).
[2/4] Synced code to /opt/star-tracker/app & LF data delta to /opt/star-tracker/runtime_data in 5.97s (staged data/sim_dataset/ preserved).
[3/4] Built star-tracker:latest (sha256:a893244a7708) & started container star-tracker in 4s.
[4/4] Running internal container & Docker-network checks...
[PASS] docker exec star-tracker python scripts/verify_repro_bundle.py -> verified=13/13 (36.02 MB) | checkpoint=verified | ok=True
[PASS] Local container health (http://127.0.0.1:8765/api/health) -> {"ok":true,"service":"star-tracker"}
[PASS] Docker DNS on agentlens_agentlens (http://star-tracker:8765/api/health) -> {"ok":true,"service":"star-tracker"}
=== Running Containers on VPS ===
NAMES                     STATUS                  IMAGE                                   NETWORKS              PORTS
star-tracker              Up 2 seconds            star-tracker:latest                     agentlens_agentlens   127.0.0.1:8765->8765/tcp
lunar-navigator           Up 13 days              nginx:alpine                            agentlens_agentlens   127.0.0.1:8088->80/tcp
multi-agent-blog          Up 3 months (healthy)   multi-agent-blog:latest                 blog-writer_default   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
agentlens-cloudflared-1   Up 3 months             cloudflare/cloudflared:latest
agentlens-gateway-1       Up 3 months             caddy:2.10-alpine                       agentlens_agentlens   80/tcp, 443/tcp, 2019/tcp, 443/udp
agentlens-backend-1       Up 3 months (healthy)   agentlens/backend:dev                   agentlens_agentlens   8000/tcp
agentlens-frontend-1      Up 3 months (healthy)   agentlens/frontend:prod-20260825-1046   agentlens_agentlens   3000/tcp
agentlens-worker-1        Up 3 months (healthy)   agentlens/backend:dev                   agentlens_agentlens   8000/tcp
agentlens-postgres-1      Up 3 months (healthy)   pgvector/pgvector:pg16                  agentlens_agentlens   5432/tcp
=== DEPLOY COMPLETE in 13.47s total ===

=== [2/2] PUBLIC HTTPS VERIFICATION (https://startracker.agentlens.dpdns.org) ===
[PASS] GET /api/health -> 200 in 0.85s: {'ok': True, 'service': 'star-tracker'}
[PASS] GET / -> 200 (75,763 bytes) | st_sid issued (HttpOnly, SameSite=Lax, distinct sessions)
[PASS] GET /api/frames -> 200 (17 staged frames)
[PASS] GET /api/sky-catalog -> 200 (source=BSC5+filt, synthetic=False, n=5023, named=462)
[PASS] GET /api/repro-status -> ok=True (13/13 verified, 36.02 MB, checkpoint=verified, preview_isolation=True, session_isolation=True, error_rollback=True, sweeper=60s)
[PASS] GET /static/app.js -> 200 (140,504 bytes) | SHA-256=514d9ed372bb5ac0... (100% match with 3c6d5a6)
[PASS] GET /static/app.css -> 200 (68,830 bytes) | SHA-256=f48dec48276eff5f... (100% match with 3c6d5a6)
[PASS] GET /output/execution_log.jsonl -> HTTP 404 (raw JSONL download blocked)
[PASS] GET /output/..%2f..%2fapp.py -> HTTP 400 (blocked safely, never 500)
[PASS] POST /api/run (seed=42 classical) -> SOLVED in 1.39s (n_matched=36, att_err=0.45")
[PASS] POST /api/run (tetra3 Alt60 real frame) -> SOLVED in 0.55s (n_matched=9)
[PASS] POST /api/run (Zhao nightsky Auto-Router) -> SOLVED in 2.73s (selected=cnn, n_matched=8)
[PASS] POST /api/run (cnn simulate_missing_weights=True) -> cnn -> classical [FALLBACK_TO_COG] | checkpoint_status=simulated_missing | reason=FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt
[PASS] POST /api/run (Zhao auto simulate_missing_weights=True) -> auto -> classical [FALLBACK_TO_COG] | status=LOST | reason=FileNotFoundError: missing public weights: third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt
[PASS] Live ephemeral upload (581bf38d62db4c30) -> inline base64 preview (890 chars), deleted_immediately=True, verified_gone=True | Browser A log sees own entries (2), Browser B log leak=0
[PASS] Live TTL error rollback -> HTTP 400 rolled back cleanly (0 orphan uploads on disk)
[PASS] Live session isolation (7e1451430ca34435) -> Browser A preview 200 | Browser B list=0 & preview/DELETE 404 | Browser A DELETE verified_gone=True -> preview 404
[PASS] Live cookieless anti-IDOR (ab06f4888eb44588) -> auto-minted st_sid (session_scoped=True) | Browser B preview/DELETE 404 | Owner DELETE verified_gone=True -> preview 404 | active=0
[PASS] Raw Evidence MD UTF-8    -> HTTP 200 (48,492 bytes) | utf8=OK nul_bytes=0
[PASS] Raw Report PDF           -> HTTP 200 (1,440,866 bytes)
[PASS] Raw Checksums            -> HTTP 200 (1,578 bytes) | utf8=OK nul_bytes=0
[PASS] Raw Diagram PNG          -> HTTP 200 (660,556 bytes)

[ALL LIVE PUBLIC HTTPS CHECKS PASSED 100%]
```

---

## 7. Khai báo trung thực phạm vi & công cụ hỗ trợ

- Hệ thống định vị ở **mức thử nghiệm phần mềm trên PC / ARM64 (NASA TRL 3–4)**, không tuyên bố đạt chuẩn bay vệ tinh thực tế.
- Trong Chặng 2 (Hackathon), đội sử dụng trợ lý lập trình AI (Google Antigravity / Gemini) hỗ trợ triển khai cấu trúc gói tái lập, kiểm tra SHA-256, phân vùng lưu ảnh tạm UUID4/TTL, bảo vệ cô lập phiên `st_sid`, ghi nhật ký JSONL nguyên tử, cập nhật Web UI và đồng bộ tài liệu. Toàn bộ kiểm thử thực tế, chạy bản clone sạch đa nền tảng, kiểm tra trực tiếp trên giao diện và đối chiếu số liệu được thực hiện trực tiếp trên mã nguồn và chịu trách nhiệm bởi đội thi.
