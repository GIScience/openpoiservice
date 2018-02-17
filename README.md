# Openpoiservice

Openpoiservice (ops) is a flask application which hosts a highly customizable points of interest database derived from OpenStreetMap.org data.

[![Build Status](https://travis-ci.org/realpython/flask-skeleton.svg?branch=master)](https://travis-ci.org/realpython/flask-skeleton)

## Quick Start

### Basics

1. Create and activate a virtualenv
2. Make sure `google protobuf` is installed on your system (**caution**: most likely you will have to
install from source on ubuntu [(instructions)](https://github.com/google/protobuf/blob/master/src/README.md).
Using **homebrew** on OS X `brew install protobuf` will suffice.
3. Afterwards you can install the necessary requirements via pipwith `pip install -r requirements.txt`

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

The documentation for this flask service is provided via [flasgger](https://github.com/rochacbruno/flasgger) and can be
accessed via `http://localhost:5000/apidocs/`.

Generally you have three different request types `pois`, `category_stats` and
`category_list`.

Using `request=poi` in the POST body will return a GeoJSON FeatureCollection
in your specified bounding box or geometry. 

Using `request=category_stats` will do the same but group by the categories, ultimately
returning a JSON object with the absolute numbers of pois of a certain group.

Finally, `request=category_list` will return a JSON object generated from 
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
  -H 'content-type: application/json' \
  -d '{
	"request": "pois",
	"category_ids": [601, 280],
	"geometry_type": "point",
	"geometry": [[53.075051,8.798952]],
	"radius": 10000,
	"limit": 100,
	"sortby": "distance",
	"wheelchair": "yes",
	"bbox": [[53.075051,8.798952],[53.080785,8.907160]]
}'
```

##### POI Statistics
```sh
curl -X POST \
  http://127.0.0.1:5000/places \
  -H 'content-type: application/json' \
  -d '{
	"request": "category_stats",
	"category_ids": [601, 280],
	"geometry_type": "point",
	"geometry": [[53.075051,8.798952]],
	"radius": 10000,
	"limit": 100,
	"wheelchair": "yes",
	"bbox": [[53.075051,8.798952],[53.080785,8.907160]]
}'
```

##### POI Category List

```sh
curl -X POST \
  http://127.0.0.1:5000/places \
  -H 'content-type: application/json' \
  -d '{
	"request": "category_list"
}'
```


### Testing: TODO

```sh
$ python manage.py test
```

