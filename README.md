# Openpoiservice (WIP)

Openpoiservice is a flask application which hosts a POI database derived from openstreetmap data.

[![Build Status](https://travis-ci.org/realpython/flask-skeleton.svg?branch=master)](https://travis-ci.org/realpython/flask-skeleton)

## Quick Start

### Basics

1. Create and activate a virtualenv
2. Install the requirements via pip
3. Make sure protoc is installed on your host system (needed to parse the osm pbf files, `$ protoc --version`

### Set Environment Variables

Update *openpoiservice/server/ops_settings.yml* with your database, and then run:

```sh
$ export APP_SETTINGS="openpoiservice.server.config.ProductionConfig"
```

(or

```sh
$ export APP_SETTINGS="openpoiservice.server.config.DevelopmentConfig"
```
)

### Configuration

##### *ops_settings.yml*

...

##### *categories.yml*

...


### Create the POI DB

```sh
$ python manage.py create_db
```
### Drop the POI DB

```sh
$ python manage.py drop_db
```

### Parse and import OSM data

```sh
$ python manage.py import_data
```

### Run the Application

```sh
$ python manage.py run
```

Access the application at the address [http://localhost:5000/](http://localhost:5000/)

> Want to specify a different port?

> ```sh
> $ python manage.py run -h 0.0.0.0 -p 8080
> ```

### API Documentation

... /places..

parameters

### Testing

```sh
$ python manage.py test
```

