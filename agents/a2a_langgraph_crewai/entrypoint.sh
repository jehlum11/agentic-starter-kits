#!/bin/sh
# Chooses which A2A server to run (same image, two Deployment variants).
set -e
export PORT="${PORT:-8080}"
export HOME="${HOME:-/home/appuser}"
case "${A2A_ROLE:-crew}" in
  crew)
    exec python crew_a2a_server.py
    ;;
  langgraph)
    exec python langgraph_a2a_server.py
    ;;
  *)
    echo "A2A_ROLE must be 'crew' or 'langgraph', got: ${A2A_ROLE}" >&2
    exit 1
    ;;
esac
