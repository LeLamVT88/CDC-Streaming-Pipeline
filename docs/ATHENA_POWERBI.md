# Athena and Power BI handoff

The pipeline writes curated parquet files for `silver`, `mapping`, and `gold`. Athena can expose those files as external tables, and Power BI can connect to Athena through the Amazon Athena ODBC driver.

## Configure S3 output

For AWS-backed runs, set these before running Spark:

```bash
export DWH_BRONZE_PATH=s3a://your-bucket/dwh/bronze
export DWH_CLEAN_PATH=s3a://your-bucket/dwh/clean
export DWH_SILVER_PATH=s3a://your-bucket/dwh/silver
export DWH_MAPPING_PATH=s3a://your-bucket/dwh/mapping
export DWH_GOLD_PATH=s3a://your-bucket/dwh/gold
export DWH_ATHENA_LOCATION=s3://your-bucket/dwh
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=ap-southeast-1
```

Or edit `configs/app_config.yaml`:

```yaml
paths:
  bronze: s3a://your-bucket/dwh/bronze
  clean: s3a://your-bucket/dwh/clean
  silver: s3a://your-bucket/dwh/silver
  mapping: s3a://your-bucket/dwh/mapping
  gold: s3a://your-bucket/dwh/gold

aws:
  athena_database: s3_lakehouse_dwh
  athena_s3_location: s3://your-bucket/dwh
```

## Generate Athena DDL

After the parquet layers exist:

```bash
./pipeline.sh athena-ddl
```

Run the generated SQL from `docs/athena_lakehouse_ddl.sql` in Athena. Table names are prefixed with the layer, for example `silver_orders`, `mapping_fct_order_items`, and `gold_sales_daily`.

## Connect Power BI

1. Install the Amazon Athena ODBC driver.
2. Create a DSN that points to the AWS region and S3 query result location.
3. In Power BI Desktop, choose Amazon Athena or ODBC.
4. Select the `s3_lakehouse_dwh` database and import or direct-query the gold marts.

