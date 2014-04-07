from copy import copy
import datetime

from dealfu_groupon.items import MerchantAddressItem, MerchantItem, DealfuItem
from dealfu_groupon.utils import get_in
import factory
from scrapy.item import Field


class MerchantAddressFactory(factory.Factory):
    """
    Merchant Factory
    """
    FACTORY_FOR = MerchantAddressItem


class MerchantAddressWithGeo(MerchantAddressItem):

    geo_location = Field()


class MerchantAddressWithGeoFactory(factory.Factory):

    FACTORY_FOR = MerchantAddressWithGeo


class MerchantItemFactory(factory.Factory):

    FACTORY_FOR = MerchantItem


class DealfuItemFactory(factory.Factory):

    FACTORY_FOR = DealfuItem


def get_address_factory(**kw):
    """
    Gets a full address
    """
    default_dict = {
        "address_name":"beautiful store",
        "address":"new york stone",
        "country":"USA",
        "country_code":"US",
        "phone_number":"123-356-33"
    }

    default_dict.update(kw)

    return MerchantAddressFactory(**default_dict)


def get_address_geo_factory(**kw):

    def_addr = dict(get_address_factory(**kw))

    geo_info ={
        "geo_location": {
            "lon": -84.200987,
            "lat": 33.838202
            }
    }

    if kw.has_key("geo_location"):
        geo_info["geo_location"] = kw["geo_location"]

    def_addr.update(geo_info)

    return MerchantAddressWithGeoFactory(**def_addr)


def get_merchant_factory(**kw):
    """
    Gets a merchant
    """
    mutable_kw = copy(kw)

    default_dict = {
        "name":"big_merchant",
        "url":"http://bigboss.com",
        "facebook_url":"http://facebook.com",
        "addresses":[]
    }

    if mutable_kw.has_key("addresses"):
        default_dict["addresses"] = mutable_kw["addresses"]
    else:
        default_dict["addresses"] = [get_address_geo_factory()]

    if mutable_kw.has_key("addresses"):
        mutable_kw.pop("addresses")

    default_dict.update(mutable_kw)

    return MerchantItemFactory(**default_dict)



def get_item_factory(**kw):
    """
    Gets a full item
    """
    mutable_kw = copy(kw)

    default_dict = {
        "id":"12345",
        "untracked_url":"http://untracked.com",
        "online":False,
        "discount_amount":70,
        "discount_percentage":50,
        "price":70,
        "value":140,
        "commission":0,
        "number_sold":100,
        "title":"Cool item",
        "short_title":"%50 off at big boss",
        "image_url":"http://image.com",
        "description":"desc",
        "fine_print":"fine",
        "expires_at": datetime.datetime.utcnow(),
        "enabled":False,
        "category_name":"food",
        "category_slug":"food",
        "provider_name":"groupon",
        "provider_slug":"groupon",
        "created_at":datetime.datetime.utcnow(),
        "updated_at":datetime.datetime.utcnow(),
        "merchant":{}
    }

    if mutable_kw.has_key("merchant"):
        merchant = mutable_kw.pop("merchant")
        merchant_inst = get_merchant_factory(**merchant)
    else:
        merchant_inst = get_merchant_factory()

    default_dict["merchant"] = merchant_inst
    default_dict.update(mutable_kw)


    return DealfuItemFactory(**default_dict)



def remove_fields(d, *fields):
    """
    It will be a list of like

    merchant.name
    price
    merchant.addresses
    """

    for f in fields:
        splitted = f.split(".")
        #print "SPLITTED : ",splitted

        if len(splitted) == 1:
            if d.has_key(splitted[0]):
                d.pop(splitted[0])
        else:
            tmp_d = get_in(d, *splitted[:-1])
            #print "TMP_D", tmp_d
            if tmp_d and tmp_d.has_key(splitted[-1]):
                tmp_d.pop(splitted[-1])

    return d

