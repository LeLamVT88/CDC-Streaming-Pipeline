---
name: local-deploy-stack
description: >-
	Chuẩn hóa cấu hình Docker Compose cho môi trường local gồm MySQL, Postgres,
	pgAdmin, Kafka, Kafka UI và Airflow để chạy ổn định, dễ debug.
---

# Local deploy stack

## When to use

- Thêm hoặc chỉnh sửa service trong local environment.
- Đổi cổng, volume, credentials hoặc dependency service.
- Cập nhật tài liệu vận hành ở `deploy/README.md`.

## Required artifact

Các thay đổi hạ tầng local phải nằm trong:

```
deploy/docker-compose.yml
deploy/README.md
```

## Compose rules

- `deploy/docker-compose.yml` là nguồn cấu hình duy nhất cho local stack.
- Mỗi service cần `container_name` rõ ràng và `depends_on` hợp lý.
- Cổng public phải tránh xung đột và được ghi trong README.
- Service có dữ liệu trạng thái phải dùng named volume.
- Không hardcode bí mật production trong compose local.

## Default policy

- Giữ default cổng: MySQL `3306`, pgAdmin `5050`, Kafka `9092`, Kafka UI `8085`, Airflow `8080`.
- Dùng named volume cho MySQL, Postgres, Kafka.
- Giữ Airflow dùng `LocalExecutor` cho môi trường dev.

## Validation checklist

- [ ] `docker compose config` chạy thành công.
- [ ] `docker compose up -d` khởi tạo đầy đủ service.
- [ ] UI truy cập được: Airflow, pgAdmin, Kafka UI.
- [ ] README khớp với port và credential hiện tại.
- [ ] Không có service thiếu dependency bắt buộc.
