"""Core lakehouse pipeline stages."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pyspark.sql.functions import current_timestamp, lit

from dwh.config import is_uri, resolve_path
from dwh.datasets import DatasetSpec, bronze_path, clean_path, raw_csv_path, silver_path
from dwh.io import read_layer, write_layer
from dwh.transforms.olist import write_clean_dataset, write_silver_dataset


def parse_table_filter(raw: str | None) -> list[str] | None:
    if not raw or raw.strip().lower() == "all":
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_csv_to_bronze(spark, config: dict, datasets: Iterable[DatasetSpec]) -> dict[str, int]:
    print("\n[bronze] CSV -> bronze")
    results: dict[str, int] = {}
    mode = config.get("storage", {}).get("write_mode", "overwrite")

    for spec in datasets:
        csv_path = raw_csv_path(config, spec)
        if not is_uri(csv_path) and not Path(resolve_path(csv_path)).exists():
            raise FileNotFoundError(f"Missing source CSV file: {resolve_path(csv_path)}")

        out_path = bronze_path(config, spec)
        print(f"  {csv_path} -> {out_path}")
        df = (
            spark.read.option("header", True)
            .option("inferSchema", False)
            .option("multiLine", True)
            .option("quote", '"')
            .option("escape", '"')
            .csv(csv_path)
        )

        for name in spec.columns:
            if name not in df.columns:
                df = df.withColumn(name, lit(None).cast("string"))

        df = df.select(*spec.columns)
        df = (
            df.withColumn("_source_table", lit(spec.source))
            .withColumn("_ingest_source", lit("csv"))
            .withColumn("_processing_timestamp", current_timestamp())
        )
        results[spec.target] = write_layer(df, out_path, mode=mode)
        print(f"    bronze records: {results[spec.target]:,}")

    return results


def run_clean(spark, config: dict, datasets: Iterable[DatasetSpec]) -> dict[str, int]:
    print("\n[clean] bronze -> clean")
    mode = config.get("storage", {}).get("write_mode", "overwrite")
    results: dict[str, int] = {}
    for spec in datasets:
        results[spec.target] = write_clean_dataset(
            spark,
            spec,
            bronze_path(config, spec),
            clean_path(config, spec),
            mode=mode,
        )
    return results


def run_silver(spark, config: dict, datasets: Iterable[DatasetSpec]) -> dict[str, int]:
    print("\n[silver] clean -> silver")
    mode = config.get("storage", {}).get("write_mode", "overwrite")
    results: dict[str, int] = {}
    for spec in datasets:
        results[spec.target] = write_silver_dataset(
            spark,
            spec,
            clean_path(config, spec),
            silver_path(config, spec),
            mode=mode,
        )
    return results


def show_layer_stats(spark, title: str, paths: Iterable[tuple[str, str]]) -> None:
    print(f"\n[stats] {title}")
    for name, path in paths:
        try:
            count = read_layer(spark, path).count()
            print(f"  {name}: {count:,} records")
        except Exception as exc:
            print(f"  {name}: {str(exc)[:160]}")


def validate_config(config: dict, datasets: list[DatasetSpec]) -> bool:
    print("[validate] lakehouse configuration")
    print(f"  project: {config.get('project', {}).get('root')}")
    for key in ["raw", "bronze", "clean", "silver", "mapping", "gold"]:
        print(f"  {key}: {resolve_path(config['paths'][key])}")
    print(f"  tables: {len(datasets)}")

    missing = []
    for spec in datasets:
        path = raw_csv_path(config, spec)
        if not is_uri(path) and not Path(resolve_path(path)).exists():
            missing.append(resolve_path(path))
    if missing:
        print("  missing raw CSV files:")
        for path in missing:
            print(f"    {path}")
        return False

    print("  status: ok")
    return True

