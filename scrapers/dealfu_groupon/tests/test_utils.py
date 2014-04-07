from copy import copy

from dealfu_groupon.utils import merge_dict_items, clean_float_values, some, get_in, are_addresses_geo_encoded, \
    is_valid_address, missing_mandatory_field, needs_geo_fetch, needs_address_geo_fetch, needs_retry, needs_price_retry

from tests.tutil import get_address_factory, get_address_geo_factory, get_merchant_factory, get_item_factory, \
    remove_fields


def test_merge_items():

    d1 = {"one":1, "two":None}
    d2 = {"one":None, "two":2}

    d3 = merge_dict_items(d1, d2)
    assert d3["one"] == 1
    assert d3["two"] == 2

    #it should just work for falsy
    d1 = {"one":1}
    d2 = {"one":[]}

    d3 = merge_dict_items(d1, d2)
    assert d3["one"] == 1

    #we have deal with merchant info
    d1 = {"title":"cool title",
          "merchant":{}}

    d2 = {"merchant":{
        "name":"bestmercahnt",
        "url":None
    }}

    d3 = merge_dict_items(d1, d2)
    assert d3["title"] == d1["title"]
    assert d3["merchant"]
    assert d3["merchant"].get("name") == "bestmercahnt"
    assert d3["merchant"].has_key("url") == False

    #try something with addresses

    d1 = {"title":"cool title",
          "merchant":{"name":"puma",
                      "addresses":[]}}

    d2 = {"merchant":{
        "name":"bestmercahnt",
        "url":None,
        "addresses":[
             {
                "country": "United States",
                "country_code": "US",
                "address_name": "Midtown West/57th Street"
             }
        ]
    }}

    d3 = merge_dict_items(d1, d2)
    assert d3["title"] == d1["title"]
    assert d3["merchant"]
    assert d3["merchant"].get("name") == "bestmercahnt"
    assert d3["merchant"].has_key("url") == False
    assert d3["merchant"]["addresses"] == d2["merchant"]["addresses"]



def test_clean_float_values():

    val = clean_float_values("From $55/nigh", "$")
    assert int(val) == 55


def test_some():

    t = [True, True, True]
    tf = [False, True, False]
    f = [False, False, False]

    assert some(lambda x: x, t)
    assert some(lambda x: x, tf)
    assert some(lambda x: x, f) == False

    a1 = [{"geo_location":{"lat":1212, "lon":1221}}]
    a2 = [{},{}]
    a3 = [{"geo_location":{"lat":1212, "lon":1221}},
        {}]

    not_in = lambda x : True if not x.get("geo_location") else False

    assert some(not_in, a1) == False
    assert some(not_in, a2)
    assert some(not_in, a3)



def test_get_in():

    item = {
        "merchant":{}
    }

    item2 = {
        "merchant":{
            "addresses":["a1", "a2"]
        }
    }

    assert get_in(item, "non") is None
    assert get_in(item, "merchant") is None
    assert get_in(item, "merchant", "addresses") is None

    #the item2 tests
    assert get_in(item2, "merchant") == {
        "addresses":["a1", "a2"]
    }

    assert get_in(item2, "merchant", "addresses") == ["a1", "a2"]



def test_are_addresses_geo_encoded():
    #get a geo encoded address
    addr = get_address_geo_factory()
    item = get_item_factory(merchant={"addresses":[addr]})
    assert are_addresses_geo_encoded(item)


    #get a non geo encoded address
    non_geo = get_address_factory()
    item = get_item_factory(merchant={"addresses":[non_geo]})
    assert not are_addresses_geo_encoded(item)

    #get a semi geonecoded address
    item = get_item_factory(merchant={"addresses":[addr, non_geo]})
    assert not are_addresses_geo_encoded(item)


def test_is_valid_address():
    addr = get_address_geo_factory()
    assert is_valid_address(addr)

    invalid_addr = remove_fields(addr, "address")
    assert not is_valid_address(invalid_addr)


def test_missing_mandatory_field():

    #test the success first
    item = get_item_factory()
    assert not missing_mandatory_field(item)

    #remove some of th mandatory fields
    for m in ["description","title","short_title",
              "merchant", "category_name", "category_slug", "merchant.name"]:

        miss_item = get_item_factory()
        miss_item = remove_fields(miss_item, m)
        assert missing_mandatory_field(miss_item)

    #the next part is the address part
    miss_item = get_item_factory()
    #remove the addresses
    miss_item = remove_fields(miss_item, "merchant.addresses")
    assert missing_mandatory_field(miss_item)

    #now make the miss item online True and it should be fine
    miss_item = get_item_factory(online=True)
    miss_item = remove_fields(miss_item, "merchant.addresses")
    assert not missing_mandatory_field(miss_item)

    #finally check the price part
    miss_item = get_item_factory()
    miss_item = remove_fields(miss_item, "price", "discount_amount", "discount_percentage")
    assert missing_mandatory_field(miss_item)

    #enable any of it it should be ok
    miss_item = get_item_factory()
    #print "MISS_ITEM : ",miss_item
    miss_item = remove_fields(miss_item, "price")
    assert not missing_mandatory_field(miss_item)



def test_needs_geo_fetch():

    #a success case
    addr = get_address_geo_factory()
    item = get_item_factory(merchant={"addresses":[addr]})
    assert not needs_geo_fetch(item)

    #without merchant
    item = get_item_factory()
    item = remove_fields(item, "merchant")
    assert not needs_geo_fetch(item)

    #without addresses
    item = get_item_factory()
    item = remove_fields(item, "merchant.addresses")
    assert not needs_geo_fetch(item)

    #the invalid address
    invalid_addr = get_address_factory()
    invalid_addr = remove_fields(invalid_addr, "address")
    item = get_item_factory(merchant={"addresses":[invalid_addr]})
    assert not needs_geo_fetch(item)

    #one valid and one invalid
    invalid_addr = get_address_factory()
    invalid_addr = remove_fields(invalid_addr, "address")

    addr = get_address_factory()
    item = get_item_factory(merchant={"addresses":[invalid_addr, addr]})
    assert needs_geo_fetch(item)


def test_needs_address_geo_fetch():
    addr = get_address_factory()
    assert needs_address_geo_fetch(addr)

    geo_addr = get_address_geo_factory()
    assert not needs_address_geo_fetch(geo_addr)


def test_needs_retry():
    #without merchant
    item = get_item_factory()
    item = remove_fields(item, "merchant")
    assert needs_retry(item)

    #offline withtou addresses
    item = get_item_factory(online=False)
    item = remove_fields(item, "merchant.addresses")
    assert needs_retry(item)

    #online without address
    item = get_item_factory(online=True)
    item = remove_fields(item, "merchant.addresses")
    assert not needs_retry(item)



def test_needs_price_retry():
    #finally check the price part
    miss_item = get_item_factory()
    miss_item = remove_fields(miss_item, "price", "discount_amount", "discount_percentage")
    assert needs_price_retry(miss_item)

    #enable any of it it should be ok
    miss_item = get_item_factory()
    #print "MISS_ITEM : ",miss_item
    miss_item = remove_fields(miss_item, "price")
    assert not needs_price_retry(miss_item)



def test_tutil():
    pass
    #print remove_fields(get_address_geo_factory(), "address")
    #print get_address_factory(address_name="beautiful_place")
    #print get_address_geo_factory()
    #print get_merchant_factory()
    #print get_merchant_factory(name="smallbuss")
    #d = get_item_factory(merchant={"name":"smallboss"})
    #print remove_fields(d, "merchant.name", "merchant.url", "merchant.addresses")