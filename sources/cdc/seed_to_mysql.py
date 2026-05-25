#!/usr/bin/env python3
"""Load CSV source files into MySQL for optional Debezium CDC snapshots."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_DIR))

from dwh.config import load_config, resolve_path
from dwh.datasets import DatasetSpec, load_datasets, raw_csv_path
from dwh.pipeline import parse_table_filter


def cdc_config(config: dict) -> dict:
    return config.get("source_adapters", {}).get("cdc", {})


def mysql_config(config: dict) -> dict:
    return cdc_config(config).get("mysql", {})


def mysql_url(config: dict) -> str:
    mysql = mysql_config(config)
    user = quote_plus(str(mysql.get("user", "root")))
    password = quote_plus(str(mysql.get("password", "root")))
    host = mysql.get("host", "localhost")
    port = mysql.get("port", 3306)
    database = mysql.get("database", "app")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"


def ensure_database(config: dict) -> None:
    mysql = mysql_config(config)
    user = quote_plus(str(mysql.get("user", "root")))
    password = quote_plus(str(mysql.get("password", "root")))
    host = mysql.get("host", "localhost")
    port = mysql.get("port", 3306)
    database = mysql.get("database", "app")
    base_url = f"mysql+pymysql://{user}:{password}@{host}:{port}?charset=utf8mb4"
    engine = create_engine(base_url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4"))
    engine.dispose()


def import_seed_data(
    config: dict | None = None,
    datasets: list[DatasetSpec] | None = None,
    if_exists: str | None = None,
) -> dict[str, int]:
    config = config or load_config()
    datasets = datasets or load_datasets(config)
    chunksize = int(cdc_config(config).get("seed", {}).get("chunksize", 50000))
    default_if_exists = if_exists or cdc_config(config).get("seed", {}).get("if_exists", "replace")

    ensure_database(config)
    engine = create_engine(mysql_url(config), pool_pre_ping=True)
    results: dict[str, int] = {}

    try:
        for spec in datasets:
            csv_path = Path(resolve_path(raw_csv_path(config, spec)))
            if not csv_path.exists():
                raise FileNotFoundError(f"Missing source file: {csv_path}")

            print(f"[cdc:seed] {spec.csv_name} -> MySQL table {spec.source}")
            start = time.time()
            total = 0
            first_chunk = True

            for chunk in pd.read_csv(
                csv_path,
                chunksize=chunksize,
                dtype=str,
                keep_default_na=False,
                encoding="utf-8",
            ):
                write_mode = default_if_exists if first_chunk else "append"
                chunk.to_sql(
                    name=spec.source,
                    con=engine,
                    if_exists=write_mode,
                    index=False,
                    chunksize=5000,
                    method="multi",
                )
                total += len(chunk)
                first_chunk = False
                print(f"           loaded {total:,} rows", end="\r")

            elapsed = time.time() - start
            print(f"           done: {total:,} rows in {elapsed:.1f}s")
            results[spec.source] = total
    finally:
        engine.dispose()

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Load configured CSV source files into MySQL.")
    parser.add_argument("--config", help="Path to app_config.yaml")
    parser.add_argument("--tables", help="Comma-separated source or target table names")
    parser.add_argument("--if-exists", choices=["replace", "append", "fail"], help="pandas to_sql behavior")
    args = parser.parse_args()

    config = load_config(args.config)
    datasets = load_datasets(config, parse_table_filter(args.tables))
    import_seed_data(config, datasets, if_exists=args.if_exists)
    return 0


if __name__ == "__main__":
    sys.exit(main())

