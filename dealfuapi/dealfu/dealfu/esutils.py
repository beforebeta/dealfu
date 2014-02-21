from copy import copy
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



class EsDeals(EsHandleMixin):

    def __init__(self):
        self.index = settings.ES_INDEX
        self.doc_type = settings.ES_INDEX_TYPE_DEALS
        self.handle = self.get_es_handle()


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



class EsDealsQuery(EsHandleMixin):

    def __init__(self):

        self.index = settings.ES_INDEX
        self.doc_type = settings.ES_INDEX_TYPE_DEALS
        self.handle = self.get_es_handle()

        self._default_query = {
            "query":{
                "filtered":{
                    "query":{
                        "match_all":{}
                    }
                }
            }
        }

        self._query = copy(self._default_query)

    @property
    def query(self):
        print "QUERYYYYYYYYY ",self._query
        result = self.handle.search(index=self.index,
                                    doc_type=self.doc_type,
                                    body=self._query)

        self.total = result["hits"]["total"]
        if self.total == 0:
            return []


        return result["hits"]["hits"]



    def reset(self):
        """
        Resets the query
        """
        self._query = copy(self._default_query)
        self.total = 0

    def filter_query(self, query):
        """
        Filters according to query
        """
        q = {
               "bool":{
                "should" : [
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
        self._query["query"]["filtered"]["query"] = q
        return self



    def filter_online(self, online):
        """
        Filters the online true false
        """
        boolq = self._get_filter_bool()
        if boolq.get("must"):
            boolq["must"].append({"term":{"online":online}})
        else:
            boolq["must"] = [{"term":{"online":online}}]

        return self


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


    def filter_page(self, page=0, per_page=10):
        """
        Filters per page
        """
        self._query["from"]= page
        self._query["size"] = per_page

        return self

    def _get_filter_bool(self):
        """
        Gets the bool part of filter query
        """
        filtered = self._query["query"]["filtered"]
        if not filtered.get("filter"):
           self._query["query"]["filtered"].update(self._get_default_filter())

        filtered = self._query["query"]["filtered"]

        boolq = filtered["filter"]["bool"]
        return boolq


    def order_by(self, asc_list, desc_list):
        """
        Orders the query by supplied parameters
        """
        asc_sorts = [{o:"asc"} for o in asc_list]
        desc_sorts = [{o:"desc"} for o in desc_list]

        sort_dict = {"sort" : asc_sorts + desc_sorts}
        self._query.update(sort_dict)

        return self




    def _get_default_filter(self):
        """
        The default filter query
        """
        return {
            "filter":{
                "bool":{}
            }
        }
