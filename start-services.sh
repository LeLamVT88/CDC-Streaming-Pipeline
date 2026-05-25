#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$PROJECT_ROOT/scripts/shell/pipeline.sh" start "$@"

cat <<URLS

Services:
  Airflow: http://localhost:8080 (admin/admin)

To start the optional CDC source stack:
  ./pipeline.sh start-cdc

URLS

