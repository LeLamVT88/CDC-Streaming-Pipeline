#!/usr/bin/env python3
"""CDC pipeline entry point: silver (CSV) or cdc (Kafka bronze)."""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "scripts" / "ingestion"))

from pyspark.sql.functions import current_timestamp
from spark_jobs.silver_utils import get_spark
from spark_jobs.silver_transforms import clean_customers, clean_orders, clean_order_items
from spark_jobs.kafka_to_bronze import consume_all_topics, KAFKA_SERVERS
from seed_to_mysql import import_seed_data

SEED_DIR = PROJECT_DIR / "db" / "seed"
BRONZE_DIR = PROJECT_DIR / "data" / "bronze"
SILVER_DIR = PROJECT_DIR / "data" / "silver"

DATASETS = [
    ("olist_customers_dataset", "customers", "Customers", clean_customers),
    ("olist_orders_dataset", "orders", "Orders", clean_orders),
    ("olist_order_items_dataset", "order_items", "Order Items", clean_order_items),
]


def load_seed_to_bronze(spark):
    print("\n[bronze] CSV → bronze parquet\n")
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    for file_name, _, label in DATASETS:
        csv_path = SEED_DIR / f"{file_name}.csv"
        out_path = BRONZE_DIR / file_name
        print(f"  {file_name}.csv ({label})")
        df = spark.read.csv(str(csv_path), header=True, inferSchema=True)
        df = df.withColumn("_processing_timestamp", current_timestamp())
        df.write.format("parquet").mode("overwrite").save(str(out_path))
        print(f"    ✓ {df.count():,} records")


def run_silver(spark):
    print("\n[silver] bronze → silver\n")
    results = {}
    for bronze_name, silver_name, label, clean_fn in DATASETS:
        try:
            clean_fn(
                spark,
                str(BRONZE_DIR / bronze_name),
                str(SILVER_DIR / silver_name),
            )
            results[label] = "✓"
        except Exception as e:
            results[label] = f"✗ {str(e)[:50]}"
            print(f"  ✗ {label}: {e}")
    return results


def show_silver_stats(spark):
    print("\n[stats] silver layer\n")
    for _, silver_name, label, _ in DATASETS:
        try:
            n = spark.read.parquet(str(SILVER_DIR / silver_name)).count()
            print(f"  ✓ {label}: {n:,} records")
        except Exception as e:
            print(f"  ✗ {label}: {e}")


def run_silver_mode(spark):
    load_seed_to_bronze(spark)
    results = run_silver(spark)
    show_silver_stats(spark)
    return all(v == "✓" for v in results.values())


def run_cdc_mode(spark, seed_mysql=False):
    if seed_mysql:
        print("\n[1/3] CSV → MySQL")
        import_seed_data()
    print("\n[2/3] Kafka → bronze (raw JSON)")
    time.sleep(5)
    total = consume_all_topics(spark, KAFKA_SERVERS)
    if total == 0:
        print("  ⚠ No Kafka messages — deploy connector and wait for snapshot")
    print("\n[3/3] bronze → silver")
    print("  ⚠ Bronze from Kafka is raw JSON; use --mode silver for CSV-based silver.")
    return total > 0


def main():
    parser = argparse.ArgumentParser(description="CDC Streaming Pipeline")
    parser.add_argument(
        "--mode",
        choices=["silver", "cdc"],
        default="silver",
        help="silver: CSV→bronze→silver | cdc: Kafka→bronze (optional MySQL seed)",
    )
    parser.add_argument("--seed-mysql", action="store_true", help="With --mode cdc: load CSV to MySQL first")
    args = parser.parse_args()

    start = datetime.now()
    print("\n" + "=" * 50)
    print(f"CDC PIPELINE — mode={args.mode}")
    print("=" * 50)

    spark = get_spark("CDCPipeline")
    spark.sparkContext.setLogLevel("WARN")
    try:
        if args.mode == "silver":
            ok = run_silver_mode(spark)
        else:
            ok = run_cdc_mode(spark, seed_mysql=args.seed_mysql)
        elapsed = (datetime.now() - start).total_seconds()
        print(f"\n⏱ {elapsed:.1f}s\n")
        return 0 if ok else 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())
