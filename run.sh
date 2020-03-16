#!/usr/bin/env bash

create=${1}

if ! [ -z "$create" ]; then
  cd /app
  python manage.py drop-db
  python manage.py create-db
  python manage.py import-data
fi

cd /app && /usr/local/bin/gunicorn --config /app/conf/config_gunicorn.py manage:app
