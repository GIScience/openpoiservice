# openpoiservice/server/tests/test_main.py


import unittest
import json

from tests.base import BaseTestCase


class TestCategoryListBlueprint(BaseTestCase):

    def test_category_list(self):
        response = self.client.get('/list')
        self.assertEqual(response.status_code, 200)
        self.assertIn('accomodation', response.json)
        self.assertIn('animals', response.json)


if __name__ == '__main__':
    unittest.main()
