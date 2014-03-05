"""
Test geolocation fns here
"""

from dealfu_groupon.background.geocode import is_valid_address, format_str_address


def test_is_valid_address():
    a = {}
    assert not is_valid_address(a)

    a = {
        "address":"my address",
        "region_long":"New Mexico"
    }

    assert is_valid_address(a)



def test_format_str_address():
    a = {
        "address":"address",
        "region_long":"region",
        "postal_code":"zipcode"
    }

    assert format_str_address(a) == "address:region:zipcode"

    a = {
    "address":"address",
    "region_long":"region"
    }

    assert format_str_address(a) == "address:region"