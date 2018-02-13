# openpoiservice/server/query_builder.py

from openpoiservice.server import db
from openpoiservice.server import categories_tools, ops_settings
import geoalchemy2.functions as geo_func
from geoalchemy2.types import Geography
from shapely import wkb
from openpoiservice.server.db_import.models import Pois, Tags
from sqlalchemy.sql.expression import type_coerce
from sqlalchemy import func
import geojson as geojson
from itertools import tee, islice, chain, izip


class QueryBuilder(object):
    """ Class that creates the query."""

    def __init__(self, payload):
        """
        Initializes the query builder.

        :param payload: processed GET or POST parameters
        :type payload: dict
        """

        self.payload = payload

    def request_pois(self):
        """
        Queries pois or statistics from the database

        :return: Will either return a feature collection of pois or poi statistics.
        :type: dict
        """

        query = self.payload
        if 'radius' in query:
            radius = query['radius']
        else:
            radius = 0

        # https://github.com/geoalchemy/geoalchemy2/issues/61
        # q1 = db.session.query(Pois).filter(Pois.geom.ST_Distance(type_coerce(geom.wkt, Geography)) < radius)

        # https://github.com/geoalchemy/geoalchemy2/issues/90
        # query_intersects = db.session.query(Pois).filter(
        #    func.ST_Intersects(func.ST_Buffer(type_coerce(geom.wkt, Geography), radius), Pois.geom))

        if 'bbox' in query and 'geometry' not in query:
            geom = query['bbox'].wkt
            filter_group = [  # buffer around bbox
                geo_func.ST_DWithin(geo_func.ST_Buffer(type_coerce(geom, Geography), radius), Pois.geom, 0)]

        elif 'bbox' in query and 'geometry' in query:
            geom_bbox = query['bbox'].wkt
            geom = query['geometry'].wkt
            filter_group = [  # in bbox
                geo_func.ST_DWithin(
                    geo_func.ST_Intersection(geo_func.ST_Buffer(type_coerce(geom, Geography), radius),
                                             type_coerce(geom_bbox, Geography)), Pois.geom, 0)]

        elif 'bbox' not in query and 'geometry' in query:

            geom = query['geometry'].wkt
            filter_group = [  # buffer around geom
                geo_func.ST_DWithin(geo_func.ST_Buffer(type_coerce(geom, Geography), radius), Pois.geom, 0)]

        if 'category_ids' in query:
            filter_group.append(Pois.category.in_(query['category_ids']))

        # custom filters
        for tag, settings in ops_settings['column_mappings'].iteritems():

            if tag in query:

                # STUCK HERE!
                if settings['query_type'] == 'like':
                    print query[tag]
                    filter_group.append(func.lower(Tags.value).like('%' + query[tag].lower() + '%'))

                # DOES THIS WORK?
                if settings['query_type'] == 'equals':
                    filter_group.append(func.lower(Tags.value) == query[tag].lower())

        if query['stats']:
            pg_query = db.session \
                .query(Pois.category, func.count(Pois.category).label("count")) \
                .filter(*filter_group) \
                .group_by(Pois.category) \
                .all()

            places_json = self.generate_category_stats(pg_query)

            return places_json

        if 'sortby' in query:

            sortby = []
            if 'sortby' in query:

                if query['sortby'] == 'distance':
                    sortby.append(geo_func.ST_Distance(type_coerce(geom, Geography), Pois.geom))

                elif query['sortby'] == 'category':
                    sortby.append(Pois.category)

        pg_query = db.session \
            .query(Pois, Pois.geom.ST_Distance(type_coerce(geom, Geography)), Tags) \
            .join(Tags) \
            .filter(*filter_group) \
            .order_by(*sortby) \
            .limit(query['limit']) \
            .all()

        print 'Tim', str(pg_query)

        # response as geojson feature collection
        features = self.generate_geojson_features(pg_query)

        return features

    @classmethod
    def generate_category_stats(cls, query):
        """
        Generates the json object from group by query.

        :param query: response from the database
        :type query: list of objects

        :return: returns a dictionary with poi statistics
        :type: dict
        """

        places_dict = {
            "places": {
                "total_count": 0
            }
        }

        for poi_group in query:
            # get the group of this category
            category_group = categories_tools.category_to_group_index[poi_group.category]
            group_id = category_group["group_id"]
            group_name = category_group["group_name"]
            category_obj = {
                poi_group.category: poi_group.count
            }

            if group_id not in places_dict:

                places_dict["places"][group_id] = {
                    "name": group_name,
                    "categories": category_obj,
                    "total_count": poi_group.count
                }

            elif group_id in places_dict:

                places_dict["places"][group_id]['categories'].update(category_obj)
                places_dict["places"][group_id]['total_count'] += poi_group.count

            places_dict["places"]["total_count"] += poi_group.count

        return places_dict

    @classmethod
    def generate_geojson_features(cls, query):
        """
        Generates a GeoJSON feature collection from the response.
        :param query: the response from the database
        :type query: list of objects

        :return: GeoJSON feature collection containing properties
        :type: list
        """

        features = []

        query = iter(query)

        properties = dict()

        for previous, item, nxt in cls.previous_and_next(query):
            print item, nxt
            osm_id = item[0].osm_id
            poi_distance = item[1]

            if nxt is not None:
                next_osm_id = nxt[0].osm_id

            if next_osm_id == osm_id:
                properties[item[2].key] = item[2].value

            elif next_osm_id != osm_id or nxt is None:

                properties['distance'] = poi_distance
                properties['osm_id'] = osm_id
                properties[item[2].key] = item[2].value
                point = wkb.loads(str(item[0].geom), hex=True)
                geojson_point = geojson.Point((point.y, point.x))
                geojson_feature = geojson.Feature(geometry=geojson_point,
                                                  properties=properties
                                                  )
                features.append(geojson_feature)

                properties = dict()

        feature_collection = geojson.FeatureCollection(features)

        return feature_collection

    @staticmethod
    def previous_and_next(some_iterable):
        """
        Gets previous, current and next in iterable list

        :param some_iterable: a list
        :return: returns the previous, current and next in the list
        """

        prevs, items, nexts = tee(some_iterable, 3)
        prevs = chain([None], prevs)
        nexts = chain(islice(nexts, 1, None), [None])
        return izip(prevs, items, nexts)
