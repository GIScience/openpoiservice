# openpoiservice/server/utils/geometries.py

from functools import partial
import pyproj
from shapely.ops import transform


def truncate(f, n):
    '''Truncates/pads a float f to n decimal places without rounding'''
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


def transform_geom(g1, src_proj, dest_proj):
    project = partial(
        pyproj.transform,
        pyproj.Proj(init=src_proj),
        pyproj.Proj(init=dest_proj))

    g2 = transform(project, g1)

    return g2


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
