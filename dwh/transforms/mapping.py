"""Mapping-layer models that turn silver tables into conformed facts and dimensions."""

from __future__ import annotations

from typing import Callable

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, concat_ws, date_format, dayofmonth, lit, month, sha2, to_date, weekofyear, year

from dwh.config import layer_table_path
from dwh.io import read_layer, write_layer

MAPPING_MODELS = [
    "dim_customers",
    "dim_products",
    "dim_sellers",
    "dim_dates",
    "fct_orders",
    "fct_order_items",
]


def run_mapping_models(spark, config: dict, mode: str = "overwrite") -> dict[str, int]:
    results: dict[str, int] = {}
    builders: dict[str, Callable] = {
        "dim_customers": build_dim_customers,
        "dim_products": build_dim_products,
        "dim_sellers": build_dim_sellers,
        "dim_dates": build_dim_dates,
        "fct_orders": build_fct_orders,
        "fct_order_items": build_fct_order_items,
    }

    for name, builder in builders.items():
        try:
            df = builder(spark, config)
            path = layer_table_path(config, "mapping", name)
            results[name] = write_layer(df, path, mode=mode)
            print(f"[mapping] {name}: {results[name]:,} records")
        except Exception as exc:
            print(f"[mapping] {name}: skipped ({str(exc)[:180]})")
    return results


def build_dim_customers(spark, config: dict) -> DataFrame:
    df = _silver(spark, config, "customers")
    return df.select(
        _hash_key("customer_id").alias("customer_key"),
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ).dropDuplicates(["customer_id"])


def build_dim_products(spark, config: dict) -> DataFrame:
    products = _silver(spark, config, "products")
    try:
        translations = _silver(spark, config, "product_category_translation")
        products = products.join(translations, "product_category_name", "left")
    except Exception:
        products = products.withColumn("product_category_name_english", col("product_category_name"))

    selected = [
        _hash_key("product_id").alias("product_key"),
        col("product_id"),
        col("product_category_name"),
        col("product_category_name_english"),
    ]
    for name in [
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]:
        if name in products.columns:
            selected.append(col(name))
    return products.select(*selected).dropDuplicates(["product_id"])


def build_dim_sellers(spark, config: dict) -> DataFrame:
    df = _silver(spark, config, "sellers")
    return df.select(
        _hash_key("seller_id").alias("seller_key"),
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ).dropDuplicates(["seller_id"])


def build_dim_dates(spark, config: dict) -> DataFrame:
    orders = _silver(spark, config, "orders")
    dates = orders.select(to_date(col("order_purchase_timestamp")).alias("date_day")).where(col("date_day").isNotNull())
    return (
        dates.dropDuplicates(["date_day"])
        .withColumn("date_key", date_format(col("date_day"), "yyyyMMdd").cast("int"))
        .withColumn("year", year(col("date_day")))
        .withColumn("month", month(col("date_day")))
        .withColumn("day", dayofmonth(col("date_day")))
        .withColumn("week_of_year", weekofyear(col("date_day")))
    )


def build_fct_orders(spark, config: dict) -> DataFrame:
    orders = _silver(spark, config, "orders")
    return orders.select(
        _hash_key("order_id").alias("order_key"),
        _hash_key("customer_id").alias("customer_key"),
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        to_date(col("order_purchase_timestamp")).alias("order_purchase_date"),
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
        "delivery_delay_days",
    ).dropDuplicates(["order_id"])


def build_fct_order_items(spark, config: dict) -> DataFrame:
    items = _silver(spark, config, "order_items")
    orders = build_fct_orders(spark, config).select(
        "order_id",
        "customer_id",
        "customer_key",
        "order_status",
        "order_purchase_timestamp",
        "order_purchase_date",
    )

    df = items.join(orders, "order_id", "left")
    return df.select(
        sha2(concat_ws("||", col("order_id"), col("order_item_id").cast("string")), 256).alias("order_item_key"),
        _hash_key("order_id").alias("order_key"),
        _hash_key("product_id").alias("product_key"),
        _hash_key("seller_id").alias("seller_key"),
        col("customer_key"),
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_purchase_date",
        "shipping_limit_date",
        "price",
        "freight_value",
        "total_item_value",
    )


def _silver(spark, config: dict, table: str) -> DataFrame:
    return read_layer(spark, layer_table_path(config, "silver", table))


def _hash_key(column_name: str):
    return sha2(concat_ws("||", col(column_name).cast("string"), lit("")), 256)

