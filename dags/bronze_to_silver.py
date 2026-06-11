"""Airflow DAG for cleaning Bronze parquet into the Silver layer."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

from _common import DEFAULT_ARGS, PIPELINE_ENV, spark_submit_command


with DAG(
    dag_id="olist_bronze_to_silver",
    description="Clean Olist Bronze parquet tables and write standardized Silver parquet.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        **DEFAULT_ARGS,
        "retries": 1,
        "retry_delay": timedelta(minutes=3),
    },
    tags=["olist", "s3", "bronze", "silver", "spark"],
) as dag:
    clean_bronze_to_silver = BashOperator(
        task_id="clean_bronze_to_silver",
        bash_command=spark_submit_command("scripts/silver/bronze_to_silver.py"),
        env=PIPELINE_ENV,
        append_env=True,
        execution_timeout=timedelta(hours=2),
    )
