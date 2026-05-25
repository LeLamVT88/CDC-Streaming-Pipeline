#!/usr/bin/env python3
"""Inspect bronze, clean, silver, mapping, and gold layers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyspark.sql.functions import avg, col, max as f_max, min as f_min, sum as f_sum

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from dwh.config import config_uses_s3, layer_table_path, load_config, resolve_path
from dwh.datasets import bronze_path, clean_path, load_datasets, silver_path
from dwh.io import get_spark, read_layer
from dwh.pipeline import parse_table_filter
from dwh.transforms.gold import GOLD_MODELS
from dwh.transforms.mapping import MAPPING_MODELS


def show_layer(spark, title: str, paths: list[tuple[str, str]]) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    for name, path in paths:
        try:
            df = read_layer(spark, path)
            columns = df.columns
            print(f"  {name}: {df.count():,} rows | {len(columns)} columns")
            print(f"    path: {path}")
            print(f"    columns: {', '.join(columns[:8])}{'...' if len(columns) > 8 else ''}")
        except Exception as exc:
            print(f"  {name}: {str(exc)[:160]}")


def validate_silver(spark, config: dict, datasets) -> None:
    print("\n" + "=" * 72)
    print("SILVER DATA QUALITY")
    print("=" * 72)
    for spec in datasets:
        path = silver_path(config, spec)
        try:
            df = read_layer(spark, path)
            total = df.count()
            print(f"\n  {spec.target}: {total:,} records")
            for key in spec.primary_key:
                if key in df.columns:
                    print(f"    null {key}: {df.filter(col(key).isNull()).count()}")

            if spec.target == "orders" and "order_status" in df.columns:
                print(f"    unknown status: {df.filter(col('order_status') == 'unknown').count()}")
                print(f"    delivered: {df.filter(col('order_status') == 'delivered').count()}")
            elif spec.target == "order_items" and "price" in df.columns:
                stats = df.select(avg("price"), f_min("price"), f_max("price"), f_sum("price")).collect()[0]
                print(f"    zero price: {df.filter(col('price') == 0).count()}")
                print(f"    avg price: {round(stats[0] or 0, 2)}")
            elif spec.target == "customers" and "customer_city" in df.columns:
                print(f"    unknown cities: {df.filter(col('customer_city') == 'unknown').count()}")
        except Exception as exc:
            print(f"  {spec.target}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect lakehouse outputs.")
    parser.add_argument("--config")
    parser.add_argument("--tables", help="Comma-separated source or target table names.")
    parser.add_argument("--validate", action="store_true", help="Include silver data-quality metrics.")
    args = parser.parse_args()

    config = load_config(args.config)
    datasets = load_datasets(config, parse_table_filter(args.tables))
    print("\nS3 LAKEHOUSE DWH INSPECT")
    print(f"project: {PROJECT_DIR}")
    print(f"raw: {resolve_path(config['paths']['raw'])}")

    spark = get_spark("LakehouseInspector", config=config, s3=config_uses_s3(config))
    spark.sparkContext.setLogLevel("ERROR")
    try:
        show_layer(spark, "BRONZE", [(spec.target, bronze_path(config, spec)) for spec in datasets])
        show_layer(spark, "CLEAN", [(spec.target, clean_path(config, spec)) for spec in datasets])
        show_layer(spark, "SILVER", [(spec.target, silver_path(config, spec)) for spec in datasets])
        show_layer(spark, "MAPPING", [(name, layer_table_path(config, "mapping", name)) for name in MAPPING_MODELS])
        show_layer(spark, "GOLD", [(name, layer_table_path(config, "gold", name)) for name in GOLD_MODELS])
        if args.validate:
            validate_silver(spark, config, datasets)
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

