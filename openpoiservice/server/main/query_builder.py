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

                    if 'radius' not in payload:
                        raise api_exceptions.InvalidUsage('Radius is missing', status_code=404)

                    if not self.validate_limits(int(payload['radius']),
                                                ops_settings['maximum_search_radius_for_linestrings']):
                        raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

                    geojson_obj = LineString(self.parse_geometry(payload['geometry']))
                    payload['geometry'] = self.check_validity(geojson_obj)

                if payload['geometry_type'].lower() == 'polygon':

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

            self.query_type = 0

            payload['stats'] = True if payload['request'] == 'category_stats' else False

        elif payload['request'] == 'category_list':

            self.query_type = 2

            pass

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
            coords = coords.split(',')
            geom.append((float(coords[1]), float(coords[0])))

        return geom

    def get_query(self):

        return self.query_type, self.query_object

    def request_category_stats(self):

        pass

    def request_category_list(self):

        pass

    @staticmethod
    def request_pois(query):

        def generate_properties(poi, poi_dist, columns):
            properties = dict(distance=poi_dist)

            for column_name in columns:
                if getattr(poi, column_name) is not None and column_name != 'geom':
                    properties[column_name] = getattr(poi, column_name)

            return properties

        if 'radius' in query:
            radius = query['radius']
        else:
            radius = 0

        print query

        # https://github.com/geoalchemy/geoalchemy2/issues/61
        # q1 = db.session.query(Pois).filter(Pois.geom.ST_Distance(type_coerce(geom.wkt, Geography)) < radius)

        # https://github.com/geoalchemy/geoalchemy2/issues/90
        # query_intersects = db.session.query(Pois).filter(
        #    func.ST_Intersects(func.ST_Buffer(type_coerce(geom.wkt, Geography), radius), Pois.geom))

        if query['stats']:
            # group by and count!

            pass

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

        sortby = []
        if 'sortby' in query:

            if query['sortby'] == 'distance':
                sortby.append(geo_func.ST_Distance(type_coerce(geom, Geography), Pois.geom))

            elif query['sortby'] == 'category':
                sortby.append(Pois.category)

        pg_query = db.session.query(Pois, Pois.geom.ST_Distance(type_coerce(geom, Geography))).filter(
            *filter_group).order_by(*sortby).limit(query['limit'])

        print str(pg_query)

        # response as geojson feature collection
        poi_features = []
        for poi_object, poi_distance in pg_query:
            point = wkb.loads(str(poi_object.geom), hex=True)
            geojson_point = geojson.Point((point.y, point.x))
            geojson_feature = geojson.Feature(geometry=geojson_point,
                                              properties=generate_properties(poi_object, poi_distance,
                                                                             Pois.__table__.columns.keys()))
            poi_features.append(geojson_feature)

            print poi_object, poi_distance

        feature_collection = geojson.FeatureCollection(poi_features)
        return feature_collection

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
