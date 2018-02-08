# openpoiservice/server/main/query_builder.py

from openpoiservice.server import api_exceptions, db
from openpoiservice import ops_settings
from openpoiservice.server import categories_tools
import geoalchemy2.functions as geo_func
from geoalchemy2.types import Geography
from shapely.geometry import Point, Polygon, LineString, MultiPoint
from shapely import wkb
from openpoiservice.server.models import Pois
from sqlalchemy.sql.expression import type_coerce
from sqlalchemy import func
import geojson as geojson


class QueryBuilder(object):
    """ Class that creates the query."""

    def __init__(self, payload):

        if payload['request'] == 'pois' or payload['request'] == 'category_stats':

            # merge category group ids and category ids
            payload['category_ids'] = categories_tools.unify_categories(payload)

            # parse radius
            if 'radius' in payload:
                payload['radius'] = int(payload['radius'])

            # parse geom
            if 'geometry' in payload and 'geometry_type' in payload:

                if payload['geometry_type'].lower() == 'point':
                    if 'radius' not in payload:
                        raise api_exceptions.InvalidUsage('Radius is missing', status_code=404)

                    if not self.validate_limits(int(payload['radius']),
                                                ops_settings['maximum_search_radius_for_points']):
                        raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

                    point = self.parse_geometry(payload['geometry'])[0]
                    geojson_obj = Point((point[0], point[1]))
                    payload['geometry'] = self.check_validity(geojson_obj)

                if payload['geometry_type'].lower() == 'linestring':
                    # RESTRICT?
                    if 'radius' not in payload:
                        raise api_exceptions.InvalidUsage('Radius is missing', status_code=404)

                    if not self.validate_limits(int(payload['radius']),
                                                ops_settings['maximum_search_radius_for_linestrings']):
                        raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

                    geojson_obj = LineString(self.parse_geometry(payload['geometry']))
                    # simplify? https://github.com/GIScience/openrouteservice/blob/master/openrouteservice/docs/services/locations/providers/postgresql/scripts/functions.sql
                    payload['geometry'] = self.check_validity(geojson_obj)

                if payload['geometry_type'].lower() == 'polygon':
                    # RESTRICT?
                    if not self.validate_limits(int(payload['radius']),
                                                ops_settings['maximum_search_radius_for_polygons']):
                        raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

                    print self.parse_geometry(payload['geometry'])
                    geojson_obj = Polygon(self.parse_geometry(payload['geometry']))
                    print geojson
                    payload['geometry'] = self.check_validity(geojson_obj)

            # parse bbox
            if 'bbox' in payload:
                geojson_obj = MultiPoint(self.parse_geometry(payload['bbox']))
                payload['bbox'] = self.check_validity(geojson_obj).envelope

            payload['stats'] = True if payload['request'] == 'category_stats' else False

        self.query_object = payload

    @staticmethod
    def parse_geometry(geometry):
        """
        GeoJSON order is [longitude, latitude, elevation]
        :param geometry:
        :return:
        """
        geom = []
        for coords in geometry:
            geom.append((float(coords[1]), float(coords[0])))

        return geom

    def get_query(self):

        return self.query_object

    def request_category_stats(self):

        pass

    def request_category_list(self):

        pass

    @classmethod
    def request_pois(cls, query):

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

        if 'name' in query:
            filter_group.append(func.lower(Pois.name).like(query['name'].lower()))

        if 'wheelchair' in query:
            filter_group.append(Pois.wheelchair == query['wheelchair'])

        if 'smoking' in query:
            filter_group.append(Pois.smoking == query['smoking'])

        if 'fee' in query:
            filter_group.append(Pois.wheelchair == query['fee'])

        if query['stats']:
            pg_query = db.session \
                .query(Pois.category, func.count(Pois.category).label("count")) \
                .filter(*filter_group) \
                .group_by(Pois.category) \
                .all()

            places_json = cls.generate_category_stats(pg_query)

            return places_json

        if 'sortby' in query:

            sortby = []
            if 'sortby' in query:

                if query['sortby'] == 'distance':
                    sortby.append(geo_func.ST_Distance(type_coerce(geom, Geography), Pois.geom))

                elif query['sortby'] == 'category':
                    sortby.append(Pois.category)

        pg_query = db.session \
            .query(Pois, Pois.geom.ST_Distance(type_coerce(geom, Geography))) \
            .filter(*filter_group) \
            .order_by(*sortby) \
            .limit(query['limit']) \
            .all()

        print str(pg_query)

        # response as geojson feature collection
        features = cls.generate_geojson_features(pg_query)

        return features

    @classmethod
    def generate_category_stats(cls, query):

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

    @staticmethod
    def generate_properties(poi, poi_dist, columns):
        properties = dict(distance=poi_dist)

        for column_name in columns:
            if getattr(poi, column_name) is not None and column_name != 'geom':
                properties[column_name] = getattr(poi, column_name)

        return properties

    @staticmethod
    def check_validity(geojson):

        if geojson.is_valid:
            return geojson
        else:
            raise api_exceptions.InvalidUsage('{} {}'.format("geojson", geojson.is_valid), status_code=401)

    @staticmethod
    def validate_limits(radius, limit):

        if 0 < radius <= limit:
            return True

        return False

    @classmethod
    def generate_geojson_features(cls, query):

        features = []
        i = 0
        for poi_object, poi_distance in query:
            point = wkb.loads(str(poi_object.geom), hex=True)
            geojson_point = geojson.Point((point.y, point.x))
            geojson_feature = geojson.Feature(geometry=geojson_point,
                                              properties=cls.generate_properties(poi_object, poi_distance,
                                                                                 Pois.__table__.columns.keys()))
            features.append(geojson_feature)

            print i, poi_object, poi_distance
            i += 1
        feature_collection = geojson.FeatureCollection(features)

        return feature_collection
