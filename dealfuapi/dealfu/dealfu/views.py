from dealfu.esutils import EsDeals, EsDealsQuery
from django.http import Http404

from rest_framework.response import Response
from rest_framework.views import APIView


from dealfu.serializers import DealSerializer


def _get_order_lists(order_str):
    """
    By default the order field is a little bit complex
    so we have to split by comma and then filter those
    that are ending with _desc
    """
    asc_list = []
    desc_list = []

    ordered_list = [o.strip() for o in order_str.split(",") if o.strip()]
    if not ordered_list:
        return (), ()

    asc_list = filter(lambda o:not o.endswith("_desc"), ordered_list)
    desc_list = filter(lambda o:o.endswith("_desc"), ordered_list)
    desc_list = [o.replace("_desc","") for o in desc_list]

    return asc_list, desc_list



class DealsListView(APIView):

    def get(self, request, format=None):
        """
        Gets a list of the deals from db
        """
        es = EsDealsQuery()
        params = request.QUERY_PARAMS

        if params.get("query"):
            es = es.filter_query(params.get("query"))

        if params.get("online"):
            es = es.filter_online(params.get("online"))

        if params.get("category_slugs"):
            cs = params.get("category_slugs")
            category_slugs = [c.strip() for c in cs.split(",")]
            es = es.filter_category_slugs(category_slugs)


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


        docs = es.query
        serializer = DealSerializer(instance=docs, many=True)
        return Response(serializer.data)





class DealsDetailView(APIView):

    def get(self, request, pk, format=None):
        """
        Gets a single one
        """
        es = EsDeals()
        if not es.exists(pk):
            ##we should raise 404
            raise Http404("not existing id")

        doc = es.get(pk)
        serializer = DealSerializer(instance=doc)
        return Response(serializer.data)
