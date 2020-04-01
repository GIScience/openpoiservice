# OpenPoiService 

[![Build Status](https://travis-ci.org/GIScience/openpoiservice.svg?branch=master)](https://travis-ci.org/GIScience/openpoiservice)

**OpenPoiServer** is a flask application which hosts a highly customizable database for points of interest derived from 
[OpenStreetMap.org](https://openrouteservice.org) data.

> OpenStreetMap [tags](https://wiki.openstreetmap.org/wiki/Tags) consisting of a key and value describe specific features of 
> map elements (nodes, ways, or relations) or changesets.  Both items are free format text fields, but often represent numeric 
> or other structured items. 

## Introduction

**OpenPoiServer** consumes OSM tags on nodes, ways and relations by grouping them into predefined categories, which can be accessed in [`config_categories.yml`](config_categories.yml).
If it picks up an OSM object tagged with one of the OSM keys defined in `config_categories.yml` it will import the object with specific additional tags which may be defined via `OPS_ADDITIONAL_TAGS` environment variable. 
Any additional tag, for instance `wheelchair` or `smoking`, may then be used to filter POIs via the API after the import, see [Examples](#Examples).

You may pass 3 different types of geometry within the request to the database:

- `Point` geometry with a buffer
- `LineString` geometry with a buffer
- `Polygon` geometry

POIs will be returned within the (buffered) geometry, complete with OSM ID and their `osm_type` (node: 1, way: 2, relation: 3). 
That helps finding the object on [openstreetmap.org](https://openstreetmap.org).

Furthermore you can control the most sensitive API settings, such as `maximum_area`, `response_limit`.

## Installation and Setup

You can either host the service on your machine directly or use Docker/docker-compose to virtualize a new environment to run **OpenPoiServer**.

### Docker

The image is available on [Dockerhub](https://docker.hub.com) or can be built locally. 

The image provides a stable and configurable WSGI server, `gunicorn`.

#### Quickstart

```bash
docker run -dt \
    --name openpoiservice \
    -v $PWD/osm:/app/osm \  # The data volume
    -v $PWD/conf:/srv/app/conf \  # The config_categories.yml file to be exposed
    #-p 5000:5000 \  # The port to request OpenPoiService
    --net host \  # if PostGIS is installed on the host
    -e POSTGRES_HOST=localhost \
    -e POSTGRES_DBNAME=gis \
    -e POSTGRES_PORT=5432 \
    -e POSTGRES_USER=admin \
    -e POSTGRES_PASS=xxx \
    openrouteservice/openpoiservice:1.0.0 \  # The image
    all  # The CMD to be executed
```

Note, that you'll have to have a working PostGIS installation available. The necessary settings can either be in form of in-line environment variables or putting them in a local `.env` file and letting `docker` know about it with `--env-file=.env`.

#### Environment variables

All of OpenPOIService's settings are set via environment variables, which have sensible defaults already.

Best is to set up a `.env` file with the settings that need changing (e.g. `POSTGRES_PASS`). This `.env` is automatically considered `flask` commands are run or when running `docker-compose`. However, for Docker you'll need to inline `--env-file=.env`.

##### PostgreSQL

The PostgreSQL specific settings are the same as for Kartoza's excellent [PostGIS image](https://github.com/kartoza/docker-postgis):

- `POSTGRES_HOST`: The host for the PG installation. Can be a physical IP address or Docker container/service name if containers are linked in a network. Default `localhost`.
- `POSTGRES_DBNAME`: The database name. Default `gis`.
- `POSTGRES_PORT`: The PG published port. Default `5432`.
- `POSTGRES_USER`: The PG user name. Default `gis_admin`.
- `POSTGRES_PASS`: The PG password for the user name. Default `admin`.

##### App

- `OPS_LOGGING`: Set the logging level for the application, one of \['debug', 'info', 'warning', 'error'\]. Default depends on `FLASK_ENV`.
- `OPS_OSMIUM`: The [memory strategy](https://osmcode.org/osmium-concepts/#list-of-map-index-classes) used by `osmium` to extract the information. Default: `flex_mem`.
- `OPS_CONCURRENT_WORKERS`: The amount of parallel processes started for multiple PBFs (one per PBF). Default: CPU cores - 1 (recommended).
- `OPS_ATTRIBUTION`: The attribution returned by the API. Default: `openrouteservice.org | OpenStreetMap contributors`.
- `OPS_MAX_POIS`: Maximum amount of POIs returned per request. Default: 2000.
- `OPS_MAX_CATEGORIES`: Maximum amount of categories which can be specified in a filter. Default: 5.
- `OPS_MAX_RADIUS_POINT`: Maximum buffer radius for Point geometry requests. Default: 2000.
- `OPS_MAX_RADIUS_LINE`: Maximum buffer radius for LineString geometry requests. Default: 2000.
- `OPS_MAX_RADIUS_POLY`: Maximum buffer radius for Polygon geometry requests. Default: 2000.
- `OPS_MAX_AREA`: Maximum area of Polygon geometry in one request \[sqm\]. Default 50000000.
- `OPS_MAX_LENGTH_LINE`: Maximum length of a LineString geometry per request \[m]\. Default 500000.
- `OPS_ADDITIONAL_TAGS`: Extract these tags from PBFs per matched POI as comma-separated list of OSM keys. Default: `name,wheelchair,smoking,fee,opening_hours,phone,website`.

#### Volumes

There are two main container locations interesting for mounting to the host:

- `/app/osm`: the service looks in this directory for PBF files. So in `-v $PWD/osm:/app/osm`, your local directory `./osm` should hold at least one OSM file.
- `/srv/app/conf`: all config files are located in this directory. If you change any of those and restart the container, the changes will be effective immediately.
    - `categories.yml`: holds the information which OSM keys are imported to the database. This is important for the `import-data` command.
    - `config_gunicorn.py`: some basic configuration for the Python server `gunicorn`

#### Commands

The entrypoint for a container is `./run.sh` which can take one `CMD` argument of the following:

- `all`: Will do the whole thing: drop previous tables, create new ones and import all data available.
- `create-db`: Creates the tables.
- `drop-db`: Drops the tables.
- `import-data`: Import the available OSM data into the tables.

E.g. the following command would import available OSM data into existing tables and remove the container afterward:

`docker run --rm -t -v $PWD/osm:/app/osm -v $PWD/conf:/srv/app/conf --net host openrouteservice/openpoiservice:0.1.0 import-data`

### Conventional Installation

#### Requirements

Installation can only be confirmed on Linux.

- Python => 3.6
- `poetry` as package manager

#### Workflow

1. Clone the repo and install the dependencies. Depending on your system you might have to additionally install some system libraries.
    ```bash
    git clone https://github.com/GIScience/openpoiservice.git
    cd openpoiservice
    poetry install --no-dev
    ```
2. Download one or more PBF (only) files into the `osm` directory. This is where the service will look for data.
    ```bash
    cd osm 
    wget http://download.geofabrik.de/europe/andorra-latest.osm.pbf
    wget  http://download.geofabrik.de/europe/faroe-islands-latest.osm.pbf
    ```
3. Copy the `conf/config.template.yml` to `conf/config.yml` and adjust the settings as needed.
    ```bash
    cp conf/config.template.yml conf/config.yml
    nano conf/config.yml
    ```
4. Create the tables and import the data. This might take a while and depends on your machine specs.
    ```bash
   export APP_SETTINGS=production python manage.py create-db
   export APP_SETTINGS=production python manage.py import-data 
   ```
5. Run the service either in Flask or with `gunicorn`.
    ```bash
   FLASK_APP=manage flask run
   #or
   ./.venv/bin/gunicorn -config conf/config_gunicorn.py manage:app
   ```
   
### Available Flask commands

The following commands are registered in `manage.py` to be used like this `python manage.py <command>`:

- `create-db`: Creates the tables in the PostGIS database registered in `conf/config.yml`
- `import-data`: Imports all PBF files located in `osm/` directory.
- `drop-db`: Deletes the tables registered in `conf/config.yml`
- `test`: Runs the test suite, needs a `APP_SETTINGS=testing`, i.e. `APP_SETTINGS=testing python manage.py test`

## Important aspects for running OpenPoiService

### Machine specs

Parsing OSM data and extracting geometries of ways and relations is a very heavy task. The problem is that ways and
relations only reference node IDs, who keep the actual geometry. So, to extract the geometry of a way (or a relation),
one has to keep a reference of the underlying nodes. We decided to rely on
`pyosmium`, as it offers the flexiblity of various strategies to cope with the processing. 
Please see [link]() for a more in-depth explanation of the available strategies. 

The configuration value `osmium_strategy` can be set in [`conf/config.yml`]().

Also, we use `multiprocessing` to spawn each PBF file to its own process/core. We use a maxium of `available_cores - 1`. So,
it can be beneficial to split up a region into multiple PBF files prior to importing, which will considerably speed up 
the process. However, do note that this will mostly require the same RAM as a single, big PBF file.

That's why we can't and won't give ultimate recommendations to hardware, as it depends on the `osmium` memory/mmap strategy
and whether you split up the processing on multiple PBF files.

However, for small to medium-sized OSM extracts 16 GB RAM should be sufficient for `flex_mem` strategy, even on multiple cores.

### PostGIS-enabled Database

OpenPoiService requires to have a PostGIS instance running. This can be an existing database system or, highly recommended,
[Kartoza's docker image](https://github.com/kartoza/docker-postgis). Our provided [`docker-compose.yml`](docker-compose.yml)
uses Kartoza's PostgreSQL 12.0 with PostGIS 3.0 extension.

## Customization

### POI categories

OpenPoiService divides OpenStreetMap tags into reasonable categories, which act as parents for OSM tags. Additionally, 
it can extract a user-settable list of tags from each POI, if present, such as `opening_hours`, `wheelchair`, `smoking` etc.

`conf/categories.yml` contains the pre-set mapping of POI tags which OpenPoiService will extract. As long as you keep 
the general structure and make sure IDs are not duplicated, you can extend the list to your convenience.

In `conf/config.yml` there's a section `column_mappings` which lists the OSM tags which are extracted for each POI found,
if they are present.

Both `categories` and the `column_mappings` can be used in API queries to filter POIs.

### API Documentation

The documentation for this flask service is provided via [flasgger](https://github.com/rochacbruno/flasgger) and can be
accessed via `http://localhost:5000/apidocs/`.

Generally you have three different request types `pois`, `stats` and
`list`.

Using `request=pois` in the POST body will return a GeoJSON FeatureCollection
in your specified bounding box or geometry. 

Using `request=stats` will do the same but group by the categories, ultimately
returning a JSON object with the absolute numbers of pois of a certain group. 

Finally, `request=list` will return a JSON object generated from 
`openpoiservice/server/categories/categories.yml`.

### Endpoints

The default base url is `http://localhost:5000/`.

The openpoiservice holds the endpoint `/pois`:

| Method allowed | Parameter | Values \[optional\]                            			     |
|----------------|:----------|:----------------------------------------------------------------------|
| POST           | request   | pois, stats, list                 				     |
|                | geometry  | bbox, geojson, buffer             				     |
|                | filter    | category_group_ids, category_ids, \[name, wheelchair, smoking, fee\]  | 
|                | limit     | integer                           				     |
|                | sortby    | category, distance                				     |

### Examples

##### POIS around a buffered point

```sh
curl -X POST \
  http://localhost:5000/pois \
  -H 'Content-Type: application/json' \
  -d '{
  "request": "pois",
  "geometry": {
    "bbox": [
      [8.8034, 53.0756],
      [8.7834, 53.0456]
    ],
    "geojson": {
      "type": "Point",
      "coordinates": [8.8034, 53.0756]
    },
    "buffer": 250  
  }
}'
```

##### POIs of given categories
```sh
curl -X POST \
  http://localhost:5000/pois \
  -H 'Content-Type: application/json' \
  -d '{
  "request": "pois",
  "geometry": {
    "bbox": [
      [8.8034, 53.0756],
      [8.7834, 53.0456]
    ],
    "geojson": {
      "type": "Point",
      "coordinates": [8.8034, 53.0756]
    },
    "buffer": 100  
  },
  "limit": 200,
  "filters": {
    "category_ids": [180, 245]
  } 
}'
```

##### POIs of given category groups

```sh
curl -X POST \
  http://localhost:5000/pois \
  -H 'Content-Type: application/json' \
  -d '{
  "request": "pois",
  "geometry": {
    "bbox": [
      [8.8034, 53.0756],
      [8.7834, 53.0456]
    ],
    "geojson": {
      "type": "Point",
      "coordinates": [8.8034, 53.0756]
    },
    "buffer": 100  
  },
  "limit": 200,
  "filters": {
    "category_group_ids": [160]
  } 
}'
```

##### POI Statistics
```sh
curl -X POST \
  http://129.206.7.157:5005/pois \
  -H 'Content-Type: application/json' \
  -d '{
  "request": "stats",
  "geometry": {
    "bbox": [
      [8.8034, 53.0756],
      [8.7834, 53.0456]
    ],
    "geojson": {
      "type": "Point",
      "coordinates": [8.8034, 53.0756]
    },
    "buffer": 100  
  }
}'
```

##### POI Categories as a list

```sh
curl -X POST \
  http://127.0.0.1:5000/pois \
  -H 'content-type: application/json' \
  -d '{
	"request": "list"
}'
```

