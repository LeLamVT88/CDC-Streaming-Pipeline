"""Airflow DAG for the Silver -> Gold Spark transformation."""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="olist_silver_to_gold",
    description="Build Olist Gold dimensions, facts, and marts from S3 Silver parquet.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        "owner": "data-platform",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["s3", "silver", "gold", "spark"],
) as dag:
    build_gold_models = BashOperator(
        task_id="build_gold_models",
        bash_command="cd /opt/airflow && python scripts/gold/create_fact_table.py",
    )
