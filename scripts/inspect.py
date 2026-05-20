#!/usr/bin/env python3
"""Inspect MySQL, bronze, silver layers and optional data-quality metrics."""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, min as f_min, max as f_max, sum as f_sum
from sqlalchemy import create_engine, text

LAYER_ITEMS = [
    ("Customers", "olist_customers_dataset", "customers"),
    ("Orders", "olist_orders_dataset", "orders"),
    ("Order Items", "olist_order_items_dataset", "order_items"),
]


def get_spark():
    return SparkSession.builder.appName("DataInspector").master("local[*]").getOrCreate()


def show_mysql():
    print("\n" + "=" * 70)
    print("MySQL DATABASE (app)")
    print("=" * 70)
    try:
        engine = create_engine("mysql+pymysql://root:root@localhost:3306/app")
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA='app' ORDER BY TABLE_NAME"
            ))
            tables = [r[0] for r in rows]
            print(f"\nTables: {len(tables)}\n")
            for table in tables:
                n = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
                print(f"  • {table}: {n:,} rows")
    except Exception as e:
        print(f"  Error: {e}")


def show_parquet_layer(spark, layer_name, base_dir, items):
    print("\n" + "=" * 70)
    print(f"{layer_name} ({base_dir})")
    print("=" * 70)
    for label, sub in items:
        path = PROJECT_DIR / base_dir / sub
        try:
            df = spark.read.parquet(str(path))
            cols = df.columns
            print(f"\n  {label}")
            print(f"     Rows: {df.count():,} | Columns: {len(cols)}")
            print(f"     Path: {path}")
            print(f"     Sample cols: {', '.join(cols[:5])}{'...' if len(cols) > 5 else ''}")
        except Exception as e:
            print(f"  {label}: {str(e)[:60]}")


def validate_silver(spark):
    print("\n" + "=" * 70)
    print("SILVER DATA QUALITY")
    print("=" * 70)
    for name, _, sub in LAYER_ITEMS:
        path = PROJECT_DIR / "data/silver" / sub
        try:
            df = spark.read.parquet(str(path))
            total = df.count()
            print(f"\n  {name.upper()}: {total:,} records")
            if name == "customers":
                print(f"     null customer_id: {df.filter(col('customer_id').isNull()).count()}")
                print(f"     unknown cities: {df.filter(col('customer_city') == 'unknown').count()}")
            elif name == "orders":
                print(f"     unknown status: {df.filter(col('order_status') == 'unknown').count()}")
                print(f"     delivered: {df.filter(col('order_status') == 'delivered').count()}")
            elif name == "order_items":
                stats = df.select(
                    avg("price"), f_min("price"), f_max("price"), f_sum("price")
                ).collect()[0]
                print(f"     zero price: {df.filter(col('price') == 0).count()}")
                print(f"     avg price: {round(stats[0] or 0, 2)}")
        except Exception as e:
            print(f"  {name}: {e}")


def show_sample(spark, limit=3):
    path = PROJECT_DIR / "data/silver/customers"
    print("\n" + "=" * 70)
    print("SAMPLE — Silver / Customers")
    print("=" * 70)
    try:
        df = spark.read.parquet(str(path))
        df.limit(limit).show(truncate=False)
    except Exception as e:
        print(f"  Error: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true", help="Include silver quality metrics")
    parser.add_argument("--skip-mysql", action="store_true")
    args = parser.parse_args()

    print("\nCDC PIPELINE — INSPECT")
    if not args.skip_mysql:
        show_mysql()

    spark = get_spark()
    spark.sparkContext.setLogLevel("ERROR")
    try:
        show_parquet_layer(
            spark, "BRONZE", "data/bronze",
            [(label, bronze) for label, bronze, _ in LAYER_ITEMS],
        )
        show_parquet_layer(
            spark, "SILVER", "data/silver",
            [(label, silver) for label, _, silver in LAYER_ITEMS],
        )
        if args.validate:
            validate_silver(spark)
        show_sample(spark)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
