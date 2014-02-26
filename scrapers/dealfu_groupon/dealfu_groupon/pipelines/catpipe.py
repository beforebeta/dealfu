import datetime

from scrapy.exceptions import DropItem

from dealfu_groupon.utils import get_es
from dealfu_groupon.utils import check_spider_pipeline

import elasticsearch


class CatPipeLine(object):
    """
    Generally inserts data into ES
    """

    def open_spider(self, spider):
        """
        Here will initialize some the data
        """
        self.settings = spider.settings
        self.es = get_es(self.settings)


    @check_spider_pipeline
    def process_item(self, item, spider):
        """
        Insert item into database or just drop it if not handled
        """
        #well we don't want duplicates so, check before inserting

        dup_query = {
            "query":{
                "match": {
                    "slug": item["slug"]
                }
            }
        }

        result = self.es.search(index=self.settings.get("ES_INDEX"),
                                doc_type=self.settings.get("ES_INDEX_TYPE_CATEGORY"),
                                body=dup_query)

        total = result["hits"]["total"]
        if not total == 0:
            raise DropItem("Item : %s already exists "%item["slug"])


        #insert the item we are good to go
        self.es.create(index=self.settings.get("ES_INDEX"),
                       doc_type=self.settings.get("ES_INDEX_TYPE_CATEGORY"),
                       body=dict(item))

        return item



