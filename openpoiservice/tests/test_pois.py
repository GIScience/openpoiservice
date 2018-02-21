# openpoiservice/server/tests/test_main.py


import unittest
import json

from base import BaseTestCase


# GEOM POINT


# GEOM POLYGON


# GEOM LINESTRING


# GEOM POINT BBOX


# GEOM POLYGON BBOX


# GEOM LINESTRING BBOX


# BBOX


class TestPoisBlueprint(BaseTestCase):

    def test_pois(self):
        response = self.client.post('/places', data=json.dumps(dict(request='category_list')),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'accomodation', response.data)
        self.assertIn(b'animals', response.data)


if __name__ == '__main__':
    unittest.main()
