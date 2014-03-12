from rest_framework import serializers


class EsFieldMixin(object):
    """
    Simple mixing to look at _source field of the ES data
    """
    def field_to_native(self, obj, field_name):
        src = obj.get("_source")
        if src:
            return src.get(field_name)
        return None


class EsCharField(EsFieldMixin, serializers.CharField):
    pass

class EsFloatField(EsFieldMixin, serializers.FloatField):
    pass

class EsBooleanField(EsFieldMixin, serializers.BooleanField):
    pass

class EsIntegerField(EsFieldMixin, serializers.IntegerField):
    pass


class DealMerchantAddress(serializers.Serializer):

    region = serializers.CharField()
    phone_number = serializers.CharField()

    postal_code = serializers.CharField()
    country_code = serializers.CharField()
    country = serializers.CharField()


class DealMerchantSerializer(serializers.Serializer):


    name = serializers.CharField()
    url = serializers.CharField()

    #address info here
    address = serializers.CharField()
    region = serializers.CharField()
    postal_code = serializers.CharField()
    country_code = serializers.CharField()
    country = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()

    def to_native(self, obj):
        """
        Should transform the object into something else
        Because our data in database is in format like :

        :merchant : addresses [...]

        we should extract the first address from list and put
        it into the object !!

        """
        address = obj.get("addresses")
        if address:
            address = address[0]
        else:
            return super(DealMerchantSerializer, self).to_native(obj)

        #now we should put the fields into obj
        del obj["addresses"]

        obj["address"] = address.get("address")
        obj["region"] = address.get("region")
        obj["postal_code"] = address.get("postal_code")
        obj["country_code"] = address.get("country_code")
        obj["country"] = address.get("country")

        #get the latitude and  longtitude info here
        if address.get("geo_location"):
            obj["latitude"] = address["geo_location"]["lat"]
            obj["longitude"] = address["geo_location"]["lon"]


        return super(DealMerchantSerializer, self).to_native(obj)

class EsMerchantField(EsFieldMixin, serializers.CharField):

    def field_to_native(self, obj, field_name):
        native = super(EsMerchantField, self).field_to_native(obj, field_name)
        return DealMerchantSerializer(instance=native).data


class DealSerializer(serializers.Serializer):


    id = serializers.CharField()
    title = EsCharField()
    short_title = EsCharField()
    url = EsCharField()
    untracked_url = EsCharField()
    price = EsFloatField(default=0)
    value = EsFloatField(default=0)
    discount_amount = EsFloatField(default=0)
    discount_percentage = EsFloatField(default=0)
    provider_name = EsCharField()
    provider_slug = EsCharField()
    category_name = EsCharField()
    category_slug = EsCharField()
    description = EsCharField()
    fine_print = EsCharField()
    image_url = EsCharField()
    online = EsBooleanField()
    number_sold = EsIntegerField(default=0)
    expires_at = EsCharField()

    #generate those on items pipeline first
    created_at = EsCharField()
    updated_at = EsCharField()

    merchant = EsMerchantField()


    def transform_id(self, obj, value):
        """
        Because it is _id on ES part we need to extract it
        """
        return obj.get("_id")



class DealsCategoryItemSerializer(serializers.Serializer):
    """
    The category list
    """
    parent_slug = EsCharField()
    name = EsCharField()
    slug = EsCharField()


class EsCategoryField(EsFieldMixin, serializers.CharField):
    """
    Because we have to wrap every category in "category"
    field in reponse we have to do that here !
    """
    def field_to_native(self, obj, field_name):
        return DealsCategoryItemSerializer(instance=obj).data


class DealsCategorySerializer(serializers.Serializer):

    category = EsCategoryField()

