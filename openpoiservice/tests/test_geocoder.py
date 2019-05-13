# openpoiservice/server/tests/test_main.py


import unittest
import json
from openpoiservice.server.db_import.objects import AddressObject, GeocoderSetup
from openpoiservice.server.categories.categories import CategoryTools

# from base import BaseTestCase
from openpoiservice.tests.base import BaseTestCase

# VALID GEOCODER AND PARAMETER
valid_geocoder_param = dict(
    nominatim=dict(
        timeout=60
    )
)

# VALID GEOCODER FOR class TestGeocoderBlueprint
valid_geocoder = GeocoderSetup(list(valid_geocoder_param.items())[0]).define_geocoder()

# INVALID GEOCODER
invalid_geocoder = dict(
    peliaas=dict()
)

# INVALID GEOCODER LOGGER RESPONSE
logger_message_geocoder = "Unknown geocoder 'peliaas'; " \
                 "options are: dict_keys(['arcgis', 'azure', 'baidu', 'banfrance', 'bing', 'databc', 'geocodeearth', " \
                 "'geocodefarm', 'geonames', 'google', 'googlev3', 'geolake', 'here', 'ignfrance', 'mapbox', " \
                 "'opencage', 'openmapquest', 'pickpoint', 'nominatim', 'pelias', 'photon', 'liveaddress', 'tomtom', " \
                 "'what3words', 'yandex'])"

# MISSING PARAMETER
missing_key = dict(
    azure=dict(
        domain='atlas.microsoft.com'
    )
)

# MISSING PARAMETER LOGGER RESPONSE
logger_message_parameter = "__init__() missing 1 required positional argument: 'subscription_key'"

# VALID COORDINATES
coordinates = [8.807527, 53.07620980000001]

# VALID GEOCODE CATEGORY ID
college_category_id = 151

# INVALID GEOCODE CATEGORY ID
bench_category_id = 162


class TestGeocoderBlueprint(BaseTestCase):

    def test_valid_geocoder(self):
        response = GeocoderSetup(list(valid_geocoder_param.items())[0]).define_geocoder()
        self.assertEqual('https://nominatim.openstreetmap.org/search', response.api)

    def test_unvalid_geocoder(self):
        response = GeocoderSetup(list(invalid_geocoder.items())[0]).define_geocoder()
        self.assertEqual(logger_message_geocoder, response.args[0])

    def test_missing_key(self):
        response = GeocoderSetup(list(missing_key.items())[0]).define_geocoder()
        self.assertEqual(logger_message_parameter, response.args[0])


class TestAddressBlueprint(BaseTestCase):

    def test_address_request(self):
        response = json.loads(AddressObject(coordinates, valid_geocoder).address_request())
        self.assertEqual('Stadtbezirk Bremen-Mitte', response['address']['city_district'])

    def test_address_type(self):
        response = AddressObject(coordinates, valid_geocoder).address_request()
        self.assertTrue(json.loads(response))


class TestGeocodeCategoriesBlueprint(BaseTestCase):

    def test_geocode_categories(self):
        response = CategoryTools('categories.yml').generate_geocode_categories()
        self.assertTrue(college_category_id in response)
        self.assertTrue(bench_category_id not in response)


if __name__ == '__main__':
    unittest.main()
