#!/usr/bin/env python3
"""CLI entry point for the S3 lakehouse DWH."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from dwh.athena import generate_athena_ddl
from dwh.config import config_uses_s3, load_config
from dwh.datasets import bronze_path, clean_path, load_datasets, silver_path
from dwh.io import get_spark
from dwh.pipeline import load_csv_to_bronze, parse_table_filter, run_clean, run_silver, show_layer_stats, validate_config
from dwh.transforms.gold import run_gold_marts
from dwh.transforms.mapping import run_mapping_models


def main() -> int:
    parser = argparse.ArgumentParser(description="S3 lakehouse DWH pipeline")
    parser.add_argument(
        "--mode",
        choices=["validate", "bronze", "clean", "silver", "mapping", "gold", "all", "athena-ddl"],
        default="all",
        help="Pipeline stage to run.",
    )
    parser.add_argument("--config", help="Path to app_config.yaml")
    parser.add_argument("--tables", help="Comma-separated source or target table names. Default: all enabled tables.")
    parser.add_argument("--skip-missing", action="store_true", help="With athena-ddl: skip layers that do not exist.")
    args = parser.parse_args()

    config = load_config(args.config)
    datasets = load_datasets(config, parse_table_filter(args.tables))

    start = datetime.now()
    print("\n" + "=" * 72)
    print(f"S3 Lakehouse DWH | mode={args.mode} | tables={len(datasets)}")
    print("=" * 72)

    if args.mode == "validate":
        return 0 if validate_config(config, datasets) else 1

    spark = get_spark(
        config.get("spark", {}).get("app_name", "S3LakehouseDWH"),
        config=config,
        s3=config_uses_s3(config),
    )
    spark.sparkContext.setLogLevel(config.get("spark", {}).get("log_level", "WARN"))

    try:
        if args.mode in {"bronze", "all"}:
            load_csv_to_bronze(spark, config, datasets)
        if args.mode in {"clean", "all"}:
            run_clean(spark, config, datasets)
        if args.mode in {"silver", "all"}:
            run_silver(spark, config, datasets)
            show_layer_stats(spark, "silver", [(spec.target, silver_path(config, spec)) for spec in datasets])
        if args.mode in {"mapping", "all"}:
            run_mapping_models(spark, config, mode=config.get("storage", {}).get("write_mode", "overwrite"))
        if args.mode in {"gold", "all"}:
            run_gold_marts(spark, config, mode=config.get("storage", {}).get("write_mode", "overwrite"))
        if args.mode == "athena-ddl":
            generate_athena_ddl(spark, config, datasets, skip_missing=args.skip_missing)

        if args.mode in {"bronze", "clean"}:
            layer = args.mode
            path_fn = bronze_path if layer == "bronze" else clean_path
            show_layer_stats(spark, layer, [(spec.target, path_fn(config, spec)) for spec in datasets])

        elapsed = (datetime.now() - start).total_seconds()
        print(f"\n[done] {elapsed:.1f}s")
        return 0
    except Exception as exc:
        print(f"\n[error] {exc}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        spark.stop()


if __name__ == "__main__":
    sys.exit(main())

