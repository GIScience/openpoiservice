# openpoiservice/server/main/query_builder.py

from openpoiservice.server import api_exceptions, db
from openpoiservice import ops_settings
import geoalchemy2.functions as geo_func
import geoalchemy2.elements as elements
from geoalchemy2.types import Geography
from shapely.geometry import Point, Polygon, LineString, MultiPoint
from openpoiservice.server.models import Pois
from sqlalchemy.sql.expression import type_coerce
from sqlalchemy import func


class QueryBuilder(object):
    """ Class that creates the query."""

    def __init__(self, payload):

        if payload['request'] == 'pois':

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
                    geojson = Point((point[0], point[1]))
                    payload['geometry'] = self.check_validity(geojson)

                if payload['geometry_type'].lower() == 'linestring':

                    if 'radius' not in payload:
                        raise api_exceptions.InvalidUsage('Radius is missing', status_code=404)

                    if not self.validate_limits(int(payload['radius']),
                                                ops_settings['maximum_search_radius_for_linestrings']):
                        raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

                    geojson = LineString(self.parse_geometry(payload['geometry']))
                    payload['geometry'] = self.check_validity(geojson)

                if payload['geometry_type'].lower() == 'polygon':

                    if not self.validate_limits(int(payload['radius']),
                                                ops_settings['maximum_search_radius_for_polygons']):
                        raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

                    geojson = Polygon([self.parse_geometry(payload['geometry'])])
                    payload['geometry'] = self.check_validity(geojson)

            # parse bbox
            if 'bbox' in payload:
                geojson = MultiPoint(self.parse_geometry(payload['bbox']))
                payload['bbox'] = self.check_validity(geojson).envelope

            self.query_type = 0

        elif payload['request'] == 'category_stats':

            self.query_type = 1

            pass

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
        # if query["geometry_type"] ==

        # case a: point and buffer around, query within
        # case b: linestring and buffer around, query within
        # case c: polygon and buffer around, query within

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

        # if 'category_group_ids' in query:
        #    filter_group.append(Pois.category_group_id.in_(query['category_group_ids']))

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

        query_dwithin = db.session.query(Pois, Pois.geom.ST_Distance(type_coerce(geom, Geography))).filter(
            *filter_group).order_by(*sortby).limit(query['limit'])

        print str(query_dwithin)

        for poi_object, distance in query_dwithin:
            # create geojson object..

            print poi_object, distance

        # filters.append(Pois.wheelchair.in_(query['wheelchair']))

        # filter_group = list(Column.in_('a', 'b'), Pois.like('%'))

        # filters = (
        #    Transaction.amount > 10,
        #    Transaction.amount < 100,
        # )

        # polygon

        # User.firstname.like(search_var1),
        # User.lastname.like(search_var2)

        return query

    @staticmethod
    def check_validity(geojson):

        if geojson.is_valid:
            return geojson
        else:
            raise api_exceptions.InvalidUsage(geojson.errors(), status_code=401)

    @staticmethod
    def validate_limits(radius, limit):

        if 0 < radius <= limit:
            return True

        return False
