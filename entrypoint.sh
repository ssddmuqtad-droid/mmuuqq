#!/usr/bin/env bash
set -o errexit

echo "=== Dalal Platform Startup ==="
exec python run_server.py
