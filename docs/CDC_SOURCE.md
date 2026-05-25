# Optional CDC source adapter

MySQL, Kafka, Debezium, Kafka Connect, and CDC-specific scripts are isolated from the DWH core. Treat CDC as one source adapter that lands data into bronze; the DWH then continues with `clean -> silver -> mapping -> gold`.

## Start CDC infrastructure

```bash
./pipeline.sh setup-cdc
./pipeline.sh start-cdc
```

Service URLs:

```text
Airflow:         http://localhost:8080  admin/admin
Kafka UI:        http://localhost:8085
phpMyAdmin:      http://localhost:8082  root/root
Schema Registry: http://localhost:8081
Kafka Connect:   http://localhost:8083
```

## Run CDC source adapter

```bash
./pipeline.sh cdc --mode seed
./pipeline.sh cdc --mode deploy-connector
./pipeline.sh cdc --mode bronze
```

Or run all CDC source steps:

```bash
./pipeline.sh cdc --mode all
```

Then continue with the core DWH:

```bash
./pipeline.sh clean
./pipeline.sh silver
./pipeline.sh mapping
./pipeline.sh gold
```

## Where CDC lives

```text
sources/cdc/seed_to_mysql.py
sources/cdc/debezium.py
sources/cdc/kafka_to_bronze.py
sources/cdc/mysql-source-connector.json
sources/cdc/init.sql
docker/docker-compose.cdc.yml
requirements-cdc.txt
```

For future crawl data, create a sibling adapter such as `sources/crawl/` that lands raw data into bronze or provides CSV files for the core bronze step.

