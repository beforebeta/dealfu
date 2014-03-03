from dealfu_groupon.utils import merge_dict_items, clean_float_values



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
