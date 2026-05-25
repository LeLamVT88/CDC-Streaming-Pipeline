# S3 Lakehouse DWH

Lakehouse-style DWH project built around S3/local object storage layers:

```text
bronze (raw CSV)
  -> clean
  -> silver
  -> mapping
  -> gold
```

Airflow orchestrates the core DWH. MySQL, Kafka, Debezium, and other CDC pieces are isolated under `sources/cdc` as an optional source adapter, so the lakehouse can later accept crawl data or other sources without changing the DWH core.

## Quick start

```bash
./pipeline.sh setup
./pipeline.sh validate
./pipeline.sh all --tables customers,orders,order_items
./pipeline.sh inspect --validate --tables customers,orders,order_items
```

Start Airflow:

```bash
./pipeline.sh start
```

Airflow: [http://localhost:8080](http://localhost:8080) with `admin/admin`.

## S3 output

Set layer paths to S3A before running Spark:

```bash
export DWH_BRONZE_PATH=s3a://your-bucket/dwh/bronze
export DWH_CLEAN_PATH=s3a://your-bucket/dwh/clean
export DWH_SILVER_PATH=s3a://your-bucket/dwh/silver
export DWH_MAPPING_PATH=s3a://your-bucket/dwh/mapping
export DWH_GOLD_PATH=s3a://your-bucket/dwh/gold
export AWS_DEFAULT_REGION=ap-southeast-1
```

Generate Athena DDL after data exists:

```bash
./pipeline.sh athena-ddl
```

## Optional CDC source

CDC is no longer part of the main DWH path. To run it as a source adapter:

```bash
./pipeline.sh setup-cdc
./pipeline.sh start-cdc
./pipeline.sh cdc --mode all
./pipeline.sh clean
./pipeline.sh silver
./pipeline.sh mapping
./pipeline.sh gold
```

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md), [docs/LOCAL_DEMO.md](docs/LOCAL_DEMO.md), and [docs/CDC_SOURCE.md](docs/CDC_SOURCE.md).

