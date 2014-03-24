import datetime

from scrapy import log

from dealfu_groupon.utils import needs_retry
from dealfu_groupon.background.retry import retry_document
from dealfu_groupon.pipelines.genespipe import BaseEsPipe


class GrouponEsPipeLine(BaseEsPipe):
    """
    Generally inserts data into ES
    and maybe something more !!!
    """

    def open_spider(self, spider):
        """
        Here will initialize some the data
        """
        #call it to init the stuff
        super(GrouponEsPipeLine, self).open_spider(spider)

        #those are your stuff from here
        self.retry_list = []


    def on_duplicate_item(self, item, item_id):
        """
        Some action to be taken on duplication
        """
        self._add_if_to_geo_request(item, item_id)

        return True



    def on_end_processing(self, item, spider):
        """
        Some action to be taken at the end of the processing item
        """
        self._add_if_to_rety_list(item)
        return True



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
