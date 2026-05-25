"""Athena DDL generation for lakehouse layers."""

from __future__ import annotations

from pathlib import Path

from pyspark.sql.types import (
    BooleanType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    ShortType,
    StringType,
    TimestampType,
)

from dwh.config import join_path, layer_table_path, resolve_path
from dwh.datasets import DatasetSpec
from dwh.io import read_layer
from dwh.transforms.gold import GOLD_MODELS
from dwh.transforms.mapping import MAPPING_MODELS


def generate_athena_ddl(
    spark,
    config: dict,
    datasets: list[DatasetSpec],
    layers: tuple[str, ...] = ("silver", "mapping", "gold"),
    skip_missing: bool = False,
) -> Path:
    database = config.get("aws", {}).get("athena_database", "s3_lakehouse_dwh")
    ddl_path = Path(resolve_path(config["paths"].get("athena_ddl", "docs/athena_lakehouse_ddl.sql")))
    ddl_path.parent.mkdir(parents=True, exist_ok=True)

    statements = [f"CREATE DATABASE IF NOT EXISTS {database};", f"USE {database};"]
    for layer, table, partition_cols in _layer_tables(datasets, layers):
        path = layer_table_path(config, layer, table)
        try:
            df = read_layer(spark, path)
        except Exception:
            if skip_missing:
                continue
            raise

        location = athena_location(config, layer, table)
        partition_set = set(partition_cols)
        regular_fields = [field for field in df.schema.fields if field.name not in partition_set]
        fields_sql = ",\n  ".join(
            f"`{field.name}` {spark_type_to_athena(field.dataType)}" for field in regular_fields
        )

        statement = [
            f"DROP TABLE IF EXISTS `{layer}_{table}`;",
            f"CREATE EXTERNAL TABLE `{layer}_{table}` (",
            f"  {fields_sql}",
            ")",
        ]
        if partition_cols:
            partitions_sql = ", ".join(f"`{name}` string" for name in partition_cols)
            statement.append(f"PARTITIONED BY ({partitions_sql})")
        statement.extend(
            [
                "STORED AS PARQUET",
                f"LOCATION '{location}';",
            ]
        )
        if partition_cols:
            statement.append(f"MSCK REPAIR TABLE `{layer}_{table}`;")
        statements.append("\n".join(statement))

    ddl_path.write_text("\n\n".join(statements) + "\n", encoding="utf-8")
    print(f"[athena] DDL written to {ddl_path}")
    return ddl_path


def athena_location(config: dict, layer: str, table: str) -> str:
    configured = config.get("aws", {}).get("athena_s3_location")
    if configured:
        return join_path(configured, layer, table).replace("s3a://", "s3://")

    path = layer_table_path(config, layer, table).replace("\\", "/")
    if path.startswith("s3://") or path.startswith("s3a://"):
        return path.replace("s3a://", "s3://")

    bucket = config.get("aws", {}).get("s3_bucket")
    prefix = config.get("aws", {}).get("s3_prefix", "dwh")
    if bucket:
        return join_path(f"s3://{bucket}", prefix, layer, table)
    return join_path("s3://CHANGE_ME", "dwh", layer, table)


def spark_type_to_athena(data_type) -> str:
    if isinstance(data_type, StringType):
        return "string"
    if isinstance(data_type, BooleanType):
        return "boolean"
    if isinstance(data_type, (IntegerType, ShortType)):
        return "int"
    if isinstance(data_type, LongType):
        return "bigint"
    if isinstance(data_type, (DoubleType, FloatType)):
        return "double"
    if isinstance(data_type, TimestampType):
        return "timestamp"
    if isinstance(data_type, DateType):
        return "date"
    if isinstance(data_type, DecimalType):
        return f"decimal({data_type.precision},{data_type.scale})"
    return "string"


def _layer_tables(datasets: list[DatasetSpec], layers: tuple[str, ...]):
    for layer in layers:
        if layer == "silver":
            for spec in datasets:
                yield layer, spec.target, spec.partition_by
        elif layer == "mapping":
            for table in MAPPING_MODELS:
                yield layer, table, ()
        elif layer == "gold":
            for table in GOLD_MODELS:
                yield layer, table, ()
