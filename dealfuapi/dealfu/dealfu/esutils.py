from copy import copy
from dealfu.utils import find_nearest_address
from django.conf import settings
import elasticsearch


class EsHandleMixin(object):

    def get_es_handle(self):
        """
        Gets an ES handle
        """
        d = {
            "host":settings.ES_SERVER,
            "port":settings.ES_PORT
        }

        return elasticsearch.Elasticsearch(hosts=[d])


    @property
    def handle(self):
        """
        The default implementation
        """
        return self.get_es_handle()


class EsDeals(EsHandleMixin):

    def __init__(self):
        self.index = settings.ES_INDEX
        self.doc_type = settings.ES_INDEX_TYPE_DEALS
        #self.handle = self.get_es_handle()


    def get(self, obj_id):
        """
        Returns the object from db
        """
        doc = self.handle.get(index=self.index,
                            id=obj_id,
                            doc_type=self.doc_type)


        return doc

    def exists(self, obj_id):
        """
        Checks if it is there
        """
        return self.handle.exists(index=self.index,
                                  id=obj_id,
                                  doc_type=self.doc_type)


class EsBaseQueryMixin(object):
    """
    The base query class

    It is mixed in something that has
    @index
    @doc_type
    @_query : this is the internal structure of search query
    @total
    @handle
    """
    @property
    def query(self):
        #print "QUERYYYYYYYYY ",self._query
        return self.fetch()


    def fetch(self):
        """
        That seems to be a better name for getting data
        """
        print "QUERY : ",self._query
        result = self.handle.search(index=self.index,
                                    doc_type=self.doc_type,
                                    body=self._query)

        self.total = result["hits"]["total"]
        if self.total == 0:
            return []


        return result["hits"]["hits"]


    def filter_page(self, page=0, per_page=10):
        """
        Filters per page
        """
        self._query["from"]= page * per_page
        self._query["size"] = per_page

        #print self._query

        return self


    def order_by(self, asc_list, desc_list):
        """
        Orders the query by supplied parameters
        """
        asc_sorts = [{o:"asc"} for o in asc_list]
        desc_sorts = [{o:"desc"} for o in desc_list]

        sort_list = self._query.get("sort", [])
        sort_list.extend(asc_sorts)
        sort_list.extend(desc_sorts)

        sort_dict = {"sort" : sort_list}
        self._query.update(sort_dict)

        return self


    def order_by_distance(self, lat, lon, order="asc"):
        """
        It is a separate order_by method because we should handle
        that one differently, its structure is kind of different
        """
        d = {
            "_geo_distance": {
                "merchant.addresses.geo_location":[lon, lat],
                "unit":"mi",
                "order": order
          }
        }

        sort_list = self._query.get("sort", [])
        sort_list.append(d)
        self._query.update({"sort":sort_list})

        return self


class EsDealCategoryQuery(EsHandleMixin, EsBaseQueryMixin):
    """
    The deals query
    """
    index = settings.ES_INDEX
    doc_type = settings.ES_INDEX_TYPE_CATEGORY


    def __init__(self):
        """
        Init some of the data
        maybe we should move more to the base class ?
        """
        self.total = 0
        self._default_query = {

            "query":{
                "match_all":{}
            }

        }

        self._query = copy(self._default_query)


class EsDealsQuery(EsHandleMixin, EsBaseQueryMixin):

    index = settings.ES_INDEX
    doc_type = settings.ES_INDEX_TYPE_DEALS

    def __init__(self):

        self.total = 0

        self._default_query = {
            "query": {
                "filtered":{
                    "filter": {
                        "and": {
                            "filters": [
                                {
                                    "query": {
                                        "match_all": {}
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }

        self._query = copy(self._default_query)

        #geo info resetting
        self._geo_enabled = False
        self._geo_params = {}

        #first get only enabled:True
        self.filter_by_enabled()


    def _get_and_filter(self):
        """
        Returns back the and filter from internal query
        """
        return self._query["query"]["filtered"]["filter"]["and"]["filters"]



    def _get_filter_bool(self):
        """
        Gets the bool part of filter query
        """
        and_filter = self._get_and_filter()
        for f in and_filter:
            if f.has_key("bool"):
                return f

        bools = {"bool":{}}
        and_filter.append(bools)

        return bools




    def reset(self):
        """
        Resets the query
        """
        self._query = copy(self._default_query)
        self.total = 0

        self._geo_enabled = False
        self._geo_params = {}



    def filter_query(self, query):
        """
        Filters according to query
        """
        q = {
            "query":{
                "bool":{
                    "should":[
                        {
                            "term" : { "title" : query }
                        },
                        {
                            "term" : { "description" : query }
                        },
                        {
                            "term" : { "fine_print" : query }
                        }
                    ]
                }
            }
        }

        and_filter = self._get_and_filter()

        #we should have only one query so lets check if have another one
        found = False
        for a in and_filter:
            if a.has_key("query"):
                a["query"] = q["query"]
                found = True
                break
        if not found:
            and_filter.append(q)

        return self


    def filter_field_generic(self, fieldname, value):
        """
        A generic filter that works for any value which is
        filterable !!!
        """
        boolq = self._get_filter_bool()["bool"]
        if boolq.get("must"):
            boolq["must"].append({"term":{fieldname:value}})
        else:
            boolq["must"] = [{"term":{fieldname:value}}]

        return self


    def filter_by_enabled(self):
        """
        Filters only enabled=True
        """
        return self.filter_field_generic("enabled", True)


    def filter_online(self, online):
        """
        Filters the online true false
        """
        return self.filter_field_generic("online", online)


    def filter_category_slugs(self, category_slugs):
        """
        Filters a list of category slugs
        """
        shoulds = [{"term":{"category_slug":c}} for c in category_slugs]

        boolq = self._get_filter_bool()
        if boolq.get("should"):
            boolq["should"].extend(shoulds)
        else:
            boolq["should"] = shoulds

        return self


    def filter_geo_location(self, lat, lon, miles=10):
        geo_dict = {
            "geo_distance": {
                "distance": "%dmi"%miles,
                "merchant.addresses.geo_location": {
                    "lat": lat,
                    "lon": lon
                }
            }
        }

        and_filter = self._get_and_filter()
        and_filter.append(geo_dict)

        #enable geo params
        self._geo_enabled = True
        self._geo_params["lat"] = lat
        self._geo_params["lon"] = lon

        return self


    def _add_to_and_filter(self, d):
        """
        Adds the supplied dictionary into and filter
        TODO: implement those
        """
        pass

    def _add_to_bool_filter(self, d):
        """
        Adds the supplied dictionary into bool filter
        it should contain some sort of "should", "must" and etc
        TODO: implement
        """
        pass
