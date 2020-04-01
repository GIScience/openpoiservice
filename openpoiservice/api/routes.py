from flask import Blueprint, request, make_response, current_app, jsonify

import copy
import json
import geojson
from shapely.geometry import shape, MultiPoint
from voluptuous.error import MultipleInvalid

from .. import categories_tools
from . import api_exceptions
from .schemas import get_schema
from .query_info import QueryInfo
from .query_builder import QueryBuilder
from ..utils.geometries import validate_limit, transform_geom, parse_geometry

main_bp = Blueprint('api', __name__)


@main_bp.route('/pois', methods=['POST'])
def pois():
    """
    Function called when user posts or gets to /places.

    :return: This function will either return category statistics or poi information within a given
    geometry. Depending on GET or POST it will prepare the payload accordingly.
    :type: string
    """

    if 'application/json' in request.headers['Content-Type'] and request.is_json:

        all_args = request.get_json(silent=True)

        raw_request = copy.deepcopy(all_args)

        if all_args is None:
            raise api_exceptions.InvalidUsage(status_code=400, error_code=4000)

        try:
            schema = get_schema()
            schema(all_args)
        except MultipleInvalid as error:
            raise api_exceptions.InvalidUsage(status_code=400, error_code=4000, message=str(error))

        if 'filters' in all_args and 'category_group_ids' in all_args['filters']:
            all_args['filters']['category_ids'] = categories_tools.unify_categories(all_args['filters'])

        if 'limit' not in all_args:
            all_args['limit'] = current_app.config['OPS_MAX_POIS']

        if 'geometry' not in all_args:
            raise api_exceptions.InvalidUsage(status_code=400, error_code=4002)

        are_required_geom_present(all_args['geometry'])

        # check restrictions and parse geometry
        all_args['geometry'] = parse_geometries(all_args['geometry'])
        features = []
        gj = all_args['geometry'].get('geojson')
        if gj and gj.get('type') == 'MultiPolygon':
            polygons = list(all_args['geometry']['geom'])

            for polygon in polygons:
                all_args['geometry']['geom'] = polygon
                tmp = request_pois(all_args)
                query_info = QueryInfo(raw_request).__dict__
                tmp["information"] = query_info
                features.append(tmp)

        else:
            tmp = request_pois(all_args)
            query_info = QueryInfo(raw_request).__dict__
            tmp["information"] = query_info
            features.append(tmp)

        return jsonify(features)


def request_pois(all_args):
    """
    First this validates the schema. Then builds the query and fires it against the database.
    :param all_args: params parsed in get or post request
    :return: returns the jsonified response from the db
    """

    query_builder = QueryBuilder(all_args)
    response = query_builder.request_pois()

    return response


def are_required_keys_present(filters):
    """
    Checks if category group ids of category ids are present in request.
    :param filters: Request parameters from get or post request
    """
    if 'category_group_ids' not in filters and 'category_ids' not in filters:
        raise api_exceptions.InvalidUsage(status_code=400, error_code=4001)


def are_required_geom_present(geometry):
    """
    Checks if enough geometry options are are present in request.
    :param geometry: Geometry parameters from  post request
    """
    if 'geojson' not in geometry and 'bbox' not in geometry:
        raise api_exceptions.InvalidUsage(status_code=400, error_code=4003)


def check_for_buffer(geometry, maximum_search_radius):
    if 'buffer' not in geometry:
        raise api_exceptions.InvalidUsage(status_code=400, error_code=4004)

    if not validate_limit(int(geometry['buffer']), maximum_search_radius):
        raise api_exceptions.InvalidUsage(status_code=400, error_code=4008)


def check_validity(geojson):
    """
    Checks if geojson is valid, throws exception otherwise.
    :param geojson: geojson object
    :return: will return the geo
    """
    if geojson.is_valid:
        return geojson
    else:
        raise api_exceptions.InvalidUsage(status_code=500, error_code=4007)


def parse_geometries(geometry):
    """
    Parses the geometries to geojson objects and checks them for validity.
    :param geometry: Request parameters from get or post request
    :return: returns processed request parameters
    """
    # parse radius
    if 'buffer' not in geometry:
        geometry['buffer'] = 0

    # parse geojson
    if 'geojson' in geometry:

        s = json.dumps(geometry['geojson'])
        # Convert to geojson.geometry
        try:
            g1 = geojson.loads(s)
        except ValueError as e:
            raise api_exceptions.InvalidUsage(status_code=400, error_code=4007, message=str(e))

        # Feed to shape() to convert to shapely.geometry.polygon.Polygon
        # This will invoke its __geo_interface__ (https://gist.github.com/sgillies/2217756)
        try:
            g2 = shape(g1)
        except ValueError as e:
            raise api_exceptions.InvalidUsage(status_code=400, error_code=4007, message=str(e))
        except AttributeError as e:
            raise api_exceptions.InvalidUsage(status_code=400, error_code=4007, message=str(e))

        # parse geom if valid
        geojson_obj = check_validity(g2)

        if geojson_obj.geom_type == 'Point':
            check_for_buffer(geometry, current_app.config['OPS_MAX_RADIUS_POINT'])

        elif geojson_obj.geom_type == 'LineString':
            check_for_buffer(geometry, current_app.config['OPS_MAX_RADIUS_LINE'])

            # check if linestring not too long
            length = transform_geom(geojson_obj, 'epsg:4326', 'epsg:3857').length
            if length > current_app.config['OPS_MAX_LENGTH_LINE']:
                raise api_exceptions.InvalidUsage(
                    status_code=400, error_code=4005,
                    message='Your linestring geometry is too long ({} meters), check the server restrictions.'.format(
                        length))

        elif geojson_obj.geom_type == 'Polygon' or geojson_obj.geom_type == 'MultiPolygon':

            check_for_buffer(geometry, current_app.config['OPS_MAX_RADIUS_POLY'])

            # check if area not too large
            area = transform_geom(geojson_obj, 'epsg:4326', 'epsg:3857').area
            if area > current_app.config['OPS_MAX_AREA']:
                raise api_exceptions.InvalidUsage(
                    message='Your polygon geometry is too large ({} square meters), check the server '
                            'restrictions.'.format(area),
                    status_code=400, error_code=4008)

        else:
            # type not supported
            raise api_exceptions.InvalidUsage(error_code=4007,
                                              message='GeoJSON type {} not supported'.format(geojson_obj.geom_type),
                                              status_code=400)

        geometry['geom'] = geojson_obj

    # parse bbox, can be provided additionally to geometry
    if 'bbox' in geometry:

        try:
            geojson_obj = MultiPoint(parse_geometry(geometry['bbox']))
        except ValueError as e:
            raise api_exceptions.InvalidUsage(status_code=400, error_code=4007, message=str(e))

        geometry['bbox'] = check_validity(geojson_obj).envelope

        # print(geometry['bbox'].wkt)

        # check if area not too large
        area = transform_geom(geometry['bbox'], 'epsg:4326', 'epsg:3857').area
        if area > current_app.config['OPS_MAX_AREA']:
            raise api_exceptions.InvalidUsage(error_code=4008, status_code=400,
                                              message='Your polygon geometry is too large ({} square meters), '
                                                      'check the server restrictions.'.format(area))

    return geometry
