# Openpoiservice

[![Build Status](https://travis-ci.org/GIScience/openpoiservice.svg?branch=master)](https://travis-ci.org/GIScience/openpoiservice)

Openpoiservice (ops) is a flask application which hosts a highly customizable points of interest database derived from OpenStreetMap.org data and it's notion of tags. 

> OpenStreetMap [tags](https://wiki.openstreetmap.org/wiki/Tags) consisting of a key and value describe specific features of 
> map elements (nodes, ways, or relations) or changesets.  Both items are free format text fields, but often represent numeric 
> or other structured items. 

This service consumes OSM tags on nodes, ways and relations by grouping them into predefined categories. 
If it picks up an OSM object tagged with one of the osm key's defined in `categories.yml` it will import this 
point of interest with additional tags which may be defined in `ops_settings.yml`. Any additional tag, 
for instance `wheelchair` may then be used to query the service via the API after import.

The database may be queried by providing a point / linestring and buffer or a polygon.
Pois will be returned within the given geometry

#### Import Process 

The osm file(s) to be imported are parsed several times to extract points of interest from relations (osm_type 1), ways (osm_type 2) and nodes (osm_type 3) in order. 
Which type the specific poi originated from will be returned in the response.
This will help you find the object directly on OpenStreetMap.org. 

## Installation

You can either run openpoiservice on your host machine in a virtual environment or simply with docker. The Dockerfile 
installs a WSGI server (gunicorn) which starts the flask service on port 5000. 

### Run as Docker Container (Flask + Gunicorn)

Make your necessary changes to the settings in `ops_settings_docker.yml`. This file will be copied to the docker container.
If you are planning to import a different osm file, please download it to the `osm folder` as this will
be a shared volume. Afterwards run:


```sh
$ docker-compose up -d -f /path/to/docker-compose.yml
```

Once the container is built you can either, create the database:

```sh
$ docker exec -it container_name python manage.py create_db
```

To delete the database:

```sh
$ docker exec -it container_name python manage.py drop_db
```

To import the OSM data:

```sh
$ docker exec -it container_name python manage.py import_data
```


### Run in Virtual Environment

1. Create and activate a virtualenv
2. This repository uses [imposm.parser](https://imposm.org/docs/imposm.parser/latest/index.html) to parse the 
OpenStreetMap data. To this end, make sure `google's protobuf` is installed on your system 
- **Ubuntu (16.04 and earlier, fixed on 17.10)**: most likely you will have to install protobuf [from source](https://github.com/google/protobuf/blob/master/src/README.md) if 
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

### Run the Application

```sh
$ python manage.py run
```

Access the application at the address [http://localhost:5000/](http://localhost:5000/)

> Want to specify a different port?

> ```sh
> $ python manage.py run -h 0.0.0.0 -p 8080
> ```

### Testing

```sh
$ export TESTING="True" && python manage.py test
```


### Technical requirements for importing OSM

Please consider the following technical specifications for importing an osm file.

| Region        | Memory        | 
| ------------- |:-------------:|
| Germany       | 16 GB         |
| Europe        | 64 GB         | 
| Planet        | 128 GB        | 

**Note:** Openpoiservice will import any osm pbf file located in the osm folder. 
This way you can split the planet file into smaller regions (e.g. download from Geofabrik, scraper script to be
found in the osm folder) and still use a smaller machine to import the data. As long as
the pbf files don't exceed 5 GB of disk space, 16 GB of memory will suffice.

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

### Category IDs and configuration

`openpoiservice/server/categories/categories.yml` 

is a list of (note: not all!) OpenStreetMap tags with arbitrary category IDs. If you keep the structure as follows, you can manipulate this list as you wish.
 
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
 
 Openpoiservice uses this dictionary while its importing pois
 from the OpenStreetMap data and assigns the custom category IDs
 accordingly.

`openpoiservice/server/ops_settings.yml` 

This is where you will configure your spatial restrictions and database connection (find more information within the file). 

Also, these settings file controls which OSM information will be considered in the database and also if 
these may be queried by the user via the API. As an example:

```py
wheelchair:
    common_values: ['yes', 'limited', 'no', 'designated']
    filterable: 'equals'
```

Means that the OpenStreetMap tag [wheelchair](https://wiki.openstreetmap.org/wiki/Key:wheelchair) will be considered
during import and also if a user adds `wheelchair:` as a property and one of the `common_values` as value to the POST body.

### Examples

##### POIs
```sh
curl -X POST \
  http://127.0.0.1:5000/places \
  -H 'cache-control: no-cache' \
  -H 'content-type: application/json' \
  -d '{
	"request": "pois",
	"geometry": {
	    "geojson": {
	        "coordinates": [53.075051,8.798952],
		"type": "Point"
	    },
	    "bbox": [[53.075051,8.798952],[53.080785,8.907160]],
	    "buffer": 10000
	},
	"filters": {
            "category_ids": [601, 280] 
	}
}'
```

##### POI Statistics
```sh
curl -X POST \
  http://127.0.0.1:5000/places \
  -H 'content-type: application/json' \
  -d '{
	"request": "stats",
	"geometry": {
	    "geojson": {
	        "coordinates": [53.075051,8.798952],
		"type": "Point"
	    },
	    "bbox": [[53.075051,8.798952],[53.080785,8.907160]],
	    "buffer": 10000
	},
	"filters": {
        "category_ids": [601, 280] 
	},
	"limit": 100,
	"sortby": "distance"
}'
```

##### POI Category List

```sh
curl -X POST \
  http://127.0.0.1:5000/places \
  -H 'content-type: application/json' \
  -d '{
	"request": "list"
}'
```

