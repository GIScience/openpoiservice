# gunicorn-flask

# requires this ubuntu version due to protobuf library update
FROM ubuntu:18.04
MAINTAINER Timothy Ellersiek <timothy@openrouteservice.org>

RUN apt-get update && apt-get install -y python3-pip python-virtualenv nano wget git locales build-essential \
protobuf-compiler=3.0.0-9.1ubuntu1 libprotobuf-dev=3.0.0-9.1ubuntu1

# Set the locale
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8

# Setup flask application
COPY requirements.txt /deploy/app/requirements.txt
RUN virtualenv --python=python3.6 /ops_venv && /bin/bash -c "source /ops_venv/bin/activate" && \
/ops_venv/bin/pip3 install Cython && /ops_venv/bin/pip3 install -r /deploy/app/requirements.txt

COPY gunicorn_config.py /deploy/gunicorn_config.py
COPY run.sh manage.py /deploy/app/
COPY openpoiservice /deploy/app/openpoiservice

WORKDIR /deploy/app
EXPOSE 5000
ENTRYPOINT ["/bin/bash", "/deploy/app/run.sh"]
