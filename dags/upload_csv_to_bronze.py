"""Airflow DAG for uploading seed CSV files to the Bronze S3 layer."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

from _common import DEFAULT_ARGS, PIPELINE_ENV, project_command


with DAG(
    dag_id="olist_upload_csv_to_bronze",
    description="Convert Olist seed CSV files to parquet and upload them to the Bronze S3 layer.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        **DEFAULT_ARGS,
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["olist", "s3", "bronze"],
) as dag:
    upload_seed_csv_to_bronze = BashOperator(
        task_id="upload_seed_csv_to_bronze",
        bash_command=project_command("python scripts/bronze/upload_csv_to_bronze.py"),
        env=PIPELINE_ENV,
        append_env=True,
    )
