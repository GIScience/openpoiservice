#!/usr/bin/env bash

if ! test -f /srv/app/config_categories.yml; then
  cp /app/config_categories.yml /srv/app/conf
else
  cp /srv/app/conf/config_categories.yml /app
fi

if ! test -f /srv/app/wsgi.py; then
  cp /app/wsgi.py /srv/app/conf
else
  cp /srv/app/wsgi.py /app
fi

cmd=${1}

cd /app

if [ "${cmd}" == 'all' ]; then
  python manage.py drop-db
  python manage.py create-db
  python manage.py import-data
elif [ "${cmd}" == 'create-db' ]; then
  python manage.py create-db
elif [ "${cmd}" == 'drop-db' ]; then
  python manage.py drop-db
elif [ "${cmd}" == 'import-data' ]; then
  python manage.py import-data
elif [ -n "${cmd}" ]; then
  echo "Command ${cmd} not recognized"
  exit 1
fi

cd /app && /usr/local/bin/gunicorn --config /app/wsgi.py manage:app
