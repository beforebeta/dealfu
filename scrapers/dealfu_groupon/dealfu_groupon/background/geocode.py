import json
import time
import datetime
import calendar

from elasticsearch.exceptions import TransportError
import requests

from dealfu_groupon.utils import get_redis, get_es, save_deal_item, extract_lang_lon_from_cached_result, \
    merge_dict_items
from dealfu_groupon.background.celery import app


try:
    #sometimes fails inside the tests
    from celery.utils.log import get_task_logger
    logger = get_task_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)




def is_valid_address(addr_dict):
    """
    Check if supplied address dictionary is
    legitimate to be queried by google's api

    Should have at least :
    -address
    -region_long
    """
    mandatory = ["address"]
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
            merged_addr = merge_dict_items(address, cached_coords)

            to_save.append(merged_addr)

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
        merge_list = _merge_addr_lists(item["merchant"]["addresses"], to_save)
        item["merchant"]["addresses"] = merge_list
        save_deal_item(settings, item_id, item)
        logger.info("Items : {0} saved with address info in db".format(item_id))

    return True




def _merge_addr_lists(first, second):
    """
    Merges two lists if "address" field is
    same take the second otherwise get the first
    """
    merged_list = []
    for f in first:
        for s in second:
            if f["address"] == s["address"]:
                merged_list.append(s)
            else:
                merged_list.append(f)

    return merged_list
