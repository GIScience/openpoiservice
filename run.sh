#!/bin/sh
if [[ ! -z "$REBUILD_DB" ]]; then
  echo "Rebuilding POI database"
  /ops_venv/bin/python manage.py drop-db
  /ops_venv/bin/python manage.py create-db
  /ops_venv/bin/python manage.py import-data
fi
/ops_venv/bin/gunicorn --config /deploy/gunicorn_config.py manage:app
