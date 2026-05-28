# Bronze Layer

Bronze là layer đầu tiên trên S3. Dữ liệu từ các file CSV trong `db/seed` được chuyển sang định dạng Parquet và upload lên S3 Bronze.

## Danh sách file

| File | Mục đích |
| --- | --- |
| `upload_csv_to_bronze.py` | Đọc các file CSV trong seed, chia dữ liệu thành từng chunk, chuyển sang Parquet và upload lên `s3://<bucket>/bronze/<table>/part_*.parquet`. |

## Cách chạy

Chạy bằng cấu hình mặc định trong `configs/app_config.yaml`:

```bash
.venv/bin/python scripts/bronze/upload_csv_to_bronze.py
```

Override bucket hoặc prefix khi cần:

```bash
.venv/bin/python scripts/bronze/upload_csv_to_bronze.py \
  --bucket olist-lakehouse-data \
  --prefix bronze
```

## Kết quả

Sau khi chạy, dữ liệu Bronze sẽ nằm ở:

```text
s3://olist-lakehouse-data/bronze/<table_name>/part_0000.parquet
```
