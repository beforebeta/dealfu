# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

from scrapy.item import Item, Field


class MerchantAddressItem(Item):

    address_name = Field()
    address = Field()
    locality = Field() #mountain view ?
    region = Field()
    postal_code = Field()
    country = Field()
    country_code = Field()
    latitude = Field()
    longtitude = Field()
    phone_number = Field()


class MerchantItem(Item):
    """
    Merchant Item in a deal
    """
    name = Field()
    addresses = Field() #list of MerchantAddressItems



class DealfuItem(Item):

    url = Field()

    #price information
    discount_amount = Field()
    discount_percentage = Field()
    price = Field()
    value = Field()
    commission = Field()

    number_sold = Field()

    #content fields
    title = Field()
    short_title = Field()
    image_url = Field()
    description = Field()
    fine_print = Field()
    expires_at = Field()

    #online = Field not sure how to get that one
    #how to figure out the categories at that stage ?
    #category_name = Field()
    #category_field = Field()

    #the site you're getting the deals
    provider_name = Field()
    provider_slug = Field()

    #ref to MerchantItem
    merchant = Field()
