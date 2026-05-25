"""Debezium connector management for the optional CDC source adapter."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from dwh.datasets import DatasetSpec, table_include_list


def deploy_debezium_connector(config: dict, datasets: list[DatasetSpec], recreate: bool = False) -> None:
    cdc = config.get("source_adapters", {}).get("cdc", {})
    kafka = cdc.get("kafka", {})
    name = kafka.get("connector_name", "mysql-source-connector")
    connect_url = kafka.get("connect_url", "http://localhost:8083").rstrip("/")
    wait_for_connect(connect_url)

    connector_config = build_connector_config(config, datasets)
    exists = http_request("GET", f"{connect_url}/connectors/{name}", ok_statuses={200, 404})
    if exists["status"] == 200 and recreate:
        http_request("DELETE", f"{connect_url}/connectors/{name}", ok_statuses={204, 404})
        exists = {"status": 404, "body": ""}

    if exists["status"] == 200:
        print(f"[cdc:debezium] updating connector {name}")
        http_request("PUT", f"{connect_url}/connectors/{name}/config", connector_config, ok_statuses={200, 201})
    else:
        print(f"[cdc:debezium] creating connector {name}")
        payload = {"name": name, "config": connector_config}
        http_request("POST", f"{connect_url}/connectors", payload, ok_statuses={200, 201})

    time.sleep(3)
    status = http_request("GET", f"{connect_url}/connectors/{name}/status", ok_statuses={200})
    print(json.dumps(json.loads(status["body"]), indent=2))


def build_connector_config(config: dict, datasets: list[DatasetSpec]) -> dict[str, str]:
    cdc = config.get("source_adapters", {}).get("cdc", {})
    mysql = cdc.get("mysql", {})
    debezium = cdc.get("debezium", {})
    database_host = debezium.get("database_hostname", "mysql")
    database_port = str(debezium.get("database_port", mysql.get("port", 3306)))
    database = mysql.get("database", "app")

    return {
        "connector.class": debezium.get("connector_class", "io.debezium.connector.mysql.MySqlConnector"),
        "tasks.max": "1",
        "database.hostname": database_host,
        "database.port": database_port,
        "database.user": str(mysql.get("user", "root")),
        "database.password": str(mysql.get("password", "root")),
        "database.server.id": str(debezium.get("server_id", "184054")),
        "database.include.list": database,
        "table.include.list": table_include_list(config, datasets),
        "topic.prefix": debezium.get("topic_prefix", "cdc"),
        "schema.history.internal.kafka.bootstrap.servers": debezium.get(
            "schema_history_bootstrap_servers", "kafka:9092"
        ),
        "schema.history.internal.kafka.topic": f"schemahistory.{database}",
        "include.schema.changes": str(debezium.get("include_schema_changes", "false")).lower(),
        "snapshot.mode": debezium.get("snapshot_mode", "initial"),
        "tombstones.on.delete": str(debezium.get("tombstones_on_delete", "false")).lower(),
        "decimal.handling.mode": debezium.get("decimal_handling_mode", "string"),
        "database.allowPublicKeyRetrieval": "true",
        "key.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "key.converter.schemas.enable": "false",
        "value.converter.schemas.enable": "false",
    }


def wait_for_connect(connect_url: str, attempts: int = 40, delay_seconds: int = 5) -> None:
    for attempt in range(1, attempts + 1):
        try:
            http_request("GET", connect_url, ok_statuses={200})
            print("[cdc:debezium] Kafka Connect is ready")
            return
        except RuntimeError:
            if attempt == attempts:
                raise
            time.sleep(delay_seconds)


def http_request(method: str, url: str, payload: dict | None = None, ok_statuses: set[int] | None = None) -> dict:
    ok_statuses = ok_statuses or {200}
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            status = response.getcode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        status = exc.code
    except Exception as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc

    if status not in ok_statuses:
        raise RuntimeError(f"{method} {url} returned HTTP {status}: {body[:500]}")
    return {"status": status, "body": body}

