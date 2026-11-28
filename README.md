# Star tracker

Demo trên laptop (Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin): từ ảnh bầu trời sao ra quaternion hướng camera. Đường ống mặc định là **centroid (trọng tâm) → Pyramid (Mortari) / K-vector → Wahba (SVD hoặc QUEST)**. Đầu ra là quaternion J2000, **4 × float32 = 16 byte**.

Tùy chọn: centroid CNN theo trọng số công khai MobileUNet của Zhao và cộng sự (arXiv:2404.19108), không huấn luyện lại. Nếu thiếu trọng số hoặc suy luận lỗi thì quay về trọng tâm cổ điển.

Camera trong demo là một **máy ảnh tĩnh phổ thông**: cảm biến cỡ APS-C khoảng 24 megapixel và ống kính tiêu cự **50 mm**. Không ghi tên cảm biến và không ghi tên ống kính.

- **Demo Web trực tuyến 24/7:** https://startracker.agentlens.dpdns.org (giao diện không gian vũ trụ 3D J2000 5.023 sao thực Yale BSC5 & đối chiếu tâm sao trực tiếp).

## Camera demo

| Hạng mục | Giá trị |
|---|---|
| Mảng | **6000 × 4000** |
| Cạnh pixel | **3,72 µm** |
| Tiêu cự | **50 mm** |
| Trường nhìn | **25,16° × 16,93°**, đường chéo **30,03°** |
| Thước góc | **15,35″/pixel** |
| FAST (gộp 4×4) | **1500 × 1000**, cạnh pixel **14,88 µm**, cùng trường nhìn, **61,38″/pixel** |
| Tâm ảnh | cột `(6000−1)/2 = 2999,5`, hàng `(4000−1)/2 = 1999,5` |

Công thức: \(f_x = f / p\), trường nhìn \(2\arctan(\text{cạnh cảm biến} / 2f)\).

Ảnh khác kích thước vẫn giải được nếu nhập tiêu cự thật (mm) và cạnh pixel của đúng file (µm). Không dùng tiêu cự quy đổi 35 mm.

## Thuật toán & Chốt chặn an toàn (Vòng Chung kết · Chặng 1)

1. **Centroid** — mặc định: nền theo khối, ngưỡng theo độ lệch, opening nhị phân, connected components, trọng tâm cửa sổ (`CoG`). Tùy chọn: MobileUNet công khai (Zhao et al., `arXiv:2404.19108`) + trilateration (`centroid_backend=cnn`), hỗ trợ ảnh thật **8-bit, 12-bit (`/16`) và 16-bit (`/256` + xếp hạng contrast SNR)**. Nếu thiếu trọng số hoặc suy luận lỗi sẽ tự fallback về `CoG`.
2. **Nhận dạng sao** — góc giữa các sao, bảng **K-vector**, **Pyramid (Mortari)** và gán các sao còn lại trên catalog mặc định **Yale BSC5** (`V ≤ 6`, 5.023 sao; hỗ trợ `Hipparcos V ≤ 7` tùy chọn). Không khớp chòm sao văn hóa.
3. **Wahba + Chốt chặn chống khóa sai (`0% False Lock`)** — `src/camera.py` hỗ trợ tâm `(cx, cy)` hiệu chuẩn; `src/attitude.py` kiểm tra hạng hình học bằng SVD (`s_min >= 1e-6`, chặn hình học thẳng hàng `COLLINEAR_DEGENERATE_GEOMETRY`); `src/pipeline.py` lọc ngoại lai lặp `_refine_inliers` cả **trước và sau** `_associate_remaining` (không `break` giữ ngoại lai khi `< 3` inlier), kiểm dư RMS hậu kiểm, cưỡng chế `min_stars >= 4` và kiểm mật độ FOV (`LOW_FOV_CONSISTENCY`).
4. **Đầu ra `TrackerResult` & Downlink 16 byte** — khi hợp lệ trả `status="SOLVED"` kèm `q = [w, x, y, z]` (J2000, `4 × float32`) và `match_stats`; khi không đạt trả `status="LOST"`, `q=None`, `reject_code` cụ thể và gói downlink **16 byte `0x00`**.

Bảng góc mặc định phủ tới **30,5°** (đường chéo trường nhìn demo). Ảnh rộng hơn thì lần đầu dựng bảng mới và lưu trong `data/catalogs/`.

Hằng số electron, nhiễu đọc và dòng tối trong `config/camera_specs.json` có `"assumption": true`. Đó là số để mô phỏng trên PC, không phải số đo phần cứng vệ tinh hay cảm biến bay thực tế.

> **Phạm vi kiểm chứng (Demo trên PC):** Toàn bộ số liệu bên dưới đo trên **PC Laptop (NVIDIA GeForce RTX 5070 Laptop GPU + CPU)** — phần mềm nghiên cứu mô phỏng & thử nghiệm dữ liệu công khai, **chưa kiểm chứng** trên phần cứng vệ tinh, chip nhúng chịu bức xạ, nhiệt chân không hay giao tiếp ADCS thực tế.

## Kết quả kiểm chứng sau cải tiến (Chặng 1)

| Thử nghiệm | CoG (Mặc định) | CNN MobileUNet (`d_th=2,0`) | False Lock Rate |
|---|---|---|---|
| **Stress đối kháng (100 ca)** (`benchmark_rejection_stress.json`) | Từ chối `LOST` 100/100 (`16B 0x00`) vs Legacy `41/100` | Dùng chung chốt chặn hậu kiểm & SVD | **`0,0%` (`0/100`)** vs `41,0%` cũ |
| **500 khung sạch `hd1024` E2E** (`benchmark_sim_hd1024_e2e.json`) | `500/500 <40″` (`100,0%`), `Δθ` tv **`2,00″`** (`P90 6,26″`), `87,2 ms` | `500/500 solved`, `498/500 <40″` (`99,6%`), `Δθ` tv **`7,94″`**, `123,9 ms`, `1.118 FP` | **`0,0%` (`0/500`)** |
| **500 khung `thr2` Centroid** (`log_reconciliation_audit.json`) | `25.206/27.017` (`Rec 93,30%` · `Prec 100,00%` · `0 FP`), RMSE `0,1804 px`, `34,2 ms` | `25.050/27.017` (`Rec 92,72%` · `Prec 75,36%` · `8.191 FP`), RMSE `0,4745 px`, `60,2 ms` | — |
| **40 khung lóa mạnh E2E** (`benchmark_sim_glare_e2e.json`) | `40/40 <40″`, `Δθ` tv **`1,99″`**, `78,3 ms` | `40/40 solved`, `39/40 <40″`, `Δθ` tv **`10,59″`**, `131,1 ms`, `157 FP` | **`0,0%` (`0/40`)** |
| **Seed 42 FAST** (`seed42_cog_vs_cnn.json`) | **`0,446″`** (`36/36`, Prec/Rec `100%`, `146,4 ms`) | **`1,648″`** (`30/36`, Prec `85,7%`, Rec `83,3%`, `399,5 ms` / warm `226,1 ms`) | **`0,0%`** |
| **Ảnh trời thật hiệu chuẩn** (`benchmark_real_calibrated_e2e.json`) | `1/5` BSC5 (`Alt60 2,26″`); `Alt40 Hip V≤7 39,51″`; `MSH LOST [INSUFFICIENT_INLIER_PAIRS]` | `3/5` BSC5 (`Alt60 4,65″`, `Zhao 54,70″`, `MSH 0,034°` vs UW LOST / `54/79` ~`2,76 s`); `Alt40 Hip V≤7 26,60″` | **`0,0%`** (kể cả `0006.png` & `verification`) |

### Nâng cấp bổ sung Chặng 1: `CNN-Hybrid`, `Auto-Router (CoG → CNN-Hybrid)`, Ngưỡng kiểu ESA `tetra3` & Tăng tốc 5×–11×

Chi tiết đầy đủ nằm tại `data/outputs/benchmark_3way_comparison.json` (**566 khung × 5 phương pháp = 2.830 lượt**) và `data/outputs/benchmark_stress_curves.json` (**600 lượt stress ω / sao giả / lóa**), toàn bộ **3.430 lượt đều đạt 0,0% Khóa sai**:

| Phương pháp | 500 sạch (`hd1024`) | 40 lóa (`glare`) | 20 Rìa TĐ + Mây | 4 ảnh trời thật hiệu chuẩn | Stress 30 sao giả / `ω=1,5°/s` |
|---|---|---|---|---|---|
| **CoG (Nhóm)** | `500/500`, **`1,91″`**, `0 FP`, `84,3 ms` | `40/40`, **`1,54″`**, `69,9% Rec`, `74,2 ms` | `20/20`, **`2,46″`** | `3/4` (`Zhao LOST`) | `70%` / `100%` |
| **Ngưỡng kiểu `tetra3`** | `500/500`, `2,34″`, `0 FP`, `82,4 ms` | `40/40`, `5,06″`, `51,3% Rec`, `77,2 ms` | `20/20`, `2,90″` | `2/4` (`Zhao & MSH LOST`) | `70%` / `100%` |
| **CNN gốc (Trước)** | `498/500`, `7,99″`, `1.118 FP`, `125,6 ms` | `39/40`, `9,82″`, `157 FP`, `140,1 ms` | `20/20`, `14,58″` | `4/4` (`MSH 120,3″`) | — |
| **`CNN-Hybrid` (Sau)** | **`500/500`**, **`2,02″`**, **`2 FP` (-99,8%)**, `152,4 ms` | **`40/40`**, **`2,73″`**, **`0 FP` (-100%)**, `69,9% Rec` | `20/20`, `3,17″` (`75 FP` thấp nhất) | **`4/4`** (`Alt60 6,8″`, `Zhao 48,3″`, `MSH 71,1″`) | **`100%`** / `40%` (giới hạn PSF tròn) |
| **`Auto (CoG → CNN)`** *(Mặc định Web)* | **`500/500`**, **`1,91″`**, **`0 FP`**, **`85,8 ms`** | **`40/40`**, **`1,54″`**, **`0 FP`**, **`77,8 ms`** | **`20/20`**, **`2,46″`** | **`4/4`** (`Alt60 2,3″`, `Zhao 48,3″`, `MSH 49,5″`) | **`100%`** / **`100%`** |

- **Tối ưu tốc độ 5×–11× không giảm độ phân giải:** Bộ tiền lọc góc 2 tầng BLAS `float32 SGEMM` trong `StarIdentifier.identify_wide` (`Mount St. Helens tetra3`: `11,3 s → 1,43 s`; `Zhao CoG`: `2,7 s → 0,25 s`), vector hóa NumPy `trilateration_centroids`, vẽ đồ thị Matplotlib nền bất đồng bộ trên `app.py` và tải sẵn trọng số CNN (`STAR_TRACKER_PRELOAD=1`).
- **Kiểm toán khả thi nhúng CubeSat & Tiêm lỗi vũ trụ mô phỏng (`benchmark_embedded_cubesat.json`, NASA TRL 3–4 — chưa kiểm chứng bay):**
  - **1 nhân ARM64 (`aarch64`, `--cpus=1.0`, `OMP=1`):** `CoG` **`58,8 ms` (`17,0 Hz`)**, `Auto` **`59,2 ms` (`16,9 Hz`)**, `ESA Alt60` **`62,5 ms` (`16,0 Hz`)**, Peak RSS `328,2 MB`; `PyTorch CNN` `4.782,7 ms` / `1.119,2 MB` RSS (OOM ở `768 MB` → MCU chỉ chạy `CoG` port C; SoC Linux ≥ 2 GB chạy `Auto`). Xuất **ONNX FP32 (1 luồng)** tăng tốc **`4,75×`** (`6.678 → 1.405 ms`, `12,5 MB`, FP16 `6,3 MB`).
  - **Mưa hạt Proton vùng SAA (`0–100` vệt xiên/khung):** `CoG` & `Auto` giữ **`100,0%`** (`2,2″`, `0% FL`) ở cả `100` vệt/khung (khi `tetra3` giảm còn `0,0%` từ `50` vệt).
  - **Gói Telemetry 32 byte bảo vệ bằng `CRC-16-CCITT` (`src/telemetry.py`):** phát hiện **`10.512 / 10.512` (`100,0000%`)** lỗi lật bit SEU (`512` 1-bit vét cạn + `5.000` 2-bit + `5.000` burst 4–16 bit).

## Tái lập Độc lập, Minh bạch Fallback CoG & Kiểm soát Dữ liệu Ảnh (Chặng 2)

Chi tiết đầy đủ hướng dẫn chạy từ bản tải sạch nằm trong [REPRODUCIBILITY.md](REPRODUCIBILITY.md) và bảng mã băm [CHECKSUMS.sha256](CHECKSUMS.sha256).

- **Gói tái lập độc lập đóng gói sẵn (13/13 tệp, `36,03 MB`, kiểm chứng SHA-256):** Bao gồm checkpoint `MobileUNet_B10_50.pt`, toàn bộ 6 ảnh bầu trời thật hiệu chuẩn (`Alt40`, `Alt60`, `nightsky_june16_2021.npy`, `verification_img.npy`, `mount_st_helens_1.png`, `0006.png`), `manifest_real_calibrated.json`, `metadata.yaml`, `config/camera_specs.json`, `config/pipeline_default.json`, `data/catalogs/BSC5` và `IAU-CSN.txt`.
- **Chạy kiểm chứng 1 lệnh từ bản clone sạch:**
  ```text
  python scripts/verify_repro_bundle.py
  python scripts/run_clean_repro.py
  ```
- **Minh bạch chế độ thực thi & Fallback CoG:** Mọi lượt chạy qua CLI (`demo_star_tracker.py --centroid ... [--simulate-cnn-fallback]`) và Web API (`/api/run`, `/api/compare`, `/api/run-upload`) đều ghi nhật ký cấu trúc JSONL tại `data/outputs/execution_log.jsonl` (`GET /api/execution-log`) phân biệt rõ `requested_backend` vs `executed_backend`, `fallback_triggered`, `fallback_reason` và hiển thị dải cảnh báo `FALLBACK → CoG` trực tiếp trên giao diện khi CNN phải chuyển về CoG.
- **Kiểm soát lưu ảnh người dùng, chống ghi đè & quyền xóa (`src/upload_store.py`):**
  - Ảnh mẫu đọc-chỉ nằm cố định tại `data/uploads/` và **không bao giờ bị ghi đè hay xóa** khi người dùng tải ảnh lên.
  - Ảnh người dùng + sidecar JSON + ảnh xem trước tải lên qua Web được cách ly hoàn toàn vào thư mục UUID4 16 ký tự độc lập tại **`data/user_uploads/<upload_id>/`** (hai tệp trùng tên, kể cả `mount_st_helens_1.png`, luôn nhận hai thư mục khác nhau — **0% nguy cơ ghi đè** tệp mẫu hay `data/outputs/demo_*.png` dùng chung).
  - **Chế độ mặc định (`retention_mode=ephemeral`):** ảnh xem trước trả inline dạng `data:image/png;base64,...` và toàn bộ tệp gốc, sidecar, preview tạm bị xóa vĩnh viễn ngay trong khối `finally:` sau khi giải tư thế xong (**0 giây / 0 byte lưu đĩa**, xác minh `verified_gone_on_disk=True`).
  - **Chế độ lưu tạm tùy chọn (`retention_mode=ttl`):** giữ tạm tối đa **15 phút (`900 s`)**, phục vụ preview cách ly tại `/api/uploads/<upload_id>/preview/<name>`, tự động dọn khi hết hạn, đồng thời người dùng có thể kiểm tra và xóa tức thì từng tệp hoặc toàn bộ qua giao diện hoặc API (`GET /api/uploads`, `DELETE /api/uploads/<upload_id>`, `DELETE /api/uploads`, sau khi xóa preview trả `404` ngay lập tức), mọi thao tác xóa đều ghi dấu `DATA_DELETION` vào `execution_log.jsonl`.

![Sơ đồ kiến trúc Pipeline & Kiểm soát Dữ liệu Ảnh (Chặng 2)](data/outputs/e2e_figures/stage2_pipeline_architecture.png)

## Chạy & Tái lập kiểm thử

```text
pip install -r requirements.txt
pytest -v
python scripts/verify_repro_bundle.py
python scripts/run_clean_repro.py
python scripts/benchmark_3way_centroid_e2e.py --real-only
python scripts/benchmark_end_to_end.py --suites real seed42 stress
python scripts/benchmark_stress_curves.py
python scripts/benchmark_embedded_cubesat.py
python scripts/reconcile_logs.py
python demo_star_tracker.py --mode fast --seed 42 --lookup --no-show
python app.py
```

Trọng số CNN công khai (không huấn luyện lại):

```text
third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt
```

Nguồn: https://github.com/HongruiZhao/CNNStarDetectCentroid — bài arXiv:2404.19108.

`app.py` mở giao diện Web tại `http://127.0.0.1:8765/` (hoặc truy cập bản trực tuyến 24/7 tại https://startracker.agentlens.dpdns.org; hỗ trợ `STAR_TRACKER_NO_BROWSER=1` / `--no-browser` và `STAR_TRACKER_PORT`) với thanh kịch bản nhanh (**`Bầu trời chuẩn`**, **`Trời thực ESA`**, **`Núi St. Helens`**, **`Ngược nắng`**), hiển thị trực tiếp trạng thái `SOLVED` / `LOST`, `reject_code`, số cặp inlier, dư góc RMS/Max và gói 16 byte. Giao diện tích hợp endpoint `GET /api/sky-catalog` dựng không gian 3D quỹ đạo Trái Đất, dải Ngân Hà và thiên cầu thực J2000 (**5.023 sao Yale BSC5**, cấp sáng V ≤ 6) ở hai góc nhìn (`Quỹ đạo Trái Đất` và `Góc nhìn Cảm biến 1:1` theo ma trận DCM từ quaternion `q_est`), cho phép **đối chiếu trực quan tư thế vệ tinh 3D trên nền sao thực với ảnh sao không viền** (lưu ý: đây là mô phỏng trực quan chạy trên máy tính, không phải phần cứng bay hay vòng điều khiển ADCS thực tế).

Một khung đã lưu:

```text
python demo_star_tracker.py --image duong/dan/anh.tif --focal-mm 50 --pixel-um 3.72 --lookup --no-show
```

Khung đúng **6000×4000** hoặc **1500×1000** có thể bỏ qua hai cờ tiêu cự và cạnh pixel. File khác kích thước thì phải nhập cả hai.

## Thư mục

```text
app.py                         giao diện demo
demo_star_tracker.py           chạy dòng lệnh
config/camera_specs.json       thông số camera demo
config/pipeline_default.json   ngưỡng centroid và dung sai góc
src/                           camera, catalog, centroid, nhận dạng, Wahba, mô phỏng
web/                           giao diện
scripts/                       tải catalog, sinh ảnh giả lập
tests/                         pytest
data/catalogs/                 Yale BSC5, tên sao IAU
data/uploads/                  ảnh mẫu, mỗi bộ giữ thông số riêng
THIRD_PARTY_NOTICES.md         giấy phép mã tham khảo
```

Mã tham khảo, không copy nguyên văn: [ESA tetra3](https://github.com/esa/tetra3) (Apache-2.0), [UW LOST](https://github.com/UWCubeSat/lost) (MIT), toán QUEST / K-vector / Hipparcos đã công bố trong NASA COTS Star Tracker.

## Ảnh mẫu

Ảnh thử trong `data/uploads/` được giữ. Mỗi bộ có tiêu cự và cạnh pixel của chính nó, ghi trong README hoặc metadata cạnh ảnh. Những số đó không phải camera demo ở bảng trên. Thiếu tiêu cự hoặc cạnh pixel thì pipeline không tự đoán được.

Ảnh giả lập mới, nếu cần sinh lại:

```text
python scripts/generate_sim_dataset.py
```
