# Deploy Stack (Local)

This folder contains the Docker Compose setup for the local stack:
- MySQL
- Postgres (Airflow metadata)
- pgAdmin
- Kafka (KRaft mode)
- Kafka UI
- Airflow 3 (LocalExecutor)

## Quick Start

```bash
cd deploy
docker compose up -d
```

## UIs

- Airflow: http://localhost:8080
- Kafka UI: http://localhost:8085
- pgAdmin: http://localhost:5050

## Default Credentials

- Airflow: `admin` / `admin`
- pgAdmin: `admin@local` / `admin`
- MySQL: `root` / `root`

## Volumes

Named volumes are used to persist data:
- `mysql_data`
- `postgres_data`
- `kafka_data`

## Notes

- If ports are in use, edit [docker-compose.yml](docker-compose.yml).
- Airflow uses Postgres only for metadata; MySQL is independent.
