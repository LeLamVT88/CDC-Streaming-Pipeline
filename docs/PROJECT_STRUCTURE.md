# Project structure

The project is split into a DWH core and optional source adapters.

```text
db/seed/                         Local raw CSV source files
configs/app_config.yaml          Layer paths, datasets, Spark, S3, optional source configs
dwh/                             Core lakehouse package
  config.py                      Config, path, and environment override helpers
  datasets.py                    Dataset registry helpers
  io.py                          Spark session and parquet/S3 IO helpers
  pipeline.py                    Bronze, clean, silver stage functions
  athena.py                      Athena DDL generator
  transforms/olist.py            Clean and silver rules for Olist data
  transforms/mapping.py          Conformed facts and dimensions
  transforms/gold.py             Analytical marts
scripts/lakehouse.py             Core DWH CLI
scripts/inspect_lakehouse.py     Layer inspection and DQ checks
airflows/dags/s3_lakehouse_dwh_dag.py
docker/docker-compose.yml        Airflow-only orchestration stack
sources/cdc/                     Optional MySQL/Debezium/Kafka source adapter
docker/docker-compose.cdc.yml    Optional CDC infrastructure stack
```

## Core flow

```text
CSV/raw source
  -> bronze: raw landed tables with ingestion metadata
  -> clean: type normalization and data quality standardization
  -> silver: keyed, deduplicated, curated tables
  -> mapping: conformed dimensions and facts
  -> gold: business-facing marts
```

## CLI

Use the root wrapper:

```bash
./pipeline.sh setup
./pipeline.sh validate
./pipeline.sh bronze
./pipeline.sh clean
./pipeline.sh silver
./pipeline.sh mapping
./pipeline.sh gold
./pipeline.sh all
./pipeline.sh inspect --validate
./pipeline.sh athena-ddl
```

On Windows PowerShell, call Python directly after setup:

```powershell
.\.venv\Scripts\python.exe scripts\lakehouse.py --mode all
.\.venv\Scripts\python.exe scripts\inspect_lakehouse.py --validate
```

## Adding a new source such as crawl data

1. Land raw crawl files under a new source prefix or point `DWH_RAW_PATH` to the source.
2. Add dataset entries in `configs/app_config.yaml`.
3. Add a domain-specific clean transform in `dwh/transforms/` if generic trim/null handling is not enough.
4. Add mapping/gold models only when the table needs to become a fact, dimension, or mart.

The DWH core only assumes that source adapters write compatible raw data into bronze or provide CSV files for the bronze step.

