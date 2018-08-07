# openpoiservice/server/categories.py

import yaml
import os
import copy


class CategoryTools(object):

    def __init__(self, categories_file):
        self.basedir = os.path.abspath(os.path.dirname(__file__))
        self.categories_object = yaml.safe_load(open(os.path.join(self.basedir, categories_file)))
        self.category_group_ids = []
        self.category_ids = []
        self.group_index = {}
        self.category_to_group_index = {}
        self.generate_category_indices()

    def unify_categories(self, filters):

        category_ids_of_group = []

        if 'category_group_ids' in filters:

            for group_id in filters['category_group_ids']:

                if group_id in self.group_index:
                    category_ids_of_group.extend(self.group_index[group_id])

        if 'category_ids' in filters:
            in_first = set(category_ids_of_group)
            in_second = set(filters['category_ids'])

            in_second_but_not_in_first = in_second - in_first

            result = category_ids_of_group + list(in_second_but_not_in_first)

            return result

        return category_ids_of_group

    def generate_category_indices(self):

        self.category_index = {}
        self.category_ids_index = {}

        for k, v in copy.deepcopy(self.categories_object).items():

            group_name = k
            group_id = v['id']
            self.group_index[group_id] = []

            self.category_group_ids.append(int(group_id))
            group_children = v['children']

            for tag_name, pois in group_children.items():

                if tag_name in self.category_index:

                    self.category_index[tag_name].update(pois)
                else:
                    self.category_index[tag_name] = pois

                for poi, cat_id in pois.items():

                    self.category_ids_index[cat_id] = {
                        'poi_name': poi,
                        'poi_group': group_name
                    }

                    self.category_ids.append(int(cat_id))
                    self.group_index[group_id].append(int(cat_id))

                    if cat_id not in self.category_to_group_index:
                        self.category_to_group_index[cat_id] = {'group_id': v['id'],
                                                                'group_name': k}

    def get_category(self, tags):

        categories = []

        if bool(tags):

            for tag_name, tag_value in tags.items():

                if tag_name:

                    if tag_name in self.category_index:

                        if tag_value in self.category_index[tag_name]:
                            category_id = self.category_index[tag_name][tag_value]

                            if category_id > 0:
                                categories.append(category_id)

        return categories
