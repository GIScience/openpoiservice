# openpoiservice/server/main/views.py

from flask import render_template, Blueprint, request, jsonify
from openpoiservice.server import db, categories_tools
import geoalchemy2.functions as func
import json
from voluptuous import Schema, Required, Length, Range, Coerce, Any, All, MultipleInvalid, ALLOW_EXTRA
from openpoiservice import ops_settings
from query_builder import QueryBuilder

# maximum_search_radius_for_linestrings: 1000
# maximum_search_radius_for_points: 20000
# maximum_search_radius_for_polygons: 1000

parameters = Schema({
    # Required('request'): Coerce(str),
    Required('request'): Required(Any('pois', 'category_stats', 'category_list')),
    Required('geometry'): Required(Any(list, Length(min=1, max=30))),
    Required('geometry_type'): Required(Any('point', 'linestring', 'polygon')),
    'bbox': Required(All(list, Length(min=4, max=4))),
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

        pass

    elif request.method == 'GET':
        all_args = request.args.to_dict()
        print all_args
        if 'category_ids' in all_args:
            all_args['category_ids'] = all_args['category_ids'].split(',')
        if 'category_group_ids' in all_args:
            all_args['category_group_ids'] = all_args['category_group_ids'].split(',')
        if 'geometry' in all_args:
            all_args['geometry'] = all_args['geometry'].split('|')
        if 'bbox' in all_args:
            all_args['bbox'] = all_args['bbox'].split('|')
        if 'details' in all_args:
            all_args['details'] = all_args['details'].split('|')

        print all_args

        try:
            parameters(all_args)
        except MultipleInvalid as e:
            return e

        query_builder = QueryBuilder()

        return jsonify(all_args)
