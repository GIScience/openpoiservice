# openpoiservice/server/tests/test_main.py


import unittest
import json

from base import BaseTestCase

# GEOM POINT
request_poi_point_geom = dict(
    request='pois',
    geometry=dict(
        geojson=dict(type="Point",
                     coordinates=[8.807499091203672, 53.07528723347236]),
        buffer=50
    )
)

# GEOM POINT WITH BBOX
request_poi_point_geom_with_bbox = dict(
    request='pois',
    geometry=dict(
        geojson=dict(type='Point',
                     coordinates=[8.807499091203672, 53.07528723347236]
                     ),
        bbox=[[8.807054, 53.075024], [8.807533, 53.075363]],
        buffer=50
    )
)

# GEOM POLYGON
request_poi_polygon_geom = dict(
    request='pois',
    geometry=dict(
        geojson=dict(type='Polygon',
                     coordinates=[[[8.80864522981668685, 53.07594435294385704],
                                   [8.80864522981668685, 53.07536364271325624],
                                   [8.80824790176417238, 53.07508856944613029],
                                   [8.80803395588974247, 53.07545533380229585],
                                   [8.80821733806782525, 53.07589850739933013],
                                   [8.80864522981668685, 53.07594435294385704]]]
                     ),
        buffer=0
    )
)

# GEOM POLYGON WITH BBOX
request_poi_polygon_geom_with_bbox = dict(
    request='pois',
    geometry=dict(
        geojson=dict(type='Polygon',
                     coordinates=[[[8.80864522981668685, 53.07594435294385704],
                                   [8.80864522981668685, 53.07536364271325624],
                                   [8.80824790176417238, 53.07508856944613029],
                                   [8.80803395588974247, 53.07545533380229585],
                                   [8.80821733806782525, 53.07589850739933013],
                                   [8.80864522981668685, 53.07594435294385704]]]
                     ),
        buffer=0,
        bbox=[[8.808345, 53.075677], [8.808781, 53.076031]],
    )
)

# GEOM LINESTRING
request_poi_linestring_geom = dict(
    request='pois',
    geometry=dict(
        geojson=dict(type="LineString",
                     coordinates=[[8.807132326847508, 53.07574568891761], [8.807514373051843, 53.0756845615249],
                                  [8.807865855559836, 53.07559287043586], [8.807926982952514, 53.07545533380228]]),
        buffer=10
    )
)

# GEOM LINESTRING WITH BBOX
request_poi_linestring_geom_with_bbox = dict(
    request='pois',
    geometry=dict(
        geojson=dict(type="LineString",
                     coordinates=[[8.807132326847508, 53.07574568891761], [8.807514373051843, 53.0756845615249],
                                  [8.807865855559836, 53.07559287043586], [8.807926982952514, 53.07545533380228]]
                     ),
        bbox=[[8.807054, 53.075024], [8.807533, 53.075363]],
        buffer=50
    )
)

# BBOX ONLY
request_poi_bbox = dict(
    request='pois',
    geometry=dict(
        bbox=[[8.807054, 53.075024], [8.807533, 53.075363]]
    )
)

# MISSING GEOMETRY
request_poi_missing_geometry = dict(
    request='pois'
)

# MISSING GEOM
request_poi_missing_geometry_geom = dict(
    request='pois',
    geometry=dict(
        geojson=dict(
            type="LineString"
        )
    )
)

# MISSING GEOM
request_poi_missing_geometry_type = dict(
    request='pois',
    geometry=dict(
        geojson=dict(
            coordinates=[[8.807499091203672, 53.07528723347236]]
        )
    )
)


class TestPoisBlueprint(BaseTestCase):

    def test_request_poi_missing_geom(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_missing_geometry),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_request_poi_missing_geometry_geom(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_missing_geometry_geom),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_request_poi_missing_geometry_type(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_missing_geometry_type),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_request_poi_point_geom(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_point_geom),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'features', response.data)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['features']), 13)

    def test_request_poi_point_geom_with_bbox(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_point_geom_with_bbox),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'features', response.data)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['features']), 7)

    def test_request_poi_polygon_geom(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_polygon_geom),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'features', response.data)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['features']), 7)

    def test_request_poi_polygon_geom_with_bbox(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_polygon_geom_with_bbox),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'features', response.data)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['features']), 1)

    def test_request_poi_linestring_geom(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_linestring_geom),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'features', response.data)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['features']), 3)

    def test_request_poi_linestring_geom_with_bbox(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_linestring_geom_with_bbox),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'features', response.data)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['features']), 6)

    def test_request_poi_bbox(self):
        response = self.client.post('/pois', data=json.dumps(request_poi_bbox),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'features', response.data)
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(len(data['features']), 7)


if __name__ == '__main__':
    unittest.main()
