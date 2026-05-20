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
    cd "$PROJECT_DIR/scripts/py"
    python3 seed_to_mysql.py
    cd "$PROJECT_DIR"
    ok "MySQL seeded"
}

deploy_connector() {
    info "Deploying Debezium connector"
    if curl -s http://localhost:8083/connectors | grep -q mysql-source-connector; then
        warn "Connector already deployed"
        return
    fi
    curl -X POST http://localhost:8083/connectors \
        -H "Content-Type: application/json" \
        -d @"$PROJECT_DIR/kafka/mysql-source-connector.json" 2>/dev/null
    sleep 5
    ok "Connector deployed"
}

pipeline() {
    info "Running pipeline"
    source "$PROJECT_DIR/.venv/bin/activate"
    cd "$PROJECT_DIR/scripts/py"
    python3 pipeline_orchestration.py
    cd "$PROJECT_DIR"
}

clean() {
    warn "Cleaning data"
    rm -rf "$PROJECT_DIR/data/bronze"/* "$PROJECT_DIR/data/silver"/* "$PROJECT_DIR/checkpoints"/* 2>/dev/null || true
    ok "Cleaned"
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
    pipeline) pipeline ;;
    clean) clean ;;
    full-setup) full_setup ;;
    *)
        echo "Usage: $0 {setup|start|stop|seed|deploy-connector|pipeline|clean|full-setup}"
        ;;
esac
