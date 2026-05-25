"""Configuration helpers for the S3 lakehouse DWH."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_DIR / "configs" / "app_config.yaml"


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load YAML config and apply runtime environment overrides."""
    path = Path(config_path or os.getenv("DWH_CONFIG") or os.getenv("PIPELINE_CONFIG") or DEFAULT_CONFIG_PATH)
    if not path.is_absolute():
        path = PROJECT_DIR / path

    with path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}

    config.setdefault("project", {})
    config["project"]["root"] = str(PROJECT_DIR)
    config.setdefault("source_adapters", {})

    _apply_env_overrides(config)
    return config


def _apply_env_overrides(config: dict[str, Any]) -> None:
    paths = config.setdefault("paths", {})
    path_envs = {
        "raw": ["DWH_RAW_PATH", "PIPELINE_RAW_PATH"],
        "bronze": ["DWH_BRONZE_PATH", "PIPELINE_BRONZE_PATH"],
        "clean": ["DWH_CLEAN_PATH"],
        "silver": ["DWH_SILVER_PATH", "PIPELINE_SILVER_PATH"],
        "mapping": ["DWH_MAPPING_PATH"],
        "gold": ["DWH_GOLD_PATH"],
        "checkpoints": ["DWH_CHECKPOINTS_PATH", "PIPELINE_CHECKPOINTS_PATH"],
    }
    for key, env_names in path_envs.items():
        for env_name in env_names:
            if os.getenv(env_name):
                paths[key] = os.environ[env_name]
                break

    aws = config.setdefault("aws", {})
    if os.getenv("DWH_S3_BUCKET"):
        aws["s3_bucket"] = os.environ["DWH_S3_BUCKET"]
    if os.getenv("DWH_S3_PREFIX"):
        aws["s3_prefix"] = os.environ["DWH_S3_PREFIX"]
    if os.getenv("DWH_ATHENA_DATABASE"):
        aws["athena_database"] = os.environ["DWH_ATHENA_DATABASE"]
    if os.getenv("DWH_ATHENA_LOCATION"):
        aws["athena_s3_location"] = os.environ["DWH_ATHENA_LOCATION"]

    cdc = config.setdefault("source_adapters", {}).setdefault("cdc", {})
    mysql = cdc.setdefault("mysql", {})
    mysql["host"] = os.getenv("MYSQL_HOST", mysql.get("host", "localhost"))
    mysql["port"] = int(os.getenv("MYSQL_PORT", mysql.get("port", 3306)))
    mysql["user"] = os.getenv("MYSQL_USER", mysql.get("user", "root"))
    mysql["password"] = os.getenv("MYSQL_PASSWORD", mysql.get("password", "root"))
    mysql["database"] = os.getenv("MYSQL_DATABASE", mysql.get("database", "app"))

    kafka = cdc.setdefault("kafka", {})
    kafka["bootstrap_servers"] = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        kafka.get("bootstrap_servers", "localhost:9092"),
    )
    kafka["connect_url"] = os.getenv(
        "KAFKA_CONNECT_URL",
        kafka.get("connect_url", "http://localhost:8083"),
    )
    kafka["schema_registry_url"] = os.getenv(
        "SCHEMA_REGISTRY_URL",
        kafka.get("schema_registry_url", "http://localhost:8081"),
    )


def is_uri(path: str | Path) -> bool:
    raw = str(path)
    return "://" in raw or raw.startswith("dbfs:")


def resolve_path(path: str | Path) -> str:
    """Resolve local paths relative to the project root; leave URIs untouched."""
    raw = str(path)
    if is_uri(raw):
        return raw.rstrip("/")
    resolved = Path(raw)
    if not resolved.is_absolute():
        resolved = PROJECT_DIR / resolved
    return str(resolved)


def join_path(base: str | Path, *parts: str) -> str:
    base_text = str(base).rstrip("/")
    if is_uri(base_text):
        suffix = "/".join(part.strip("/") for part in parts if part)
        return f"{base_text}/{suffix}" if suffix else base_text
    return str(Path(resolve_path(base_text), *parts))


def read_csv_header(csv_path: str | Path) -> list[str]:
    path = Path(resolve_path(csv_path))
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        return next(reader)


def layer_base_path(config: dict[str, Any], layer: str) -> str:
    paths = config.setdefault("paths", {})
    if layer not in paths:
        raise KeyError(f"Missing paths.{layer} in config")
    return paths[layer]


def layer_table_path(config: dict[str, Any], layer: str, table: str) -> str:
    return join_path(layer_base_path(config, layer), table)


def config_uses_s3(config: dict[str, Any], layers: tuple[str, ...] | None = None) -> bool:
    layers = layers or ("bronze", "clean", "silver", "mapping", "gold")
    paths = config.get("paths", {})
    return any(str(paths.get(layer, "")).startswith(("s3://", "s3a://")) for layer in layers)

