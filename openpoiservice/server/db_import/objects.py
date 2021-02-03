# openpoiservice/server/poi_entity.py


class PoiObject(object):

    def __init__(self, osm_type, osmid, lat_lng, categories):
        self.osmtype = int(osm_type)
        self.osmid = int(osmid)
        self.categories = categories
        self.geom = f"SRID=4326;POINT({float(lat_lng[0])} {float(lat_lng[1])})"
        # add geocoder connector here...
        self.address = None


class TagsObject(object):

    def __init__(self, osmtype, osmid, key, value):
        self.osmtype = int(osmtype)
        self.osmid = int(osmid)
        self.key = key
        self.value = value
