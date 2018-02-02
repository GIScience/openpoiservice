# Openpoiservice (WIP)

Openpoiservice is a flask application which hosts a POI database derived from openstreetmap data.

[![Build Status](https://travis-ci.org/realpython/flask-skeleton.svg?branch=master)](https://travis-ci.org/realpython/flask-skeleton)

## Quick Start

### Basics

1. Create and activate a virtualenv
1. Install the requirements via pip

### Set Environment Variables

Update *openpoiservice/server/config.py*, and then run:

```sh
$ export APP_SETTINGS="openpoiservice.server.config.DevelopmentConfig"
```

or

```sh
$ export APP_SETTINGS="openpoiservice.server.config.ProductionConfig"
```

### Create DB

```sh
$ python manage.py create_db
```
### Drop DB

```sh
$ python manage.py drop_db
```

### Import OSM data

```sh
$ python manage.py import_data
```

### Run the Application

```sh
$ python manage.py runserver
```

Access the application at the address [http://localhost:5000/](http://localhost:5000/)

> Want to specify a different port?

> ```sh
> $ python manage.py runserver -h 0.0.0.0 -p 8080
> ```

### Documentation

...

### Testing

Without coverage:

```sh
$ python manage.py test
```

With coverage:

```sh
$ python manage.py cov
```
