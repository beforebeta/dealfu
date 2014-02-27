import datetime
from copy import copy

from dealfu_groupon.utils import check_spider_pipeline, get_es


class EsPipeLine(object):
    """
    Generally inserts data into ES
    and maybe something more ?
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
        #ser = json.dumps(dict(item))
        #res = json.loads(ser)

        item["created_at"] = datetime.datetime.utcnow()
        item["updated_at"] = datetime.datetime.utcnow()

        #we don't need that part here !
        copy_item = copy(dict(item))
        copy_item.pop("id")


        self.es.create(index=self.settings.get("ES_INDEX"),
                       doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                       body=copy_item)
        return item
