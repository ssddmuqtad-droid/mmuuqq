#!/usr/bin/env bash
set -o errexit

# Force Railway redeploy - 2026-07-12-16-59
echo "=== Dalal Platform Startup ==="
export PYTHONPATH=/app:$PYTHONPATH

# Check if settings_production.py contains properties app
if [ -f /app/dalal_project/settings_production.py ]; then
    echo "Settings_production.py contains 'properties': $(grep -c 'properties' /app/dalal_project/settings_production.py || echo '0')"
    echo "Settings_production.py contains 'INSTALLED_APPS': $(grep -c 'INSTALLED_APPS' /app/dalal_project/settings_production.py || echo '0')"
else
    echo "ERROR: settings_production.py not found"
fi

# Check if properties app exists
if [ -d /app/properties ]; then
    echo "Properties app exists: True"
else
    echo "ERROR: Properties app not found"
fi

exec python run_server.py
