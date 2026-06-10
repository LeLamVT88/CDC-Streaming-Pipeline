"""End-to-end Airflow DAG for the Olist Medallion Lakehouse pipeline."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from _athena import execute_sql_file
from _common import DEFAULT_ARGS, PIPELINE_ENV, PROJECT_ROOT, project_command


ATHENA_SQL_DIR = PROJECT_ROOT / "scripts" / "athena"


with DAG(
    dag_id="olist_medallion_pipeline",
    description="Run the full Olist Medallion flow: seed CSV -> Bronze -> Silver -> Gold -> Athena.",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        **DEFAULT_ARGS,
        "retries": 1,
        "retry_delay": timedelta(minutes=3),
    },
    tags=["olist", "medallion", "bronze", "silver", "gold", "athena"],
) as dag:
    upload_seed_csv_to_bronze = BashOperator(
        task_id="upload_seed_csv_to_bronze",
        bash_command=project_command("python scripts/bronze/upload_csv_to_bronze.py"),
        env=PIPELINE_ENV,
        append_env=True,
    )

    clean_bronze_to_silver = BashOperator(
        task_id="clean_bronze_to_silver",
        bash_command=project_command("python scripts/silver/bronze_to_silver.py"),
        env=PIPELINE_ENV,
        append_env=True,
        execution_timeout=timedelta(hours=2),
    )

    build_gold_layer = BashOperator(
        task_id="build_gold_layer",
        bash_command=project_command("python scripts/gold/create_fact_table.py"),
        env=PIPELINE_ENV,
        append_env=True,
        execution_timeout=timedelta(hours=2),
    )

    create_gold_external_tables = PythonOperator(
        task_id="create_gold_external_tables",
        python_callable=execute_sql_file,
        op_kwargs={"sql_path": str(ATHENA_SQL_DIR / "create_tables.sql")},
    )

    create_power_bi_views = PythonOperator(
        task_id="create_power_bi_views",
        python_callable=execute_sql_file,
        op_kwargs={"sql_path": str(ATHENA_SQL_DIR / "create_views.sql")},
    )

    upload_seed_csv_to_bronze >> clean_bronze_to_silver >> build_gold_layer
    build_gold_layer >> create_gold_external_tables >> create_power_bi_views
