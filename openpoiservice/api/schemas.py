from flask import current_app as app

from voluptuous import Schema, Required, Length, Range, Coerce, Any, All, MultipleInvalid, Optional, Boolean

from openpoiservice import categories_tools

def custom_schema():
    custom_dict = {}

    for tag in app.config['OPS_ADDITIONAL_TAGS']:
        custom_dict[tag] = Required(list, msg='Must be a list')

    return custom_dict

def get_schema():

    geom_schema = {

        Optional('geojson'): Required(object, msg='Must be a geojson object'),
        Optional('bbox'): Required(All(list, Length(min=2, max=2)),
                                   msg='Must be length of {}'.format(2)),
        Optional('buffer'): Required(
            All(Coerce(int), Range(min=0, max=app.config['OPS_MAX_RADIUS_POINT'])),
            msg='Must be between 1 and {}'.format(
                app.config['OPS_MAX_RADIUS_POINT']))

    }

    filters_schema = {

        Optional('category_group_ids'): Required(
            All(categories_tools.category_group_ids, Length(max=app.config['OPS_MAX_CATEGORIES'])),
            msg='Must be one of {} and have a maximum amount of {}'.format(
                categories_tools.category_group_ids, app.config['OPS_MAX_CATEGORIES'])),

        Optional('category_ids'): Required(
            All(categories_tools.category_ids, Length(max=app.config['OPS_MAX_CATEGORIES'])),
            msg='Must be one of {} and have a maximum amount of {}'.format(categories_tools.category_ids,
                                                                           app.config['OPS_MAX_CATEGORIES'])),

        Optional('address'): Required(Boolean(Coerce(str)), msg='Must be true or false'),

    }

    filters_schema.update(custom_schema())

    return Schema({
        Required('request'): Required(Any('pois', 'stats', 'list'),
                                      msg='pois, stats or list missing'),

        Optional('geometry'): geom_schema,

        Optional('filters'): filters_schema,

        Optional('limit'): Required(All(Coerce(int), Range(min=1, max=app.config['OPS_MAX_POIS'])),
                                    msg='must be between 1 and {}'.format(
                                        app.config['OPS_MAX_POIS'])),
        Optional('sortby'): Required(Any('distance', 'category'), msg='must be distance or category'),

        Optional('id'): Required(Coerce(str), msg='must be a string')
    })
