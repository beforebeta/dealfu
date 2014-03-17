"""
Some useful common functions
"""
import urlparse
import urllib
import json
import re
import functools
import logging
from copy import copy

from redis import Redis

from dealfu_groupon.items import MerchantItem, MerchantAddressItem


import elasticsearch

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


def get_first_non_empty(lst):
    """
    Sometimes we need the next non empty value
    @param lst:
    @return: stripped item with index tuple
    """

    for i,e in enumerate(lst):
        se = e.strip()
        if se:
            return se, i


    return None, -1


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



REGION_DICT = {
        "Alabama" : "AL",
        "Alaska": "AK",
        "Arizona" : "AZ",
        "Arkansas" : "AR",
        "California" :"CA",
        "Colorado": "CO",
        "Connecticut" :"CT",
        "Delaware" :"DE",
        "Florida" : "FL",
        "Georgia" :"GA",
        "Hawaii" :"HI",
        "Illinois" :"IL",
        "Indiana" :"IN",
        "Iowa": "IA",
        "Kansas": "KS",
        "Kentucky":"KY",
        "Louisiana": "LA",
        "Maine":"ME",
        "Maryland": "MD",
        "Massachusetts":"MA",
        "Michigan": "MI",
        "Minnesota":"MN",
        "Mississippi":"MS",
        "Missouri":"MO",
        "Montana":"MT",
        "Nebraska":"NB",
        "Nevada":"NV",
        "New Hampshire" : "NH",
        "New Jersey":"NJ",
        "New Mexico":"NM",
        "New York":"NY",
        "North Carolina":"NC",
        "North Dakota":"ND",
        "Ohio":"OH",
        "Oklahoma":"OK",
        "Oregon":"OR",
        "Pennsylvania":"PA",
        "Rhode Island":"RI",
        "South Carolina":"SC",
        "South Dakota":"SD",
        "Tennessee":"TN",
        "Texas":"TX",
        "Utah":"UT",
        "Vermont":"VT",
        "Virginia":"VA",
        "Washington":"WA",
        "West Virginia":"WV",
        "Wisconsin":"WI",
        "Wyoming":"WY"
    }


def get_short_region_name(region_name):
    """
    Gets the shorter version of the given region
    @param region_name:
    @return: shorter name
    """
    return REGION_DICT.get(region_name.strip())


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



def iter_divisions(fpath):
    """
    Gets a path to the division file and traverses the file
    by returning 1 record of division at time
    """
    divs = json.loads(open(fpath, "r").read())
    for d in divs["divisions"]:
        yield d





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


def get_redis(settings):
    """
    Gets a redis connection from supplied settings
    """
    db_num = settings.get("REDIS_DEFAULT_DB", 0)

    redis_conn = Redis(host=settings.get("REDIS_HOST"),
                       port=settings.get("REDIS_PORT"),
                       db=db_num)

    return redis_conn


def needs_retry(item):
    """
    Method checks the given item if it should be
    re-parsed or not. Basically the mandatory fields are :

    -category_name
    -category_slug
    -description
    -title
    -short_title
    -merchant.name
    -merchant.address

    or we need any of those :

    - price
    - discount_amount
    - discount_percentage
    """

    mandatory_offline = ("category_name",
                "category_slug",
                "description",
                "title",
                "short_title",
                "merchant",)

    mandatory_online = ("category_name",
                "category_slug",
                "description",
                "title",
                "short_title",)

    merchant_mandatory = (
        "name",
        "addresses",
    )



    if item["online"]:
        mandatory = mandatory_online
    else:
        mandatory = mandatory_offline

    if any([False if item.get(f) else True for f in mandatory]):
        return True

    if not item["online"]:
        #if it is online those ar not relevant
        merchant = item.get("merchant")
        if any([False if merchant.get(f) else True for f in merchant_mandatory]):
            return True

        #now check if we have at least the address
        if not merchant.get("addresses")[0]:
            return True

    if needs_price_retry(item):
        return True

    return False


def needs_price_retry(item):
    """
    Checks if current item needa a price refetch
    """
    optional = (
        "price",
        "discount_amount",
        "discount_percentage",
    )

    #check the optional pieces here
    if not any([True if item.get(f) else False for f in optional]):
        return True

    return False


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
            tmp = merge_dict_items(d3.get(k, {}), second[k])
            d3[k] = tmp
        else:
            d3[k] = v

    return d3


def from_obj_settings(obj):
    """
    Converts the object into a dictionary
    """
    d = {}
    for key in dir(obj):
        if key.isupper():
            d[key] = getattr(obj, key)

    return d


def save_deal_item(settings, item_id, item, es_conn=None):
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