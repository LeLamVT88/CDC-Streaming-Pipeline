---
name: data-artifact-management
description: >-
	Thiết lập quy tắc quản lý dữ liệu trong thư mục data nhằm đảm bảo tính toàn vẹn
	cho raw, clean, dim, fact và serving artifacts.
---

# Data artifact management

## When to use

- Thêm dữ liệu đầu vào mới vào khu vực raw.
- Cập nhật đường dẫn output của clean/dim/fact/serving.
- Điều chỉnh cấu trúc partition hoặc dọn dẹp dữ liệu cũ.

## Required artifact

Các thao tác dữ liệu phải tuân thủ cấu trúc:

```
data/raw/
data/clean/
data/dim/
data/fact/
data/serving/
```

## Data rules

- Chỉ đặt dữ liệu nguồn gốc trong `data/raw/`.
- Không chỉnh sửa thủ công file marker `_SUCCESS`.
- Output dẫn xuất phải ghi đúng domain (clean/dim/fact/serving).
- Giữ ổn định tên thư mục partition để không phá consumer.
- Không xóa partition khi chưa kiểm tra tác động downstream.

## Default policy

- Ưu tiên append theo cấu trúc partition chuẩn hiện có.
- Nếu cần rewrite dữ liệu, phải có bước validate sau ghi.
- Dùng naming rõ ràng, không viết tắt mơ hồ cho thư mục output.

## Validation checklist

- [ ] Dữ liệu raw và dữ liệu dẫn xuất không bị trộn lẫn vị trí.
- [ ] `_SUCCESS` được tạo đúng sau mỗi bước ghi thành công.
- [ ] Tên partition giữ tương thích với logic đọc hiện tại.
- [ ] Không có thay đổi vô tình vào dữ liệu serving đang dùng.
- [ ] Kết quả output khớp với cấu hình pipeline.
