# THÔNG TIN ĐIỀN FORM NỘP BÀI · VÒNG CHUNG KẾT CHẶNG 1

Trang nộp bài: https://ai.tainangviet.vn/dashboard/final

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
https://github.com/hoangtranduchai/star-tracker/blob/main/AI2026_Portfolio/BAO_CAO_CAI_TIEN_VONG_CHUNG_KET_CHANG_1.pdf
```

*(Link dự phòng bản Word `.docx` nếu cần: `https://github.com/hoangtranduchai/star-tracker/blob/main/AI2026_Portfolio/BAO_CAO_CAI_TIEN_VONG_CHUNG_KET_CHANG_1.docx`)*

## 4. Commit / tag / phiên bản mã nguồn *(không bắt buộc)*

```text
v1.1.0-stage1 / 21559e0 (nhánh main & feat/national-round-stage1; bản gốc trước cải tiến gắn tag v1.0.0-pre-stage1)
```

## 5. Tài khoản dùng thử sản phẩm *(không bắt buộc)*

*(Để trống — xóa nếu trình duyệt tự điền sẵn)*

## 6. Mật khẩu dùng thử *(không bắt buộc)*

*(Để trống — xóa nếu trình duyệt tự điền sẵn)*

## 7. Hướng dẫn cài đặt / chạy *(không bắt buộc)*

```text
1. Trải nghiệm trực tuyến 24/7 (host trên VPS qua Cloudflare HTTPS, không cần tài khoản đăng nhập):
- Truy cập trực tiếp: https://startracker.agentlens.dpdns.org
- Chế độ mặc định trên thanh đầu trang là "Tự động (Auto: CoG → CNN-Hybrid)" (tự chọn CoG nhanh trên trời sạch và tự động nâng cấp sang CNN-Hybrid khi CoG gặp ảnh đêm/tiền cảnh khó).
- Chọn nhanh các kịch bản ("Bầu trời chuẩn", "Trời thực ESA", "Núi St. Helens", "Ngược nắng"), hoặc mở tab "So sánh CoG / tetra3 ↔ CNN":
  + Bấm nút 1 chạm "Ảnh đêm Zhao (8-bit)" để chứng kiến trực tiếp CoG=LOST, tetra3=LOST và duy nhất CNN-Hybrid SOLVED 48,26" (8/8 sao khớp).
  + Hỗ trợ tải ảnh tự chọn để đối chiếu 3 lớp tâm sao trực tiếp, nút "Xuất JSON", bảng đối chuẩn 5 phương pháp (566 khung) và bảng đường cong suy giảm stress (ω, sao giả, nền lóa — 0% Khóa sai trên 3.430 lượt kiểm thử).

2. Cài đặt và chạy trực tiếp trên máy tính cá nhân (Python 3.10+):
git clone https://github.com/hoangtranduchai/star-tracker.git
cd star-tracker
pip install -r requirements.txt
python app.py
(Mở http://127.0.0.1:8765 trên trình duyệt)

3. Chạy kiểm thử tự động & tái lập toàn bộ benchmark Chặng 1:
pytest -q
python scripts/reconcile_logs.py
python scripts/benchmark_end_to_end.py --suites all
python scripts/benchmark_3way_centroid_e2e.py
python scripts/benchmark_stress_curves.py
python scripts/benchmark_embedded_cubesat.py
python scripts/make_stage1_upgrade_figures.py
```

## 8. Khai báo sử dụng AI, mã nguồn và dữ liệu bên ngoài *(không bắt buộc)*

```text
1. Danh mục sao & chuẩn tên thiên văn công khai:
- Yale Bright Star Catalog v5 (BSC5, 5.023 sao V <= 6.0), ESA Hipparcos I/239, danh mục tên sao quốc tế IAU-CSN.

2. Mô hình AI & dữ liệu ảnh bầu trời thật công khai:
- Trọng số mạng MobileUNet_B10_50.pt công bố mở bởi Hongrui Zhao et al. (arXiv:2404.19108, GitHub: HongruiZhao/CNNStarDetectCentroid) — sử dụng nguyên bản không huấn luyện lại, kết hợp tầng tinh chỉnh sub-pixel CNN-Hybrid.
- Ảnh bầu trời thật hiệu chuẩn công khai: ESA tetra3 (Apache-2.0, camera FLIR IMX265), UW CubeSat LOST (MIT, ảnh thực địa Mount St. Helens), ảnh đêm MT9V022 từ Zhao et al., và ảnh góc rộng NTNU (ca kiểm từ chối an toàn LOST).

3. Thư viện mã nguồn mở & tham khảo toán học:
- NumPy, SciPy, OpenCV, PyTorch, ONNX Runtime, Matplotlib, Flask, Gunicorn, Three.js.
- Tham khảo thuật toán công bố của ESA tetra3 (Apache-2.0), UW LOST (MIT), Pyramid/K-vector (Mortari), Wahba SVD/QUEST và chuẩn đồng bộ khung CCSDS/CRC-16-CCITT (chi tiết tại THIRD_PARTY_NOTICES.md).

4. Khai báo sử dụng công cụ AI hỗ trợ phát triển:
- Trong Chặng 1, đội sử dụng trợ lý lập trình AI (Google Antigravity / Gemini) để hỗ trợ viết và chỉnh sửa mã nguồn cải tiến (chốt chặn từ chối khớp sai, CNN-Hybrid, Auto-Router, tối ưu hóa nhận dạng, đóng gói Telemetry CRC-16), viết script kiểm thử/benchmark, nâng cấp giao diện Web và hỗ trợ đồng bộ hóa tài liệu/biểu đồ.
- Các thành viên đội thi là người định hướng bài toán, đặt yêu cầu kỹ thuật, trực tiếp chạy kiểm chứng thực tế trên giao diện/hệ thống, phát hiện lỗi để điều chỉnh, đối chiếu tính chính xác của số liệu và chịu hoàn toàn trách nhiệm về sản phẩm nộp dự thi.
```
