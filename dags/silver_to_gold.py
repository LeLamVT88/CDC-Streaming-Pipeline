"""Airflow DAG for the Silver -> Gold Spark transformation."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

from _common import DEFAULT_ARGS, PIPELINE_ENV, spark_submit_command


with DAG(
    dag_id="olist_silver_to_gold",
    description="Build Olist Gold dimensions, facts, and marts from S3 Silver parquet.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        **DEFAULT_ARGS,
        "retries": 1,
        "retry_delay": timedelta(minutes=3),
    },
    tags=["olist", "s3", "silver", "gold", "spark"],
) as dag:
    build_gold_layer = BashOperator(
        task_id="build_gold_layer",
        bash_command=spark_submit_command("scripts/gold/create_fact_table.py"),
        env=PIPELINE_ENV,
        append_env=True,
        execution_timeout=timedelta(hours=2),
    )
