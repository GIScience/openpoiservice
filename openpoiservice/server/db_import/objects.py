# openpoiservice/server/poi_entity.py

import json
import logging
from geopy.geocoders import get_geocoder_for_service
# from geopy.extra.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

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


class GeocoderSetup(object):
    """Initialises geocoder"""

    def __init__(self, geocoder_name):
        self.geocoder_name = geocoder_name
        self.geocoder = None

    def define_geocoder(self):

        # returns warning if no valid geocoder is provided
        try:
            self.geocoder_settings = get_geocoder_for_service(self.geocoder_name[0])

        except Exception as err_geocoder:
            logger.warning(err_geocoder)
            return err_geocoder

        # returns warning if no valid geocoder settings are provided
        try:
            if self.geocoder_name[1] is not None:
                self.geocoder = self.geocoder_settings(**self.geocoder_name[1])

            else:
                self.geocoder = self.geocoder_settings()
            return self.geocoder

        except Exception as err_parameter:
            logger.warning(err_parameter)
            return err_parameter


class AddressObject(object):

    def __init__(self, lat_lng, geocoder):
        self.lat_lng = lat_lng[::-1]
        self.geocoder = geocoder

    def address_request(self):

        # address_delaied = RateLimiter(self.geocoder.reverse, min_delay_seconds=1)
        response = self.geocoder.reverse(query=self.lat_lng)

        # Checks if address for location is available
        if response is not None:
            return json.dumps(response.raw)
            # try:
            #     return json.dumps(response.raw)
            # except AttributeError:
            #     return json.dumps(response)

        return None
