# Hướng dẫn Tái lập Độc lập từ Bản tải sạch (Clean Clone) — DUT.StarTracker (Chặng 2)

Kho mã nguồn này đã đóng gói **đầy đủ 100% gói tái lập độc lập** ngay trên nhánh `main` (tổng dung lượng gói tài nguyên ~`37,6 MB`, mỗi tệp `< 19 MB`, không cần tải thủ công ngoài kho):
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

## 4. Chạy bộ kiểm thử tự động & Toàn bộ Benchmark

```powershell
# Bộ kiểm thử hồi quy, chốt chặn chống khóa sai, tái lập & kiểm soát dữ liệu ảnh
pytest -q

# Benchmark End-to-End 5 phương pháp trên 6 ảnh trời thật + mô phỏng
python scripts/benchmark_3way_centroid_e2e.py

# Benchmark đường cong stress (vận tốc quay ω, sao giả, nền lóa)
python scripts/benchmark_stress_curves.py

# Benchmark khả thi nhúng CubeSat (ONNX 1-luồng, mưa proton SAA, lật bit SEU CRC-16)
python scripts/benchmark_embedded_cubesat.py

# Đối soát log và tài liệu
python scripts/reconcile_logs.py
```

## 5. Chính sách kiểm soát dữ liệu ảnh tải lên & Quyền xóa (Web UI / API)

- **Ảnh mẫu hệ thống (chỉ đọc):** `data/uploads/` — tách biệt hoàn toàn khỏi tệp người dùng tải lên.
- **Nơi lưu ảnh người dùng tải lên:** `data/user_uploads/<upload_id>/` (mỗi lượt tải nhận một mã UUID4 16 ký tự duy nhất $\rightarrow$ **tuyệt đối không ghi đè** tệp trùng tên).
- **Thời gian lưu (2 chế độ do người dùng chọn ngay khi tải ảnh):**
  1. **`ephemeral` *(mặc định an toàn — 0 giây lưu đĩa)*:** Ảnh và tệp `sidecar.json` chỉ tồn tại tạm thời trong lúc giải, sau đó bị **xóa vĩnh viễn ngay trong khối `finally:`** trước khi trả kết quả HTTP.
  2. **`ttl` *(lưu tạm tối đa 15 phút / `900s`, cấu hình qua `STAR_TRACKER_UPLOAD_TTL_S`)*:** Tự động dọn sạch khi hết hạn; cho phép người dùng xem danh sách tệp tạm và thực thi **quyền xóa ngay lập tức** qua giao diện Web hoặc API:
     - `GET /api/uploads` — liệt kê các tệp tải lên tạm và thời gian tự xóa còn lại.
     - `DELETE /api/uploads/<upload_id>` — xóa vĩnh viễn ảnh & `sidecar.json` của phiên đó (xác minh `verified_gone: true`).
     - `DELETE /api/uploads` — xóa toàn bộ tệp người dùng đã tải lên.
- **Nhật ký chế độ thực thi & Fallback CoG:** Mọi lượt chạy và xóa dữ liệu đều ghi vào `data/outputs/execution_log.jsonl` và tra cứu trực tiếp qua `GET /api/execution-log` (ghi rõ `requested_backend`, `executed_backend`, `fallback_triggered`, `fallback_reason`).
