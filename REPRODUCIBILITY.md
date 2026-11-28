# Hướng dẫn Tái lập Độc lập từ Bản tải sạch (Clean Clone) — DUT.StarTracker (Chặng 2)

Kho mã nguồn này đã đóng gói **đầy đủ 100% gói tái lập độc lập** ngay trên nhánh `main` (tổng dung lượng gói tài nguyên **`36,02 MiB` / `37,77 MB`** = `37.773.058 byte`, mỗi tệp `< 19 MB`, không cần tải thủ công ngoài kho, khóa chuẩn kết thúc dòng **LF** qua `.gitattributes` cho cả **Linux, macOS và Windows**):
- **Checkpoint CNN (`17,71 MiB` / `18,57 MB`):** `third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt` (trọng số công khai của Hongrui Zhao et al., `arXiv:2404.19108`, không huấn luyện lại; SHA-256 `e02d7723b832d12cf2535a8a9794eaedc822023722f07da3126dcd8473cbe062`).
- **6 ảnh bầu trời thật có hiệu chuẩn:** `ESA tetra3 Alt40 & Alt60` (16-bit), `Zhao MT9V022 nightsky_june16_2021.npy & verification_img.npy` (8-bit + hiệu chuẩn méo Heikkila), `UW LOST mount_st_helens_1.png`, và `NTNU 0006.png` (ca kiểm âm tính góc siêu rộng `77,5°`).
- **Hồ sơ hiệu chuẩn & Danh mục sao:** `data/real_calibrated/manifest_real_calibrated.json`, `data/uploads/real_sky/metadata.yaml`, `config/camera_specs.json`, `config/pipeline_default.json`, `data/catalogs/BSC5`, `data/catalogs/IAU-CSN.txt`.
- **Bảng kiểm tra toàn vẹn SHA-256 & khóa LF đa nền tảng:** `CHECKSUMS.sha256` và `.gitattributes`.

---

## 1. Tải sạch & Cài đặt môi trường (Python 3.10+)

```powershell
git clone https://github.com/hoangtranduchai/star-tracker.git star-tracker-clean
cd star-tracker-clean
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Xác thực SHA-256 đa nền tảng (Linux, macOS & Windows)

```powershell
python scripts/verify_repro_bundle.py
# Hoặc bằng GNU coreutils trên Linux / macOS / Windows Git Bash:
sha256sum -c CHECKSUMS.sha256
```

Kỳ vọng: `verified=13/13 (36.02 MiB / 37.77 MB) | checkpoint=verified | ok=True` (cả trên bản clone `core.autocrlf=false` Linux/macOS lẫn `core.autocrlf=true` Windows).

## 3. Chạy xác thực tái lập 1 lệnh (ảnh thật hiệu chuẩn, Fallback CoG & Demo xóa ảnh)

```powershell
python scripts/run_clean_repro.py
```

Lệnh này tự động:
1. Kiểm tra `CHECKSUMS.sha256` (`13/13` tệp khớp LF).
2. Tự dựng bảng `K-Vector` từ `data/catalogs/BSC5` và giải tư thế trên `Seed 42 (Auto)` (`Δθ 0,45″`, `93,6 ms`), `ESA Alt60 (16-bit)` (`Δθ 2,26″`, `72,4 ms`), `Zhao nightsky (8-bit, Auto tự nâng cấp sang CNN-Hybrid)` (`Δθ 48,26″`), và `Mount St. Helens (CNN-Hybrid)` (`Δθ 71,13″`).
3. Mô phỏng thiếu checkpoint (`simulate_missing_weights=True`) trên cả `cnn` lẫn `auto` để chứng minh **Fallback CNN → CoG** có báo rõ nguyên nhân (chuẩn hóa đường dẫn tương đối) và ghi vào `data/outputs/execution_log.jsonl`.
4. Kiểm chứng tải lên 2 tệp trùng tên `mount_st_helens_1.png` vào 2 thư mục UUID4 độc lập (không ghi đè nhau, không chạm ảnh mẫu) rồi xóa sạch và xác minh đã mất khỏi đĩa (`verified_gone=True`, `remaining=0`).

## 4. Chạy bộ kiểm thử tự động & Toàn bộ Benchmark (Chạy sạch 100% từ bản clone)

```powershell
# Bộ kiểm thử hồi quy, chốt chặn chống khóa sai, tái lập & kiểm soát dữ liệu ảnh
# Kỳ vọng: 151 passed, 1 skipped (gồm 17 kiểm thử chuyên biệt Chặng 2 trong tests/test_stage2_repro_and_privacy.py)
pytest -q

# Benchmark End-to-End 5 phương pháp chạy trực tiếp trên bản tải sạch (6 ảnh trời thật hiệu chuẩn + 20 khung stress Rìa Trái Đất/mây, ~86,5 s)
python scripts/benchmark_3way_centroid_e2e.py --real-only

# Benchmark End-to-End chuẩn (ảnh trời thật hiệu chuẩn + Seed 42 + 100 ca stress từ chối khớp sai)
python scripts/benchmark_end_to_end.py --suites real seed42 stress

# Benchmark đường cong stress (vận tốc quay ω, sao giả, nền lóa)
python scripts/benchmark_stress_curves.py

# Benchmark khả thi nhúng CubeSat (mưa proton SAA, lật bit SEU CRC-16; ONNX nếu cài thêm onnxruntime)
python scripts/benchmark_embedded_cubesat.py

# Benchmark Monte Carlo 100 khung giả lập ngẫu nhiên toàn bầu trời trên BSC5
python benchmarks/monte_carlo.py --trials 100 --mode fast --catalog bsc5

# Đối soát log và tài liệu
python scripts/reconcile_logs.py
```

*(Ghi chú: Bộ 540 khung mô phỏng `hd1024` / `hd1024_glare` dung lượng ~373 MB không đóng gói vào Git để giữ repo gọn nhẹ; khi chạy không có `--real-only` trên bản tải sạch, script tự động bỏ qua nhẹ nhàng mà không crash và lưu kết quả riêng tại `data/outputs/benchmark_3way_clean_clone.json`. Có thể tái sinh 500 khung sạch `hd1024` bằng `python scripts/benchmark_centroid_cnn_hd1024.py`, 40 khung lóa `hd1024_glare` bằng `python scripts/benchmark_centroid_cnn_glare.py`, hoặc sinh bộ khung `fast`/`full` bằng `python scripts/generate_sim_dataset.py`.)*

## 5. Bảo vệ Checkpoint Runtime, Minh bạch Fallback CoG & Kiểm soát Dữ liệu Ảnh

- **Xác thực SHA-256 trước `torch.load` (`src/centroid_cnn.py`):** Trước mọi lời gọi `torch.load(..., weights_only=False)`, `inspect_checkpoint_status()` & `verify_checkpoint_integrity()` kiểm tra tồn tại tệp, phát hiện tệp cắt cụt (`CHECKPOINT_TRUNCATED`) và đối chiếu SHA-256 (`CHECKPOINT_SHA256_MISMATCH`). Nếu lệch dù chỉ 1 byte, hệ thống **chặn tuyệt đối `torch.load`** và chuyển về `CoG` tường minh với `checkpoint_status` trung thực (`verified` / `checksum_mismatch` / `corrupted_truncated` / `missing` / `simulated_missing`) cùng `checkpoint_sha256`.
- **0% Fallback ngầm trên mọi lối vào:** Cả CLI (`demo_star_tracker.py`), `/api/run`, `/api/run-upload`, `/api/compare` (kể cả `backends=["auto"]` và `["cnn"]`), `/api/compare-upload` và gói Telemetry 32 byte (`FLAG_FALLBACK_USED = 0x08`) đều báo rõ `requested_backend`, `executed_backend`, `fallback_triggered`, `fallback_reason` (đường dẫn chuẩn hóa tương đối, không lộ đường dẫn OS) và ghi vào `data/outputs/execution_log.jsonl` (ghi nguyên tử `os.replace` kèm retry Windows).
- **Bảo vệ nhật ký kiểm toán:** Tra cứu qua `GET /api/execution-log` được lọc cô lập theo phiên `st_sid` (`owner_sid_hash` đối với sự kiện upload/xóa để không lộ tên tệp giữa người dùng), đồng thời chặn truy cập trực tiếp `GET /output/*.jsonl` (trả HTTP `404`).
- **Ảnh mẫu hệ thống (chỉ đọc):** `data/uploads/` — tách biệt hoàn toàn khỏi tệp người dùng tải lên.
- **Nơi lưu ảnh người dùng, chống ghi đè & cô lập phiên chống IDOR:** `data/user_uploads/<upload_id>/` (mỗi lượt tải nhận một mã UUID4 16 ký tự duy nhất + luôn ghi `meta.json` và gắn cookie phiên `st_sid` `HttpOnly; SameSite=Lax; Secure` trên HTTPS kể cả khi gọi trực tiếp API upload) $\rightarrow$ **tuyệt đối không ghi đè** tệp trùng tên, ảnh mẫu hay `data/outputs/demo_*.png`, và người dùng khác không thể liệt kê, xem preview hay xóa tệp tạm của nhau (`HTTP 404`). Nếu gặp lỗi xử lý (`HTTP 400/409`) ở cả hai chế độ, thư mục tạm lập tức được xóa hoàn tác (`ERROR_ROLLBACK_DELETE`, 0 tệp mồ côi).
- **Thời gian lưu (2 chế độ do người dùng chọn ngay khi tải ảnh):**
  1. **`ephemeral` *(mặc định an toàn — Xóa ngay trong `finally:` / 0s sau xử lý)*:** Ảnh gốc, `sidecar.json`, `meta.json` và các ảnh xem trước chỉ tồn tại tạm trong thư mục UUID lúc xử lý; ảnh xem trước trả trực tiếp dạng inline `data:image/png;base64,...` và toàn bộ thư mục tạm bị **xóa vĩnh viễn ngay trong khối `finally:`** trước khi trả kết quả HTTP (`verified_gone_on_disk: true`, 0 tệp sót lại trên đĩa).
  2. **`ttl` *(lưu tạm tối đa 15 phút / `900s`, cấu hình qua `STAR_TRACKER_UPLOAD_TTL_S`)*:** Ảnh gốc, sidecar, `meta.json` và ảnh xem trước (`demo_clean.png`, `demo_input.png`, `demo_output.png`, `demo_result.png`, `demo_compare_clean.png`) được cách ly hoàn toàn trong `data/user_uploads/<upload_id>/` (phục vụ qua `GET /api/uploads/<upload_id>/preview/<filename>`), có **quét dọn tức thì khi khởi động server (startup orphan sweep) + luồng nền tự dọn mỗi `60s`** (`TTL_EXPIRED_AUTO_PURGE`); cho phép người dùng thực thi **quyền xóa ngay lập tức** (URL preview trả `404` ngay lập tức và UI xóa sạch URL ảnh trên DOM):
     - `GET /api/uploads` — liệt kê các tệp tải lên tạm thuộc phiên hiện tại và thời gian tự xóa còn lại.
     - `DELETE /api/uploads/<upload_id>` — xóa vĩnh viễn ảnh, `sidecar.json`, `meta.json` & ảnh xem trước của phiên đó (`verified_gone: true`).
     - `DELETE /api/uploads` — xóa toàn bộ tệp tạm của phiên hiện tại.
