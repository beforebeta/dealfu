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
    region_long = Field()
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
    url = Field()#company web site
    addresses = Field() #list of MerchantAddressItems



class DealfuItem(Item):

    untracked_url = Field()
    online = Field()

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

    #category info
    category_name = Field()
    category_slug = Field()

    #the site you're getting the deals
    provider_name = Field()
    provider_slug = Field()

    #ref to MerchantItem
    merchant = Field()



class DealCategoryItem(Item):
    """
    That will be the category tree
    matching the sqoot structure !!
    """
    name = Field()
    slug = Field()
    parent_slug = Field()
