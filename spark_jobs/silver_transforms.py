"""Silver layer transforms: customers, orders, order items."""

from pyspark.sql.functions import (
    col, trim, upper, lower, lit, when, coalesce,
    to_timestamp, datediff, round,
)
from spark_jobs.silver_utils import deduplicate, add_metadata, read_layer, write_layer

VALID_STATUS = [
    "pending", "processing", "shipped", "delivered", "canceled",
    "unavailable", "on_return", "returned",
]


def clean_customers(spark, input_path, output_path):
    df = read_layer(spark, input_path)
    df = df.filter(col("customer_id").isNotNull())

    for name in ["customer_id", "customer_unique_id", "customer_zip_code_prefix"]:
        df = df.withColumn(name, trim(col(name)))

    df = df.withColumn("customer_city", trim(lower(col("customer_city"))))
    df = df.withColumn("customer_state", trim(upper(col("customer_state"))))
    df = df.withColumn(
        "customer_unique_id",
        when(
            (col("customer_unique_id").isNull()) | (col("customer_unique_id") == ""),
            col("customer_id"),
        ).otherwise(col("customer_unique_id")),
    )
    df = df.withColumn("customer_city", coalesce(col("customer_city"), lit("unknown")))
    df = df.withColumn("customer_state", coalesce(col("customer_state"), lit("UNKNOWN")))
    df = df.withColumn(
        "customer_zip_code_prefix",
        when(col("customer_zip_code_prefix").rlike(r"^\d{5}$"), col("customer_zip_code_prefix"))
        .otherwise(lit("00000")),
    )

    df = deduplicate(df, ["customer_id"])
    df = add_metadata(df)
    count = write_layer(df, output_path, partition_cols=["customer_state"] if layer_is_dbfs(output_path) else None)
    print(f"✓ Customers: {count:,} records")


def clean_orders(spark, input_path, output_path):
    df = read_layer(spark, input_path)
    df = df.filter((col("order_id").isNotNull()) & (col("customer_id").isNotNull()))

    df = df.withColumn("order_id", trim(col("order_id")))
    df = df.withColumn("customer_id", trim(col("customer_id")))
    df = df.withColumn("order_status", trim(lower(col("order_status"))))

    for ts_col in [
        "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ]:
        df = df.withColumn(
            ts_col,
            when(col(ts_col).isNotNull(), to_timestamp(col(ts_col), "yyyy-MM-dd HH:mm:ss")).otherwise(None),
        )

    df = df.withColumn(
        "order_status",
        when(col("order_status").isin(VALID_STATUS), col("order_status")).otherwise("unknown"),
    )
    df = df.withColumn(
        "delivery_delay_days",
        when(
            col("order_delivered_customer_date").isNotNull()
            & col("order_estimated_delivery_date").isNotNull(),
            datediff(col("order_delivered_customer_date"), col("order_estimated_delivery_date")),
        ).otherwise(None),
    )

    df = deduplicate(df, ["order_id"])
    df = add_metadata(df)
    parts = ["order_status"] if layer_is_dbfs(output_path) else None
    count = write_layer(df, output_path, partition_cols=parts)
    print(f"✓ Orders: {count:,} records")


def clean_order_items(spark, input_path, output_path):
    df = read_layer(spark, input_path)
    df = df.filter((col("order_id").isNotNull()) & (col("order_item_id").isNotNull()))

    for c in ["order_id", "product_id", "seller_id"]:
        df = df.withColumn(c, trim(col(c)))
    df = df.filter((col("product_id") != "") & (col("seller_id") != ""))

    df = df.withColumn(
        "shipping_limit_date",
        when(
            col("shipping_limit_date").isNotNull(),
            to_timestamp(col("shipping_limit_date"), "yyyy-MM-dd HH:mm:ss"),
        ).otherwise(None),
    )
    df = df.withColumn(
        "price",
        when((col("price").isNotNull()) & (col("price").cast("double") > 0), round(col("price").cast("double"), 2))
        .otherwise(0.0),
    )
    df = df.withColumn(
        "freight_value",
        when((col("freight_value").isNotNull()) & (col("freight_value").cast("double") >= 0),
             round(col("freight_value").cast("double"), 2)).otherwise(0.0),
    )
    df = df.withColumn("total_item_value", round(col("price") + col("freight_value"), 2))

    df = deduplicate(df, ["order_id", "order_item_id"])
    df = add_metadata(df)
    count = write_layer(df, output_path)
    print(f"✓ Order Items: {count:,} records")


def layer_is_dbfs(path):
    return str(path).startswith("dbfs:")
