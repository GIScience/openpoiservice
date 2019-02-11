# openpoiservice/server/poi_entity.py

from openpoiservice.server import ops_settings
from geopy.geocoders import * # get_geocoder_for_service
import json
from flask import jsonify, Response


class PoiObject(object):

    def __init__(self, uuid, categories, osmid, lat_lng, osm_type, address=None):
        self.uuid = uuid
        self.osmid = int(osmid)
        self.type = int(osm_type)
        self.categories = categories

        # self.geom = 'SRID={};POINT({} {})'.format(4326, float(lat_lng.lat),
        #                                          float(lat_lng.lng))

        self.geom = 'SRID={};POINT({} {})'.format(4326, float(lat_lng[0]),
                                                  float(lat_lng[1]))
        self.address = address


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

        # try:
        geocoder_settings = list(ops_settings['geocoder'].items())[0]
        geolocator = get_geocoder_for_service(geocoder_settings[0])

        if list(ops_settings['geocoder'].values())[0] is not None:
            setup_geolocator = geolocator(domain=geocoder_settings[1]['domain'],
                                          api_key=geocoder_settings[1]['api_key'])
        else:
            setup_geolocator = geolocator()

        response = setup_geolocator.reverse(query=self.lat_lng)
        # Checks if address for location is available
        if response is not None:
            return json.dumps(response.raw['properties'])

        # except AttributeError:
        #     pass


