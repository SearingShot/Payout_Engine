#!/usr/bin/env sh
set -e

python manage.py migrate --noinput
python manage.py seed_if_empty

celery -A payout_engine worker -l info --concurrency=1 &
celery -A payout_engine beat -l info &

gunicorn payout_engine.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}"
