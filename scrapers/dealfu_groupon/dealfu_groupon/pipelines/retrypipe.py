from celery.utils import jsonify
from elasticsearch.exceptions import TransportError
from scrapy.exceptions import DropItem
from scrapy import log
from redis import Redis

from dealfu_groupon.utils import check_spider_pipeline, get_es, merge_dict_items, needs_retry


class RetryPipeLine(object):
    """
    Retry pipeline checks for specific item if current
    parsed version is better than the one in database
    if not it re-schedules it again to be checked later
    """

    def open_spider(self, spider):
        """
        Here will initialize some the data
        """
        #print "SPIDER PIPELINEEEEE ",spider.pipeline
        self.settings = spider.settings
        self.es = get_es(self.settings)
        self.redis_conn = Redis(host=self.settings.get("REDIS_HOST"),
                                port=self.settings.get("REDIS_PORT"))


    @check_spider_pipeline
    def process_item(self, item, spider):
        """
        Retry specified the specified item
        """
        spider.log("RETRY ITEM : %s "%item["id"], log.INFO)
        spider.log("RETRY_DETAIL : %s"%jsonify(dict(item)), log.INFO)

        retry_key = self.settings.get("REDIS_RETRY_PREFIX")%item.get("id")
        if not self.redis_conn.exists(retry_key):
            raise DropItem("Non existing retry task : %s "%item["id"])

        retry_dict = self.redis_conn.hgetall(retry_key)

        try:
            result = self.es.get(index=self.settings.get("ES_INDEX"),
                        doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                        id=item["id"])['_source']

        except TransportError,ex:
            self._mark_failed(retry_key, retry_dict)
            raise DropItem("Non existing item : %s "%item["id"])

        merged_item = merge_dict_items(result, item)

        if not needs_retry(merged_item):
            #mark item as finished so the other end can finish that
            retry_dict["status"] = self.settings.get("REDIS_RETRY_STATUS_FINISHED")
            self.redis_conn.hmset(retry_key, retry_dict)
        else:
            #decrase the retry count so other part can know if it failed
            retry_count = int(retry_dict["retry_count"])
            retry_count -= 1

            if retry_count <= 0:
                retry_dict["status"] = self.settings.get("REDIS_RETRY_STATUS_FAILED")

            retry_dict["retry_count"] = retry_count
            #set the final structure
            self.redis_conn.hmset(retry_key, retry_dict)

        return item


    def _mark_failed(self, retry_key, retry_dict):
        """
        Mark item as failed
        """
        retry_dict["status"] = self.settings.get("REDIS_RETRY_STATUS_FAILED")
        self.redis_conn.hmset(retry_key, retry_dict)
        return True
