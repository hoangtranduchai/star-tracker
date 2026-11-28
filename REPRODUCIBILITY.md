# Hướng dẫn Tái lập Độc lập từ Bản tải sạch (Clean Clone) — DUT.StarTracker (Chặng 2)

Kho mã nguồn này đã đóng gói **đầy đủ 100% gói tái lập độc lập** ngay trên nhánh `main` (tổng dung lượng gói tài nguyên **`36,03 MiB`** / `~37,78 MB`, mỗi tệp `< 19 MB`, không cần tải thủ công ngoài kho):
- **Checkpoint CNN:** `third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt` (trọng số công khai của Hongrui Zhao et al., `arXiv:2404.19108`, không huấn luyện lại).
- **6 ảnh bầu trời thật có hiệu chuẩn:** `ESA tetra3 Alt40 & Alt60` (16-bit), `Zhao MT9V022 nightsky_june16_2021.npy & verification_img.npy` (8-bit + hiệu chuẩn méo Heikkila), `UW LOST mount_st_helens_1.png`, và `NTNU 0006.png` (ca kiểm âm tính góc siêu rộng `77,5°`).
- **Hồ sơ hiệu chuẩn & Danh mục sao:** `data/real_calibrated/manifest_real_calibrated.json`, `data/uploads/real_sky/metadata.yaml`, `config/camera_specs.json`, `config/pipeline_default.json`, `data/catalogs/BSC5`, `data/catalogs/IAU-CSN.txt`.
- **Bảng kiểm tra toàn vẹn SHA-256:** `CHECKSUMS.sha256`.

---

## 1. Tải sạch & Cài đặt môi trường (Python 3.10+)

```powershell
git clone https://github.com/hoangtranduchai/star-tracker.git star-tracker-clean
cd star-tracker-clean
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Xác thực SHA-256 toàn bộ checkpoint, ảnh mẫu & hiệu chuẩn

```powershell
python scripts/verify_repro_bundle.py
# Hoặc trên Linux/macOS: sha256sum -c CHECKSUMS.sha256
```

Kỳ vọng: `verified=13/13 | checkpoint=verified | ok=True`.

## 3. Chạy xác thực tái lập 1 lệnh (gồm ảnh thật hiệu chuẩn, chứng minh Fallback CoG & Demo xóa ảnh)

```powershell
python scripts/run_clean_repro.py
```

Lệnh này tự động:
1. Kiểm tra `CHECKSUMS.sha256` (`13/13` tệp khớp).
2. Tự dựng bảng `K-Vector` từ `data/catalogs/BSC5` và giải tư thế trên `Seed 42 (Auto)`, `ESA Alt60 (16-bit)`, `Zhao nightsky (8-bit, Auto tự nâng cấp sang CNN-Hybrid)`, và `Mount St. Helens (CNN-Hybrid)`.
3. Mô phỏng thiếu checkpoint (`simulate_missing_weights=True`) để chứng minh **Fallback CNN → CoG** có báo rõ nguyên nhân và ghi vào `data/outputs/execution_log.jsonl`.
4. Kiểm chứng tải lên 2 tệp trùng tên `mount_st_helens_1.png` vào 2 thư mục UUID độc lập (không ghi đè nhau, không chạm ảnh mẫu) rồi xóa sạch và xác minh đã mất khỏi đĩa.

## 4. Chạy bộ kiểm thử tự động & Toàn bộ Benchmark (Chạy sạch 100% từ bản clone)

```powershell
# Bộ kiểm thử hồi quy, chốt chặn chống khóa sai, tái lập & kiểm soát dữ liệu ảnh
pytest -q

# Benchmark End-to-End 5 phương pháp chạy trực tiếp trên bản tải sạch (6 ảnh trời thật hiệu chuẩn + 20 khung stress Rìa Trái Đất/mây)
python scripts/benchmark_3way_centroid_e2e.py --real-only

# Benchmark End-to-End chuẩn (ảnh trời thật hiệu chuẩn + Seed 42 + 100 ca stress từ chối khớp sai)
python scripts/benchmark_end_to_end.py --suites real seed42 stress

# Benchmark đường cong stress (vận tốc quay ω, sao giả, nền lóa)
python scripts/benchmark_stress_curves.py

# Benchmark khả thi nhúng CubeSat (mưa proton SAA, lật bit SEU CRC-16; ONNX nếu cài thêm onnxruntime)
python scripts/benchmark_embedded_cubesat.py

# Đối soát log và tài liệu
python scripts/reconcile_logs.py
```

*(Ghi chú: Bộ 540 khung mô phỏng `hd1024` / `hd1024_glare` dung lượng ~373 MB không đóng gói vào Git để giữ repo gọn nhẹ; khi chạy không có `--real-only` trên bản tải sạch, script tự động bỏ qua nhẹ nhàng mà không crash và lưu kết quả riêng tại `data/outputs/benchmark_3way_clean_clone.json`. Có thể tái sinh 500 khung sạch `hd1024` bằng `python scripts/benchmark_centroid_cnn_hd1024.py`, 40 khung lóa `hd1024_glare` bằng `python scripts/benchmark_centroid_cnn_glare.py`, hoặc sinh bộ khung `fast`/`full` bằng `python scripts/generate_sim_dataset.py`.)*

## 5. Chính sách kiểm soát dữ liệu ảnh tải lên & Quyền xóa (Web UI / API)

- **Ảnh mẫu hệ thống (chỉ đọc):** `data/uploads/` — tách biệt hoàn toàn khỏi tệp người dùng tải lên.
- **Nơi lưu ảnh người dùng tải lên & ảnh xem trước:** `data/user_uploads/<upload_id>/` (mỗi lượt tải nhận một mã UUID4 16 ký tự duy nhất $\rightarrow$ **tuyệt đối không ghi đè** tệp trùng tên, ảnh mẫu hay các tệp `data/outputs/demo_*.png` dùng chung).
- **Cô lập phiên trình duyệt & rollback khi lỗi:** Mỗi trình duyệt truy cập Web nhận cookie phiên ẩn danh `st_sid` (`HttpOnly`, `SameSite=Lax`) để cô lập danh sách, ảnh xem trước và quyền xóa `ttl` giữa các người dùng cùng truy cập. Nếu yêu cầu tải lên gặp lỗi xử lý (`HTTP 400/409`) ở cả hai chế độ, thư mục tạm lập tức được xóa hoàn tác (`ERROR_ROLLBACK_DELETE`, 0 tệp mồ côi).
- **Thời gian lưu (2 chế độ do người dùng chọn ngay khi tải ảnh):**
  1. **`ephemeral` *(mặc định an toàn — 0 giây lưu đĩa)*:** Ảnh gốc, tệp `sidecar.json` và các ảnh xem trước chỉ tồn tại tạm trong thư mục UUID lúc xử lý; ảnh xem trước trả trực tiếp dạng inline `data:image/png;base64,...` và toàn bộ thư mục tạm bị **xóa vĩnh viễn ngay trong khối `finally:`** trước khi trả kết quả HTTP (`verified_gone_on_disk: true`, 0 byte sót lại trên đĩa).
  2. **`ttl` *(lưu tạm tối đa 15 phút / `900s`, cấu hình qua `STAR_TRACKER_UPLOAD_TTL_S`)*:** Ảnh gốc, sidecar và ảnh xem trước (`demo_clean.png`, `demo_input.png`, `demo_output.png`, `demo_result.png`, `demo_compare_clean.png`) được cách ly hoàn toàn trong `data/user_uploads/<upload_id>/` (phục vụ qua `GET /api/uploads/<upload_id>/preview/<filename>`), có luồng nền tự động quét dọn mỗi `60s` (`TTL_EXPIRED_AUTO_PURGE`) ngay cả khi không có lưu lượng mới; cho phép người dùng thực thi **quyền xóa ngay lập tức** (URL preview trả `404` ngay lập tức):
     - `GET /api/uploads` — liệt kê các tệp tải lên tạm thuộc phiên hiện tại và thời gian tự xóa còn lại.
     - `DELETE /api/uploads/<upload_id>` — xóa vĩnh viễn ảnh, `sidecar.json` & ảnh xem trước của phiên đó (`verified_gone: true`).
     - `DELETE /api/uploads` — xóa toàn bộ tệp tạm của phiên hiện tại.
- **Nhật ký chế độ thực thi & Fallback CoG (ghi nguyên tử `os.replace`):** Mọi lượt chạy (kể cả khi `Auto-Router` hoặc `CNN` gặp lỗi checkpoint/sai SHA-256 và fallback về CoG) cùng mọi thao tác xóa dữ liệu đều ghi vào `data/outputs/execution_log.jsonl` và tra cứu trực tiếp qua `GET /api/execution-log` (ghi rõ `requested_backend`, `executed_backend`, `fallback_triggered`, `fallback_reason`, `checkpoint_status`).
