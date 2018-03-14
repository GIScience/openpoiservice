# openpoiservice/server/tests/test_main.py


import unittest
import json

from base import BaseTestCase


class TestCategoryListBlueprint(BaseTestCase):

    def test_category_list(self):
        response = self.client.post('/pois', data=json.dumps(dict(request='list')),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'accomodation', response.data)
        self.assertIn(b'animals', response.data)


if __name__ == '__main__':
    unittest.main()
