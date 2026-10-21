# openpoiservice/server/tests/test_geometries.py
import math
import unittest

from shapely.geometry import LineString, Point, Polygon

from openpoiservice.server.utils.geometries import GeomTransformer

earth_radius = 6378137  # semi-major axis used by EPSG:3857


def web_mercator(lon, lat):
    return (earth_radius * math.radians(lon),
            earth_radius * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


class TestGeomTransformer(unittest.TestCase):

    def setUp(self):
        GeomTransformer.init_transformer()

    def test_point_matches_web_mercator_formula(self):
        point = GeomTransformer.transform_geom(Point(8.8034, 53.0756))

        x, y = web_mercator(8.8034, 53.0756)
        self.assertAlmostEqual(point.x, x, places=3)
        self.assertAlmostEqual(point.y, y, places=3)

    def test_transforms_every_vertex(self):
        coordinates = [(8.80, 53.07), (8.81, 53.07), (8.81, 53.08), (8.80, 53.08)]

        polygon = GeomTransformer.transform_geom(Polygon(coordinates))
        line = GeomTransformer.transform_geom(LineString(coordinates))

        expected = [web_mercator(lon, lat) for lon, lat in coordinates]
        self.assertAlmostEqual(polygon.area, Polygon(expected).area, places=0)
        self.assertAlmostEqual(line.length, LineString(expected).length, places=3)

    def test_fails_before_initialisation(self):
        GeomTransformer.transformer = None
        with self.assertRaises(RuntimeError):
            GeomTransformer.transform_geom(Point(8.8, 53.07))


if __name__ == '__main__':
    unittest.main()
