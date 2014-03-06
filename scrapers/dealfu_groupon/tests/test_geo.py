"""
Test geolocation fns here
"""
from elasticsearch.exceptions import TransportError
from os.path import abspath, dirname
import os
import json

from dealfu_groupon.background.geocode import is_valid_address, format_str_address, submit_geo_request, cache_item, \
    extract_lang_lon_from_cached_result
from dealfu_groupon.utils import get_es, get_redis
from unittest import TestCase


def test_is_valid_address():
    a = {}
    assert not is_valid_address(a)

    a = {
        "address":"my address",
        "region_long":"New Mexico"
    }

    assert is_valid_address(a)



def test_format_str_address():
    a = {
        "address":"address",
        "region_long":"region",
        "postal_code":"zipcode"
    }

    assert format_str_address(a) == "address:region:zipcode"

    a = {
    "address":"address",
    "region_long":"region"
    }

    assert format_str_address(a) == "address:region"


GOOGLE_GEO_REQUESTS_PER_DAY = 2500
GOOGLE_GEO_REQUESTS_PERIOD = 24*60*60

TEST_SETTINGS_OBJECT = dict(
    SCRAPY_ROOT = dirname(dirname(abspath(__file__))),
    #ES_SETTINGS
    ES_SERVER = "192.168.0.113",
    ES_PORT = "9200",
    #ES index information
    ES_INDEX = "test_dealfu",
    ES_INDEX_TYPE_DEALS = "deal",
    ES_INDEX_TYPE_CATEGORY = "category",

    #REDIS QUEUE PARAMETERS
    REDIS_DEFAULT_DB = 1,
    REDIS_DEFAULT_QUEUE = "default_test",
    REDIS_HOST = "192.168.0.113",
    REDIS_PORT = 6379,
    REDIS_RETRY_PREFIX = "scrapy:retry:%s",
    REDIS_RETRY_COUNT = 4,
    REDIS_RETRY_DELAY = 20, #seconds to wait after we start retrying
    REDIS_RETRY_STATUS_READY = "READY",
    REDIS_RETRY_STATUS_FINISHED = "FINISHED",
    REDIS_RETRY_STATUS_FAILED = "FAILED",

    #REDIS GEO SETTINGS
    REDIS_GEO_CACHE_KEY = "scrapy:geo:cache:%s", #pattern for cached values so far !
    REDIS_GEO_POLL_LIST = "scrapy:geo:queue", # alist with items to pull

    #GOOGLE GEOCODING SETTINGS
    GOOGLE_GEO_API_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json",
    GOOGLE_GEO_REQUESTS_PER_DAY = GOOGLE_GEO_REQUESTS_PER_DAY,
    GOOGLE_GEO_REQUESTS_PERIOD = GOOGLE_GEO_REQUESTS_PERIOD,
    GOOGLE_GEO_DEFAULT_DELAY = GOOGLE_GEO_REQUESTS_PERIOD / GOOGLE_GEO_REQUESTS_PER_DAY
 )


from elasticsearch.client import IndicesClient


class TestSubmitGeoRequest(TestCase):

    def setUp(self):
        self.settings = TEST_SETTINGS_OBJECT
        self.es = get_es(self.settings)
        self.esi = IndicesClient(self.es)

        self.index = self.settings.get("ES_INDEX")

        #create the index firstly
        self.esi.create(index=self.index)

        mapping_path = os.path.join(self.settings.get("SCRAPY_ROOT"),
                                 "resources/mappings.json")

        mapping_str = open(mapping_path, "r").read()
        mappings = json.loads(mapping_str)


        for k,v in mappings.iteritems():
            res = self.esi.put_mapping(self.index, k, {k:mappings[k]})
            #print res


        self.redis_conn = get_redis(self.settings)


    def tearDown(self):
        if self.esi.exists(self.index):
            self.esi.delete(index=self.index)
            print "ES INDEX DELETED"

        #remove redis stuff
        self.redis_conn.flushdb()
        print "REDIS DB DELETED"


    def test_submit_non_existing_geo_item(self):
        """
        Test failure
        """
        self.assertRaises(TransportError,
                          submit_geo_request,
                          self.settings,
                          "fake_id")



    def test_submit_item_success(self):
        """
        It is the success scenario
        """
        item = {
            "merchant": {
                  "url": "http://northdallasmedspa.com",
                  "name": "Medical Aesthetics of North Dallas",
                  "addresses": [
                     {
                        "phone_number": "214-577-1777",
                        "country_code": "US",
                        "country": "United States",
                        "region": "TX",
                        "postal_code": "75093",
                        "address_name": "Plano",
                        "address": "4716 Alliance Boulevard Pavillion II, Suite 270 Plano",
                        "region_long": "Texas"
                     }
                  ]
               },
               "untracked_url": "http://www.groupon.com/deals/medical-aesthetics-of-north-dallas",
        }

        result = self.es.create(index=self.settings.get("ES_INDEX"),
                                doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                                body=item)

        doc_id = result.get("_id")

        self.assertEqual(submit_geo_request(self.settings,doc_id), True)

        #it should be submitted in queue so far
        address_queue_key = self.settings.get("REDIS_GEO_POLL_LIST")
        push_item = self.redis_conn.blpop(address_queue_key)[1]

        #print "PUSHED_ITEM ",push_item

        address, region, postal_code = push_item.split(":")
        self.assertEqual(address, item["merchant"]["addresses"][0]["address"])
        self.assertEqual(region, item["merchant"]["addresses"][0]["region_long"])
        self.assertEqual(postal_code, item["merchant"]["addresses"][0]["postal_code"])


    def test_submit_geo_request_cache_hit(self):
        """
        Tests the cache hit version
        """
        item = {
            "merchant": {
                  "url": "http://northdallasmedspa.com",
                  "name": "Medical Aesthetics of North Dallas",
                  "addresses": [
                     {
                        "phone_number": "214-577-1777",
                        "country_code": "US",
                        "country": "United States",
                        "region": "TX",
                        "postal_code": "75093",
                        "address_name": "Plano",
                        "address": "4716 Alliance Boulevard Pavillion II, Suite 270 Plano",
                        "region_long": "Texas"
                     }
                  ]
               },
               "untracked_url": "http://www.groupon.com/deals/medical-aesthetics-of-north-dallas",
        }

        result = self.es.create(index=self.settings.get("ES_INDEX"),
                                doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                                body=item)

        doc_id = result.get("_id")

        cached_request = {u'results': [
                            {u'address_components': [{u'long_name': u'75093',
                             u'short_name': u'75093',
                             u'types': [u'postal_code']},
                            {u'long_name': u'Plano',
                             u'short_name': u'Plano',
                             u'types': [u'locality', u'political']},
                            {u'long_name': u'Texas',
                             u'short_name': u'TX',
                             u'types': [u'administrative_area_level_1', u'political']},
                            {u'long_name': u'United States',
                             u'short_name': u'US',
                             u'types': [u'country', u'political']}],
                           u'formatted_address': u'Plano, TX 75093, USA',
                           u'geometry': {u'bounds': {u'northeast': {u'lat': 33.094414,
                              u'lng': -96.766645},
                             u'southwest': {u'lat': 33.007773, u'lng': -96.8602289}},
                            u'location': {u'lat': 33.0386278, u'lng': -96.8243812},
                            u'location_type': u'APPROXIMATE',
                            u'viewport': {u'northeast': {u'lat': 33.065598, u'lng': -96.766645},
                             u'southwest': {u'lat': 33.007773, u'lng': -96.8602289}}},
                           u'partial_match': True,
                           u'types': [u'postal_code']}],
                         u'status': u'OK'}


        #cache that result into redis, so test code can get it
        formatted_addr = format_str_address(item["merchant"]["addresses"][0])
        cache_key = self.settings.get("REDIS_GEO_CACHE_KEY") % formatted_addr
        cache_item(self.redis_conn, cache_key, cached_request)

        self.assertEqual(submit_geo_request(self.settings,doc_id), True)

        #now get the address from ES and check if it has address geo info
        item = self.es.get(index=self.settings.get("ES_INDEX"),
                            doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                            id=doc_id)['_source']

        geo_dict = extract_lang_lon_from_cached_result(cached_request)
        item_geo = item["merchant"]["addresses"][0]["geo_location"]

        self.assertEqual(geo_dict, item_geo)


    def test_submit_geo_request_partial_success(self):
        """
        That is the scenario when we have some of the addresses
        in our cache, but we don't have the other, so the code
        should be able to get those that are in cache and submit
        the new ones !!!
        """
        item = {
            "merchant": {
                  "url": "http://northdallasmedspa.com",
                  "name": "Medical Aesthetics of North Dallas",
                  "addresses": [
                     {
                        "phone_number": "214-577-1777",
                        "country_code": "US",
                        "country": "United States",
                        "region": "TX",
                        "postal_code": "75093",
                        "address_name": "Plano",
                        "address": "4716 Alliance Boulevard Pavillion II, Suite 270 Plano",
                        "region_long": "Texas"
                     },
                     {
                        "phone_number": "443-546-3968",
                        "country_code": "US",
                        "country": "United States",
                        "region": "MD",
                        "postal_code": "21045",
                        "address_name": "Columbia",
                        "address": "6476 Dobbin Center Way Columbia",
                        "region_long": "Maryland"
                     }
                  ]
               },
               "untracked_url": "http://www.groupon.com/deals/medical-aesthetics-of-north-dallas",
        }

        result = self.es.create(index=self.settings.get("ES_INDEX"),
                                doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                                body=item)

        doc_id = result.get("_id")

        cached_request = {u'results': [
                            {u'address_components': [{u'long_name': u'75093',
                             u'short_name': u'75093',
                             u'types': [u'postal_code']},
                            {u'long_name': u'Plano',
                             u'short_name': u'Plano',
                             u'types': [u'locality', u'political']},
                            {u'long_name': u'Texas',
                             u'short_name': u'TX',
                             u'types': [u'administrative_area_level_1', u'political']},
                            {u'long_name': u'United States',
                             u'short_name': u'US',
                             u'types': [u'country', u'political']}],
                           u'formatted_address': u'Plano, TX 75093, USA',
                           u'geometry': {u'bounds': {u'northeast': {u'lat': 33.094414,
                              u'lng': -96.766645},
                             u'southwest': {u'lat': 33.007773, u'lng': -96.8602289}},
                            u'location': {u'lat': 33.0386278, u'lng': -96.8243812},
                            u'location_type': u'APPROXIMATE',
                            u'viewport': {u'northeast': {u'lat': 33.065598, u'lng': -96.766645},
                             u'southwest': {u'lat': 33.007773, u'lng': -96.8602289}}},
                           u'partial_match': True,
                           u'types': [u'postal_code']}],
                         u'status': u'OK'}


        #cache that result into redis, so test code can get it
        formatted_addr = format_str_address(item["merchant"]["addresses"][0])
        cache_key = self.settings.get("REDIS_GEO_CACHE_KEY") % formatted_addr
        cache_item(self.redis_conn, cache_key, cached_request)

        self.assertEqual(submit_geo_request(self.settings,doc_id), True)

        #now get the address from ES and check if it has address geo info
        item = self.es.get(index=self.settings.get("ES_INDEX"),
                            doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                            id=doc_id)['_source']

        geo_dict = extract_lang_lon_from_cached_result(cached_request)
        item_geo = item["merchant"]["addresses"][0]["geo_location"]

        self.assertEqual(geo_dict, item_geo)

        #also we should have a new submission with one item which
        #will be the other address
        address_queue_key = self.settings.get("REDIS_GEO_POLL_LIST")
        push_item = self.redis_conn.blpop(address_queue_key)[1]
        #print "PUSHED_ITEM ",push_item
        #check if it is the second address in item
        address, region, postal_code = push_item.split(":")
        self.assertEqual(address, item["merchant"]["addresses"][1]["address"])
        self.assertEqual(region, item["merchant"]["addresses"][1]["region_long"])
        self.assertEqual(postal_code, item["merchant"]["addresses"][1]["postal_code"])


class TestProcessGeoRequest(TestCase):


    def setUp(self):
        pass

    def tearDown(self):
        pass

