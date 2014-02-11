import json
import re

from scrapy.http.response.html import HtmlResponse
from scrapy.http import Request
from scrapy.spider import Spider
from scrapy.selector import Selector

from dealfu_groupon.items import DealfuItem, MerchantItem
from dealfu_groupon.utils import get_fresh_merchant_address, get_first_non_empty


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
        :return: DealfuItem
        """
        d = DealfuItem()
        d["url"] = response.url
        m = MerchantItem()

        #extracting some merchant data
        sel = Selector(response)
        title = sel.xpath('//h2[@class="deal-page-title"]/text()')[0].extract().strip()

        index = title.rfind("-")
        if index == -1:
            return None

        merchant_name = title[:index].strip()
        location = title[index+1:].strip()

        m["name"] = merchant_name

        #price info
        purchase_block = sel.xpath('//div[@id="purchase-cluster"]')
        if purchase_block:
            price = purchase_block.xpath('.//span[@class="price"]/text()')[0].extract()
            d["price"] = price

            discount_xp = sel.xpath('//div[@id="purchase-cluster"]//tr[@id="discount-data"]')
            d["discount_percentage"] = discount_xp.xpath('.//td[@id="discount-percent"]/text()')[0].extract()
            d["discount_amount"] = discount_xp.xpath('.//td[@id="discount-you-save"]/text()')[0].extract()
            d["value"] = discount_xp.xpath('.//td[@id="discount-value"]/text()')[0].extract()

        #extract address info
        addresses_xp = sel.xpath('//ol[@id="redemption-locations"]//div[@class="address"]')
        addresses = []
        for a in addresses_xp:
            ma = self._extract_addr_info(a)
            if ma:
                addresses.append(dict(ma))

        #set addresses
        m["addresses"] = addresses

        #set the merchant
        d["merchant"] = m


        return d


    def _extract_addr_info(self, xpath_sel):
        """
        Extracts strctured data from xpath supplied
        @param xpath_sel:
        @return: MerchantAddressItem
        """

        text_list = [a.strip() for a in xpath_sel.xpath("./text()").extract() if a.strip()]
        name = xpath_sel.xpath(".//strong/text()")[0].extract()

        ma = get_fresh_merchant_address()

        if name:
            ma["address_name"] = name

        #try to match the whole address
        addr_text = " ".join(text_list)
        res = re.search("(.*),\s+(\w+)\s+(\d{5})", addr_text)
        if res:
            final_address = res.group(1).strip()
            ma["address"] = final_address
            ma["region"] = res.group(2)
            #locality at that stage ?
            ma["postal_code"] = res.group(3)

            #check for phone number
            res = re.search("(\d{3}\-\d{3}\-\d{4})", addr_text)
            if res:
                ma["phone_number"] = res.group().strip()

        return ma


