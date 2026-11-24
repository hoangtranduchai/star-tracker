# Kịch bản thuyết trình miệng — Star Tracker (laptop demo)

**Đơn vị:** Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin  
**Đội (theo hồ sơ):** Hoàng Trần Đức Hải · Nguyễn Tiến · Mai Tạ Trúc Vy  
**File này:** lời nói + hỏi đáp. Không phải slide. Slide: `AI2026_SLIDE_THUYET_TRINH.pptx`.

---

## 1. Cách dùng file

| Hạng mục | Gợi ý |
|---|---|
| Thời lượng nói | **8–9 phút** (không tính hỏi đáp · 19 slide mở rộng Vòng Chung kết · Chặng 1) |
| Công cụ | Laptop + trình duyệt `http://127.0.0.1:8765/` (chạy `python app.py` trước) |
| Demo sạch (Seed) | **⚡ FAST MODE**, Yale BSC5 (V ≤ 6), Wahba **SVD**, kính demo 50 mm · 3,72 µm, Seed **42** — preset tự gắn **CoG** |
| Demo sáng tạo & Ảnh thật | Nút **🏔 Ảnh núi thật** (tự gắn **CNN** + 4,2 mm · 4,1 µm) & **🌌 Ảnh trời thật (ESA tetra3)** (16-bit Alt60, 35,291 mm · 6,9 µm) → đọc số trên màn |
| Quy tắc lai | Ảnh giả lập / Sao chuẩn / ESA `tetra3` → CoG; CNN demo cho ảnh núi thật (núi/cây 1 vs CoG 25). Không claim CNN thắng mọi khung. |
| Số liệu kết quả live | Chỉ đọc số **đang hiện trên màn hình** (`SOLVED` / `LOST`, `reject_code`, số cặp inlier, dư góc). Không đọc số nhớ cũ. |
| Số liệu hồ sơ (kiểm toán Chặng 1) | `thr2` (27.017 sao GT): CoG RMSE **0,1804** px (`25.206/27.017`, Recall **93,3%**, Precision **100,0%**, `0` FP, ~**34,2** ms) vs CNN **0,4745** px (`25.050/27.017`, Recall **92,7%**, Precision **75,4%** [`8.191` FP], ~**60,2** ms). **E2E 500 khung `hd1024`**: CoG **500/500 <40″** (`Δθ` tv **2,00″**, **87,2** ms) vs CNN **498/500 <40″** (`Δθ` tv **7,94″**, **123,9** ms, `0% False Lock`). **Seed 42 FAST** (`seed42_cog_vs_cnn.json`): CoG **0,446″** (`36/36`, Prec/Rec 100%) vs CNN **1,648″** (`30/36`, Prec **85,7%**, Rec **83,3%**). **Stress 100 ca**: **0/100 (0,0% False Lock)** vs **41/100 (41,0%)** ở mã cũ. **Núi St. Helens**: CoG `111` (độc lập `bg=31`) vs `106` (pipeline `mask+bg=32→33`), hậu kiểm bị chặn an toàn **`LOST [INSUFFICIENT_INLIER_PAIRS]`** (1 inlier); CNN giải **`SOLVED` `54/79`**, RA **310,48°** Dec **+36,00°** (**Δ `0,034°`** vs UW LOST, **`~2,76 s`**). |
| Tên người | Chỉ dùng tên đã có trong hồ sơ. Không bịa thêm. |

**Nhịp thời gian gợi ý (tổng ~7–8 phút):**

| Phần | Thời lượng |
|---|---|
| Mở đầu | ~40–50 s |
| Bài toán + camera | ~70–80 s |
| Pipeline 3 bước + CNN tùy chọn | ~80–90 s |
| Demo live Seed 42 (CoG) | ~60–75 s |
| Demo Ảnh núi thật (CoG rồi CNN) | ~90–110 s |
| Số đo hồ sơ + Zhao (ngắn) | ~40–50 s |
| Quaternion 16 byte + giới hạn + kết | ~50–60 s |

---

## 2. Kịch bản nói từng phần

### 2.1. Mở đầu (~40–50 giây)

**Trên màn:** Toàn trang web, tiêu đề Star Tracker laptop demo.

**Lời thoại:**

« Thưa quý thầy cô và ban giám khảo. Em xin trình bày demo phần mềm Star Tracker trên laptop, Trường Đại học Bách khoa, Đại học Đà Nẵng, Khoa Công nghệ thông tin.

Mục tiêu: từ ảnh bầu trời sao tính hướng trục máy ảnh dưới dạng quaternion J2000 — mười sáu byte. Đường ống: centroid → Pyramid với K-vector → Wahba. Ảnh giả lập dùng centroid cổ điển; CNN chỉ để demo ảnh núi thật vì ở đó nó gần như không chấm địa hình (1 vs CoG 25) và nhanh hơn — không huấn luyện lại. »

### 2.2. Bài toán + camera (~70–80 giây)

**Trên màn:** Tab **Camera demo** rồi quay lại tab ảnh.

**Lời thoại:**

« Bài toán lost-in-space: không biết đang nhìn hướng nào. Đầu ra không phải ảnh thô mà là quaternion. Star tracker giải hướng bằng hình học góc giữa các sao — không dùng GSD mét mặt đất.

Camera demo: máy ảnh tĩnh APS-C khoảng hai mươi bốn megapixel, khung sáu nghìn nhân bốn nghìn, pixel ba phẩy bảy hai micrômet, tiêu cự năm mươi milimet. Để demo mượt em dùng FAST — một nghìn năm trăm nhân một nghìn. Bộ đo centroid trong hồ sơ là năm trăm khung một nghìn không hai bốn nhân sáu trăm tám mươi ba trên RTX 5070. »

### 2.3. Pipeline + CNN tùy chọn (~80–90 giây)

**Trên màn:** Chỉ mục **01 · Chế độ centroid** — hai nút CoG / CNN.

**Lời thoại:**

« Bước một — centroid: trọng tâm cường độ, gọi là CoG. Trên giao diện còn nút CNN với cổng «chỉ sao từ cấp sáu trở lên sáng» — MobileUNet công khai, Zhao và cộng sự, arXiv hai bốn không bốn chấm một chín một không tám; em không huấn luyện lại. Preset web: sim và Sao chuẩn gắn CoG; nút Ảnh núi thật gắn CNN. Trên một khung sim đã thử, cổng sáng này không làm CNN thắng CoG — em không overclaim.

Bước hai — Pyramid của Mortari cộng K-vector trên Yale BSC5, cấp sáng nhỏ hơn hoặc bằng sáu.

Bước ba — Wahba, SVD hoặc QUEST, ra quaternion. »

### 2.4. Demo live Seed 42 — CoG (~60–75 giây)

**Chuẩn bị:** FAST · BSC5 · SVD · Kính demo · Seed 42 · **Centroid cổ điển**.

**Lời thoại:**

« Em chọn FAST, Seed bốn mươi hai, centroid cổ điển — để thấy trên ảnh sạch CoG thường chính xác hơn. Em bấm SINH ẢNH và GIẢI TƯ THẾ. »

*(Bấm 🚀 SINH ẢNH & GIẢI TƯ THẾ. Đọc số trên màn.)*

« Sai số góc trên màn là … . Độ trễ … . Số sao định danh … trên … . Em chỉ đọc số vừa hiện. Trên bộ năm trăm khung sạch trong hồ sơ, ở bước centroid CoG đạt RMSE không phẩy một tám không bốn pixel với Precision một trăm phần trăm, Recall chín mươi ba phẩy ba phần trăm và không đốm giả; CNN đạt không phẩy bốn bảy bốn năm pixel với Precision bảy mươi lăm phẩy bốn phần trăm và tám nghìn một trăm chín mươi mốt đốm giả. Khi chạy End-to-End 3-DOF trên RTX 5070, CoG giải đúng năm trăm trên năm trăm khung dưới bốn mươi giây cung với trung vị hai phẩy không không giây cung và tám mươi bảy phẩy hai mili giây; CNN đạt bốn trăm chín mươi tám trên năm trăm khung với trung vị bảy phẩy chín bốn giây cung, và cả hai đều không phần trăm khóa sai. »

### 2.5. Demo Ảnh núi thật & Ảnh trời thật hiệu chuẩn (~90–110 giây)

**Việc:**

1. Bấm **🏔 Ảnh núi thật** (preset tự gắn CNN + 4,2 mm · 4,1 µm) → đọc `SOLVED`, `54/79` sao, RA/Dec, `Δ 0,034°`.
2. Đổi radio sang **Centroid cổ điển** → chạy lại → chỉ rõ hệ thống tự động từ chối **`LOST [INSUFFICIENT_INLIER_PAIRS]`** kèm **16 byte `0x00`** (không trả tư thế giả từ tạp núi).
3. (Nếu có thời gian) Bấm **🌌 Ảnh trời thật (ESA tetra3)** để minh họa giải ảnh sao thật 16-bit (`2,26″` CoG / `4,65″` CNN).

**Lời thoại:**

« Đây là điểm sáng tạo và cũng là minh chứng cho chốt chặn an toàn Chặng 1. Em bấm Ảnh núi thật — ảnh công bố kèm bộ LOST của Đại học Washington, Mount St. Helens, khung một nghìn không hai bốn vuông, tiêu cự bốn phẩy hai milimet, pixel bốn phẩy một micrômet — không phải ảnh nhóm tự chụp. Trên ảnh này CNN chỉ đánh một điểm trên núi nên giải đúng năm mươi bốn trên bảy mươi chín cặp, lệch mốc UW LOST không phẩy không ba bốn độ trong khoảng hai phẩy bảy sáu giây.

Khi em chuyển sang CoG cổ điển, vì tách hàng chục điểm giả trên địa hình cộng méo góc rộng, chốt chặn hậu kiểm sau cải tiến chỉ giữ được một cặp inlier hợp lệ — dưới ngưỡng ba cặp — nên hệ thống chủ động trả về LOST với mã INSUFFICIENT_INLIER_PAIRS và gói mười sáu byte không, không phần trăm khóa sai.

### 2.6. Cải tiến Chặng 1 & Đối chiếu Zhao (~60 giây)

**Trên slide 12–15 (`AI2026_SLIDE_THUYET_TRINH.pptx`).**

**Lời thoại:**

« Ở Chặng 1 Vòng Chung kết, nhóm hoàn thiện ba cải tiến lớn. Thứ nhất, sửa triệt để lỗi thoát vòng lặp break cũ và kiểm tra suy biến thẳng hàng SVD, giảm tỷ lệ khóa sai False Lock trên một trăm ca đối kháng từ bốn mươi mốt phần trăm xuống không phần trăm. Thứ hai, đánh giá End-to-End 3-DOF đầy đủ trên năm trăm bốn mươi khung mô phỏng cùng sáu khung ảnh thật có hiệu chuẩn của ESA tetra3, Zhao và LOST — đạt không phần trăm khóa sai trên mọi tập thử nghiệm.

Thêm bộ lóa mạnh bốn mươi khung: CoG giải đúng bốn mươi trên bốn mươi khung với trung vị một phẩy chín chín giây cung, CNN đạt ba mươi chín trên bốn mươi khung với mười phẩy năm chín giây cung. Riêng số khoảng hai mươi mili giây trên RTX 2060M và hai trăm sáu mươi sáu mili giây trên Coral TPU là số của bài báo Zhao và cộng sự, tách bạch hoàn toàn khỏi số đo RTX 5070 của nhóm. »

### 2.7. Quaternion + Đối soát & Phạm vi PC Demo + Kết (~50–60 giây)

**Trên màn:** Tab **📐 Đối Chiếu Tư Thế & Downlink** và Slide 15–17.

**Lời thoại:**

« Đầu ra đóng gói bốn float ba mươi hai bit — mười sáu byte theo quy ước J2000 trên phần mềm demo PC, và tự động xuất mười sáu byte không khi LOST.

Cuối cùng, nhóm đã đối soát toàn bộ hai mươi mốt sai lệch giữa nhật ký JSON, tài liệu và slide — xóa hoàn toàn số cũ chưa kiểm chứng và khẳng định rõ đây là phần mềm demo nghiên cứu chạy trên laptop RTX 5070 / CPU, chưa kiểm chứng trên phần cứng vệ tinh, bức xạ hay bus ADCS thực tế.

Em xin cảm ơn quý thầy cô. Em sẵn sàng trả lời câu hỏi. »

---

## 3. Câu hỏi nhanh (rút gọn — chi tiết ở `CAU_HOI_BGK.md`)

1. Lost-in-space? → Không có tư thế ban đầu; từ ảnh sao ra quaternion 16 byte (hoặc `0x00` khi `LOST`).
2. Vì sao CoG thắng sim sạch? → `thr2`: CoG `0,1804` px (`Prec 100%`, `Rec 93,3%`, `0 FP`) vs CNN `0,4745` px (`Prec 75,4%`, `8.191 FP`); E2E `hd1024`: CoG `2,00″` vs CNN `7,94″`.
3. Ảnh núi LOST + `111 vs 106`? → Độc lập `bg=31` tách `111` (`25` núi), pipeline `GlareMasker+bg=33` tách `106`; hậu kiểm CoG trả **`LOST [INSUFFICIENT_INLIER_PAIRS]`** an toàn, CNN giải **`SOLVED 54/79`** (`Δ 0,034°`, `~2,76 s`).
4. Chốt chặn False Lock Chặng 1? → Sửa lỗi `break` + lọc lặp trước/sau `_associate_remaining` + SVD `s_min >= 1e-6` → `0/100 (0,0%)` vs `41/100 (41,0%)` ở mã cũ.
5. Ảnh thật hiệu chuẩn & phạm vi PC? → CoG `Alt60` `2,26″`, CNN `Alt60` `4,65″` / `Zhao` `54,70″` / `MSH` `0,034°`; `Alt40 Hip V≤7` đạt `39,51″` / `26,60″`. Chưa kiểm chứng phần cứng vệ tinh bay / ADCS.
6. Seed 42 FAST? → `seed42_cog_vs_cnn.json`: CoG `0,446″` (`36/36`) vs CNN `1,648″` (`30/36`).
7. Đối soát Log–Slide? → Sửa Slide 7, 8, 10, 17; xóa số mồ côi cũ không có log đối chiếu; đồng bộ MD/DOCX/PDF.
8. CNN-Hybrid vs `tetra3` & Auto-Router? → `CNN-Hybrid` cắt `-99,8% FP` (`1.118 → 2 FP`), vượt `tetra3` trên 500 sạch (`2,02″` vs `2,34″`), 40 lóa (`2,73″/69,9%` vs `5,06″/51,3%`), 30 sao giả (`100%` vs `70%`) và giải cả 2 ảnh thật mà `tetra3` `LOST` (`Zhao 48,3″` & `MSH 71,1″`). Chế độ mặc định **`Tự động (Auto: CoG → CNN)`** kết hợp tốc độ `CoG` (`85,8 ms`, `100%` tới `ω=1,5°/s`) với độ bền `CNN-Hybrid` → giải **4/4 ảnh trời thật**, **0% False Lock trên 3.430 lượt kiểm thử**.

---

## 4. Năm câu không được nói

1. Chỉ trình bày đúng cấu hình camera demo trên PC (APS-C 50 mm) và dữ liệu thật công khai (`ESA tetra3`, `Zhao MT9V022`, `UW LOST MSH`, `NTNU 0006.png`).
2. Không gán GSD mét mặt đất cho star tracker; **không** claim sẵn sàng vệ tinh bay, bức xạ hay giao tiếp ADCS.
3. Không nói «CNN luôn tốt hơn» — trên 500 khung sạch và 40 lóa, CoG vẫn nhanh & chính xác hơn một chút, và ở `ω ≥ 1,5 °/s` CNN giảm tỷ lệ giải do PSF tròn; đó là lý do chọn kiến trúc lai `Auto (CoG → CNN-Hybrid)`.
4. Không gọi ảnh núi là «ảnh nhóm chụp» — là mẫu công bố kèm LOST.
5. Không đọc lại số cũ chưa đối soát hay số ngoài JSON; chỉ đọc số trên màn hình hoặc trong `log_reconciliation_audit.json`, `benchmark_3way_comparison.json`, `benchmark_stress_curves.json`.

---

## 5. Checklist sân khấu

```text
□ python app.py → http://127.0.0.1:8765/ (hoặc https://startracker.agentlens.dpdns.org)
□ Chế độ mặc định: Tự động (Auto: CoG → CNN-Hybrid) + Mẫu chuẩn Seed 42 → đọc KPI (0,446″)
□ Tab So sánh CoG / tetra3 ↔ CNN → bấm 1 chạm "Ảnh đêm Zhao (8-bit)" (~1,3s): CoG LOST · tetra3 LOST · CNN-Hybrid SOLVED 48,26″
□ 🏔 Ảnh núi thật Mount St. Helens → CNN-Hybrid SOLVED (72/77, 71,13″, 2 FP) vs tetra3 LOST (57 FP)
□ 🌌 Ảnh trời thật (ESA tetra3 Alt60) → giải ảnh 16-bit thực tế (2,26″)
□ Tab Đối chiếu tư thế & Downlink 16 byte + nêu rõ phạm vi Demo PC/VPS (chưa kiểm chứng bay)
□ Slide: AI2026_Portfolio/AI2026_SLIDE_THUYET_TRINH.pptx (19 slide đã đối soát, có Hình 10, 11 & 12 — Kiểm toán CubeSat ARM64/SAA/SEU)
```
