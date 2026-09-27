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
| Quy tắc lai | Ảnh giả lập / Sao chuẩn / khung dataset → CoG; CNN chỉ demo núi thật (núi/cây 1 vs CoG 25, nhanh hơn). Không claim CNN cho mọi khung. |
| Số liệu kết quả live | Chỉ đọc số **đang hiện trên màn hình**. Không nhớ số cũ. Không bịa. |
| Số liệu hồ sơ (đã đo) | CoG RMSE **0.1804** px / ~**34** ms; CNN **0.4745** px / ~**60** ms (500 khung 1024×683, RTX 5070). Sim sạch: CoG ~**0,446″** vs CNN ~**1,65″**. Núi LOST: núi/cây CoG **25** vs CNN **1**. Web khóa: CNN **63/79** ~**5** s RA **310,49°** Dec **+36,01°**; CoG **64/106** ~**16** s RA **310,52°** Dec **+35,95°** — cả hai lệch LOST ≲ **0,1°** (LOST 310,446/+36,023). |
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

« Sai số góc trên màn là … . Độ trễ … . Số sao định danh … trên … . Em chỉ đọc số vừa hiện. Trên bộ năm trăm khung sạch trong hồ sơ, CoG RMSE khoảng không phẩy một tám không bốn pixel, khoảng ba mươi bốn mili giây; CNN khoảng không phẩy bốn bảy bốn năm pixel, khoảng sáu mươi mili giây — CoG thắng trên sim sạch. Không được nói CNN luôn tốt hơn. »

### 2.5. Demo Ảnh núi thật — điểm sáng tạo (~90–110 giây)

**Việc:**

1. Bấm **🏔 Ảnh núi thật** (preset tự gắn CNN + 4,2 mm · 4,1 µm).
2. Đọc số trên màn (RA/Dec, ID, độ trễ).
3. (Tuỳ chọn so) Đổi radio sang **Centroid cổ điển** → chạy lại → đọc số.
4. So sánh miệng với số hồ sơ nếu khớp.

**Lời thoại:**

« Đây là điểm sáng tạo. Em bấm Ảnh núi thật — preset tự chọn CNN vì trên ca núi CNN gần như không chấm địa hình (một điểm vs CoG hai mươi lăm) và nhanh hơn CoG. Đây là ảnh thật công bố kèm bộ LOST của Đại học Washington — Mount St. Helens — không phải ảnh nhóm em chụp. Khung một nghìn không hai bốn vuông, tiêu cự bốn phẩy hai milimet, pixel bốn phẩy một micrômet. »

*(Đọc RA/Dec, ID, độ trễ trên màn)* « Hồ sơ: CNN một điểm trên núi cây; CoG hai mươi lăm điểm núi/cây. Boresight gần LOST. Đây là chỗ dùng CNN — không thay số RMSE trên sim sạch. »

### 2.6. Số đo + Zhao ngắn (~40–50 giây)

**Có thể chỉ slide 5–7 nếu đang chiếu song song.**

**Lời thoại:**

« Thêm bộ lóa mạnh bốn mươi khung: CoG RMSE khoảng không phẩy một bốn năm, CNN khoảng không phẩy ba chín năm — CNN vẫn không thắng RMSE trên bộ đó.

Số bài báo Zhao: MobileUNet khoảng hai mươi mili giây trên RTX 2060M ở sáu trăm bốn mươi nhân bốn trăm tám mươi, khoảng hai trăm sáu mươi sáu mili giây trên Coral TPU — đó là số của tác giả, không phải đo của nhóm. Hình minh họa ghi chú Nguồn Zhao và cộng sự. »

### 2.7. Quaternion + giới hạn + kết (~50–60 giây)

**Trên màn:** Tab **📐 Đối Chiếu Tư Thế & Downlink**.

**Lời thoại:**

« Đầu ra đóng gói bốn float ba mươi hai bit — mười sáu byte — hướng camera J2000. Ảnh chỉ để kiểm mắt.

Giới hạn: ảnh Seed là mô phỏng; trên sim sạch CNN lệch miền nên RMSE cao hơn CoG; mặt nạ núi cây là heuristic kèm overlay; attitude end-to-end trên bộ lớn chưa kiểm được lần này.

Em xin cảm ơn quý thầy cô. Em sẵn sàng trả lời câu hỏi. »

---

## 3. Câu hỏi nhanh (rút gọn — chi tiết ở `CAU_HOI_BGK.md`)

1. Lost-in-space? → Không có tư thế ban đầu; từ ảnh sao ra quaternion.  
2. Vì sao CoG thắng sim sạch? → Đo 500 khung thr2: RMSE 0.1804 vs 0.4745 px.  
3. Vì sao nói CNN sáng tạo? → Ảnh núi LOST: núi/cây 25 vs 1; CNN ~5 s (63/79) vs CoG ~16 s (64/106).  
4. Ảnh núi có phải nhóm chụp? → Không — mẫu công bố kèm LOST.  
5. Có AI không? → CNN centroid tùy chọn; lõi Pyramid/Wahba cổ điển.  
6. GSD mét? → Không dùng cho star tracker.  
7. Đầu ra? → Quaternion 16 byte.  
8. Cổng cấp 6? → Có trên web; một khung sim thử không thắng CoG — không overclaim.

---

## 4. Năm câu không được nói

1. Không nêu VinAI, Alvium, IMX, Schneider, Jetson, 8U, điểm số công ty cũ.  
2. Không gán GSD mét mặt đất cho star tracker.  
3. Không nói «CNN luôn tốt hơn» — trên sim sạch và lóa mạnh CoG thắng RMSE.  
4. Không gọi ảnh núi là «ảnh nhóm chụp».  
5. Không bịa số — thiếu thì «chưa kiểm được»; live thì chỉ đọc màn hình.

---

## 5. Checklist sân khấu

```text
□ python app.py → http://127.0.0.1:8765/
□ FAST + Seed 42 + CoG → chạy thử → đọc KPI
□ 🏔 Ảnh núi thật → CoG rồi CNN → đối chiếu 25 vs 1
□ Tab quaternion 16 byte
□ Nhắc: sim sạch CoG thắng; núi LOST = sáng tạo; số Zhao = của tác giả
□ Slide: AI2026_SLIDE_THUYET_TRINH.pptx (có overlay núi)
```
