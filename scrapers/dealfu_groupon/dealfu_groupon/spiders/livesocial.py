from dateutil.parser import parse
import re

from scrapy.http import Request
from scrapy.spider import Spider
from scrapy.selector import Selector

from dealfu_groupon.items import DealfuItem, MerchantItem
from dealfu_groupon.utils import get_first_from_xp, clean_float_values
from dealfu_groupon.pipelines import genespipe


class LiveSocialSpider(Spider):

    name = "livesocial"
    allowed_domains = ["livingsocial.com"]

    #only work with those pipelines by default
    pipeline = set([
        genespipe.BaseEsPipe
    ])


    start_urls = ["https://www.livingsocial.com/more_deals"]

    def __init__(self, only_one_page=False, only_one_deal=False,
                 pipeline=None, one_url=None, num_of_deals=None,
                 *args, **kw):
        super(LiveSocialSpider, self).__init__(*args, **kw)

        self.only_one_page = only_one_page
        self.only_one_deal  = only_one_deal
        self.num_of_deals = int(num_of_deals) if num_of_deals else num_of_deals
        self.total_deals = 0

        if pipeline:
            self.pipeline = pipeline if isinstance(pipeline, list) or isinstance(pipeline, set) else set([pipeline])



    def parse(self, response):
        """
        Starts parsing from here!
        @param response:
        @return:
        """
        yield Request(response.url,
                      callback=self.parse_deal)

        # if not self.only_one_deal:
        #     #if wee need get whole list go from here
        #     yield Request(response.url,
        #                   callback=self._parse_pagination)
        # else:
        #     #if we need only one deal just go from here
        #     yield Request(response.url,
        #                   callback=self.parse_deal)




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
        d["provider_name"] = "Living Social"
        d["provider_slug"] = "living-social"

        #price and etc
        tmp_d = self._extract_deal_stats(response)
        d.update(tmp_d)

        #merchant info
        tmp_d = self._extract_merchant_info(response)
        if tmp_d:
            d["merchant"] = tmp_d


        #expires_at
        tmp_d = self._extract_expires_at(response)
        d.update(tmp_d)

        #content
        tmp_d = self._extract_content(response)
        d.update(tmp_d)

        #short_title
        #content
        tmp_d = self._get_short_title(d.get("merchant", {}), d)
        d.update(tmp_d)

        #get the image url
        tmp_d = self._extract_deal_image(response)
        d.update(tmp_d)

        #TODO category info here should be added !
        #TODO online/offline here

        return d

    def _get_short_title(self, merchant, item):
        #get the short title here
        d = item
        m = merchant
        tmp = {}

        if d.get("discount_percentage"):
            if m.get("name"):
                tmp["short_title"]= "{}% off at {}!".format("%s"%int(d["discount_percentage"]*100),
                                                     m.get("name"))
            else:
                tmp["short_title"]= "{}% off!".format("%s"%int(d["discount_percentage"]*100))
        else:
            #is that right ?
            if m.get("name"):
                tmp["short_title"]= "coupon at {}".format(m.get("name"))
            else:
                tmp["short_title"]= d["title"]


        return tmp



    def _extract_deal_stats(self, response):
        """
        Extracts price estimated time and sold count
        """
        d = {}
        sel = Selector(response)

        #get price first
        price_xp = sel.xpath('//li[@id="deal-buy-box-price"]//text()')
        if price_xp:
            price = "".join([s.strip() for s in price_xp.extract() if s.strip])
            d["price"] = clean_float_values(price, "$")

        #check for discount info
        discount_percentage = get_first_from_xp(sel.xpath('//ul[@id="stats_deal_list"]//li[1]/div/text()'))
        if discount_percentage:
            d["discount_percentage"] = clean_float_values(discount_percentage, "%")/100

            if d.get("price") and d.get("discount_percentage"):
                #computhe the value
                value_of_hundred = 100-d["discount_percentage"]*100
                value = float("%.2f"%(d["price"] * 100 / value_of_hundred))
                d["value"] = value

                #compute the discount amount
                d["discount_amount"] = value - d["price"]



        #check for sold quantity
        sold_items = get_first_from_xp(sel.xpath('//ul[@id="stats_deal_list"]//li[2]/div/text()'))
        if sold_items:
            sold_str = sold_items.strip()
            res = re.search("(\d+)", sold_str.replace(",", ""))
            if res:
                d["number_sold"] = int(res.group().strip())

        return d


    def _extract_merchant_info(self, response):
        m = MerchantItem()

        #extracting some merchant data
        sel = Selector(response)

        merchant_name_xp = sel.xpath('//h1[@id="deal_merchant_display_name"]/text()')
        merchant_name = get_first_from_xp(merchant_name_xp)
        if not merchant_name:
            return  m

        m["name"] = merchant_name.strip()
        #extract the address info here
        #'//*[contains(@class, "phone")]'
        address_info_xps = sel.xpath('//div[contains(@class, "location")]//div[contains(@class, "address-location-info")]')

        addresses = []
        for address_xp in address_info_xps:
            tmp_addr = {}
            address = get_first_from_xp(address_xp.xpath('.//*[contains(@class, "street_1")]//text()'))
            if address:
                tmp_addr["address"] = address.strip()

            phone = get_first_from_xp(address_xp.xpath('.//*[contains(@class, "phone")]//text()'))
            if phone:
                tmp_addr["phone_number"] = phone.replace("|", "").strip()

            if tmp_addr:
                addresses.append(tmp_addr)

        #assign the collected addresses
        m["addresses"] = addresses
        return dict(m)


    def _extract_deal_image(self, response):
        """
        Gets the deal image
        """
        d = {}

        sel = Selector(response)
        image_xp = get_first_from_xp(sel.xpath('//div[contains(@class, "deal-image")]/@style'))
        if not image_xp:
            return d

        result = re.search("url\s*\(\'(http.*\.jpg)\'\)", image_xp.strip())
        if not result:
            return d

        d["image_url"] = result.group(1).strip()
        return d


    def _extract_expires_at(self, response):
        d = {}

        sel = Selector(response)
        meta_xp = sel.xpath('//meta[@name="robots"]/@content')

        if not meta_xp:
            return d

        for m in [mx.extract() for mx in meta_xp]:
            if not m:
                continue

            tm = re.search("unavailable_after\s*\:\s*(.*)", m)
            if not tm:
                continue

            d["expires_at"] = parse(tm.group(1).strip())
            break


        return d

    def _extract_content(self, response):
        """
        Extracts title, description, fine_print
        """
        d = {}
        sel = Selector(response)

        title_xp = sel.xpath('//*[@id="option_title_for_deal"]/text()')
        d["title"] = get_first_from_xp(title_xp)

        #get the description
        description_xp = sel.xpath('//div[@id="view-details-full"]//p')
        if description_xp:
            description_xp_lst = description_xp.extract()
            d["description"] = "".join([desc.strip() for desc in description_xp_lst if desc.strip()])

        #get the fine_print
        fine_print_xp = sel.xpath('//div[@id="fine-print-full"]//div[@class="fine-print"]//text()')
        if fine_print_xp:
            fine_print_lst = [f.extract().strip() for f in fine_print_xp]
            fine_print_lst = [f for f in fine_print_lst if f]
            fine_print = "".join(fine_print_lst)

            fine_print = "".join([f.strip() for f in fine_print.split("\n")])
            d["fine_print"] = fine_print


        #done at that stage
        return d
