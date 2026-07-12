#!/usr/bin/env bash
set -o errexit

# Force Railway redeploy - 2026-07-05-13-38
echo "=== Dalal Platform Startup ==="
export PYTHONPATH=/app:$PYTHONPATH
exec python run_server.py
