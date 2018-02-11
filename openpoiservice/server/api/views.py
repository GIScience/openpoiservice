# openpoiservice/server/main/views.py

from flask import Blueprint, request, jsonify
from openpoiservice.server import categories_tools
from voluptuous import Schema, Required, Length, Range, Coerce, Any, All, MultipleInvalid, ALLOW_EXTRA
from shapely.geometry import Point, Polygon, LineString, MultiPoint
from openpoiservice.server import api_exceptions
from openpoiservice.server.config import ops_settings
from openpoiservice.server.api.query_builder import QueryBuilder
from openpoiservice.server.utils.geometries import parse_geometry, validate_limits

# json get/post schema for raw request
schema_get = Schema({
    Required('request'): Required(Any('pois', 'category_stats', 'category_list')),
    'geometry': Required(Any(list, Length(min=1, max=30))),
    'geometry_type': Required(Any('point', 'linestring', 'polygon')),
    'bbox': Required(All(list, Length(min=2, max=2))),
    'category_group_ids': Required(
        All(categories_tools.category_group_ids, Length(max=ops_settings['maximum_categories']))),
    'category_ids': Required(All(categories_tools.category_ids, Length(max=ops_settings['maximum_categories']))),
    'name': Required(Coerce(str)),
    'wheelchair': Required(Any('true', 'false', 'limited')),
    'smoking': Required(Any('true', 'false')),
    'fee': Required(Any('true', 'false')),
    'radius': Required(All(Coerce(int), Range(min=1, max=ops_settings['maximum_search_radius_for_points']))),
    'limit': Required(All(Coerce(int), Range(min=1, max=ops_settings['response_limit']))),
    'sortby': Required(Any('distance', 'category')),
    'details': Required(All(['address', 'contact', 'attributes'], Length(min=1, max=3))),
    'id': Required(Coerce(str))
}, extra=ALLOW_EXTRA)


main_blueprint = Blueprint('main', __name__, )


@main_blueprint.route('/places', methods=['GET', 'POST'])
def places():
    """
    Function called when user posts or gets to /places.

    :return: This function will either return category statistics or poi information within a given
    geometry. Depending on GET or POST it will prepare the payload accordingly.
    :type: string
    """

    if request.method == 'POST' or request.method == 'GET':

        if request.method == 'POST':

            if request.headers['Content-Type'] == 'application/json' and request.is_json:

                all_args = request.get_json(silent=True)
                if all_args is None:
                    raise api_exceptions.InvalidUsage('Invalid JSON object in request', status_code=400)

        elif request.method == 'GET':

            all_args = request.args.to_dict()
            all_args = split_get_values(all_args)

        else:

            raise api_exceptions.InvalidUsage('HTTP request not supported.', status_code=499)

        # validate json schema
        try:
            schema_get(all_args)
        except MultipleInvalid as e:
            exc = e
            raise api_exceptions.InvalidUsage(str(exc), status_code=401)

        # query stats
        if all_args['request'] == 'category_list':
            return jsonify(categories_tools.categories_object)

        # are required params presents
        are_required_keys_present(all_args)
        are_required_geom_present(all_args)

        # check restrictions and parse geometry
        all_args = parse_geometries(all_args)

        # query pois
        return jsonify(request_pois(all_args))


def split_get_values(all_args):
    """
    Splits values of the get request into lists.
    :param all_args: params parsed in get or post request
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
    # merge category group ids and category ids
    args['category_ids'] = categories_tools.unify_categories(args)

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
            args['geometry'] = api_exceptions.check_validity(geojson_obj)

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


