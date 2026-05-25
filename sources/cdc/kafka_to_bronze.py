"""Read Debezium CDC topics from Kafka and land them in the bronze layer."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

from pyspark.sql.functions import coalesce, col, current_timestamp, from_unixtime, get_json_object, lit

PROJECT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_DIR))

from dwh.config import config_uses_s3, load_config
from dwh.datasets import DatasetSpec, bronze_path, load_datasets
from dwh.io import get_spark, write_layer


def consume_topic_to_bronze(
    spark,
    config: dict,
    spec: DatasetSpec,
    mode: str = "overwrite",
) -> int:
    cdc = config.get("source_adapters", {}).get("cdc", {})
    kafka_config = cdc.get("kafka", {})
    topic = spec.cdc_topic(kafka_config.get("topic_prefix", "cdc.app"))
    output_path = bronze_path(config, spec)

    raw = (
        spark.read.format("kafka")
        .option("kafka.bootstrap.servers", kafka_config.get("bootstrap_servers", "localhost:9092"))
        .option("subscribe", topic)
        .option("startingOffsets", kafka_config.get("starting_offsets", "earliest"))
        .option("endingOffsets", kafka_config.get("ending_offsets", "latest"))
        .load()
    )

    message_count = raw.count()
    if message_count == 0:
        print(f"[cdc:bronze] {spec.label}: no messages in {topic}")
        return 0

    value_json = col("value").cast("string")
    key_json = col("key").cast("string")
    cdc_op = get_json_object(value_json, "$.op")
    ts_ms = get_json_object(value_json, "$.ts_ms").cast("double")

    business_columns = [
        coalesce(
            get_json_object(value_json, f"$.after.{name}"),
            get_json_object(value_json, f"$.before.{name}"),
        ).alias(name)
        for name in spec.columns
    ]

    df = raw.select(
        *business_columns,
        cdc_op.alias("_cdc_op"),
        from_unixtime((ts_ms / lit(1000)).cast("long")).cast("timestamp").alias("_event_timestamp"),
        col("timestamp").alias("_kafka_timestamp"),
        col("topic").alias("_kafka_topic"),
        col("partition").alias("_kafka_partition"),
        col("offset").alias("_kafka_offset"),
        key_json.alias("_kafka_key"),
        value_json.alias("_debezium_payload"),
        lit(spec.source).alias("_source_table"),
        lit("cdc").alias("_ingest_source"),
        current_timestamp().alias("_processing_timestamp"),
    ).filter(col("_cdc_op").isin("c", "u", "r", "d"))

    count = write_layer(df, output_path, mode=mode)
    print(f"[cdc:bronze] {spec.label}: {count:,} bronze records from {topic}")
    return count


def consume_all_topics(
    spark,
    config: dict,
    datasets: Iterable[DatasetSpec],
    mode: str = "overwrite",
) -> int:
    total = 0
    for spec in datasets:
        try:
            total += consume_topic_to_bronze(spark, config, spec, mode=mode)
        except Exception as exc:
            print(f"[cdc:bronze] {spec.label}: {str(exc)[:160]}")
    return total


def main() -> int:
    config = load_config()
    datasets = load_datasets(config)
    spark = get_spark("CDCSourceToBronze", config=config, kafka=True, s3=config_uses_s3(config, ("bronze",)))
    spark.sparkContext.setLogLevel(config.get("spark", {}).get("log_level", "WARN"))
    try:
        total = consume_all_topics(spark, config, datasets)
        return 0 if total > 0 else 1
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
