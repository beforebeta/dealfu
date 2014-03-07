import json
import time
import datetime
import calendar

from elasticsearch.exceptions import TransportError
import requests

from dealfu_groupon.utils import get_redis, get_es
from dealfu_groupon.background.celery import app


try:
    #sometimes fails inside the tests
    from celery.utils.log import get_task_logger
    logger = get_task_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)



def compute_delay(settings, redis_conn):
    """
    Computes the delay that we should apply between 2 requests
    Basicly it sends back the delay (in secs) and the number of items
    that should be applied

    @returns back a tuple of :
        (delay, num_of_requests)


    """
    return settings.get("GOOGLE_GEO_DEFAULT_DELAY"), settings.get("GOOGLE_GEO_REQUESTS_PER_DAY")



@app.task
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
            print "INFINITE ======="
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


        #submit the item to the cache
        cache_addr = ":".join(formatted_list[1:])
        cache_key = settings.get("REDIS_GEO_CACHE_KEY") % cache_addr
        #print "FN_CACHE_KEY ",cache_key
        cache_item(redis_conn, cache_key, result)
        logger.info("Item submitted to the cache with key : {0}".format(cache_key))

        #at that point we should update the specified item's lat and lon
        update_save_item_addr(settings, item_id, cache_addr, result)
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
        for addr in item["merchant"]["addresses"]:
            if addr["address"] == formatted_addr_lst[0] and addr["region_long"] == formatted_addr_lst[1]:
                addr["geo_location"] = geo_info
                should_save = True
                break
        if should_save:
            _save_deal_item(settings, item_id, item, es_conn=es)

    except TransportError,ex:
        return False

    return True


def is_valid_address(addr_dict):
    """
    Check if supplied address dictionary is
    legitimate to be queried by google's api

    Should have at least :
    -address
    -region_long
    """
    mandatory = ["address", "region_long"]
    for m in mandatory:
        if not m in addr_dict:
            return False

    return True



def format_str_address(sdict, delimiter=":"):
    """
    the formatting will be in format
    address:region:postal_code
    """
    fields = ["address", "region_long", "postal_code"]
    lst = [sdict.get(f) for f in fields if sdict.has_key(f)]
    return delimiter.join(lst)


@app.task
def submit_geo_request(settings, item_id):
    """
    You submit a geo request
    the fn will check first the cache if there it will set
    the geolocation immediately and won't hit the google servers
    """
    es = get_es(settings)
    item = es.get(index=settings.get("ES_INDEX"),
                    doc_type=settings.get("ES_INDEX_TYPE_DEALS"),
                    id=item_id)['_source']

    logger.info("Submitting geo request for id : {0}".format(item_id))
    #print "ITEM fetched ",item

    merchant = item.get("merchant")
    if not merchant:
        raise Exception("No merchant info in item : %s"%item_id)

    addresses = merchant.get("addresses")

    if not merchant or not addresses:
        raise Exception("No address info in item : %s"%item_id)


    #check the cache for the given address
    to_check = [address for address in addresses if is_valid_address(address)]
    to_save = []
    redis_conn = get_redis(settings)
    #if it is there get it from cache

    cache_key = settings.get("REDIS_GEO_CACHE_KEY")
    fetch_queue_key = settings.get("REDIS_GEO_POLL_LIST")

    for address in to_check:
        formated_address = format_str_address(address)
        logger.info("Checking address : {0} for {1}".format(formated_address, item_id))
        if redis_conn.exists(cache_key%formated_address):
            logger.info("We have a cache hit {0} for {1}".format(formated_address, item_id))
            #get the cached value
            cached_addr = redis_conn.get(cache_key%formated_address)
            cached_addr = json.loads(cached_addr)

            cached_coords = extract_lang_lon_from_cached_result(cached_addr)
            lat = cached_coords["lat"]
            lon = cached_coords["lon"]

            address["geo_location"] = {}
            address["geo_location"]["lat"] = lat
            address["geo_location"]["lon"] = lon

            to_save.append(address)

        else:
            logger.info("We have a cache miss {0} for {1}".format(formated_address, item_id))
            #push it on queue  to be fetched later
            # we should encode the id here also when submitting
            # it to the part that processes the addresses
            formated_address = ":".join([item_id, formated_address])
            redis_conn.rpush(fetch_queue_key, formated_address)
            logger.info("Item submitted to be fetched : {0}".format(formated_address))

    #set on item
    if to_save:
        _save_deal_item(settings, item_id, item)
        logger.info("Items : {0} saved with address info in db".format(item_id))

    return True


def extract_lang_lon_from_cached_result(result):
    """
    Simple result extractor util
    """

    results = result["results"][0]["geometry"]["location"]

    #print "RESULTS : ",results

    return {
        "lat":results["lat"],
        "lon":results["lng"],
    }



def cache_item(redis_conn, address_key, geo_response):
    """
    Saves the queried address as cache value, so we can get it
    later again !
    """
    if redis_conn.exists(address_key):
        return False

    redis_conn.set(address_key, json.dumps(geo_response))
    return True



def _save_deal_item(settings, item_id, item, es_conn=None):
    """
    Saves the changed item into ES
    """
    if not es_conn:
        es = get_es(settings)
    else:
        es = es_conn

    es.index(index=settings.get("ES_INDEX"),
             doc_type=settings.get("ES_INDEX_TYPE_DEALS"),
             body=item,
             id=item_id)

    return True

