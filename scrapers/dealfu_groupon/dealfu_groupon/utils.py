"""
Some useful common functions
"""

from dealfu_groupon.items import MerchantItem, MerchantAddressItem

def get_fresh_merchant_address():
    """
    Gets a MerchantItem with defaults attached to it
    @return:
    """
    m = MerchantAddressItem()
    m["country"] = "United States"
    m["country_code"] = "US"
    m["latitude"] = 0.0
    m["longtitude"] = 0.0
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
