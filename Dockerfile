# gunicorn-flask

# requires this ubuntu version due to protobuf library update
FROM ubuntu:17.10
MAINTAINER Timothy Ellersiek <timothy@openrouteservice.org>

RUN apt-get update
RUN apt-get install -y python python-pip python-virtualenv gunicorn git nano wget

# Install protobuf
RUN apt-get install -y build-essential protobuf-compiler libprotobuf-dev

# Setup flask application
RUN mkdir -p /deploy/app

COPY gunicorn_config.py /deploy/gunicorn_config.py
COPY manage.py /deploy/app/manage.py

COPY requirements.txt /deploy/app/requirements.txt
RUN pip install -r /deploy/app/requirements.txt

COPY openpoiservice /deploy/app/openpoiservice
COPY ops_settings_docker.yml /deploy/app/openpoiservice/server/ops_settings.yml

WORKDIR /deploy/app

EXPOSE 5000

# Start gunicorn
CMD ["/usr/bin/gunicorn", "--config", "/deploy/gunicorn_config.py", "manage:app"]