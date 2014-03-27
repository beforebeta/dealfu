import json
import re
from datetime import datetime

from scrapy.http.response.html import HtmlResponse
from scrapy.http import Request
from scrapy.spider import Spider
from scrapy.selector import Selector
from dateutil.relativedelta import relativedelta

from dealfu_groupon.items import DealfuItem, MerchantItem
from dealfu_groupon.utils import get_fresh_merchant_address, get_short_region_name, get_first_from_xp, extract_query_params, replace_query_param, \
    iter_divisions, clean_float_values

from dealfu_groupon.pipelines import espipe


class GrouponSpider(Spider):

    name = "groupon"
    allowed_domains = ["groupon.com"]

    #only work with those pipelines by default
    pipeline = set([
        espipe.EsPipeLine
    ])


    def __init__(self, division_path=None, only_one_page=False,
                 only_one_deal=False, pipeline=None, one_url=None,
                 doc_id=None, num_of_deals=None, *args, **kw):
        super(GrouponSpider, self).__init__(*args, **kw)

        self.only_one_page = only_one_page
        self.only_one_deal  = only_one_deal
        self.doc_id = doc_id #that only makes sense when it is a retry !!!
        #sometimes it makes sense to limit the deals we need
        self.num_of_deals = int(num_of_deals) if num_of_deals else num_of_deals
        self.total_deals = 0

        if pipeline:
            self.pipeline = pipeline if isinstance(pipeline, list) or isinstance(pipeline, set) else set([pipeline])

        if not division_path:
            if not self.only_one_deal:
                #put it to start with los-angeles
                self.start_urls = [
                    "https://www.groupon.com/browse/deals/partial?division=new-york&isRefinementBarDisplayed=true&facet_group_filters=topcategory%7Ccategory%7Ccategory2%7Ccategory3%3Bdeal_type%3Bcity%7Cneighborhood&page=1"
                ]
            else:
                #if it is only one deal we should go from here and parse only it
                self.start_urls = [one_url]
        else:
            #set the start urls from the file supplied
            start_s = "https://www.groupon.com/browse/deals/partial?division={}&isRefinementBarDisplayed=true&facet_group_filters=topcategory%7Ccategory%7Ccategory2%7Ccategory3%3Bdeal_type%3Bcity%7Cneighborhood&page=1"
            self.start_urls = [start_s.format(d["id"]) for d in iter_divisions(division_path)]




    def parse(self, response):
        """
        Starts parsing from here!
        @param response:
        @return:
        """
        if not self.only_one_deal:
            #if wee need get whole list go from here
            yield Request(response.url,
                          callback=self._parse_pagination)
        else:
            #if we need only one deal just go from here
            yield Request(response.url,
                          callback=self.parse_deal)


    def _parse_pagination(self, response):
        resp = json.loads(response.body)
        pagination = resp["deals"]["metadata"]["pagination"]

        deal_html = resp["deals"]["dealsHtml"]

        new_resp = self._recreate_resp(response, deal_html)
        sel = Selector(new_resp)
        deals_xp = sel.xpath("//figure/a/@href")
        deals_urls = [d.extract() for d in deals_xp]
        #print "DEAL URLS : ",deals_urls

        for d in deals_urls:
            if self.total_deals == self.num_of_deals:
                continue

            if d.startswith("//"):
                d = d.replace("//", "http://")

            r = Request(d, callback=self.parse_deal, meta={"cache_me":True})
            self.total_deals += 1

            yield r

        #and at that stage we should check if there is more page
        if int(pagination.get("nextPageSize")) > 0 and not self.only_one_page \
                and not self.total_deals == self.num_of_deals:
            #we should get the next page
            d = extract_query_params(response.url, "page")
            if d.get("page"):
                next_page = int(d["page"]) + 1
                next_url = replace_query_param(response.url,
                                               "page",
                                               str(next_page))

                #you get the next page here !
                yield Request(next_url,
                              callback=self._parse_pagination)


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

        #setup default values here probably need factory
        d["enabled"] = False
        #the url of the deal
        d["untracked_url"] = response.url


        if self.doc_id:
            d["id"] = self.doc_id


        #check for online=True/False of deal
        tmp_online = self._extract_online_deal(response)
        d.update(tmp_online)

        #get pricing information
        price_dict = self._extract_price_info(response)
        d.update(price_dict)

        #get expires info
        expires_dict = self._extract_expires_at(response)
        d.update(expires_dict)

        #set the merchant
        m = self._extract_merchant_info(response)
        d["merchant"] = dict(m)


        #content information
        d["title"] = sel.xpath('//h2[@class="deal-page-title"]/text()')[0].extract().strip()
        if d.get("discount_percentage"):
            if m.get("name"):
                d["short_title"]= "{}% off at {}!".format("%s"%int(d["discount_percentage"]*100),
                                                       m.get("name"))
            else:
                d["short_title"]= "{}% off!".format("%s"%int(d["discount_percentage"]*100))
        else:
            #is that right ?
            if m.get("name"):
                d["short_title"]= "coupon at {}".format(m.get("name"))
            else:
                d["short_title"]= d["title"]


        #description extraction WARN: XPATH MAGIC!!!
        desc_list = sel.xpath('//article[contains(@class, "pitch")]/div[contains(@class, "discussion")]/preceding-sibling::node()').extract()
        d["description"] = "".join([desc.strip() for desc in desc_list if desc.strip()])

        #extract fine_print information
        tmp_fine_print = self._extract_fine_print(response)
        d.update(tmp_fine_print)


        #number sold
        sold_xp = sel.xpath('//div[@class="deal-status"]//span/text()')
        if sold_xp:
            sold_str = sold_xp[0].extract().strip()
            res = re.search("(\d+)", sold_str.replace(",", ""))
            if res:
                d["number_sold"] = int(res.group().strip())

        #image_url
        img_xp = sel.xpath('//img[@id="featured-image"]/@src')
        if img_xp:
            d["image_url"] = img_xp[0].extract().strip()


        #get the category info from page
        d.update(self._extract_category_info(response))

        #provide info
        d["provider_name"] = "Groupon"
        d["provider_slug"] = "groupon"

        return d


    def _extract_fine_print(self, response):
        """
        Extracts the fine_print information
        """
        d = {"fine_print":None}

        sel = Selector(response)

        fine_print_xp = sel.xpath('//div[contains(@class, "fine-print")]//p/text()')
        if not fine_print_xp:
            return d

        fine_print_lst = [f.extract().strip() for f in fine_print_xp]
        fine_print_lst = [f for f in fine_print_lst if f]
        fine_print = "".join(fine_print_lst)

        fine_print = "".join([f.strip() for f in fine_print.split("\n")])
        d["fine_print"] = fine_print

        return d

    def _extract_online_deal(self, response):
        """
        Checks if the deal is online or offline
        """
        d = {"online":False}
        sel = Selector(response)

        online_xp = get_first_from_xp(sel.xpath('//h3[@class="deal-subtitle"]/text()'))
        if not online_xp:
            return d

        if "online" in online_xp.strip().lower():
            d["online"] = True

        return d


    def _extract_category_info(self, response):
        """
        Gets category info from script tag of the page !!!
        @param response:
        @return: a dict with category info
        """
        sel = Selector(response)
        d = {"category_slug":None,
             "category_name":None}

        script_xp = sel.xpath("//script")
        for sc in script_xp:
            res = re.search("dataLayer\s*\=\s*(\{.*\})\s*;",sc.extract())
            if res:
                data = json.loads(res.group(1).strip())
                if data.get("dl_category_sub"):
                    d["category_slug"] = data["dl_category_sub"]
                    d["category_name"] = data["dl_category_sub"]
                elif data.get("dl_category"):
                    d["category_slug"] = data["dl_category"]
                    d["category_name"] = data["dl_category"]
                elif data.get("dl_channel"):
                    d["category_slug"] = data["dl_channel"]
                    d["category_name"] = data["dl_channel"]

                break

        return d


    def _extract_expires_at(self, response):
        """
        Gets the expires_at info
        @param response:
        @return:
        """
        sel = Selector(response)
        d = {"expires_at":None}

        expires_xp = sel.xpath('//li[@class="countdown-timer"]/text()')
        if not expires_xp:
            return d

        expires_at = expires_xp[0].extract()

        if not expires_at:
            return d

        res = re.search("(\d+)\s*day[s]*\s*(\d+)\:(\d+)\:(\d+)", expires_at)
        if res:
            days = int(res.group(1))
            hours = int(res.group(2))
            minutes = int(res.group(3))
            secs = int(res.group(4))

            delta = relativedelta(days=+days,
                                  hours=+hours,
                                  minutes=+minutes,
                                  seconds=+secs)

            d["expires_at"] = datetime.utcnow() + delta

        res = re.search("(\d+)\:(\d+)\:(\d+)", expires_at)
        if res:
            hours = int(res.group(1))
            minutes = int(res.group(2))
            secs = int(res.group(3))

            delta = relativedelta(hours=+hours,
                                  minutes=+minutes,
                                  seconds=+secs)

            d["expires_at"] = datetime.utcnow() + delta


        return d


    def _extract_price_info(self, response):
        """
        Looks up for the pricing info into response
        @param response:
        @return: a dict of populated info
        """
        sel = Selector(response)
        d = {}
        d["commission"] = 0

        #price info
        purchase_block = sel.xpath('//div[@id="purchase-cluster"]')
        if purchase_block:
            price = get_first_from_xp(purchase_block.xpath('.//span[@class="price"]/text()'))
            if price:
                d["price"] = clean_float_values(price, "$", ",")


            discount_xp = sel.xpath('//div[@id="purchase-cluster"]//tr[@id="discount-data"]')
            if discount_xp:
                discount_percentage = get_first_from_xp(discount_xp.xpath('.//td[@id="discount-percent"]/text()'))
                if discount_percentage:
                    discount_percentage = clean_float_values(discount_percentage, "%")/100
                    d["discount_percentage"] = discount_percentage

                discount_amount = get_first_from_xp(discount_xp.xpath('.//td[@id="discount-you-save"]/text()'))
                if discount_amount:
                    d["discount_amount"] = clean_float_values(discount_amount, "$", ",")

                value = get_first_from_xp(discount_xp.xpath('.//td[@id="discount-value"]/text()'))
                if value:
                    d["value"] = clean_float_values(value, "$", ",")

        #it maybe a different kind of page so, try that requires JS
        #if not d.get("value") or not d.get("price"):
        #    return self._extract_price_selenium(response)


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

        merchant_name_xp = sel.xpath('//div[@class="merchant-profile"]/*[1]/text()')
        if not merchant_name_xp:
            merchant_name_xp = sel.xpath('//aside[@data-bhw="MerchantBox"]/*[1]/text()')
            #sometimes it is in a div

        if not merchant_name_xp:
            #we can not have a merchant without name
            return {}


        merchant_name = get_first_from_xp(merchant_name_xp).strip()
        m["name"] = merchant_name

        #extract address info
        #sometimes we have different formats, scrapping sucks!!!

        addresses_xp = sel.xpath('//ul[@class="merchant-list"]/li')
        if not addresses_xp:
            addresses_xp = sel.xpath('//ol[@id="redemption-locations"]//div[@class="address"]')

        addresses = []
        for a in addresses_xp:
            ma = self._extract_addr_info(a)
            if ma:
                addresses.append(dict(ma))

        #set addresses
        m["addresses"] = addresses

        #check for website
        ahrefs = sel.xpath('//div[@class="merchant-links"]//a')
        if ahrefs:
           for ahref in ahrefs:
                url = get_first_from_xp(ahref.xpath("./@href"))
                text = get_first_from_xp(ahref.xpath("./text()"))
                if text and "website" in text.strip().lower():
                    m["url"] = url
                elif text and "facebook" in text.strip().lower():
                    m["facebook_url"] = url

        return m


    def _extract_addr_info(self, xpath_sel):
        """
        Extracts strctured data from xpath supplied
        @param xpath_sel:
        @return: MerchantAddressItem
        """

        text_list = [a.strip() for a in xpath_sel.xpath("./text()").extract() if a.strip()]
        if not text_list:
            #sometimes they send a longer list hidden in html !
            text_list = [a.strip() for a in xpath_sel.xpath("./div[@class='address']/text()").extract() if a.strip()]

        name = xpath_sel.xpath(".//strong/text()")[0].extract()

        ma = get_fresh_merchant_address()

        if name:
            ma["address_name"] = name

        #try to match the whole address
        addr_text = " ".join(text_list)
        #print "ADDR_TEXT : ",addr_text
        res = re.search("(.*)(\d{3}\-\d{3}\-\d{4})", addr_text)

        if res:
            final_address = res.group(1).strip()
            ma["address"] = final_address
            ma["phone_number"] = res.group(2).strip()
        else:
            ma["address"] = addr_text.strip()

        return ma


