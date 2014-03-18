"""
Test geolocation fns here
"""
import json
import datetime
import calendar
from unittest import TestCase

from dealfu_groupon.utils import get_es, get_redis
from elasticsearch.exceptions import TransportError
from mock import MagicMock, patch
from os.path import abspath, dirname
import os
from dealfu_groupon.background.geocode import is_valid_address, format_str_address, submit_geo_request, \
    extract_lang_lon_from_cached_result
from dealfu_groupon.cli.geopoll import cache_item, fetch_geo_addresses


def test_is_valid_address():
    a = {}
    assert not is_valid_address(a)

    a = {
        "address":"my address"
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


def _get_default_google_resp():
    return {u'results': [
                {u'address_components': [
                    {   u'long_name': u'75093',
                        u'short_name': u'75093',
                        u'types': [u'postal_code']
                    },
                    {   u'long_name': u'Plano',
                        u'short_name': u'Plano',
                        u'types': [u'locality', u'political']
                    },
                    {   u'long_name': u'Texas',
                        u'short_name': u'TX',
                        u'types': [u'administrative_area_level_1', u'political']
                    },
                    {   u'long_name': u'United States',
                        u'short_name': u'US',
                        u'types': [u'country', u'political']
                    }],

                u'formatted_address': u'Plano, TX 75093, USA',
                u'geometry': {
                    u'bounds': {u'northeast': {u'lat': 33.094414, u'lng': -96.766645},
                    u'southwest': {u'lat': 33.007773, u'lng': -96.8602289}},
                    u'location': {u'lat': 33.0386278, u'lng': -96.8243812},
                    u'location_type': u'APPROXIMATE',
                    u'viewport': {u'northeast': {u'lat': 33.065598, u'lng': -96.766645},
                    u'southwest': {u'lat': 33.007773, u'lng': -96.8602289}}
                },
               u'partial_match': True,
               u'types': [u'postal_code']}
              ],
              u'status': u'OK'}


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
    REDIS_GEO_REQUEST_LOG = "scrapy:geo:requests",

    #GOOGLE GEOCODING SETTINGS
    GOOGLE_GEO_API_KEY = "fake_test",
    GOOGLE_GEO_API_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json",
    GOOGLE_GEO_REQUESTS_PER_DAY = GOOGLE_GEO_REQUESTS_PER_DAY,
    GOOGLE_GEO_REQUESTS_PERIOD = GOOGLE_GEO_REQUESTS_PERIOD,
    GOOGLE_GEO_DEFAULT_DELAY = GOOGLE_GEO_REQUESTS_PERIOD / GOOGLE_GEO_REQUESTS_PER_DAY
 )


from elasticsearch.client import IndicesClient


class RedisEsSetupMixin(object):

    def setUp(self):
        self.settings = TEST_SETTINGS_OBJECT
        self.es = get_es(self.settings)
        self.esi = IndicesClient(self.es)

        self.index = self.settings.get("ES_INDEX")

        #create the index firstly
        if self.esi.exists(self.index):
            self.esi.delete(index=self.index)

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


class TestSubmitGeoRequest(RedisEsSetupMixin, TestCase):


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
            "online":False,
            "merchant": {
                  "url": "http://northdallasmedspa.com",
                  "name": "Medical Aesthetics of North Dallas",
                  "addresses": [
                     {
                        "phone_number": "214-577-1777",
                        "country_code": "US",
                        "country": "United States",
                        "address_name": "Plano",
                        "address": "4716 Alliance Boulevard Pavillion II, Suite 270 Plano"
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

        item_id, address = push_item.split(":")
        self.assertEqual(item_id, doc_id)
        self.assertEqual(address, item["merchant"]["addresses"][0]["address"])


    def test_submit_geo_request_cache_hit(self):
        """
        Tests the cache hit version
        """
        item = {
            "online":False,
            "merchant": {
                  "url": "http://northdallasmedspa.com",
                  "name": "Medical Aesthetics of North Dallas",
                  "addresses": [
                     {
                        "phone_number": "214-577-1777",
                        "country_code": "US",
                        "country": "United States",
                        "address_name": "Plano",
                        "address": "4716 Alliance Boulevard Pavillion II, Suite 270 Plano",
                     }
                  ]
               },
               "untracked_url": "http://www.groupon.com/deals/medical-aesthetics-of-north-dallas",
        }

        result = self.es.create(index=self.settings.get("ES_INDEX"),
                                doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                                body=item)

        doc_id = result.get("_id")
        cached_request = _get_default_google_resp()


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
        item_geo = item["merchant"]["addresses"][0]

        self.assertEqual(geo_dict["geo_location"], item_geo["geo_location"])
        self.assertEqual(geo_dict["postal_code"], item_geo["postal_code"])
        self.assertEqual(geo_dict["region"], item_geo["region"])
        self.assertEqual(geo_dict["region_long"], item_geo["region_long"])
        self.assertEqual(geo_dict["country"], item_geo["country"])
        self.assertEqual(geo_dict["country_code"], item_geo["country_code"])



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
                        "address_name": "Plano",
                        "address": "4716 Alliance Boulevard Pavillion II, Suite 270 Plano",
                     },
                     {
                        "phone_number": "443-546-3968",
                        "country_code": "US",
                        "country": "United States",
                        "address_name": "Columbia",
                        "address": "6476 Dobbin Center Way Columbia",
                     }
                  ]
               },
               "online":False,
               "untracked_url": "http://www.groupon.com/deals/medical-aesthetics-of-north-dallas",
        }

        result = self.es.create(index=self.settings.get("ES_INDEX"),
                                doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                                body=item)

        doc_id = result.get("_id")

        cached_request = _get_default_google_resp()


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
        item_geo = item["merchant"]["addresses"][0]

        #print "GEO_DICT",geo_dict,
        #print "ITEM_DICT"
        _should_first_in_second(geo_dict, item_geo)

        #also we should have a new submission with one item which
        #will be the other address
        address_queue_key = self.settings.get("REDIS_GEO_POLL_LIST")
        push_item = self.redis_conn.blpop(address_queue_key)[1]
        #print "PUSHED_ITEM ",push_item
        #check if it is the second address in item
        item_id, address = push_item.split(":")
        self.assertEqual(item_id, doc_id)
        self.assertEqual(address, item["merchant"]["addresses"][1]["address"])



def _should_first_in_second(first, second):
    """
    An util to check if all values in first are
    in second and are identical
    """
    for k,v in first.iteritems():
        assert second[k] == v


class TestProcessGeoRequest(RedisEsSetupMixin, TestCase):

    @patch("dealfu_groupon.cli.geopoll.requests")
    def test_fetch_geo_addresses_success(self, mock_requests):
        class GetJson(object):

            def __init__(self, response):
                self.response = response

            def json(self):
                return self.response

        item = {
            "merchant": {
                  "url": "http://northdallasmedspa.com",
                  "name": "Medical Aesthetics of North Dallas",
                  "addresses": [
                     {
                        "phone_number": "214-577-1777",
                        "country_code": "US",
                        "country": "United States",
                        "address_name": "Plano",
                        "address": "4716 Alliance Boulevard Pavillion II, Suite 270 Plano",
                     },
                     {
                        "phone_number": "443-546-3968",
                        "country_code": "US",
                        "country": "United States",
                        "address_name": "Columbia",
                        "address": "6476 Dobbin Center Way Columbia",
                     }
                  ]
               },
               "online":False,
               "untracked_url": "http://www.groupon.com/deals/medical-aesthetics-of-north-dallas",
        }

        result = self.es.create(index=self.settings.get("ES_INDEX"),
                                doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                                body=item)

        doc_id = result.get("_id")


        mock_response = _get_default_google_resp()


        get_mock = MagicMock(return_value=GetJson(mock_response))
        mock_requests.get = get_mock

        address_dict = {
                        "phone_number": "214-577-1777",
                        "country_code": "US",
                        "country": "United States",
                        "address_name": "Plano",
                        "address": "4716 Alliance Boulevard Pavillion II, Suite 270 Plano",
                     }

        formatted_addr = format_str_address(address_dict)
        formatted_addr_id = doc_id + ":" + formatted_addr

        #add it on the queue
        fetch_queue_key = self.settings.get("REDIS_GEO_POLL_LIST")
        self.redis_conn.rpush(fetch_queue_key, formatted_addr_id)

        assert  fetch_geo_addresses(self.settings, 1, 0.1)

        #now check the cache we should have one value there
        cache_key = self.settings.get("REDIS_GEO_CACHE_KEY")%formatted_addr
        #print "CACHE_KEY  :",cache_key
        self.assertEqual(self.redis_conn.exists(cache_key), True)

        cache_result = json.loads(self.redis_conn.get(cache_key))
        geo_dict = extract_lang_lon_from_cached_result(cache_result)

        assert geo_dict["geo_location"]["lat"]
        assert geo_dict["geo_location"]["lon"]

        #we should check the mocked request args
        args, kwargs = get_mock.call_args

        #print "KWARGS : ",kwargs
        self.assertEqual(kwargs["params"]["address"],
                         format_str_address(address_dict, delimiter=","))

        #the last step is to check the zset member if it is there !
        now_time = datetime.datetime.utcnow()
        before_time = now_time - datetime.timedelta(hours=24)

        now = calendar.timegm(now_time.utctimetuple())
        before = calendar.timegm(before_time.utctimetuple())

        time_logs =  self.redis_conn.zrangebyscore(self.settings.get("REDIS_GEO_REQUEST_LOG"),
                                            before,
                                            now)
        assert len(time_logs) == 1
        time_stamp = int(time_logs[0].split(":")[-1])
        log_time = datetime.datetime.utcfromtimestamp(time_stamp)

        assert log_time < now_time
        assert log_time > before_time

        #also check if the address is update of the item

        fresh_item = self.es.get(index=self.settings.get("ES_INDEX"),
                            doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                            id=doc_id)['_source']

        #check if we have lat/lon
        address = fresh_item["merchant"]["addresses"][0]
        _should_first_in_second(geo_dict, address)
