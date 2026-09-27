# Câu hỏi ban giám khảo — star tracker demo

Trường Đại học Bách khoa, Đại học Đà Nẵng, Khoa Công nghệ thông tin  
Đội: Hoàng Trần Đức Hải · Nguyễn Tiến · Mai Tạ Trúc Vy · GVHD: TS. Nguyễn Năng Hùng Vân

Số đo chỉ lấy từ JSON đã khóa. Thiếu thì nói « chưa kiểm được ». Live demo: đọc số trên màn hình.

---

### 1. Đây là bài toán gì? Lost-in-space nghĩa là gì?

**Trả lời:** Không có tư thế ban đầu. Từ ảnh sao trong trường nhìn, nhận dạng sao rồi ước lượng hướng camera (quaternion) so với catalog cố định.

### 2. Tâm sao (centroid) là gì? Em tính thế nào?

**Trả lời:** Tọa độ dưới mức pixel của đốm sao. Mặc định: trọng tâm cường độ (CoG) sau khử nền và thành phần liên thông. Tùy chọn: MobileUNet công khai (Zhao et al.) + trilateration, d_th=2 — không huấn luyện lại.

### 3. Pyramid / Mortari là gì?

**Trả lời:** Nhận dạng sao theo khoảng cách góc; khớp bộ bốn sao với catalog rồi mở rộng. Không cần tư thế trước; không khớp theo tên chòm sao văn hóa.

### 4. K-vector là gì?

**Trả lời:** Bảng tra nhanh cặp sao theo góc trong catalog, giúp tìm ứng viên gần như thời gian hằng số.

### 5. Wahba / SVD / QUEST?

**Trả lời:** Wahba tìm phép quay tối ưu giữa vector quan sát và catalog. SVD (Kabsch) hoặc QUEST đều cho quaternion; demo mặc định SVD.

### 6. Quaternion — vì sao 16 byte?

**Trả lời:** Bốn float32 × 4 byte = 16 byte. q và −q cùng một tư thế. Không gửi ảnh thô.

### 7. Vì sao FAST, không FULL suốt demo?

**Trả lời:** FULL 6000×4000 nặng trên laptop. FAST 1500×1000 cùng FOV, demo mượt hơn.

### 8. Có dùng AI / CNN không? Lõi có phải học sâu không?

**Trả lời:** Lõi nhận dạng và tư thế là Pyramid + Wahba — cổ điển. CNN chỉ thay bước centroid khi chọn trên web («CNN, chỉ sao từ cấp 6 trở lên sáng»). Không huấn luyện lại trọng số công khai. **Quy tắc lai preset:** ảnh giả lập / Seed 42 / Sao chuẩn / khung dataset → CoG; nút **Ảnh núi thật** → CNN (núi/cây 1 vs CoG 25, nhanh hơn). Radio vẫn đổi tay được. Không claim CNN cho mọi khung.

### 9. CNN có luôn tốt hơn CoG không?

**Trả lời:** Không. Trên 500 khung sạch 1024×683 (RTX 5070, d_th=2): CoG RMSE **0.1804** px / ~**34** ms; CNN **0.4745** px / ~**60** ms — CoG thắng. Lóa mạnh 40 khung: CoG **0.1449** vs CNN **0.3951** — CNN cũng không thắng RMSE. Điểm CNN nổi trên **ảnh núi thật LOST** (núi/cây 1 vs CoG 25, thường nhanh hơn) — preset web gắn CNN chỉ cho ca núi, không cho mọi bộ sim.

### 10. Ảnh núi thật — kết quả và nguồn?

**Trả lời:** File công bố kèm LOST (UW), `mount_st_helens_1.png`, 1024×1024, f=4,2 mm, pixel 4,1 µm — **không phải ảnh nhóm chụp**. Mặt nạ (chỉ dưới rid): CoG tổng 111 (núi/cây **25**, trời **86**); CNN tổng 79 (núi/cây **1**, trời **78**). Web khóa vs LOST **310.446° / +36.0229°**: CNN RA **310.49°** Dec **+36.01°** (Δ **~0.038°**, **63/79**, ~**5** s); CoG RA **310.52°** Dec **+35.95°** (Δ **~0.094°**, **64/106**, ~**16** s) — cả hai ≲ **0,1°**. CNN nhanh hơn trên ca này vì không nhai sao giả địa hình; sim sạch CoG vẫn chính xác hơn (~0,446″ vs CNN ~1,65″). Live chỉ đọc màn. Overlay: `mount_st_helens_cog_vs_cnn.png`. Web: nút **Ảnh núi thật**.

### 11. Vì sao đó là điểm sáng tạo?

**Trả lời:** Cùng pipeline, cùng ảnh khó: CoG đánh nhiều điểm giả trên núi/cây (**25**); CNN gần như chỉ trên trời (**1** trên núi); trên ca núi CNN sạch hơn và ID nhanh hơn (~5 s vs ~16 s). Boresight cả hai gần LOST (≲ ~0,1°). Vẫn trung thực: trên sim sạch CoG chính xác hơn (~0,446″ vs CNN ~1,65″) — không claim CNN luôn tốt hơn.

### 12. Giới hạn trên ảnh tổng hợp / sim?

**Trả lời:** Trên hd1024 sạch (và bộ lóa mạnh đã đo) CNN công khai lệch miền — RMSE cao hơn CoG. Không được claim CNN thắng mọi tình huống. Attitude end-to-end (Δθ) trên bộ sim lớn: chưa kiểm được lần này. Hai file video minh chứng và URL git remote: **chưa kiểm được**. Mặt nạ núi/cây là heuristic — kèm overlay để kiểm mắt.

### 13. Cổng «chỉ sao từ cấp 6 trở lên sáng»?

**Trả lời:** Có trên giao diện CNN. Mục đích: bỏ đỉnh yếu hơn sao catalog V≤6. Trên một khung sim đã thử, cổng này **không** làm CNN thắng CoG — nhắc ngắn, không overclaim.

### 14. Số ~20 ms / Coral TPU trong bài báo?

**Trả lời:** Đó là số **Zhao et al., arXiv:2404.19108** (MobileUNet ~20 ms trên RTX 2060M @ 640×480; ~266 ms trên Coral TPU) — **không phải** đo của nhóm. Đo nhóm: RTX 5070, 1024×683, ~34 ms CoG / ~60 ms CNN. Hình minh họa ghi «Nguồn: Zhao et al.».

### 15. Sai số / thời gian lần demo này?

**Trả lời:** Đọc đúng số trên ô KPI sau lần chạy hiện tại. Không lấy số nhớ. Ô còn `--` → «chưa kiểm được trên lần chạy này».

### 16. Star tracker có GSD mét không? (câu mẹo)

**Trả lời:** Không. GSD mét là ảnh mặt đất khoảng cách hữu hạn. Sao coi như vô cực góc; sản phẩm là hướng / quaternion.

### 17. Catalog? Cần tên sao không?

**Trả lời:** Yale BSC5, V ≤ 6. Khớp theo góc và ID catalog, không theo tên chòm sao.

### 18. Nguồn mã / giấy phép?

**Trả lời:** Tham khảo công bố và mã mở (ESA tetra3 Apache-2.0, UW LOST MIT, toán QUEST/K-vector đã công bố). Tái hiện toán đã công bố; không copy mã NOSA. Chi tiết trong thông báo bên thứ ba của repo.

### 19. Đổi máy ảnh thì sao?

**Trả lời:** Nhập đúng tiêu cự mm và cạnh pixel µm của đúng file. Không dùng «tương đương 35 mm» để giải. Ảnh núi dùng 4,2 mm / 4,1 µm theo mẫu LOST.

### 20. Vì sao Seed 42?

**Trả lời:** Cùng seed → cùng khung mô phỏng / ground truth, dễ đối chiếu giữa các lần chạy và với BGK.

---

## Không được nói

1. Không nêu VinAI, Alvium, IMX, Schneider, Jetson, 8U, điểm số công ty cũ.  
2. Không gán GSD mét cho star tracker; không gọi đây là thiết bị bay.  
3. Không nói «CNN luôn tốt hơn» — sim sạch và lóa mạnh: CoG thắng RMSE.  
4. Không gọi ảnh núi là ảnh nhóm chụp — là mẫu LOST công bố.  
5. Không bịa số / tên người ngoài hồ sơ — thiếu thì «chưa kiểm được».
