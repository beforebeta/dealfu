import json
from scrapy.exceptions import DropItem

import elasticsearch
from elasticsearch.client import IndicesClient

class EsPipeLine(object):
    """
    Generally inserts data into ES
    """

    def open_spider(self, spider):
        """
        Here will initialize some the data
        """
        self.settings = spider.settings
        self.es = self._get_es(self.settings)


    def process_item(self, item, spider):
        """
        Insert item into database or just drop it if not handled
        """
        #ser = json.dumps(dict(item))
        #res = json.loads(ser)
        print "WHAT IS : ",self.es.create(index=self.settings.get("ES_INDEX"),
                                        doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                                        body=dict(item))
        return item



    def _get_es(self, settings):
        """
        Gets an ES handle
        """
        d = {
            "host":settings.get("ES_SERVER"),
            "port":settings.get("ES_PORT")
        }

        return elasticsearch.Elasticsearch(hosts=[d])
