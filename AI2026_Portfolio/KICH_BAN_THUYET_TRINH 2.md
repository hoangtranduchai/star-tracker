# Kịch bản thuyết trình miệng — Star Tracker (laptop demo)

**Đơn vị:** Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin  
**Đội (theo hồ sơ):** Hoàng Trần Đức Hải · Nguyễn Tiến · Mai Tạ Trúc Vy  
**GVHD:** TS. Nguyễn Năng Hùng Vân  
**File này:** lời nói + hỏi đáp. Không phải slide. Slide: `AI2026_SLIDE_THUYET_TRINH.pptx`.

---

## 1. Cách dùng file

| Hạng mục | Gợi ý |
|---|---|
| Thời lượng nói | **7–8 phút** (không tính hỏi đáp) |
| Công cụ | Laptop + trình duyệt `http://127.0.0.1:8765/` (chạy `python app.py` trước) |
| Demo sạch (Seed) | **⚡ FAST MODE**, Yale BSC5 (V ≤ 6), Wahba **SVD**, kính demo 50 mm · 3,72 µm, Seed **42** — preset tự gắn **CoG** |
| Demo sáng tạo | Nút **🏔 Ảnh núi thật** — preset tự gắn **CNN** + 4,2 mm · 4,1 µm → đọc số trên màn (radio vẫn đổi tay được) |
| Quy tắc lai | Ảnh giả lập và Seed 42 dùng CoG. Nút Ảnh núi thật dùng CNN. |
| Số liệu kết quả live | Chỉ đọc số **đang hiện trên màn hình**. |
| Số liệu hồ sơ (đã đo) | 500 khung sạch: CoG RMSE **0,1804** px / khoảng **34** ms; CNN **0,4745** px / khoảng **60** ms. Một khung sạch, tâm cổ điển, seed 42: **0,446″**. Núi LOST: núi/cây CoG **25**, CNN **1**. CNN khớp **63/79**, khoảng **5** s, RA **310,49°**, Dec **+36,01°**. CoG khớp **64/106**, khoảng **16** s, RA **310,52°**, Dec **+35,95°**. LOST công bố: **310,446° / +36,0229°**. |
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

**Trang «Nội dung thuyết trình»:**

« Em đi sáu phần. Trước hết là bài toán: từ một ảnh sao ra quaternion mười sáu byte. Tiếp theo là đường ống thuật toán: tìm tâm, nhận dạng sao, rồi giải hướng. Sau đó là số đo trên ảnh sạch, rồi ảnh núi thật, và phần trích dẫn tách riêng khỏi số của nhóm. »

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

« Sai số góc trên màn là … . Độ trễ … . Số sao định danh … trên … . Em chỉ đọc số vừa hiện. Trên năm trăm khung sạch, tâm cổ điển có RMSE không phẩy một tám không bốn pixel, khoảng ba mươi bốn mili giây. Mạng là không phẩy bốn bảy bốn năm pixel, khoảng sáu mươi mili giây. Khung sạch seed bốn mươi hai, tâm cổ điển, lệch không phẩy bốn bốn sáu giây cung. »

### 2.5. Demo Ảnh núi thật — điểm sáng tạo (~90–110 giây)

**Việc:**

1. Bấm **🏔 Ảnh núi thật** (preset tự gắn CNN + 4,2 mm · 4,1 µm).
2. Đọc số trên màn (RA/Dec, ID, độ trễ).
3. (Tuỳ chọn so) Đổi radio sang **Centroid cổ điển** → chạy lại → đọc số.
4. So sánh miệng với số hồ sơ nếu khớp.

**Lời thoại:**

« Đây là điểm sáng tạo. Em bấm Ảnh núi thật. Ảnh này công bố kèm phần mềm LOST của Đại học Washington, núi St. Helens, không phải ảnh nhóm em chụp. Khung một nghìn không hai mươi bốn vuông, tiêu cự bốn phẩy hai milimet, pixel bốn phẩy một micrômet. »

*(Đọc xích kinh, xích vĩ, số sao khớp và độ trễ trên màn.)* « Trên mặt nạ địa hình, mạng còn một điểm, tâm cổ điển còn hai mươi lăm điểm. Cả hai hướng lệch số LOST công bố dưới một phần mười độ. Trên năm trăm khung sạch, tâm cổ điển vẫn chính xác hơn về tâm sao. »

### 2.6. Số đo + Zhao ngắn (~40–50 giây)

**Có thể chỉ slide 5–7 nếu đang chiếu song song.**

**Lời thoại:**

« Thêm bốn mươi khung lóa mạnh: tâm cổ điển RMSE khoảng không phẩy một bốn bốn chín pixel, mạng khoảng không phẩy ba chín năm một pixel.

Số trong bài Zhao là số của tác giả: khoảng hai mươi mili giây trên RTX 2060M, khoảng hai trăm sáu mươi sáu mili giây trên Coral. Hình trên slide có ghi nguồn arXiv 2404.19108. »

### 2.7. Quaternion + giới hạn + kết (~50–60 giây)

**Trên màn:** Tab **📐 Đối Chiếu Tư Thế & Downlink**.

**Lời thoại:**

« Đầu ra là bốn số thực ba mươi hai bit, tức mười sáu byte, hướng camera trong hệ J2000.

Ảnh seed là mô phỏng. Trên năm trăm khung sạch, mạng có RMSE cao hơn tâm cổ điển. Mặt nạ núi là ước lượng, có hình để kiểm bằng mắt. Sai số góc em vừa đọc là của một khung sạch.

Em xin cảm ơn quý thầy cô. Em sẵn sàng trả lời câu hỏi. »

---

## 3. Câu hỏi nhanh (rút gọn — chi tiết ở `CAU_HOI_BGK.md`)

1. Lost-in-space? → Không có tư thế ban đầu; từ ảnh sao ra quaternion.  
2. Vì sao tâm cổ điển chính xác hơn trên ảnh sạch? → 500 khung: RMSE 0,1804 px so với 0,4745 px.  
3. Vì sao dùng mạng trên ảnh núi? → Núi/cây 25 so với 1; mạng khoảng 5 giây, khớp 63/79; tâm cổ điển khoảng 16 giây, khớp 64/106.  
4. Ảnh núi có phải nhóm chụp? → Không. Ảnh công bố kèm LOST.  
5. Có AI không? → Mạng chỉ ở bước tìm tâm. Nhận dạng và tư thế là Pyramid và Wahba.  
6. Có dùng mét trên mặt đất không? → Không. Đầu ra là hướng.  
7. Đầu ra? → Quaternion 16 byte.  
8. Cổng chỉ sao từ cấp 6? → Có trên giao diện. Trên một khung đã thử, cổng này không làm mạng chính xác hơn tâm cổ điển.

---

## 4. Checklist sân khấu

```text
□ python app.py → http://127.0.0.1:8765/
□ FAST + Seed 42 + CoG → chạy thử → đọc KPI
□ 🏔 Ảnh núi thật → CoG rồi CNN → đối chiếu 25 vs 1
□ Tab quaternion 16 byte
□ Nhắc: sim sạch CoG thắng; núi LOST = sáng tạo; số Zhao = của tác giả
□ Slide: AI2026_SLIDE_THUYET_TRINH.pptx (có overlay núi)
```
