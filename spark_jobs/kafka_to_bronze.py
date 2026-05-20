"""Consume CDC Kafka topics into bronze parquet (raw Debezium JSON)."""

import sys
from pyspark.sql.functions import col
from spark_jobs.silver_utils import get_spark

KAFKA_SERVERS = "localhost:9092"
BRONZE_BASE = "data/bronze"
CONSUME_SECONDS = 30

TOPICS = [
    ("cdc.app.olist_customers_dataset", f"{BRONZE_BASE}/olist_customers_dataset", "Customers"),
    ("cdc.app.olist_orders_dataset", f"{BRONZE_BASE}/olist_orders_dataset", "Orders"),
    ("cdc.app.olist_order_items_dataset", f"{BRONZE_BASE}/olist_order_items_dataset", "Order Items"),
]


def consume_batch(spark, kafka_servers, topic, output_path, table_name, duration_seconds=CONSUME_SECONDS):
    try:
        stream = (
            spark.readStream.format("kafka")
            .option("kafka.bootstrap.servers", kafka_servers)
            .option("subscribe", topic)
            .option("startingOffsets", "earliest")
            .load()
        )
        df_write = stream.select(
            col("value").cast("string").alias("json_value"),
            col("timestamp").alias("kafka_timestamp"),
        )
        query = (
            df_write.writeStream.format("parquet")
            .option("path", output_path)
            .option("checkpointLocation", f"{output_path}_checkpoint")
            .outputMode("append")
            .start()
        )
        query.awaitTermination(timeout=duration_seconds)
        query.stop()

        count = spark.read.parquet(output_path).count()
        print(f"✓ {table_name}: {count:,} records")
        return count
    except Exception as e:
        print(f"⚠ {table_name}: {str(e)[:80]}")
        return 0


def consume_all_topics(spark, kafka_servers=KAFKA_SERVERS):
    return sum(
        consume_batch(spark, kafka_servers, topic, path, label)
        for topic, path, label in TOPICS
    )


def main():
    spark = get_spark("KafkaToBronze", kafka=True)
    spark.sparkContext.setLogLevel("WARN")
    try:
        total = consume_all_topics(spark)
        return total > 0
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
