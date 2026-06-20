#!/bin/sh
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py bootstrap_superuser
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
