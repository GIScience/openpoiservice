# openpoiservice/server/tests/test_main.py


import unittest
import json

from base import BaseTestCase

# CATEGORY_IDS
request_stats_category_ids_point_geom = dict(
    request='stats',
    geometry=dict(
        geojson=dict(type="Point",
                     coordinates=[8.807499091203672, 53.07528723347236]
                     ),
        buffer=50
    ),
    filters=dict(
        category_ids=[621],
    )
)

# CATEGORY_GROUP_IDS
request_stats_category_group_ids_point_geom = dict(
    request='stats',
    geometry=dict(
        geojson=dict(type="Point",
                     coordinates=[8.807499091203672, 53.07528723347236]
                     ),
        buffer=50
    ),
    filters=dict(
        category_group_ids=[620],
    )
)


class TestPoisBlueprint(BaseTestCase):

    def test_request_stats_category_ids_point_geom(self):
        response = self.client.post('/pois', data=json.dumps(request_stats_category_ids_point_geom),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'places', response.data)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['places']['total_count'], 6)

    def test_request_stats_category_group_ids_point_geom(self):
        response = self.client.post('/pois', data=json.dumps(request_stats_category_group_ids_point_geom),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'places', response.data)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data['places']['total_count'], 9)


if __name__ == '__main__':
    unittest.main()
