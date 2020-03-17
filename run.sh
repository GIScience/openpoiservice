#!/usr/bin/env bash

if ! test -f /srv/app/conf/categories.yml; then
  cp /app/conf/categories.yml /srv/app/conf
else
  cp /srv/app/conf/categories.yml /app/conf
fi

if ! test -f /srv/app/conf/config_gunicorn.py; then
  cp /app/conf/config_gunicorn.py /srv/app/conf
else
  cp /srv/app/conf/config_gunicorn.py /app/conf
fi

if ! test -f /srv/app/conf/config.yml; then
  mv /app/conf/config.template.yml /app/conf/config.yml
  cp /app/conf/config.template.yml /srv/app/conf/config.yml
else
  cp /srv/app/conf/config.yml /app/conf
fi

# If create is true
create=${1}

if [ "${create}" == "create" ]; then
  cd /app
  python manage.py drop-db
  python manage.py create-db
  python manage.py import-data
elif [ -n "${create}" ]; then
  echo "Command ${create} not recognized"
  exit 1
fi

cd /app && /usr/local/bin/gunicorn --config /app/conf/config_gunicorn.py manage:app
