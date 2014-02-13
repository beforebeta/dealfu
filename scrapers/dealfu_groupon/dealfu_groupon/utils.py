"""
Some useful common functions
"""
import urlparse

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


