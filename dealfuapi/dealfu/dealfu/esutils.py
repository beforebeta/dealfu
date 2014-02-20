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
        #print "QUERYYYYYYYYY ",self._query
        result = self.handle.search(index=self.index,
                                    doc_type=self.doc_type,
                                    body=self._query)

        if result["hits"]["total"] == 0:
            return []

        return result["hits"]["hits"]



    def reset(self):
        """
        Resets the query
        """
        self._query = copy(self._default_query)


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

