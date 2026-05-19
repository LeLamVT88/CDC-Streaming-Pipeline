"""Common utilities for silver layer data cleaning"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, row_number, current_timestamp
from pyspark.sql.window import Window

def get_spark():
    """Initialize Spark session"""
    return SparkSession.builder \
        .appName("SilverLayer") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

def deduplicate(df, partition_cols):
    """Remove duplicates, keep latest record"""
    window = Window.partitionBy(*partition_cols).orderBy(col("_processing_timestamp").desc())
    df = df.withColumn("_rn", row_number().over(window))
    return df.filter(col("_rn") == 1).drop("_rn")

def add_metadata(df):
    """Add processed timestamp"""
    return df.withColumn("_silver_processed_at", current_timestamp())

def write_delta(df, output_path, partition_cols=None):
    """Write dataframe to delta format"""
    writer = df.write.format("delta").mode("overwrite")
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
    writer.save(output_path)
    return df.count()
