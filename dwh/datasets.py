"""Dataset registry loaded from project configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dwh.config import join_path, read_csv_header, resolve_path


@dataclass(frozen=True)
class DatasetSpec:
    source: str
    target: str
    label: str
    primary_key: tuple[str, ...]
    columns: tuple[str, ...]
    partition_by: tuple[str, ...] = ()
    domain: str = "default"
    enabled: bool = True

    @property
    def csv_name(self) -> str:
        return f"{self.source}.csv"

    def cdc_topic(self, topic_prefix: str) -> str:
        return f"{topic_prefix.rstrip('.')}.{self.source}"


def load_datasets(config: dict, include: Iterable[str] | None = None) -> list[DatasetSpec]:
    """Load enabled dataset specs from config, optionally filtered by source or target name."""
    include_set = {item.strip() for item in include or [] if item.strip()}
    raw_dir = resolve_path(config["paths"].get("raw", config["paths"].get("seed", "db/seed")))
    specs: list[DatasetSpec] = []

    for item in config.get("datasets", []):
        if not item.get("enabled", True):
            continue

        source = item["source"]
        target = item.get("target", source)
        if include_set and source not in include_set and target not in include_set:
            continue

        columns = item.get("columns")
        if not columns:
            columns = read_csv_header(Path(raw_dir) / f"{source}.csv")

        specs.append(
            DatasetSpec(
                source=source,
                target=target,
                label=item.get("label", target.replace("_", " ").title()),
                primary_key=tuple(item.get("primary_key", [])),
                columns=tuple(columns),
                partition_by=tuple(item.get("partition_by", [])),
                domain=item.get("domain", "default"),
                enabled=item.get("enabled", True),
            )
        )

    if include_set and not specs:
        raise ValueError(f"No configured datasets matched: {', '.join(sorted(include_set))}")
    return specs


def table_include_list(config: dict, datasets: Iterable[DatasetSpec]) -> str:
    cdc = config.get("source_adapters", {}).get("cdc", {})
    database = cdc.get("mysql", {}).get("database", "app")
    return ",".join(f"{database}.{spec.source}" for spec in datasets)


def raw_csv_path(config: dict, spec: DatasetSpec) -> str:
    return join_path(config["paths"].get("raw", config["paths"].get("seed", "db/seed")), spec.csv_name)


def bronze_path(config: dict, spec: DatasetSpec) -> str:
    return join_path(config["paths"]["bronze"], spec.source)


def clean_path(config: dict, spec: DatasetSpec) -> str:
    return join_path(config["paths"]["clean"], spec.target)


def silver_path(config: dict, spec: DatasetSpec) -> str:
    return join_path(config["paths"]["silver"], spec.target)

