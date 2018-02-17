# openpoiservice/server/query_builder.py

from openpoiservice.server import db
from openpoiservice.server import categories_tools, ops_settings
import geoalchemy2.functions as geo_func
from geoalchemy2.types import Geography
from shapely import wkb
from openpoiservice.server.db_import.models import Pois, Tags
from sqlalchemy.sql.expression import type_coerce
from sqlalchemy import func
from sqlalchemy import dialects
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

        params = self.payload
        if 'radius' in params:
            radius = params['radius']
        else:
            radius = 0

        # https://github.com/geoalchemy/geoalchemy2/issues/61
        # q1 = db.session.query(Pois).filter(Pois.geom.ST_Distance(type_coerce(geom.wkt, Geography)) < radius)

        # https://github.com/geoalchemy/geoalchemy2/issues/90
        # query_intersects = db.session.query(Pois).filter(
        #    func.ST_Intersects(func.ST_Buffer(type_coerce(geom.wkt, Geography), radius), Pois.geom))

        geom_filters, geom = self.generate_geom_filters(params, radius, Pois)

        if 'category_ids' in params:
            geom_filters.append(Pois.category.in_(params['category_ids']))

        bbox_query = db.session \
            .query(Pois, Tags.osm_id.label('t_osm_id'), Tags.key, Tags.value) \
            .filter(*geom_filters) \
            .join(Tags) \
            .subquery()

        custom_filters = self.generate_custom_filters(params, bbox_query)

        if params['stats']:
            stats_query = db.session \
                .query(bbox_query.c.category, func.count(bbox_query.c.category).label("count")) \
                .filter(*custom_filters) \
                .group_by(bbox_query.c.category) \
                .all()

            places_json = self.generate_category_stats(stats_query)

            return places_json

        sortby_group = []
        if 'sortby' in params:

            sortby_group = self.generate_sortby(params, geom, bbox_query)

        pois_query = db.session \
            .query(bbox_query.c.osm_id, bbox_query.c.category,
                   bbox_query.c.geom.ST_Distance(type_coerce(geom, Geography)),
                   bbox_query.c.t_osm_id, bbox_query.c.key, bbox_query.c.value, bbox_query.c.geom) \
            .filter(*custom_filters) \
            .order_by(*sortby_group) \
            .limit(params['limit']) \
            .all()

        # print str(pois_query.statement.compile(
        #    dialect=dialects.postgresql.dialect(),
        #    compile_kwargs={"literal_binds": True}))

        # response as geojson feature collection
        features = self.generate_geojson_features(pois_query)

        return features

    @staticmethod
    def generate_sortby(params, geom, query):
        """

        :param params:
        :param query:
        :param geom:
        :return:
        """

        sortby = []
        if 'sortby' in params:

            if params['sortby'] == 'distance':
                sortby.append(geo_func.ST_Distance(type_coerce(geom, Geography), query.c.geom))

            elif params['sortby'] == 'category':
                sortby.append(query.c.category)

        return sortby

    @staticmethod
    def generate_geom_filters(params, radius, Pois):

        filters, geom = [], None

        if 'bbox' in params and 'geometry' not in params:
            geom = params['bbox'].wkt
            filters.append(
                geo_func.ST_DWithin(geo_func.ST_Buffer(type_coerce(geom, Geography), radius), Pois.geom, 0))

        elif 'bbox' in params and 'geometry' in params:
            geom_bbox = params['bbox'].wkt
            geom = params['geometry'].wkt
            filters.append(  # in bbox
                geo_func.ST_DWithin(
                    geo_func.ST_Intersection(geo_func.ST_Buffer(type_coerce(geom, Geography), radius),
                                             type_coerce(geom_bbox, Geography)), Pois.geom, 0))

        elif 'bbox' not in params and 'geometry' in params:

            geom = params['geometry'].wkt
            filters.append(  # buffer around geom
                geo_func.ST_DWithin(geo_func.ST_Buffer(type_coerce(geom, Geography), radius), Pois.geom, 0))

        return filters, geom

    @staticmethod
    def generate_custom_filters(params, query):
        """
        Generates a list of custom filters used for query.

        :param params:
        :param query: sqlalchemy flask query
        :return: returns sqlalchemy filters
        :type: list
        """

        filters = []
        for tag, settings in ops_settings['column_mappings'].iteritems():

            if tag in params:

                filters.append(query.c.key == tag.lower())

                # STUCK HERE!
                if settings['filterable'] == 'like':
                    filters.append(query.c.value.like('%' + params[tag].lower() + '%'))

                # DOES THIS WORK?
                if settings['filterable'] == 'equals':
                    filters.append(query.c.value == params[tag].lower())

        return filters

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
            osm_id = item[0]
            poi_distance = item[2]

            if nxt is None or nxt[0] != osm_id:
                properties['distance'] = poi_distance
                properties['osm_id'] = osm_id
                properties['category_id'] = item[1]
                properties[item[4]] = item[5]
                point = wkb.loads(str(item[6]), hex=True)
                geojson_point = geojson.Point((point.x, point.y))
                geojson_feature = geojson.Feature(geometry=geojson_point,
                                                  properties=properties
                                                  )
                features.append(geojson_feature)

                properties = dict()

            else:
                properties[item[4]] = item[5]

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
