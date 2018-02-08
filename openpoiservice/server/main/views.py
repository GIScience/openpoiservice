# openpoiservice/server/main/views.py

from flask import render_template, Blueprint, request, jsonify
from openpoiservice.server import categories_tools
from voluptuous import Schema, Required, Length, Range, Coerce, Any, All, MultipleInvalid, ALLOW_EXTRA
from openpoiservice import ops_settings
from query_builder import QueryBuilder
from openpoiservice.server import api_exceptions

# maximum_search_radius_for_linestrings: 1000
# maximum_search_radius_for_points: 20000
# maximum_search_radius_for_polygons: 1000

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

    if request.method == 'POST':
        print request.headers['Content-Type']
        if request.headers['Content-Type'] == 'application/json' and request.is_json:

            all_args = request.get_json(silent=True)
            if all_args is None:
                raise api_exceptions.InvalidUsage('Invalid JSON object in request', status_code=400)

            # stats
            if all_args['request'] == 'category_list':
                return jsonify(categories_tools.categories_object)

            # poi request
            are_required_keys_present(all_args)
            are_required_geom_present(all_args)

            return request_pois(all_args)

    elif request.method == 'GET':

        all_args = request.args.to_dict()

        # stats
        if all_args['request'] == 'category_list':
            return jsonify(categories_tools.categories_object)

        # poi request
        are_required_keys_present(all_args)
        are_required_geom_present(all_args)

        # split values
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

        return request_pois(all_args)

        # public class LocationsErrorCodes
        # {
        #	public static int INVALID_JSON_FORMAT = 400;
        #	public static int MISSING_PARAMETER = 401;
        #	public static int INVALID_PARAMETER_FORMAT = 402;
        #	public static int INVALID_PARAMETER_VALUE = 403;
        #	public static int PARAMETER_VALUE_EXCEEDS_MAXIMUM = 404;
        #	public static int UNKNOWN = 499;
        # }


def request_pois(all_args):
    # validate json schema
    try:
        schema_get(all_args)
    except MultipleInvalid as e:
        exc = e
        raise api_exceptions.InvalidUsage(str(exc), status_code=401)

    query_builder = QueryBuilder(all_args)

    query = query_builder.get_query()

    response = query_builder.request_pois(query)
    return jsonify(response)


def are_required_keys_present(all_args):

    if 'category_group_ids' not in all_args and 'category_ids' not in all_args:

        raise api_exceptions.InvalidUsage('Category or category group ids missing', status_code=401)

    return True


def are_required_geom_present(all_args):

    if 'geometry' not in all_args and 'geometry_type' not in all_args and 'bbox' not in all_args:

        raise api_exceptions.InvalidUsage('Bounding box, geometry and geometry_type not present in request', status_code=401)

    if 'geometry' in all_args and 'geometry_type' not in all_args:

        raise api_exceptions.InvalidUsage('Geometry_type not present in request', status_code=401)

    if 'geometry' not in all_args and 'geometry_type' in all_args:

        raise api_exceptions.InvalidUsage('Geometry not present in request', status_code=401)

    return True
