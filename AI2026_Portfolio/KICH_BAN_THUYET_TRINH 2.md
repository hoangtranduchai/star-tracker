# Kịch bản thuyết trình miệng — Star Tracker (laptop demo)

**Đơn vị:** Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin  
**Đội (theo hồ sơ):** Hoàng Trần Đức Hải · Nguyễn Tiến · Mai Tạ Trúc Vy  
**File này:** lời nói + hỏi đáp. Không phải slide. Slide: `AI2026_SLIDE_THUYET_TRINH.pptx`.

---

## 1. Cách dùng file

| Hạng mục | Gợi ý |
|---|---|
| Thời lượng nói | **8–9 phút** (không tính hỏi đáp · 19 slide Vòng Chung kết · Chặng 1) |
| Công cụ | Laptop + trình duyệt `http://127.0.0.1:8765/` (chạy `python app.py` trước) |
| Demo sạch (Seed) | **⚡ FAST MODE**, Yale BSC5 (V ≤ 6), Wahba **SVD**, kính demo 50 mm · 3,72 µm, Seed **42** — preset tự gắn **CoG** |
| Demo sáng tạo & Ảnh thật | Nút **🏔 Ảnh núi thật** (tự gắn **CNN** + 4,2 mm · 4,1 µm) & **🌌 Ảnh trời thật (ESA tetra3)** → đọc số trên màn |
| Quy tắc lai | Ảnh giả lập, Seed 42 và ảnh trời thật `tetra3` dùng CoG. Nút Ảnh núi thật dùng CNN. |
| Số liệu kết quả live | Chỉ đọc số **đang hiện trên màn hình** (`SOLVED`/`LOST`, `reject_code`, số inlier). |
| Số liệu hồ sơ (đã kiểm toán) | 500 khung sạch (`thr2`): CoG RMSE **0,1804** px (**Recall 93,3% · Precision 100,0% · 0 FP**, ~**34,2** ms); CNN **0,4745** px (**Rec 92,7% · Prec 75,4% · 8.191 FP**, ~**60,2** ms). **E2E 500 khung `hd1024`**: CoG **500/500 <40″** (`Δθ` tv **2,00″**, **87,2** ms) vs CNN **498/500 <40″** (`Δθ` tv **7,94″**, **123,9** ms). **Seed 42 FAST**: CoG **0,446″** (`36/36`) vs CNN **1,648″** (`30/36`). **Stress 100 ca**: **0/100 (0% False Lock)** vs **41/100 (41%)** cũ. **Núi St. Helens**: CoG `111` (`bg=31`) vs `106` (pipeline `mask+bg=33`), hậu kiểm **`LOST [INSUFFICIENT_INLIER_PAIRS]`** (1 inlier); CNN **`SOLVED` `54/79`**, RA **310,48°**, Dec **+36,00°**, **Δ `0,034°`** vs LOST (**`~2,76 s`**). |
**Nhịp thời gian gợi ý (tổng ~8–9 phút):**

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

**Trang «Nội dung thuyết trình»:**

« Em đi theo trình tự bộ mười bảy slide. Trước hết là bài toán và đường ống lai CoG hoặc CNN ra quaternion mười sáu byte. Tiếp theo là số đo trên năm trăm khung sạch, bốn mươi khung lóa và ảnh núi thật. Sau đó là phần trích dẫn riêng bài báo Zhao. Cuối cùng là ba cải tiến Vòng Chung kết Chặng một: chốt chặn không phần trăm khóa sai, đánh giá End-to-End năm trăm bốn mươi khung mô phỏng cùng ảnh trời thật hiệu chuẩn, và đối soát minh bạch phạm vi demo PC. »

**Trên màn sau đó:** Toàn trang web, tiêu đề Star Tracker laptop demo.

**Lời thoại:**

« Thưa quý thầy cô và ban giám khảo. Em xin trình bày demo phần mềm Star Tracker trên laptop, Trường Đại học Bách khoa, Đại học Đà Nẵng, Khoa Công nghệ thông tin.

Mục tiêu: từ ảnh bầu trời sao tính hướng trục máy ảnh, ra quaternion J2000 dài mười sáu byte. Đường ống gồm tìm tâm sao, nhận dạng Pyramid với bảng K-vector, rồi giải Wahba. Ảnh giả lập dùng tâm cổ điển. Trên ảnh núi, mạng công khai gần như không đánh dấu địa hình: một điểm so với hai mươi lăm điểm của tâm cổ điển. Nhóm không huấn luyện lại mạng. »

### 2.2. Bài toán + camera (~70–80 giây)

**Trên màn:** Tab **Camera demo** rồi quay lại tab ảnh.

**Lời thoại:**

« Bài toán lost-in-space: không biết đang nhìn hướng nào. Đầu ra là quaternion, không phải ảnh thô. Hướng được giải bằng góc giữa các sao.

Kính demo khoảng hai mươi bốn megapixel, sáu nghìn nhân bốn nghìn, pixel ba phẩy bảy hai micrômet, tiêu cự năm mươi milimet, trường nhìn khoảng hai mươi lăm độ nhân mười bảy độ. Lúc đo năm trăm khung, cạnh dài được thu về một nghìn không trăm hai mươi bốn. Máy đo là RTX 5070 Laptop. »

### 2.3. Pipeline + CNN tùy chọn (~80–90 giây)

**Trên màn:** Chỉ mục **01 · Chế độ centroid** — hai nút CoG / CNN.

**Lời thoại:**

« Bước một là tìm tâm sao. Mặc định là trọng tâm cường độ. Nhánh kia là MobileUNet công khai của Zhao và cộng sự, arXiv 2404.19108, ngưỡng hai phẩy không. Nhóm không huấn luyện lại. Ảnh giả lập gắn tâm cổ điển. Nút Ảnh núi thật gắn mạng.

Bước hai là Pyramid của Mortari và bảng K-vector trên Yale BSC5, cấp sáng đến sáu, năm nghìn không trăm hai mươi ba sao.

Bước ba là Wahba, SVD hoặc QUEST, ra quaternion. »

### 2.4. Demo live Seed 42 — CoG (~60–75 giây)

**Chuẩn bị:** FAST · BSC5 · SVD · Kính demo · Seed 42 · **Centroid cổ điển**.

**Lời thoại:**

« Em chọn FAST, Seed bốn mươi hai, centroid cổ điển — để thấy trên ảnh sạch CoG thường chính xác hơn. Em bấm SINH ẢNH và GIẢI TƯ THẾ. »

*(Bấm 🚀 SINH ẢNH & GIẢI TƯ THẾ. Đọc số trên màn.)*

« Sai số góc trên màn là … . Độ trễ … . Số sao định danh … trên … . Em chỉ đọc số vừa hiện. Trên năm trăm khung sạch, tâm cổ điển đạt RMSE không phẩy một tám không bốn pixel với Precision một trăm phần trăm và không đốm giả; mạng đạt không phẩy bốn bảy bốn năm pixel với Precision bảy mươi lăm phẩy bốn phần trăm. Khi chạy End-to-End ba bậc tự do, tâm cổ điển giải đúng cả năm trăm khung dưới bốn mươi giây cung, trung vị hai phẩy không không giây cung; khung seed bốn mươi hai đạt không phẩy bốn bốn sáu giây cung so với một phẩy sáu bốn tám giây cung của mạng. »

### 2.5. Demo Ảnh núi thật & Ảnh trời thật (~90–110 giây)

**Việc:**

1. Bấm **🏔 Ảnh núi thật** (preset tự gắn CNN + 4,2 mm · 4,1 µm) → đọc `SOLVED`, `54/79` sao, `0,034°`.
2. Đổi radio sang **Centroid cổ điển** → chạy lại → thấy badge **`LOST [INSUFFICIENT_INLIER_PAIRS]`** và gói 16 byte `0x00`.
3. Bấm **🌌 Ảnh trời thật (ESA tetra3)** (16-bit Alt60) để minh họa ảnh sao thật hiệu chuẩn.

**Lời thoại:**

« Đây là điểm sáng tạo. Em bấm Ảnh núi thật. Ảnh này công bố kèm phần mềm LOST của Đại học Washington, núi St. Helens, không phải ảnh nhóm em chụp. Khung một nghìn không hai mươi bốn vuông, tiêu cự bốn phẩy hai milimet, pixel bốn phẩy một micrômet. »

*(Đọc xích kinh, xích vĩ, số sao khớp và độ trễ trên màn.)* « Trên mặt nạ địa hình, mạng còn một điểm, tâm cổ điển còn hai mươi lăm điểm. Sau cải tiến, mạng giải đúng năm mươi bốn trên bảy mươi chín cặp, lệch LOST không phẩy không ba bốn độ trong khoảng hai phẩy bảy sáu giây. Còn tâm cổ điển, khi lọc sạch đốm nhiễu địa hình chỉ còn một cặp đúng — dưới ngưỡng ba — nên chốt chặn trả về LOST an toàn kèm mười sáu byte không, tuyệt đối không xuất tư thế giả. »

### 2.6. Cải tiến Chặng 1 & Số Zhao (~60 giây)

**Có thể chỉ slide 9–15 nếu đang chiếu song song.**

**Lời thoại:**

« Thêm bốn mươi khung lóa mạnh: tâm cổ điển giải đúng bốn mươi trên bốn mươi khung với trung vị một phẩy chín chín giây cung, mạng giải đúng ba mươi chín trên bốn mươi khung. Trên một trăm ca đối kháng của Chặng một, chốt chặn mới và kiểm tra thẳng hàng SVD kéo tỷ lệ khóa sai False Lock từ bốn mươi mốt phần trăm về không phần trăm. Trên tập ảnh trời thật hiệu chuẩn của ESA tetra3 Alt60, cả hai giải đúng ở mức hai phẩy hai sáu đến bốn phẩy sáu lăm giây cung.

Số trong bài Zhao là số của tác giả: khoảng hai mươi mili giây trên RTX 2060M, khoảng hai trăm sáu mươi sáu mili giây trên Coral. Hình trên slide có ghi nguồn arXiv 2404.19108. »

### 2.7. Quaternion + giới hạn + kết (~50–60 giây)

**Trên màn:** Tab **📐 Đối Chiếu Tư Thế & Downlink**.

**Lời thoại:**

« Đầu ra là bốn số thực ba mươi hai bit, tức mười sáu byte, hướng camera trong hệ J2000 trên phần mềm demo PC, hoặc mười sáu byte không khi LOST.

Ảnh seed là mô phỏng. Trên năm trăm khung sạch, mạng có RMSE cao hơn tâm cổ điển. Mặt nạ núi là ước lượng, có hình để kiểm bằng mắt. Toàn bộ thí nghiệm chạy trên laptop RTX 5070 và CPU — nhóm chưa kiểm chứng trên phần cứng vệ tinh hay bức xạ bay.

Em xin cảm ơn quý thầy cô. Em sẵn sàng trả lời câu hỏi. »

---

## 3. Câu hỏi nhanh (rút gọn — chi tiết ở `CAU_HOI_BGK.md`)

1. Lost-in-space? → Không có tư thế ban đầu; từ ảnh sao ra quaternion 16 byte (hoặc `0x00` khi `LOST`).
2. Vì sao tâm cổ điển chính xác hơn trên ảnh sạch? → 500 khung `thr2`: RMSE `0,1804` px (`Prec 100%`) vs `0,4745` px (`Prec 75,4%`); E2E `2,00″` vs `7,94″`.
3. Vì sao dùng mạng trên ảnh núi? → Núi/cây `25` so với `1`; hậu kiểm mạng giải `SOLVED 54/79` (`Δ 0,034°`, `~2,76 s`), còn CoG bị tạp núi & méo góc rộng nên chốt chặn từ chối an toàn `LOST [INSUFFICIENT_INLIER_PAIRS]`.
4. Chốt chặn từ chối khớp sai Chặng 1? → Sửa lỗi `break`, lọc ngoại lai trước & sau gắn sao bổ sung, kiểm SVD thẳng hàng → `0/100 (0% False Lock)` vs `41/100 (41%)` cũ.
5. Ảnh núi có phải nhóm chụp? → Không. Ảnh công bố kèm LOST (ĐH Washington).
6. Có AI không? → Mạng chỉ ở bước tìm tâm (hỗ trợ 8/12/16-bit). Nhận dạng và tư thế là Pyramid và Wahba.
7. Có dùng mét trên mặt đất hay kiểm chứng bay chưa? → Không dùng GSD mét; đây là phần mềm demo PC Laptop, chưa kiểm chứng trên phần cứng vệ tinh hay bus ADCS bay.
8. Đối soát Log–Slide? → Đã xóa toàn bộ số cũ chưa đối soát, sửa Slide 7/8/10/18, bổ sung 6 slide cải tiến, CNN-Hybrid/Auto-Router & kiểm toán nhúng CubeSat (tổng 19 slide).

---

## 4. Checklist sân khấu

```text
□ python app.py → http://127.0.0.1:8765/
□ FAST + Seed 42 + CoG → chạy thử → đọc KPI (đối chiếu 0,446″ trong JSON)
□ 🏔 Ảnh núi thật → CNN SOLVED (54/79) rồi CoG LOST [INSUFFICIENT_INLIER_PAIRS]
□ 🌌 Ảnh trời thật (ESA tetra3 Alt60) → giải ảnh 16-bit thực tế
□ Tab quaternion 16 byte + nhấn mạnh phạm vi PC Demo (chưa kiểm chứng bay)
□ Slide: AI2026_Portfolio/AI2026_SLIDE_THUYET_TRINH.pptx (19 slide đã đối soát)
```
