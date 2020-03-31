#!/usr/bin/env bash

if ! test -f /srv/app/categories.yml; then
  cp /app/categories.yml /srv/app/conf
else
  cp /srv/app/conf/categories.yml /app/conf
fi

if ! test -f /srv/app/gunicorn_config.py; then
  cp /app/gunicorn_config.py /srv/app/conf
else
  cp /srv/app/gunicorn_config.py /app
fi

if ! test -f /srv/app/conf/config.yml; then
  cp /app/conf/config.template.yml /app/conf/config.yml
  cp /app/conf/config.template.yml /srv/app/conf/config.yml
else
  cp /srv/app/conf/config.yml /app/conf
fi

# If create is true
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

cd /app && /usr/local/bin/gunicorn --config /app/conf/gunicorn_config.py manage:app
