# MINH CHỨNG CẢI TIẾN VÒNG CHUNG KẾT · CHẶNG 2 (HACKATHON)

> **Đội thi:** `DUT.StarTracker` (`AI26C0083`) · Bảng C · Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin  
> **Ngày kiểm chứng:** `28/11/2026` · **Phiên bản mã nguồn:** `v1.2.0-stage2` (nhánh `main`, commit nền `e38c899`)  
> **Đề cải tiến Chặng 2 (Phiên bản 1):** *1. Tái lập pipeline và kiểm soát dữ liệu ảnh*  
> **Sản phẩm trực tuyến 24/7:** https://startracker.agentlens.dpdns.org  
> **Hướng dẫn tái lập từ bản clone sạch:** [`REPRODUCIBILITY.md`](../REPRODUCIBILITY.md) · **Bảng Checksum:** [`CHECKSUMS.sha256`](../CHECKSUMS.sha256)

---

## 1. Bảng đối chiếu 3 minh chứng bắt buộc của Đề Chặng 2

| Yêu cầu minh chứng trong Đề Chặng 2 | Bằng chứng trực tiếp trong tài liệu này | Đường dẫn xác thực trực tiếp |
|---|---|---|
| **(1) Hướng dẫn chạy từ bản tải sạch** (checkpoint, ảnh mẫu, checksum, hiệu chuẩn, lệnh benchmark) | Bảng 13/13 tệp SHA-256 (`36,03 MB`), lệnh chạy 1 bước & **log terminal thực tế chạy trên bản `git clone` sạch mới hoàn toàn** (Mục 2 & Mục 3) | [`REPRODUCIBILITY.md`](../REPRODUCIBILITY.md), [`CHECKSUMS.sha256`](../CHECKSUMS.sha256), [`scripts/run_clean_repro.py`](../scripts/run_clean_repro.py) |
| **(2) Log mode thực thi & báo rõ Fallback CoG** | Nhật ký JSONL có cấu trúc (`requested_backend` vs `executed_backend`, `FALLBACK_TO_COG`, `fallback_reason`), ảnh chụp dải cảnh báo cam trực tuyến trên Web UI (Hình 1–2 & Mục 4) | `GET /api/execution-log`, `data/outputs/execution_log.jsonl`, [`src/execution_log.py`](../src/execution_log.py) |
| **(3) Demo kiểm soát dữ liệu ảnh, chống ghi đè & xóa dữ liệu** | Chính sách `data/user_uploads/<uuid4>/`, mặc định xóa ngay `0s` (`ephemeral`) + chế độ `ttl` 15 phút, chống ghi đè 2 ảnh trùng tên & ảnh chụp xóa xác minh trống đĩa (Hình 3–4 & Mục 5) | `GET /api/uploads`, `DELETE /api/uploads/<id>`, `DELETE /api/uploads`, [`src/upload_store.py`](../src/upload_store.py) |

---

## 2. Kiểm chứng toàn vẹn 13/13 tệp Gói Tái lập Độc lập (`CHECKSUMS.sha256`)

Tổng dung lượng gói tái lập đóng gói trực tiếp trong kho Git (không cần Git LFS, mọi tệp đều `< 19 MB`): **`36.03 MB`** (`13/13` hợp lệ, `checkpoint_status=verified`).

| Nhóm | Đường dẫn tệp trong kho | Kích thước | SHA-256 (24 ký tự đầu) | Trạng thái |
|---|---|---:|---|---|
| Checkpoint CNN | `third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt` | 17.71 MB | `e02d7723b832d12cf2535a8a…` | **verified** |
| Ảnh trời thật | `data/tetra3/2019-07-29T204726_Alt40_Azi-135_Try1.tiff` | 1.50 MB | `f5d6c27ac7e8e2114fbeb451…` | **verified** |
| Ảnh trời thật | `data/tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff` | 1.50 MB | `f288f6e1fb3a1299626956e3…` | **verified** |
| Ảnh trời thật | `data/real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy` | 2.34 MB | `57ec7838e430900b438c7217…` | **verified** |
| Ảnh trời thật | `data/real_calibrated/zhao_mt9v022/verification_img.npy` | 2.34 MB | `b9a413dc087ccea0d6c68224…` | **verified** |
| Ảnh trời thật | `data/uploads/mount_st_helens_1.png` | 1.05 MB | `f29437dbb96e70cbeda5a9ea…` | **verified** |
| Ảnh trời thật | `data/uploads/real_sky/images/0006.png` | 9.12 MB | `9a699a274af866bd6a7928c7…` | **verified** |
| Hiệu chuẩn / Config | `data/real_calibrated/manifest_real_calibrated.json` | 132.7 KB | `07f8ecfc87adc1dcbd2e5e25…` | **verified** |
| Hiệu chuẩn / Config | `data/uploads/real_sky/metadata.yaml` | 3.2 KB | `25aafd40039ddbcd0cfa9207…` | **verified** |
| Hiệu chuẩn / Config | `config/camera_specs.json` | 1.5 KB | `205e15f2b3e0a75eb989f5b0…` | **verified** |
| Hiệu chuẩn / Config | `config/pipeline_default.json` | 1.4 KB | `a91838711f4bb881bb97bc9f…` | **verified** |
| Danh mục sao | `data/catalogs/BSC5` | 284.7 KB | `e471d02eaf4eecb61c12f879…` | **verified** |
| Danh mục sao | `data/catalogs/IAU-CSN.txt` | 50.8 KB | `8b99bae659fbfe8dcb35845b…` | **verified** |

---

## 3. Bằng chứng chạy thực tế từ bản `git clone` sạch (Clean-Clone Verification Log)

Đội đã thực hiện **`git clone`** thực sự từ kho `e:\SangTaoTreQG` sang một thư mục tạm hoàn toàn trống (không copy bất kỳ tệp trung gian hay cache nào từ máy phát triển) và chạy hai lệnh kiểm chứng:

```bash
python scripts/verify_repro_bundle.py
python scripts/run_clean_repro.py
```

### Kết quả stdout nguyên văn từ bản clone sạch:

```text
=== Clean Git Clone Verification ===
$ git clone . C:\Users\ADMIN\AppData\Local\Temp\star_tracker_clean_clone_stage2
Cloning into 'C:\Users\ADMIN\AppData\Local\Temp\star_tracker_clean_clone_stage2'...
done.

$ python scripts/verify_repro_bundle.py
  [PASS] checkpoint      third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt ( 18137.5 KB) sha256=e02d7723b832d12c...
  [PASS] sample_real_sky data/tetra3/2019-07-29T204726_Alt40_Azi-135_Try1.tiff          (  1536.3 KB) sha256=f5d6c27ac7e8e211...
  [PASS] sample_real_sky data/tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff          (  1536.3 KB) sha256=f288f6e1fb3a1299...
  [PASS] sample_real_sky data/real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy     (  2400.1 KB) sha256=57ec7838e430900b...
  [PASS] sample_real_sky data/real_calibrated/zhao_mt9v022/verification_img.npy         (  2400.1 KB) sha256=b9a413dc087ccea0...
  [PASS] sample_real_sky data/uploads/mount_st_helens_1.png                             (  1070.3 KB) sha256=f29437dbb96e70cb...
  [PASS] sample_real_sky data/uploads/real_sky/images/0006.png                          (  9337.9 KB) sha256=9a699a274af866bd...
  [PASS] calibration     data/real_calibrated/manifest_real_calibrated.json             (   132.7 KB) sha256=07f8ecfc87adc1dc...
  [PASS] calibration     data/uploads/real_sky/metadata.yaml                            (     3.2 KB) sha256=25aafd40039ddbcd...
  [PASS] calibration     config/camera_specs.json                                       (     1.5 KB) sha256=205e15f2b3e0a75e...
  [PASS] calibration     config/pipeline_default.json                                   (     1.4 KB) sha256=a91838711f4bb881...
  [PASS] catalog         data/catalogs/BSC5                                             (   284.7 KB) sha256=e471d02eaf4eecb6...
  [PASS] catalog         data/catalogs/IAU-CSN.txt                                      (    50.8 KB) sha256=8b99bae659fbfe8d...

[SUMMARY] verified=13/13 (36.03 MB) | checkpoint=verified | ok=True

$ python scripts/run_clean_repro.py
=== [1/4] Verifying SHA-256 Checksums (CHECKSUMS.sha256) ===
  Verified: 13/13 (36.03 MB) | ok=True
  Checkpoint SHA-256: e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062

=== [2/4] Clean-Clone Pipeline Runs (Seed 42 + Calibrated Real-Sky) ===
Building angle table 0.02-30.5 deg for BSC5+filt (first time, then cached).
  [seed42_auto           ] req=auto -> exe=classical | fallback=False | SOLVED | pairs=36 | dTh=0.4463370537767079 | t=97.56930000003194ms
  [esa_alt60_auto        ] req=auto -> exe=classical | fallback=False | SOLVED | pairs=9 | dTh=None | t=65.54270000015094ms
  [zhao_nightsky_auto    ] req=auto -> exe=cnn_hybrid | fallback=False | SOLVED | pairs=8 | dTh=None | t=3138.432499999908ms
Building angle table 0.02-71.5 deg for BSC5+filt (first time, then cached).
  [mount_st_helens_cnn   ] req=cnn -> exe=cnn_hybrid | fallback=False | SOLVED | pairs=72 | dTh=None | t=329.8821000003045ms

=== [3/4] Explicit CNN -> CoG Fallback Proof (Simulated Missing Checkpoint) ===
  [FALLBACK PROOF] req=cnn -> exe=classical | fallback=True | reason=FileNotFoundError: missing public weights: C:\Users\ADMIN\AppData\Local\Temp\star_tracker_clean_clone_stage2\third_party\cnn_star_centroid\saved_models\__simulated_missing_checkpoint__.pt | status=SOLVED

=== [4/4] Upload Isolation (Zero-Overwrite) & Verified Deletion Proof ===
  [DATA CONTROL] Same filename -> isolated UUIDs (a9633fcb3edf4b0a, 3a7e343c72af433d); deleted & verified_gone=True; remaining=0

[PASS] Clean-clone reproducibility & data-control audit completed in 6.67s -> C:\Users\ADMIN\AppData\Local\Temp\star_tracker_clean_clone_stage2\data\outputs\clean_repro_log.json
```

### Tóm tắt kết quả định lượng từ bản clone sạch (`clean_repro_log.json`):

| Ca kiểm chứng tái lập | Chế độ yêu cầu → Thực thi | Trạng thái | Cặp sao hợp lệ | Sai số / Thời gian |
|---|---|---|---|---|
| `seed42_auto` | `auto -> classical` | **SOLVED** | `36 sao` | Δθ 0.45″ · `97.6 ms` |
| `esa_alt60_auto` | `auto -> classical` | **SOLVED** | `9 sao` | Không có GT góc · `65.5 ms` |
| `zhao_nightsky_auto` | `auto -> cnn_hybrid` | **SOLVED** | `8 sao` | Không có GT góc · `3138.4 ms` |
| `mount_st_helens_cnn` | `cnn -> cnn_hybrid` | **SOLVED** | `72 sao` | Không có GT góc · `329.9 ms` |
| `fallback_missing_checkpoint` | `cnn -> classical [FALLBACK_TO_COG]` | **SOLVED** (`fallback=True`) | `36 sao` | Lý do: `FileNotFoundError: missing public weights: C:\Users\ADMIN\AppData\Local\Temp\star_tracker_clean_clone_stage2\third_party\cnn_star_centroid\saved_models\__simulated_missing_checkpoint__.pt` |
| `upload_isolation_and_delete` | `same filename (mount_st_helens_1.png)` | **VERIFIED** (`remaining=0`) | 2 UUID: `a9633fcb3edf4b0a`, `3a7e343c72af433d` | Chống ghi đè & xóa sạch đĩa (`bundled_untouched=True`) |

---

## 4. Minh chứng trực tiếp trên hệ thống trực tuyến 24/7 (`https://startracker.agentlens.dpdns.org`)

### Hình 1. Giao diện trực tuyến (https://startracker.agentlens.dpdns.org) — Tab Cấu hình, Checksum & Dữ liệu xác thực 13/13 tệp SHA-256 (36,03 MB) và hiển thị nhật ký thực thi thời gian thực.

![Hình 1. Giao diện trực tuyến (https://startracker.agentlens.dpdns.org) — Tab Cấu hình, Checksum & Dữ liệu xác thực 13/13 tệp SHA-256 (36,03 MB) và hiển thị nhật ký thực thi thời gian thực.](stage2_evidence/ev1_repro_checksums_and_audit_log.png)

### Hình 2. Minh chứng cơ chế báo rõ Fallback CNN → CoG: bấm "Thử nghiệm Fallback CNN → CoG" kích hoạt dải cảnh báo màu cam phía trên cùng và ghi sự kiện FALLBACK_TO_COG kèm nguyên nhân FileNotFoundError vào execution_log.jsonl.

![Hình 2. Minh chứng cơ chế báo rõ Fallback CNN → CoG: bấm "Thử nghiệm Fallback CNN → CoG" kích hoạt dải cảnh báo màu cam phía trên cùng và ghi sự kiện FALLBACK_TO_COG kèm nguyên nhân FileNotFoundError vào execution_log.jsonl.](stage2_evidence/ev2_fallback_cog_banner.png)

### Hình 3. Minh chứng chống ghi đè & lưu tạm TTL 15 phút: hai lượt tải cùng tên tệp được tách vào hai thư mục UUID4 độc lập trong data/user_uploads/<upload_id>/ kèm đếm ngược TTL và nút Xóa ngay.

![Hình 3. Minh chứng chống ghi đè & lưu tạm TTL 15 phút: hai lượt tải cùng tên tệp được tách vào hai thư mục UUID4 độc lập trong data/user_uploads/<upload_id>/ kèm đếm ngược TTL và nút Xóa ngay.](stage2_evidence/ev3_upload_ttl_and_zero_overwrite.png)

### Hình 4. Minh chứng quyền xóa dữ liệu tức thì: sau khi bấm Xóa ngay / Xóa toàn bộ ảnh tạm, thư mục data/user_uploads/ xác minh trống hoàn toàn (0 ảnh tạm trên đĩa) và ghi dấu DATA_DELETION vào nhật ký.

![Hình 4. Minh chứng quyền xóa dữ liệu tức thì: sau khi bấm Xóa ngay / Xóa toàn bộ ảnh tạm, thư mục data/user_uploads/ xác minh trống hoàn toàn (0 ảnh tạm trên đĩa) và ghi dấu DATA_DELETION vào nhật ký.](stage2_evidence/ev4_delete_verified_empty.png)

---

## 5. Nhật ký Mode Thực thi & Xóa Dữ liệu thực tế từ VPS (`GET /api/execution-log`)

Các bản ghi JSONL thực tế trích xuất trực tiếp từ `https://startracker.agentlens.dpdns.org/api/execution-log` sau khi thực hiện chuỗi thao tác kiểm chứng (Checksum → Fallback CNN→CoG → Tải 2 tệp trùng tên chế độ TTL → Xóa ngay → Xóa toàn bộ):

```json
[
  {
    "action": "USER_DELETE_ALL",
    "deleted_files": [
      "1716f7add59f4fb4/img_mount_st_helens_1.png",
      "1716f7add59f4fb4/meta.json"
    ],
    "endpoint": "DELETE /api/uploads",
    "event_id": "fa3a648bc139",
    "event_type": "DATA_DELETION",
    "n_deleted_files": 2,
    "timestamp_epoch": 1795828078.96,
    "timestamp_utc": "2026-11-28T01:07:58Z",
    "upload_id": null,
    "verified_gone": true
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "available",
    "deleted_immediately": false,
    "endpoint": "/api/run-upload",
    "event_id": "1b9994441c36",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 4.2,
    "mode_summary": "classical -> classical [DIRECT]",
    "n_detected": 1,
    "n_valid_pairs": 0,
    "reject_code": "INSUFFICIENT_DETECTIONS",
    "requested_backend": "classical",
    "retention_mode": "ttl",
    "source_name": "mount_st_helens_1.png",
    "source_type": "upload",
    "status": "LOST",
    "timestamp_epoch": 1795828078.52,
    "timestamp_utc": "2026-11-28T01:07:58Z",
    "upload_id": "1716f7add59f4fb4"
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "simulated_missing",
    "deleted_immediately": null,
    "endpoint": "/api/run",
    "event_id": "63e89028cdb1",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": "FileNotFoundError: missing public weights: /app/third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt",
    "fallback_triggered": true,
    "latency_ms": 126.48,
    "mode_summary": "cnn -> classical [FALLBACK_TO_COG]",
    "n_detected": 36,
    "n_valid_pairs": 36,
    "reject_code": null,
    "requested_backend": "cnn",
    "retention_mode": null,
    "source_name": "seed=42",
    "source_type": "simulator",
    "status": "SOLVED",
    "timestamp_epoch": 1795828052.634,
    "timestamp_utc": "2026-11-28T01:07:32Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "available",
    "deleted_immediately": null,
    "endpoint": "/api/compare",
    "event_id": "966b21e02678",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "cnn_hybrid",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 3912.69,
    "mode_summary": "cnn -> cnn_hybrid [DIRECT]",
    "n_detected": 77,
    "n_valid_pairs": 72,
    "reject_code": null,
    "requested_backend": "cnn",
    "retention_mode": null,
    "source_name": "mount_st_helens_1.png",
    "source_type": "dataset",
    "status": "SOLVED",
    "timestamp_epoch": 1795828051.971,
    "timestamp_utc": "2026-11-28T01:07:31Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "available",
    "deleted_immediately": null,
    "endpoint": "/api/compare",
    "event_id": "0c9fb1ebbecf",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "tetra3",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 2861.07,
    "mode_summary": "tetra3 -> tetra3 [DIRECT]",
    "n_detected": 80,
    "n_valid_pairs": 4,
    "reject_code": "LOW_FOV_CONSISTENCY",
    "requested_backend": "tetra3",
    "retention_mode": null,
    "source_name": "mount_st_helens_1.png",
    "source_type": "dataset",
    "status": "LOST",
    "timestamp_epoch": 1795828051.97,
    "timestamp_utc": "2026-11-28T01:07:31Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "available",
    "deleted_immediately": null,
    "endpoint": "/api/compare",
    "event_id": "9ca7531dc6c4",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 474.69,
    "mode_summary": "classical -> classical [DIRECT]",
    "n_detected": 106,
    "n_valid_pairs": 83,
    "reject_code": null,
    "requested_backend": "classical",
    "retention_mode": null,
    "source_name": "mount_st_helens_1.png",
    "source_type": "dataset",
    "status": "SOLVED",
    "timestamp_epoch": 1795828051.969,
    "timestamp_utc": "2026-11-28T01:07:31Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "available",
    "deleted_immediately": null,
    "endpoint": "/api/compare",
    "event_id": "e0502503fc04",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "cnn_hybrid",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 1190.83,
    "mode_summary": "cnn -> cnn_hybrid [DIRECT]",
    "n_detected": 8,
    "n_valid_pairs": 8,
    "reject_code": null,
    "requested_backend": "cnn",
    "retention_mode": null,
    "source_name": "nightsky_june16_2021.npy",
    "source_type": "dataset",
    "status": "SOLVED",
    "timestamp_epoch": 1795828044.385,
    "timestamp_utc": "2026-11-28T01:07:24Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "available",
    "deleted_immediately": null,
    "endpoint": "/api/compare",
    "event_id": "03a1ae7083f4",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "tetra3",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 916.03,
    "mode_summary": "tetra3 -> tetra3 [DIRECT]",
    "n_detected": 5,
    "n_valid_pairs": 5,
    "reject_code": "LOW_FOV_CONSISTENCY",
    "requested_backend": "tetra3",
    "retention_mode": null,
    "source_name": "nightsky_june16_2021.npy",
    "source_type": "dataset",
    "status": "LOST",
    "timestamp_epoch": 1795828044.384,
    "timestamp_utc": "2026-11-28T01:07:24Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "available",
    "deleted_immediately": null,
    "endpoint": "/api/compare",
    "event_id": "be635f9bda4c",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 696.61,
    "mode_summary": "classical -> classical [DIRECT]",
    "n_detected": 4,
    "n_valid_pairs": 3,
    "reject_code": "INSUFFICIENT_INLIER_PAIRS",
    "requested_backend": "classical",
    "retention_mode": null,
    "source_name": "nightsky_june16_2021.npy",
    "source_type": "dataset",
    "status": "LOST",
    "timestamp_epoch": 1795828044.384,
    "timestamp_utc": "2026-11-28T01:07:24Z",
    "upload_id": null
  },
  {
    "auto_router_reason": "CoG trả LOST [INSUFFICIENT_INLIER_PAIRS] → tự động chuyển sang CNN-Hybrid",
    "auto_router_selected": "cnn",
    "auto_router_used": true,
    "checkpoint_status": "available",
    "deleted_immediately": null,
    "endpoint": "/api/run",
    "event_id": "d0714bab681b",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "cnn_hybrid",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 1819.44,
    "mode_summary": "auto -> cnn_hybrid [AUTO_ESCALATED]",
    "n_detected": 8,
    "n_valid_pairs": 8,
    "reject_code": null,
    "requested_backend": "auto",
    "retention_mode": null,
    "source_name": "nightsky_june16_2021.npy",
    "source_type": "dataset",
    "status": "SOLVED",
    "timestamp_epoch": 1795828041.359,
    "timestamp_utc": "2026-11-28T01:07:21Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "available",
    "deleted_immediately": null,
    "endpoint": "/api/run",
    "event_id": "11bb1afac7ac",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "classical",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 100.0,
    "mode_summary": "classical -> classical [DIRECT]",
    "n_detected": 14,
    "n_valid_pairs": 9,
    "reject_code": null,
    "requested_backend": "classical",
    "retention_mode": null,
    "source_name": "2019-07-29T204726_Alt60_Azi-135_Try1.tiff",
    "source_type": "dataset",
    "status": "SOLVED",
    "timestamp_epoch": 1795828039.239,
    "timestamp_utc": "2026-11-28T01:07:19Z",
    "upload_id": null
  },
  {
    "auto_router_reason": null,
    "auto_router_selected": null,
    "auto_router_used": false,
    "checkpoint_status": "available",
    "deleted_immediately": null,
    "endpoint": "/api/run",
    "event_id": "b3ccb7425a0a",
    "event_type": "PIPELINE_RUN",
    "executed_backend": "cnn_hybrid",
    "fallback_reason": null,
    "fallback_triggered": false,
    "latency_ms": 4567.13,
    "mode_summary": "cnn -> cnn_hybrid [DIRECT]",
    "n_detected": 77,
    "n_valid_pairs": 72,
    "reject_code": null,
    "requested_backend": "cnn",
    "retention_mode": null,
    "source_name": "mount_st_helens_1.png",
    "source_type": "dataset",
    "status": "SOLVED",
    "timestamp_epoch": 1795828038.874,
    "timestamp_utc": "2026-11-28T01:07:18Z",
    "upload_id": null
  }
]
```

---

## 6. Kết quả Bộ kiểm thử tự động (`pytest`) & Smoke Test trực tuyến trên VPS

- **Bộ kiểm thử tự động (`pytest -q`):** `137 passed, 2 skipped in 66.68s` (bao gồm 4 bài kiểm thử chuyên biệt Chặng 2 trong [`tests/test_stage2_repro_and_privacy.py`](../tests/test_stage2_repro_and_privacy.py)).
- **Kết quả triển khai & smoke test 24/7 trên VPS ARM64 (`https://startracker.agentlens.dpdns.org`):**

```text
��[ 1 / 4 ]   P a c k e d   a p p l i c a t i o n   s o u r c e   b u n d l e   ( 5 0 4 . 0   K B   c o m p r e s s e d ) . 
 
 [ 2 / 4 ]   S y n c e d   c o d e   t o   / o p t / s t a r - t r a c k e r / a p p   i n   9 . 6 8 s . 
 
 [ 3 / 4 ]   B u i l t   s t a r - t r a c k e r : l a t e s t   &   s t a r t e d   c o n t a i n e r   s t a r - t r a c k e r   i n   2 . 6 0 s   ( s h a 2 5 6 : 5 4 c c 4 ) . 
 
 [ 4 / 4 ]   R u n n i n g   r e m o t e   H T T P   &   D o c k e r - n e t w o r k   s m o k e   t e s t s . . . 
 
 [ P A S S ]   G E T   / a p i / h e a l t h   - >   2 0 0   i n   0 . 2 0 s :   { ' o k ' :   T r u e ,   ' s e r v i c e ' :   ' s t a r - t r a c k e r ' } 
 
 [ P A S S ]   G E T   /   - >   2 0 0   ( 7 5 , 2 0 6   b y t e s ) 
 
 [ P A S S ]   G E T   / a p i / f r a m e s   - >   2 0 0   ( 1 7   s t a g e d   f r a m e s ) 
 
 [ P A S S ]   G E T   / a p i / s k y - c a t a l o g   - >   2 0 0   ( s o u r c e = B S C 5 + f i l t ,   s y n t h e t i c = F a l s e ,   n = 5 0 2 3 ,   n a m e d = 4 6 2 ) 
 
 [ P A S S ]   P O S T   / a p i / r u n   ( s e e d = 4 2   c l a s s i c a l )   - >   S O L V E D   i n   0 . 8 1 s   ( n _ m a t c h e d = 3 6 ,   a t t _ e r r = 0 . 4 5 " ) 
 
               G E T   / o u t p u t / d e m o _ r e s u l t . p n g   - >   2 0 0   ( 3 4 3 , 4 0 4   b y t e s ) 
 
               G E T   / o u t p u t / d e m o _ i n p u t . p n g   - >   2 0 0   ( 9 7 , 8 8 0   b y t e s ) 
 
               G E T   / o u t p u t / d e m o _ o u t p u t . p n g   - >   2 0 0   ( 1 7 0 , 3 0 0   b y t e s ) 
 
               G E T   / o u t p u t / d e m o _ c l e a n . p n g   - >   2 0 0   ( 2 1 , 7 1 1   b y t e s ) 
 
 [ P A S S ]   P O S T   / a p i / r u n   ( m o u n t _ s t _ h e l e n s _ 1 . p n g   C N N )   - >   S O L V E D   i n   5 . 2 1 s   ( d e t e c t o r = c n n _ z h a o 2 0 2 4 ,   f a l l b a c k = F a l s e ,   n _ m a t c h e d = 7 2 ,   R A = 2 0 h   4 1 m   5 8 . 2 0 s ,   D e c = + 3 5 d   5 9 m   2 7 . 9 s ) 
 
 [ P A S S ]   P O S T   / a p i / r u n   ( t e t r a 3   A l t 6 0   r e a l   f r a m e )   - >   S O L V E D   i n   0 . 3 6 s   ( n _ m a t c h e d = 9 ) 
 
 [ P A S S ]   P O S T   / a p i / r u n   ( Z h a o   n i g h t s k y   A u t o - R o u t e r )   - >   S O L V E D   i n   2 . 1 3 s   ( s e l e c t e d = c n n ) 
 
 [ P A S S ]   P O S T   / a p i / c o m p a r e   ( Z h a o   n i g h t s k y )   i n   3 . 0 2 s   - >   C o G = L O S T ,   t e t r a 3 = L O S T ,   C N N - H y b r i d = S O L V E D 
 
 [ P A S S ]   P O S T   / a p i / c o m p a r e   ( M o u n t   S t .   H e l e n s )   i n   7 . 5 9 s   - >   C o G = S O L V E D ,   t e t r a 3 = L O S T ,   C N N - H y b r i d = S O L V E D   ( 7 2 / 7 7 ) 
 
 [ P A S S ]   G E T   / a p i / b e n c h m a r k - s u m m a r y   - >   a v a i l a b l e = T r u e   s t r e s s = T r u e   d e v i c e = N V I D I A   G e F o r c e   R T X   5 0 7 0   L a p t o p   G P U 
 
 [ P A S S ]   G E T   / a p i / r e p r o - s t a t u s   - >   o k = T r u e   ( 1 3 / 1 3   v e r i f i e d ,   3 6 . 0 3   M B ) 
 
 [ P A S S ]   P O S T   / a p i / r u n   ( s i m u l a t e _ m i s s i n g _ w e i g h t s = T r u e )   - >   c n n   - >   c l a s s i c a l   [ F A L L B A C K _ T O _ C O G ]   r e a s o n = F i l e N o t F o u n d E r r o r :   m i s s i n g   p u b l i c   w e i g h t s :   / a p p / t h i r d _ p a r t y / c n n _ s t a r _ c e n t r o i d / s a v e d _ m o d e l s / _ _ s i m u l a t e d _ m i s s i n g _ c h e c k p o i n t _ _ . p t 
 
 [ P A S S ]   G E T   / a p i / e x e c u t i o n - l o g   - >   1 0   e n t r i e s   ( f a l l b a c k   l o g g e d ) 
 
 [ P A S S ]   G E T   / a p i / u p l o a d s   - >   d e f a u l t = e p h e m e r a l ,   a c t i v e = 0 
 
 [ P A S S ]   D o c k e r   D N S   o n   a g e n t l e n s _ a g e n t l e n s   ( h t t p : / / s t a r - t r a c k e r : 8 7 6 5 / a p i / h e a l t h )   - >   { " o k " : t r u e , " s e r v i c e " : " s t a r - t r a c k e r " } 
 
 = = =   R u n n i n g   C o n t a i n e r s   o n   V P S   = = = 
 
 N A M E S                                           S T A T U S                                     I M A G E                                                                       N E T W O R K S                             P O R T S 
 
 s t a r - t r a c k e r                             U p   2 7   s e c o n d s                       s t a r - t r a c k e r : l a t e s t                                           a g e n t l e n s _ a g e n t l e n s       1 2 7 . 0 . 0 . 1 : 8 7 6 5 - > 8 7 6 5 / t c p 
 
 l u n a r - n a v i g a t o r                       U p   1 3   d a y s                             n g i n x : a l p i n e                                                         a g e n t l e n s _ a g e n t l e n s       1 2 7 . 0 . 0 . 1 : 8 0 8 8 - > 8 0 / t c p 
 
 m u l t i - a g e n t - b l o g                     U p   3   m o n t h s   ( h e a l t h y )       m u l t i - a g e n t - b l o g : l a t e s t                                   b l o g - w r i t e r _ d e f a u l t       0 . 0 . 0 . 0 : 8 0 0 0 - > 8 0 0 0 / t c p ,   [ : : ] : 8 0 0 0 - > 8 0 0 0 / t c p 
 
 a g e n t l e n s - c l o u d f l a r e d - 1       U p   3   m o n t h s                           c l o u d f l a r e / c l o u d f l a r e d : l a t e s t                                                                   
 
 a g e n t l e n s - g a t e w a y - 1               U p   3   m o n t h s                           c a d d y : 2 . 1 0 - a l p i n e                                               a g e n t l e n s _ a g e n t l e n s       8 0 / t c p ,   4 4 3 / t c p ,   2 0 1 9 / t c p ,   4 4 3 / u d p 
 
 a g e n t l e n s - b a c k e n d - 1               U p   3   m o n t h s   ( h e a l t h y )       a g e n t l e n s / b a c k e n d : d e v                                       a g e n t l e n s _ a g e n t l e n s       8 0 0 0 / t c p 
 
 a g e n t l e n s - f r o n t e n d - 1             U p   3   m o n t h s   ( h e a l t h y )       a g e n t l e n s / f r o n t e n d : p r o d - 2 0 2 6 0 8 2 5 - 1 0 4 6       a g e n t l e n s _ a g e n t l e n s       3 0 0 0 / t c p 
 
 a g e n t l e n s - w o r k e r - 1                 U p   3   m o n t h s   ( h e a l t h y )       a g e n t l e n s / b a c k e n d : d e v                                       a g e n t l e n s _ a g e n t l e n s       8 0 0 0 / t c p 
 
 a g e n t l e n s - p o s t g r e s - 1             U p   3   m o n t h s   ( h e a l t h y )       p g v e c t o r / p g v e c t o r : p g 1 6                                     a g e n t l e n s _ a g e n t l e n s       5 4 3 2 / t c p 
 
 = = =   D E P L O Y   C O M P L E T E   i n   4 2 . 0 3 s   t o t a l   = = = 
 
 
```

---

## 7. Khai báo trung thực phạm vi & công cụ hỗ trợ

- Hệ thống định vị ở **mức thử nghiệm phần mềm trên PC / ARM64 (NASA TRL 3–4)**, không tuyên bố đạt chuẩn bay vệ tinh thực tế.
- Trong Chặng 2 (Hackathon), đội sử dụng trợ lý lập trình AI (Google Antigravity / Gemini) hỗ trợ triển khai cấu trúc gói tái lập, kiểm tra SHA-256, phân vùng lưu ảnh tạm UUID4/TTL, ghi nhật ký JSONL, cập nhật Web UI và đồng bộ tài liệu. Toàn bộ kiểm thử thực tế, chạy bản clone sạch, kiểm tra trên giao diện trực tuyến và đối chiếu số liệu được thực hiện trực tiếp trên mã nguồn và chịu trách nhiệm bởi đội thi.
