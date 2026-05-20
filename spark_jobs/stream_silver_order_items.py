"""Silver Layer - Order Items Data Cleaning"""

from pyspark.sql.functions import col, trim, to_timestamp, when, round
from spark_jobs.silver_utils import get_spark, deduplicate, add_metadata, write_delta

def clean_order_items(spark, input_path, output_path):
    # Detect format: local (parquet) or dbfs (delta)
    fmt = "parquet" if not input_path.startswith("dbfs:") else "delta"
    df = spark.read.format(fmt).load(input_path)
    
    # Filter nulls & clean
    df = df.filter((col("order_id").isNotNull()) & (col("order_item_id").isNotNull()))
    for c in ["order_id", "product_id", "seller_id"]:
        df = df.withColumn(c, trim(col(c)))
    df = df.filter((col("product_id") != "") & (col("seller_id") != ""))
    
    # Parse timestamp
    df = df.withColumn("shipping_limit_date",
        when(col("shipping_limit_date").isNotNull(),
             to_timestamp(col("shipping_limit_date"), "yyyy-MM-dd HH:mm:ss")).otherwise(None))
    
    # Validate & round prices
    df = df.withColumn("price", 
        when((col("price").isNotNull()) & (col("price").cast("double") > 0),
             round(col("price").cast("double"), 2)).otherwise(0.0))
    df = df.withColumn("freight_value",
        when((col("freight_value").isNotNull()) & (col("freight_value").cast("double") >= 0),
             round(col("freight_value").cast("double"), 2)).otherwise(0.0))
    
    # Calculate total
    df = df.withColumn("total_item_value", round(col("price") + col("freight_value"), 2))
    
    # Deduplicate & write
    df = deduplicate(df, ["order_id", "order_item_id"])
    df = add_metadata(df)
    
    fmt = "parquet" if not output_path.startswith("dbfs:") else "delta"
    if fmt == "parquet":
        df.write.format("parquet").mode("overwrite").save(output_path)
    else:
        write_delta(df, output_path)
    print(f"✓ Order Items: {df.count()} records")

if __name__ == "__main__":
    spark = get_spark()
    try:
        clean_order_items(spark, "dbfs:/mnt/bronze/olist_order_items_dataset", "dbfs:/mnt/silver/order_items")
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        spark.stop()
