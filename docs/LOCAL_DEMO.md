# Local demo

This path does not require Kafka or MySQL. It proves the full lakehouse shape with local CSV files.

```bash
./pipeline.sh setup
./pipeline.sh all --tables customers,orders,order_items,products,sellers,product_category_translation
./pipeline.sh inspect --validate --tables customers,orders,order_items,products,sellers,product_category_translation
```

Outputs:

```text
data/lakehouse/bronze/<source_table>/
data/lakehouse/clean/<target_table>/
data/lakehouse/silver/<target_table>/
data/lakehouse/mapping/<model_name>/
data/lakehouse/gold/<mart_name>/
```

## Airflow

Open Airflow and trigger the `s3_lakehouse_dwh` DAG. The DAG runs:

```text
validate_config
  -> bronze_from_csv
  -> clean_from_bronze
  -> silver_from_clean
  -> build_mapping
  -> build_gold
  -> generate_athena_ddl
```

## Athena and Power BI

Run:

```bash
./pipeline.sh athena-ddl
```

The generated SQL is written to `docs/athena_lakehouse_ddl.sql`.

