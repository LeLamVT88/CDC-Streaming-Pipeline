#!/usr/bin/env python3
"""CLI for the optional MySQL/Debezium/Kafka CDC source adapter."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from dwh.config import config_uses_s3, load_config
from dwh.datasets import load_datasets
from dwh.io import get_spark
from dwh.pipeline import parse_table_filter
from sources.cdc.debezium import deploy_debezium_connector
from sources.cdc.kafka_to_bronze import consume_all_topics
from sources.cdc.seed_to_mysql import import_seed_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional CDC source adapter")
    parser.add_argument(
        "--mode",
        choices=["seed", "deploy-connector", "bronze", "all"],
        default="all",
        help="CDC source step to run.",
    )
    parser.add_argument("--config", help="Path to app_config.yaml")
    parser.add_argument("--tables", help="Comma-separated source or target table names")
    parser.add_argument("--recreate-connector", action="store_true", help="Delete and recreate Debezium connector.")
    parser.add_argument("--snapshot-wait-seconds", type=int, default=20, help="Wait after connector deploy.")
    args = parser.parse_args()

    config = load_config(args.config)
    datasets = load_datasets(config, parse_table_filter(args.tables))

    if args.mode in {"seed", "all"}:
        import_seed_data(config, datasets)

    if args.mode in {"deploy-connector", "all"}:
        deploy_debezium_connector(config, datasets, recreate=args.recreate_connector)
        if args.snapshot_wait_seconds:
            print(f"[cdc] waiting {args.snapshot_wait_seconds}s for snapshot messages")
            time.sleep(args.snapshot_wait_seconds)

    if args.mode in {"bronze", "all"}:
        spark = get_spark("CDCSourceToBronze", config=config, kafka=True, s3=config_uses_s3(config, ("bronze",)))
        spark.sparkContext.setLogLevel(config.get("spark", {}).get("log_level", "WARN"))
        try:
            total = consume_all_topics(
                spark,
                config,
                datasets,
                mode=config.get("storage", {}).get("write_mode", "overwrite"),
            )
            return 0 if total > 0 else 1
        finally:
            spark.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())

