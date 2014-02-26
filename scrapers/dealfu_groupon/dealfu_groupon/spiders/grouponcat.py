import json

from scrapy.spider import Spider

from dealfu_groupon.items import DealCategoryItem
from dealfu_groupon.pipelines import catpipe


class GrouponCategorySpider(Spider):

    name = "grouponcat"
    allowed_domains = ["groupon.com"]
    start_urls = [
        "http://www.groupon.com/browse/deals/partial?lat=40.7143528&lng=-74.0059731&address=New+York%2C+NY%2C+USA&query=new&locale=en_US&division=new-york&isRefinementBarDisplayed=true&facet_group_filters=topcategory%7Ccategory%7Ccategory2%7Ccategory3%3Bdeal_type%3Bcity%7Cneighborhood&page=2"
    ]

    pipeline = set([catpipe.CatPipeLine])


    def parse(self, response):
        resp = json.loads(response.body)
        deal_cats = resp["deals"]["metadata"]["facets"][0]["values"]

        categories = []

        for cat in deal_cats:
            categories.extend(self._extract_categories(cat, "groupon"))

        return categories


    def _extract_categories(self, cur_dict, parent_cat):
        """
        That is a recursive method that traverses the cur_dict tree structure
        and returns back a flat list of categories with relations coded in them!

        @param cur_dict: tree of nested categories
        @param parent_cat: str
        @param category_list: list of those collected so far
        @return: a list of DealCategoryItems
        """
        dc = DealCategoryItem()
        dc["name"] = cur_dict.get("friendlyName")
        dc["slug"] = cur_dict.get("id")
        dc["parent_slug"] = parent_cat

        cats = [dc]

        if not cur_dict.get("children"):
            return [dc]


        for child_cat in cur_dict.get("children"):
            cats.extend(self._extract_categories(child_cat,
                                                 dc["slug"]))

        return cats
