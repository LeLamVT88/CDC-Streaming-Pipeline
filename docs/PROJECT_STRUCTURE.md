# Giải thích code — `scripts/` và `spark_jobs/`

Tài liệu mô tả vai trò từng file Python và shell trong hai thư mục này.

## Quan hệ giữa hai folder

```
scripts/
  pipeline.py ──────────────┬──► spark_jobs/silver_transforms.py
  inspect.py                │         └── silver_utils.py
  ingestion/seed_to_mysql.py│
  shell/pipeline.sh ────────┼──► spark_jobs/kafka_to_bronze.py
                            │         └── silver_utils.py
                            └──► (gọi pipeline.py, inspect.py, seed)
```

- **`scripts/`**: điều phối, CLI, seed MySQL, kiểm tra dữ liệu.
- **`spark_jobs/`**: logic Spark (đọc/ghi parquet, clean silver, consume Kafka).

---

## `spark_jobs/`

### `silver_utils.py`

Helper dùng chung cho mọi job silver và kafka.

| Hàm | Việc làm |
|-----|----------|
| `get_spark(app_name, kafka=False)` | Tạo SparkSession local. Nếu `kafka=True` thêm package `spark-sql-kafka` để đọc topic. |
| `read_layer(spark, path)` | Đọc bronze/silver: **parquet** (path local) hoặc **delta** (path bắt đầu `dbfs:`). |
| `write_layer(df, path, partition_cols)` | Ghi parquet (overwrite) hoặc delta có partition tùy chọn. Trả về số dòng. |
| `deduplicate(df, partition_cols)` | Giữ 1 bản ghi mới nhất theo key, sort theo `_processing_timestamp` desc. |
| `add_metadata(df)` | Thêm cột `_silver_processed_at` (timestamp lúc chạy silver). |

**Lưu ý:** `deduplicate` cần bronze có cột `_processing_timestamp` (do `pipeline.py` thêm khi load CSV).

---

### `silver_transforms.py`

Chứa **toàn bộ logic clean** cho silver layer. Mỗi hàm nhận `(spark, input_path, output_path)`.

#### `clean_customers(spark, input_path, output_path)`

| Bước | Mô tả |
|------|--------|
| Đọc bronze | `read_layer` |
| Lọc | Bỏ dòng `customer_id` null |
| Chuẩn hóa chuỗi | Trim id, unique_id, zip; `lower(city)`, `upper(state)` |
| Fill null | `customer_unique_id` rỗng → dùng `customer_id`; city/state null → `unknown` / `UNKNOWN` |
| Validate zip | Chỉ giữ 5 chữ số, không hợp lệ → `00000` |
| Dedupe | Theo `customer_id` |
| Ghi silver | `data/silver/customers` (parquet) |

#### `clean_orders(spark, input_path, output_path)`

| Bước | Mô tả |
|------|--------|
| Lọc | `order_id`, `customer_id` không null |
| Chuẩn hóa | Trim id; `lower(order_status)` |
| Timestamp | Parse 5 cột thời gian format `yyyy-MM-dd HH:mm:ss` |
| Status | Chỉ giữ status trong `VALID_STATUS`, còn lại → `unknown` |
| Tính toán | `delivery_delay_days` = ngày giao thực tế − ngày giao dự kiến |
| Dedupe | Theo `order_id` |
| Ghi silver | `data/silver/orders` |

#### `clean_order_items(spark, input_path, output_path)`

| Bước | Mô tả |
|------|--------|
| Lọc | `order_id`, `order_item_id` không null; product/seller không rỗng |
| Timestamp | `shipping_limit_date` |
| Giá | `price` > 0 (round 2 số); `freight_value` ≥ 0; `total_item_value` = price + freight |
| Dedupe | Theo `order_id` + `order_item_id` |
| Ghi silver | `data/silver/order_items` |

---

### `kafka_to_bronze.py`

Đưa message CDC từ Kafka vào bronze dạng **raw** (chưa parse Debezium).

| Thành phần | Mô tả |
|------------|--------|
| `TOPICS` | 3 topic `cdc.app.olist_*` → path tương ứng trong `data/bronze/` |
| `consume_batch(...)` | Spark Structured Streaming đọc topic ~30s, ghi parquet + checkpoint |
| Output schema | `json_value` (string), `kafka_timestamp` |
| `consume_all_topics(spark)` | Chạy lần lượt 3 topic, trả tổng số record |

**Lưu ý:** Bronze từ file này **không** dùng trực tiếp cho `clean_*` — silver cần cột business (`customer_id`, …) như bronze tạo từ CSV trong `pipeline.py`.

---

## `scripts/`

### `pipeline.py`

**Entry chính** chạy pipeline Spark.

| Hàm / mode | Việc làm |
|------------|----------|
| `load_seed_to_bronze(spark)` | Đọc 3 CSV trong `db/seed/`, thêm `_processing_timestamp`, ghi `data/bronze/olist_*` |
| `run_silver(spark)` | Gọi `clean_customers`, `clean_orders`, `clean_order_items` |
| `show_silver_stats(spark)` | In số dòng mỗi bảng silver |
| `--mode silver` (mặc định) | CSV → bronze → silver → stats |
| `--mode cdc` | Tùy chọn seed MySQL, consume Kafka → bronze; **không** chạy silver (cảnh báo raw JSON) |
| `--seed-mysql` | Với mode `cdc`: gọi `import_seed_data()` trước khi consume Kafka |

**Chạy:**

```bash
python scripts/pipeline.py --mode silver
python scripts/pipeline.py --mode cdc --seed-mysql
```

---

### `inspect.py`

Công cụ kiểm tra sau khi chạy pipeline (không transform dữ liệu).

| Hàm | Việc làm |
|-----|----------|
| `show_mysql()` | Liệt kê bảng + `COUNT(*)` trong database `app` |
| `show_parquet_layer(...)` | Đọc bronze/silver parquet, in số dòng và tên cột |
| `validate_silver(spark)` | Metrics DQ: null id, unknown status/city, giá trung bình, … |
| `show_sample(spark)` | In 3 dòng mẫu từ `data/silver/customers` |

| Flag | Ý nghĩa |
|------|---------|
| `--validate` | Bật phần data quality silver |
| `--skip-mysql` | Chỉ xem bronze/silver, bỏ qua MySQL |

---

### `ingestion/seed_to_mysql.py`

Nạp dữ liệu nguồn vào MySQL (phục vụ CDC / Debezium).

| Hàm | Việc làm |
|-----|----------|
| `import_seed_data()` | Đọc mọi `*.csv` trong `db/seed/`, ghi vào MySQL `app` (tên bảng = tên file). Chunk 50k dòng. Bảng đầu `replace`, các chunk sau `append`. |

Không dùng Spark — chỉ pandas + SQLAlchemy.

---

### `shell/pipeline.sh`

Wrapper bash gọi các bước trên (từ root: `./pipeline.sh <lệnh>`).

| Lệnh | Gọi tới |
|------|---------|
| `setup` | Tạo `.venv`, pip install |
| `start` / `stop` | Docker compose |
| `seed` | `scripts/ingestion/seed_to_mysql.py` |
| `deploy-connector` | REST API Kafka Connect (Debezium) |
| `silver` / `pipeline` | `scripts/pipeline.py --mode silver` |
| `cdc` | `scripts/pipeline.py --mode cdc` (+ args) |
| `inspect` | `scripts/inspect.py` (+ args) |
| `clean` | Xóa `data/bronze`, `data/silver`, `checkpoints` |
| `full-setup` | setup + start + seed + deploy-connector |

---

## Luồng code khi chạy Silver (thường dùng)

```
./pipeline.sh silver
    └── scripts/pipeline.py --mode silver
            ├── load_seed_to_bronze()
            │       └── spark.read.csv → data/bronze/olist_*
            └── run_silver()
                    ├── spark_jobs.clean_customers()
                    ├── spark_jobs.clean_orders()
                    └── spark_jobs.clean_order_items()
                            └── silver_utils: read_layer → transform → write_layer
```

Output: `data/silver/customers`, `orders`, `order_items`.

---

## File nào sửa khi mở rộng?

| Nhu cầu | File sửa |
|---------|----------|
| Thêm rule clean cột | `spark_jobs/silver_transforms.py` |
| Đổi cách đọc/ghi parquet | `spark_jobs/silver_utils.py` |
| Thêm bảng mới vào pipeline | `silver_transforms.py` + `DATASETS` trong `pipeline.py` + `LAYER_ITEMS` trong `inspect.py` |
| Parse Debezium → bronze có schema | Thêm module mới trong `spark_jobs/` hoặc mở rộng `kafka_to_bronze.py` |
| Thêm bước orchestration | `scripts/pipeline.py` |
| Lệnh CLI mới | `scripts/shell/pipeline.sh` |
