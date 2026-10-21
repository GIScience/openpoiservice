FROM python:3.11-slim
LABEL org.opencontainers.image.authors="Timothy Ellersiek <timothy@openrouteservice.org>"

# protobuf is required to parse osm files.
# git to install imposm-parser via pip from github
# build-essential to build imposm-parser
# libexpat1 for osmium (pyosmium), used by osm/download.py
RUN apt-get update && apt-get install -y libprotobuf-dev protobuf-compiler locales git build-essential libexpat1

# Set the locale
ENV LANG=C.UTF-8 LANGUAGE=C:en LC_ALL=C.UTF-8

# Setup flask application
WORKDIR /deploy/app
COPY requirements.txt ./
RUN pip3 install -r /deploy/app/requirements.txt
COPY gunicorn_config.py run.sh manage.py ./
COPY openpoiservice ./openpoiservice

EXPOSE 5000
ENTRYPOINT ["/bin/bash", "run.sh"]
