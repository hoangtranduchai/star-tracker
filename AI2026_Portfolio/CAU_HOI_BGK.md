# Câu hỏi ban giám khảo — star tracker demo

Trường Đại học Bách khoa, Đại học Đà Nẵng, Khoa Công nghệ thông tin  
Đội: Hoàng Trần Đức Hải · Nguyễn Tiến · Mai Tạ Trúc Vy

Số đo chỉ lấy từ `data/outputs/log_reconciliation_audit.json` và các file JSON kiểm toán Chặng 1. Không dùng số nhớ cũ. Live demo: đọc đúng số trên màn hình.

---

### 1. Đây là bài toán gì? Lost-in-space nghĩa là gì?

**Trả lời:** Không có tư thế ban đầu. Từ ảnh sao trong trường nhìn, nhận dạng sao rồi ước lượng hướng camera (quaternion J2000) so với catalog cố định trên **phần mềm demo PC (Laptop RTX 5070 / CPU)** — chưa kiểm chứng trên phần cứng vệ tinh bay.

### 2. Tâm sao (centroid) là gì? Em tính thế nào?

**Trả lời:** Tọa độ dưới mức pixel của đốm sao. Mặc định: trọng tâm cường độ (`CoG`) sau khử nền và thành phần liên thông. Tùy chọn: MobileUNet công khai (Zhao et al.) + trilateration, `d_th=2,0` — không huấn luyện lại; Chặng 1 bổ sung chia thang chuẩn **8/12/16-bit** (`/16` với 12-bit, `/256` với 16-bit + xếp hạng tương phản SNR) để chạy tốt trên ảnh sao thật 16-bit.

### 3. Pyramid / Mortari là gì?

**Trả lời:** Nhận dạng sao theo khoảng cách góc; khớp bộ bốn sao với catalog rồi mở rộng (`_associate_remaining`), không khớp theo tên chòm sao văn hóa.

### 4. K-vector là gì?

**Trả lời:** Bảng tra nhanh cặp sao theo góc trong catalog, giúp tìm ứng viên gần như thời gian hằng số.

### 5. Wahba / SVD / QUEST?

**Trả lời:** Wahba tìm phép quay tối ưu giữa vector quan sát và catalog. SVD (Kabsch) hoặc QUEST đều cho quaternion; demo mặc định SVD, kèm chốt chặn kiểm tra giá trị kỳ dị nhỏ nhất `s_min >= 1e-6` để chặn cấu hình 3 sao thẳng hàng (`COLLINEAR_DEGENERATE_GEOMETRY`).

### 6. Quaternion — vì sao 16 byte? Nếu LOST thì sao?

**Trả lời:** Bốn `float32 × 4 byte = 16 byte` (`[w, x, y, z]` J2000) trên phần mềm demo PC. Khi bất kỳ chốt chặn kiểm tra nào không đạt, hệ thống trả `status="LOST"`, `q=None`, `reject_code` cụ thể và gói downlink **16 byte `0x00`** (không bao giờ xuất tư thế giả).

### 7. Vì sao FAST, không FULL suốt demo?

**Trả lời:** FULL 6000×4000 nặng trên laptop. FAST 1500×1000 cùng FOV, demo mượt hơn (`CoG 146,4 ms`, `CNN warm GPU 226,1 ms`).

### 8. Có dùng AI / CNN không? Lõi có phải học sâu không?

**Trả lời:** Lõi nhận dạng và giải tư thế là Pyramid + Wahba — cổ điển. CNN chỉ thay bước tìm tâm khi chọn (`centroid_backend=cnn`), không huấn luyện lại trọng số công khai. **Quy tắc lai preset:** ảnh giả lập / Seed 42 / Sao chuẩn / ESA `tetra3` → CoG mặc định; nút **Ảnh núi thật** → CNN (núi/cây chỉ `1` điểm vs CoG `25` điểm trên mặt nạ độc lập). Không khẳng định CNN thắng mọi khung.

### 9. CNN có luôn tốt hơn CoG không? Kết quả 500 khung sạch & 40 lóa thế nào?

**Trả lời:** Không — trên mô phỏng sạch và lóa, CoG vượt trội toàn diện:
- **Centroid `thr2` (500 khung, 27.017 sao GT):** CoG đạt RMSE **`0,1804 px`**, khớp `25.206/27.017` (**Recall `93,3%` · Precision `100,0%` · 0 sao giả**, `34,2 ms`); CNN đạt RMSE **`0,4745 px`**, khớp `25.050/27.017` (**Recall `92,7%` · Precision `75,4%`** [`25.050/33.241 · 8.191 sao giả`], `60,2 ms`).
- **End-to-End 500 khung `hd1024` (RTX 5070):** CoG đạt **`500/500 <40″` (`100,0%`)**, `Δθ` trung vị **`2,00″`** (`P90 6,26″`, `Cross-Boresight 0,49″`, `Roll 1,89″`, `87,2 ms`); CNN đạt `500/500 solved`, **`498/500 <40″` (`99,6%`)**, `2 WARN` (`55,95″` & `42,26″`), `Δθ` trung vị **`7,94″`** (`123,9 ms`, `1.118 FP`), cả hai đạt **`0% False Lock`**.
- **End-to-End 40 khung lóa mạnh:** CoG **`40/40 <40″`** (`Δθ` tv **`1,99″`**, centroid RMSE `0,1449 px`, `78,3 ms`) vs CNN `39/40 <40″` (`Δθ` tv **`10,59″`**, centroid RMSE `0,3951 px`, `131,1 ms`).
- **Seed 42 FAST (`seed42_cog_vs_cnn.json`):** CoG **`0,446″`** (`36/36`, Prec/Rec `100%`) vs CNN **`1,648″`** (`30/36`, Prec `85,7%`, Rec `83,3%`).

### 10. Ảnh núi thật Mount St. Helens — nguồn, đối soát 111 vs 106 và kết quả hậu kiểm?

**Trả lời:** File công bố kèm LOST (UW), `mount_st_helens_1.png`, 1024×1024, f=4,2 mm, pixel 4,1 µm — **không phải ảnh nhóm chụp**.
- **Đối soát `111` vs `106` điểm của CoG:** `CentroidDetector` độc lập (`bg_block=31`, không mask) tách **`111`** điểm (`25` núi/cây, `86` trời); còn trong `StarTrackerPipeline` (`GlareMasker` phủ `0 px` trên ảnh 8-bit + `bg_block=32→33`), CoG tách **`106`** điểm (chênh 5 đốm sát ngưỡng). CNN tách `79` điểm (`1` núi/cây, `78` trời).
- **Kết quả E2E hậu kiểm:** CNN giải **`SOLVED`** **`54/79`** cặp (`RA 310,48° Dec +36,00°`, lệch UW LOST **`0,034°`**, **`~2,76 s`**; hoặc `0,55 s` khi bật tham số hiệu chuẩn `k1/k2`). Còn **CoG** khi đi qua chốt chặn `_refine_inliers` mới bị loại `8/9` cặp nhiễu do đốm núi và méo góc rộng (53°×53°), chỉ còn **`1` inlier (< 3)** nên trả về an toàn **`LOST [INSUFFICIENT_INLIER_PAIRS]`** kèm 16 byte `0x00` (trước sửa, lỗi `break` cũ khiến CoG giải ép `64/106` trong `~16,2 s`).

### 11. Vì sao chốt chặn từ chối khớp sai là cải tiến cốt lõi ở Vòng Chung kết · Chặng 1?

**Trả lời:** Trong mã gốc `HEAD:src/pipeline.py` (dòng 98–100), khi `count_nonzero(inliers) < 3`, vòng lặp thoát `break` mà **không xóa cặp ngoại lai** khỏi `obs_sel, cat_sel`; cộng thêm thiếu lọc sau `_associate_remaining` và thiếu kiểm SVD thẳng hàng ở `src/attitude.py`. Điều này khiến 100 ca stress đối kháng ở mã cũ bị **`41/100 (41,0%) False Lock`** (tạo góc giả lên tới `647.283″` ở nhóm khớp nhiễu và `928,8″` ở 3 sao thẳng hàng). Sau khi bổ sung chuỗi chốt chặn (`_dedup_pairs`, `_refine_inliers` trước & sau gán bổ sung, kiểm SVD `s_min >= 1e-6`, `min_stars >= 4`, RMS hậu kiểm, `LOW_FOV_CONSISTENCY`), tỷ lệ False Lock giảm từ **`41,0%` xuống `0,0% (0/100)`**, kèm `123 passed, 2 skipped` trong `pytest`.

### 12. Giới hạn & các ca lỗi trên ảnh thật hiệu chuẩn?

**Trả lời:** Đã đánh giá đầy đủ trên **6 khung ảnh trời thật** (`benchmark_real_calibrated_e2e.json`, `0% False Lock` ở mọi ca):
- Với quang học danh nghĩa (`BSC5`): CoG `0/6`, CNN `1/6` (`MSH 110,05″`). Với quang học hiệu chuẩn `(f, cx, cy, k1, k2)`: CoG đạt **`2,26″`** trên `ESA tetra3 Alt60`; CNN đạt `3/5` (**`4,65″`** `Alt60`, **`54,70″`** `Zhao MT9V022` sau hiệu chỉnh Heikkila, **`120,26″` vs manifest / `0,034°` vs LOST** trên `MSH`).
- **Ca thiếu sao & méo chưa hiệu chuẩn:** `tetra3 Alt40` (FOV 11,4°) chỉ có 3 sao `BSC5 V≤6` đạt lề 5 px nên trả **`LOST`** an toàn; khi dùng hiệu chuẩn + `Hipparcos V≤7`, CoG giải **`39,51″`** và CNN **`26,60″`**. Ảnh siêu rộng chưa hiệu chuẩn `NTNU 0006.png` (`77,5°`) và ảnh 4 đốm `Zhao verification_img.npy` đều bị chặn **`LOST`** (`0% False Lock`).
- URL GitHub: `https://github.com/hoangtranduchai/star-tracker` (nhánh `feat/national-round-stage1`, xem `00_LINK_MA_NGUON_GITHUB.txt`). Mặt nạ núi/cây là heuristic kèm overlay để kiểm bằng mắt.

### 13. Đối soát Log–Tài liệu–Slide (vì sao phải rà soát Slide 7 và các FAQ cũ)?

**Trả lời:** Qua kiểm toán tự động `scripts/reconcile_logs.py` (`log_reconciliation_audit.json`, 21 mục), nhóm phát hiện Slide 7 trước đây ghi nhầm tỷ lệ khung thành tỷ lệ sao khớp trên 27.017 sao GT (chuẩn là CoG Recall `93,3%` / Precision `100,0%` và CNN Recall `92,7%` / Precision `75,4%` với `8.191` FP); Slide FAQ cũ chứa con số mồ côi không có log đối chiếu. Nhóm đã xóa bỏ hoàn toàn, sửa Slide 7/8/10/16, bổ sung Slide 12–15 và đồng bộ toàn bộ MD/DOCX/PDF.

### 14. Phần mềm này đã chứng minh chạy được trên vệ tinh / ADCS / môi trường bức xạ chưa?

**Trả lời:** **Chưa.** Tất cả thí nghiệm (540 sim, 100 stress, 6 ảnh thật) đều chạy trên **PC Laptop (RTX 5070 / CPU)** với tập ảnh tĩnh. Hệ thống **chưa kiểm chứng** trên phần cứng CubeSat/MCU/FPGA, chưa thử bức xạ không gian (TID/SEE), nhiệt chân không, rung động phóng hay vòng điều khiển ADCS vật lý; việc nhúng bay là định hướng phát triển tiếp theo.

### 15. Sai số / thời gian lần demo này?

**Trả lời:** Đọc đúng số đang hiển thị trên badge & KPI giao diện web (mặc định Laptop demo), không đọc theo trí nhớ. Nếu trạng thái là `LOST`, đọc rõ mã `reject_code` và xác nhận gói downlink 16 byte `0x00`.

### 16. Star tracker có GSD mét không? (câu mẹo)

**Trả lời:** Không. GSD mét là ảnh mặt đất khoảng cách hữu hạn. Sao coi như vô cực góc; sản phẩm là hướng / quaternion.

### 17. Catalog? Cần tên sao không?

**Trả lời:** Mặc định Yale BSC5, `V ≤ 6` (`5.023` sao); hỗ trợ thêm `Hipparcos V ≤ 7` cho trường nhìn hẹp/ít sao như `tetra3 Alt40`. Khớp theo góc và ID catalog, không theo tên chòm sao.

### 18. Nguồn mã / giấy phép?

**Trả lời:** Tham khảo công bố và mã mở (ESA tetra3 Apache-2.0, UW LOST MIT, toán QUEST/K-vector đã công bố). Tái hiện toán đã công bố; không copy mã NOSA. Chi tiết trong `THIRD_PARTY_NOTICES.md`.

### 19. Đổi máy ảnh thì sao?

**Trả lời:** Nhập đúng tiêu cự mm, cạnh pixel µm, và (nếu có) tâm ảnh hiệu chuẩn `(cx, cy)` cùng hệ số méo `(k1, k2)` trong manifest/YAML. Không dùng «tương đương 35 mm» để giải.

### 20. Vì sao Seed 42?

**Trả lời:** Cùng seed → cùng khung mô phỏng / ground truth (`seed42_cog_vs_cnn.json`), dễ tái lập và đối chiếu trực tiếp giữa hai nhánh CoG (`0,446″`) và CNN (`1,648″`).

---

## Không được nói

1. Chỉ trình bày đúng cấu hình camera demo (APS-C 50 mm trên Laptop) và dữ liệu thật công khai (`ESA tetra3`, `Zhao MT9V022`, `UW LOST Mount St. Helens`, `NTNU 0006.png`).
2. Không gán GSD mét cho star tracker; **không** gọi phần mềm demo là thiết bị bay hay khẳng định đã sẵn cho ADCS vệ tinh.
3. Không nói «CNN luôn tốt hơn» — trên 500 khung sạch & 40 lóa, CoG thắng cả RMSE lẫn 3-DOF E2E.
4. Không gọi ảnh núi là ảnh nhóm chụp — là mẫu LOST công bố của ĐH Washington.
5. Không bịa số hay trích dẫn số mồ côi không có log kiểm toán; chỉ trích đúng số từ `log_reconciliation_audit.json` và các JSON Chặng 1.
