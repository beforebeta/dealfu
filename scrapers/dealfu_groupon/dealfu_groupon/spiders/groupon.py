import json

from scrapy.http.response.html import HtmlResponse
from scrapy.http import Request
from scrapy.spider import Spider
from scrapy.selector import Selector

from dealfu_groupon.items import DealfuItem


class GrouponSpider(Spider):

    name = "groupon"
    allowed_domains = ["groupon.com"]
    start_urls = [
        "https://www.groupon.com/browse/deals/partial?division=denver&isRefinementBarDisplayed=true&facet_group_filters=topcategory%7Ccategory%7Ccategory2%7Ccategory3%3Bdeal_type%3Bcity%7Cneighborhood&page=1"
    ]


    def parse(self, response):
        resp = json.loads(response.body)
        deal_html = resp["deals"]["dealsHtml"]

        new_resp = self._recreate_resp(response, deal_html)
        sel = Selector(new_resp)
        deals_xp = sel.xpath("//figure/a/@href")
        deals_urls = [d.extract() for d in deals_xp]


        for d in deals_urls:
            r = Request(d, callback=self.parse_deal)
            yield r



    def _recreate_resp(self, response, body):
        """
        Gets a copy of the request except the body part !
        :param response:
        :param body:
        :return: new response
        """
        new_response = HtmlResponse(url=response.url,
                                status=response.status,
                                headers=response.headers,
                                body=body,
                                flags=response.flags,
                                encoding=response.encoding)

        return new_response


    def parse_deal(self, response):
        """
        The detail page parsing is done at that stage
        :param response:
        :return: return Item
        """
        d = DealfuItem()
        d["url"] = response.url

        return d

