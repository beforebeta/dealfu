import json
import time
import datetime
import calendar
import logging
import sys


from elasticsearch.exceptions import TransportError
import requests
import cli.app

from dealfu_groupon.utils import get_redis, get_es, save_deal_item, extract_lang_lon_from_cached_result, \
    merge_dict_items
from scrapy.utils.project import get_project_settings


def get_default_logger(name):
    root = logging.getLogger(name)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)
    root.setLevel(logging.DEBUG)

    return root

logger = get_default_logger("dealfu_groupon.cli.geopoll")



@cli.app.CommandLineApp
def process_geo_requests_cli(app):
    """
    The main point of the application !
    """

    #we need that one to be startd when system is up
    settings = get_project_settings()
    return process_geo_requests(settings)


def compute_delay(settings, redis_conn):
    """
    Computes the delay that we should apply between 2 requests
    Basicly it sends back the delay (in secs) and the number of items
    that should be applied

    @returns back a tuple of :
        (delay, num_of_requests)


    """
    return settings.get("GOOGLE_GEO_DEFAULT_DELAY"), settings.get("GOOGLE_GEO_REQUESTS_PER_DAY")



def process_geo_requests(settings):
    """
    The main process that polls for new addresses to be gathered
    """
    delay, num_of_reqs = compute_delay(settings, None)
    logger.info("Starting the geo_request_processor with delay of : {0} for {1} reqs"
                .format(delay, num_of_reqs))

    while True:
        fetch_geo_addresses(settings, num_of_reqs, delay)
        delay, num_of_reqs = compute_delay(settings, None)
        logger.info("Setting the geo_request_processor with delay of : {0} for {1} reqs"
                .format(delay, num_of_reqs))




def fetch_geo_addresses(settings, num_of_requests, delay):
    """
    That task will check for submitted geolocation
    """

    def _iter_addr_queue(redis_conn, key):
        while True:
            logger.info("=== WAITING FOR ADDRESS TO FETCH ===")
            yield redis_conn.blpop(key)[1]

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

        payload = {"address":address,
                  "sensor":"false",
                  "key":settings.get("GOOGLE_GEO_API_KEY")}

        now = datetime.datetime.utcnow()
        r = requests.get(settings.get("GOOGLE_GEO_API_ENDPOINT"),
                         params=payload)

        #add an entry to the redis so we don't flood the api endpoint
        time_entry = calendar.timegm(now.utctimetuple())
        #print "TIME_ENTRY : ",float(time_entry)
        #print formatted_addr

        redis_conn.zadd(settings.get("REDIS_GEO_REQUEST_LOG"),
                        formatted_addr+":"+str(time_entry),
                        float(time_entry))

        logger.info("A new request log entry added : {0}".format(formatted_addr+":"+str(time_entry)))


        result = r.json()
        if result["status"] != "OK":
            #log something here and start waiting
            time.sleep(delay * 5)
            #TODO! we should retry that entry here again
            continue


        #submit the item to the cache
        cache_addr = ":".join(formatted_list[1:])
        cache_key = settings.get("REDIS_GEO_CACHE_KEY") % cache_addr
        #print "FN_CACHE_KEY ",cache_key
        cache_item(redis_conn, cache_key, result)
        logger.info("Item submitted to the cache with key : {0}".format(cache_key))

        #at that point we should update the specified item's lat and lon
        if update_save_item_addr(settings, item_id, cache_addr, result):
            logger.info("Item : {0} updated with geo info ".format(item_id))

        #wait for the desired time
        time.sleep(delay)

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


if __name__ == "__main__":
    process_geo_requests_cli.run()
