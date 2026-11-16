#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
python -m deployment.seed_demo
exec gunicorn fitcoach.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 2 --timeout 60
