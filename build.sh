#!/usr/bin/env bash
set -o errexit
export PYTHONPATH=/app
export MISE_PYTHON_GITHUB_ATTESTATIONS=false
mise install
pip install -r requirements.txt
mkdir -p staticfiles
python manage.py collectstatic --noinput --clear
python manage.py migrate --noinput
