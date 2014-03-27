from itertools import chain
import re

from dateutil.parser import parse


from scrapy.http import Request
from scrapy.spider import Spider
from scrapy.selector import Selector

from dealfu_groupon.items import DealfuItem, MerchantItem
from dealfu_groupon.utils import get_first_from_xp, clean_float_values, strip_list_to_str, slugify, get_in
from dealfu_groupon.pipelines import genespipe, emptypipe


class LiveSocialSpider(Spider):

    name = "livesocial"
    allowed_domains = ["livingsocial.com"]

    #only work with those pipelines by default
    pipeline = set([
        genespipe.BaseEsPipe
        #emptypipe.EmptyPipe
    ])


    main_url = "https://www.livingsocial.com"

    start_urls = ["https://www.livingsocial.com/categories"]

    def __init__(self, only_one_page=False, only_one_deal=False,
                 pipeline=None, num_of_deals=None,
                 start_point="category", *args, **kw):
        super(LiveSocialSpider, self).__init__(*args, **kw)

        self.only_one_page = only_one_page
        self.only_one_deal  = only_one_deal
        self.num_of_deals = int(num_of_deals) if num_of_deals else num_of_deals
        self.total_deals = 0
        self.start_point = start_point

        if start_point == "city": #we should change the start urls
            self.start_urls = ["https://www.livingsocial.com/locations"]
        elif start_point == "paging":
            self.start_urls = ["https://www.livingsocial.com/more_deals?page=1",
                               "https://www.livingsocial.com/more_deals/online"]

        if pipeline:
            self.pipeline = pipeline if isinstance(pipeline, list) or isinstance(pipeline, set) else set([pipeline])



    def parse(self, response):
        """
        Starts parsing from here!
        @param response:
        @return:
        """
        #print "START ",self.start_point

        if self.only_one_deal:
            #if wee need get whole list go from here
            yield Request(response.url,
                          callback=self.parse_deal)

        elif self.start_point == "category":
            #if we need only one deal just go from here
            yield Request(response.url,
                           callback=self._parse_categories)

        elif self.start_point == "city":
            yield Request(response.url,
                           callback=self._parse_cities)


        elif self.start_point == "paging":
            yield Request(response.url,
                           callback=self._parse_pages)


    def _parse_pages(self, response):
        """
        Traverses pages and goes to the next page if any
        """
        sel = Selector(response)
        ahrefs = sel.xpath('//div[contains(@class, "lead")]/div/p[2]/a')
        ## print ahrefs
        if not ahrefs:
            return

        found_url = None
        for a in ahrefs:
            t = get_first_from_xp(a.xpath("./text()"))
            if not t:
                continue
            if "next" in t.strip().lower():
                url = get_first_from_xp(a.xpath("./@href"))
                url = '/'.join(s.strip('/') for s in [self.main_url, url])
                #print "NEXT : ",url
                found_url = url
                break

        if found_url:
            yield Request(found_url,
                          callback=self._parse_pages)


        #look for links and yield them also
        deals_a = sel.xpath('//div[contains(@class, "lead")]/p/a')
        if deals_a:
            for deal_xp in deals_a:
                url = get_first_from_xp(deal_xp.xpath("./@href"))
                yield Request(url,
                              callback=self.parse_deal)


    def _parse_categories(self, response):
        """
        Get the category list and yield to categoried city pages
        """

        def _make_cb(catname):
            return lambda response: self._parse_cities(response, catname)

        sel = Selector(response)
        main_categories_xpath = sel.xpath("//ul[contains(@class, 'regions')]/li[contains(@class, 'region')]")
        if not main_categories_xpath:
            return

        for mc in main_categories_xpath:
            main_name = get_first_from_xp(mc.xpath('.//h3/text()'))
            sub_cats = mc.xpath("./ul[contains(@class, 'cities')]//a")
            for sub_cat in sub_cats:
                url = get_first_from_xp(sub_cat.xpath("./@href"))
                text = get_first_from_xp(sub_cat.xpath("./text()"))

                cb = _make_cb(text)
                yield Request(url, callback=cb)



    def _parse_cities(self, response, category=None):
        """
        Gets the list of cities and yield to pages with deals
        """
        #print "IN CITIES : "
        def _make_cb(city, category):
            return lambda resp: self._parse_deals_in_cities(resp, city, category=category)

        sel = Selector(response)

        ids_get = ["continent-north-america", "continent-south-america"]
        for i in ids_get:
            regions_xp = sel.xpath('//li[@id="{}"]//ul[contains(@class, "regions")]'.format(i))
            #print regions_xp

            if not regions_xp:
                continue

            #country with states
            states_xp = regions_xp.xpath("./li[contains(@class,'country-with-states')]//li[contains(@class, 'region')]")
            for state_xp in states_xp:
                state_name = get_first_from_xp(state_xp.xpath("./h3/text()"))
                cities_xp = states_xp.xpath(".//li/a")
                for city_xp in cities_xp:
                    city_name = get_first_from_xp(city_xp.xpath("./text()"))
                    url = get_first_from_xp(city_xp.xpath("./@href"))

                    #print "%s:%s%s"%(state_name, city_name, url)
                    if not url.startswith("http"):
                        url = '/'.join(s.strip('/') for s in [self.main_url, url])

                    yield Request(url, callback=_make_cb(city_name, category))

            #country without states
            cities_xp = regions_xp.xpath('./li[contains(@class, "region")]//ul[contains(@class, "cities")]//a')
            for city_xp in cities_xp:
                city_name = get_first_from_xp(city_xp.xpath("./text()"))
                url = get_first_from_xp(city_xp.xpath("./@href"))

                if not url.startswith("http"):
                    url = '/'.join(s.strip('/') for s in [self.main_url, url])

                yield Request(url, callback=_make_cb(city_name, category))


    def _parse_deals_in_cities(self, response, city, category=None):
        """
        Parses deals in cities list page
        """
        def _make_cb(catname):
            return lambda response: self.parse_deal(response, catname)

        sel = Selector(response)

        #we have 2 xps feautured
        featured_xp = sel.xpath('//ul[contains(@class, "featured-deals")]/li/a/@href')
        #and popular ones
        popular_xp = sel.xpath('//ul[contains(@class, "popular-deals")]/li/a/@href')

        for ahref_xp in chain(featured_xp, popular_xp):
            if not ahref_xp:
                continue

            url = ahref_xp.extract().strip()
            yield Request(url, callback=_make_cb(category), meta={"cache_me":True})


    def parse_deal(self, response, category=None):
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

        #category info here
        if category:
            d["category_slug"] = slugify(category)
            d["category_name"] = category

        #online/offline here
        if not get_in(d, "merchant", "addresses"):
            d["online"] = True
        else:
            d["online"] = False

        return d

    def _extract_title_from_meta(self, response):
        """
        Gets the title from meta info
        """
        d = {}
        sel = Selector(response)


        meta_xp = sel.xpath('//meta[@property="og:title"]/@content')
        if not meta_xp:
            return d

        meta_title = meta_xp.extract()[0]
        if not meta_title:
            return d

        d["title"] = meta_title.strip()

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
        else:
            price = get_first_from_xp(sel.xpath('//div[contains(@class, "price")]//b/text()'))
            if price:
                d["price"] = clean_float_values(price, "$")


        #check for discount info
        discount_percentage = get_first_from_xp(sel.xpath('//ul[@id="stats_deal_list"]//li[1]/div/text()'))
        if not discount_percentage:
            discount_percentage = get_first_from_xp(sel.xpath('//div[contains(@class, "deal-info")]/div[contains(@class, "discount")]/span[contains(@class, "value")]/text()'))

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
        if not sold_items:
            sold_items = get_first_from_xp(sel.xpath('//div[contains(@class, "deal-info")]/div[contains(@class, "purchased")]/span[contains(@class, "value")]/text()'))
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
        if not merchant_name_xp:
            merchant_name_xp = sel.xpath('//section[contains(@class, "event-venue")]/div[contains(@class, "venue-info")]/h4/text()')
        merchant_name = get_first_from_xp(merchant_name_xp)
        if not merchant_name:
            return  m

        m["name"] = merchant_name.strip()
        #extract the address info here
        #'//*[contains(@class, "phone")]'
        address_info_xps = sel.xpath('//div[contains(@class, "location")]//div[contains(@class, "address-location-info")]')
        addresses = []

        if address_info_xps:
            for address_xp in address_info_xps:
                tmp_addr = {"country":"United States",
                            "country_code":"US"}

                address = address_xp.xpath('.//*[contains(@class, "street_1")]//text()')
                if address:
                    address_txt = strip_list_to_str(address.extract())
                    tmp_addr["address"] = address_txt

                phone = get_first_from_xp(address_xp.xpath('.//*[contains(@class, "phone")]//text()'))
                if phone:
                    tmp_addr["phone_number"] = phone.replace("|", "").strip()

                if tmp_addr:
                    addresses.append(tmp_addr)
        else:
            xp_str = '//section[contains(@class, "event-venue")]/div[contains(@class, "venue-info")]/address//text()[not(ancestor::a)]'
            addr_xp = sel.xpath(xp_str)
            if addr_xp:
                addr_text = strip_list_to_str(addr_xp.extract())
                res = re.search("(.*)(\d{3}\-\d{3}\-\d{4})", addr_text)
                tmp_addr = {"country":"United States",
                            "country_code":"US"}

                if res:
                    final_address = res.group(1).strip().strip("|")
                    tmp_addr["address"] = final_address
                    tmp_addr["phone_number"] = res.group(2).strip()
                else:
                    tmp_addr["address"] = addr_text.strip().strip("|")

                addresses.append(tmp_addr)

        #assign the collected addresses
        m["addresses"] = addresses

        tmp_dict = self._extract_merchant_urls(response)
        if tmp_dict:
            m.update(tmp_dict)
        

        return dict(m)

    def _extract_merchant_urls(self, response):
        """
        Gets the merchant url and facebook url
        """
        d = {}

        sel = Selector(response)

        ahrefs = sel.xpath('//div[@id="view-details-full"]//a')
        if not ahrefs:
            ahrefs = sel.xpath('//div[@id="event-details"]//a')

        if not ahrefs:
            return d

        for ahref in ahrefs:
            url = get_first_from_xp(ahref.xpath("./@href"))
            text = get_first_from_xp(ahref.xpath("./text()"))
            if text and "website" in text.strip().lower():
                d["url"] = url
            elif text and "facebook" in text.strip().lower():
                d["facebook_url"] = url

        return d



    def _extract_deal_image(self, response):
        """
        Gets the deal image
        """
        d = {}

        sel = Selector(response)
        image_xp = get_first_from_xp(sel.xpath('//div[contains(@class, "deal-image")]/@style'))
        if not image_xp:
            #it maybe some event type thing
            meta_xp = sel.xpath('//meta[@property="og:image"]/@content')
            if not meta_xp:
                return d

            meta_image = meta_xp.extract()[0]
            if not meta_image:
                return d

            d["image_url"] = meta_image
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
        if title_xp:
            d["title"] = get_first_from_xp(title_xp)
        else:
            d["title"] = self._extract_title_from_meta(response).get("title")


        #get the description
        description_xp = sel.xpath('//div[@id="view-details-full"]//p')
        if description_xp:
            description_xp_lst = description_xp.extract()
            d["description"] = "".join([desc.strip() for desc in description_xp_lst if desc.strip()])
        else:
            description_xp = sel.xpath('//div[contains(@class, "event-details")]//div[contains(@class, "deal-description")]')
            description_xp_lst = description_xp.extract()
            d["description"] = strip_list_to_str(description_xp_lst)


        #get the fine_print
        fine_print_xp = sel.xpath('//div[@id="fine-print-full"]//div[@class="fine-print"]//text()')
        if not fine_print_xp:
            fine_print_xp = sel.xpath('//div[contains(@class, "event-details")]//section[contains(@class, "fine-print")]//text()')

        if fine_print_xp:
            fine_print_lst = [f.extract().strip() for f in fine_print_xp]
            fine_print_lst = [f for f in fine_print_lst if f]
            fine_print = "".join(fine_print_lst)

            fine_print = "".join([f.strip() for f in fine_print.split("\n")])
            d["fine_print"] = fine_print


        #done at that stage
        return d
