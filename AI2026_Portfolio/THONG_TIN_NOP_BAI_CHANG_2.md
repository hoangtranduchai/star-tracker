# THÔNG TIN ĐIỀN FORM NỘP BÀI · VÒNG CHUNG KẾT CHẶNG 2 (HACKATHON)

Trang nộp bài: https://ai.tainangviet.vn/dashboard/final *(Mục: **Nộp / cập nhật bài · Chặng 2** — Hạn chót: **13:30:00 28/11/2026**)*

> **Lưu ý trước khi nộp:** Đảm bảo bạn đã tự bấm nút **"Xác nhận đã nhận đề"** (nếu cổng yêu cầu), kiểm tra bỏ trống 2 ô Tài khoản / Mật khẩu dùng thử (sản phẩm mở trực tiếp không yêu cầu đăng nhập — xóa nếu trình duyệt tự điền sẵn), tích chọn ô cam kết cuối trang rồi bấm nộp bài chính thức.

---

## 1. Liên kết mã nguồn (HTTPS) *(bắt buộc)*

```text
https://github.com/hoangtranduchai/star-tracker
```

## 2. Liên kết sản phẩm chạy thử (HTTPS) *(bắt buộc — chạy 24/7 trên VPS)*

```text
https://startracker.agentlens.dpdns.org
```

## 3. Liên kết báo cáo cải tiến PDF/Word (HTTPS) *(bắt buộc)*

```text
https://github.com/hoangtranduchai/star-tracker/blob/main/AI2026_Portfolio/BAO_CAO_CAI_TIEN_VONG_CHUNG_KET_CHANG_2.pdf
```

*(Bản Word `.docx` dự phòng: `https://github.com/hoangtranduchai/star-tracker/blob/main/AI2026_Portfolio/BAO_CAO_CAI_TIEN_VONG_CHUNG_KET_CHANG_2.docx`)*

## 4. Link minh chứng cải tiến (HTTPS) *(bắt buộc)*

```text
https://github.com/hoangtranduchai/star-tracker/blob/main/AI2026_Portfolio/MINH_CHUNG_CAI_TIEN_CHANG_2.md
```

*(Trang minh chứng hiển thị trực tiếp trên GitHub gồm: bảng SHA-256 13/13 tệp `36,02 MiB (37,77 MB)` khóa LF đa nền tảng `.gitattributes`, stdout chạy thực tế từ bản `git clone` sạch trên cả Linux/macOS lẫn Windows `autocrlf=true`, chứng minh Runtime Guard chặn 1-byte tamper `CHECKPOINT_SHA256_MISMATCH` trước `torch.load`, benchmark 5 phương pháp đủ 20 khung clutter, sơ đồ kiến trúc & 4 ảnh chụp giao diện Web UI cho Checksum / Fallback CoG / Chống ghi đè TTL / Xóa sạch dữ liệu, log JSONL `execution_log` và kết quả `151 passed, 1 skipped` + VPS smoke test).*

## 5. Commit / tag / phiên bản mã nguồn *(không bắt buộc)*

```text
v1.2.0-stage2 (nhánh main; Chặng 1 gắn tag v1.1.0-stage1; bản gốc trước cải tiến gắn tag v1.0.0-pre-stage1)
```

## 6. Tài khoản dùng thử sản phẩm *(không bắt buộc — sản phẩm không yêu cầu đăng nhập)*

*(Để trống — xóa nếu trình duyệt tự điền sẵn)*

## 7. Mật khẩu dùng thử *(không bắt buộc — sản phẩm không yêu cầu đăng nhập)*

*(Để trống — xóa nếu trình duyệt tự điền sẵn)*

## 8. Hướng dẫn cài đặt / chạy *(không bắt buộc)*

```text
1. Kiểm chứng trực tiếp Chặng 2 trên bản Web trực tuyến 24/7 (không cần tài khoản đăng nhập):
- Truy cập: https://startracker.agentlens.dpdns.org
- Mở tab "Cấu hình, Checksum & Dữ liệu":
  + Xem bảng kiểm chứng toàn vẹn 13/13 tệp SHA-256 — 36,02 MiB (37,77 MB): MobileUNet_B10_50.pt (17,71 MiB / 18,57 MB), 6 ảnh trời thật hiệu chuẩn, manifest hiệu chuẩn, config & danh mục BSC5/IAU — gọi trực tiếp từ GET /api/repro-status và khóa LF đa nền tảng qua .gitattributes (13/13 OK trên cả Linux/macOS lẫn Windows).
  + Bấm nút 1 chạm "Thử nghiệm Fallback CNN → CoG" để kiểm chứng dải cảnh báo màu cam FALLBACK → CoG hiện ngay trên đầu trang kèm đường dẫn tương đối đã lọc (không lộ đường dẫn OS), bit telemetry FLAG_FALLBACK_USED (0x08) và bản ghi FALLBACK_TO_COG trong nhật ký execution_log.jsonl (GET /api/execution-log — lọc cô lập theo phiên owner_sid_hash; chặn tải trực tiếp GET /output/*.jsonl bằng HTTP 404).
- Mở ngăn "Tùy chỉnh & Tải ảnh" (góc trên phải):
  + Ảnh người dùng, sidecar JSON và toàn bộ 4 ảnh xem trước (demo_clean.png, demo_input.png, demo_output.png, demo_result.png) được cách ly hoàn toàn trong thư mục UUID4 riêng data/user_uploads/<upload_id>/ (mkdir exist_ok=False) + luôn ghi meta.json gắn cookie phiên st_sid (HttpOnly, SameSite=Lax, Secure, tự cấp ngay cả khi gọi API không cookie → chống IDOR) — 0% ghi đè tệp trùng tên hay ảnh mẫu đọc-chỉ data/uploads/, tự động rollback khi lỗi HTTP 400/409 (ERROR_ROLLBACK_DELETE) và trình duyệt khác không xem/xóa được tệp tạm hay đọc nhật ký tải lên của nhau.
  + Mặc định chọn chế độ "Xóa vĩnh viễn ngay sau xử lý (ephemeral — 0s sau phản hồi)": preview trả inline data:image/png;base64,..., khối finally: xóa sạch 100% ảnh gốc + sidecar + meta.json + 4 preview (verified_gone_on_disk=True); server cũng quét sạch slot ephemeral mồ côi ngay lúc khởi động (_run_startup_sweep).
  + Có thể chuyển sang "Lưu tạm 15 phút (TTL 900s, quét lúc khởi động + luồng nền mỗi 60s)", tải 2 tệp trùng tên kèm sidecar để thấy 2 thư mục UUID4 riêng biệt, rồi bấm "Xóa ngay" hoặc "Xóa toàn bộ ảnh tạm" (DELETE /api/uploads/<id> & DELETE /api/uploads): URL preview lập tức trả HTTP 404, giao diện xóa sạch DOM preview & ghi dấu DATA_DELETION vào nhật ký (ghi nguyên tử os.replace có retry trên Windows).
  + Ngoài ra, src/centroid_cnn.py xác thực SHA-256 của MobileUNet_B10_50.pt ngay trước torch.load(..., weights_only=False) (chặn tuyệt đối tệp sửa 1 byte CHECKPOINT_SHA256_MISMATCH hoặc tệp cụt <1 MB CHECKPOINT_TRUNCATED và fallback tường minh về CoG trên cả cnn, auto & /api/compare).

2. Chạy tái lập độc lập từ bản git clone sạch (Python 3.10+, kiểm chứng trên cả Linux/macOS LF & Windows autocrlf=true):
git clone https://github.com/hoangtranduchai/star-tracker.git
cd star-tracker
pip install -r requirements.txt
python scripts/verify_repro_bundle.py                       # Xác thực 13/13 tệp theo CHECKSUMS.sha256 (36,02 MiB / 37,77 MB)
sha256sum -c CHECKSUMS.sha256                               # 13/13 OK đa nền tảng (Linux/macOS & Windows)
python scripts/run_clean_repro.py                           # Chạy Seed 42 + Alt60 + Zhao + MSH (có Δθ GT) + Fallback CoG + Demo xóa upload
pytest -q                                                   # 151 passed, 1 skipped (bao gồm 17 test chuyên biệt Chặng 2 trong tests/test_stage2_repro_and_privacy.py)
python demo_star_tracker.py --centroid cnn --simulate-cnn-fallback --seed 42 --no-show
python scripts/benchmark_3way_centroid_e2e.py --real-only   # Benchmark 5 phương pháp (6 ảnh thật + 20 khung clutter, 0% FL)
python scripts/benchmark_end_to_end.py --suites real seed42 stress
python app.py                                               # Chạy Web cục bộ tại http://127.0.0.1:8765
(Chi tiết đầy đủ xem tại REPRODUCIBILITY.md và CHECKSUMS.sha256)
```

## 9. Khai báo sử dụng AI, mã nguồn và dữ liệu bên ngoài *(không bắt buộc)*

```text
1. Danh mục sao & chuẩn tên thiên văn công khai:
- Yale Bright Star Catalog v5 (BSC5, 5.023 sao V <= 6.0), ESA Hipparcos I/239, danh mục tên sao quốc tế IAU-CSN.

2. Mô hình AI & dữ liệu ảnh bầu trời thật công khai (đóng gói sẵn 13/13 tệp — 36,02 MiB / 37,77 MB — kèm CHECKSUMS.sha256 & .gitattributes LF):
- Trọng số mạng MobileUNet_B10_50.pt (17,71 MiB / 18,57 MB; SHA-256: e02d7723b832d12c...) công bố mở bởi Hongrui Zhao et al. (arXiv:2404.19108, GitHub: HongruiZhao/CNNStarDetectCentroid) — sử dụng nguyên bản không huấn luyện lại, kết hợp tinh chỉnh sub-pixel CNN-Hybrid và kiểm tra SHA-256 runtime trước torch.load.
- 6 ảnh bầu trời thật hiệu chuẩn công khai: ESA tetra3 Alt40/Alt60 (Apache-2.0), ảnh đêm MT9V022 (nightsky_june16_2021.npy, verification_img.npy) từ Zhao et al., UW CubeSat LOST Mount St. Helens (MIT), và ảnh góc rộng NTNU 0006.png (ca kiểm từ chối an toàn LOST).

3. Thư viện mã nguồn mở & tham khảo toán học:
- NumPy, SciPy, OpenCV, PyTorch, ONNX Runtime, Matplotlib, Flask, Gunicorn, Three.js.
- Tham khảo thuật toán công bố của ESA tetra3 (Apache-2.0), UW LOST (MIT), Pyramid/K-vector (Mortari), Wahba SVD/QUEST và chuẩn CCSDS/CRC-16-CCITT (chi tiết tại THIRD_PARTY_NOTICES.md).

4. Khai báo sử dụng công cụ AI hỗ trợ phát triển:
- Trong Chặng 1 và Chặng 2, đội sử dụng trợ lý lập trình AI (Google Antigravity / Gemini) hỗ trợ thiết kế và viết mã các mô-đun cải tiến (chốt chặn chống khóa sai, CNN-Hybrid, Auto-Router, gói tái lập kèm SHA-256/.gitattributes, Runtime Guard trước torch.load, phân vùng lưu ảnh tạm UUID4/TTL/st_sid chống IDOR và quyền xóa, nhật ký JSONL nguyên tử cô lập phiên), viết kiểm thử tự động, nâng cấp giao diện Web và tổng hợp báo cáo/minh chứng.
- Đội thi trực tiếp định hướng yêu cầu kỹ thuật, chạy kiểm chứng thực tế trên bản git clone sạch đa nền tảng và trên môi trường triển khai 24/7, kiểm tra sai sót thực tế, đồng bộ tài liệu và chịu hoàn toàn trách nhiệm về sản phẩm nộp dự thi.
```
