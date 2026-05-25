"""Shared Spark and lakehouse IO utilities."""

from __future__ import annotations

import os
import platform
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, current_timestamp, lit, row_number
from pyspark.sql.window import Window

from dwh.config import PROJECT_DIR


def get_spark(
    app_name: str = "S3LakehouseDWH",
    config: dict | None = None,
    kafka: bool = False,
    s3: bool = False,
) -> SparkSession:
    """Create a local Spark session with optional Kafka and S3 support."""
    config = config or {}
    spark_config = config.get("spark", {})
    _configure_windows_hadoop()

    builder = (
        SparkSession.builder.appName(app_name)
        .master(spark_config.get("master", "local[*]"))
        .config("spark.sql.shuffle.partitions", str(spark_config.get("shuffle_partitions", 8)))
        .config("spark.sql.session.timeZone", spark_config.get("timezone", "UTC"))
    )

    packages: list[str] = []
    if kafka:
        packages.append(
            spark_config.get(
                "kafka_package",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0",
            )
        )
    if s3:
        packages.append(spark_config.get("s3_package", "org.apache.hadoop:hadoop-aws:3.3.4"))

    if packages:
        builder = builder.config("spark.jars.packages", ",".join(packages))

    if s3:
        builder = _with_s3_config(builder, config)

    return builder.getOrCreate()


def _configure_windows_hadoop() -> None:
    if platform.system().lower() != "windows":
        return
    hadoop_home = PROJECT_DIR / "hadoop"
    configured_home = os.getenv("HADOOP_HOME")
    configured_home_exists = bool(configured_home and Path(configured_home).exists())
    if hadoop_home.exists() and not configured_home_exists:
        os.environ["HADOOP_HOME"] = str(hadoop_home)
        os.environ["PATH"] = f"{hadoop_home / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"


def _with_s3_config(builder, config: dict):
    storage = config.get("storage", {}).get("s3a", {})
    endpoint = storage.get("endpoint") or os.getenv("AWS_ENDPOINT_URL")
    if endpoint:
        builder = builder.config("spark.hadoop.fs.s3a.endpoint", endpoint)
        builder = builder.config("spark.hadoop.fs.s3a.path.style.access", "true")
    if storage.get("region") or os.getenv("AWS_DEFAULT_REGION"):
        builder = builder.config(
            "spark.hadoop.fs.s3a.endpoint.region",
            storage.get("region") or os.getenv("AWS_DEFAULT_REGION"),
        )
    builder = builder.config(
        "spark.hadoop.fs.s3a.aws.credentials.provider",
        storage.get("credentials_provider", "com.amazonaws.auth.DefaultAWSCredentialsProviderChain"),
    )
    return builder


def layer_format(path: str) -> str:
    if str(path).startswith("dbfs:"):
        return "delta"
    return "parquet"


def read_layer(spark: SparkSession, path: str) -> DataFrame:
    return spark.read.format(layer_format(path)).load(str(path))


def write_layer(
    df: DataFrame,
    path: str,
    mode: str = "overwrite",
    partition_cols: list[str] | tuple[str, ...] | None = None,
) -> int:
    fmt = layer_format(path)
    partition_cols = [name for name in (partition_cols or []) if name in df.columns]
    writer = df.write.format(fmt).mode(mode)
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
    writer.save(str(path))
    return df.sparkSession.read.format(fmt).load(str(path)).count()


def require_columns(df: DataFrame, required: list[str] | tuple[str, ...], dataset_name: str) -> None:
    missing = [name for name in required if name not in df.columns]
    if missing:
        raise ValueError(f"{dataset_name} missing required columns: {', '.join(missing)}")


def trim_strings(df: DataFrame, columns: list[str] | tuple[str, ...] | None = None) -> DataFrame:
    from pyspark.sql.functions import trim

    selected = columns or [name for name, dtype in df.dtypes if dtype == "string"]
    for name in selected:
        if name in df.columns:
            df = df.withColumn(name, trim(col(name)))
    return df


def empty_to_null(df: DataFrame, columns: list[str] | tuple[str, ...] | None = None) -> DataFrame:
    from pyspark.sql.functions import when

    selected = columns or [name for name, dtype in df.dtypes if dtype == "string"]
    for name in selected:
        if name in df.columns:
            df = df.withColumn(name, when(col(name) == "", None).otherwise(col(name)))
    return df


def ensure_processing_metadata(df: DataFrame, source_table: str | None = None) -> DataFrame:
    if "_processing_timestamp" not in df.columns:
        df = df.withColumn("_processing_timestamp", current_timestamp())
    if source_table and "_source_table" not in df.columns:
        df = df.withColumn("_source_table", lit(source_table))
    return df


def deduplicate_latest(df: DataFrame, key_cols: list[str] | tuple[str, ...]) -> DataFrame:
    if not key_cols:
        return df

    order_cols = []
    for name in ["_event_timestamp", "_processing_timestamp", "_kafka_timestamp", "_kafka_offset"]:
        if name in df.columns:
            order_cols.append(col(name).desc_nulls_last())
    if not order_cols:
        order_cols.append(lit(1).desc())

    window = Window.partitionBy(*key_cols).orderBy(*order_cols)
    return df.withColumn("_rn", row_number().over(window)).filter(col("_rn") == 1).drop("_rn")


def remove_deleted_cdc_rows(df: DataFrame) -> DataFrame:
    if "_cdc_op" not in df.columns:
        return df
    return df.filter((col("_cdc_op").isNull()) | (col("_cdc_op") != "d"))


def add_clean_metadata(df: DataFrame) -> DataFrame:
    return df.withColumn("_clean_processed_at", current_timestamp())


def add_silver_metadata(df: DataFrame) -> DataFrame:
    return df.withColumn("_silver_processed_at", current_timestamp())

