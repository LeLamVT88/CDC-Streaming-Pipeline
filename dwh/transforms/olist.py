"""Bronze-clean-silver transforms for the Olist sample domain."""

from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    avg,
    coalesce,
    col,
    datediff,
    lit,
    lower,
    regexp_replace,
    round as spark_round,
    to_timestamp,
    upper,
    when,
)

from dwh.datasets import DatasetSpec
from dwh.io import (
    add_clean_metadata,
    add_silver_metadata,
    deduplicate_latest,
    empty_to_null,
    ensure_processing_metadata,
    read_layer,
    remove_deleted_cdc_rows,
    require_columns,
    trim_strings,
    write_layer,
)

VALID_ORDER_STATUS = [
    "approved",
    "canceled",
    "created",
    "delivered",
    "invoiced",
    "on_return",
    "pending",
    "processing",
    "returned",
    "shipped",
    "unavailable",
]


def write_clean_dataset(spark, spec: DatasetSpec, input_path: str, output_path: str, mode: str = "overwrite") -> int:
    transform = CLEAN_TRANSFORMS.get(spec.target, normalize_generic)
    df = transform(spark, spec, input_path)
    df = ensure_processing_metadata(df, spec.source)
    df = add_clean_metadata(df)
    count = write_layer(df, output_path, mode=mode)
    print(f"[clean] {spec.label}: {count:,} records")
    return count


def write_silver_dataset(spark, spec: DatasetSpec, input_path: str, output_path: str, mode: str = "overwrite") -> int:
    df = read_layer(spark, input_path)
    df = finalize_silver_df(df, spec)
    count = write_layer(df, output_path, mode=mode, partition_cols=spec.partition_by)
    print(f"[silver] {spec.label}: {count:,} records")
    return count


def normalize_generic(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    df = trim_strings(df)
    return empty_to_null(df)


def normalize_customers(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    require_columns(
        df,
        ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
        spec.target,
    )

    df = trim_strings(df)
    df = empty_to_null(df)
    df = df.withColumn("customer_city", lower(col("customer_city")))
    df = df.withColumn("customer_state", upper(col("customer_state")))
    df = df.withColumn(
        "customer_unique_id",
        when(col("customer_unique_id").isNull(), col("customer_id")).otherwise(col("customer_unique_id")),
    )
    df = df.withColumn("customer_city", coalesce(col("customer_city"), lit("unknown")))
    df = df.withColumn("customer_state", coalesce(col("customer_state"), lit("UNKNOWN")))
    df = df.withColumn(
        "customer_zip_code_prefix",
        regexp_replace(col("customer_zip_code_prefix").cast("string"), r"[^0-9]", ""),
    )
    return df.withColumn(
        "customer_zip_code_prefix",
        when(col("customer_zip_code_prefix").rlike(r"^[0-9]{5}$"), col("customer_zip_code_prefix")).otherwise(
            lit("00000")
        ),
    )


def normalize_orders(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    require_columns(df, ["order_id", "customer_id", "order_status"], spec.target)

    df = trim_strings(df)
    df = empty_to_null(df)
    df = df.withColumn("order_status", lower(col("order_status")))
    for name in [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        if name in df.columns:
            df = df.withColumn(name, to_timestamp(col(name)))

    df = df.withColumn(
        "order_status",
        when(col("order_status").isin(VALID_ORDER_STATUS), col("order_status")).otherwise(lit("unknown")),
    )
    return df.withColumn(
        "delivery_delay_days",
        when(
            col("order_delivered_customer_date").isNotNull()
            & col("order_estimated_delivery_date").isNotNull(),
            datediff(col("order_delivered_customer_date"), col("order_estimated_delivery_date")),
        ),
    )


def normalize_order_items(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    require_columns(df, ["order_id", "order_item_id", "product_id", "seller_id"], spec.target)

    df = trim_strings(df)
    df = empty_to_null(df)
    df = df.filter(col("product_id").isNotNull() & col("seller_id").isNotNull())
    df = df.withColumn("order_item_id", col("order_item_id").cast("int"))
    if "shipping_limit_date" in df.columns:
        df = df.withColumn("shipping_limit_date", to_timestamp(col("shipping_limit_date")))
    df = _non_negative_double(df, "price", strict_positive=True)
    df = _non_negative_double(df, "freight_value")
    return df.withColumn("total_item_value", spark_round(col("price") + col("freight_value"), 2))


def normalize_order_payments(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    require_columns(df, ["order_id", "payment_sequential", "payment_type", "payment_value"], spec.target)

    df = trim_strings(df)
    df = empty_to_null(df)
    df = df.withColumn("payment_type", lower(coalesce(col("payment_type"), lit("unknown"))))
    df = df.withColumn("payment_sequential", col("payment_sequential").cast("int"))
    df = df.withColumn(
        "payment_installments",
        when(col("payment_installments").cast("int") >= 0, col("payment_installments").cast("int")).otherwise(0),
    )
    return _non_negative_double(df, "payment_value")


def normalize_products(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    require_columns(df, ["product_id"], spec.target)

    df = trim_strings(df)
    df = empty_to_null(df)
    if "product_name_lenght" in df.columns:
        df = df.withColumnRenamed("product_name_lenght", "product_name_length")
    if "product_description_lenght" in df.columns:
        df = df.withColumnRenamed("product_description_lenght", "product_description_length")
    df = df.withColumn("product_category_name", lower(coalesce(col("product_category_name"), lit("unknown"))))
    for name in [
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]:
        if name in df.columns:
            df = df.withColumn(name, when(col(name).cast("double") >= 0, col(name).cast("double")))
    return df


def normalize_sellers(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    require_columns(df, ["seller_id", "seller_city", "seller_state"], spec.target)

    df = trim_strings(df)
    df = empty_to_null(df)
    df = df.withColumn("seller_city", lower(coalesce(col("seller_city"), lit("unknown"))))
    df = df.withColumn("seller_state", upper(coalesce(col("seller_state"), lit("UNKNOWN"))))
    return df.withColumn("seller_zip_code_prefix", regexp_replace(col("seller_zip_code_prefix"), r"[^0-9]", ""))


def normalize_order_reviews(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    require_columns(df, ["review_id", "order_id", "review_score"], spec.target)

    df = trim_strings(df)
    df = empty_to_null(df)
    df = df.withColumn(
        "review_score",
        when(col("review_score").cast("int").between(1, 5), col("review_score").cast("int")),
    )
    for name in ["review_creation_date", "review_answer_timestamp"]:
        if name in df.columns:
            df = df.withColumn(name, to_timestamp(col(name)))
    return df


def normalize_geolocation(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    require_columns(
        df,
        ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"],
        spec.target,
    )

    df = trim_strings(df)
    df = empty_to_null(df)
    df = df.withColumn("geolocation_zip_code_prefix", regexp_replace(col("geolocation_zip_code_prefix"), r"[^0-9]", ""))
    df = df.withColumn("geolocation_city", lower(coalesce(col("geolocation_city"), lit("unknown"))))
    df = df.withColumn("geolocation_state", upper(coalesce(col("geolocation_state"), lit("UNKNOWN"))))
    df = df.withColumn("geolocation_lat", col("geolocation_lat").cast("double"))
    df = df.withColumn("geolocation_lng", col("geolocation_lng").cast("double"))
    df = df.filter(col("geolocation_lat").between(-90, 90) & col("geolocation_lng").between(-180, 180))
    df = df.groupBy("geolocation_zip_code_prefix", "geolocation_city", "geolocation_state").agg(
        spark_round(avg("geolocation_lat"), 6).alias("geolocation_lat"),
        spark_round(avg("geolocation_lng"), 6).alias("geolocation_lng"),
    )
    return ensure_processing_metadata(df, spec.source)


def normalize_product_category_translation(spark, spec: DatasetSpec, input_path: str) -> DataFrame:
    df = read_layer(spark, input_path)
    require_columns(df, ["product_category_name", "product_category_name_english"], spec.target)
    df = trim_strings(df)
    df = empty_to_null(df)
    df = df.withColumn("product_category_name", lower(col("product_category_name")))
    return df.withColumn("product_category_name_english", lower(col("product_category_name_english")))


def finalize_silver_df(df: DataFrame, spec: DatasetSpec) -> DataFrame:
    df = ensure_processing_metadata(df, spec.source)
    require_columns(df, spec.primary_key, spec.target)

    dtypes = dict(df.dtypes)
    for key in spec.primary_key:
        key_is_string = dtypes.get(key) == "string"
        valid_key = col(key).isNotNull()
        if key_is_string:
            valid_key = valid_key & (col(key) != "")
        df = df.filter(valid_key)

    df = deduplicate_latest(df, spec.primary_key)
    df = remove_deleted_cdc_rows(df)
    return add_silver_metadata(df)


def _non_negative_double(df: DataFrame, name: str, strict_positive: bool = False) -> DataFrame:
    if name not in df.columns:
        return df
    value = col(name).cast("double")
    condition = value > 0 if strict_positive else value >= 0
    return df.withColumn(name, when(condition, spark_round(value, 2)).otherwise(lit(0.0)))


CLEAN_TRANSFORMS = {
    "customers": normalize_customers,
    "orders": normalize_orders,
    "order_items": normalize_order_items,
    "order_payments": normalize_order_payments,
    "products": normalize_products,
    "sellers": normalize_sellers,
    "order_reviews": normalize_order_reviews,
    "geolocation": normalize_geolocation,
    "product_category_translation": normalize_product_category_translation,
}

