# openpoiservice/server/query_builder.py

from openpoiservice.server import db
from openpoiservice.server import categories_tools, ops_settings
import geoalchemy2.functions as geo_func
from geoalchemy2.types import Geography, Geometry
from geoalchemy2.elements import WKBElement, WKTElement
from shapely import wkb
from shapely.geometry import MultiPoint, Point
from openpoiservice.server.db_import.models import Pois, Tags, Categories
from sqlalchemy.sql.expression import type_coerce
from sqlalchemy import func, cast, Integer, ARRAY
from sqlalchemy import dialects
import geojson as geojson
import logging
from timeit import default_timer as timer

logger = logging.getLogger(__name__)


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
        Queries pois or statistics from the database. Pois will always be less then querying category statistics
        because one poi can have several categories.

        :return: Will either return a feature collection of pois or poi statistics.
        :type: dict
        """

        params = self.payload

        geom_filters, geom = self.generate_geom_filters(params['geometry'], Pois)

        logger.debug('geometry filters: {}, geometry: {}'.format(geom_filters, geom))

        category_filters = []
        if 'filters' in params:
            if 'category_ids' in params['filters']:
                category_filters.append(Categories.category.in_(params['filters']['category_ids']))

        # currently only available for request=pois
        custom_filters = []
        if 'filters' in params:
            custom_filters = self.generate_custom_filters(params['filters'])

        if params['request'] == 'stats':

            bbox_query = db.session \
                .query(Pois.uuid, Categories.category) \
                .filter(*geom_filters) \
                .filter(*category_filters) \
                .outerjoin(Categories) \
                .subquery()

            stats_query = db.session \
                .query(bbox_query.c.category, func.count(bbox_query.c.category).label("count")) \
                .group_by(bbox_query.c.category) \
                # .all()

            places_json = self.generate_category_stats(stats_query)

            return places_json

        # join with tags
        elif params['request'] == 'pois':

            bbox_query = db.session \
                .query(Pois) \
                .filter(*geom_filters) \
                .subquery()

            # sortby needed here for generating features in next step
            # sortby_group = [bbox_query.c.osm_id]
            sortby_group = []
            if 'sortby' in params:
                if params['sortby'] == 'distance':
                    sortby_group.append(geo_func.ST_Distance(type_coerce(geom, Geography), bbox_query.c.geom))

                elif params['sortby'] == 'category':
                    sortby_group.append(bbox_query.c.category)

            # start = timer()

            keys_agg = func.array_agg(Tags.key).label('keys')
            values_agg = func.array_agg(Tags.value).label('values')
            categories_agg = func.array_agg(Categories.category).label('categories')

            pois_query = db.session \
                .query(bbox_query.c.osm_id,
                       bbox_query.c.osm_type,
                       bbox_query.c.geom.ST_Distance(type_coerce(geom, Geography)),
                       bbox_query.c.geom,
                       keys_agg,
                       values_agg,
                       categories_agg) \
                .order_by(*sortby_group) \
                .filter(*category_filters) \
                .filter(*custom_filters) \
                .outerjoin(Tags) \
                .outerjoin(Categories) \
                .group_by(bbox_query.c.uuid) \
                .group_by(bbox_query.c.osm_id) \
                .group_by(bbox_query.c.osm_type) \
                .group_by(bbox_query.c.geom) \
                # .all()

            # end = timer()
            # print(end - start)

            #print(str(pois_query))
            # for dude in pois_query:
            # print(dude)

            # response as geojson feature collection
            features = self.generate_geojson_features(pois_query, params['limit'])

            return features

    @staticmethod
    def generate_geom_filters(geometry, Pois):
        filters, geom = [], None

        if 'bbox' in geometry and 'geom' not in geometry:
            geom = geometry['bbox'].wkt
            filters.append(
                geo_func.ST_DWithin(geo_func.ST_Buffer(type_coerce(geom, Geography), geometry['buffer']), Pois.geom, 0))

        elif 'bbox' in geometry and 'geom' in geometry:
            geom_bbox = geometry['bbox'].wkt
            geom = geometry['geom'].wkt
            filters.append(  # in bbox
                geo_func.ST_DWithin(
                    geo_func.ST_Intersection(geo_func.ST_Buffer(type_coerce(geom, Geography), geometry['buffer']),
                                             type_coerce(geom_bbox, Geography)), Pois.geom, 0))

        elif 'bbox' not in geometry and 'geom' in geometry:

            geom = geometry['geom'].wkt

            filters.append(  # buffer around geom
                geo_func.ST_DWithin(geo_func.ST_Buffer(type_coerce(geom, Geography), geometry['buffer']), Pois.geom, 0)
            )

        return filters, geom

    @staticmethod
    def generate_custom_filters(filters):
        """
        Generates a list of custom filters used for query.

        :param filters:
        :param query: sqlalchemy flask query
        :return: returns sqlalchemy filters
        :type: list
        """

        custom_filters = []
        for tag, settings in ops_settings['column_mappings'].items():
            if tag in filters:
                custom_filters.append(Tags.key == tag.lower())
                custom_filters.append(Tags.value.in_(filters[tag]))

        return custom_filters

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
                categories_tools.category_ids_index[poi_group.category]['poi_name']: {
                    'count': poi_group.count,
                    'category_id': poi_group.category

                }
            }
            if group_name not in places_dict["places"]:

                places_dict["places"][group_name] = {
                    "group_id": group_id,
                    "categories": category_obj,
                    "total_count": poi_group.count
                }

            elif group_name in places_dict["places"]:

                places_dict["places"][group_name]['categories'].update(category_obj)
                places_dict["places"][group_name]['total_count'] += poi_group.count

            places_dict["places"]["total_count"] += poi_group.count

        logger.info('Number of poi stats groups: {}'.format(len(places_dict)))

        return places_dict

    @classmethod
    def generate_geojson_features(cls, query, limit):
        """
        Generates a GeoJSON feature collection from the response.
        :param limit:
        :param query: the response from the database
        :type query: list of objects
        :return: GeoJSON feature collection containing properties
        :type: list
        """

        geojson_features = []
        lat_lngs = []

        for q_idx, q in enumerate(query):

            geometry = wkb.loads(str(q[3]), hex=True)
            x = float(format(geometry.x, ".6f"))
            y = float(format(geometry.y, ".6f"))
            trimmed_point = Point(x, y)

            lat_lngs.append((trimmed_point.x, trimmed_point.y))

            properties = dict(
                osm_id=int(q[0]),
                osm_type=int(q[1]),
                distance=float(q[2])
            )

            category_ids_obj = {}
            for c_id in set(q[6]):
                category_name = categories_tools.category_ids_index[c_id]['poi_name']
                category_group = categories_tools.category_ids_index[c_id]['poi_group']
                category_ids_obj[c_id] = {
                    "category_name": category_name,
                    "category_group": category_group
                }
            properties["category_ids"] = category_ids_obj

            key_values = {}
            for idx, key in enumerate(q[4]):
                if key != "null":
                    key_values[key] = q[5][idx]

            properties["osm_tags"] = key_values

            geojson_feature = geojson.Feature(geometry=trimmed_point,
                                              properties=properties)
            geojson_features.append(geojson_feature)

            # limit reached
            if q_idx == limit - 2:
                break

        feature_collection = geojson.FeatureCollection(geojson_features, bbox=MultiPoint(lat_lngs).bounds)

        logger.info("Amount of features {}".format(len(geojson_features)))

        return feature_collection
