"""
The general pipe that is base for all spiders
"""
import datetime
from copy import copy
from redis.client import Redis

from scrapy import log
from scrapy.exceptions import DropItem

from dealfu_groupon.utils import check_spider_pipeline, get_es, needs_geo_fetch, is_item_in_geo_queue, \
    should_item_be_enabled
from dealfu_groupon.background.geocode import submit_geo_request


class BaseEsPipe(object):
    """
    The general duty fo that pipe is to get scrapped item
    and save it into ES database, and send its addresses to be
    geo processed
    """

    def open_spider(self, spider):
        """
        Here will initialize some the data you can be sure
        you get after that method is

        settings, log, es, and redis_conn objects
        """
        self.settings = spider.settings
        self.log = spider.log
        self.es = get_es(self.settings)

        self.redis_conn = Redis(host=self.settings.get("REDIS_HOST"),
                                port=self.settings.get("REDIS_PORT"))


    @check_spider_pipeline
    def process_item(self, item, spider):
        """
        Process the item
        """
        if self._is_duplicate(item):
            #maybe we missed the geo thing before
            self._add_if_to_geo_request(item, item["id"])
            #the item is already in database we don't need to add it again
            self.on_duplicate_item(item, item["id"])

            raise DropItem("The item :%s is already in db"%item.get("untracked_url"))

        doc_id = self.save_item(item)
        if not doc_id:
            raise DropItem("Error when inserting item : %s"%item)
        item["id"] = doc_id


        #here check if we should add it to retry list
        self._add_if_to_geo_request(item, doc_id)


        #check if we should enabled the item
        if should_item_be_enabled(item):
            self.update_item(doc_id, {"enabled":True})

        #you can hook on here !
        self.on_end_processing(item, spider)

        return item


    #hook methods

    def on_duplicate_item(self, item, item_id):
        """
        Some action to be taken on duplication
        """
        pass


    def on_end_processing(self, item, spider):
        """
        Some action to be taken at the end of the processing item
        """
        pass


    def save_item(self, item):
        """
        Saves the item into db
        """

        item["created_at"] = datetime.datetime.utcnow()
        item["updated_at"] = datetime.datetime.utcnow()

        #we don't need that part here !
        copy_item = copy(dict(item))
        if copy_item.get("id"):
            copy_item.pop("id")

        result = self.es.create(index=self.settings.get("ES_INDEX"),
                                doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                                body=copy_item)


        doc_id = result.get("_id")
        return doc_id


    def update_item(self, item_id, item_dict):
        """
        Updates the item
        """
        res = self.es.update(index=self.settings.get("ES_INDEX"),
                            doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                            body={"doc":item_dict},
                            id=item_id)

        return res


    def _add_if_to_geo_request(self, item, item_id):
        """
        Adds item into geo request queue if legitime to be gathered
        """
        #print "SUBMIT GEO REQUEST : ",item_id
        if not needs_geo_fetch(item, item_id=item_id, logger=self.log):
            return False

        #check here if it is the geo list for fetching, if yes no need
        #to resubmit it again
        redis_key = self.settings.get("REDIS_GEO_POLL_LIST")
        if is_item_in_geo_queue(self.redis_conn, redis_key, item_id):
            self.log("Item already in geo queue no need for refetch", log.INFO)
            return False

        #submit to celery to be processed!
        async_result = submit_geo_request.delay(self.settings, item_id)
        #print "SUBMITED GEO REQUEST : ",item_id
        return True



    def _is_duplicate(self, item):
        """
        Checks for an item if it is a duplicate in database
        Basically checks the untracked_url attribute
        and if there is such an item return True oterwise False

        NOTE: if item exists it should add an "id" field to item
        it is a mutation in read only, so not very beautiful!!!

        """
        query = {
            "query": {
                "match": {
                    "untracked_url": item.get("untracked_url")
                }
            }
        }

        result = self.es.search(index=self.settings.get("ES_INDEX"),
                                doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                                body=query)

        total = result["hits"]["total"]
        if total != 0:
            item_id = result["hits"]["hits"][0]["_id"]
            item["id"] = item_id
            return True

        return False
