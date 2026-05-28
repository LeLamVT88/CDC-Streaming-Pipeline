# Silver Layer

Silver đọc dữ liệu Parquet từ Bronze, thực hiện clean/standardize/deduplicate và ghi kết quả ra S3 Silver.

## Danh sách file

| File | Mục đích |
| --- | --- |
| `bronze_to_silver.py` | Spark job chính. Đọc Parquet từ Bronze, clean từng bảng và ghi Parquet ra Silver. |
| `standardize_schema.py` | Helper chuẩn hóa tên cột, sửa typo của dataset, trim string, cast timestamp/int/double và chuẩn hóa zip code. |

## Luồng xử lý

```text
s3://olist-lakehouse-data/bronze/<table>/
  -> Spark clean/transform
  -> s3://olist-lakehouse-data/silver/<table>/
```

## Cách chạy

Chạy bằng cấu hình mặc định trong `configs/app_config.yaml`:

```bash
AWS_ACCESS_KEY_ID=$(.venv/bin/aws configure get aws_access_key_id) \
AWS_SECRET_ACCESS_KEY=$(.venv/bin/aws configure get aws_secret_access_key) \
AWS_DEFAULT_REGION=ap-southeast-1 \
spark-submit \
  --packages org.apache.hadoop:hadoop-aws:3.4.1 \
  --conf spark.hadoop.fs.s3a.endpoint=s3.ap-southeast-1.amazonaws.com \
  scripts/silver/bronze_to_silver.py
```

Override path khi cần test local:

```bash
spark-submit scripts/silver/bronze_to_silver.py \
  --bronze-path data/bronze_test \
  --silver-path data/silver_test
```

## Kết quả

Sau khi chạy, dữ liệu Silver sẽ nằm ở:

```text
s3://olist-lakehouse-data/silver/<table_name>/*.parquet
```
