"""Airflow DAG for registering Gold Parquet tables and BI views in Athena."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from _athena import execute_sql_file
from _common import DEFAULT_ARGS, PROJECT_ROOT

ATHENA_SQL_DIR = PROJECT_ROOT / "scripts" / "athena"


with DAG(
    dag_id="olist_athena_refresh",
    description="Register Olist Gold Parquet tables and Power BI views in Athena.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    default_args={
        **DEFAULT_ARGS,
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["olist", "s3", "gold", "athena", "power-bi"],
) as dag:
    create_tables = PythonOperator(
        task_id="create_gold_external_tables",
        python_callable=execute_sql_file,
        op_kwargs={"sql_path": str(ATHENA_SQL_DIR / "create_tables.sql")},
    )

    create_views = PythonOperator(
        task_id="create_power_bi_views",
        python_callable=execute_sql_file,
        op_kwargs={"sql_path": str(ATHENA_SQL_DIR / "create_views.sql")},
    )

    create_tables >> create_views
