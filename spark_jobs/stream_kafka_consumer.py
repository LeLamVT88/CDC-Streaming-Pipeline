"""Kafka Consumer - CDC Events to Bronze Layer"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col
import sys

def get_spark():
    return SparkSession.builder \
        .appName("KafkaConsumer") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0") \
        .getOrCreate()

def consume_batch(spark, kafka_servers, topic, output_path, table_name, duration_seconds=30):
    """Consume from Kafka for fixed duration and save as parquet"""
    try:
        df = spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_servers) \
            .option("subscribe", topic) \
            .option("startingOffsets", "earliest") \
            .load()
        
        df_write = df.select(
            col("value").cast("string").alias("json_value"),
            col("timestamp").alias("kafka_timestamp")
        )
        
        query = df_write.writeStream \
            .format("parquet") \
            .option("path", output_path) \
            .option("checkpointLocation", f"{output_path}_checkpoint") \
            .outputMode("append") \
            .start()
        
        query.awaitTermination(timeout=duration_seconds)
        query.stop()
        
        count = spark.read.parquet(output_path).count()
        print(f"✓ {table_name}: {count:,} records")
        return count
        
    except Exception as e:
        print(f"⚠ {table_name}: {str(e)[:50]}")
        return 0

def main():
    spark = get_spark()
    spark.sparkContext.setLogLevel("WARN")
    
    kafka_servers = "localhost:9092"
    bronze_base = "data/bronze"
    
    topics = [
        ("cdc.app.olist_customers_dataset", f"{bronze_base}/olist_customers_dataset", "Customers"),
        ("cdc.app.olist_orders_dataset", f"{bronze_base}/olist_orders_dataset", "Orders"),
        ("cdc.app.olist_order_items_dataset", f"{bronze_base}/olist_order_items_dataset", "Order Items"),
    ]
    
    total = 0
    for topic, path, label in topics:
        total += consume_batch(spark, kafka_servers, topic, path, label, 30)
    
    spark.stop()
    return total > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
