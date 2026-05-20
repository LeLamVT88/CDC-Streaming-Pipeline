# Demo pipeline đến Silver layer

Hướng dẫn chạy end-to-end trên máy local: từ Docker + MySQL + Kafka đến **Silver** (dữ liệu đã làm sạch).

**Thời gian ước tính:** 15–25 phút (lần đầu có thể lâu hơn do tải Docker image / Spark JAR).

---

## Yêu cầu

- macOS / Linux
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) đang chạy
- Python 3.11+ (khuyến nghị 3.11 hoặc 3.12; tránh 3.14 nếu PySpark báo lỗi lạ)
- Java 8+ (cho Spark)
- Dữ liệu CSV trong `db/seed/` (đã có sẵn trong project)

---

## Kiến trúc demo

```
┌─────────────┐     ┌────────┐     ┌───────────────┐     ┌────────┐     ┌────────┐
│ db/seed CSV │────►│ MySQL  │────►│ Debezium/   │────►│ Kafka  │     │ (tùy   │
└─────────────┘     └────────┘     │ Kafka Connect│     └────────┘     │ chọn)  │
       │                            └───────────────┘                  └────────┘
       │
       └──────────────────► Bronze (parquet) ──► Silver (parquet)
                            scripts/pipeline.py --mode silver
```

**Demo chính (Silver):** dùng CSV → Bronze → Silver (không phụ thuộc format Kafka raw).

**Phụ (CDC):** MySQL → Kafka qua Debezium để quan sát topic trên Kafka UI.

---

## Bước 0 — Clone & vào project

```bash
cd /Users/tunglam/CDC-Streaming-Pipeline
```

---

## Bước 1 — Python environment

```bash
./pipeline.sh setup
source .venv/bin/activate
```

Kỳ vọng: `✓ Venv exists` hoặc `✓ Venv created`.

---

## Bước 2 — Khởi động Docker

```bash
./pipeline.sh start
```

Đợi **1–2 phút**. Kiểm tra:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Cần thấy: `mysql`, `kafka`, `kafka-connect`, `schema-registry` đều **Up**.

| UI | URL |
|----|-----|
| Kafka UI | http://localhost:8085 |
| phpMyAdmin | http://localhost:8082 (user/pass: `root` / `root`) |

---

## Bước 3 — Nạp dữ liệu vào MySQL

```bash
./pipeline.sh seed
```

Mất khoảng **2–5 phút**. Kiểm tra:

```bash
docker exec mysql mysql -uroot -proot -e \
  "USE app; SELECT COUNT(*) FROM olist_customers_dataset;"
```

Kỳ vọng: ~**99,441** dòng.

---

## Bước 4 — Deploy Debezium (CDC)

```bash
./pipeline.sh deploy-connector
```

Kỳ vọng:

- `✓ Kafka Connect is ready`
- `✓ Connector deployed (HTTP 201)`
- `"state": "RUNNING"` trong JSON status

Nếu Kafka Connect crash sau khi từng reset topic:

```bash
# Chỉ khi Connect không lên được — tạo lại topic compact thủ công:
docker stop kafka-connect
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --delete --topic cdc-connect-offsets --if-exists
docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --topic cdc-connect-offsets --partitions 1 --replication-factor 1 \
  --config cleanup.policy=compact
# (lặp tương tự cho cdc-connect-configs, cdc-connect-status)
docker start kafka-connect
./pipeline.sh deploy-connector
```

Trên **Kafka UI** (http://localhost:8085) kiểm tra topic:

- `cdc.app.olist_customers_dataset`
- `cdc.app.olist_orders_dataset`
- `cdc.app.olist_order_items_dataset`

---

## Bước 5 — Silver (CSV → Bronze → Silver)

Đây là bước **hoàn tất demo Silver**.

```bash
./pipeline.sh silver
```

Hoặc:

```bash
source .venv/bin/activate
export PYTHONPATH="/Users/tunglam/CDC-Streaming-Pipeline:$PYTHONPATH"
python scripts/pipeline.py --mode silver
```

**Lưu ý:** Không nhấn Ctrl+C khi đang đọc CSV (có thể im lặng 10–30 giây ở file đầu).

Kỳ vọng cuối:

```
✓ Customers: 99,441 records
✓ Orders: 99,441 records
✓ Order Items: 112,650 records
```

Output nằm tại:

- `data/bronze/olist_*_dataset/`
- `data/silver/customers/`, `orders/`, `order_items/`

---

## Bước 6 — Kiểm tra kết quả

```bash
./pipeline.sh inspect --validate
```

Hoặc:

```bash
python scripts/inspect.py --validate
```

Kỳ vọng phần Silver:

| Bảng | Số dòng |
|------|---------|
| customers | ~99,441 |
| orders | ~99,441 |
| order_items | ~112,650 |

Xem file parquet:

```bash
ls data/silver/customers/
ls data/silver/orders/
ls data/silver/order_items/
```

---

## (Tùy chọn) Bước 7 — Kafka → Bronze

Chỉ để thử luồng streaming CDC (bronze = raw JSON, **chưa** dùng cho silver):

```bash
./pipeline.sh cdc
```

Hoặc kèm seed MySQL:

```bash
./pipeline.sh cdc --seed-mysql
```

---

## (Tùy chọn) Xóa data local chạy lại

Chỉ xóa parquet trên máy (giữ MySQL/Kafka):

```bash
./pipeline.sh clean
./pipeline.sh silver
```

---

## Tóm tắt lệnh một lần

```bash
cd /Users/tunglam/CDC-Streaming-Pipeline
./pipeline.sh setup
source .venv/bin/activate
./pipeline.sh start
./pipeline.sh seed
./pipeline.sh deploy-connector
# đợi connector RUNNING
./pipeline.sh silver
./pipeline.sh inspect --validate
```

---

## Xử lý lỗi thường gặp

| Triệu chứng | Cách xử lý |
|-------------|------------|
| `Connection refused` :8083 | `./pipeline.sh start`, đợi thêm; `docker logs kafka-connect --tail 50` |
| Connector không RUNNING | Xem log Connect; kiểm tra MySQL đã seed |
| `Py4JNetworkError` + `^C` | Đã interrupt — chạy lại, không Ctrl+C |
| `inspect` lỗi MySQL | Bỏ qua: `./pipeline.sh inspect --skip-mysql` (nếu chỉ cần xem silver) |
| Silver treo đọc CSV | Đợi thêm; thử Python 3.12 cho venv |

---

## Silver layer làm gì?

| Bảng | Một số bước clean |
|------|-------------------|
| **customers** | Trim, chuẩn hóa city/state, fill null, validate zip 5 số, dedupe theo `customer_id` |
| **orders** | Parse timestamp, chuẩn hóa `order_status`, tính `delivery_delay_days`, dedupe theo `order_id` |
| **order_items** | Làm sạch giá, `freight_value`, `total_item_value`, dedupe theo `order_id` + `order_item_id` |

Mỗi bảng có thêm cột `_silver_processed_at`.

Chi tiết code: `spark_jobs/silver_transforms.py`.

---

## Bước tiếp theo (ngoài demo)

- Parse Debezium JSON → bronze có schema → silver từ Kafka
- Gold layer (join / aggregate)
- Airflow DAG schedule job trong `airflows/dags/`

Xem thêm cấu trúc file: [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md).
