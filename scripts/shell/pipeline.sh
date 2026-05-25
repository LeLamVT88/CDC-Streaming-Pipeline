#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
COMPOSE_FILES=(-f "$PROJECT_DIR/docker/docker-compose.yml")

info() { printf "\033[0;34m[info]\033[0m %s\n" "$1"; }
ok() { printf "\033[0;32m[ok]\033[0m %s\n" "$1"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$1"; }

compose() {
    if docker compose version >/dev/null 2>&1; then
        docker compose "${COMPOSE_FILES[@]}" "$@"
    else
        docker-compose "${COMPOSE_FILES[@]}" "$@"
    fi
}

compose_with_cdc() {
    if docker compose version >/dev/null 2>&1; then
        docker compose -f "$PROJECT_DIR/docker/docker-compose.yml" -f "$PROJECT_DIR/docker/docker-compose.cdc.yml" "$@"
    else
        docker-compose -f "$PROJECT_DIR/docker/docker-compose.yml" -f "$PROJECT_DIR/docker/docker-compose.cdc.yml" "$@"
    fi
}

python_bin() {
    if [ -x "$VENV_DIR/Scripts/python.exe" ]; then
        printf "%s" "$VENV_DIR/Scripts/python.exe"
    elif [ -x "$VENV_DIR/bin/python" ]; then
        printf "%s" "$VENV_DIR/bin/python"
    elif command -v python >/dev/null 2>&1; then
        printf "%s" "python"
    else
        printf "%s" "python3"
    fi
}

activate_env() {
    export PYTHONPATH="$PROJECT_DIR:${PYTHONPATH:-}"
}

setup() {
    info "Setting up Python environment"
    if [ ! -d "$VENV_DIR" ]; then
        python -m venv "$VENV_DIR" 2>/dev/null || python3 -m venv "$VENV_DIR"
    fi
    "$(python_bin)" -m pip install --upgrade pip
    "$(python_bin)" -m pip install -r "$PROJECT_DIR/requirements.txt"
    ok "Core DWH environment ready"
}

setup_cdc() {
    setup
    "$(python_bin)" -m pip install -r "$PROJECT_DIR/requirements-cdc.txt"
    ok "CDC source dependencies ready"
}

start_infra() {
    info "Starting Airflow orchestration services"
    compose up -d --build
    ok "Airflow services started"
}

start_cdc_infra() {
    info "Starting Airflow + optional CDC source services"
    compose_with_cdc up -d --build
    ok "Airflow and CDC services started"
}

stop_infra() {
    info "Stopping services"
    compose_with_cdc down
    ok "Services stopped"
}

lakehouse() {
    activate_env
    "$(python_bin)" "$PROJECT_DIR/scripts/lakehouse.py" "$@"
}

cdc_source() {
    activate_env
    "$(python_bin)" "$PROJECT_DIR/scripts/cdc_source.py" "$@"
}

inspect() {
    activate_env
    "$(python_bin)" "$PROJECT_DIR/scripts/inspect_lakehouse.py" "$@"
}

clean_local() {
    warn "Removing generated local lakehouse data and Athena DDL"
    rm -rf "$PROJECT_DIR/data/lakehouse"
    rm -f "$PROJECT_DIR/docs/athena_lakehouse_ddl.sql"
    mkdir -p "$PROJECT_DIR/data/lakehouse/bronze" \
        "$PROJECT_DIR/data/lakehouse/clean" \
        "$PROJECT_DIR/data/lakehouse/silver" \
        "$PROJECT_DIR/data/lakehouse/mapping" \
        "$PROJECT_DIR/data/lakehouse/gold" \
        "$PROJECT_DIR/data/lakehouse/checkpoints"
    ok "Generated local lakehouse data removed"
}

case "${1:-help}" in
    setup) shift; setup "$@" ;;
    setup-cdc) shift; setup_cdc "$@" ;;
    start) shift; start_infra "$@" ;;
    start-cdc) shift; start_cdc_infra "$@" ;;
    stop) shift; stop_infra "$@" ;;
    validate) shift; lakehouse --mode validate "$@" ;;
    bronze) shift; lakehouse --mode bronze "$@" ;;
    clean) shift; lakehouse --mode clean "$@" ;;
    silver) shift; lakehouse --mode silver "$@" ;;
    mapping) shift; lakehouse --mode mapping "$@" ;;
    gold) shift; lakehouse --mode gold "$@" ;;
    all|pipeline) shift; lakehouse --mode all "$@" ;;
    athena-ddl) shift; lakehouse --mode athena-ddl "$@" ;;
    inspect) shift; inspect "$@" ;;
    cdc) shift; cdc_source "$@" ;;
    clean-local) shift; clean_local "$@" ;;
    *)
        cat <<USAGE
Usage: ./pipeline.sh <command> [args]

Core DWH:
  setup          Create/update .venv and install core requirements
  start          Start Airflow only
  validate       Validate config and raw CSV files
  bronze         Load raw CSV files into bronze
  clean          Transform bronze into clean
  silver         Transform clean into silver
  mapping        Build conformed facts and dimensions
  gold           Build analytical marts
  all            Run bronze -> clean -> silver -> mapping -> gold
  athena-ddl     Generate Athena external table DDL
  inspect        Inspect lakehouse layers and optional DQ metrics
  clean-local    Remove generated local lakehouse data

Optional CDC source:
  setup-cdc      Install core + CDC requirements
  start-cdc      Start Airflow plus MySQL/Kafka/Debezium services
  cdc            Run CDC source adapter: --mode seed|deploy-connector|bronze|all

Examples:
  ./pipeline.sh all --tables customers,orders,order_items
  ./pipeline.sh inspect --validate
  ./pipeline.sh setup-cdc
  ./pipeline.sh start-cdc
  ./pipeline.sh cdc --mode all
USAGE
        ;;
esac

