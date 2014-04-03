import json
import time
import datetime
import calendar


from elasticsearch.exceptions import TransportError
import requests
import cli.app

from dealfu_groupon.utils import get_redis, get_es, save_deal_item, extract_lang_lon_from_cached_result, \
    merge_dict_items, get_default_logger
from scrapy.utils.project import get_project_settings


logger = get_default_logger("dealfu_groupon.cli.geopoll")


@cli.app.CommandLineApp
def process_geo_requests_cli(app):
    """
    The main point of the application !
    """

    #we need that one to be startd when system is up
    settings = get_project_settings()
    return process_geo_requests(settings, app.params.geoapi)

process_geo_requests_cli.add_param("geoapi", help="geoapi to use [google, datascience]", default="google", type=str)


def process_geo_requests(settings, geoapi_str):
    """
    The main process that polls for new addresses to be gathered
    """
    geo_api = get_current_geo_api(settings, geoapi_str)
    delay, num_of_reqs = geo_api.compute_delay()
    logger.info("Starting the geo_request_processor with delay of : {0} for {1} reqs"
                .format(delay, num_of_reqs))

    while True:
        fetch_geo_addresses(settings, num_of_reqs, geo_api)
        delay, num_of_reqs = geo_api.compute_delay()
        logger.info("Setting the geo_request_processor with delay of : {0} for {1} reqs"
                .format(delay, num_of_reqs))




def fetch_geo_addresses(settings, num_of_requests, geoapi):
    """
    That task will check for submitted geo location
    """

    def _iter_addr_queue(redis_conn, key):
        while True:
            logger.info("=== WAITING FOR ADDRESS TO FETCH ===")
            #implement a more reliable thing here
            yield redis_conn.brpoplpush(key, key)


    #compute the submitted requsts for the last 24 hrs
    redis_conn = get_redis(settings)
    address_queue_key = settings.get("REDIS_GEO_POLL_LIST")
    processed_requests = 0

    for formatted_addr in _iter_addr_queue(redis_conn, address_queue_key):
        #at that stage we will get the data from google
        logger.info("Pulling geo info for : {0}".format(formatted_addr))

        formatted_list = formatted_addr.split(":")
        #the first part is the id of the item ignore it
        item_id = formatted_list[0] #will be used later
        address = ",".join(formatted_list[1:])

        now = datetime.datetime.utcnow()
        #add an entry to the redis so we don't flood the api endpoint
        time_entry = calendar.timegm(now.utctimetuple())
        #print "TIME_ENTRY : ",float(time_entry)
        #print formatted_addr

        redis_conn.zadd(settings.get("REDIS_GEO_REQUEST_LOG"),
                        formatted_addr+":"+str(time_entry),
                        float(time_entry))

        logger.info("A new request log entry added : {0}".format(formatted_addr+":"+str(time_entry)))

        result = geoapi.fetch_geo(address)

        #submit the item to the cache
        cache_addr = ":".join(formatted_list[1:])
        cache_key = settings.get("REDIS_GEO_CACHE_KEY") % cache_addr
        #print "FN_CACHE_KEY ",cache_key
        cache_item(redis_conn, cache_key, result)
        logger.info("Item submitted to the cache with key : {0}".format(cache_key))

        #at that point we should update the specified item's lat and lon
        if update_save_item_addr(settings, item_id, cache_addr, result):
            logger.info("Item : {0} updated with geo info ".format(item_id))


        #now you should remove the found item from queue
        #note that this is different than StrictRedis interface
        redis_conn.lrem(address_queue_key, formatted_addr, 1)

        #print "Removing address : ",formatted_addr
        #print "Keys : ",redis_conn.lrange(address_queue_key, 0, -1)
        #print "Equal : ",redis_conn.lrange(address_queue_key, 0, -1)[0] == formatted_addr
        #print "Remove result : ",redis_conn.lrem(address_queue_key, formatted_addr, 1)

        #wait for the desired time
        time.sleep(geoapi.delay)



        processed_requests += 1
        if processed_requests == num_of_requests:
            break


    return True


def update_save_item_addr(settings, item_id, formatted_addr, geo_result):

    es = get_es(settings)
    try:
        item = es.get(index=settings.get("ES_INDEX"),
                      doc_type=settings.get("ES_INDEX_TYPE_DEALS"),
                      id=item_id)['_source']

        formatted_addr_lst = formatted_addr.split(":")
        geo_info = extract_lang_lon_from_cached_result(geo_result)

        should_save = False
        index = -1
        for i, addr in enumerate(item["merchant"]["addresses"]):
            if addr["address"] == formatted_addr_lst[0]:
                index = i
                should_save = True
                break

        if should_save:
            #merge 2 addresses so we have the best of two
            item["merchant"]["addresses"][index] = merge_dict_items(item["merchant"]["addresses"][index],
                                                                    geo_info)
            save_deal_item(settings, item_id, item, es_conn=es)

    except TransportError,ex:
        return False

    return True


def cache_item(redis_conn, address_key, geo_response):
    """
    Saves the queried address as cache value, so we can get it
    later again !
    """
    if redis_conn.exists(address_key):
        return False

    redis_conn.set(address_key, json.dumps(geo_response))
    return True


class GoogleGeoApi(object):
    """
    Converts the address data to geo data
    from google api
    """

    def __init__(self, settings):

        self.settings = settings
        self.api_key = settings["GOOGLE_GEO_API_KEY"]
        self.api_endpoint = settings.get("GOOGLE_GEO_API_ENDPOINT")
        self.delay = self.compute_delay()[0]


    def get_payload(self, address):

        return {"address":address,
                  "sensor":"false",
                  "key":self.api_key
                }


    def compute_delay(self):
        """
        Computes the delay between 2 requests
        """
        return self.settings.get("GOOGLE_GEO_DEFAULT_DELAY"), self.settings.get("GOOGLE_GEO_REQUESTS_PER_DAY")


    def fetch_geo(self, address):

        retry_count = 5

        while retry_count > 0:
            payload = self.get_payload(address)

            r = requests.get(self.api_endpoint,
                             params=payload)

            result = r.json()
            if result["status"] != "OK":
                #log something here and start waiting
                time.sleep(self.delay * 5)
                retry_count -= 1
                continue
            else:
                #we're done exit
                return result

        raise GeoApiError("Retry count exceeded!")


class DataScienceToolkitGeoApi(GoogleGeoApi):

    def __init__(self, settings):

        self.settings = settings
        self.api_endpoint = settings.get("DATASCIENCE_GEO_API_ENDPOINT")
        self.delay = self.compute_delay()[0]


    def get_payload(self, address):
        """
        Overriden payload
        """

        return {
            "address":address,
            "sensor":"false"
        }


    def compute_delay(self):
        """
        Computes the delay between 2 requests
        """
        return 1, 1000000


class GeoApiError(Exception):
    pass


def get_current_geo_api(settings, geo_api):
    """
    A factory to choose the right geo api class
    """
    if geo_api == "google":
        return GoogleGeoApi(settings)
    elif geo_api == "datascience":
        return DataScienceToolkitGeoApi(settings)
    else:
        raise GeoApiError("No suitable factory for : {}".format(geo_api))



if __name__ == "__main__":
    process_geo_requests_cli.run()
