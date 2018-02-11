# openpoiservice/server/main/geom_utils.py


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
        geom.append((float(coords[1]), float(coords[0])))

    return geom


def validate_limits(radius, limit):
    """
    Returns True if radius is in custom specific limits.

    :param radius: The radius of the request in meters
    :type radius: int

    :param limit: The limit set by the custom settings
    :type limit: int

    :return: True if radius within limits, otherwise False
    :type: bool
    """

    if 0 < radius <= limit:
        return True

    return False
