# openpoiservice/server/utils/geometries.py

import pyproj
from shapely.ops import transform


def truncate(f, n):
    """
    Truncates/pads a float f to n decimal places without rounding
    """
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return '.'.join([i, (d + '0' * n)[:n]])


def parse_geometry(geometry):
    """
     GeoJSON order is [longitude, latitude, elevation].

    :param geometry: Is a list of coordinates in latLng order
    :type geometry: list
    :return: returns a list of coordinates in lngLat order for geojson
    :type: list
    """
    geom = []
    for coords in geometry:
        geom.append((float(coords[0]), float(coords[1])))
    return geom


def validate_limit(radius, limit):
    """
    Returns True if radius is in custom specific limits.

    :param radius: The radius of the request in meters
    :type radius: int
    :param limit: The limit set by the custom settings
    :type limit: int
    :return: True if radius within limits, otherwise False
    :type: bool
    """
    if 0 <= radius <= limit:
        return True

    return False


class GeomTransformer:
    transformer = None

    @staticmethod
    def init_transformer():
        GeomTransformer.transformer = pyproj.Transformer.from_crs(pyproj.CRS('epsg:4326'), pyproj.CRS('epsg:3857'), always_xy=True).transform

    @staticmethod
    def transform_geom(geom):
        if GeomTransformer.transformer is None:
            raise RuntimeError("GeomTransformer called before being initialized.")
        return transform(GeomTransformer.transformer, geom)
