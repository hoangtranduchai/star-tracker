# Kịch bản quay demo Star Tracker (laptop)

Dùng cho người quay / bạn bè chưa biết dự án. Đọc to được. Không làm slide. Quay màn hình + giọng đọc.

**Đơn vị:** Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin  
**Thời lượng mục tiêu:** **3–5 phút**  
**Web:** `http://127.0.0.1:8765/` sau `python app.py`  
**Quy tắc số:** Mọi số live chỉ đọc **đúng trên màn hình**. Số hồ sơ chỉ nhắc khi đã đo sẵn (xem mục 0).

**Thiếu (không bịa):** hai file video minh chứng · URL git remote.

**Quy tắc lai (đọc trước khi quay):** Preset Seed 42 / Sao chuẩn / khung dataset tự chọn **Centroid cổ điển**; nút **Ảnh núi thật** tự chọn **CNN** + f=4,2 mm · pixel 4,1 µm. CNN không dùng cho mọi khung — chỉ demo núi thật (núi/cây 1 vs CoG 25, nhanh hơn). Radio vẫn đổi tay được.

---

## 0. Số đã khóa (đọc khi cần, không bịa)

| Bộ | Kết luận |
|---|---|
| 500 khung sạch 1024×683, RTX 5070, `centroid_benchmark_hd1024_thr2.json` | CoG RMSE **0.1804** px · ~**34** ms; CNN **0.4745** px · ~**60** ms → **CoG thắng** |
| Lóa mạnh 40 khung, `…_glare_sun_strong.json` | CoG **0.1449** vs CNN **0.3951** → **CNN không thắng** |
| Ảnh núi LOST — mặt nạ `mount_st_helens_centroid_compare.json` | CoG núi/cây **25** · trời **86**; CNN núi/cây **1** · trời **78** (tổng CoG 111 / CNN 79) |
| Ảnh núi — web khóa `mount_st_helens_lost_compare.json` vs LOST **310.446° / +36.0229°** | CNN RA **310.49°** Dec **+36.01°** (Δ **~0.038°**) · **63/79** · ~**5,1** s; CoG RA **310.52°** Dec **+35.95°** (Δ **~0.094°**) · **64/106** · ~**16,2** s — cả hai ≲ **0,1°** vs LOST |
| Sim sạch (tham chiếu hồ sơ) | CoG vẫn chính xác hơn (~**0,446″** vs CNN ~**1,65″**); không claim CNN luôn tốt hơn |
| Zhao et al. arXiv:2404.19108 | ~**20** ms RTX 2060M @ 640×480; ~**266** ms Coral TPU — **số tác giả** |

---

## 1. Chuẩn bị (trước khi ghi)

1. `pip install -r requirements.txt` (một lần).  
2. Trong thư mục dự án: `python app.py` → mở `http://127.0.0.1:8765/`.  
3. Phòng yên; Full HD; zoom trình duyệt ~90–100%.  
4. Chạy thử: Seed 42 (tự CoG); rồi **Ảnh núi thật** (tự CNN) — hết lỗi mới Record.

**Cấu hình mặc định trước cảnh 1:**  
FAST MODE · Yale BSC5 · SVD · Kính demo (50 mm · 3,72 µm) · Seed 42 · **Centroid cổ điển**.

---

## 2. Thời lượng

| Phần | Thời lượng |
|------|------------|
| Mở đầu | 20–30 s |
| Pipeline + camera | 35–45 s |
| Seed 42 CoG (đọc KPI) | 45–60 s |
| Ảnh núi thật (CNN mặc định; tuỳ chọn so CoG) | 70–100 s |
| Quaternion 16 byte + kết | 35–45 s |
| **Tổng** | **3–5 phút** |

Nếu dài: cắt bớt quang học; **giữ** cảnh núi + đọc số màn hình.

---

## 3. Từng cảnh

### Cảnh 0 — Thẻ mở (tuỳ chọn, 5 s)

```text
Trường Đại học Bách khoa, Đại học Đà Nẵng
Khoa Công nghệ thông tin
Demo Star Tracker trên laptop
```

« Demo Star Tracker trên laptop, Trường Đại học Bách khoa, Đại học Đà Nẵng, Khoa Công nghệ thông tin. »

---

### Cảnh 1 — Mở app (25–35 s)

**Việc:** Chỉ tiêu đề; chỉ hai chế độ centroid (CoG / CNN).

**Lời thoại:**  
« Giao diện demo: từ ảnh sao ra quaternion hướng camera. Ba bước — centroid, Pyramid với K-vector, Wahba. Ảnh giả lập dùng centroid cổ điển; CNN chỉ để demo ảnh núi thật vì ở đó nó gần như không chấm địa hình (một vs hai mươi lăm) và nhanh hơn. »

---

### Cảnh 2 — Camera ngắn (20–30 s)

**Việc:** Tab **Camera demo** → chỉ 6000×4000, 3,72 µm, 50 mm, FAST 1500×1000 → quay lại tab ảnh.

**Lời thoại:**  
« Camera demo APS-C khoảng hai mươi bốn megapixel, năm mươi milimet. Quay bằng FAST cho mượt. »

---

### Cảnh 3 — Seed 42, CoG (45–60 s) — cảnh bắt buộc

**Việc:** Bấm **↺ Khung Chuẩn (Seed 42)** (tự gắn CoG) · đọc KPI trên màn.

**Lời thoại lúc bấm:**  
« Em bấm Seed bốn mươi hai — preset tự chọn centroid cổ điển vì trên ảnh sạch CoG chính xác hơn CNN. »

**Sau khi có số:**  
« Sai số góc … . Độ trễ … . Sao định danh … trên … . Trong hồ sơ năm trăm khung sạch: CoG khoảng không phẩy một tám, CNN khoảng không phẩy bốn bảy — không được nói CNN luôn tốt hơn. »

---

### Cảnh 4 — Ảnh núi thật (70–100 s) — cảnh sáng tạo, bắt buộc

**Việc (chậm, rõ nút):**

1. Bấm **🏔 Ảnh núi thật** (tự gắn CNN + f=4,2 mm · pixel 4,1 µm · 1024×1024).  
2. **Đọc số trên màn hình** (RA/Dec, ID x/y, độ trễ).  
3. (Tuỳ chọn so) Đổi radio sang **Centroid cổ điển** → chạy lại → đọc số.  
4. Nói rõ đây là mẫu LOST công bố, không phải ảnh nhóm chụp. So với LOST **310,446° / +36,0229°** nếu số gần.

**Lời thoại:**  
« Bấm Ảnh núi thật. Preset tự chọn CNN và quang học bốn phẩy hai milimet, bốn phẩy một micrômet. Đây là ảnh công bố kèm LOST — Mount St. Helens — không phải ảnh nhóm chụp. »

*(Đọc số màn: RA … Dec … · định danh … / … · độ trễ …)*  
« Hồ sơ: CNN một điểm trên núi cây; CoG hai mươi lăm điểm núi/cây. CNN sạch hơn trên ca này và thường nhanh hơn CoG trên ảnh núi — đó là điểm sáng tạo. Boresight gần LOST. Không nói CNN thắng RMSE trên sim sạch. »

**Gợi ý số nếu màn gần lần khóa đã ghi:** CNN RA ~310,49° Dec ~+36,01° · 63/79 · ~5 s; CoG RA ~310,52° Dec ~+35,95° · 64/106 · ~16 s. **Chỉ đọc số đang hiện.**

---

### Cảnh 5 — Quaternion + kết (35–45 s)

**Việc:** Tab **📐 Đối Chiếu Tư Thế & Downlink** · chỉ q0–q3 · 16 byte.

**Lời thoại:**  
« Đầu ra là bốn float ba mươi hai bit — mười sáu byte — không gửi ảnh thô. Cảm ơn đã xem. »

---

## 4. Không quay / không nói

- Không nói CNN luôn thắng.  
- Không gọi ảnh núi là ảnh tự chụp.  
- Không nêu VinAI / Alvium / IMX / Schneider / Jetson / 8U.  
- Không đọc số nhớ từ lần trước — chỉ màn hình.  
- Không bịa Drive / git remote / video thiếu.

---

## 5. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|------------|------------|
| Trang trắng | Chạy lại `python app.py`, đúng cổng **8765** |
| CNN chậm / lỗi lần đầu | Chạy thử trước khi ghi; lần đầu có thể warmup GPU |
| Status 409 | Đợi hết vòng, chỉ bấm một lần |
| Quên nút núi | Nhìn quick-actions: **🏔 Ảnh núi thật** |

---

## 6. Checklist trước khi gửi video

- [ ] 3–5 phút, mở được trên điện thoại  
- [ ] Có Seed 42 (CoG) và nhắc CoG thắng trên sim sạch  
- [ ] Có bấm **Ảnh núi thật** (CNN mặc định), đọc số màn hình (RA/Dec + ID); tùy chọn so CoG  
- [ ] Nói rõ ảnh LOST công bố, không phải nhóm chụp  
- [ ] Có quaternion 16 byte  
- [ ] Không lộ VinAI / cảm biến thương mại cấm  
- [ ] Âm thanh rõ, không popup Windows  

```text
1) python app.py → 127.0.0.1:8765
2) ↺ Seed 42 → (tự CoG) đọc KPI
3) 🏔 Ảnh núi thật → (tự CNN + 4,2 mm / 4,1 µm) đọc RA/Dec + ID trên màn
4) Tab Downlink → 16 byte → kết
```
