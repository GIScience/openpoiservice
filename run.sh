#!/bin/sh
if [[ ! -z "$UPDATE_DB" ]]; then
  echo "Updating POI database"
  /ops_venv/bin/python manage.py import-data
elif [[ ! -z "$REBUILD_DB" ]]; then
    echo "Rebuilding POI database"
    /ops_venv/bin/python manage.py drop-db
    /ops_venv/bin/python manage.py create-db
    /ops_venv/bin/python manage.py import-data
else
  /ops_venv/bin/gunicorn --config /deploy/gunicorn_config.py manage:app
fi
