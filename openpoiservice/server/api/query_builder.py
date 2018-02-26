# openpoiservice/server/query_builder.py

from openpoiservice.server import db
from openpoiservice.server import categories_tools, ops_settings
import geoalchemy2.functions as geo_func
from geoalchemy2.types import Geography, Geometry
from geoalchemy2.elements import WKBElement, WKTElement
from shapely import wkb
from openpoiservice.server.db_import.models import Pois, Tags
from sqlalchemy.sql.expression import type_coerce
from sqlalchemy import func, cast
from sqlalchemy import dialects
import geojson as geojson
from itertools import tee, islice, chain, izip
import logging

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
        Queries pois or statistics from the database

        :return: Will either return a feature collection of pois or poi statistics.
        :type: dict
        """

        params = self.payload

        # https://github.com/geoalchemy/geoalchemy2/issues/61
        # q1 = db.session.query(Pois).filter(Pois.geom.ST_Distance(type_coerce(geom.wkt, Geography)) < radius)

        # https://github.com/geoalchemy/geoalchemy2/issues/90
        # query_intersects = db.session.query(Pois).filter(
        #    func.ST_Intersects(func.ST_Buffer(type_coerce(geom.wkt, Geography), radius), Pois.geom))

        # 298
        # print str(pois_query)

        # test_query = db.session \
        #    .query(Pois) \
        #    .filter(*geom_filters) \
        #    .all()

        # print str(test_query)
        # for dude in test_query:
        #    print wkb.loads(str(dude.geom), hex=True)

        geom_filters, geom = self.generate_geom_filters(params['geometry'], Pois)

        logger.debug('geometry filters: {}, geometry: {}'.format(geom_filters, geom))
        if 'filters' in params and 'category_ids' in params['filters']:
            geom_filters.append(Pois.category.in_(params['filters']['category_ids']))

        if params['request'] == 'category_stats':

            bbox_query = db.session \
                .query(Pois) \
                .filter(*geom_filters) \
                .subquery()

            if 'filters' in params:
                custom_filters = self.generate_custom_filters(params['filters'], bbox_query)
            else:
                custom_filters = []

            stats_query = db.session \
                .query(bbox_query.c.category, func.count(bbox_query.c.category).label("count")) \
                .filter(*custom_filters) \
                .group_by(bbox_query.c.category) \
                .all()

            logger.debug('number of poi stats: {}'.format(len(stats_query)))
            places_json = self.generate_category_stats(stats_query)

            return places_json

        # join with tags
        elif params['request'] == 'pois':

            # how can I limit here already before the join?
            bbox_query = db.session \
                .query(Pois, Tags.osm_id.label('t_osm_id'), Tags.key, Tags.value) \
                .filter(*geom_filters) \
                .outerjoin(Tags) \
                .subquery()

            custom_filters = []
            if 'filters' in params:
                custom_filters = self.generate_custom_filters(params['filters'], bbox_query)

            sortby_group = [bbox_query.c.osm_id]
            if 'sortby' in params:
                sortby_group = self.generate_sortby(params, geom, bbox_query)

            pois_query = db.session \
                .query(bbox_query.c.osm_id, bbox_query.c.category,
                       bbox_query.c.geom.ST_Distance(type_coerce(geom, Geography)),
                       bbox_query.c.t_osm_id, bbox_query.c.key, bbox_query.c.value, bbox_query.c.geom) \
                .filter(*custom_filters) \
                .order_by(*sortby_group) \
                .all()

            # for dude in pois_query:
            #    print wkb.loads(str(dude[6]), hex=True)
            logger.info("number of pois: {}".format(len(pois_query)))

            # response as geojson feature collection
            features = self.generate_geojson_features(pois_query, params['limit'])

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
    def generate_geom_filters(geometry, Pois):
        filters, geom = [], None

        if 'bbox' in geometry and 'geom' not in geometry:
            geom = geometry['bbox'].wkt
            filters.append(
                geo_func.ST_DWithin(geo_func.ST_Buffer(type_coerce(geom, Geography), geometry['radius']), Pois.geom, 0))

        elif 'bbox' in geometry and 'geom' in geometry:
            geom_bbox = geometry['bbox'].wkt
            geom = geometry['geom'].wkt
            filters.append(  # in bbox
                geo_func.ST_DWithin(
                    geo_func.ST_Intersection(geo_func.ST_Buffer(type_coerce(geom, Geography), geometry['radius']),
                                             type_coerce(geom_bbox, Geography)), Pois.geom, 0))

        elif 'bbox' not in geometry and 'geom' in geometry:

            geom = geometry['geom'].wkt

            filters.append(  # buffer around geom
                geo_func.ST_DWithin(geo_func.ST_Buffer(type_coerce(geom, Geography), geometry['radius']), Pois.geom, 0)
            )

        return filters, geom

    @staticmethod
    def generate_custom_filters(filters, query):
        """
        Generates a list of custom filters used for query.

        :param filters:
        :param query: sqlalchemy flask query
        :return: returns sqlalchemy filters
        :type: list
        """

        filters_list = []
        for tag, settings in ops_settings['column_mappings'].iteritems():

            if tag in filters:

                filters.append(query.c.key == tag.lower())

                if settings['filterable'] == 'like':
                    filters_list.append(query.c.value.like('%' + filters[tag].lower() + '%'))

                elif settings['filterable'] == 'equals':
                    filters_list.append(query.c.value == filters[tag].lower())

                else:
                    pass

        return filters_list

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

        return places_dict

    @classmethod
    def generate_geojson_features(cls, query, limit):
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

        cnt = 1
        for previous, item, nxt in cls.previous_and_next(query):

            osm_id = item[0]

            if nxt is not None:
                next_osm_id = nxt[0]
            else:
                next_osm_id = None

            poi_distance = item[2]

            if nxt is None or osm_id != next_osm_id:

                properties['distance'] = poi_distance
                properties['osm_id'] = osm_id
                category_id = item[1]
                properties['category_id'] = category_id
                # add category name and group
                properties['category_name'] = categories_tools.category_ids_index[category_id]['poi_name']
                properties['category_group'] = categories_tools.category_ids_index[category_id]['poi_group']

                properties[item[4]] = item[5]
                point = wkb.loads(str(item[6]), hex=True)
                geojson_point = geojson.Point((point.x, point.y))
                geojson_feature = geojson.Feature(geometry=geojson_point,
                                                  properties=properties
                                                  )
                features.append(geojson_feature)

                if cnt == limit:
                    break

                cnt += 1

                properties = dict()

            elif next_osm_id == osm_id:

                properties[item[4]] = item[5]

        feature_collection = geojson.FeatureCollection(features)

        logger.debug("Amount of features {}".format(len(features)))
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
