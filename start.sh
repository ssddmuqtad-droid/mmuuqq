#!/usr/bin/env bash
set -o errexit

echo "=== Dalal Platform Startup ==="
echo "PORT=${PORT:-8080}"
echo "DEBUG=${DEBUG:-False}"

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn dalal_project.wsgi:application \
  --bind "0.0.0.0:${PORT:-8080}" \
  --workers 2 \
  --timeout 300 \
  --access-logfile - \
  --error-logfile -
