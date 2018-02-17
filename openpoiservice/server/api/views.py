# openpoiservice/server/main/views.py

from flask import Blueprint, request, jsonify
from openpoiservice.server import categories_tools
from voluptuous import Schema, Required, Length, Range, Coerce, Any, All, MultipleInvalid, ALLOW_EXTRA, Invalid, \
    Optional, Boolean
from shapely.geometry import Point, Polygon, LineString, MultiPoint
from openpoiservice.server import api_exceptions, ops_settings
from openpoiservice.server.api.query_builder import QueryBuilder
from openpoiservice.server.utils.geometries import parse_geometry, validate_limits
from flasgger.utils import swag_from
from flasgger import validate

# json get/post schema for raw request
# bool: http://nullege.com/codes/search/voluptuous.Boolean
schema = Schema({
    Required('request'): Required(Any('pois', 'category_stats', 'category_list'),
                                  msg='pois, category_stats or category_list missing'),
    Optional('geometry'): Required(Any(list, Length(min=1, max=1000)),
                                   msg='Maximum length reached of {}'.format(1000)),
    Optional('geometry_type'): Required(Any('point', 'linestring', 'polygon'),
                                        msg='must be point, linestring or polygon'),
    Optional('bbox'): Required(All(list, Length(min=2, max=2)),
                               msg='must be length of {}'.format(2)),
    Optional('category_group_ids'): Required(
        All(categories_tools.category_group_ids, Length(max=ops_settings['maximum_categories'])),
        msg='must be one of {}'.format(
            categories_tools.category_group_ids)),
    Optional('category_ids'): Required(
        All(categories_tools.category_ids, Length(max=ops_settings['maximum_categories'])),
        msg='must be one of {}'.format(categories_tools.category_ids)),
    Optional('radius'): Required(
        All(Coerce(int), Range(min=1, max=ops_settings['maximum_search_radius_for_points'])),
        msg='must be between 1 and {}'.format(
            ops_settings['maximum_search_radius_for_points'])),
    Optional('limit'): Required(All(Coerce(int), Range(min=1, max=ops_settings['response_limit'])),
                                msg='must be between 1 and {}'.format(
                                    ops_settings['response_limit'])),
    Optional('sortby'): Required(Any('distance', 'category'), msg='must be distance or category'),
    Optional('address'): Required(Boolean(Coerce(str)), msg='must be true or false'),
    Optional('id'): Required(Coerce(str), msg='must be a string')
})


def custom_schema():
    custom_dict = {}

    for tag, settings in ops_settings['column_mappings'].iteritems():
        possible_values = []
        print tag, ops_settings['column_mappings']
        if ops_settings['column_mappings'][tag] is not None and 'filterable' in ops_settings['column_mappings'][tag]:
            print tag
            for value in settings['common_values']:

                if value == 'str':
                    possible_values.append(Coerce(str))

                else:
                    possible_values.append(value)
            custom_dict[tag] = Required(Any(*possible_values), msg='must be one of {}'.format(possible_values))

    return custom_dict


schema = schema.extend(custom_schema())
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

            # are required params presents
            are_required_keys_present(all_args)
            are_required_geom_present(all_args)

            # merge category group ids and category ids
            all_args['category_ids'] = categories_tools.unify_categories(all_args)

            # check restrictions and parse geometry
            all_args = parse_geometries(all_args)

            # query pois
            return jsonify(request_pois(all_args))

    else:

        raise api_exceptions.InvalidUsage('HTTP request not supported.', status_code=499)


def split_get_values(all_args):
    """
    Splits values of the get request into lists
    :return: params with processed values
    """

    if 'category_ids' in all_args:
        all_args['category_ids'] = [int(cat_id) for cat_id in all_args['category_ids'].split(',')]
    if 'category_group_ids' in all_args:
        all_args['category_group_ids'] = [int(cat_group_id) for cat_group_id in
                                          all_args['category_group_ids'].split(',')]

    if 'geometry' in all_args and 'geometry_type' in all_args:
        all_args['geometry'] = [pair.split(',') for pair in all_args['geometry'].split('|')]

        if 'bbox' in all_args:
            all_args['bbox'] = [pair.split(',') for pair in all_args['bbox'].split('|')]
    elif 'bbox' in all_args:
        all_args['bbox'] = [pair.split(',') for pair in all_args['bbox'].split('|')]

    if 'details' in all_args:
        all_args['details'] = all_args['details'].split('|')

    return all_args


def request_pois(all_args):
    """
    First this validates the schema. Then builds the query and fires it against the database.
    :param all_args: params parsed in get or post request
    :return: returns the jsonified response from the db
    """

    query_builder = QueryBuilder(all_args)
    response = query_builder.request_pois()

    return response


def are_required_keys_present(all_args):
    """
    Checks if category group ids of category ids are present in request.
    :param all_args: Request parameters from get or post request
    """
    if 'category_group_ids' not in all_args and 'category_ids' not in all_args:
        raise api_exceptions.InvalidUsage('Category or category group ids missing', status_code=401)


def are_required_geom_present(all_args):
    """
    Checks if enough geometry options are are present in request.
    :param all_args: Request parameters from get or post request
    """
    if 'geometry' not in all_args and 'geometry_type' not in all_args and 'bbox' not in all_args:
        raise api_exceptions.InvalidUsage('Bounding box, geometry and geometry_type not present in request',
                                          status_code=401)

    if 'geometry' in all_args and 'geometry_type' not in all_args:
        raise api_exceptions.InvalidUsage('Geometry_type not present in request', status_code=401)

    if 'geometry' not in all_args and 'geometry_type' not in all_args:
        raise api_exceptions.InvalidUsage(' Geometry and Geometry_type not present in request', status_code=401)

    if 'geometry' not in all_args and 'geometry_type' in all_args:
        raise api_exceptions.InvalidUsage('Geometry not present in request', status_code=401)


def parse_geometries(args):
    """
    Parses the geometries to geojson objects and checks them for validity.
    :param args: Request parameters from get or post request
    :return: returns processed request parameters
    """

    # parse radius
    if 'radius' in args:
        args['radius'] = int(args['radius'])

    # parse geom
    if 'geometry' in args and 'geometry_type' in args:

        print True
        if args['geometry_type'].lower() == 'point':
            if 'radius' not in args:
                raise api_exceptions.InvalidUsage('Radius is missing', status_code=404)

            if not validate_limits(int(args['radius']),
                                   ops_settings['maximum_search_radius_for_points']):
                raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

            point = parse_geometry(args['geometry'])[0]
            geojson_obj = Point((point[0], point[1]))
            args['geometry'] = check_validity(geojson_obj)

        if args['geometry_type'].lower() == 'linestring':
            # RESTRICT?
            if 'radius' not in args:
                raise api_exceptions.InvalidUsage('Radius is missing', status_code=404)

            if not validate_limits(int(args['radius']),
                                   ops_settings['maximum_search_radius_for_linestrings']):
                raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

            geojson_obj = LineString(parse_geometry(args['geometry']))
            # simplify? https://github.com/GIScience/openrouteservice/blob/master/openrouteservice/docs/services/locations/providers/postgresql/scripts/functions.sql
            args['geometry'] = check_validity(geojson_obj)

        if args['geometry_type'].lower() == 'polygon':
            # RESTRICT?
            if not validate_limits(int(args['radius']),
                                   ops_settings['maximum_search_radius_for_polygons']):
                raise api_exceptions.InvalidUsage('Maximum restrictions reached', status_code=404)

            geojson_obj = Polygon(parse_geometry(args['geometry']))
            args['geometry'] = check_validity(geojson_obj)

    # parse bbox
    if 'bbox' in args:
        geojson_obj = MultiPoint(parse_geometry(args['bbox']))
        args['bbox'] = check_validity(geojson_obj).envelope

    args['stats'] = True if args['request'] == 'category_stats' else False

    print args, args['geometry']
    return args


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
