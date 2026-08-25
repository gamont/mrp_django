#!/bin/sh
set -eu

if [ "${SKIP_DJANGO_BOOTSTRAP:-0}" != "1" ]; then
  python manage.py check --deploy --fail-level ERROR
  python manage.py migrate --noinput
  python manage.py bootstrap_roles
  python manage.py collectstatic --noinput
fi

exec "$@"
