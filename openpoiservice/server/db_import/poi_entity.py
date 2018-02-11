# openpoiservice/server/poi_entity.py


class PoiEntity(object):

    def __init__(self, category, osmid, tags, lat_lng, osm_type):

        self.osmid = int(osmid)
        self.type = int(osm_type)
        self.category = int(category)
        self.latitude = lat_lng.lat
        self.longitude = lat_lng.lng
        self.name = None
        self.wheelchair_access = None
        self.smoking = None
        self.fee = None
        self.opening_hours = None
        self.phone = None
        self.website = None

        for tag, value in tags.iteritems():
            if tag == 'name':
                self.name = value

            elif tag == 'wheelchair':
                self.wheelchair_access = 'yes' if value == 'true' else 'no'
                self.wheelchair_access = value

            elif tag == 'smoking':
                self.smoking = 'yes' if value == 'true' else 'no'
                self.smoking = value

            elif tag == 'fee':
                self.fee = value

            elif tag == 'opening_hours':
                self.opening_hours = value

            elif tag == 'phone' or tag == 'contact:phone':
                self.phone = value

            elif tag == 'website':
                self.website = value

            self.address = None
