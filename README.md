# Star tracker

Demo trên laptop (Trường Đại học Bách khoa, Đại học Đà Nẵng — Khoa Công nghệ thông tin): từ ảnh bầu trời sao ra quaternion hướng camera. Đường ống mặc định là **centroid (trọng tâm) → Pyramid (Mortari) / K-vector → Wahba (SVD hoặc QUEST)**. Đầu ra là quaternion J2000, **4 × float32 = 16 byte**.

Tùy chọn: centroid CNN theo trọng số công khai MobileUNet của Zhao và cộng sự (arXiv:2404.19108), không huấn luyện lại. Nếu thiếu trọng số hoặc suy luận lỗi thì quay về trọng tâm cổ điển.

Camera trong demo là một **máy ảnh tĩnh phổ thông**: cảm biến cỡ APS-C khoảng 24 megapixel và ống kính tiêu cự **50 mm**. Không ghi tên cảm biến và không ghi tên ống kính.

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

## Thuật toán

1. **Centroid** — mặc định: nền theo khối, ngưỡng theo độ lệch, opening nhị phân, connected components, trọng tâm cửa sổ. Tùy chọn: MobileUNet công khai (Zhao et al.) + trilateration (`centroid_backend=cnn`).
2. **Nhận dạng sao** — góc giữa các sao, bảng **K-vector**, **Pyramid** và các sao còn lại. Không khớp chòm sao văn hóa.
3. **Wahba** — SVD hoặc QUEST ra quaternion. `q` và `−q` là cùng một tư thế.

Bảng góc mặc định phủ tới **30,5°** (đường chéo trường nhìn demo). Ảnh rộng hơn thì lần đầu dựng bảng mới và lưu trong `data/catalogs/`.

Hằng số electron, nhiễu đọc và dòng tối trong `config/camera_specs.json` có `"assumption": true`. Đó là số để mô phỏng, không phải số đo của một máy ảnh.

## Chạy

```text
pip install -r requirements.txt
python demo_star_tracker.py --mode fast --seed 42 --lookup --no-show
python app.py
python scripts/benchmark_centroid_cnn.py --n 500
```

Trọng số CNN công khai (không huấn luyện lại):

```text
third_party/cnn_star_centroid/saved_models/MobileUNet_B10_50.pt
```

Nguồn: https://github.com/HongruiZhao/CNNStarDetectCentroid — bài arXiv:2404.19108.

`app.py` mở giao diện tại `http://127.0.0.1:8765/`. Nút sinh ảnh vẽ bầu trời bằng `SkySimulator` rồi giải quaternion. Catalog mặc định là Yale BSC5, cấp sáng V ≤ 6.

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
