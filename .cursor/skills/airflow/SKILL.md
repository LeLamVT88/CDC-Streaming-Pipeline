---
name: airflow-pipeline-dag
description: >-
	Định nghĩa tiêu chuẩn cho DAG Airflow của customer pipeline để cấu trúc task,
	lịch chạy và cấu hình retry nhất quán, dễ vận hành.
---

# Airflow pipeline DAG

## When to use

- Tạo DAG mới trong `airflow/dags/`.
- Chỉnh sửa thứ tự task, schedule hoặc retry policy của DAG hiện có.
- Chuẩn hóa tên task và tham số runtime trước khi release.

## Required artifact

Mỗi thay đổi orchestration phải cập nhật đúng file DAG:

```
airflow/dags/Customer_Pipeline_dags.py
```

## DAG rules

- `dag_id` phải ổn định, viết thường và dùng dấu gạch dưới.
- `task_id` rõ nghĩa, duy nhất trong DAG, bám theo flow nghiệp vụ.
- Các tác vụ nặng phải chạy ở Spark job, không xử lý nặng trong scheduler.
- Cấu hình retry cần tường minh (`retries`, `retry_delay`) cho task quan trọng.
- `schedule` phải đồng bộ với thời điểm dữ liệu đầu vào sẵn sàng.

## Default policy

- Bật retry cho các bước ingest/serve để giảm lỗi tạm thời.
- Giữ `catchup` theo đúng yêu cầu vận hành (không đổi ngẫu nhiên).
- Hạn chế thay đổi `start_date` nếu không có lý do rõ ràng.

## Validation checklist

- [ ] DAG parse thành công trong môi trường local.
- [ ] `dag_id` và `task_id` không bị trùng.
- [ ] Dependency giữa các task không tạo vòng lặp.
- [ ] Lịch chạy phù hợp với SLA dữ liệu.
- [ ] Không có logic xử lý dữ liệu nặng trong file DAG.
