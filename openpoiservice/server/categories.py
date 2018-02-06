# openpoiservice/server/categories.py

import yaml
import os


class CategoryTools(object):

    def __init__(self, categories_file):
        self.basedir = os.path.abspath(os.path.dirname(__file__))
        self.categories_object = yaml.safe_load(open(os.path.join(self.basedir, categories_file)))
        self.category_group_ids = []
        self.category_ids = []
        self.group_index = {}
        self.category_index = self.generate_category_index()

    def unify_categories(self, request):

        category_ids_of_group = []

        for group_id in request['category_group_ids']:

            if group_id in self.group_index:
                category_ids_of_group.extend(self.group_index[group_id])

        if 'category_ids' in request:

            in_first = set(category_ids_of_group)
            in_second = set(request['category_ids'])

            in_second_but_not_in_first = in_second - in_first

            result = category_ids_of_group + list(in_second_but_not_in_first)

            return result

        return category_ids_of_group


    def generate_category_index(self):

        category_index = {}

        for k, v in self.categories_object.iteritems():

            group_name = k
            group_id = v['id']
            self.group_index[group_id] = []

            self.category_group_ids.append(int(group_id))
            group_children = v['children']

            for tag_name, pois in group_children.iteritems():

                if tag_name in category_index:
                    category_index[tag_name].update(pois)
                else:
                    category_index[tag_name] = pois

                for poi, cat_id in pois.iteritems():
                    self.category_ids.append(int(cat_id))
                    self.group_index[group_id].append(int(cat_id))

        return category_index

    def get_category(self, tags):

        category_id = 0
        if bool(tags):

            for tag_name, tag_value in tags.iteritems():

                if tag_name:

                    if tag_name in self.category_index:

                        if tag_value in self.category_index[tag_name]:
                            category_id = self.category_index[tag_name][tag_value]

                            if category_id > 0:
                                return category_id

        return category_id
