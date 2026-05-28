# Cấu hình dự án

Thư mục này chứa các file cấu hình dùng chung cho toàn bộ pipeline Medallion Lakehouse.

## Danh sách file

| File | Mục đích |
| --- | --- |
| `app_config.yaml` | File cấu hình chính của project: bucket, region, đường dẫn S3 cho Bronze/Silver/Gold, cấu hình Athena, Spark và danh sách bảng Olist cần xử lý. |
| `aws.yaml` | Chứa thông tin AWS không nhạy cảm như region và bucket. Không lưu access key hoặc secret key trong file này. |
| `table.yaml` | Khai báo danh sách bảng và khóa chính logic của từng bảng. |
| `airflow.yaml` | Khai báo thông tin orchestration: DAG id và mapping task với script tương ứng. |

## Ghi chú

- Không lưu AWS access key trong repository.
- Credentials nên được cấu hình bằng `~/.aws/credentials`, IAM role hoặc environment variables.
- Các script đọc cấu hình chính thông qua `scripts/common/config.py`.
