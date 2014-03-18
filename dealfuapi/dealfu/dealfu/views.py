from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.conf import settings

from rest_framework.authentication import BaseAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import exceptions

from dealfu.esutils import EsDeals, EsDealsQuery, EsDealCategoryQuery
from dealfu.serializers import DealSerializer, DealsCategorySerializer


def get_query_default():
    """
    TODO move those stats into some of the query classes !
    """
    return {"query":{
            "page":1,
            "per_page":10,
            "location":{},
            "radius":10,
            "online":True,
            "category_slugs":[],
            "provider_slugs":[],
            "updated_after":None}
        }


def update_query_total(d, total):
    d["query"]["total"] = total
    return d

def update_query_page(d, page):
    d["query"]["page"] = page
    return d

def update_query_per_page(d, per_page):
    d["query"]["per_page"] = per_page
    return d

def update_query_location(d, location, radius):
    d["query"]["location"] = location
    d["query"]["radius"] = radius

    return d

def update_query_online(d, online):
    d["query"]["online"] = online
    return d

def update_query_category_slugs(d, category_slugs):
    d["query"]["category_slugs"] = category_slugs
    return d




def _get_order_lists(order_str, valid_keys):
    """
    By default the order field is a little bit complex
    so we have to split by comma and then filter those
    that are ending with _desc
    """
    ordered_list = [o.strip() for o in order_str.split(",") if o.strip()]
    if not ordered_list:
        return (), ()

    asc_list = filter(lambda o:not o.endswith("_desc"), ordered_list)
    desc_list = filter(lambda o:o.endswith("_desc"), ordered_list)
    desc_list = [o.replace("_desc","") for o in desc_list]

    #finally we should remove those that are not supported
    asc_list = [a for a in asc_list if a in valid_keys]
    desc_list = [d for d in desc_list if d in valid_keys]


    return asc_list, desc_list


class ApiKeyAuth(BaseAuthentication):

    def authenticate(self, request):
        if not request.QUERY_PARAMS.get("api_key"):
            raise exceptions.AuthenticationFailed('Api Key required')

        api_key = request.QUERY_PARAMS.get("api_key")
        if settings.AUTH_KEY != api_key:
            raise exceptions.AuthenticationFailed('Invalid Api Key')

        return (AnonymousUser(), None)




class DealsListView(APIView):

    authentication_classes = (ApiKeyAuth,)

    def get(self, request, format=None):
        """
        Gets a list of the deals from db
        """
        context = {} #the context for serializer
        es = EsDealsQuery()
        params = request.QUERY_PARAMS
        query = get_query_default()

        if params.get("query"):
            es = es.filter_query(params.get("query"))

        if params.get("online"):
            query = update_query_online(query, params.get("online"))
            es = es.filter_online(params.get("online"))

        if params.get("category_slugs"):
            cs = params.get("category_slugs")
            category_slugs = [c.strip() for c in cs.split(",")]
            query = update_query_category_slugs(query, category_slugs)

            es = es.filter_category_slugs(category_slugs)

        if params.get("location"):
            lat, lon = params.get("location").strip().split(",")
            lat = float(lat)
            lon = float(lon)


            radius = 10 #default value TODO move to settings
            if params.get("radius"):
                radius = int(params.get("radius"))

            geo_dict = {
                "latitude":lat,
                "longitude":lon
            }

            query = update_query_location(query, geo_dict, radius)

            #update the context here
            context["geo_info"] = geo_dict


            es = es.filter_geo_location(lat, lon, miles=radius)




        if params.get("order"):
            asc, desc = _get_order_lists(params.get("order"),
                                         settings.API_DEALS_SORT_KEYS)
            #we have a distance param which is should be handled
            #differently than others
            if "distance" in asc:
                asc.remove("distance")
                if context.has_key("geo_info"):
                    es = es.order_by_distance(context["geo_info"]["latitude"],
                                              context["geo_info"]["longitude"],
                                              order="asc")

            if "distance" in desc:
                desc.remove("distance")
                if context.has_key("geo_info"):
                    es = es.order_by_distance(context["geo_info"]["latitude"],
                                              context["geo_info"]["longitude"],
                                              order="desc")

            #we should remove those that are not supported ?
            if asc or desc:
                es = es.order_by(asc, desc)


        #put those in settings
        page = 1
        per_page = settings.API_DEALS_PER_PAGE


        if params.get("page"):
            query = update_query_page(query, params.get("page"))
            page = int(params.get("page"))

        if params.get("per_page"):
            query = update_query_per_page(query, params.get("per_page"))
            per_page = int(params.get("per_page"))


        #the pagination will be here !
        es = es.filter_page(page=page-1,
                            per_page=per_page)


        docs = es.fetch()
        query = update_query_total(query, es.total)
        #print "FINAL_QUERY : ",query
        serializer = DealSerializer(instance=docs, many=True, context=context)
        data = {"deals":serializer.data}
        data.update(query)
        return Response(data)





class DealsDetailView(APIView):

    authentication_classes = (ApiKeyAuth,)

    def get(self, request, pk, format=None):
        """
        Gets a single one
        """
        es = EsDeals()
        if not es.exists(pk):
            ##we should raise 404
            raise Http404("not existing id")

        doc = es.get(pk)
        if not doc["_source"].get("enabled"):
            raise Http404("not existing document")

        
        serializer = DealSerializer(instance=doc)
        return Response(serializer.data)


class DealsCategoryListView(APIView):
    authentication_classes = (ApiKeyAuth,)


    def get(self, request, format=None):
        """
        Gets a list of the deals from db
        """
        es = EsDealCategoryQuery()
        params = request.QUERY_PARAMS


        if params.get("order"):
            asc, desc = _get_order_lists(params.get("order"))
            es = es.order_by(asc, desc)

        #put those in settings
        page = 0
        per_page = 10

        if params.get("page"):
            page = int(params.get("page"))

        if params.get("per_page"):
            per_page = int(params.get("per_page"))


        #the pagination will be here !
        es = es.filter_page(page=page,
                            per_page=per_page)


        docs = es.fetch()
        #print "FINAL_QUERY : ",query
        serializer = DealsCategorySerializer(instance=docs, many=True)
        data = {"categories":serializer.data}
        #data.update(query)
        return Response(data)
