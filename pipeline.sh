#!/bin/bash
# Convenience wrapper - delegates to scripts/shell/pipeline.sh
exec "$(dirname "$0")/scripts/shell/pipeline.sh" "$@"

