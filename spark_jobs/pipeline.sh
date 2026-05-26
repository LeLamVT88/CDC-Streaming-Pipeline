#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ $1${NC}"; }
ok() { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }

docker_running() {
    docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$1"
}

setup() {
    info "Setup Python environment"
    if [ ! -d "$PROJECT_DIR/.venv" ]; then
        python3 -m venv "$PROJECT_DIR/.venv"
        source "$PROJECT_DIR/.venv/bin/activate"
        pip install -q pyspark sqlalchemy pymysql pandas confluent-kafka
        ok "Venv created"
    else
        ok "Venv exists"
    fi
}

start_infra() {
    info "Starting Docker infrastructure"
    cd "$PROJECT_DIR/docker"
    docker-compose up -d
    sleep 15
    ok "Infrastructure started"
    cd "$PROJECT_DIR"
}

stop_infra() {
    info "Stopping Docker"
    cd "$PROJECT_DIR/docker"
    docker-compose down
    ok "Stopped"
    cd "$PROJECT_DIR"
}

seed() {
    info "Seeding MySQL"
    source "$PROJECT_DIR/.venv/bin/activate"
    export PYTHONPATH="$PROJECT_DIR/scripts/ingestion:$PROJECT_DIR:$PYTHONPATH"
    python3 "$PROJECT_DIR/scripts/ingestion/seed_to_mysql.py"
    ok "MySQL seeded"
}

wait_for_connect() {
    info "Waiting for Kafka Connect (localhost:8083)..."
    local i
    for i in $(seq 1 40); do
        if curl -sf http://localhost:8083/ >/dev/null 2>&1; then
            ok "Kafka Connect is ready"
            return 0
        fi
        sleep 5
    done
    warn "Kafka Connect not ready after 200s — check: docker logs kafka-connect --tail 50"
    return 1
}

deploy_connector() {
    info "Deploying Debezium connector"
    if ! docker_running kafka-connect; then
        warn "Container kafka-connect is not running — run: ./pipeline.sh start"
        return 1
    fi
    wait_for_connect || return 1

    if curl -sf http://localhost:8083/connectors 2>/dev/null | grep -q mysql-source-connector; then
        warn "Connector already deployed"
        curl -sf http://localhost:8083/connectors/mysql-source-connector/status | python3 -m json.tool 2>/dev/null || true
        return 0
    fi

    local response http_code
    response=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8083/connectors \
        -H "Content-Type: application/json" \
        -d @"$PROJECT_DIR/kafka/mysql-source-connector.json")
    http_code=$(echo "$response" | tail -1)
    response=$(echo "$response" | sed '$d')

    if [[ "$http_code" =~ ^2 ]]; then
        ok "Connector deployed (HTTP $http_code)"
    else
        warn "Deploy failed (HTTP $http_code)"
        echo "$response"
        return 1
    fi

    sleep 5
    info "Connector status:"
    curl -sf http://localhost:8083/connectors/mysql-source-connector/status | python3 -m json.tool
}

pipeline() {
    info "Running pipeline (silver: CSV → bronze → silver)"
    source "$PROJECT_DIR/.venv/bin/activate"
    export PYTHONPATH="$PROJECT_DIR/scripts/ingestion:$PROJECT_DIR:$PYTHONPATH"
    python3 "$PROJECT_DIR/scripts/pipeline.py" --mode silver
}

silver() {
    pipeline
}

cdc() {
    info "Running CDC ingest (Kafka → bronze)"
    source "$PROJECT_DIR/.venv/bin/activate"
    export PYTHONPATH="$PROJECT_DIR/scripts/ingestion:$PROJECT_DIR:$PYTHONPATH"
    python3 "$PROJECT_DIR/scripts/pipeline.py" --mode cdc "$@"
}

inspect() {
    info "Inspecting data layers"
    source "$PROJECT_DIR/.venv/bin/activate"
    export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
    python3 "$PROJECT_DIR/scripts/inspect_pipeline.py" "$@"
}

clean() {
    warn "Cleaning local parquet data"
    rm -rf "$PROJECT_DIR/data/bronze"/* "$PROJECT_DIR/data/silver"/* "$PROJECT_DIR/checkpoints"/* 2>/dev/null || true
    find "$PROJECT_DIR/data/bronze" -maxdepth 1 -type d -name '*_checkpoint' -exec rm -rf {} + 2>/dev/null || true
    ok "Local data cleaned"
}

full_setup() {
    setup
    start_infra
    seed
    deploy_connector
    ok "Full setup complete"
}

case "${1:-help}" in
    setup) setup ;;
    start) start_infra ;;
    stop) stop_infra ;;
    seed) seed ;;
    deploy-connector) deploy_connector ;;
    pipeline|silver) pipeline ;;
    cdc) shift; cdc "$@" ;;
    inspect) shift; inspect "$@" ;;
    clean) clean ;;
    full-setup) full_setup ;;
    *)
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  setup            Create Python venv and install deps"
        echo "  start            Start Docker infrastructure"
        echo "  stop             Stop Docker infrastructure"
        echo "  seed             Load CSV seed data into MySQL"
        echo "  deploy-connector Deploy Debezium MySQL connector"
        echo "  pipeline|silver  CSV → bronze → silver"
        echo "  cdc              Kafka → bronze (--seed-mysql optional)"
        echo "  inspect          Inspect MySQL/bronze/silver (--validate for DQ)"
        echo "  clean            Remove local bronze/silver/checkpoints only"
        echo "  full-setup       setup + start + seed + deploy-connector"
        ;;
esac
