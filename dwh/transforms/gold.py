"""Gold-layer analytical marts built from mapping models."""

from __future__ import annotations

from typing import Callable

from pyspark.sql import DataFrame
from pyspark.sql.functions import avg, col, count, countDistinct, round as spark_round, sum as spark_sum

from dwh.config import layer_table_path
from dwh.io import read_layer, write_layer

GOLD_MODELS = [
    "sales_daily",
    "sales_by_customer_state",
    "product_category_performance",
    "seller_performance",
    "order_status_summary",
]


def run_gold_marts(spark, config: dict, mode: str = "overwrite") -> dict[str, int]:
    results: dict[str, int] = {}
    builders: dict[str, Callable] = {
        "sales_daily": build_sales_daily,
        "sales_by_customer_state": build_sales_by_customer_state,
        "product_category_performance": build_product_category_performance,
        "seller_performance": build_seller_performance,
        "order_status_summary": build_order_status_summary,
    }

    for name, builder in builders.items():
        try:
            df = builder(spark, config)
            path = layer_table_path(config, "gold", name)
            results[name] = write_layer(df, path, mode=mode)
            print(f"[gold] {name}: {results[name]:,} records")
        except Exception as exc:
            print(f"[gold] {name}: skipped ({str(exc)[:180]})")
    return results


def build_sales_daily(spark, config: dict) -> DataFrame:
    items = _mapping(spark, config, "fct_order_items")
    return (
        items.groupBy("order_purchase_date")
        .agg(
            countDistinct("order_id").alias("orders"),
            count("*").alias("items"),
            spark_round(spark_sum("price"), 2).alias("gross_item_revenue"),
            spark_round(spark_sum("freight_value"), 2).alias("freight_revenue"),
            spark_round(spark_sum("total_item_value"), 2).alias("total_revenue"),
            spark_round(avg("price"), 2).alias("avg_item_price"),
        )
        .orderBy("order_purchase_date")
    )


def build_sales_by_customer_state(spark, config: dict) -> DataFrame:
    items = _mapping(spark, config, "fct_order_items")
    customers = _mapping(spark, config, "dim_customers").select("customer_key", "customer_state")
    return (
        items.join(customers, "customer_key", "left")
        .groupBy("customer_state")
        .agg(
            countDistinct("order_id").alias("orders"),
            countDistinct("customer_id").alias("customers"),
            spark_round(spark_sum("total_item_value"), 2).alias("total_revenue"),
            spark_round(avg("total_item_value"), 2).alias("avg_item_value"),
        )
        .orderBy(col("total_revenue").desc_nulls_last())
    )


def build_product_category_performance(spark, config: dict) -> DataFrame:
    items = _mapping(spark, config, "fct_order_items")
    products = _mapping(spark, config, "dim_products").select("product_key", "product_category_name_english")
    return (
        items.join(products, "product_key", "left")
        .groupBy("product_category_name_english")
        .agg(
            countDistinct("order_id").alias("orders"),
            countDistinct("product_id").alias("products"),
            count("*").alias("items"),
            spark_round(spark_sum("total_item_value"), 2).alias("total_revenue"),
            spark_round(avg("price"), 2).alias("avg_item_price"),
        )
        .orderBy(col("total_revenue").desc_nulls_last())
    )


def build_seller_performance(spark, config: dict) -> DataFrame:
    items = _mapping(spark, config, "fct_order_items")
    sellers = _mapping(spark, config, "dim_sellers").select("seller_key", "seller_state", "seller_city")
    return (
        items.join(sellers, "seller_key", "left")
        .groupBy("seller_id", "seller_state", "seller_city")
        .agg(
            countDistinct("order_id").alias("orders"),
            countDistinct("product_id").alias("products"),
            spark_round(spark_sum("total_item_value"), 2).alias("total_revenue"),
            spark_round(avg("total_item_value"), 2).alias("avg_item_value"),
        )
        .orderBy(col("total_revenue").desc_nulls_last())
    )


def build_order_status_summary(spark, config: dict) -> DataFrame:
    orders = _mapping(spark, config, "fct_orders")
    return (
        orders.groupBy("order_status")
        .agg(
            countDistinct("order_id").alias("orders"),
            spark_round(avg("delivery_delay_days"), 2).alias("avg_delivery_delay_days"),
        )
        .orderBy(col("orders").desc())
    )


def _mapping(spark, config: dict, table: str) -> DataFrame:
    return read_layer(spark, layer_table_path(config, "mapping", table))

