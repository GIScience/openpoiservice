#--- BEGIN Usual Python stuff ---
FROM python:3.8.2-slim-buster
# for Alpine, try "apk --no-cache --update add build-base"
MAINTAINER Nils Nolde <nils@openrouteservice.org>

ENV POETRY_VERSION=1.0.5

COPY pyproject.toml poetry.lock

RUN apt-get update -y > /dev/null && \
    apt-get install -y build-essential > /dev/null && \
    pip install "poetry==$POETRY_VERSION" && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi
#--- END Usual Python stuff ---

WORKDIR /deploy/app

COPY config_gunicorn.py manage.py /deploy/app/

COPY openpoiservice /deploy/app/openpoiservice

EXPOSE 5000

# Start gunicorn
CMD ["/usr/local/bin/gunicorn", "--config", "/deploy/app/gunicorn_config.py", "manage:app"]
