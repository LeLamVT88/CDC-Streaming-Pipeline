"""Athena SQL execution helpers for Airflow DAGs."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time

from _common import ATHENA_OUTPUT_LOCATION, ATHENA_WORKGROUP, AWS_REGION


TERMINAL_QUERY_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}


def split_sql_statements(sql_text):
    """Split controlled DDL files without breaking quoted S3 locations."""
    statements = []
    current = []
    in_single_quote = False
    index = 0

    while index < len(sql_text):
        character = sql_text[index]

        if character == "'":
            current.append(character)
            if in_single_quote and index + 1 < len(sql_text) and sql_text[index + 1] == "'":
                current.append(sql_text[index + 1])
                index += 2
                continue
            in_single_quote = not in_single_quote
        elif character == ";" and not in_single_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(character)

        index += 1

    trailing_statement = "".join(current).strip()
    if trailing_statement:
        statements.append(trailing_statement)

    return statements


def wait_for_query(client, query_execution_id, timeout_seconds=900):
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        execution = client.get_query_execution(QueryExecutionId=query_execution_id)["QueryExecution"]
        status = execution["Status"]
        state = status["State"]

        if state in TERMINAL_QUERY_STATES:
            if state != "SUCCEEDED":
                reason = status.get("StateChangeReason", "No failure reason returned by Athena")
                raise RuntimeError(f"Athena query {query_execution_id} ended in {state}: {reason}")
            return

        time.sleep(2)

    client.stop_query_execution(QueryExecutionId=query_execution_id)
    raise TimeoutError(f"Athena query {query_execution_id} exceeded {timeout_seconds} seconds")


def execute_sql_file(sql_path):
    if os.environ.get("ATHENA_SKIP_EXECUTION", "false").lower() in {"1", "true", "yes"}:
        path = Path(sql_path)
        statements = split_sql_statements(path.read_text(encoding="utf-8"))
        logging.info("Skipping %s Athena statements from %s because ATHENA_SKIP_EXECUTION is true", len(statements), path)
        return

    import boto3

    path = Path(sql_path)
    statements = split_sql_statements(path.read_text(encoding="utf-8"))
    if not statements:
        raise ValueError(f"No SQL statements found in {path}")

    client = boto3.client("athena", region_name=os.environ.get("AWS_DEFAULT_REGION", AWS_REGION))
    workgroup = os.environ.get("ATHENA_WORKGROUP", ATHENA_WORKGROUP)
    output_location = os.environ.get("ATHENA_OUTPUT_LOCATION", ATHENA_OUTPUT_LOCATION)

    for number, statement in enumerate(statements, start=1):
        first_line = statement.splitlines()[0]
        logging.info("Running Athena statement %s/%s from %s: %s", number, len(statements), path.name, first_line)
        response = client.start_query_execution(
            QueryString=statement,
            WorkGroup=workgroup,
            ResultConfiguration={"OutputLocation": output_location},
        )
        wait_for_query(client, response["QueryExecutionId"])
