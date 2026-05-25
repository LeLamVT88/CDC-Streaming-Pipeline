"""Airflow DAG for CSV bronze -> clean -> silver -> mapping -> gold."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/s3-lakehouse-dwh"
PYTHON = "python"

PIPELINE_ENV = {
    "DWH_CONFIG": f"{PROJECT_DIR}/configs/app_config.yaml",
    "PYTHONPATH": PROJECT_DIR,
}


def lakehouse_cmd(args: str) -> str:
    return f"cd {PROJECT_DIR} && {PYTHON} scripts/lakehouse.py {args}"


with DAG(
    dag_id="s3_lakehouse_dwh",
    description="Build the lakehouse DWH layers: bronze, clean, silver, mapping, and gold.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        "owner": "data-platform",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["s3", "lakehouse", "dwh", "spark"],
) as dag:
    validate_config = BashOperator(
        task_id="validate_config",
        bash_command=lakehouse_cmd("--mode validate"),
        env=PIPELINE_ENV,
    )

    bronze_from_csv = BashOperator(
        task_id="bronze_from_csv",
        bash_command=lakehouse_cmd("--mode bronze"),
        env=PIPELINE_ENV,
    )

    clean_from_bronze = BashOperator(
        task_id="clean_from_bronze",
        bash_command=lakehouse_cmd("--mode clean"),
        env=PIPELINE_ENV,
    )

    silver_from_clean = BashOperator(
        task_id="silver_from_clean",
        bash_command=lakehouse_cmd("--mode silver"),
        env=PIPELINE_ENV,
    )

    build_mapping = BashOperator(
        task_id="build_mapping",
        bash_command=lakehouse_cmd("--mode mapping"),
        env=PIPELINE_ENV,
    )

    build_gold = BashOperator(
        task_id="build_gold",
        bash_command=lakehouse_cmd("--mode gold"),
        env=PIPELINE_ENV,
    )

    generate_athena_ddl = BashOperator(
        task_id="generate_athena_ddl",
        bash_command=lakehouse_cmd("--mode athena-ddl --skip-missing"),
        env=PIPELINE_ENV,
    )

    validate_config >> bronze_from_csv >> clean_from_bronze >> silver_from_clean >> build_mapping >> build_gold >> generate_athena_ddl

