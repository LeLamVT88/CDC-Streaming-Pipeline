"""Build gold-layer dimensions, facts, and analytical marts from silver parquet."""

from collections import OrderedDict
import os
from pathlib import Path

from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    avg,
    coalesce,
    col,
    concat_ws,
    count,
    countDistinct,
    current_timestamp,
    date_format,
    dayofmonth,
    dayofweek,
    explode,
    expr,
    lit,
    max as spark_max,
    min as spark_min,
    month,
    quarter,
    round as spark_round,
    sequence,
    sha2,
    sum as spark_sum,
    to_date,
    weekofyear,
    year,
)

try:
    from scripts.common.config import get_nested, load_yaml
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.config import get_nested, load_yaml


CONFIG = load_yaml()

SILVER_TABLES = {
    "customers": "olist_customers_dataset",
    "geolocation": "olist_geolocation_dataset",
    "order_items": "olist_order_items_dataset",
    "order_payments": "olist_order_payments_dataset",
    "order_reviews": "olist_order_reviews_dataset",
    "orders": "olist_orders_dataset",
    "products": "olist_products_dataset",
    "sellers": "olist_sellers_dataset",
    "translations": "product_category_name_translation",
}

DIMENSION_MODELS = [
    "dim_customers",
    "dim_geolocation",
    "dim_products",
    "dim_sellers",
    "dim_dates",
]

FACT_MODELS = [
    "fact_orders",
    "fact_order_items",
    "fact_order_payments",
    "fact_order_reviews",
]

MART_MODELS = [
    "mart_sales_daily",
    "mart_sales_by_customer_state",
    "mart_product_category_performance",
    "mart_seller_performance",
    "mart_order_status_summary",
]

GOLD_MODELS = DIMENSION_MODELS + FACT_MODELS + MART_MODELS


def build_spark(app_name="OlistSilverToGold", silver_path=None, gold_path=None):
    """Create Spark with S3A support when either layer uses S3."""
    master = get_nested(CONFIG, "spark", "master", default="local[*]")
    builder = SparkSession.builder.appName(app_name).master(master)

    paths = [str(path or "") for path in [silver_path, gold_path]]
    if any(path.startswith(("s3://", "s3a://")) for path in paths):
        package = os.environ.get(
            "HADOOP_AWS_PACKAGE",
            get_nested(CONFIG, "spark", "hadoop_aws_package", default="org.apache.hadoop:hadoop-aws:3.4.1"),
        )
        jars = os.environ.get("HADOOP_AWS_JARS")
        repositories = os.environ.get("SPARK_JARS_REPOSITORIES", "https://repo.maven.apache.org/maven2")
        endpoint = os.environ.get("S3_ENDPOINT", get_nested(CONFIG, "spark", "s3_endpoint", default=None))
        region = os.environ.get("AWS_DEFAULT_REGION", get_nested(CONFIG, "aws", "region", default="ap-southeast-1"))

        if jars:
            builder = builder.config("spark.jars", jars)
        else:
            builder = builder.config("spark.jars.packages", package)
            builder = builder.config("spark.jars.repositories", repositories)
        builder = builder.config("spark.hadoop.fs.s3a.endpoint.region", region)
        if endpoint:
            builder = builder.config("spark.hadoop.fs.s3a.endpoint", endpoint)

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def read_silver_tables(spark, silver_path):
    """Read the Silver table folders exactly as they are written by bronze_to_silver."""
    tables = {}
    for alias, table_name in SILVER_TABLES.items():
        path = join_path(silver_path, table_name)
        print(f"Reading silver table {path}")
        tables[alias] = spark.read.parquet(path)
    return tables


def build_dimensions(tables):
    """Create reusable conformed dimensions."""
    customers = tables["customers"]
    require_columns(
        customers,
        ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
        SILVER_TABLES["customers"],
    )
    dim_customers = customers.select(
        hash_key("customer_id").alias("customer_key"),
        "customer_id",
        "customer_unique_id",
        "customer_zip_code_prefix",
        "customer_city",
        "customer_state",
    ).dropDuplicates(["customer_id"])

    geolocation = tables["geolocation"]
    require_columns(
        geolocation,
        [
            "geolocation_zip_code_prefix",
            "geolocation_lat",
            "geolocation_lng",
            "geolocation_city",
            "geolocation_state",
        ],
        SILVER_TABLES["geolocation"],
    )
    dim_geolocation = (
        geolocation.groupBy("geolocation_zip_code_prefix", "geolocation_city", "geolocation_state")
        .agg(
            spark_round(avg("geolocation_lat"), 6).alias("geolocation_lat"),
            spark_round(avg("geolocation_lng"), 6).alias("geolocation_lng"),
        )
        .withColumn(
            "geolocation_key",
            hash_key("geolocation_zip_code_prefix", "geolocation_city", "geolocation_state"),
        )
        .select(
            "geolocation_key",
            "geolocation_zip_code_prefix",
            "geolocation_city",
            "geolocation_state",
            "geolocation_lat",
            "geolocation_lng",
        )
    )

    products = tables["products"]
    translations = tables["translations"]
    require_columns(products, ["product_id", "product_category_name"], SILVER_TABLES["products"])
    require_columns(
        translations,
        ["product_category_name", "product_category_name_english"],
        SILVER_TABLES["translations"],
    )
    products = products.join(
        translations.select("product_category_name", "product_category_name_english").dropDuplicates(
            ["product_category_name"]
        ),
        "product_category_name",
        "left",
    )
    product_columns = [
        hash_key("product_id").alias("product_key"),
        col("product_id"),
        col("product_category_name"),
        coalesce(col("product_category_name_english"), col("product_category_name")).alias(
            "product_category_name_english"
        ),
    ]
    for column_name in [
        "product_name_length",
        "product_description_length",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]:
        if column_name in products.columns:
            product_columns.append(col(column_name))
    dim_products = products.select(*product_columns).dropDuplicates(["product_id"])

    sellers = tables["sellers"]
    require_columns(
        sellers,
        ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
        SILVER_TABLES["sellers"],
    )
    dim_sellers = sellers.select(
        hash_key("seller_id").alias("seller_key"),
        "seller_id",
        "seller_zip_code_prefix",
        "seller_city",
        "seller_state",
    ).dropDuplicates(["seller_id"])

    orders = tables["orders"]
    require_columns(orders, ["order_purchase_timestamp"], SILVER_TABLES["orders"])
    date_range = orders.select(to_date("order_purchase_timestamp").alias("date_day")).where(
        col("date_day").isNotNull()
    )
    date_range = date_range.agg(spark_min("date_day").alias("min_date"), spark_max("date_day").alias("max_date"))
    dim_dates = (
        date_range.select(explode(sequence("min_date", "max_date", expr("interval 1 day"))).alias("date_day"))
        .withColumn("date_key", date_format("date_day", "yyyyMMdd").cast("int"))
        .withColumn("year", year("date_day"))
        .withColumn("quarter", quarter("date_day"))
        .withColumn("month", month("date_day"))
        .withColumn("day", dayofmonth("date_day"))
        .withColumn("week_of_year", weekofyear("date_day"))
        .withColumn("day_of_week", dayofweek("date_day"))
        .select("date_key", "date_day", "year", "quarter", "month", "day", "week_of_year", "day_of_week")
    )

    return OrderedDict(
        [
            ("dim_customers", dim_customers),
            ("dim_geolocation", dim_geolocation),
            ("dim_products", dim_products),
            ("dim_sellers", dim_sellers),
            ("dim_dates", dim_dates),
        ]
    )


def build_facts(tables):
    """Create order-grain and event-grain facts from Silver."""
    orders = tables["orders"]
    items = tables["order_items"]
    payments = tables["order_payments"]
    reviews = tables["order_reviews"]

    require_columns(
        orders,
        [
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
            "delivery_delay_days",
        ],
        SILVER_TABLES["orders"],
    )
    require_columns(
        items,
        ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
        SILVER_TABLES["order_items"],
    )
    require_columns(
        payments,
        ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
        SILVER_TABLES["order_payments"],
    )
    require_columns(reviews, ["review_id", "order_id", "review_score"], SILVER_TABLES["order_reviews"])

    items = ensure_total_item_value(items)
    item_summary = items.groupBy("order_id").agg(
        count("*").alias("item_count"),
        countDistinct("product_id").alias("product_count"),
        countDistinct("seller_id").alias("seller_count"),
        spark_round(spark_sum("price"), 2).alias("item_revenue"),
        spark_round(spark_sum("freight_value"), 2).alias("freight_revenue"),
        spark_round(spark_sum("total_item_value"), 2).alias("total_order_value"),
    )
    payment_summary = payments.groupBy("order_id").agg(
        count("*").alias("payment_count"),
        countDistinct("payment_type").alias("payment_type_count"),
        spark_max("payment_installments").alias("max_payment_installments"),
        spark_round(spark_sum("payment_value"), 2).alias("payment_value"),
    )
    review_summary = reviews.groupBy("order_id").agg(
        count("*").alias("review_count"),
        spark_round(avg("review_score"), 2).alias("avg_review_score"),
    )

    fact_orders = (
        orders.join(item_summary, "order_id", "left")
        .join(payment_summary, "order_id", "left")
        .join(review_summary, "order_id", "left")
        .select(
            hash_key("order_id").alias("order_key"),
            hash_key("customer_id").alias("customer_key"),
            date_key("order_purchase_timestamp").alias("purchase_date_key"),
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
            "delivery_delay_days",
            coalesce(col("item_count"), lit(0)).alias("item_count"),
            coalesce(col("product_count"), lit(0)).alias("product_count"),
            coalesce(col("seller_count"), lit(0)).alias("seller_count"),
            coalesce(col("item_revenue"), lit(0.0)).alias("item_revenue"),
            coalesce(col("freight_revenue"), lit(0.0)).alias("freight_revenue"),
            coalesce(col("total_order_value"), lit(0.0)).alias("total_order_value"),
            coalesce(col("payment_count"), lit(0)).alias("payment_count"),
            coalesce(col("payment_type_count"), lit(0)).alias("payment_type_count"),
            coalesce(col("max_payment_installments"), lit(0)).alias("max_payment_installments"),
            coalesce(col("payment_value"), lit(0.0)).alias("payment_value"),
            coalesce(col("review_count"), lit(0)).alias("review_count"),
            col("avg_review_score"),
        )
        .dropDuplicates(["order_id"])
    )

    order_context = orders.select(
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
    ).dropDuplicates(["order_id"])

    fact_order_items = (
        items.join(order_context, "order_id", "left")
        .select(
            hash_key("order_id", "order_item_id").alias("order_item_key"),
            hash_key("order_id").alias("order_key"),
            hash_key("customer_id").alias("customer_key"),
            hash_key("product_id").alias("product_key"),
            hash_key("seller_id").alias("seller_key"),
            date_key("order_purchase_timestamp").alias("purchase_date_key"),
            "order_id",
            "order_item_id",
            "customer_id",
            "product_id",
            "seller_id",
            "order_status",
            "order_purchase_timestamp",
            "shipping_limit_date",
            "price",
            "freight_value",
            "total_item_value",
        )
        .dropDuplicates(["order_id", "order_item_id"])
    )

    fact_order_payments = (
        payments.join(order_context, "order_id", "left")
        .select(
            hash_key("order_id", "payment_sequential").alias("payment_key"),
            hash_key("order_id").alias("order_key"),
            hash_key("customer_id").alias("customer_key"),
            date_key("order_purchase_timestamp").alias("purchase_date_key"),
            "order_id",
            "payment_sequential",
            "customer_id",
            "order_status",
            "payment_type",
            "payment_installments",
            "payment_value",
        )
        .dropDuplicates(["order_id", "payment_sequential"])
    )

    review_columns = [
        hash_key("review_id", "order_id").alias("review_key"),
        hash_key("order_id").alias("order_key"),
        hash_key("customer_id").alias("customer_key"),
        date_key("order_purchase_timestamp").alias("purchase_date_key"),
        col("review_id"),
        col("order_id"),
        col("customer_id"),
        col("order_status"),
        col("review_score"),
    ]
    for column_name in [
        "review_comment_title",
        "review_comment_message",
        "review_creation_date",
        "review_answer_timestamp",
    ]:
        if column_name in reviews.columns:
            review_columns.append(col(column_name))
    fact_order_reviews = (
        reviews.join(order_context, "order_id", "left")
        .select(*review_columns)
        .dropDuplicates(["review_id", "order_id"])
    )

    return OrderedDict(
        [
            ("fact_orders", fact_orders),
            ("fact_order_items", fact_order_items),
            ("fact_order_payments", fact_order_payments),
            ("fact_order_reviews", fact_order_reviews),
        ]
    )


def build_marts(dimensions, facts):
    """Create business-facing aggregate marts for Athena and BI tools."""
    fact_orders = facts["fact_orders"]
    fact_items = facts["fact_order_items"]
    customers = dimensions["dim_customers"].select("customer_key", "customer_state")
    products = dimensions["dim_products"].select("product_key", "product_category_name_english")
    sellers = dimensions["dim_sellers"].select("seller_key", "seller_state", "seller_city")

    mart_sales_daily = (
        fact_orders.groupBy(to_date("order_purchase_timestamp").alias("order_purchase_date"))
        .agg(
            countDistinct("order_id").alias("orders"),
            spark_sum("item_count").alias("items"),
            spark_round(spark_sum("item_revenue"), 2).alias("item_revenue"),
            spark_round(spark_sum("freight_revenue"), 2).alias("freight_revenue"),
            spark_round(spark_sum("total_order_value"), 2).alias("total_revenue"),
            spark_round(spark_sum("payment_value"), 2).alias("payment_value"),
        )
        .orderBy("order_purchase_date")
    )

    mart_sales_by_customer_state = (
        fact_orders.join(customers, "customer_key", "left")
        .groupBy("customer_state")
        .agg(
            countDistinct("order_id").alias("orders"),
            countDistinct("customer_id").alias("customers"),
            spark_round(spark_sum("total_order_value"), 2).alias("total_revenue"),
            spark_round(avg("total_order_value"), 2).alias("avg_order_value"),
        )
        .orderBy(col("total_revenue").desc_nulls_last())
    )

    mart_product_category_performance = (
        fact_items.join(products, "product_key", "left")
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

    mart_seller_performance = (
        fact_items.join(sellers, "seller_key", "left")
        .groupBy("seller_id", "seller_state", "seller_city")
        .agg(
            countDistinct("order_id").alias("orders"),
            countDistinct("product_id").alias("products"),
            spark_round(spark_sum("total_item_value"), 2).alias("total_revenue"),
            spark_round(avg("total_item_value"), 2).alias("avg_item_value"),
        )
        .orderBy(col("total_revenue").desc_nulls_last())
    )

    mart_order_status_summary = (
        fact_orders.groupBy("order_status")
        .agg(
            countDistinct("order_id").alias("orders"),
            spark_round(avg("delivery_delay_days"), 2).alias("avg_delivery_delay_days"),
            spark_round(spark_sum("total_order_value"), 2).alias("total_revenue"),
        )
        .orderBy(col("orders").desc())
    )

    return OrderedDict(
        [
            ("mart_sales_daily", mart_sales_daily),
            ("mart_sales_by_customer_state", mart_sales_by_customer_state),
            ("mart_product_category_performance", mart_product_category_performance),
            ("mart_seller_performance", mart_seller_performance),
            ("mart_order_status_summary", mart_order_status_summary),
        ]
    )


def build_gold_models(tables):
    dimensions = build_dimensions(tables)
    facts = build_facts(tables)
    marts = build_marts(dimensions, facts)

    models = OrderedDict()
    models.update(dimensions)
    models.update(facts)
    models.update(marts)
    return models


def write_models(models, gold_path, mode="overwrite"):
    """Write every Gold model without recomputing its lineage for the row count."""
    output_partitions = max(1, int(os.environ.get("GOLD_OUTPUT_PARTITIONS", "1")))
    results = {}
    for model_name, df in models.items():
        output_path = join_path(gold_path, model_name)
        print(f"Writing gold model {output_path}")
        persisted_df = df.withColumn("_gold_processed_at", current_timestamp()).persist(StorageLevel.MEMORY_AND_DISK)
        try:
            results[model_name] = persisted_df.count()
            persisted_df.coalesce(output_partitions).write.mode(mode).parquet(output_path)
            print(f"  {results[model_name]:,} rows")
        finally:
            persisted_df.unpersist()
    return results


def run_dimensions(spark, silver_path, gold_path, mode="overwrite"):
    tables = cache_tables(read_silver_tables(spark, silver_path))
    try:
        return write_models(build_dimensions(tables), gold_path, mode)
    finally:
        unpersist_tables(tables)


def run_gold_pipeline(spark, silver_path, gold_path, mode="overwrite"):
    tables = cache_tables(read_silver_tables(spark, silver_path))
    try:
        return write_models(build_gold_models(tables), gold_path, mode)
    finally:
        unpersist_tables(tables)


def cache_tables(tables):
    for df in tables.values():
        df.persist(StorageLevel.MEMORY_AND_DISK)
    return tables


def unpersist_tables(tables):
    for df in tables.values():
        df.unpersist()


def require_columns(df, columns, table_name):
    missing = [column_name for column_name in columns if column_name not in df.columns]
    if missing:
        raise ValueError(f"{table_name} missing required columns: {', '.join(missing)}")


def ensure_total_item_value(df):
    if "total_item_value" in df.columns:
        return df
    return df.withColumn("total_item_value", spark_round(col("price") + col("freight_value"), 2))


def hash_key(*column_names):
    values = [coalesce(col(column_name).cast("string"), lit("")) for column_name in column_names]
    return sha2(concat_ws("||", *values), 256)


def date_key(column_name):
    return date_format(to_date(col(column_name)), "yyyyMMdd").cast("int")


def join_path(base_path, name):
    return f"{str(base_path).rstrip('/')}/{name}"
