from dealfu_groupon.items import DealCategoryItem
from dealfu_groupon.utils import get_first_from_xp, get_dealfu_category
from scrapy.spider import Spider
from scrapy.selector import Selector

from dealfu_groupon.pipelines import genespipe


class LiveSocialCategorySpider(Spider):

    name = "livesocialcat"
    allowed_domains = [
        "livingsocial.com"
    ]

    start_urls = [
        "https://www.livingsocial.com/categories"
    ]

    pipeline = set([genespipe.BaseEsPipe])


    def parse(self, response):
        """
        Parse Group items and return them
        """
        categories = []

        sel = Selector(response)
        main_categories_xpath = sel.xpath("//ul[contains(@class, 'regions')]/li[contains(@class, 'region')]")
        if not main_categories_xpath:
            return []

        for mc in main_categories_xpath:
            main_name = get_first_from_xp(mc.xpath('.//h3//text()'))
            print "MAIN ",main_name
            categories.append(get_dealfu_category(main_name))

            sub_cats = mc.xpath("./ul[contains(@class, 'cities')]//a")
            for sub_cat in sub_cats:
                text = get_first_from_xp(sub_cat.xpath("./text()"))
                categories.append(get_dealfu_category(text,
                                                      parent=main_name))

        return categories
