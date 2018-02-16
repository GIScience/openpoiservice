# openpoiservice/server/poi_entity.py


class PoiObject(object):

    def __init__(self, category, osmid, lat_lng, osm_type):
        self.osmid = int(osmid)
        self.type = int(osm_type)
        self.category = int(category)

        self.geom = 'SRID={};POINT({} {})'.format(4326, float(lat_lng.lat),
                                                  float(lat_lng.lng))

        # add geocoder connector here...
        self.address = None


class TagsObject(object):

    def __init__(self, osmid, key, value):
        self.osmid = int(osmid)
        self.key = key
        self.value = value
