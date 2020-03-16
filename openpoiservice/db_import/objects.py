# openpoiservice/server/poi_entity.py


class PoiObject(object):

    def __init__(self, uuid, categories, osmid, lat_lng, osm_type):
        self.uuid = uuid
        self.osmid = int(osmid)
        self.type = int(osm_type)
        self.categories = categories

        # self.geom = 'SRID={};POINT({} {})'.format(4326, float(lat_lng.lat),
        #                                          float(lat_lng.lng))

        self.geom = 'SRID={};POINT({} {})'.format(4326, float(lat_lng[0]),
                                                  float(lat_lng[1]))

        # add geocoder connector here...
        self.address = None


class TagsObject(object):

    def __init__(self, uuid, osmid, key, value):
        self.uuid = uuid
        self.osmid = int(osmid)
        self.key = key
        self.value = value
