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
- **Kết quả E2E hậu kiểm:** Với quang học danh nghĩa Chặng 1, CNN giải **`SOLVED`** **`54/79`** cặp (`RA 310,48° Dec +36,00°`, lệch UW LOST **`0,034°`**, **`~2,76 s`**; hoặc `0,55 s` khi bật tham số hiệu chuẩn `k1/k2`), còn **CoG** bị loại `8/9` cặp nhiễu do đốm núi và méo góc rộng (53°×53°), chỉ còn **`1` inlier (< 3)** nên trả về an toàn **`LOST [INSUFFICIENT_INLIER_PAIRS]`** kèm 16 byte `0x00` (trước sửa, lỗi `break` cũ khiến CoG giải ép `64/106` trong `~16,2 s`). *(Ghi chú đối chiếu Chặng 1 nâng cấp & Chặng 2: khi bật tham số hiệu chuẩn góc rộng `k1/k2` từ `manifest_real_calibrated.json` và bộ tìm rộng nâng cấp, **CoG** giải được **`SOLVED 83/106` (`Δθ 49,51″`)** và **CNN-Hybrid** giải **`SOLVED 72/77` (`Δθ 71,13″`)**, vẫn giữ `0%` False Lock.)*

### 11. Vì sao chốt chặn từ chối khớp sai là cải tiến cốt lõi ở Vòng Chung kết · Chặng 1?

**Trả lời:** Trong mã gốc `HEAD:src/pipeline.py` (dòng 98–100), khi `count_nonzero(inliers) < 3`, vòng lặp thoát `break` mà **không xóa cặp ngoại lai** khỏi `obs_sel, cat_sel`; cộng thêm thiếu lọc sau `_associate_remaining` và thiếu kiểm SVD thẳng hàng ở `src/attitude.py`. Điều này khiến 100 ca stress đối kháng ở mã cũ bị **`41/100 (41,0%) False Lock`** (tạo góc giả lên tới `647.283″` ở nhóm khớp nhiễu và `928,8″` ở 3 sao thẳng hàng). Sau khi bổ sung chuỗi chốt chặn (`_dedup_pairs`, `_refine_inliers` trước & sau gán bổ sung, kiểm SVD `s_min >= 1e-6`, `min_stars >= 4`, RMS hậu kiểm, `LOW_FOV_CONSISTENCY`), tỷ lệ False Lock giảm từ **`41,0%` xuống `0,0% (0/100)`**, kèm **`151 passed, 1 skipped`** trong `pytest` (tính tới Chặng 2, gồm 17 kiểm thử chuyên biệt Chặng 2).

### 12. Giới hạn & các ca lỗi trên ảnh thật hiệu chuẩn?

**Trả lời:** Đã đánh giá đầy đủ trên **6 khung ảnh trời thật** (`benchmark_real_calibrated_e2e.json`, `0% False Lock` ở mọi ca):
- Với quang học danh nghĩa (`BSC5`): CoG `0/6`, CNN `1/6` (`MSH 110,05″`). Với quang học hiệu chuẩn `(f, cx, cy, k1, k2)`: CoG đạt **`2,26″`** trên `ESA tetra3 Alt60`; CNN đạt `3/5` (**`4,65″`** `Alt60`, **`54,70″`** `Zhao MT9V022` sau hiệu chỉnh Heikkila, **`120,26″` vs manifest / `0,034°` vs LOST** trên `MSH`).
- **Ca thiếu sao & méo chưa hiệu chuẩn:** `tetra3 Alt40` (FOV 11,4°) chỉ có 3 sao `BSC5 V≤6` đạt lề 5 px nên trả **`LOST`** an toàn; khi dùng hiệu chuẩn + `Hipparcos V≤7`, CoG giải **`39,51″`** và CNN **`26,60″`**. Ảnh siêu rộng chưa hiệu chuẩn `NTNU 0006.png` (`77,5°`) và ảnh 4 đốm `Zhao verification_img.npy` đều bị chặn **`LOST`** (`0% False Lock`).
- URL GitHub: `https://github.com/hoangtranduchai/star-tracker` (nhánh `main`, nhãn `v1.2.0-stage2`, xem `00_LINK_MA_NGUON_GITHUB.txt`). Mặt nạ núi/cây là heuristic kèm overlay để kiểm bằng mắt.

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

### 21. CNN có vượt được thuật toán chọn ngưỡng truyền thống kiểu ESA `tetra3` không?

**Trả lời:** Với bản nâng cấp **`CNN-Hybrid`** (MobileUNet lọc ngữ nghĩa + trừ nền `31×31` + cổng SNR vòng khuyên rỗng + lọc điểm nóng đơn pixel `pk_net/flux > 0,75` + tinh chỉnh tọa độ dưới mức pixel Windowed CoG), câu trả lời định lượng trên `566 khung × 5 phương pháp` (`benchmark_3way_comparison.json`) và `600 ca stress` (`benchmark_stress_curves.json`, **0% Khóa sai**) là **CÓ ở độ chính xác nền phức tạp/lóa/tiền cảnh và ảnh trời thật**:
- Giảm **-99,8% FP** so với `CNN gốc` (`1.118 → 2 FP` trên 500 khung sạch, `157 → 0 FP` trên 40 khung lóa) và giảm sai số Δθ **4×** (`7,99″ → 2,02″`).
- Vượt trực diện `tetra3` trên 500 khung sạch (`2,02″` vs `2,34″`), vượt gần **2×** độ chính xác & `+18,6%` Recall trên 40 khung lóa (`2,73″ / 69,9%` vs `5,06″ / 51,3%`), giữ **100%** khi tiêm `30` sao giả (trong khi `CoG` và `tetra3` giảm còn `70%`), và giải đúng cả 2 ảnh thực địa mà `tetra3` trả `LOST` là `Zhao MT9V022` (`48,26″`) và `Mount St. Helens` (`71,13″`).
- Đánh đổi trung thực: `CNN-Hybrid` chậm hơn ~1,8× trên nền sạch (`152 ms` vs `82–84 ms`) và suy giảm ở vận tốc quay góc cực cao `ω ≥ 1,5 °/s` (`40%–20%`) vì MobileUNet học trên PSF tròn. Chính vì vậy, kiến trúc mặc định **`Tự động (Auto: CoG → CNN-Hybrid)`** chạy `CoG` trước rồi chỉ nâng cấp `CNN-Hybrid` khi `CoG` trả `LOST` — đạt đồng thời `1,91″ / 85,8 ms` trên trời sạch, `100%` tới `ω = 1,5 °/s`, `100%` ở `30` sao giả, và giải trọn **4/4 ảnh trời thật hiệu chuẩn**.

### 22. Tại sao tốc độ tăng 5×–11× mà không phải giảm độ phân giải ảnh?

**Trả lời:** Giảm độ phân giải (downsample) sẽ phá hỏng độ chính xác cận pixel của tâm sao (`σ_centroid`) và mất sao mờ. Thay vào đó, nhóm xử lý đúng nút thắt cổ chai bằng thuật toán: (1) bộ tiền lọc góc 2 tầng dùng nhân ma trận BLAS `float32 SGEMM` trong `StarIdentifier.identify_wide` (`Mount St. Helens tetra3`: `11,3 s → 1,43 s`; `Zhao CoG`: `2,7 s → 0,25 s`), (2) vector hóa NumPy vòng lặp tinh chỉnh `trilateration_centroids`, (3) vẽ biểu đồ Matplotlib tĩnh trên luồng nền bất đồng bộ để Web UI phản hồi ngay với ảnh sạch không viền, và (4) tải sẵn trọng số CNN khi khởi động server (`STAR_TRACKER_PRELOAD=1`).

### 23. Dữ liệu PC chưa chứng minh sẵn sàng dùng trên vệ tinh — đội giải quyết câu này ra sao?

**Trả lời:** Nhóm giải quyết theo 2 tầng minh bạch: (1) **Gỡ bỏ 100% tuyên bố quá đà** (*sẵn sàng vệ tinh / ADCS*) ở toàn bộ slide, hồ sơ, báo cáo và Web UI, định vị trung thực dự án hiện ở mức **NASA TRL 3–4**; (2) **Đo kiểm định lượng ràng buộc phần cứng nhúng & môi trường vũ trụ mô phỏng** (`benchmark_embedded_cubesat.json`): trên đúng **1 nhân ARM64 (`aarch64`, không GPU)** nhánh `CoG/Auto` đạt **`59,2 ms` (`16,9 Hz`)**, `ESA Alt60` đạt **`62,5 ms` (`16,0 Hz`)**; chỉ rõ trung thực rằng `PyTorch CNN` chiếm `1.119 MB` RSS (bị OOM ở `768 MB` nên **MCU 1–16 MB SRAM chỉ chạy `CoG` port C/MISRA-C**, còn **SoC Linux ≥ 2 GB** mới chạy `Auto + ONNX` nhanh hơn **`4,75×`**); tiêm thử **100 vệt proton SAA/khung** (`CoG/Auto` giữ `100%`, `0% FL` trong khi `tetra3` sập còn `0%`) và tiêm **10.512 lỗi lật bit SEU** vào gói Telemetry 32 byte **`CRC-16-CCITT`** (`src/telemetry.py`, phát hiện `100,00%`). Nhóm cũng nêu rõ 5 cổng kiểm định phần cứng bắt buộc (MISRA-C, Collimator HIL, chiếu xạ TID/SEE, TVAC/rung phóng, bus CAN/SpaceWire ADCS) để lên TRL 6–8.

---

## Phần B — Câu hỏi Phản biện Chặng 2 (Hackathon: Tái lập Pipeline & Kiểm soát Dữ liệu Ảnh)

### 24. Làm sao chứng minh kho mã nguồn tải sạch (`git clone`) chạy lại được độc lập trên cả Linux, macOS và Windows mà không cần môi trường máy của đội?

**Trả lời:** Đội đã đóng gói **đủ 13/13 tệp cốt lõi (`36,02 MiB` / `37,77 MB`, checkpoint `17,71 MiB` / `18,57 MB`, mọi tệp `< 19 MB`, không cần Git LFS)** ngay trên nhánh `main` kèm [CHECKSUMS.sha256](../CHECKSUMS.sha256), [REPRODUCIBILITY.md](../REPRODUCIBILITY.md) và `.gitattributes` khóa chuẩn kết thúc dòng **LF** cho mọi tệp văn bản trong gói tái lập: checkpoint `MobileUNet_B10_50.pt`, 6 ảnh bầu trời thật hiệu chuẩn (`Alt40`, `Alt60`, `Zhao nightsky/verification`, `Mount St. Helens`, `NTNU 0006.png`), manifest hiệu chuẩn, config và danh mục `BSC5`/`IAU-CSN.txt`. Nhờ `.gitattributes`, cả `python scripts/verify_repro_bundle.py` lẫn `sha256sum -c CHECKSUMS.sha256` đều **PASS 13/13** trên cả bản clone `core.autocrlf=false` (Linux/macOS) lẫn `core.autocrlf=true` (Windows). Bộ kiểm thử đạt **`151 passed, 1 skipped`** (17 test chuyên biệt Chặng 2), và toàn bộ lệnh (`run_clean_repro.py`, `benchmark_3way_centroid_e2e.py --real-only` đủ 20 khung stress, `demo_star_tracker.py --focal-mm ...`) đều chạy sạch (`RC=0`, log tại `stage2_evidence/clean_clone_terminal_log.txt`).

### 25. Tại sao trong `src/centroid_cnn.py` dùng `torch.load(..., weights_only=False)`? Nếu tệp `.pt` bị sửa hoặc bị cắt cụt thì sao?

**Trả lời:** Trọng số công khai `MobileUNet_B10_50.pt` của tác giả Zhao et al. được lưu bằng `torch.save(model)` toàn đối tượng nên PyTorch 2.6+ cần `weights_only=False`. Để loại bỏ rủi ro giải tuần tự pickle từ tệp hỏng hoặc bị chỉnh sửa, đội đã bổ sung **`inspect_checkpoint_status()` và `verify_checkpoint_integrity()` trong `src/centroid_cnn.py`** kiểm tra tồn tại tệp trước kích thước (phát hiện tệp cắt cụt `CHECKPOINT_TRUNCATED`) và đối chiếu mã băm **SHA-256** khớp `CHECKSUMS.sha256` (`e02d7723b832d12c...`) **trước** khi gọi `torch.load` (kể cả trong `scripts/benchmark_embedded_cubesat.py`). Nếu sai lệch dù chỉ 1 byte, hệ thống **chặn tuyệt đối `torch.load`**, ném `CHECKPOINT_SHA256_MISMATCH`, ghi đúng `checkpoint_status="checksum_mismatch"` kèm `checkpoint_sha256`, và tự chuyển về `CoG` kèm cảnh báo/nhật ký `FALLBACK_TO_COG` (đã chứng minh trên cả `pytest` lẫn bản clone sạch tại `clean_clone_terminal_log.txt`).

### 26. Khi CNN lỗi hoặc thiếu checkpoint, hệ thống có âm thầm dùng CoG không? Kể cả ở chế độ mặc định `Auto-Router` hay API so sánh `/api/compare`?

**Trả lời:** **Tuyệt đối không âm thầm (0% fallback ngầm trên mọi lối vào).** Ở cả chế độ chọn trực tiếp `cnn`, chế độ mặc định `auto` (khi `Auto-Router` thử nâng cấp sang CNN mà gặp thiếu/lỗi checkpoint), lẫn API `/api/compare` (kể cả khi truyền `backends=["auto"]` hoặc `["cnn"]`):
1. `src/centroid_cnn.py` ghi `logging.warning(...)` và lưu nguyên nhân thực (`FileNotFoundError` / `CHECKPOINT_SHA256_MISMATCH` / `CHECKPOINT_TRUNCATED`) với đường dẫn đã chuẩn hóa tương đối (không lộ đường dẫn OS nội bộ).
2. `src/pipeline.py` và `src/demo_session.py` (`run()` & `compare()`) phân biệt tường minh `requested_backend` (`cnn`/`auto`) với `executed_backend` (`classical`), gắn `centroid_fallback=True`, `execution_mode_summary="... -> classical [FALLBACK_TO_COG]"`, `checkpoint_status`, `checkpoint_sha256`, `fallback_reason` và bật bit cờ `FLAG_FALLBACK_USED (0x08)` trong gói Telemetry 32 byte.
3. `src/execution_log.py` ghi ngay bản ghi có cấu trúc bằng `os.replace` (kèm retry Windows) vào `data/outputs/execution_log.jsonl`, tra cứu an toàn theo phiên qua `GET /api/execution-log` (chặn truy cập thô `GET /output/*.jsonl` trả HTTP `404`).
4. Giao diện Web bật dải cảnh báo màu hổ phách **`FALLBACK → CoG`** nổi bật ngay đầu trang; CLI `demo_star_tracker.py` in rõ `[WARNING] FALLBACK TO CoG TRIGGERED!`. BGK có thể bấm nút 1 chạm **"Thử nghiệm Fallback CNN → CoG"** ngay trên bản trực tuyến để kiểm chứng mà không ảnh hưởng checkpoint thật.

### 27. Trước đây hồ sơ ghi «không lưu ảnh người xem» nhưng `app.py` lại ghi tệp & sidecar vào `data/uploads/`. Đội sửa mâu thuẫn này ra sao?

**Trả lời:** Đội đã sửa **cả mã nguồn lẫn tài liệu** cho khớp 100%:
- **Tách vùng lưu trữ, chống ghi đè & cô lập phiên chống IDOR:** Ảnh mẫu kiểm chuẩn chỉ đọc nằm cố định tại `data/uploads/`; mọi ảnh, `sidecar.json`, `meta.json` và 4 ảnh xem trước do người dùng tải lên được cách ly vào `data/user_uploads/<upload_id>/` với `upload_id` là UUID4 16 ký tự tạo bằng `mkdir(exist_ok=False)` và gắn cookie phiên trình duyệt `st_sid` (`HttpOnly`, `SameSite=Lax`, `Secure` trên HTTPS; luôn ghi `meta.json` và cấp `st_sid` ngay cả khi gọi thẳng API upload) → hai tệp trùng tên (kể cả trùng tên ảnh mẫu `mount_st_helens_1.png`) tuyệt đối không ghi đè nhau hay ảnh mẫu, người dùng khác không thể liệt kê/xem/xóa ảnh tạm hay xem nhật ký upload của nhau (`HTTP 404`), và lỗi HTTP 400/409 lập tức rollback xóa sạch (`ERROR_ROLLBACK_DELETE`, 0 tệp mồ côi).
- **2 chế độ lưu minh bạch & dọn rác tự động (startup + 60s):** Mặc định **`ephemeral` (Xóa ngay trong `finally:` / 0s sau xử lý)** xóa vĩnh viễn toàn bộ thư mục tạm trước khi trả HTTP response (`verified_gone_on_disk=True`, preview trả inline base64); tùy chọn **`ttl` (tối đa 15 phút / 900s)** có quét dọn tức thì khi khởi động server (startup orphan sweep) + luồng nền tự dọn mỗi 60s (`TTL_EXPIRED_AUTO_PURGE`) và cho phép người dùng bấm **Xóa ngay** / **Xóa tất cả** qua UI hoặc API (`GET /api/uploads`, `DELETE /api/uploads/<id>`, `DELETE /api/uploads`).
- **Đồng bộ tài liệu:** Đã sửa đoạn P184 & T14R8 trong `[StarTracker] - Hồ sơ dự án.docx`, mục 11 trong `AI2026_Ho-so-du-an_StarTracker.md` & `.docx`, `README.md`, `REPRODUCIBILITY.md`, 22 slide PPTX và công bố ngay trên giao diện tải ảnh.

### 28. Khi chế độ `ephemeral` xóa ngay trong `finally:` (0s sau xử lý), thế còn các ảnh kết xuất `demo_clean.png`, `demo_input.png`, `demo_output.png`, `demo_result.png` có bị lưu đè ở `data/outputs/` không?

**Trả lời:** **Không hề.** Toàn bộ ảnh xem trước cho lượt tải lên (`/api/run-upload` và `/api/compare-upload`) được kết xuất trong chính thư mục cách ly `data/user_uploads/<upload_id>/`, **không chạm tới** `data/outputs/demo_*.png` dùng chung:
- Ở chế độ **`ephemeral`**: ảnh xem trước được mã hóa trả trực tiếp dạng inline `data:image/png;base64,...` trong JSON response, sau đó `finally:` xóa trọn thư mục `data/user_uploads/<upload_id>/` → 0 tệp ảnh gốc, 0 sidecar, 0 `meta.json`, 0 ảnh preview sót lại trên đĩa sau khi trả kết quả.
- Ở chế độ **`ttl`**: ảnh xem trước phục vụ qua `GET /api/uploads/<upload_id>/preview/<filename>` (kiểm tra cookie phiên `st_sid` & `meta.json` chống IDOR); ngay khi người dùng bấm Xóa (`DELETE /api/uploads/<id>`) hoặc hết hạn TTL, cả tệp gốc + sidecar + `meta.json` + preview đều bị xóa đồng thời, DOM xóa sạch URL preview và URL preview trả **`404`** tức thì (đã kiểm chứng trên cả 17 test Chặng 2 lẫn Chromium thực tế).

### 29. Vì sao không đóng gói luôn 540 khung mô phỏng `hd1024` (~373 MB) vào kho Git?

**Trả lời:** Kho Git được tối ưu ở mức `36,02 MiB` (`37,77 MB`) cho gói tái lập cốt lõi (13/13 tệp thật + checkpoint, dưới giới hạn 50 MB/tệp của GitHub để `git clone` nhanh trong vài giây không cần Git LFS). Trên bản tải sạch, BGK vẫn chạy được ngay `scripts/run_clean_repro.py`, `scripts/benchmark_3way_centroid_e2e.py --real-only` (6 ảnh trời thật hiệu chuẩn + 20 khung stress Rìa TĐ/mây, `86,5 s`), `scripts/benchmark_end_to_end.py --suites real seed42 stress` và `benchmarks/monte_carlo.py --trials 100 --mode fast --catalog bsc5` mà không bị lỗi thiếu dữ liệu; nếu cần tái sinh 500 khung sạch `hd1024` và 40 khung lóa `hd1024_glare`, chạy `python scripts/benchmark_centroid_cnn_hd1024.py` và `python scripts/benchmark_centroid_cnn_glare.py` (hoặc `python scripts/generate_sim_dataset.py` cho bộ `fast`/`full`).

---

## Kịch bản Demo trực tiếp Chặng 2 (90 giây trước Ban Giám khảo trên `https://startracker.agentlens.dpdns.org`)

1. **Giây 0–25 — Gói tái lập & Checksum SHA-256:** Mở Tab **«Cấu hình, Checksum & Dữ liệu»** → chỉ bảng **13/13 tệp `verified` (`36,02 MiB / 37,77 MB`)** gọi trực tiếp từ `GET /api/repro-status` (gồm checkpoint `MobileUNet_B10_50.pt`, 6 ảnh thật hiệu chuẩn, manifest, catalog BSC5) và bảng Nhật ký thực thi đang hiển thị trực tiếp bên dưới.
2. **Giây 25–50 — Báo rõ Fallback CNN → CoG:** Bấm nút 1 chạm **«Thử nghiệm Fallback CNN → CoG»** → chỉ ngay dải cảnh báo màu cam **`FALLBACK → CoG`** hiện ở đầu trang kèm lý do đường dẫn tương đối an toàn và bản ghi `cnn -> classical [FALLBACK_TO_COG]` vừa xuất hiện trên bảng **Nhật ký Mode Thực thi (`execution_log.jsonl`)**.
3. **Giây 50–90 — Chống ghi đè & Quyền xóa tức thì:** Mở ngăn **«Tùy chỉnh & Tải ảnh»** → chọn chế độ **Lưu tạm 15 phút (TTL)**, tải lên **2 lần liên tiếp cùng tên tệp `mount_st_helens_1.png`** → chỉ 2 thư mục UUID4 hoàn toàn riêng biệt trong `data/user_uploads/<id>/` (ảnh mẫu `data/uploads/` giữ nguyên SHA-256) → bấm **«Xóa ngay»** / **«Xóa tất cả»** → xác nhận danh sách về **0 ảnh tạm trên đĩa**, DOM xóa sạch ảnh cũ, preview trả `404` và sự kiện **`DATA_DELETION`** ghi dấu ngay trong Nhật ký kiểm toán.

---

## Không được nói

1. Chỉ trình bày đúng cấu hình camera demo (APS-C 50 mm trên Laptop) và dữ liệu thật công khai (`ESA tetra3`, `Zhao MT9V022`, `UW LOST Mount St. Helens`, `NTNU 0006.png`).
2. Không gán GSD mét cho star tracker; **không** gọi phần mềm demo là thiết bị bay hay khẳng định đã sẵn cho ADCS vệ tinh.
3. Không nói «CNN luôn tốt hơn» — trên 500 khung sạch & 40 lóa, CoG thắng cả RMSE lẫn 3-DOF E2E.
4. Không gọi ảnh núi là ảnh nhóm chụp — là mẫu LOST công bố của ĐH Washington.
5. Không bịa số hay trích dẫn số mồ côi không có log kiểm toán; chỉ trích đúng số từ `log_reconciliation_audit.json` và các JSON Chặng 1.
