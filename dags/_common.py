"""Shared helpers for Olist Airflow DAGs."""

from __future__ import annotations

import os
import shlex
from pathlib import Path


AIRFLOW_ROOT = Path(os.environ.get("AIRFLOW_PROJECT_ROOT", "/opt/airflow"))
LOCAL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AIRFLOW_ROOT if (AIRFLOW_ROOT / "scripts").exists() else LOCAL_ROOT
CONFIG_PATH = PROJECT_ROOT / "configs" / "app_config.yaml"


def parse_scalar(value):
    value = value.strip()
    if value in {"null", "None", ""}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    return value


def load_simple_yaml(path: Path) -> dict:
    config = {}
    current_section = None

    with path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue

            if not line.startswith(" ") and line.endswith(":"):
                current_section = line[:-1]
                config[current_section] = {}
                continue

            if current_section is None:
                continue

            stripped = line.strip()
            if stripped.startswith("- "):
                if not isinstance(config[current_section], list):
                    config[current_section] = []
                config[current_section].append(parse_scalar(stripped[2:]))
                continue

            if ":" in stripped:
                key, value = stripped.split(":", 1)
                config[current_section][key.strip()] = parse_scalar(value)

    return config


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}

    try:
        import yaml
    except ImportError:
        return load_simple_yaml(CONFIG_PATH)

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def get_nested(config: dict, *keys, default=None):
    value = config
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


CONFIG = load_config()
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", get_nested(CONFIG, "aws", "region", default="ap-southeast-1"))
S3_BUCKET = os.environ.get("S3_BUCKET") or get_nested(CONFIG, "aws", "bucket", default="olist-lakehouse-data")
BRONZE_PREFIX = os.environ.get("BRONZE_PREFIX", get_nested(CONFIG, "s3", "bronze_prefix", default="bronze"))
SILVER_PREFIX = os.environ.get("SILVER_PREFIX", get_nested(CONFIG, "s3", "silver_prefix", default="silver"))
GOLD_PREFIX = os.environ.get("GOLD_PREFIX", get_nested(CONFIG, "s3", "gold_prefix", default="gold"))

BRONZE_PATH = os.environ.get(
    "BRONZE_PATH",
    get_nested(CONFIG, "s3", "bronze_uri", default=f"s3a://{S3_BUCKET}/{BRONZE_PREFIX}"),
)
SILVER_PATH = os.environ.get(
    "SILVER_PATH",
    get_nested(CONFIG, "s3", "silver_uri", default=f"s3a://{S3_BUCKET}/{SILVER_PREFIX}"),
)
GOLD_PATH = os.environ.get(
    "GOLD_PATH",
    get_nested(CONFIG, "s3", "gold_uri", default=f"s3a://{S3_BUCKET}/{GOLD_PREFIX}"),
)
HADOOP_AWS_PACKAGE = os.environ.get(
    "HADOOP_AWS_PACKAGE",
    get_nested(CONFIG, "spark", "hadoop_aws_package", default="org.apache.hadoop:hadoop-aws:3.4.1"),
)
HADOOP_AWS_JARS = os.environ.get("HADOOP_AWS_JARS")
SPARK_JARS_REPOSITORIES = os.environ.get("SPARK_JARS_REPOSITORIES", "https://repo.maven.apache.org/maven2")
S3_ENDPOINT = os.environ.get(
    "S3_ENDPOINT",
    get_nested(CONFIG, "spark", "s3_endpoint", default=f"s3.{AWS_REGION}.amazonaws.com"),
)
ATHENA_WORKGROUP = os.environ.get(
    "ATHENA_WORKGROUP",
    get_nested(CONFIG, "athena", "workgroup", default="primary"),
)
ATHENA_OUTPUT_LOCATION = os.environ.get(
    "ATHENA_OUTPUT_LOCATION",
    get_nested(CONFIG, "athena", "output_location", default=f"s3://{S3_BUCKET}/athena-results/"),
)
ATHENA_SKIP_EXECUTION = os.environ.get("ATHENA_SKIP_EXECUTION", "false")
SEED_DIR = os.environ.get("SEED_DIR", str(PROJECT_ROOT / get_nested(CONFIG, "paths", "seed", default="db/seed")))

DEFAULT_ARGS = {
    "owner": "data-platform",
    "depends_on_past": False,
}

PIPELINE_ENV = {
    "AIRFLOW_PROJECT_ROOT": str(PROJECT_ROOT),
    "PYTHONPATH": str(PROJECT_ROOT),
    "AWS_DEFAULT_REGION": AWS_REGION,
    "S3_BUCKET": S3_BUCKET,
    "BRONZE_PREFIX": BRONZE_PREFIX,
    "SILVER_PREFIX": SILVER_PREFIX,
    "GOLD_PREFIX": GOLD_PREFIX,
    "BRONZE_PATH": BRONZE_PATH,
    "SILVER_PATH": SILVER_PATH,
    "GOLD_PATH": GOLD_PATH,
    "HADOOP_AWS_PACKAGE": HADOOP_AWS_PACKAGE,
    "SPARK_JARS_REPOSITORIES": SPARK_JARS_REPOSITORIES,
    "S3_ENDPOINT": S3_ENDPOINT,
    "ATHENA_WORKGROUP": ATHENA_WORKGROUP,
    "ATHENA_OUTPUT_LOCATION": ATHENA_OUTPUT_LOCATION,
    "ATHENA_SKIP_EXECUTION": ATHENA_SKIP_EXECUTION,
    "SEED_DIR": SEED_DIR,
}
if HADOOP_AWS_JARS:
    PIPELINE_ENV["HADOOP_AWS_JARS"] = HADOOP_AWS_JARS


def project_command(command: str) -> str:
    return f"cd {shlex.quote(str(PROJECT_ROOT))} && {command}"


def uses_s3(*paths: str) -> bool:
    return any(str(path).startswith(("s3://", "s3a://")) for path in paths)


def spark_submit_command(script_path: str) -> str:
    spark_options = []
    if uses_s3(BRONZE_PATH, SILVER_PATH, GOLD_PATH):
        spark_options.extend(
            [
                "--conf",
                f"spark.hadoop.fs.s3a.endpoint.region={AWS_REGION}",
            ]
        )
        if S3_ENDPOINT:
            spark_options.extend(["--conf", f"spark.hadoop.fs.s3a.endpoint={S3_ENDPOINT}"])
        if HADOOP_AWS_JARS:
            spark_options.extend(["--jars", HADOOP_AWS_JARS])
        else:
            spark_options.extend(["--packages", HADOOP_AWS_PACKAGE])
            if SPARK_JARS_REPOSITORIES:
                spark_options.extend(["--repositories", SPARK_JARS_REPOSITORIES])

    quoted_options = " ".join(shlex.quote(str(option)) for option in spark_options)
    command_parts = ["spark-submit"]
    if quoted_options:
        command_parts.append(quoted_options)
    command_parts.append(shlex.quote(script_path))
    return project_command(" ".join(command_parts))
