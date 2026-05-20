"""Silver Layer - Orders Data Cleaning"""

from pyspark.sql.functions import col, trim, lower, to_timestamp, when, datediff
from spark_jobs.silver_utils import get_spark, deduplicate, add_metadata, write_delta

VALID_STATUS = ['pending', 'processing', 'shipped', 'delivered', 'canceled', 'unavailable', 'on_return', 'returned']

def clean_orders(spark, input_path, output_path):
    # Detect format: local (parquet) or dbfs (delta)
    fmt = "parquet" if not input_path.startswith("dbfs:") else "delta"
    df = spark.read.format(fmt).load(input_path)
    
    # Filter nulls
    df = df.filter((col("order_id").isNotNull()) & (col("customer_id").isNotNull()))
    
    # Clean strings
    df = df.withColumn("order_id", trim(col("order_id")))
    df = df.withColumn("customer_id", trim(col("customer_id")))
    df = df.withColumn("order_status", trim(lower(col("order_status"))))
    
    # Parse timestamps
    ts_cols = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date", 
               "order_delivered_customer_date", "order_estimated_delivery_date"]
    for ts_col in ts_cols:
        df = df.withColumn(ts_col, when(col(ts_col).isNotNull(),
                                        to_timestamp(col(ts_col), "yyyy-MM-dd HH:mm:ss")).otherwise(None))
    
    # Validate status
    df = df.withColumn("order_status", 
        when(col("order_status").isin(VALID_STATUS), col("order_status")).otherwise("unknown"))
    
    # Calculate delivery delay
    df = df.withColumn("delivery_delay_days",
        when((col("order_delivered_customer_date").isNotNull()) & (col("order_estimated_delivery_date").isNotNull()),
             datediff(col("order_delivered_customer_date"), col("order_estimated_delivery_date"))).otherwise(None))
    
    # Deduplicate & write
    df = deduplicate(df, ["order_id"])
    df = add_metadata(df)
    
    fmt = "parquet" if not output_path.startswith("dbfs:") else "delta"
    if fmt == "parquet":
        df.write.format("parquet").mode("overwrite").save(output_path)
    else:
        write_delta(df, output_path, ["order_status"])
    print(f"✓ Orders: {df.count()} records")

if __name__ == "__main__":
    spark = get_spark()
    try:
        clean_orders(spark, "dbfs:/mnt/bronze/olist_orders_dataset", "dbfs:/mnt/silver/orders")
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        spark.stop()
