#!/usr/bin/env bash
set -o errexit

# Force Railway redeploy - 2026-07-12-16-26
echo "=== Dalal Platform Startup ==="
export PYTHONPATH=/app:$PYTHONPATH

# Check if settings.py contains properties app
if [ -f /app/dalal_project/settings.py ]; then
    echo "Settings.py contains 'properties': $(grep -c 'properties' /app/dalal_project/settings.py || echo '0')"
    echo "Settings.py contains 'INSTALLED_APPS': $(grep -c 'INSTALLED_APPS' /app/dalal_project/settings.py || echo '0')"
fi

exec python run_server.py
