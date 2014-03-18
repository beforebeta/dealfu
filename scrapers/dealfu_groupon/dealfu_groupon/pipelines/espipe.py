import datetime
from copy import copy
from dealfu_groupon.background.geocode import is_valid_address, submit_geo_request

from redis.client import Redis

from scrapy import log
from scrapy.exceptions import DropItem

from dealfu_groupon.utils import check_spider_pipeline, get_es, needs_retry
from dealfu_groupon.background.retry import retry_document


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
        self.log = spider.log
        self.es = get_es(self.settings)
        self.redis_conn = Redis(host=self.settings.get("REDIS_HOST"),
                                port=self.settings.get("REDIS_PORT"))

        #you should put the items that will be retried here !
        self.retry_list = []

    @check_spider_pipeline
    def process_item(self, item, spider):
        """
        Insert item into database or just drop it if not handled
        """
        #ser = json.dumps(dict(item))
        #res = json.loads(ser)

        if self._is_duplicate(item):
            #maybe previous time we didn't complete whole retry thing
            self._add_if_to_rety_list(item)
            #the item is already in database we don't need to add it again
            raise DropItem("The item :%s is already in db"%item.get("untracked_url"))

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
        if not doc_id:
            raise DropItem("Error when inserting item : %s"%item)
        item["id"] = doc_id

        #here check if we should add it to retry list
        self._add_if_to_rety_list(item)
        self._add_if_to_geo_request(item, doc_id)

        return item


    def _add_if_to_geo_request(self, item, item_id):
        """
        Adds item into geo request queue if legitime to be gathered
        """
        merchant = item.get("merchant")
        if not merchant:
            self.log("No merchant info, not submitted for geo request : {0}"
                        .format(item_id))
            return False

        addresses = merchant.get("addresses")
        if not addresses:
            self.log("No address info, not submitted for geo request : {0}"
                        .format(item_id))
            return False


        if not any([a for a in addresses if is_valid_address(a)]):
            self.log("No valid address info, not submitted for geo request : {0}"
                        .format(item_id))
            return False

        #submit to celery to be processed!
        async_result = submit_geo_request.delay(self.settings, item_id)
        return True



    def _is_duplicate(self, item):
        """
        Checks for an item if it is a duplicate in database
        Basically checks the untracked_url attribute
        and if there is such an item return True oterwise False
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
            return True

        return False



    def close_spider(self, spider):
        """
        At that stage we should send the items that needs to be
        retried to our background mechanism !
        """
        spider.log("----------- THE RETRY LIST IS HERE ---------------", log.DEBUG)
        spider.log(self.retry_list, log.DEBUG)
        if not self.retry_list:
            #there is no need to schedule anything at that point
            return False


        retry_after = datetime.datetime.utcnow() + datetime.timedelta(seconds=self.settings.get("REDIS_RETRY_DELAY"))

        for r in self.retry_list:
            self._add_doc_to_retry_list(r)
            retry_key = self.settings.get("REDIS_RETRY_PREFIX")%r.get("id")
            retry_document.apply_async(args=[self.settings, retry_key, r],
                                       eta=retry_after)

        spider.log("Retry list added to queue", log.INFO)


    def _add_if_to_rety_list(self, item):
        """
        Checks if the items should be added to the retry list
        and if yes, it is added to the redis queue
        """
        if not needs_retry(item):
            return False

        retry_key = self.settings.get("REDIS_RETRY_PREFIX")%item.get("id")
        if self.redis_conn.exists(retry_key):
            #it seems it is already here we won't add it again
            self.log("The item : %s is already in retry queue skipping ",
                       log.WARNING)
            return False


        self.retry_list.append({"id":item["id"],
                                "untracked_url":item["untracked_url"]})

        return True


    def _add_doc_to_retry_list(self, item):
        """
        Adds the doc to retry list in redis
        """
        default_retry_dict  = {
            "url":item.get("untracked_url"),
            "retry_count":self.settings.get("REDIS_RETRY_COUNT"),
            "added":datetime.datetime.utcnow(),
            "status":self.settings.get("REDIS_RETRY_STATUS_READY"),
            "updated":datetime.datetime.utcnow()
        }

        retry_key = self.settings.get("REDIS_RETRY_PREFIX")%item.get("id")
        self.redis_conn.hmset(retry_key,
                              default_retry_dict)

        self.log("The item : %s was added to retry queue "%item["id"],
                 log.INFO)

        #also we should enqueue it at that point
        return True
        #return retry_document.s(self.settings, retry_key, item)
