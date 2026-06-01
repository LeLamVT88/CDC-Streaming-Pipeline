# Gold Layer

Gold reads the cleaned Silver Parquet tables, then writes dimensions, facts, and
analytical marts as Parquet.

## Flow

```text
s3://olist-lakehouse-data/silver/<olist_table>/
  -> Spark dimensions, facts, and marts
  -> s3://olist-lakehouse-data/gold/<gold_model>/
```

## Models

- Dimensions: `dim_customers`, `dim_geolocation`, `dim_products`,
  `dim_sellers`, `dim_dates`.
- Facts: `fact_orders`, `fact_order_items`, `fact_order_payments`,
  `fact_order_reviews`.
- Marts: `mart_sales_daily`, `mart_sales_by_customer_state`,
  `mart_product_category_performance`, `mart_seller_performance`,
  `mart_order_status_summary`.

## Run

Use the default S3 paths from `configs/app_config.yaml`:

```bash
AWS_ACCESS_KEY_ID=... \
AWS_SECRET_ACCESS_KEY=... \
AWS_DEFAULT_REGION=ap-southeast-1 \
spark-submit \
  --packages org.apache.hadoop:hadoop-aws:3.4.1 \
  scripts/gold/create_fact_table.py
```

Override the paths for a local or isolated test:

```bash
spark-submit scripts/gold/create_fact_table.py \
  --silver-path data/silver_test \
  --gold-path data/gold_test
```
