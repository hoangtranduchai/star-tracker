# BÁO CÁO CẢI TIẾN VÒNG CHUNG KẾT · CHẶNG 2 (HACKATHON)

**Cuộc thi Sáng tạo trẻ Quốc gia trong lĩnh vực Trí tuệ nhân tạo năm 2026 (Bảng C)**  
**Đội thi:** `DUT.StarTracker` (`AI26C0083`) — Trường Đại học Bách khoa, Đại học Đà Nẵng (Khoa Công nghệ thông tin)  
**Đề tài:** *Star Tracker — Hệ thống định hướng camera bầu trời sao lai CoG | CNN (Demo nghiên cứu trên PC)*  
**Ngày nộp:** `28/11/2026` · **Phiên bản mã nguồn:** `v1.2.0-stage2` (nhánh `main`, commit nền `3c6d5a6`)  
**Đề cải tiến Phiên bản 1:** *1. Tái lập pipeline và kiểm soát dữ liệu ảnh*

---

## 1. Phân tích vấn đề của Đề cải tiến Chặng 2 (Phiên bản 1)

Theo đề bài Chặng 2 (**"1. Tái lập pipeline và kiểm soát dữ liệu ảnh"**), hệ thống sau Chặng 1 tồn tại hai lỗ hổng quan trọng cần khắc phục triệt để trong thời gian Hackathon:

1. **Chưa đủ gói tái lập độc lập từ bản tải sạch:** Trong `.gitignore` trước đây, trọng số `third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt` (`17,71 MiB (18,57 MB)`) và 6 ảnh bầu trời thật hiệu chuẩn (`Alt40`, `Alt60`, `nightsky_june16_2021.npy`, `verification_img.npy`, `mount_st_helens_1.png`, `0006.png`) đều bị loại trừ khỏi kho Git; chưa có tệp `CHECKSUMS.sha256` chuẩn đa nền tảng và chưa có quy trình 1 lệnh tự động xác minh lại từ một bản `git clone` sạch.
2. **Mâu thuẫn giữa cam kết dữ liệu ảnh và mã nguồn thực tế + thiếu cảnh báo fallback tường minh:**
   - Tại Hồ sơ dự án (`[StarTracker] - Hồ sơ dự án.docx`, đoạn P184), tài liệu cũ ghi *"Giao diện không có tài khoản người dùng và không lưu ảnh người xem"*, trong khi mã nguồn `app.py` cũ (`/api/run-upload`, `/api/compare-upload`) lại ghi trực tiếp tệp ảnh và tệp sidecar `.json` vĩnh viễn vào `data/uploads/<safe_name>`.
   - Cách ghi phẳng này gây ra **3 rủi ro đồng thời**: (a) lưu vĩnh viễn ảnh người dùng không có thời hạn xóa hay nút xóa, (b) **ghi đè lẫn nhau** khi 2 người dùng tải tệp trùng tên, và (c) **nguy cơ ghi đè ảnh mẫu kiểm chuẩn** (ví dụ tải tệp `mount_st_helens_1.png` sẽ phá hủy tệp mẫu trong `data/uploads/`).
   - Khi yêu cầu chạy `CNN` (hoặc `Auto-Router` / `/api/compare`) nhưng thiếu/hỏng trọng số hoặc lỗi suy luận, hệ thống chưa có **nhật ký cấu trúc phân biệt chế độ yêu cầu vs thực thi**, chưa chặn tệp `.pt` giả mạo trước `torch.load`, và chưa có dải cảnh báo `FALLBACK → CoG` nổi bật kèm nguyên nhân cụ thể.

| Hạng mục kiểm toán | Hiện trạng trước Chặng 2 (`v1.1.0-stage1`) | Giải pháp sau Chặng 2 (`v1.2.0-stage2`) |
|---|---|---|
| **Gói tái lập độc lập & LF đa nền tảng** | `.gitignore` bỏ qua `MobileUNet_B10_50.pt` (`17,71 MiB (18,57 MB)`) và 6 ảnh trời thật; chưa có `CHECKSUMS.sha256` / `.gitattributes` | Đóng gói đủ **13/13 tệp (`36,02 MiB (37,77 MB)`, không cần LFS)** kèm `.gitattributes` khóa LF (13/13 OK trên cả Linux/macOS lẫn Windows `autocrlf=true`), `CHECKSUMS.sha256`, `REPRODUCIBILITY.md` & `run_clean_repro.py` |
| **Bảo vệ Checkpoint & Báo rõ Fallback CoG** | Chưa kiểm SHA-256 trước `torch.load`; dễ fallback ngầm trên `cnn`/`auto`/`/api/compare` | Runtime Guard xác thực SHA-256 trước `torch.load(..., weights_only=False)` (chặn `CHECKPOINT_SHA256_MISMATCH`/`CHECKPOINT_TRUNCATED`); 0% fallback ngầm trên mọi nhánh, bật bit `FLAG_FALLBACK_USED (0x08)`, dải cảnh báo cam Web UI & nhật ký nguyên tử `execution_log.jsonl` |
| **Lưu trữ, Chống ghi đè & Cô lập phiên** | `app.py` ghi phẳng vào `data/uploads/<safe_name>` (ghi đè tệp trùng tên & ảnh mẫu `mount_st_helens_1.png`, chạm `demo_*.png` chung) | Cách ly hoàn toàn vào **`data/user_uploads/<uuid4>/`** (`mkdir(exist_ok=False)`), luôn ghi `meta.json` + cookie `st_sid` (`HttpOnly`, `SameSite=Lax`, `Secure`, tự cấp ngay cả khi gọi API không cookie → chống IDOR), tách khỏi ảnh mẫu đọc-chỉ `data/uploads/` |
| **Thời gian lưu, Rollback & Quyền xóa** | Lưu vĩnh viễn trên đĩa; không có API/nút xóa; P184 hồ sơ mâu thuẫn *"không lưu ảnh người xem"* | Mặc định `ephemeral` xóa sạch trong `finally:` (0s sau xử lý, preview inline base64); tùy chọn `ttl` 15 phút (`900s`, quét khởi động + luồng nền mỗi `60s`, rollback lỗi 400/409); `DELETE /api/uploads[/<id>]` (preview `404` ngay, xóa DOM, thoát XSS) & đồng bộ 100% P184 Hồ sơ |

---

## 2. Thiết kế & Triển khai Giải pháp Cải tiến Chặng 2

### 2.1. Gói Tái lập Độc lập 13/13 tệp, Checksum SHA-256 Đa nền tảng & Runtime Guard (`CHECKSUMS.sha256`, `.gitattributes`, `REPRODUCIBILITY.md`)

- **Đóng gói đầy đủ vào kho Git chuẩn (không cần Git LFS):** Cập nhật `.gitignore` để theo dõi tường minh **13 tệp cốt lõi (`36,02 MiB (37,77 MB)`, `37,773,058 bytes`; tệp lớn nhất `MobileUNet_B10_50.pt` = `17,71 MiB (18,57 MB) < 100 MB`)** gồm checkpoint `MobileUNet_B10_50.pt`, 6 ảnh bầu trời thật hiệu chuẩn, 2 manifest hiệu chuẩn (`manifest_real_calibrated.json`, `metadata.yaml`), 2 tệp cấu hình quang học/pipeline (`camera_specs.json`, `pipeline_default.json`) và 2 tệp danh mục sao (`BSC5`, `IAU-CSN.txt`), đồng thời loại trừ tuyệt đối thư mục tạm người dùng (`data/user_uploads/`).
- **Khóa chuẩn LF đa nền tảng (`.gitattributes`):** Cố định kết thúc dòng `eol=lf` cho toàn bộ tệp văn bản hiệu chuẩn/JSON/YAML/catalog trong gói tái lập, giúp cả `python scripts/verify_repro_bundle.py` lẫn `sha256sum -c CHECKSUMS.sha256` đạt **13/13 OK trên cả Linux/macOS (`core.autocrlf=false`) lẫn Windows (`core.autocrlf=true`)**.
- **Runtime SHA-256 Guard trước `torch.load` (`src/centroid_cnn.py`):** Trước khi gọi `torch.load(..., weights_only=False)`, hàm `verify_checkpoint_integrity()` kiểm tra kích thước tối thiểu và đối chiếu mã băm SHA-256 với `CHECKSUMS.sha256` (`e02d7723b832d12c…`). Nếu lệch dù chỉ 1 byte hoặc tệp bị cắt cụt (`< 1 MB`), hệ thống **chặn tuyệt đối `torch.load`** (ném `CHECKPOINT_SHA256_MISMATCH` / `CHECKPOINT_TRUNCATED`), ghi `checkpoint_status` trung thực (`checksum_mismatch` / `corrupted_truncated`) và tự chuyển an toàn sang CoG.
- **Tái lập 1 lệnh, CLI đủ tham số quang học & Lệnh benchmark chuẩn (`scripts/run_clean_repro.py`, `demo_star_tracker.py`):** Hỗ trợ đầy đủ `--focal-mm`, `--pixel-um`, `--k1`, `--k2`, `--sidecar`, `--simulate-cnn-fallback`; lệnh `verify_repro_bundle.py`, `run_clean_repro.py`, `benchmark_3way_centroid_e2e.py --real-only` (mặc định 20 khung clutter) và `benchmark_end_to_end.py --suites real seed42 stress` chạy thông suốt từ bản `git clone` trống.

| Nhóm | Đường dẫn tệp (gốc repo) | Kích thước | SHA-256 (đầu) | Trạng thái |
|---|---|---:|---|---|
| Checkpoint CNN | `third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt` | 17.71 MiB | `e02d7723b832d12cf253…` | **verified** |
| Ảnh trời thật | `data/tetra3/2019-07-29T204726_Alt40_Azi-135_Try1.tiff` | 1.50 MiB | `f5d6c27ac7e8e2114fbe…` | **verified** |
| Ảnh trời thật | `data/tetra3/2019-07-29T204726_Alt60_Azi-135_Try1.tiff` | 1.50 MiB | `f288f6e1fb3a12996269…` | **verified** |
| Ảnh trời thật | `data/real_calibrated/zhao_mt9v022/nightsky_june16_2021.npy` | 2.34 MiB | `57ec7838e430900b438c…` | **verified** |
| Ảnh trời thật | `data/real_calibrated/zhao_mt9v022/verification_img.npy` | 2.34 MiB | `b9a413dc087ccea0d6c6…` | **verified** |
| Ảnh trời thật | `data/uploads/mount_st_helens_1.png` | 1.05 MiB | `f29437dbb96e70cbeda5…` | **verified** |
| Ảnh trời thật | `data/uploads/real_sky/images/0006.png` | 9.12 MiB | `9a699a274af866bd6a79…` | **verified** |
| Hiệu chuẩn / Config | `data/real_calibrated/manifest_real_calibrated.json` | 128.4 KiB | `2e2d0cd1f176f651e15d…` | **verified** |
| Hiệu chuẩn / Config | `data/uploads/real_sky/metadata.yaml` | 3.1 KiB | `5283e3ccd81c5411ed1d…` | **verified** |
| Hiệu chuẩn / Config | `config/camera_specs.json` | 1.5 KiB | `68b60198232c9bc041bb…` | **verified** |
| Hiệu chuẩn / Config | `config/pipeline_default.json` | 1.3 KiB | `8c178d068798f3ea6c3f…` | **verified** |
| Danh mục sao | `data/catalogs/BSC5` | 284.7 KiB | `e471d02eaf4eecb61c12…` | **verified** |
| Danh mục sao | `data/catalogs/IAU-CSN.txt` | 50.3 KiB | `910dd0d14f1c3f08f43f…` | **verified** |

### 2.2. Minh bạch Chế độ Thực thi, 0% Fallback Ngầm & Nhật ký Kiểm toán Cô lập (`src/execution_log.py`, `src/demo_session.py`, `src/telemetry.py`)

- **0% Fallback ngầm trên mọi nhánh (`cnn`, `auto`, `/api/run`, `/api/compare`, `/api/run-upload`, `/api/compare-upload`, CLI):** Mọi phản hồi và bản ghi nhật ký đều ghi rõ `requested_backend`, `executed_backend`, `execution_mode_summary` (như `cnn -> classical [FALLBACK_TO_COG]`, `auto -> classical [FALLBACK_TO_COG]`, `auto -> cnn_hybrid [AUTO_ESCALATED]`, `classical -> classical [DIRECT]`), `fallback_reason` (đã chuẩn hóa đường dẫn tương đối, **không lộ đường dẫn tuyệt đối của hệ điều hành**), `checkpoint_status` trung thực, `checkpoint_sha256` và bật cờ telemetry `FLAG_FALLBACK_USED (0x08)` trong gói 32 byte CRC-16.
- **Kiểm chứng Fallback an toàn 1 chạm:** Tham số `simulate_missing_weights` trên API, cờ `--simulate-cnn-fallback` trên CLI và nút **"Thử nghiệm Fallback CNN → CoG"** trên Web UI định tuyến riêng phiên thử tới `third_party/cnn_star_centroid/saved_models/__simulated_missing_checkpoint__.pt`, kích hoạt ngoại lệ `FileNotFoundError → CoG` thực tế mà không đụng trọng số thật và bật dải cảnh báo màu hổ phách nổi bật trên đầu trang.
- **Nhật ký JSONL nguyên tử & Bảo mật truy xuất (`data/outputs/execution_log.jsonl`, `GET /api/execution-log`):** Ghi nguyên tử qua tệp tạm + `os.replace` kèm cơ chế thử lại chống khóa tệp trên Windows (không bao giờ gây HTTP 500 khi xóa); lọc các sự kiện tải lên và xóa dữ liệu theo mã băm phiên `owner_sid_hash` (không lưu raw cookie `st_sid` ra đĩa, chống lộ tên tệp/sidecar của người dùng khác); đồng thời **chặn tuyệt đối `GET /output/*.jsonl`** và mọi yêu cầu path traversal (`HTTP 404`).

### 2.3. Kiểm soát Dữ liệu Ảnh Người dùng, Chống ghi đè, Anti-IDOR & Quyền xóa (`src/upload_store.py`)

- **Cách ly hoàn toàn & Anti-IDOR (`data/user_uploads/<upload_id>/`):** Thư mục `data/uploads/` chỉ chứa ảnh mẫu đọc-chỉ; mọi tệp tải lên, sidecar JSON và 4 ảnh xem trước (`demo_clean.png`, `demo_input.png`, `demo_output.png`, `demo_result.png`) được cách ly vào thư mục UUID4 16 ký tự hex tạo bằng `mkdir(exist_ok=False)`. Cookie phiên `st_sid` (`HttpOnly`, `SameSite=Lax`, `Secure` trên HTTPS) được cấp tự động ngay cả khi gọi trực tiếp `POST /api/run-upload` không kèm cookie; tệp `meta.json` luôn được ghi ngay lập tức (cả ở `ephemeral` lẫn `ttl`) để khóa quyền sở hữu `owner_sid`, chặn tuyệt đối xem/xóa chéo giữa các phiên (IDOR).
- **Chế độ mặc định `ephemeral` (0s lưu giữ sau phản hồi):** Ảnh xem trước được kết xuất trong thư mục UUID riêng và trả trực tiếp dạng inline `data:image/png;base64,...`, sau đó khối `finally:` **xóa vĩnh viễn 100% ảnh gốc, sidecar, `meta.json` và 4 ảnh xem trước** trước khi trả phản hồi (`verified_gone_on_disk=True`, không chạm `data/outputs/demo_*.png` dùng chung). Khi khởi động server, `_run_startup_sweep()` lập tức dọn mọi thư mục `ephemeral` mồ côi nếu tiến trình từng dừng đột ngột.
- **Chế độ lưu tạm tùy chọn `ttl` (tối đa 15 phút / `900 s`), Rollback lỗi & Quyền xóa tức thì:** Ảnh xem trước phục vụ cách ly qua `GET /api/uploads/<upload_id>/preview/<name>`; luồng nền tự động quét dọn mỗi **`60s`** (`TTL_EXPIRED_AUTO_PURGE`); mọi lỗi HTTP 400/409 tự động xóa hoàn tác (`ERROR_ROLLBACK_DELETE`, 0 tệp mồ côi). Người dùng kiểm tra và xóa tức thì qua giao diện hoặc API (`GET /api/uploads`, `DELETE /api/uploads/<id>`, `DELETE /api/uploads`): sau xóa, URL preview lập tức trả **`404`**, giao diện tự làm trống DOM preview (`#compare3d-img`), thoát ký tự XSS cho tên tệp và ghi dấu `DATA_DELETION` vào `execution_log.jsonl`.
- **Đồng bộ 100% với Hồ sơ dự án:** Đã cập nhật đồng bộ đoạn P184 trong `[StarTracker] - Hồ sơ dự án.docx`, mục 11 trong `AI2026_Ho-so-du-an_StarTracker.{md,docx}`, `README.md`, `REPRODUCIBILITY.md` và công bố trực tiếp ngay tại khung tải ảnh trên Web UI.

---

## 3. Kết quả Kiểm chứng Thực tế (Clean Clone Đa nền tảng, Pytest & Trực tiếp Web UI)

### 3.1. Xác thực Gói Tái lập Đa nền tảng & Chạy từ bản `git clone` sạch

- **Kiểm tra SHA-256 (`CHECKSUMS.sha256`):** **`13/13` tệp hợp lệ (`36,02 MiB (37,77 MB)`)** trên **cả Linux/macOS (`core.autocrlf=false`) lẫn Windows (`core.autocrlf=true`)** bằng cả `python scripts/verify_repro_bundle.py` lẫn `sha256sum -c CHECKSUMS.sha256`; checkpoint `MobileUNet_B10_50.pt` khớp đúng mã băm `e02d7723b832d12cf2535a8a…`.
- **Kết quả chạy thực tế bên trong bản `git clone` sạch (`scripts/run_clean_repro.py` `11.70s`, kiểm chứng tamper 1-byte và `benchmark_3way_centroid_e2e.py --real-only` đủ 20 khung clutter trong `86.46s`):**

| Kịch bản kiểm chứng (Clean Clone) | Chế độ (Yêu cầu → Thực thi) | Trạng thái | Cặp sao hợp lệ | Sai số góc / Ghi chú |
|---|---|---|---|---|
| `seed42_auto` | `auto -> classical` | **SOLVED** | `36 sao` | Δθ = 0.45″ (`93.6 ms`) |
| `esa_alt60_auto` | `auto -> classical` | **SOLVED** | `9 sao` | Δθ = 2.26″ (`72.4 ms`) |
| `zhao_nightsky_auto` | `auto -> cnn_hybrid` | **SOLVED** | `8 sao` | Δθ = 48.26″ (`5486.3 ms`) |
| `mount_st_helens_cnn` | `cnn -> cnn_hybrid` | **SOLVED** | `72 sao` | Δθ = 71.13″ (`619.5 ms`) |
| `fallback_missing_checkpoint` | `cnn -> classical [FALLBACK_TO_COG]` | **SOLVED** | `fallback=True` | `FileNotFoundError → CoG` (đường dẫn tương đối đã lọc) |
| `auto_router_fallback_zhao` | `auto -> classical [FALLBACK_TO_COG]` | **LOST** | `fallback=True` | Auto-Router báo fallback CoG & 0% khóa sai (`INSUFFICIENT_INLIER_PAIRS`) |
| `tampered_1byte_sha256_guard` | `cnn -> classical [FALLBACK_TO_COG]` | **SOLVED** | `36 sao` (`Δθ = 0.45″`) | Chặn `torch.load` (`CHECKPOINT_SHA256_MISMATCH`, `checksum_mismatch`) |
| `upload_isolation_and_delete` | `UUID4 (4250b57c19d148b3, a1cdf81ea56445e7)` | **VERIFIED** | `0 tệp sót` | Chống ghi đè `mount_st_helens_1.png` & xóa sạch đĩa |
| `benchmark_3way --real-only` | `5 pp × (6 real + 20 clutter)` | **PASS** | `0% False Lock` | `86.46s` · Clutter 20 khung: CoG/Auto `2.46″`, tetra3 `2.90″`, CNN-Hybrid `3.17″` (`75 FP` thấp nhất) |

> **Ghi chú đối chiếu Mount St. Helens (CoG danh nghĩa Chặng 1 vs hiệu chuẩn góc rộng):** Ở cấu hình quang học danh nghĩa Chặng 1 (không méo `k1/k2`), CoG trên `mount_st_helens_1.png` trả về `LOST [INSUFFICIENT_INLIER_PAIRS]` (1 inlier) nhằm minh chứng chốt chặn an toàn; khi dùng quang học hiệu chuẩn góc rộng (`f, cx, cy, k1, k2`) cùng bộ đối sánh wide-FOV nâng cấp, CoG giải đúng `SOLVED (83/106, Δθ = 49,51″)` trong khi `tetra3` trả `LOST` và `CNN-Hybrid` giải `72/77 (71,13″)`.

### 3.2. Kết quả Kiểm thử Tự động (`pytest`) & Kiểm chứng Trực tiếp Giao diện Web

- **Kiểm thử tự động toàn dự án (`pytest -q`):** **`151 passed, 1 skipped in 80.62s (0:01:20)`** (0 lỗi), bao gồm **17 ca kiểm thử chuyên biệt Chặng 2** trong `tests/test_stage2_repro_and_privacy.py` phủ trọn: SHA-256 13/13; chặn checkpoint sửa 1 byte (`CHECKPOINT_SHA256_MISMATCH`) và checkpoint cụt `<1 MB` (`corrupted_truncated`) trước `torch.load` trên cả `/api/run` lẫn `/api/compare` nhánh `auto`; `simulate_missing_weights=True` → `FALLBACK_TO_COG` không lộ đường dẫn OS; `ephemeral` preview inline base64 + không ghi đè `mount_st_helens_1.png`; tải 2 ảnh trùng tên `ttl` sinh 2 UUID riêng + preview `200 → 404` sau `DELETE` + `TTL_EXPIRED_AUTO_PURGE`; quét dọn `ephemeral` mồ côi lúc khởi động (`_run_startup_sweep`); rollback 0 tệp mồ côi khi lỗi 400 ở cả `ephemeral` & `ttl`; chống IDOR cả khi gọi API không cookie (`st_sid` + luôn ghi `meta.json`); cô lập `/api/execution-log` theo `owner_sid_hash` & chặn `GET /output/*.jsonl` (`404`); retry `os.replace` chống khóa tệp Windows; CLI `--focal-mm/--pixel-um/--k1` trên `Alt60`; và 0 byte NUL UTF-8.
- **Kiểm chứng trực tiếp trên trình duyệt Chromium (đồng bộ bản 24/7 tại `https://startracker.agentlens.dpdns.org`):** `0` lỗi console/`pageerror`, thanh trạng thái chân trang hiển thị gọn `< 178.8″` và `ĐH Đà Nẵng` không bị cắt; xác nhận thực tế phiên `ephemeral` (`51e66d6603744123` → `EPHEMERAL_AUTO_DELETE`, 6 tệp), 2 phiên `ttl` trùng tên (`e52cbdbd8d734c9d` & `544f376c3bd74dce` → xóa đơn `USER_DELETE_SINGLE` preview `404` trong khi phiên 2 còn `200`, xóa toàn bộ `USER_DELETE_ALL` preview `404`, `0` tệp sót trên đĩa, xóa sạch DOM preview) và kiểm thử trình duyệt B cô lập (`0` ảnh, preview/DELETE/`/output/execution_log.jsonl` đều `404`, `0` bản ghi rò rỉ).

### 3.3. Hình ảnh Minh chứng Trực tiếp trên Web UI

![Hình 1. Sơ đồ kiến trúc tổng thể Pipeline định hướng sao J2000 & Tầng kiểm soát dữ liệu ảnh Chặng 2 (Gói tái lập 13/13 SHA-256 36,02 MiB (37,77 MB) + .gitattributes LF, Runtime Guard trước torch.load, Auto-Router + Fallback CoG 0% fallback ngầm, Cô lập UUID4 / st_sid / Ephemeral / TTL 15 phút + quét khởi động & nền 60s, Rollback lỗi 400/409 và Nhật ký JSONL nguyên tử).](stage2_evidence/stage2_pipeline_architecture.png)

*Hình 1. Sơ đồ kiến trúc tổng thể Pipeline định hướng sao J2000 & Tầng kiểm soát dữ liệu ảnh Chặng 2 (Gói tái lập 13/13 SHA-256 36,02 MiB (37,77 MB) + .gitattributes LF, Runtime Guard trước torch.load, Auto-Router + Fallback CoG 0% fallback ngầm, Cô lập UUID4 / st_sid / Ephemeral / TTL 15 phút + quét khởi động & nền 60s, Rollback lỗi 400/409 và Nhật ký JSONL nguyên tử).*

![Hình 2. Giao diện Web UI kiểm chứng trực tiếp — Tab Cấu hình, Checksum & Dữ liệu xác thực đủ 13/13 tệp SHA-256 (36,02 MiB (37,77 MB), checkpoint verified) đồng thời hiển thị rõ 3 bản ghi nhật ký thực thi thời gian thực (AUTO_ESCALATED trên Zhao nightsky, DIRECT trên Mount St. Helens và ESA Alt60).](stage2_evidence/ev1_repro_checksums_and_audit_log.png)

*Hình 2. Giao diện Web UI kiểm chứng trực tiếp — Tab Cấu hình, Checksum & Dữ liệu xác thực đủ 13/13 tệp SHA-256 (36,02 MiB (37,77 MB), checkpoint verified) đồng thời hiển thị rõ 3 bản ghi nhật ký thực thi thời gian thực (AUTO_ESCALATED trên Zhao nightsky, DIRECT trên Mount St. Helens và ESA Alt60).*

![Hình 3. Minh chứng báo rõ Fallback CNN → CoG (0% fallback ngầm): kích hoạt "Thử nghiệm Fallback CNN → CoG" bật dải cảnh báo màu cam nổi bật trên đầu trang kèm đường dẫn tương đối đã lọc (không lộ đường dẫn OS), ghi nhận cả cnn -> classical [FALLBACK_TO_COG] (Seed 42 SOLVED 0,446″) và auto -> classical [FALLBACK_TO_COG] (Zhao nightsky LOST) vào execution_log.jsonl.](stage2_evidence/ev2_fallback_cog_banner.png)

*Hình 3. Minh chứng báo rõ Fallback CNN → CoG (0% fallback ngầm): kích hoạt "Thử nghiệm Fallback CNN → CoG" bật dải cảnh báo màu cam nổi bật trên đầu trang kèm đường dẫn tương đối đã lọc (không lộ đường dẫn OS), ghi nhận cả cnn -> classical [FALLBACK_TO_COG] (Seed 42 SOLVED 0,446″) và auto -> classical [FALLBACK_TO_COG] (Zhao nightsky LOST) vào execution_log.jsonl.*

![Hình 4. Minh chứng chống ghi đè & lưu tạm TTL 15 phút (cô lập theo phiên st_sid): hai lượt tải liên tiếp cùng ảnh thật mount_st_helens_1.png (1,05 MiB) + sidecar mount_st_helens_1.json được cách ly vào hai thư mục UUID4 độc lập (data/user_uploads/e52cbdbd8d734c9d/ và data/user_uploads/544f376c3bd74dce/) kèm đếm ngược TTL và nút Xóa ngay / Xóa tất cả.](stage2_evidence/ev3_upload_ttl_and_zero_overwrite.png)

*Hình 4. Minh chứng chống ghi đè & lưu tạm TTL 15 phút (cô lập theo phiên st_sid): hai lượt tải liên tiếp cùng ảnh thật mount_st_helens_1.png (1,05 MiB) + sidecar mount_st_helens_1.json được cách ly vào hai thư mục UUID4 độc lập (data/user_uploads/e52cbdbd8d734c9d/ và data/user_uploads/544f376c3bd74dce/) kèm đếm ngược TTL và nút Xóa ngay / Xóa tất cả.*

![Hình 5. Minh chứng quyền xóa dữ liệu tức thì & tự xóa ephemeral: sau khi bấm Xóa ngay (USER_DELETE_SINGLE cho phiên e52cbdbd8d734c9d, 7 tệp) và Xóa toàn bộ (USER_DELETE_ALL cho phiên 544f376c3bd74dce, 7 tệp) cùng phiên ephemeral trước đó (EPHEMERAL_AUTO_DELETE cho Alt60 phiên 51e66d6603744123, 6 tệp), thư mục data/user_uploads/ xác minh trống hoàn toàn (0 ảnh tạm trên đĩa, chân trang hiển thị gọn Δθ 49.506″ < 178.8″).](stage2_evidence/ev4_delete_verified_empty.png)

*Hình 5. Minh chứng quyền xóa dữ liệu tức thì & tự xóa ephemeral: sau khi bấm Xóa ngay (USER_DELETE_SINGLE cho phiên e52cbdbd8d734c9d, 7 tệp) và Xóa toàn bộ (USER_DELETE_ALL cho phiên 544f376c3bd74dce, 7 tệp) cùng phiên ephemeral trước đó (EPHEMERAL_AUTO_DELETE cho Alt60 phiên 51e66d6603744123, 6 tệp), thư mục data/user_uploads/ xác minh trống hoàn toàn (0 ảnh tạm trên đĩa, chân trang hiển thị gọn Δθ 49.506″ < 178.8″).*

---

## 4. Danh mục Tệp Cải tiến Chặng 2 & Liên kết Nộp bài

- **Liên kết mã nguồn (GitHub):** https://github.com/hoangtranduchai/star-tracker (nhánh `main`, tag `v1.2.0-stage2`)
- **Liên kết sản phẩm chạy thử 24/7:** https://startracker.agentlens.dpdns.org
- **Liên kết báo cáo cải tiến PDF:** https://github.com/hoangtranduchai/star-tracker/blob/main/AI2026_Portfolio/BAO_CAO_CAI_TIEN_VONG_CHUNG_KET_CHANG_2.pdf
- **Liên kết minh chứng cải tiến (đầy đủ log clean-clone đa nền tảng, tamper guard, JSONL & ảnh chụp):** https://github.com/hoangtranduchai/star-tracker/blob/main/AI2026_Portfolio/MINH_CHUNG_CAI_TIEN_CHANG_2.md
- **Hướng dẫn tái lập từ bản clone sạch:** [`REPRODUCIBILITY.md`](../REPRODUCIBILITY.md) (https://github.com/hoangtranduchai/star-tracker/blob/main/REPRODUCIBILITY.md)
- **Bảng mã băm toàn vẹn SHA-256:** [`CHECKSUMS.sha256`](../CHECKSUMS.sha256) (https://github.com/hoangtranduchai/star-tracker/blob/main/CHECKSUMS.sha256)
- **Mô-đun mã nguồn & cấu hình mới / cập nhật:** `.gitattributes`, `.gitignore`, `CHECKSUMS.sha256`, `REPRODUCIBILITY.md`, `src/repro_bundle.py`, `src/centroid_cnn.py`, `src/upload_store.py`, `src/execution_log.py`, `src/demo_session.py`, `src/telemetry.py`, `app.py`, `demo_star_tracker.py`, `scripts/verify_repro_bundle.py`, `scripts/run_clean_repro.py`, `scripts/benchmark_3way_centroid_e2e.py`, `web/templates/index.html`, `web/static/app.js`, `web/static/app.css`, `tests/test_stage2_repro_and_privacy.py`.

---

## 5. Phạm vi Trung thực & Khai báo Sử dụng AI

- **Phạm vi kỹ thuật:** Đây là sản phẩm phần mềm nghiên cứu & mô phỏng định hướng sao trên PC / ARM64 (NASA TRL 3–4), không tuyên bố đạt chuẩn kiểm định bay vũ trụ (phần cứng chịu bức xạ / vòng điều khiển ADCS thực).
- **Khai báo sử dụng AI:** Trong Chặng 2, đội sử dụng công cụ AI (Google Antigravity / Gemini) hỗ trợ viết mã các mô-đun kiểm chứng SHA-256, Runtime Guard trước `torch.load`, quản lý tệp tạm UUID4/TTL/`st_sid`, nhật ký JSONL nguyên tử, nâng cấp giao diện Web và tổng hợp báo cáo. Đội thi chịu trách nhiệm định hướng thiết kế, chạy kiểm thử thực tế trên bản `git clone` sạch đa nền tảng và kiểm tra trực tiếp trên môi trường triển khai 24/7.
