# gunicorn-flask

# requires this ubuntu version due to protobuf library update
FROM ubuntu:17.10
MAINTAINER Timothy Ellersiek <timothy@openrouteservice.org>

RUN apt-get update
RUN apt-get install -y python3-pip python-virtualenv nano wget git locales

# Install protobuf
RUN apt-get install -y build-essential protobuf-compiler libprotobuf-dev

# Set the locale
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# Setup flask application
RUN mkdir -p /deploy/app

COPY gunicorn_config.py /deploy/gunicorn_config.py
COPY manage.py /deploy/app/manage.py

COPY requirements.txt /deploy/app/requirements.txt

RUN virtualenv --python=python3.6 /ops_venv

RUN /bin/bash -c "source /ops_venv/bin/activate"

RUN /ops_venv/bin/pip3 install -r /deploy/app/requirements.txt

COPY openpoiservice /deploy/app/openpoiservice
COPY ops_settings_docker.yml /deploy/app/openpoiservice/server/ops_settings.yml

WORKDIR /deploy/app

EXPOSE 5000

# Start gunicorn
CMD ["/ops_venv/bin/gunicorn", "--config", "/deploy/gunicorn_config.py", "manage:app"]