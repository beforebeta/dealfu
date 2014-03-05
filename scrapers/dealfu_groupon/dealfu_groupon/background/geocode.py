import json
import time

from dealfu_groupon.utils import get_redis, merge_dict_items, get_es
from dealfu_groupon.background.celery import app

import requests

API_KEY = "AIzaSyADtvgG6dUm8JHXCX9fMRM96B68QSPI1n8"

@app.task
def process_geo_request(settings):
    """
    That task will check for submitted geolocation
    """

    def _iter_addr_queue(redis_conn, key):
        while True:
            yield redis_conn.blpop(key)

    #compute the submitted requsts for the last 24 hrs
    redis_conn = get_redis(settings)
    address_queue_key = settings.get("REDIS_GEO_POLL_LIST")

    for formated_addr in _iter_addr_queue(redis_conn, address_queue_key):
        #at that stage we will get the data from google
        payload = {"address":",".join([formated_addr.split(":")]),
                  "sensor":"false",
                  "key":settings.get("API_KEY")}

        r = requests.get(settings.get("GOOGLE_GEO_API_ENDPOINT"),
                         params=payload)

        result = r.json()
        if result["status"] != "OK":
            #log something here and start waiting
            time.sleep(settings.get("GOOGLE_GEO_DEFAULT_DELAY")*5)

        #submit the item to the cache
        cache_key = settings.get("REDIS_GEO_CACHE_KEY") % formated_addr
        cache_item(redis_conn, cache_key, result)

        #wait for the desired time
        time.sleep(settings.get("GOOGLE_GEO_DEFAULT_DELAY"))

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



def format_str_address(sdict):
    """
    the formatting will be in format
    address:region:postal_code
    """
    fields = ["address", "region_long", "postal_code"]
    lst = [sdict.get(f) for f in fields if sdict.has_key(f)]
    return ":".join(lst)


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
        if redis_conn.exists(cache_key%formated_address):
            #get the cached value
            cached_addr = redis_conn.get(cache_key%formated_address)
            cached_addr = json.loads(cached_addr)

            lat = cached_addr["geometry"]["location"]["lat"]
            lon = cached_addr["geometry"]["location"]["lon"]

            address["geo_location"]["lat"] = lat
            address["geo_location"]["lon"] = lon

            to_save.append(address)
        else:
            #push it on queue  to be fetched later
            redis_conn.rpush(fetch_queue_key, formated_address)

    #set on item
    if to_save:
        #we should merge the addresses here
        final_address_lst = []
        for a in addresses:
            for s in to_save:
                if a["address"] == s["address"]:
                    a = merge_dict_items(a, s)
            final_address_lst.append(a)

        item["merchant"]["addresses"] = final_address_lst
        #now save it to the database at that stage
        _save_deal_item(settings, item)

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


def _save_deal_item(settings, item, es_conn=None):
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
             id=item["id"])


    return True