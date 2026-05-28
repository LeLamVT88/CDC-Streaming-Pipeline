# Docker

Docker được dùng để chạy Airflow orchestration cho pipeline Medallion Lakehouse.

## Danh sách file

| File | Mục đích |
| --- | --- |
| `docker-compose.yml` | Khởi tạo Postgres metadata DB, Airflow init, Airflow webserver và Airflow scheduler. |
| `airflow/Dockerfile` | Build image Airflow có Java và các thư viện cần thiết cho pipeline. |
| `airflow/requirements.txt` | Danh sách Python dependencies cho Airflow container, gồm `boto3`, `pandas`, `pyarrow`, `pyspark`, AWS provider và `PyYAML`. |

## Các service chính

| Service | Mục đích |
| --- | --- |
| `postgres` | Metadata database cho Airflow. |
| `airflow-init` | Migrate database và tạo user admin. |
| `airflow-webserver` | Giao diện Airflow tại `http://localhost:8080`. |
| `airflow-scheduler` | Scheduler chạy các DAG. |

## Ghi chú

- Docker không phải nơi lưu data lake. Data lake nằm trên S3.
- Các thư mục `dags`, `scripts`, `configs`, `db` và `data` được mount vào Airflow container.
- Thư mục `~/.aws` được mount read-only để container có thể dùng AWS credentials local.
