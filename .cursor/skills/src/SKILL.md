---
name: spark-pipeline-jobs
description: >-
	Định nghĩa tiêu chuẩn phát triển job Spark cho pipeline ingest, clean, dim/fact,
	serving để dữ liệu đầu ra nhất quán và dễ bảo trì.
---

# Spark pipeline jobs

## When to use

- Tạo hoặc chỉnh sửa job trong `src/jobs/`.
- Điều chỉnh luồng chạy tổng trong `src/Pipeline.py`.
- Cập nhật logic schema, partition hoặc ghi dữ liệu serving.

## Required artifact

Tối thiểu phải cập nhật các file liên quan trực tiếp:

```
src/Pipeline.py
src/jobs/*.py
src/utils/config.py
src/utils/spark_utils.py
```

## Job rules

- Mỗi job chỉ nên có một nhiệm vụ chính (ingest/clean/build/validate/serve).
- Tái sử dụng hàm helper trong `src/utils/`, tránh lặp logic.
- Không hardcode đường dẫn; lấy từ cấu hình tập trung.
- Thay đổi schema phải đồng bộ với bước validate và serving.
- Thay đổi partition phải đánh giá tác động downstream.

## Default policy

- Ưu tiên transform theo DataFrame API để dễ theo dõi lineage.
- Dùng tên cột nhất quán từ clean đến serving.
- Bổ sung kiểm tra null/key trước khi ghi bảng dim/fact.

## Validation checklist

- [ ] Pipeline chạy thành công theo thứ tự ingest -> clean -> dim/fact -> serving.
- [ ] Không có đường dẫn hardcode ngoài config.
- [ ] Schema đầu ra đúng với kỳ vọng của bước sau.
- [ ] Partition output đúng naming convention hiện tại.
- [ ] Script debug/validate phản ánh đúng logic mới.
