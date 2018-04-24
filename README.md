# Openpoiservice 

[![Build Status](https://travis-ci.org/GIScience/openpoiservice.svg?branch=master)](https://travis-ci.org/GIScience/openpoiservice)

Openpoiservice (ops) is a flask application which hosts a highly customizable points of interest database derived from 
OpenStreetMap.org data and thereby **exploits** it's notion of tags...

> OpenStreetMap [tags](https://wiki.openstreetmap.org/wiki/Tags) consisting of a key and value describe specific features of 
> map elements (nodes, ways, or relations) or changesets.  Both items are free format text fields, but often represent numeric 
> or other structured items. 

This service consumes OSM tags on nodes, ways and relations by grouping them into predefined categories. 
If it picks up an OSM object tagged with one of the osm keys defined in `categories.yml` it will import this 
point of interest with specific additional tags which may be defined in `ops_settings.yml`. Any additional tag, 
for instance `wheelchair` or `smoking` may then be used to query the service via the API after import.

For instance, if you want to request all pois accessible by wheelchair within a geometry, you could add then add 
`wheelchair: ['yes', 'dedicated]` in `filters` within the body of your HTTP POST request. 

You may pass 3 different types of geometry within the request to the database. Currently "Point" and "LineString" with
a corresponding and buffer are supported as well as a polygon. Points of interest will be returned within the given geometry.

You can control the maximum size of geometries and further restrictions in the settings file of this service.

#### Import Process 

The osm file(s) to be imported are parsed several times to extract points of interest from relations (osm_type 3), 
ways (osm_type 2) and nodes (osm_type 1) in order. Which type the specific point of interest originated from will be 
returned in the response - this will help you find the object directly on [OpenStreetMap.org](OpenStreetMap.org). 

## Installation

You can either run **openpoiservice** on your host machine in a virtual environment or simply with docker. The Dockerfile 
provided installs a WSGI server (gunicorn) which starts the flask service on port 5000. 

### Technical specs for storing and importing OSM files

##### Python version

As this service makes use of the python collections library, in particular the notion of deque's and its functions
it only supports python 3.5 and greater.

##### Database
This application uses a psql/postgis setup for storing the points of interest. We highly recommend [using this](https://github.com/kartoza/docker-postgis) 
docker container.

##### Importer
Please consider the following technical requirements for parsing & importing osm files.

| Region        | Memory        | 
| ------------- |:-------------:|
| Germany       | 8 GB         |
| Europe        | 32 GB         | 
| Planet        | 128 GB        | 

**Note:** Openpoiservice will import any osm pbf file located in the osm folder or subdirectory within. 
This way you can split the planet file into smaller regions (e.g. download from Geofabrik, scraper script for the download
links to be found in the osm folder) and use a *smaller* instance to import the global data set (as long as
the OSM files don't exceed 5 GB of disk space, 16 GB of memory will suffice to import the entire planet).

### Run as Docker Container (Flask + Gunicorn)

Make your necessary changes to the settings in the file `ops_settings_docker.yml`. This file will be copied to the docker container.
If you are planning to import a different osm file, please download it to the `osm folder` (any folder within will be scanned
for osm files) as this will be a shared volume. 

Afterwards run:


```sh
$ docker-compose up -d -f /path/to/docker-compose.yml
```

Once the container is built you can either, create the empty database:

```sh
$ docker exec -it container_name /ops_venv/bin/python manage.py create_db
```

Delete the database:

```sh
$ docker exec -it container_name /ops_venv/bin/python manage.py drop_db
```

Or import the OSM data:

```sh
$ docker exec -it container_name /ops_venv/bin/python manage.py import_data
```


### Run in a Virtual Environment

1. Create and activate a virtualenv
2. This repository uses [imposm.parser](https://imposm.org/docs/imposm.parser/latest/index.html) to parse the 
OpenStreetMap data. To this end, **make sure** `google's protobuf` is installed on your system:

- **Ubuntu (16.04 and earlier, supported on 17.10)**: most likely you will have to install protobuf [from source](https://github.com/google/protobuf/blob/master/src/README.md) if 
[https://imposm.org/docs/imposm.parser/latest/install.html#requirements](https://imposm.org/docs/imposm.parser/latest/install.html#requirements) doesn't
do the job.
- **OS X**  Using homebrew` on OS X `brew install protobuf` will suffice.
3. Afterwards you can install the necessary requirements via pipwith `pip install -r requirements.txt`


### Prepare settings.yml

Update `openpoiservice/server/ops_settings.yml` with your necessary settings and then run one of the following
commands.

[
```sh
$ export APP_SETTINGS="openpoiservice.server.config.ProductionConfig|DevelopmentConfig"
```
]


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

### Run the Application with Flask-Werkzeug

```sh
$ python manage.py run
```

Per default you can access the application at the address [http://localhost:5000/](http://localhost:5000/)

> Want to specify a different port?

> ```sh
> $ python manage.py run -h 0.0.0.0 -p 8080
> ```

### Tests

```sh
$ export TESTING="True" && python manage.py test
```


### Category IDs and their configuration

`openpoiservice/server/categories/categories.yml` is a list of (**note:** not all!) OpenStreetMap tags with arbitrary category IDs. 
If you keep the structure as follows, you can manipulate this list as you wish.
 
 ```yaml
 transport:
    id: 580
    children:
        aeroway:
            aerodrome: 581        
            aeroport: 582 
            helipad: 598         
            heliport: 599 
        amenity:
            bicycle_parking: 583  
            
 sustenance:
    id: 560             
    children:
        amenity:
            bar: 561             
            bbq: 562   
 ...
 ```
 
 Openpoiservice uses this mapping while it imports pois from the OpenStreetMap data and assigns the custom category IDs
 accordingly.

`column_mappings` in `openpoiservice/server/ops_settings.yml` controls which OSM information will be considered in the database and also if 
these may be queried by the user via the API , e.g.

```py
wheelchair:

smoking:

fees:
```

For instance means that the OpenStreetMap tag [wheelchair](https://wiki.openstreetmap.org/wiki/Key:wheelchair) will be considered
during import and save to the database. A user may then add a list of common values in the filters object `wheelchair: ['yes', 'dedicated', ...]` 
which correspond to the OSM common values of the tag itself, e.g. 
[https://wiki.openstreetmap.org/wiki/Key:wheelchair](https://wiki.openstreetmap.org/wiki/Key:wheelchair).

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

