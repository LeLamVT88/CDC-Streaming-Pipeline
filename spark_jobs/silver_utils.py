"""Shared utilities for silver layer jobs."""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, row_number, current_timestamp
from pyspark.sql.window import Window


def get_spark(app_name="SilverLayer", kafka=False):
    """Spark session for local parquet (default) or Kafka consumer."""
    builder = SparkSession.builder.appName(app_name).master("local[*]")
    if kafka:
        builder = builder.config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0",
        )
    return builder.getOrCreate()


def layer_format(path):
    return "delta" if str(path).startswith("dbfs:") else "parquet"


def read_layer(spark, path):
    fmt = layer_format(path)
    return spark.read.format(fmt).load(str(path))


def write_layer(df, path, partition_cols=None):
    fmt = layer_format(path)
    if fmt == "parquet":
        df.write.format("parquet").mode("overwrite").save(str(path))
    else:
        writer = df.write.format("delta").mode("overwrite")
        if partition_cols:
            writer = writer.partitionBy(*partition_cols)
        writer.save(str(path))
    return df.count()


def deduplicate(df, partition_cols):
    """Keep latest row per key; requires _processing_timestamp on bronze."""
    window = Window.partitionBy(*partition_cols).orderBy(col("_processing_timestamp").desc())
    df = df.withColumn("_rn", row_number().over(window))
    return df.filter(col("_rn") == 1).drop("_rn")


def add_metadata(df):
    return df.withColumn("_silver_processed_at", current_timestamp())
