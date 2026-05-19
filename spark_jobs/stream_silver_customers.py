"""Silver Layer - Customer Data Cleaning"""

from pyspark.sql.functions import col, trim, upper, lower, lit, when, coalesce
from silver_utils import get_spark, deduplicate, add_metadata, write_delta

def clean_customers(spark, input_path, output_path):
    # Detect format: local (parquet) or dbfs (delta)
    fmt = "parquet" if not input_path.startswith("dbfs:") else "delta"
    df = spark.read.format(fmt).load(input_path)
    
    # Filter & trim
    df = df.filter(col("customer_id").isNotNull())
    for col_name in ["customer_id", "customer_unique_id", "customer_zip_code_prefix"]:
        df = df.withColumn(col_name, trim(col(col_name)))
    
    df = df.withColumn("customer_city", trim(lower(col("customer_city"))))
    df = df.withColumn("customer_state", trim(upper(col("customer_state"))))
    
    # Handle nulls
    df = df.withColumn("customer_unique_id", 
        when((col("customer_unique_id").isNull()) | (col("customer_unique_id") == ""), 
             col("customer_id")).otherwise(col("customer_unique_id")))
    df = df.withColumn("customer_city", coalesce(col("customer_city"), lit("unknown")))
    df = df.withColumn("customer_state", coalesce(col("customer_state"), lit("UNKNOWN")))
    
    # Validate zip code
    df = df.withColumn("customer_zip_code_prefix",
        when((col("customer_zip_code_prefix").rlike("^\\d{5}$")), 
             col("customer_zip_code_prefix")).otherwise(lit("00000")))
    
    # Deduplicate & add metadata
    df = deduplicate(df, ["customer_id"])
    df = add_metadata(df)
    
    # Write in appropriate format
    fmt = "parquet" if not output_path.startswith("dbfs:") else "delta"
    if fmt == "parquet":
        df.write.format("parquet").mode("overwrite").save(output_path)
    else:
        count = write_delta(df, output_path, ["customer_state"])
    print(f"✓ Customers: {df.count()} records")

if __name__ == "__main__":
    spark = get_spark()
    try:
        clean_customers(spark, "dbfs:/mnt/bronze/olist_customers_dataset", 
                       "dbfs:/mnt/silver/customers")
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        spark.stop()
