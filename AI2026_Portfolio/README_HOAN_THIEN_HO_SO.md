# Hướng dẫn hoàn thiện hồ sơ đêm nay — Star Tracker (Bảng C)

**Đọc file này trước.** Mục tiêu: bạn (bạn của tác giả) có thể **quay video, đóng gói, nộp** mà không cần hỏi lại tác giả.

- **Không** sửa / ghi đè `README.md` kỹ thuật của phần mềm.
- **Không** sửa `.docx` / `.pptx` trong lúc quay nếu agent khác đang sửa hình (xem mục 2.3 về PNG núi).
- File này nằm ở **gốc thư mục dự án**, không nằm trong `docs/`.

---

## 1. Đội thi (một dòng)

Trường Đại học Bách khoa, Đại học Đà Nẵng, Khoa Công nghệ thông tin — GVHD TS. Nguyễn Năng Hùng Vân — 3 sinh viên đã ghi trong hồ sơ: Hoàng Trần Đức Hải (đội trưởng), Nguyễn Tiến, Mai Tạ Trúc Vy.

*(Không nhắc số điện thoại hay địa chỉ nhà trong video / slide / kê khai công khai ngoài mẫu bắt buộc của BTC.)*

---

## 2. Đã xong vs còn phải làm tối nay

### 2.1. Đã có sẵn (không cần viết lại từ đầu)

| Hạng mục | Trạng thái |
|---|---|
| Hồ sơ 13 mục Bang C | Có `AI2026_Ho-so-du-an_StarTracker.docx` **và** bản `.md` đồng bộ nội dung |
| Slide thuyết trình | Có `AI2026_SLIDE_THUYET_TRINH.pptx` |
| Kịch bản nói miệng ~7–8 phút | Có `KICH_BAN_THUYET_TRINH.md` |
| Kịch bản quay demo ~3–5 phút | Có `KICH_BAN_QUAY_DEMO.md` |
| Ngân hàng hỏi đáp BGK | Có `CAU_HOI_BGK.md` |
| Phần mềm demo + hướng dẫn chạy | Có `app.py`, `README.md`, `requirements.txt` |
| Khai báo bên thứ ba / AI / thư viện | Có `THIRD_PARTY_NOTICES.md` (+ trích dẫn Zhao, BSC5, tetra3, LOST trong hồ sơ) |
| Hình so sánh núi CoG vs CNN | Có `data/outputs/mount_st_helens_cog_vs_cnn.png` (đã regenerate: mặt nạ chỉ dưới rid; xanh CNN trải giữa bầu trời) |

### 2.2. Bạn phải sản xuất tối nay (chưa có file sẵn)

Cuộc thi cần **hai video riêng**:

1. **Video thuyết trình** — theo `KICH_BAN_THUYET_TRINH.md` (~7–8 phút nói; có thể chiếu slide + demo).
2. **Video trình diễn sản phẩm** — theo `KICH_BAN_QUAY_DEMO.md` (~3–5 phút quay màn hình + giọng đọc).

**Hiện chỉ có kịch bản Markdown — chưa có file `.mp4`.** Bạn phải quay / export hai file video rồi gắn vào bộ nộp.

Thêm việc bắt buộc về mã nguồn:

- Thư mục dự án **chưa phải git repo** / **chưa có remote** → **chưa có link nguồn mã** để kê khai.
- Bạn hoặc tác giả phải **upload cả thư mục** lên GitHub / GitLab / Drive công khai (hoặc tạo repo rồi push), rồi điền **URL thật** vào hồ sơ / phiếu kê khai. **Không bịa URL Drive.**

### 2.3. Hình núi — kiểm tra trước khi đưa vào video

File: `data/outputs/mount_st_helens_cog_vs_cnn.png`

- Đã regenerate từ centroid hiện tại (contrast-ranked 8-bit): xanh CNN trải giữa bầu trời; đỏ chỉ vùng núi/cây dưới rid.
- Đếm khóa: CoG núi/cây **25** / trời **86**; CNN núi/cây **1** / trời **78**. Web: CNN **63/79** ~**5** s; CoG **64/106** ~**16** s.
- **Trước khi quay:** mở lại PNG một lần để kiểm mắt. Số đếm lấy đúng câu trong `AI2026_Ho-so-du-an_StarTracker.md`.

### 2.4. Cách chạy demo (để quay video trình diễn)

Trong thư mục gốc dự án (`star_tracker_an_danh`):

```text
pip install -r requirements.txt
python app.py
```

Mở trình duyệt: **http://127.0.0.1:8765/**

Chi tiết thêm: `README.md`.

### 2.5. Thứ tự bấm nút cho video demo (bắt buộc)

**Quy tắc lai (preset tự chọn centroid):** ảnh giả lập / Seed 42 / Sao chuẩn / khung dataset → **Centroid cổ điển**; nút **Ảnh núi thật** → **CNN** + quang học 4,2 mm · 4,1 µm. Radio vẫn đổi tay được nếu BGK muốn so.

1. **Seed 42** (tự gắn CoG) → Sinh ảnh & giải tư thế.  
   - Kỳ vọng trên sim sạch (tham khảo): sai số góc khoảng **~0.45″** (CoG) vs CNN **~1.65″** nếu lần chạy sạch — **CoG chính xác hơn**.  
   - **Luôn đọc số đang hiện trên màn hình** — không nhớ số lần trước.
2. Nút **Ảnh núi thật** (tự gắn CNN + 4,2 mm / 4,1 µm) → đọc số trên màn (tham chiếu hồ sơ: ~5 s, 63/79, RA ~310,49° Dec ~+36,01°).
3. (Tuỳ chọn so) Đổi radio sang **Centroid cổ điển** → chạy lại → đọc số (tham chiếu: ~16 s, 64/106, RA ~310,52° Dec ~+35,95°).
4. (Nên có) Tab đối chiếu tư thế / downlink → chỉ quaternion **16 byte**.

**Câu trung thực bắt buộc nói:**

- Trên **mô phỏng sạch**, CoG **chính xác hơn** (~0,446″ vs CNN ~1,65″).
- Trên **ảnh núi thật** (mẫu LOST công bố, không phải ảnh nhóm chụp), CNN **đánh ít sao giả trên địa hình** hơn và **ID nhanh hơn** trên ca này — **không** nói CNN luôn tốt hơn.

---

## 3. Checklist khớp yêu cầu cuộc thi

Đối chiếu trước khi mang nộp:

- [ ] **Danh sách thành viên** (3 SV + GVHD) khớp hồ sơ — không thêm người lạ.
- [ ] **Hồ sơ dự án** Bang C: `AI2026_Ho-so-du-an_StarTracker.docx` (và giữ `.md` nếu cần đồng bộ).
- [ ] **Video thuyết trình** (mp4) — theo `KICH_BAN_THUYET_TRINH.md`.
- [ ] **Video trình diễn sản phẩm** (mp4) — theo `KICH_BAN_QUAY_DEMO.md`.
- [ ] **Link mã nguồn** — repo/upload đã có URL thật (hiện **thiếu remote**; phải upload thư mục).
- [ ] **Khai báo AI / dataset / thư viện:** dùng `THIRD_PARTY_NOTICES.md` và nêu rõ:
  - Zhao et al., **arXiv:2404.19108** (MobileUNet công khai, không huấn luyện lại)
  - Catalog **Yale BSC5**
  - Tham khảo thuật toán / lineage: **ESA tetra3**, **UW LOST**
- [ ] Slide `AI2026_SLIDE_THUYET_TRINH.pptx` sẵn nếu cần chiếu.
- [ ] PNG núi đã kiểm mắt (mặt nạ đỏ không phủ trời) trước khi gắn vào video/slide.

**Bối cảnh hạn / nộp (theo thông tin đội):**

- Hoàn thiện hồ sơ khoảng **26–29/9/2026**.
- Nộp tại **Phòng Công tác Sinh viên S06.08**.
- Liên hệ: **Đới Phương Thanh**.
- Không tự bịa thêm đường dẫn Google Drive.

---

## 4. Bản đồ file (một câu mỗi file)

| File / đường dẫn | Việc gì |
|---|---|
| `AI2026_Ho-so-du-an_StarTracker.docx` | Bản Word hồ sơ dự án Bang C để in / nộp. |
| `AI2026_Ho-so-du-an_StarTracker.md` | Bản Markdown cùng nội dung hồ sơ — mở để đọc số đo và câu claim mới nhất. |
| `AI2026_SLIDE_THUYET_TRINH.pptx` | Slide chiếu khi thuyết trình. |
| `KICH_BAN_THUYET_TRINH.md` | Lời nói miệng ~7–8 phút + nhịp thời gian + checklist sân khấu. |
| `KICH_BAN_QUAY_DEMO.md` | Kịch bản quay màn hình ~3–5 phút, từng cảnh bấm nút. |
| `CAU_HOI_BGK.md` | Câu hỏi–đáp sẵn cho ban giám khảo. |
| `README.md` | Hướng dẫn kỹ thuật: cài đặt, chạy `app.py` / CLI, quang học demo. |
| `THIRD_PARTY_NOTICES.md` | Giấy phép và nguồn thư viện / catalog / CNN bên thứ ba. |
| `README_HOAN_THIEN_HO_SO.md` | File bạn đang đọc — checklist đóng gói đêm nay. |
| `app.py` | Server demo web tại cổng 8765. |
| `data/outputs/mount_st_helens_cog_vs_cnn.png` | Overlay CoG (cam) vs CNN (xanh) trên ảnh núi LOST — kiểm mặt nạ đỏ trước khi quay. |
| `data/uploads/mount_st_helens_1.png` | Ảnh núi gốc (mẫu công bố kèm LOST). |
| `requirements.txt` | Dependency Python để cài trước khi chạy demo. |

---

## 5. Không được nói (video / miệng / slide)

1. **VinAI** (và ngữ cảnh công ty / sản phẩm bay nội bộ).
2. Tên cảm biến / ống kính cũ kiểu thương mại bay: **Alvium, IMX, Schneider, Jetson, 8U**, v.v.
3. **Số liệu công ty cũ** (điểm số / GSD / thông số không thuộc demo laptop này).
4. Câu **«CNN luôn chính xác hơn»** — sai với kết quả sim sạch (và bộ lóa) trong hồ sơ.
5. Gọi ảnh núi là **«ảnh nhóm chụp»** — phải nói mẫu **LOST công bố**.
6. Gán **GSD mét mặt đất** cho star tracker.
7. Bịa số / bịa URL Drive / bịa tên người ngoài hồ sơ — thiếu thì nói **«chưa kiểm được»**; live thì **chỉ đọc màn hình**.

---

## 6. Quy trình tối thiểu tối nay (copy nhanh)

```text
1) Mở README_HOAN_THIEN_HO_SO.md + AI2026_Ho-so-du-an_StarTracker.md (đọc số núi mới nhất)
2) Kiểm mount_st_helens_cog_vs_cnn.png — đỏ không phủ trời?
3) pip install -r requirements.txt  (nếu chưa)
4) python app.py → http://127.0.0.1:8765/
5) Quay VIDEO TRÌNH DIỄN (3–5 phút): Seed 42 + CoG → Ảnh núi + CoG → CNN → 16 byte
6) Quay / ghi VIDEO THUYẾT TRÌNH (7–8 phút) theo KICH_BAN_THUYET_TRINH.md
7) Upload mã nguồn → lấy URL thật → điền kê khai
8) In / PDF hồ sơ .docx + 2 mp4 + checklist mục 3 → nộp S06.08
```

**Câu nhớ khi kết demo:** *Sim sạch thì CoG thắng độ chính xác; ảnh núi thật thì CNN lọc sao giả trên địa hình tốt hơn — đó là điểm sáng tạo, không phải “CNN luôn hơn”.*

Chúc nộp xong trước hạn.
