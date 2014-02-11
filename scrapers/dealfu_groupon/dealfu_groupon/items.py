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
    discount_amount = Field()
    discount_percentage = Field()
    price = Field()
    value = Field()

    #ref to MerchantItem
    merchant = Field()
