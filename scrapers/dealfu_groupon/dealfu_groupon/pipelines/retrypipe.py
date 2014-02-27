from scrapy.exceptions import DropItem
from scrapy import log

from dealfu_groupon.utils import check_spider_pipeline, get_es


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


    @check_spider_pipeline
    def process_item(self, item, spider):
        """
        Retry specified the specified item
        """

        spider.log("RETRY ITEM : %s "%item["id"], log.INFO)
        return item
