#!/usr/bin/env bash
set -o errexit

# Force Railway redeploy - 2026-07-13-12-42
echo "=== Dalal Platform Startup ==="
export PYTHONPATH=/app:$PYTHONPATH

# Check if settings.py contains properties app
if [ -f /app/dalal_project/settings.py ]; then
    echo "Settings.py contains 'properties': $(grep -c 'properties' /app/dalal_project/settings.py || echo '0')"
    echo "Settings.py contains 'INSTALLED_APPS': $(grep -c 'INSTALLED_APPS' /app/dalal_project/settings.py || echo '0')"
else
    echo "ERROR: settings.py not found"
fi

# Check if properties app exists
if [ -d /app/properties ]; then
    echo "Properties app exists: True"
else
    echo "ERROR: Properties app not found"
fi

exec python run_server.py
