# openpoiservice/server/poi_entity.py

from openpoiservice.server import ops_settings
from geopy.geocoders import * # get_geocoder_for_service
import json


class PoiObject(object):

    def __init__(self, uuid, categories, osmid, lat_lng, osm_type, address):
        self.uuid = uuid
        self.osmid = int(osmid)
        self.type = int(osm_type)
        self.categories = categories

        # self.geom = 'SRID={};POINT({} {})'.format(4326, float(lat_lng.lat),
        #                                          float(lat_lng.lng))

        self.geom = 'SRID={};POINT({} {})'.format(4326, float(lat_lng[0]),
                                                  float(lat_lng[1]))
        self.address = address

        # self.address = AddressObject(lat_lng).address_request()


class TagsObject(object):

    def __init__(self, uuid, osmid, key, value):
        self.uuid = uuid
        self.osmid = int(osmid)
        self.key = key
        self.value = value


class AddressObject(object):

    def __init__(self, lat_lng):
        self.lat_lng = lat_lng[::-1]

    def address_request(self):

        for geocoder, settings in ops_settings['geocoder'].items():
            if geocoder == 'pelias':
                domain = ops_settings['geocoder']['pelias']['domain']
                api_key = ops_settings['geocoder']['pelias']['api_key']
                geolocator = Pelias(domain=domain, api_key=api_key)
                response = geolocator.reverse(query=self.lat_lng)
                return json.dumps(response.raw['properties'])
                # return json.dumps(response.raw['properties'], sort_keys=True, ensure_ascii=False)
                # json_data = json.dumps(response.raw['properties'], ensure_ascii=False)
                # return json.loads(json_data)
            else:
                geolocator = get_geocoder_for_service(geocoder)
                response = geolocator().reverse(query=self.lat_lng)
                return response.raw['address']
                # json_data = json.dumps(response.raw['address'], sort_keys=True)
                # return json.loads(json_data)
