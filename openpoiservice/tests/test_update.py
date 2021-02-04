# openpoiservice/server/tests/test_main.py
import os
import unittest
import json
from base import BaseTestCase
from openpoiservice.server.db_import import parser

request_poi_bbox = dict(
    request='pois',
    geometry=dict(
        bbox=[[8.801054, 53.070024], [8.809533, 53.079363]]
    )
)


class TestUpdate(BaseTestCase):
    def test_import_update_mode(self):

        print("======== Perform database update =========")
        updated_test_file = os.path.join(os.getcwd() + '/osm_test', 'bremen-tests-mod.osm.pbf')
        parser.run_import([updated_test_file], {})

        response = self.client.post('/pois', data=json.dumps(request_poi_bbox), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'features', response.data)
        data = json.loads(response.get_data(as_text=True))

        # for debugging
        # print(json.dumps(data, indent=4, sort_keys=False))

        # 1 POI has been deleted in the update and 1 added, so number hasn't changed
        self.assertEqual(len(data[0]['features']), 38)

        # 1 POI has been added
        self.assertEqual(data[0]['features'][5]['properties']['osm_id'], 2134315509)
        self.assertEqual(data[0]['features'][5]['properties']['osm_tags']['name'], "Ein Impfzentrum")

        # 1 POI has a tag value changed
        self.assertEqual(data[0]['features'][20]['properties']['osm_tags']['name'], "Kiosk am Markt wurde umbenannt")


if __name__ == '__main__':
    unittest.main()
