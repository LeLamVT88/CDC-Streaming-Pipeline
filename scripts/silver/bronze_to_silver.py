"""Clean bronze data and write the silver layer as parquet.

Production flow:
    spark-submit scripts/silver/bronze_to_silver.py \
      --bronze-path s3a://bucket/bronze \
      --silver-path s3a://bucket/silver
"""

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    current_timestamp,
    datediff,
    lit,
    lower,
    round,
    row_number,
    trim,
    upper,
    when,
)
from pyspark.sql.window import Window

try:
    from standardize_schema import standardize_schema
except ImportError:
    from scripts.silver.standardize_schema import standardize_schema

try:
    from scripts.common.config import get_nested, load_yaml
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from scripts.common.config import get_nested, load_yaml

CONFIG = load_yaml()

VALID_ORDER_STATUS = [
    "pending",
    "processing",
    "shipped",
    "delivered",
    "canceled",
    "unavailable",
    "on_return",
    "returned",
]

VALID_PAYMENT_TYPES = [
    "credit_card",
    "boleto",
    "voucher",
    "debit_card",
    "not_defined",
]


def build_spark(app_name="OlistSilverClean"):
    spark = SparkSession.builder.appName(app_name).master("local[*]").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def clean_location_columns(df, city_col, state_col):
    if city_col in df.columns:
        df = df.withColumn(city_col, lower(trim(col(city_col))))
    if state_col in df.columns:
        df = df.withColumn(state_col, upper(trim(col(state_col))))
    return df


def clean_orders(df):
    if "order_status" in df.columns:
        df = df.withColumn("order_status", lower(trim(col("order_status"))))
        df = df.withColumn(
            "order_status",
            when(col("order_status").isin(VALID_ORDER_STATUS), col("order_status")).otherwise("unknown"),
        )

    if {"order_delivered_customer_date", "order_estimated_delivery_date"}.issubset(df.columns):
        df = df.withColumn(
            "delivery_delay_days",
            when(
                col("order_delivered_customer_date").isNotNull()
                & col("order_estimated_delivery_date").isNotNull(),
                datediff(col("order_delivered_customer_date"), col("order_estimated_delivery_date")),
            ),
        )
    return df


def clean_money_columns(df):
    for column_name in ["price", "freight_value"]:
        if column_name in df.columns:
            minimum = 0 if column_name == "freight_value" else 0.01
            df = df.withColumn(
                column_name,
                when(col(column_name) >= minimum, round(col(column_name), 2)).otherwise(lit(0.0)),
            )

    if {"price", "freight_value"}.issubset(df.columns):
        df = df.withColumn("total_item_value", round(col("price") + col("freight_value"), 2))

    if "payment_installments" in df.columns:
        df = df.withColumn(
            "payment_installments",
            when(col("payment_installments") >= 0, col("payment_installments")).otherwise(lit(0)),
        )

    if "payment_value" in df.columns:
        df = df.withColumn(
            "payment_value",
            when(col("payment_value") >= 0, round(col("payment_value"), 2)).otherwise(lit(0.0)),
        )
    return df


def clean_positive_numbers(df):
    for column_name in [
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]:
        if column_name in df.columns:
            df = df.withColumn(column_name, when(col(column_name) >= 0, col(column_name)).otherwise(lit(0)))
    return df


def clean_text_values(df):
    city_state_pairs = [
        ("customer_city", "customer_state"),
        ("geolocation_city", "geolocation_state"),
        ("seller_city", "seller_state"),
    ]
    for city_col, state_col in city_state_pairs:
        df = clean_location_columns(df, city_col, state_col)

    for column_name in ["product_category_name", "product_category_name_english"]:
        if column_name in df.columns:
            df = df.withColumn(column_name, lower(trim(col(column_name))))

    if "payment_type" in df.columns:
        df = df.withColumn("payment_type", lower(trim(col("payment_type"))))
        df = df.withColumn(
            "payment_type",
            when(col("payment_type").isin(VALID_PAYMENT_TYPES), col("payment_type")).otherwise("unknown"),
        )

    return df


def fill_nulls(df):
    text_defaults = {
        "customer_city": "unknown",
        "customer_state": "UNKNOWN",
        "seller_city": "unknown",
        "seller_state": "UNKNOWN",
        "product_category_name": "unknown",
        "product_category_name_english": "unknown",
        "review_comment_title": "",
        "review_comment_message": "",
    }

    for column_name, default_value in text_defaults.items():
        if column_name in df.columns:
            df = df.withColumn(
                column_name,
                when(col(column_name).isNull(), lit(default_value)).otherwise(col(column_name)),
            )

    if {"customer_unique_id", "customer_id"}.issubset(df.columns):
        df = df.withColumn(
            "customer_unique_id",
            when(col("customer_unique_id").isNull(), col("customer_id")).otherwise(col("customer_unique_id")),
        )

    return df


def filter_bad_rows(df):
    id_columns = [name for name in df.columns if name.endswith("_id") or name in {"review_id"}]
    for column_name in id_columns:
        df = df.filter(col(column_name).isNotNull())

    if {"geolocation_lat", "geolocation_lng"}.issubset(df.columns):
        df = df.filter(col("geolocation_lat").isNotNull() & col("geolocation_lng").isNotNull())

    if "review_score" in df.columns:
        df = df.withColumn("review_score", when(col("review_score").between(1, 5), col("review_score")))

    return df


def dedup_keys(df):
    columns = set(df.columns)
    rules = [
        ({"order_id", "order_item_id"}, ["order_id", "order_item_id"]),
        ({"order_id", "payment_sequential"}, ["order_id", "payment_sequential"]),
        (
            {"geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"},
            ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng"],
        ),
        ({"product_category_name", "product_category_name_english"}, ["product_category_name"]),
        ({"review_id"}, ["review_id"]),
        ({"order_id"}, ["order_id"]),
        ({"customer_id"}, ["customer_id"]),
        ({"product_id"}, ["product_id"]),
        ({"seller_id"}, ["seller_id"]),
    ]
    for required_columns, keys in rules:
        if required_columns.issubset(columns):
            return keys
    return df.columns


def deduplicate(df):
    keys = dedup_keys(df)
    if "_processing_timestamp" not in df.columns:
        return df.dropDuplicates(keys)

    window = Window.partitionBy(*keys).orderBy(col("_processing_timestamp").desc())
    return df.withColumn("_rn", row_number().over(window)).filter(col("_rn") == 1).drop("_rn")


def clean_table(df):
    df = standardize_schema(df)
    df = clean_text_values(df)
    df = fill_nulls(df)
    df = filter_bad_rows(df)
    df = clean_orders(df)
    df = clean_money_columns(df)
    df = clean_positive_numbers(df)
    df = deduplicate(df)
    return df.withColumn("_silver_processed_at", current_timestamp())


def read_table(spark, path):
    return spark.read.parquet(str(path))


def local_table_inputs(base_path):
    base = Path(base_path)
    paths = [path for path in sorted(base.glob("*")) if path.is_dir()]
    return [(path.name, path) for path in paths if not path.name.startswith("_")]


def s3_table_inputs(base_path, table_names):
    if table_names:
        return [(table_name, f"{base_path.rstrip('/')}/{table_name}") for table_name in table_names]

    parsed = urlparse(base_path.replace("s3a://", "s3://", 1))
    if parsed.scheme != "s3":
        raise ValueError("--tables is required when bronze path is not local or s3/s3a")

    import boto3

    bucket = parsed.netloc
    prefix = parsed.path.strip("/")
    if prefix:
        prefix = f"{prefix}/"

    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    table_names = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for item in page.get("CommonPrefixes", []):
            table_names.append(item["Prefix"].rstrip("/").split("/")[-1])

    if not table_names:
        raise FileNotFoundError(f"No bronze tables found under {base_path}")

    return [(table_name, f"{base_path.rstrip('/')}/{table_name}") for table_name in sorted(table_names)]


def table_inputs(bronze_path, table_names):
    if str(bronze_path).startswith(("s3://", "s3a://")):
        return s3_table_inputs(bronze_path, table_names)

    inputs = local_table_inputs(bronze_path)
    if table_names:
        wanted = set(table_names)
        inputs = [(name, path) for name, path in inputs if name in wanted]

    if not inputs:
        raise FileNotFoundError(f"No input tables found in {bronze_path}")

    return inputs


def clean_all_tables(spark, bronze_path, silver_path, table_names=None):
    inputs = table_inputs(bronze_path, table_names)

    results = {}
    for table_name, input_path in inputs:
        output_path = f"{silver_path.rstrip('/')}/{table_name}"
        print(f"Cleaning {input_path} -> {output_path}")

        cleaned_df = clean_table(read_table(spark, input_path))
        cleaned_df.write.mode("overwrite").parquet(str(output_path))
        results[table_name] = cleaned_df.count()
        print(f"  {results[table_name]:,} rows")

    return results


def parse_args():
    parser = argparse.ArgumentParser(description="Clean bronze parquet into silver parquet.")
    parser.add_argument(
        "--bronze-path",
        default=os.environ.get("BRONZE_PATH", get_nested(CONFIG, "s3", "bronze_uri", default="data/bronze")),
    )
    parser.add_argument(
        "--silver-path",
        default=os.environ.get("SILVER_PATH", get_nested(CONFIG, "s3", "silver_uri", default="data/silver")),
    )
    parser.add_argument("--tables", nargs="*", default=get_nested(CONFIG, "tables", default=None))
    return parser.parse_args()


def main():
    args = parse_args()

    spark = build_spark()
    try:
        clean_all_tables(spark, args.bronze_path, args.silver_path, args.tables)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
