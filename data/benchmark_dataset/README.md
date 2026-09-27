# Ảnh giả lập để chấm

Các báo cáo và file kết quả cũ đã được gỡ. Sinh lại theo camera demo hiện tại nếu cần một bộ mới:

```text
python scripts/generate_benchmark_dataset.py --mode fast --limit 8
python scripts/benchmark_stored_dataset.py --smoke
```

Quaternion trong JSON cạnh ảnh là tư thế lúc phơi. Bộ giải không đọc JSON đó.
