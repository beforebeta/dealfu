import json
import re

from scrapy.http.response.html import HtmlResponse
from scrapy.http import Request
from scrapy.spider import Spider
from scrapy.selector import Selector

from dealfu_groupon.items import DealfuItem, MerchantItem
from dealfu_groupon.utils import get_fresh_merchant_address, get_first_non_empty, get_short_region_name, get_first_from_xp


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
        sel = Selector(response)
        d = DealfuItem()

        #the url of the deal
        d["untracked_url"] = response.url

        #get pricing information
        price_dict = self._extract_price_info(response)
        d.update(price_dict)

        #get expires info
        expires_dict = self._extract_expires_at(response)
        d.update(expires_dict)

        #set the merchant
        m = self._extract_merchant_info(response)
        d["merchant"] = m


        #content information
        d["title"] = sel.xpath('//h3[@class="deal-subtitle"]/text()')[0].extract().strip()
        if d.get("discount_percentage"):
            d["short_title"] = "%s off at %s!"%(d["discount_percentage"], m.get("name"))

        #description extraction WARN: XPATH MAGIC!!!
        desc_list = sel.xpath('//article[contains(@class, "pitch")]/div[contains(@class, "discussion")]/preceding-sibling::node()').extract()
        d["description"] = "".join([desc.strip() for desc in desc_list if desc.strip()])
        d["fine_print"] = None

        #number sold
        sold_xp = sel.xpath('//div[@class="deal-status"]//span/text()')
        if sold_xp:
            sold_str = sold_xp[0].extract().strip()
            res = re.search("(\d+)", sold_str.replace(",", ""))
            if res:
                d["number_sold"] = res.group().strip()

        #image_url
        img_xp = sel.xpath('//img[@id="featured-image"]/@src')
        if img_xp:
            d["image_url"] = img_xp[0].extract().strip()


        #provide info
        d["provider_name"] = "Groupon"
        d["provider_slug"] = "groupon"

        return d


    def _extract_expires_at(self, response):
        """
        Gets the expires_at info
        @param response:
        @return:
        """
        sel = Selector(response)
        d = {"expires_at":""}

        expires_xp = sel.xpath('//li[@class="countdown-timer"]/text()')
        if expires_xp:
            d["expires_at"] = expires_xp[0].extract()

        return d


    def _extract_price_info(self, response):
        """
        Looks up for the pricing info into response
        @param response:
        @return: a dict of populated info
        """
        sel = Selector(response)
        d = {}
        #price info
        purchase_block = sel.xpath('//div[@id="purchase-cluster"]')
        if purchase_block:
            price_xp = purchase_block.xpath('.//span[@class="price"]/text()')
            if price_xp:
                d["price"] = price_xp[0].extract()

            discount_xp = sel.xpath('//div[@id="purchase-cluster"]//tr[@id="discount-data"]')
            if discount_xp:
                d["discount_percentage"] = discount_xp.xpath('.//td[@id="discount-percent"]/text()')[0].extract()
                d["discount_amount"] = discount_xp.xpath('.//td[@id="discount-you-save"]/text()')[0].extract()
                d["value"] = discount_xp.xpath('.//td[@id="discount-value"]/text()')[0].extract()

        d["commission"] = 0

        return d


    def _extract_merchant_info(self, response):
        """
        Extracts all of the merchant info here
        @param response:
        @return: MerchantItem
        """
        m = MerchantItem()

        #extracting some merchant data
        sel = Selector(response)
        title = sel.xpath('//h2[@class="deal-page-title"]/text()')[0].extract().strip()

        index = title.rfind("-")
        if index == -1:
            return {}

        merchant_name = title[:index].strip()
        #location = title[index+1:].strip()

        m["name"] = merchant_name

        #extract address info
        addresses_xp = sel.xpath('//ol[@id="redemption-locations"]//div[@class="address"]')
        addresses = []
        for a in addresses_xp:
            ma = self._extract_addr_info(a)
            if ma:
                addresses.append(dict(ma))

        #set addresses
        m["addresses"] = addresses

        #check for website
        m["url"] = get_first_from_xp(sel.xpath('//div[@class="merchant-links"]//a/@href'))

        return m


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
            ma["region_long"] = res.group(2)
            ma["region"] = get_short_region_name(res.group(2))

            #locality at that stage ?
            ma["postal_code"] = res.group(3)

            #check for phone number
            res = re.search("(\d{3}\-\d{3}\-\d{4})", addr_text)
            if res:
                ma["phone_number"] = res.group().strip()

        return ma


