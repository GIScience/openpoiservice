# openpoiservice/server/main/views.py

from flask import Blueprint, request, jsonify
from openpoiservice.server import categories_tools
from voluptuous import Schema, Required, Length, Range, Coerce, Any, All, MultipleInvalid, ALLOW_EXTRA, Invalid, \
    Optional, Boolean
from shapely.geometry import Point, Polygon, LineString, MultiPoint
from openpoiservice.server import api_exceptions, ops_settings
from openpoiservice.server.api.query_builder import QueryBuilder
from openpoiservice.server.utils.geometries import parse_geometry, validate_limit, validate_area, transform_geom
from flasgger.utils import swag_from


# from flasgger import validate


def custom_schema():
    custom_dict = {}

    for tag, settings in ops_settings['column_mappings'].iteritems():
        possible_values = []

        if ops_settings['column_mappings'][tag] is not None and 'filterable' in ops_settings['column_mappings'][tag]:

            for value in settings['common_values']:

                if value == 'str':
                    possible_values.append(Coerce(str))

                else:
                    possible_values.append(value)

            custom_dict[tag] = Required(Any(*possible_values), msg='must be one of {}'.format(possible_values))

    return custom_dict


geom_schema = {

    Optional('geom'): Required(Any(list, Length(min=1, max=1000)),
                               msg='Maximum length reached of {}'.format(1000)),
    Optional('type'): Required(Any('point', 'linestring', 'polygon', 'bounding_box'),
                               msg='must be point, linestring, bounding_box or polygon'),
    Optional('bbox'): Required(All(list, Length(min=2, max=2)),
                               msg='must be length of {}'.format(2)),
    Optional('radius'): Required(
        All(Coerce(int), Range(min=0, max=ops_settings['maximum_search_radius_for_points'])),
        msg='must be between 1 and {}'.format(
            ops_settings['maximum_search_radius_for_points']))

}

filters_schema = {

    Optional('category_group_ids'): Required(
        All(categories_tools.category_group_ids, Length(max=ops_settings['maximum_categories'])),
        msg='must be one of {}'.format(
            categories_tools.category_group_ids)),

    Optional('category_ids'): Required(
        All(categories_tools.category_ids, Length(max=ops_settings['maximum_categories'])),
        msg='must be one of {}'.format(categories_tools.category_ids)),

    Optional('address'): Required(Boolean(Coerce(str)), msg='must be true or false'),

}

filters_schema.update(custom_schema())

schema = Schema({
    Required('request'): Required(Any('pois', 'category_stats', 'category_list'),
                                  msg='pois, category_stats or category_list missing'),

    Optional('geometry'): geom_schema,

    Optional('filters'): filters_schema,

    Optional('limit'): Required(All(Coerce(int), Range(min=1, max=ops_settings['response_limit'])),
                                msg='must be between 1 and {}'.format(
                                    ops_settings['response_limit'])),
    Optional('sortby'): Required(Any('distance', 'category'), msg='must be distance or category'),

    Optional('id'): Required(Coerce(str), msg='must be a string')
})

print schema
main_blueprint = Blueprint('main', __name__, )


@main_blueprint.route('/places', methods=['POST'])
@swag_from('places_post.yml', methods=['POST'])
def places():
    """
    Function called when user posts or gets to /places.

    :return: This function will either return category statistics or poi information within a given
    geometry. Depending on GET or POST it will prepare the payload accordingly.
    :type: string
    """

    if request.method == 'POST':

        if request.headers['Content-Type'] == 'application/json' and request.is_json:

            all_args = request.get_json(silent=True)
            if all_args is None:
                raise api_exceptions.InvalidUsage('Invalid JSON object in request', status_code=400)

            try:
                schema(all_args)
            except MultipleInvalid as error:
                raise api_exceptions.InvalidUsage(str(error), status_code=401)
            # query stats
            if all_args['request'] == 'category_list':
                return jsonify(categories_tools.categories_object)

            if 'filters' in all_args and 'category_group_ids' in all_args['filters']:
                all_args['filters']['category_ids'] = categories_tools.unify_categories(all_args['filters'])

            if 'limit' not in all_args:
                all_args['limit'] = ops_settings['response_limit']

            if 'geometry' not in all_args:
                raise api_exceptions.InvalidUsage('Geometry missing', status_code=401)

            are_required_geom_present(all_args['geometry'])

            # check restrictions and parse geometry
            all_args['geometry'] = parse_geometries(all_args['geometry'])

            # query pois
            return jsonify(request_pois(all_args))

    else:

        raise api_exceptions.InvalidUsage('HTTP request not supported.', status_code=499)


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
        raise api_exceptions.InvalidUsage('Category or category group ids missing', status_code=401)


def are_required_geom_present(geometry):
    """
    Checks if enough geometry options are are present in request.
    :param geometry: Geometry parameters from  post request
    """
    if 'geom' not in geometry and 'type' not in geometry and 'bbox' not in geometry:
        raise api_exceptions.InvalidUsage('Bounding box, geometry and geometry_type not present in request',
                                          status_code=401)

    if 'geom' in geometry and 'type' not in geometry:
        raise api_exceptions.InvalidUsage('Geometry_type not present in request', status_code=401)

    if 'geom' not in geometry and 'type' not in geometry:
        raise api_exceptions.InvalidUsage('Geometry and geometry_type not present in request', status_code=401)

    if 'geom' not in geometry and 'bbox' not in geometry and 'type' in geometry:
        raise api_exceptions.InvalidUsage('Geometry not present in request', status_code=401)


def parse_geometries(geometry):
    """
    Parses the geometries to geojson objects and checks them for validity.
    :param geometry: Request parameters from get or post request
    :return: returns processed request parameters
    """

    # parse radius
    if 'radius' not in geometry:
        geometry['radius'] = 0

    # parse geom
    if 'geom' in geometry and 'type' in geometry:

        if geometry['type'].lower() == 'point':
            if 'radius' not in geometry:
                raise api_exceptions.InvalidUsage('Radius is missing', status_code=404)

            if not validate_limit(int(geometry['radius']),
                                  ops_settings['maximum_search_radius_for_points']):
                raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

            point = parse_geometry(geometry['geom'])[0]
            geojson_obj = Point((point[0], point[1]))
            geometry['geom'] = check_validity(geojson_obj)

        if geometry['type'].lower() == 'linestring':

            if 'radius' not in geometry:
                raise api_exceptions.InvalidUsage('Radius is missing', status_code=404)

            if not validate_limit(int(geometry['radius']),
                                  ops_settings['maximum_search_radius_for_linestrings']):
                raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

            # simplify? https://github.com/GIScience/openrouteservice/blob/master/openrouteservice/docs/services/locations/providers/postgresql/scripts/functions.sql
            geojson_obj = LineString(parse_geometry(geometry['geom']))

            geometry['geom'] = check_validity(geojson_obj)

            # check if linestring not too long
            length = transform_geom(geojson_obj, 'epsg:4326', 'epsg:3857').length
            if length > ops_settings['maximum_linestring_length']:
                raise api_exceptions.InvalidUsage(
                    'Your linestring geometry is too long ({} meters), check the server restrictions.'.format(length),
                    status_code=404)

        if geometry['type'].lower() == 'polygon':
            # RESTRICT?
            if not validate_limit(int(geometry['radius']),
                                  ops_settings['maximum_search_radius_for_polygons']):
                raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

            geojson_obj = Polygon(parse_geometry(geometry['geom']))
            geometry['geom'] = check_validity(geojson_obj)

            # check if area not too large
            area = transform_geom(geojson_obj, 'epsg:4326', 'epsg:3857').area
            if area > ops_settings['maximum_area']:
                raise api_exceptions.InvalidUsage(
                    'Your polygon geometry is too large ({} square meters), check the server restrictions.'.format(
                        area),
                    status_code=404)

    # parse bbox, can be provided additionally to geometry
    if 'bbox' in geometry:
        geojson_obj = MultiPoint(parse_geometry(geometry['bbox']))
        geometry['bbox'] = check_validity(geojson_obj).envelope

        # check if area not too large
        area = transform_geom(geometry['bbox'], 'epsg:4326', 'epsg:3857').area
        if area > ops_settings['maximum_area']:
            raise api_exceptions.InvalidUsage(
                'Your polygon geometry is too large ({} square meters), check the server restrictions.'.format(
                    area),
                status_code=404)

    return geometry


def check_validity(geojson):
    """
    Checks if geojson is valid, throws exception otherwise.
    :param geojson: geojson object
    :return: will return the geo
    """
    if geojson.is_valid:
        return geojson
    else:
        raise api_exceptions.InvalidUsage('{} {}'.format("geojson", geojson.is_valid), status_code=401)
