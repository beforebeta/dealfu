"""
Some useful common functions
"""
import urllib
import re
import functools
import sys
import logging
from copy import copy
from urlparse import urlparse
import unicodedata

import elasticsearch
from redis import Redis

from dealfu_groupon.items import MerchantAddressItem, DealCategoryItem



#spider utils
def get_fresh_merchant_address():
    """
    Gets a MerchantItem with defaults attached to it
    @return:
    """
    m = MerchantAddressItem()
    m["country"] = "United States"
    m["country_code"] = "US"
    #m["latitude"] = 0.0
    #m["longtitude"] = 0.0
    m["address_name"] = ""

    return m

def get_dealfu_category(name, parent=None):
    """
    Factory for dealfu category
    """
    dc = DealCategoryItem()
    dc["name"] = name
    dc["slug"] = slugify(unicode(name))
    dc["parent_slug"] = slugify(unicode(parent)) if parent else None

    return dc



def get_first_from_xp(xp, missing=None):
    """
    Asks for the first value in the xpath if available
    if not missing is returned back
    @param xp:
    @param missing:
    @return: value or missing
    """
    if not xp:
        return missing

    return xp[0].extract()


#url utils

def extract_query_params(url, *names):
    """
    Extracts names in the list from url
    @param url:
    @param names:
    @return: dict
    """
    parsed_res = urlparse.urlparse(url)
    d = urlparse.parse_qs(parsed_res.query)

    return {key:value[0] for (key, value) in d.iteritems() if key in names}



def replace_query_param(url, name, value):
    encoded_str = urllib.urlencode({name:value})
    d = extract_query_params(url, name)
    encoded_old = urllib.urlencode({name:d.get(name)})

    return url.replace(encoded_old, encoded_str)




#ES UTILS
def get_es(settings):
    """
    Gets an ES handle
    """
    d = {
        "host":settings.get("ES_SERVER"),
        "port":settings.get("ES_PORT")
    }

    return elasticsearch.Elasticsearch(hosts=[d])


def es_get_batch(settings, es, from_pg, per_page, query=None):
    """
    Gets a batch from specified query or from all
    """
    if not query:
        query = {
            "query":{
                "match_all": {}
            }
        }

    query["from"] = from_pg
    query["size"] = per_page

    result = es.search(index=settings["ES_INDEX"],
                       doc_type=settings["ES_INDEX_TYPE_DEALS"],
                       body=query)

    total = result["hits"]["total"]
    if total == 0:
        return []

    return result["hits"]["hits"]


def save_deal_item(settings, item_id, item, es_conn=None, update=True):
    """
    Saves the changed item into ES
    """
    if not es_conn:
        es = get_es(settings)
    else:
        es = es_conn

    #at that stage we should check if we need to
    #do some enabled checks
    if not item.get("enabled") and should_item_be_enabled(item):
        item["enabled"] = True

    if not update:
        es.index(index=settings.get("ES_INDEX"),
                 doc_type=settings.get("ES_INDEX_TYPE_DEALS"),
                 body=item,
                 id=item_id)
    else:
        #partial update that is better
        es.update(index=settings.get("ES_INDEX"),
                 doc_type=settings.get("ES_INDEX_TYPE_DEALS"),
                 body={"doc":item},
                 id=item_id)

    return True



#redis utils

def get_redis(settings):
    """
    Gets a redis connection from supplied settings
    """
    db_num = settings.get("REDIS_DEFAULT_DB", 0)

    redis_conn = Redis(host=settings.get("REDIS_HOST"),
                       port=settings.get("REDIS_PORT"),
                       db=db_num)

    return redis_conn



def is_item_in_geo_queue(redis_conn, redis_key ,item_id):
    """
    Checks if item_id is in queue of geo encoding fetch
    It seems it is not very wise to traverse whole list
    but it will work for now at least, later may replace
    with ordered set if have some per bottleneck
    """
    results = redis_conn.lrange(redis_key, 0, -1)
    for r in results:
        if r.split(":")[0].strip() == item_id:
            return True

    return False



#item validation

def are_addresses_geo_encoded(item):
    """
    Checks an items addresses if they're geo encoded
    """
    addresses = get_in(item, "merchant", "addresses")
    if not addresses:
        return False

    not_in = lambda x : True if not x.get("geo_location") else False
    if some(not_in, addresses):
        #if we have some blank fields they should not be enabled
        return False

    #we're good
    return True


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



def missing_mandatory_field(item):
    """
    Checks the item for mandatory fields
    """

    mandatory = (
        "description",
        "title",
        "short_title",
        "merchant",
        "category_name",
        "category_slug",
    )


    merchant_mandatory = (
        "name",
    )

    merchant_mandatory_offline = (
        "addresses",
    )


    if any([False if item.get(f) else True for f in mandatory]):
        return True


    #check mandatory merchant fields
    merchant = item.get("merchant")
    if any([False if merchant.get(f) else True for f in merchant_mandatory]):
        return True


    if not item["online"]:
        if any([False if merchant.get(f) else True for f in merchant_mandatory_offline]):
            return True

        #now check if we have at least the address
        if not merchant.get("addresses")[0]:
            return True


    if needs_price_retry(item):
        return True

    return False




def should_item_be_enabled(item):
    """
    Checks if item should be enabled or not
    """
    if missing_mandatory_field(item):
        return False

    #if it is offline check for geo encoding
    if not item["online"] and not are_addresses_geo_encoded(item):
        return False

    #we're good
    return True



def needs_geo_fetch(item, item_id=None, logger=None):
    """
    Checks if supplied item should be submitted
    for geolocation fetching
    """
    if not logger:
        logger = logging.getLogger()

    if not item_id:
        item_id = item.get("id", "not_created")



    merchant = item.get("merchant")
    if not merchant:
        logger.warn("No merchant info, not submitted for geo request : {0}"
                    .format(item_id))
        return False

    addresses = merchant.get("addresses")
    if not addresses:
        logger.warn("No address info, not submitted for geo request : {0}"
                    .format(item_id))
        return False


    if not any([a for a in addresses if is_valid_address(a)]):
        logger.warn("No valid address info, not submitted for geo request : {0}"
                    .format(item_id))
        return False

    #check if all of the addresses are geo enabled
    #if yes no need for checking
    if all([not needs_address_geo_fetch(a) for a in addresses]):
        logger.warn("All of addresses are geo encoded ")
        return False

    #logger.info("Item should be geo encoded")


    return True


def needs_address_geo_fetch(address):
    """
    Checks if address item need geo fect
    """
    return False if address.get("geo_location") else True



def needs_retry(item):
    """
    Method checks the given item if it should be
    re-parsed or not. Basically the mandatory fields are
    """

    #if it doesnt have those we need a retry
    mandatory = ("merchant",)


    #if when offline deal those are not here we should retry
    merchant_mandatory_offline = (
        "addresses",
    )

    if any([False if item.get(f) else True for f in mandatory]):
        return True

    if not item["online"]:
        #if it is online those ar not relevant
        merchant = item.get("merchant")
        if any([False if merchant.get(f) else True for f in merchant_mandatory_offline]):
            return True

        #now check if we have at least the address
        if not merchant.get("addresses")[0]:
            return True


    return False


def needs_price_retry(item):
    """
    Checks if current item needs a price refetch
    """
    optional = (
        "price",
        "discount_amount",
        "discount_percentage",
    )

    #check the optional pieces here
    if any([True if item.get(f) else False for f in optional]):
        return False

    return True



#fn programming utilities

def some(fn, iterable):
    """
    An useful util
    """
    for i in iterable:
        if fn(i):
            return True

    return False


def get_in(d, *args):
    if not d:
        return None

    if args:
        return get_in(d.get(args[0]), *args[1:])
    else:
        return d




def merge_dict_items(first, second):
    """
    That merge is a little bit different from the one
    that is builtin in Python, in builtin fn generally
    the second item should override the parts in first one,
    but what we need is second to override only when there is
    a value. If for example we have 2 dicts like :

    d1 = {"one":1, "two":None}
    d2 = {"one":None, "two":2}

    the result of merging should be :

    d3 = {"one":1, "two":2}
    """
    d3 = copy(first)

    for k,v in second.iteritems():
        if not v:
            #we are not interested in empty values
            continue
        elif isinstance(v, dict):
            if not d3.get(k) is None:
                tmp = merge_dict_items(d3[k], second[k])
                d3[k] = tmp
            else:
                d3[k] = second[k]
        else:
            d3[k] = v

    return d3



#other utils
def from_obj_settings(obj):
    """
    Converts the object into a dictionary
    """
    d = {}
    for key in dir(obj):
        if key.isupper():
            d[key] = getattr(obj, key)

    return d



def extract_lang_lon_from_cached_result(result):
    """
    Simple result extractor util
    """
    fdict = {}

    #print "RESULTS : ",results
    for r in result["results"][0]["address_components"]:
        if "postal_code" in r["types"]:
            fdict["postal_code"] = r["long_name"]
        elif "administrative_area_level_1" in r["types"]:
            fdict["region_long"] = r["long_name"]
            fdict["region"] = r["short_name"]
        elif "country" in r["types"]:
            fdict["country_code"] = r["short_name"]
            fdict["country"] = r["long_name"]


    geo = result["results"][0]["geometry"]["location"]
    fdict["geo_location"] = {
            "lat":geo["lat"],
            "lon":geo["lng"]
    }

    return fdict

def get_default_logger(name):
    root = logging.getLogger(name)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)
    root.setLevel(logging.DEBUG)

    return root



#string utils
def from_url_to_name(url):
   """
   Gets url and extract the only the domain name
   """
   r = urlparse(url.strip())
   hostname = r.hostname

   res = re.search("((www\.)*(.*)\.\w+)",hostname)
   if res:
       return res.group(3)
   return None


def slugify(value):
    """
    Converts to lowercase, removes non-word characters (alphanumerics and
    underscores) and converts spaces to hyphens. Also strips leading and
    trailing whitespace.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


def strip_list_to_str(lst):
    """
    Strips all of the members and returns a str combined
    """

    stripped = [s.strip() for s in lst]
    filtered = [s for s in stripped if s]
    return " ".join(filtered)


def clean_float_values(sfloat, *clean_lst):
    """
    Does some general cleaning of float values
    """

    for c in clean_lst:
        sfloat = sfloat.replace(c, "")

    #we should extract it from here
    res = re.search("(\d+\.?\d*)", sfloat)
    if not res:
        return 0

    sfloat = res.group(1)
    return float(sfloat.strip())



#scrappy utils
def check_spider_pipeline(process_item_method):

    @functools.wraps(process_item_method)
    def wrapper(self, item, spider):

        # message template for debugging
        clsname = self.__class__.__name__
        msg = '%%s %s pipeline step' % (clsname,)

        # if class is in the spider's pipeline, then use the
        # process_item method normally.
        pipelines = list(spider.pipeline)

        if self.__class__ in pipelines:
            return process_item_method(self, item, spider)
        elif isinstance(pipelines[0], basestring) and any([p for p in pipelines if clsname in p]):
            #we sometimess pass whole qualified name to module
            return process_item_method(self, item, spider)
        # otherwise, just return the untouched item (skip this step in
        # the pipeline)
        else:
            spider.log(msg % 'skipping', level=logging.DEBUG)
            return item

    return wrapper


