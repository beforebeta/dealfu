from dealfu.esutils import EsDeals, EsDealsQuery
from django.conf import settings
from django.http import Http404


from rest_framework.response import Response
from rest_framework.views import APIView


from dealfu.serializers import DealSerializer



class DealsListView(APIView):

    def get(self, request, format=None):
        """
        Gets a list of the deals from db
        """
        es = EsDealsQuery()

        if request.QUERY_PARAMS.get("query"):
            es = es.filter_query(request.QUERY_PARAMS.get("query"))

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
